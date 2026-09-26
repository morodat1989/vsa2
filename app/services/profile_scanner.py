import os
import shutil
import sqlite3
import tempfile
import urllib.request
import json
import datetime
import socket
import base64
import struct

def get_profiles_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    profiles_dir = os.path.join(root_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    return profiles_dir

def get_active_profile_name():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    act_file = os.path.join(root_dir, "logs", "active_profile.txt")
    if os.path.exists(act_file):
        try:
            with open(act_file, "r", encoding="utf-8") as f:
                name = f.read().strip()
                if name:
                    return name
        except Exception:
            pass
    return None

def set_active_profile_name(name):
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logs_dir = os.path.join(root_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    act_file = os.path.join(logs_dir, "active_profile.txt")
    try:
        with open(act_file, "w", encoding="utf-8") as f:
            f.write(name.strip())
    except Exception:
        pass

def cdp_send_command(ws_url, method, params=None, timeout=2.0):
    """Gửi lệnh tới Chrome DevTools Protocol qua WebSocket thuần không cần thư viện ngoài"""
    try:
        parts = ws_url.replace("ws://", "").split("/", 1)
        host_port = parts[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 9222
        path = "/" + (parts[1] if len(parts) > 1 else "")

        s = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(handshake.encode('utf-8'))
        
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(1024)
            if not chunk:
                break
            response += chunk

        if b"101" not in response:
            s.close()
            return None

        msg_id = 1
        payload = json.dumps({"id": msg_id, "method": method, "params": params or {}}).encode('utf-8')
        length = len(payload)

        # Chuẩn bị WebSocket frame client -> server
        mask = os.urandom(4)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))

        if length <= 125:
            header = struct.pack('!BB', 0x81, 0x80 | length)
        elif length <= 65535:
            header = struct.pack('!BBH', 0x81, 0x80 | 126, length)
        else:
            header = struct.pack('!BBQ', 0x81, 0x80 | 127, length)

        s.sendall(header + mask + masked)

        # Đọc dữ liệu trả về từ Chrome
        raw_data = b""
        s.settimeout(timeout)
        start_time = datetime.datetime.now()
        while (datetime.datetime.now() - start_time).total_seconds() < timeout:
            chunk = s.recv(4096)
            if not chunk:
                break
            raw_data += chunk
            if len(raw_data) >= 2:
                payload_len = raw_data[1] & 0x7F
                offset = 2
                if payload_len == 126:
                    if len(raw_data) < 4: continue
                    payload_len = struct.unpack('!H', raw_data[2:4])[0]
                    offset = 4
                elif payload_len == 127:
                    if len(raw_data) < 10: continue
                    payload_len = struct.unpack('!Q', raw_data[2:10])[0]
                    offset = 10
                
                if len(raw_data) >= offset + payload_len:
                    body = raw_data[offset:offset+payload_len].decode('utf-8', errors='ignore')
                    res_json = json.loads(body)
                    if res_json.get("id") == msg_id:
                        s.close()
                        return res_json.get("result")
        s.close()
    except Exception as e:
        pass
    return None

def check_cdp_status():
    """Kiểm tra kết nối và trích xuất thông tin tài khoản Facebook trực tiếp từ Ungoogled Chromium"""
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json", headers={"User-Agent": "FBTool"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                fb_tab = None
                for tab in data:
                    url = tab.get("url", "")
                    if "facebook.com" in url:
                        fb_tab = tab
                        break
                
                if not fb_tab:
                    return {
                        "running": True,
                        "tabs_count": len(data),
                        "fb_tab_open": False,
                        "fb_tab_title": None,
                        "fb_tab_url": None,
                        "user_name": None,
                        "c_user": None,
                        "is_logged_in": False
                    }

                tab_title = fb_tab.get("title", "")
                tab_url = fb_tab.get("url", "")
                ws_url = fb_tab.get("webSocketDebuggerUrl")

                user_name = None
                c_user = None
                is_logged_in = False
                is_login_form = False

                # 1. Truy vấn sâu vào DOM và Cookie qua WebSocket CDP
                if ws_url:
                    js_code = """
                    (() => {
                        const isLoginForm = Boolean(
                            document.querySelector('input[name="email"], input#email, input[name="pass"], button[name="login"], form[action*="login"]')
                        );
                        let uid = null;
                        const m = document.cookie.match(/c_user=(\\d+)/);
                        if (m) uid = m[1];
                        
                        let name = null;
                        try {
                            const nameEl = document.querySelector('div[data-pagelet="LeftRail"] a span, a[href*="/me/"] span, [role="navigation"] a span, div[role="banner"] span');
                            if (nameEl) name = nameEl.innerText.trim();
                        } catch(e) {}
                        
                        return JSON.stringify({ 
                            uid: uid, 
                            name: name,
                            is_login_form: isLoginForm 
                        });
                    })()
                    """
                    eval_res = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_code, "returnByValue": True})
                    if eval_res and "result" in eval_res and "value" in eval_res["result"]:
                        try:
                            val = json.loads(eval_res["result"]["value"])
                            c_user = val.get("uid")
                            user_name = val.get("name")
                            is_login_form = val.get("is_login_form", False)
                        except Exception:
                            pass

                # 2. Xác định trạng thái đăng nhập chuẩn xác
                not_logged_phrases = ["đăng nhập", "log in", "login", "explore the things you love"]
                if is_login_form or any(p in tab_title.lower() for p in not_logged_phrases):
                    is_logged_in = False
                elif c_user and str(c_user).isdigit():
                    is_logged_in = True
                elif user_name:
                    is_logged_in = True

                return {
                    "running": True,
                    "tabs_count": len(data),
                    "fb_tab_open": True,
                    "fb_tab_title": tab_title,
                    "fb_tab_url": tab_url,
                    "user_name": user_name,
                    "c_user": c_user,
                    "is_logged_in": is_logged_in
                }
    except Exception:
        pass

    return {
        "running": False,
        "tabs_count": 0,
        "fb_tab_open": False,
        "fb_tab_title": None,
        "fb_tab_url": None,
        "user_name": None,
        "c_user": None,
        "is_logged_in": False
    }

def inspect_profile_cookies(profile_path):
    """Đọc file Cookies của Chromium trong profile để tìm c_user (UID) và trạng thái login Facebook"""
    candidates = [
        os.path.join(profile_path, "Default", "Network", "Cookies"),
        os.path.join(profile_path, "Network", "Cookies"),
        os.path.join(profile_path, "Default", "Cookies"),
        os.path.join(profile_path, "Cookies")
    ]
    
    cookie_file = None
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 0:
            cookie_file = c
            break

    if not cookie_file:
        for root, dirs, files in os.walk(profile_path):
            if "Cookies" in files:
                fpath = os.path.join(root, "Cookies")
                if os.path.getsize(fpath) > 0:
                    cookie_file = fpath
                    break

    if not cookie_file:
        return {
            "has_cookie_db": False,
            "has_fb_login": False,
            "c_user": None,
            "status": "Chưa có dữ liệu duyệt web"
        }

    temp_dir = tempfile.gettempdir()
    temp_copy = os.path.join(temp_dir, f"ck_{os.path.basename(profile_path)}_{os.getpid()}.sqlite")

    c_user_val = None
    has_fb = False

    try:
        shutil.copy2(cookie_file, temp_copy)
        for ext in ["-wal", "-shm"]:
            wal_src = cookie_file + ext
            if os.path.exists(wal_src):
                try:
                    shutil.copy2(wal_src, temp_copy + ext)
                except Exception:
                    pass

        conn = sqlite3.connect(temp_copy)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, value 
            FROM cookies 
            WHERE host_key LIKE '%facebook.com%' AND name IN ('c_user', 'xs')
        """)
        rows = cursor.fetchall()
        for name, value in rows:
            if name == "c_user":
                has_fb = True
                if value and value.strip() and value.strip().isdigit():
                    c_user_val = value.strip()
            elif name == "xs":
                has_fb = True

        conn.close()
    except (PermissionError, OSError):
        # File đang bị Chromium khóa (đang chạy), an toàn bỏ qua vì CDP sẽ đọc từ memory
        return {
            "has_cookie_db": True,
            "has_fb_login": False,
            "c_user": None,
            "status": "Đang mở bởi Chromium"
        }
    except Exception as e:
        pass
    finally:
        if os.path.exists(temp_copy):
            try:
                os.remove(temp_copy)
                for ext in ["-wal", "-shm"]:
                    w = temp_copy + ext
                    if os.path.exists(w):
                        os.remove(w)
            except Exception:
                pass

    if c_user_val:
        return {
            "has_cookie_db": True,
            "has_fb_login": True,
            "c_user": c_user_val,
            "status": "Live"
        }
    else:
        return {
            "has_cookie_db": True,
            "has_fb_login": False,
            "c_user": None,
            "status": "Chưa đăng nhập Facebook"
        }

def scan_all_profiles_detail():
    """Quét toàn bộ danh sách profile và tích hợp trạng thái thời gian thực từ Chromium"""
    profiles_dir = get_profiles_dir()
    profiles = []
    
    cdp = check_cdp_status()
    active_profile = get_active_profile_name()

    if os.path.exists(profiles_dir):
        for name in sorted(os.listdir(profiles_dir)):
            item_path = os.path.join(profiles_dir, name)
            if os.path.isdir(item_path):
                cookie_info = inspect_profile_cookies(item_path)
                try:
                    mtime = os.path.getmtime(item_path)
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    mtime_str = "---"

                is_live = cookie_info["has_fb_login"]
                c_user = cookie_info["c_user"]
                display_name = None

                # Chỉ áp dụng trạng thái live từ Chromium cho profile đang được mở (active)
                is_current_active = (active_profile == name) or (active_profile is None and len(os.listdir(profiles_dir)) == 1)

                if is_current_active and cdp.get("running") and cdp.get("fb_tab_open") and cdp.get("is_logged_in"):
                    is_live = True
                    if cdp.get("c_user"):
                        c_user = cdp.get("c_user")
                    if cdp.get("user_name"):
                        display_name = cdp.get("user_name")
                    elif cdp.get("fb_tab_title"):
                        display_name = cdp.get("fb_tab_title")

                profiles.append({
                    "name": name,
                    "path": item_path,
                    "mtime": mtime_str,
                    "has_cookie_db": cookie_info["has_cookie_db"],
                    "has_fb_login": is_live,
                    "c_user": c_user,
                    "user_name": display_name,
                    "status": "Live" if is_live else "Chưa đăng nhập"
                })

    return {
        "profiles": profiles,
        "cdp": cdp,
        "active_profile": active_profile,
        "live_count": len([p for p in profiles if p["has_fb_login"]])
    }
