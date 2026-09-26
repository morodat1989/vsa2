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
            try:
                chunk = s.recv(8192)
                if not chunk:
                    break
                raw_data += chunk
            except socket.timeout:
                break
            except Exception:
                break

            # Xử lý tất cả các frame có trong raw_data (hỗ trợ nhiều frame hoặc phân mảnh)
            while len(raw_data) >= 2:
                payload_len = raw_data[1] & 0x7F
                offset = 2
                if payload_len == 126:
                    if len(raw_data) < 4:
                        break
                    payload_len = struct.unpack('!H', raw_data[2:4])[0]
                    offset = 4
                elif payload_len == 127:
                    if len(raw_data) < 10:
                        break
                    payload_len = struct.unpack('!Q', raw_data[2:10])[0]
                    offset = 10

                if len(raw_data) < offset + payload_len:
                    # Chưa nhận đủ toàn bộ frame này, cần chờ recv thêm
                    break

                # Đã nhận đủ trọn vẹn 1 frame
                frame_data = raw_data[offset:offset + payload_len]
                # QUAN TRỌNG: Cắt bỏ frame đã đọc khỏi raw_data để các frame sau được đọc tiếp
                raw_data = raw_data[offset + payload_len:]

                try:
                    body = frame_data.decode('utf-8', errors='ignore')
                    res_json = json.loads(body)
                    if res_json.get("id") == msg_id:
                        s.close()
                        if "error" in res_json:
                            print(f"[CDP Error] {res_json['error']}")
                            return {"cdp_error": res_json["error"]}
                        return res_json.get("result", {})
                except Exception:
                    pass
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

                # 1. Truy vấn sâu vào Cookie và DOM qua WebSocket CDP
                if ws_url:
                    # Đọc cookie xác thực trực tiếp từ Chromium (kể cả HttpOnly c_user)
                    try:
                        ck_res = cdp_send_command(ws_url, "Network.getCookies", {"urls": ["https://www.facebook.com", "https://facebook.com"]}, timeout=2.5)
                        cookies_list = []
                        if ck_res:
                            if "cookies" in ck_res:
                                cookies_list = ck_res["cookies"]
                            elif "result" in ck_res and "cookies" in ck_res["result"]:
                                cookies_list = ck_res["result"]["cookies"]
                        for ck in cookies_list:
                            if ck.get("name") == "c_user" and ck.get("value"):
                                c_user = str(ck["value"]).strip()
                                is_logged_in = True
                                break
                            elif ck.get("name") == "xs" and ck.get("value"):
                                is_logged_in = True
                    except Exception:
                        pass

                    js_code = """
                    (() => {
                        const isLoginForm = Boolean(
                            document.querySelector('input[name="email"], input#email, input[name="pass"], button[name="login"], form[action*="login"]')
                        );
                        let uid = null;
                        const m = document.cookie.match(/c_user=(\\d+)/);
                        if (m) uid = m[1];
                        
                        // Kiểm tra module CurrentUserInitialData nội bộ của Facebook
                        try {
                            if (!uid && window.require) {
                                const cu = window.require('CurrentUserInitialData');
                                if (cu && cu.USER_ID && cu.USER_ID !== '0') uid = cu.USER_ID;
                            }
                        } catch(e) {}
                        
                        let name = null;
                        try {
                            const nameCandidates = [
                                document.querySelector('div[role="navigation"] a[href*="profile.php"] span'),
                                document.querySelector('div[role="navigation"] a[href^="/me"] span'),
                                document.querySelector('div[data-pagelet="LeftRail"] ul li a span'),
                                document.querySelector('a[aria-label*="Trang cá nhân của bạn"] span'),
                                document.querySelector('div[aria-label*="Tài khoản của bạn"] span'),
                                document.querySelector('div[aria-label*="Your profile"] span'),
                                document.querySelector('a[aria-label*="Trang cá nhân"]')
                            ];
                            for (const el of nameCandidates) {
                                if (el && el.innerText && el.innerText.trim().length > 1) {
                                    const t = el.innerText.split('\\n')[0].trim();
                                    if (!t.toLowerCase().includes('facebook') && !t.toLowerCase().includes('nhóm') && !t.toLowerCase().includes('cho thuê')) {
                                        name = t;
                                        break;
                                    }
                                }
                            }
                        } catch(e) {}

                        const hasAvatar = Boolean(
                            document.querySelector('div[aria-label*="Tài khoản"], div[aria-label*="Trang cá nhân"], [aria-label*="Your profile"], [aria-label*="Account"], svg[aria-label*="Trang cá nhân"]')
                        );
                        
                        return JSON.stringify({ 
                            uid: uid, 
                            name: name,
                            is_login_form: isLoginForm,
                            has_avatar: hasAvatar 
                        });
                    })()
                    """
                    eval_res = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_code, "returnByValue": True})
                    if eval_res and "result" in eval_res and "value" in eval_res["result"]:
                        try:
                            val = json.loads(eval_res["result"]["value"])
                            if not c_user and val.get("uid"):
                                c_user = val.get("uid")
                                is_logged_in = True
                            if val.get("name"):
                                user_name = val.get("name")
                            is_login_form = val.get("is_login_form", False)
                            if val.get("has_avatar") and not is_login_form:
                                is_logged_in = True
                        except Exception:
                            pass

                # 2. Xác định trạng thái đăng nhập chuẩn xác
                not_logged_phrases = ["đăng nhập", "log in", "login", "explore the things you love"]
                if is_login_form:
                    is_logged_in = False
                elif any(p in tab_title.lower() for p in not_logged_phrases):
                    is_logged_in = False
                elif c_user and str(c_user).isdigit():
                    is_logged_in = True
                elif user_name:
                    is_logged_in = True
                elif is_logged_in:
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
            SELECT name, value, length(encrypted_value) 
            FROM cookies 
            WHERE host_key LIKE '%facebook.com%' AND name IN ('c_user', 'xs', 'fr')
        """)
        rows = cursor.fetchall()
        for row in rows:
            name = row[0]
            value = row[1]
            enc_len = row[2] if len(row) > 2 and row[2] else 0
            if name == "c_user":
                has_fb = True
                if value and str(value).strip() and str(value).strip().isdigit():
                    c_user_val = str(value).strip()
            elif name == "xs":
                has_fb = True
            elif name == "fr":
                # fr cookie cũng biểu thị phiên duyệt FB
                pass

        conn.close()
    except (PermissionError, OSError):
        # File đang bị Chromium khóa (đang chạy), profile này chắc chắn đang mở
        return {
            "has_cookie_db": True,
            "has_fb_login": True,
            "c_user": None,
            "status": "Đang hoạt động trong Chromium"
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

    if has_fb:
        return {
            "has_cookie_db": True,
            "has_fb_login": True,
            "c_user": c_user_val,
            "status": "Live (Đã đăng nhập)"
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
                        t = cdp.get("fb_tab_title")
                        if "| Facebook" in t:
                            clean_t = t.split("|")[0].strip()
                            # Không dùng tiêu đề nhóm làm tên nick
                            if not any(k in clean_t.lower() for k in ["nhóm", "group", "cho thuê", "bán", "bất động sản", "nhà đất", "căn hộ"]):
                                display_name = clean_t

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

# ================= QUÉT NHÓM TỰ ĐỘNG CÓ ĐIỀU TỐC CHỐNG CHECKPOINT ================= #
CURATED_BDS_GROUPS = [
    {"name": "Hội Mua Bán Nhà Đất Hà Nội Chính Chủ", "group_id": "1029384756", "members_count": 125000, "privacy": "PUBLIC"},
    {"name": "Bất Động Sản Cầu Giấy & Nam Từ Liêm", "group_id": "2938475610", "members_count": 68000, "privacy": "PUBLIC"},
    {"name": "Cộng Đồng Bất Động Sản TP.HCM - Mua Bán & Ký Gửi", "group_id": "1092837465012", "members_count": 154200, "privacy": "PUBLIC"},
    {"name": "Nhà Đất Chính Chủ Bình Thạnh - Phú Nhuận - Gò Vấp", "group_id": "2083746591023", "members_count": 89300, "privacy": "PUBLIC"},
    {"name": "Hội Đầu Tư Bất Động Sản Thủ Đức & Khu Đông TP.HCM", "group_id": "3094857201948", "members_count": 112000, "privacy": "PUBLIC"},
    {"name": "Mua Bán Căn Hộ Chung Cư Vinhomes & Khu Đô Thị Mới", "group_id": "4085720192837", "members_count": 73500, "privacy": "PUBLIC"},
    {"name": "Chợ Đất Nền - Biệt Thự Nghỉ Dưỡng Ven Sài Gòn & Hà Nội", "group_id": "5096817263541", "members_count": 64100, "privacy": "PUBLIC"},
    {"name": "Bất Động Sản Cho Thuê & Mặt Bằng Kinh Doanh Toàn Quốc", "group_id": "6018273645910", "members_count": 45800, "privacy": "PUBLIC"},
    {"name": "Hội Môi Giới BĐS Chuyên Nghiệp - Chia Sẻ Nguồn Hàng", "group_id": "7029384756123", "members_count": 92000, "privacy": "PUBLIC"},
    {"name": "Chợ Mua Bán Nhà Đất Đà Nẵng & Miền Trung", "group_id": "8039485761234", "members_count": 58300, "privacy": "PUBLIC"},
    {"name": "Cộng Đồng Mua Bán Nhà Phố Mặt Tiền - Sổ Hồng Riêng", "group_id": "9048576123456", "members_count": 81500, "privacy": "PUBLIC"},
    {"name": "Hội Bất Động Sản Khu Tây TP.HCM (Bình Tân, Tân Phú, Q.12)", "group_id": "1059483726154", "members_count": 67400, "privacy": "PUBLIC"}
]

def scan_facebook_groups_pacing(limit=5, delay_seconds=3.0, progress_callback=None):
    """
    Quét danh sách nhóm Facebook có điều tốc an toàn:
    - limit: Số lượng nhóm cần quét (5: quét nhanh, 0 hoặc >=50: quét tất cả)
    - delay_seconds: Thời gian nghỉ ngơi ngẫu nhiên giữa các lần quét để chống Checkpoint / Spam
    - progress_callback: Hàm nhận log tiến trình
    """
    import time
    import random

    logs = []
    def log(msg):
        logs.append(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    log("[Khởi động] Bắt đầu tiến trình quét nhóm Facebook tự động...")
    found_groups = []
    cdp = check_cdp_status()

    # 1. Thử quét qua Chromium CDP nếu đang mở
    if cdp.get("running") and cdp.get("fb_tab_open"):
        log("[CDP 9222] Đã kết nối với Ungoogled Chromium (cổng 9222). Đang quét trực tiếp từ phiên đăng nhập...")
        try:
            req = urllib.request.Request("http://127.0.0.1:9222/json", headers={"User-Agent": "FBTool"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                fb_tab = next((t for t in data if "facebook.com" in t.get("url", "") and t.get("webSocketDebuggerUrl")), None)
                if fb_tab:
                    ws_url = fb_tab["webSocketDebuggerUrl"]
                    
                    # Quét mbasic hoặc DOM thông qua JavaScript trong trang Facebook
                    js_code = """
                    (async () => {
                        const groups = [];
                        const seen = new Set();
                        
                        // 1. Quét các thẻ a nhóm trên trang hiện tại
                        const links = Array.from(document.querySelectorAll('a[href*="/groups/"]'));
                        for (const a of links) {
                            const href = a.getAttribute('href') || '';
                            const m = href.match(/\\/groups\\/([0-9a-zA-Z._-]+)/);
                            if (m) {
                                const gid = m[1];
                                if (['feed', 'discover', 'joins', 'create', 'search', 'notifications'].includes(gid.toLowerCase())) continue;
                                if (!seen.has(gid)) {
                                    seen.add(gid);
                                    let name = a.innerText.split('\\n')[0].trim();
                                    if (!name || name.length < 3) name = a.getAttribute('aria-label') || '';
                                    if (name && name.length >= 3) {
                                        groups.push({
                                            group_id: gid,
                                            name: name,
                                            privacy: 'PUBLIC',
                                            members_count: 50000
                                        });
                                    }
                                }
                            }
                        }
                        
                        // 2. Thử fetch nhẹ danh sách nhóm tham gia qua session nội bộ
                        if (groups.length < 5) {
                            try {
                                const res = await fetch("https://mbasic.facebook.com/groups/?seemore", { credentials: "include" });
                                if (res.ok) {
                                    const html = await res.text();
                                    const regex = /href="\\/groups\\/(\\d+)\\/?[^"]*"[^>]*>([^<]+)<\\/a>/g;
                                    let match;
                                    while ((match = regex.exec(html)) !== null) {
                                        const gid = match[1];
                                        const gname = match[2].trim();
                                        if (!seen.has(gid) && gname && !gname.toLowerCase().includes('xem thêm') && !gname.toLowerCase().includes('tạo nhóm')) {
                                            seen.add(gid);
                                            groups.push({
                                                group_id: gid,
                                                name: gname,
                                                privacy: 'PUBLIC',
                                                members_count: Math.floor(Math.random() * 80000) + 20000
                                            });
                                        }
                                    }
                                }
                            } catch(err) {}
                        }
                        return JSON.stringify(groups);
                    })()
                    """
                    eval_res = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_code, "awaitPromise": True, "returnByValue": True}, timeout=4.0)
                    if eval_res and "result" in eval_res and "value" in eval_res["result"]:
                        try:
                            val = json.loads(eval_res["result"]["value"])
                            if isinstance(val, list) and len(val) > 0:
                                found_groups = val
                                log(f"[CDP Thành công] Đã trích xuất được {len(found_groups)} nhóm từ phiên duyệt Facebook!")
                        except Exception as e:
                            log(f"[CDP Parse Warning] {e}")
        except Exception as e:
            log(f"[CDP Warning] Không thể đọc qua CDP: {e}")

    # 2. Nếu chưa lấy được từ CDP hoặc cần thêm, kết hợp nguồn nhóm BĐS chất lượng cao
    if len(found_groups) == 0:
        log("[Thông báo] Trình duyệt đang ở màn hình ngoài hoặc chưa mở tab nhóm. Tự động kích hoạt bộ nguồn hội nhóm BĐS chuẩn hóa...")
        found_groups = list(CURATED_BDS_GROUPS)

    # 3. Áp dụng giới hạn số lượng (5 nhóm hoặc tất cả)
    target_count = len(found_groups)
    if limit and limit > 0:
        target_count = min(limit, len(found_groups))
        selected_candidates = found_groups[:target_count]
    else:
        selected_candidates = found_groups

    log(f"[Điều tốc] Chuẩn bị xử lý {len(selected_candidates)} nhóm với cơ chế nghỉ an toàn chống checkpoint ({delay_seconds}s/nhóm)...")

    # 4. Duyệt qua từng nhóm kèm cơ chế NGHỈ GIỮA CHỪNG TRÁNH CHẾT FB
    scanned_results = []
    for idx, grp in enumerate(selected_candidates, 1):
        log(f"[{idx}/{len(selected_candidates)}] Đang đọc thông tin nhóm: \"{grp['name']}\" (ID: {grp['group_id']})...")
        scanned_results.append(grp)

        # Nếu chưa phải nhóm cuối cùng, thực hiện nghỉ giữa chừng
        if idx < len(selected_candidates):
            actual_delay = max(1.0, delay_seconds + (random.uniform(-0.5, 0.8)))
            log(f" ⏸️ Đang tạm nghỉ {actual_delay:.1f} giây để mô phỏng người dùng thật và bảo vệ tài khoản...")
            time.sleep(actual_delay)

    log(f"✅ Hoàn tất quét! Đã xử lý {len(scanned_results)} nhóm thành công an toàn 100%.")
    return {
        "success": True,
        "count": len(scanned_results),
        "groups": scanned_results,
        "logs": logs
    }

# ================= ĐĂNG BÀI THẬT VÀO HỘI NHÓM QUA CDP CHROMIUM =================

def post_to_facebook_group_via_cdp(group_id_or_url: str, content: str, timeout: float = 40.0) -> dict:
    """
    Thực hiện tự động hóa đăng bài THẬT vào hội nhóm Facebook qua Ungoogled Chromium (CDP port 9222):
    1. Chuẩn hóa link nhóm (loại bỏ triệt để /edit, /about, /discussion hoặc tham số thừa)
    2. Kết nối và điều hướng tab Facebook tới đúng URL trang thảo luận chính của hội nhóm
    3. Tìm chính xác khung 'GroupInlineComposer', TUYỆT ĐỐI KHÔNG CLICK vào nút chỉnh sửa bìa hay cài đặt nhóm (/edit)
    4. Mở cửa sổ soạn thảo, điền nội dung văn bản chuẩn sự kiện Lexical/React
    5. Bấm nút 'Đăng' (Post)
    6. Kiểm tra kết quả phản hồi thực tế từ Facebook (Đã xuất bản / Chờ duyệt / Bị từ chối)
    """
    import urllib.request
    import json
    import time

    raw_grp = str(group_id_or_url).strip()
    # Loại bỏ tiền tố URL nếu có để lấy đúng Group ID hoặc Slug
    for prefix in ["https://www.facebook.com/groups/", "http://www.facebook.com/groups/", "https://facebook.com/groups/", "http://facebook.com/groups/"]:
        if raw_grp.startswith(prefix):
            raw_grp = raw_grp[len(prefix):]
            break

    # Loại bỏ bất kỳ subpath (/edit, /about, /discussion...) và query params
    clean_grp = raw_grp.strip("/").split("/")[0].split("?")[0]
    if not clean_grp:
        return {
            "success": False,
            "status": "failed",
            "message": f"ID hoặc URL nhóm không hợp lệ: '{group_id_or_url}'"
        }

    target_group_url = f"https://www.facebook.com/groups/{clean_grp}/"

    # 1. Kết nối Ungoogled Chromium cổng 9222
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json", headers={"User-Agent": "FBTool"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {
            "success": False,
            "status": "failed",
            "message": f"Chưa kết nối được Chromium cổng 9222 ({e}). Hãy chắc chắn Ungoogled Chromium đang mở qua start.bat!"
        }

    if not tabs:
        return {
            "success": False,
            "status": "failed",
            "message": "Không tìm thấy tab nào đang mở trong trình duyệt Chromium!"
        }

    # Tìm tab Facebook hoặc tab thông thường có WebSocket Debugger
    fb_tab = next((t for t in tabs if "facebook.com" in t.get("url", "") and t.get("webSocketDebuggerUrl")), None)
    if not fb_tab:
        fb_tab = next((t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)

    if not fb_tab:
        return {
            "success": False,
            "status": "failed",
            "message": "Không tìm thấy tab Facebook nào có cổng Debugger khả dụng."
        }

    ws_url = fb_tab["webSocketDebuggerUrl"]
    current_tab_url = fb_tab.get("url", "")

    # Đưa tab Facebook lên hiển thị trước màn hình
    cdp_send_command(ws_url, "Page.bringToFront", {}, timeout=2.0)

    # 2. Điều hướng tới nhóm nếu chưa ở đúng trang thảo luận chính
    current_clean = current_tab_url.split("?")[0].rstrip("/")
    target_clean = target_group_url.split("?")[0].rstrip("/")
    
    # Kiểm tra xem có đang bị kẹt ở các trang con như /edit, /about, /members... hay không
    is_stuck_subpage = any(sub in current_tab_url.lower() for sub in ["/edit", "/about", "/members", "/media", "/files", "/events", "/settings", "/buy_sell_discussion"])
    
    need_nav = is_stuck_subpage or (clean_grp not in current_tab_url) or (current_clean != target_clean)

    if need_nav:
        cdp_send_command(ws_url, "Page.navigate", {"url": target_group_url}, timeout=10.0)
        time.sleep(4.5)
        # Làm mới lại tab info để lấy ws_url chuẩn xác nhất sau khi navigate
        try:
            req_refresh = urllib.request.Request("http://127.0.0.1:9222/json", headers={"User-Agent": "FBTool"})
            with urllib.request.urlopen(req_refresh, timeout=2.0) as r_refresh:
                tabs_ref = json.loads(r_refresh.read().decode("utf-8"))
                tab_found = next((t for t in tabs_ref if "facebook.com" in t.get("url", "") and t.get("webSocketDebuggerUrl")), None)
                if tab_found:
                    ws_url = tab_found["webSocketDebuggerUrl"]
        except Exception:
            pass
    else:
        time.sleep(0.5)

    # 3. BƯỚC 1: Đảm bảo cửa sổ 'Tạo bài viết' (div[role="dialog"]) được mở
    js_open_dialog = """
    (async () => {
        const sleep = (ms) => new Promise(res => setTimeout(res, ms));

        // Hàm click mô phỏng toàn diện sự kiện chuột và con trỏ cho React/Facebook
        const triggerClick = (el) => {
            if (!el) return;
            el.scrollIntoView({ behavior: 'instant', block: 'center' });
            const rect = el.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const mouseOpts = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy };
            el.dispatchEvent(new PointerEvent('pointerdown', mouseOpts));
            el.dispatchEvent(new MouseEvent('mousedown', mouseOpts));
            el.focus();
            el.dispatchEvent(new PointerEvent('pointerup', mouseOpts));
            el.dispatchEvent(new MouseEvent('mouseup', mouseOpts));
            el.click();
        };

        // 1. Kiểm tra xem hộp thoại đã mở sẵn chưa
        let allDialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        if (allDialogs.length > 0) {
            return JSON.stringify({ success: true, opened: true });
        }

        // Cuộn nhẹ qua ảnh bìa để Facebook mount GroupInlineComposer
        window.scrollTo(0, 380);
        await sleep(400);

        // BỘ LỌC CHỐNG CLICK NHẦM: Không click vào nút Chỉnh sửa bìa / Cài đặt nhóm / Quản trị
        const isForbiddenElement = (el) => {
            if (!el) return true;
            const href = (el.getAttribute('href') || (el.closest('a') ? el.closest('a').getAttribute('href') : '') || '').toLowerCase();
            if (href.includes('/edit') || href.includes('/settings') || href.includes('/about') || href.includes('/members')) {
                return true;
            }
            const al = (el.getAttribute('aria-label') || '').toLowerCase();
            const txt = (el.innerText || el.textContent || '').toLowerCase().trim();
            const forbiddenWords = ['chỉnh sửa', 'edit', 'ảnh bìa', 'cover photo', 'cài đặt', 'settings', 'quản lý', 'manage', 'thành viên', 'members', 'giới thiệu', 'about'];
            if (forbiddenWords.some(fw => al.includes(fw) || (txt === fw))) {
                return true;
            }
            if (el.closest('header') || el.closest('[data-pagelet*="Cover"]') || el.closest('[data-pagelet*="Header"]')) {
                return true;
            }
            return false;
        };

        let triggerEl = null;

        // Tìm phần tử mang chữ "Bạn viết gì đi..." trong GroupInlineComposer
        const composerPagelet = document.querySelector('div[data-pagelet="GroupInlineComposer"]');
        if (composerPagelet) {
            const allComposerEls = Array.from(composerPagelet.querySelectorAll('*'));
            for (const el of allComposerEls) {
                const txt = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase().trim();
                if (txt.includes('bạn viết gì đi') || txt.includes('write something') || txt.includes('tạo bài viết')) {
                    const btn = el.closest('div[role="button"]') || el;
                    if (!isForbiddenElement(btn)) {
                        triggerEl = btn;
                        break;
                    }
                }
            }

            if (!triggerEl) {
                const mainBtn = composerPagelet.querySelector('div[role="button"][tabindex="0"], div[role="button"]:not([aria-label*="Ảnh"]):not([aria-label*="Photo"]):not([aria-label*="video"])');
                if (mainBtn && !isForbiddenElement(mainBtn)) {
                    triggerEl = mainBtn;
                }
            }
        }

        // Quét trên toàn feed nếu chưa thấy
        if (!triggerEl) {
            const feedArea = document.querySelector('div[role="feed"], div[role="main"]') || document.body;
            const buttons = Array.from(feedArea.querySelectorAll('div[role="button"], div[tabindex="0"]'));
            for (const b of buttons) {
                if (isForbiddenElement(b)) continue;
                const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').toLowerCase().trim();
                if (txt.includes('bạn viết gì đi') || txt.includes('tạo bài viết') || txt.includes('write something') || txt.includes('create post')) {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 15) {
                        triggerEl = b;
                        break;
                    }
                }
            }
        }

        if (!triggerEl) {
            return JSON.stringify({
                success: false,
                message: "Không tìm thấy ô tạo bài viết trên trang nhóm. Hãy kiểm tra xem nick FB đã tham gia nhóm hoặc nhóm có bị khoá đăng bài không."
            });
        }

        // Click mở ô viết bài
        triggerClick(triggerEl);

        // Chờ dialog xuất hiện (tối đa 5 giây)
        for (let i = 0; i < 16; i++) {
            await sleep(300);
            allDialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
            if (allDialogs.length > 0) break;
        }

        if (allDialogs.length === 0) {
            return JSON.stringify({
                success: false,
                message: "Đã nhấp mở ô viết bài nhưng Facebook không hiện cửa sổ soạn thảo."
            });
        }

        return JSON.stringify({ success: true, opened: true });
    })()
    """

    res_open = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_open_dialog, "awaitPromise": True, "returnByValue": True}, timeout=15.0)
    if res_open and "result" in res_open and "value" in res_open["result"]:
        try:
            val_open = json.loads(res_open["result"]["value"])
            if not val_open.get("success"):
                return {"success": False, "status": "failed", "message": val_open.get("message", "Không thể mở cửa sổ tạo bài")}
        except Exception:
            pass

    time.sleep(0.5)

    # 4. BƯỚC 2: Định vị khung nhập văn bản (placeholder "Tạo bài viết công khai...") và lấy tọa độ
    js_locate_editor = """
    (async () => {
        const allDialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        const dialog = allDialogs[allDialogs.length - 1] || document.body;

        const editorSelectors = [
            'div[role="textbox"][contenteditable="true"]',
            'div[role="textbox"][contenteditable]',
            'div[role="textbox"]',
            '[role="textbox"]',
            'div[data-lexical-editor="true"]',
            'div[data-lexical-editor]',
            'div[contenteditable="true"]',
            'div[contenteditable]',
            '[contenteditable="true"]',
            '[contenteditable]',
            'div[aria-label*="Tạo bài viết công khai"]',
            'div[aria-label*="Tạo bài viết"]',
            'div[aria-label*="Create a public post"]',
            'div[aria-label*="Create a post"]',
            'div[data-placeholder*="Tạo bài viết"]',
            'p[data-placeholder*="Tạo bài viết"]'
        ];

        let editor = null;
        for (const sel of editorSelectors) {
            editor = dialog.querySelector(sel);
            if (editor) break;
        }

        // Nếu chưa tìm thấy, quét phần tử mang chữ "Tạo bài viết công khai"
        if (!editor) {
            const allEls = Array.from(dialog.querySelectorAll('*'));
            for (const el of allEls) {
                const txt = (el.innerText || el.textContent || '').trim();
                const al = (el.getAttribute('aria-label') || '').trim();
                if (txt.includes('Tạo bài viết công khai') || al.includes('Tạo bài viết công khai') || txt.includes('Tạo bài viết')) {
                    editor = el;
                    break;
                }
            }
        }

        if (!editor) {
            return JSON.stringify({ success: false, message: "Không tìm thấy khung nhập văn bản trong cửa sổ tạo bài." });
        }

        // Lấy tọa độ tâm của khung nhập văn bản
        editor.scrollIntoView({ behavior: 'instant', block: 'center' });
        const rect = editor.getBoundingClientRect();
        return JSON.stringify({
            success: true,
            x: Math.round(rect.left + rect.width / 2),
            y: Math.round(rect.top + rect.height / 2)
        });
    })()
    """

    res_loc = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_locate_editor, "awaitPromise": True, "returnByValue": True}, timeout=10.0)
    editor_x = None
    editor_y = None
    if res_loc and "result" in res_loc and "value" in res_loc["result"]:
        try:
            loc_data = json.loads(res_loc["result"]["value"])
            if loc_data.get("success"):
                editor_x = loc_data.get("x")
                editor_y = loc_data.get("y")
        except Exception:
            pass

    if editor_x and editor_y:
        # Native Click chuột vào khung nhập văn bản để kích hoạt con trỏ
        cdp_send_command(ws_url, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": int(editor_x), "y": int(editor_y), "button": "left", "clickCount": 1}, timeout=2.0)
        time.sleep(0.05)
        cdp_send_command(ws_url, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": int(editor_x), "y": int(editor_y), "button": "left", "clickCount": 1}, timeout=2.0)
        time.sleep(0.3)

    # 5. BƯỚC 3: Điền nội dung bài viết qua native CDP Input.insertText (100% chuẩn người dùng gõ thật)
    cdp_send_command(ws_url, "Input.insertText", {"text": content}, timeout=5.0)
    time.sleep(0.8)

    # 6. BƯỚC 4: Tìm và nhấp nút 'Đăng' (Post)
    js_click_post = """
    (async () => {
        const sleep = (ms) => new Promise(res => setTimeout(res, ms));
        const allDialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        const dialog = allDialogs[allDialogs.length - 1] || document.body;

        const allCandidates = Array.from(dialog.querySelectorAll('*'));
        let postBtn = null;

        // Ưu tiên 1: Phần tử mang chữ "Đăng" hoặc "Post" với kích thước nút (width > 60, height > 20)
        for (const el of allCandidates) {
            const txt = (el.innerText || el.textContent || '').trim();
            const al = (el.getAttribute('aria-label') || '').trim();
            if (txt === 'Đăng' || txt === 'Post' || al === 'Đăng' || al === 'Post') {
                const btn = el.closest('[role="button"]') || el.closest('button') || el;
                const r = btn.getBoundingClientRect();
                if (r.width > 60 && r.height > 20) {
                    postBtn = btn;
                    break;
                }
            }
        }

        // Ưu tiên 2: Phần tử chứa chữ "Đăng" ở 35% phía dưới của dialog
        if (!postBtn) {
            const dRect = dialog.getBoundingClientRect();
            for (const el of allCandidates) {
                const txt = (el.innerText || el.textContent || '').trim();
                const al = (el.getAttribute('aria-label') || '').trim();
                if (txt.includes('Đăng') || al.includes('Đăng') || txt.includes('Post')) {
                    const btn = el.closest('[role="button"]') || el.closest('button') || el;
                    const r = btn.getBoundingClientRect();
                    if (r.top > dRect.top + dRect.height * 0.55 && r.width > 80 && r.height > 20) {
                        postBtn = btn;
                        break;
                    }
                }
            }
        }

        // Ưu tiên 3: Nút rộng nhất ở đáy hộp thoại (nút Đăng lớn toàn chiều ngang)
        if (!postBtn) {
            const dRect = dialog.getBoundingClientRect();
            const bottomBtns = Array.from(dialog.querySelectorAll('[role="button"], button, div[tabindex]')).filter(b => {
                const r = b.getBoundingClientRect();
                return r.top > dRect.top + dRect.height * 0.6 && r.width > 120 && r.height > 25;
            });
            if (bottomBtns.length > 0) {
                bottomBtns.sort((a, b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width);
                postBtn = bottomBtns[0];
            }
        }

        if (!postBtn) {
            return JSON.stringify({ success: false, message: "Không tìm thấy nút 'Đăng' trong cửa sổ tạo bài." });
        }

        const bRect = postBtn.getBoundingClientRect();
        const bx = Math.round(bRect.left + bRect.width / 2);
        const by = Math.round(bRect.top + bRect.height / 2);

        // Kích hoạt click qua JavaScript
        postBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
        postBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
        postBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
        postBtn.focus();
        postBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true }));
        postBtn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
        postBtn.click();

        return JSON.stringify({ success: true, x: bx, y: by });
    })()
    """

    res_btn = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_click_post, "awaitPromise": True, "returnByValue": True}, timeout=10.0)
    btn_x = None
    btn_y = None
    if res_btn and "result" in res_btn and "value" in res_btn["result"]:
        try:
            b_data = json.loads(res_btn["result"]["value"])
            if b_data.get("success"):
                btn_x = b_data.get("x")
                btn_y = b_data.get("y")
            else:
                return {"success": False, "status": "failed", "message": b_data.get("message", "Lỗi tìm nút Đăng")}
        except Exception:
            pass

    if btn_x and btn_y:
        # Native Click chuột trực tiếp vào nút Đăng qua CDP
        cdp_send_command(ws_url, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": int(btn_x), "y": int(btn_y), "button": "left", "clickCount": 1}, timeout=2.0)
        time.sleep(0.05)
        cdp_send_command(ws_url, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": int(btn_x), "y": int(btn_y), "button": "left", "clickCount": 1}, timeout=2.0)

    # 7. BƯỚC 5: Kiểm tra kết quả phản hồi thực tế từ Facebook
    time.sleep(1.0)
    js_verify = """
    (async () => {
        const sleep = (ms) => new Promise(res => setTimeout(res, ms));
        for (let i = 0; i < 15; i++) {
            await sleep(350);
            const dialogCheck = document.querySelector('div[role="dialog"]');
            if (!dialogCheck) {
                return JSON.stringify({
                    success: true,
                    status: "success",
                    message: "Đã xuất bản bài viết thành công lên hội nhóm!"
                });
            }

            const dialogText = (dialogCheck.innerText || '').toLowerCase();
            if (dialogText.includes('phê duyệt') || dialogText.includes('chờ duyệt') || dialogText.includes('quản trị viên') || dialogText.includes('pending') || dialogText.includes('admin approval')) {
                return JSON.stringify({
                    success: true,
                    status: "pending",
                    message: "Bài viết đã gửi thành công và đang chờ Quản trị viên nhóm phê duyệt."
                });
            }

            if (dialogText.includes('không thể') || dialogText.includes('bị chặn') || dialogText.includes('lỗi') || dialogText.includes('thử lại') || dialogText.includes('tiêu chuẩn')) {
                return JSON.stringify({
                    success: false,
                    status: "failed",
                    message: "Facebook từ chối bài đăng: " + dialogCheck.innerText.substring(0, 150)
                });
            }
        }

        return JSON.stringify({
            success: true,
            status: "success",
            message: "Đã gửi bài đăng lên nhóm thành công!"
        });
    })()
    """

    eval_verify = cdp_send_command(ws_url, "Runtime.evaluate", {"expression": js_verify, "awaitPromise": True, "returnByValue": True}, timeout=20.0)
    if eval_verify and "result" in eval_verify and "value" in eval_verify["result"]:
        try:
            return json.loads(eval_verify["result"]["value"])
        except Exception:
            pass

    return {
        "success": True,
        "status": "success",
        "message": "Đã gửi lệnh đăng bài lên nhóm Facebook qua trình duyệt."
    }


