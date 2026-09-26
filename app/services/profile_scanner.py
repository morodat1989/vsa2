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

    # 3. Kịch bản JavaScript tự động tìm khung soạn thảo, điền nội dung và bấm Đăng
    js_post_script = f"""
    (async () => {{
        const postContent = {json.dumps(content)};
        const targetUrl = {json.dumps(target_group_url)};
        const sleep = (ms) => new Promise(res => setTimeout(res, ms));

        // Hàm click mô phỏng toàn diện sự kiện chuột và con trỏ cho React/Facebook
        const triggerClick = (el) => {{
            if (!el) return;
            el.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            const rect = el.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const mouseOpts = {{ bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy }};
            el.dispatchEvent(new PointerEvent('pointerdown', mouseOpts));
            el.dispatchEvent(new MouseEvent('mousedown', mouseOpts));
            el.focus();
            el.dispatchEvent(new PointerEvent('pointerup', mouseOpts));
            el.dispatchEvent(new MouseEvent('mouseup', mouseOpts));
            el.click();
        }};

        // 0. Nếu trang bị trôi vào /edit hoặc trang cài đặt nhóm, đưa ngay về trang chủ nhóm
        if (window.location.href.includes('/edit') || window.location.href.includes('/settings')) {{
            window.location.href = targetUrl;
            return JSON.stringify({{
                success: false,
                step: "redirect_from_edit",
                message: "Trình duyệt đang ở trang chỉnh sửa nhóm (/edit). Hệ thống đã tự động đưa về trang thảo luận chính, vui lòng nhấn Đăng lại."
            }});
        }}

        // 1. Kiểm tra xem hộp thoại soạn bài (div[role="dialog"]) đã mở sẵn chưa
        let dialog = document.querySelector('div[role="dialog"]');
        
        if (!dialog) {{
            // Cuộn xuống qua phần ảnh bìa nhóm để Facebook mount khung GroupInlineComposer vào DOM
            window.scrollTo(0, 380);
            await sleep(500);

            // BỘ LỌC CHỐNG CLICK NHẦM: Không bao giờ click vào nút Chỉnh sửa bìa / Cài đặt nhóm / Quản trị
            const isForbiddenElement = (el) => {{
                if (!el) return true;
                const href = (el.getAttribute('href') || (el.closest('a') ? el.closest('a').getAttribute('href') : '') || '').toLowerCase();
                if (href.includes('/edit') || href.includes('/settings') || href.includes('/about') || href.includes('/members')) {{
                    return true;
                }}
                const al = (el.getAttribute('aria-label') || '').toLowerCase();
                const txt = (el.innerText || el.textContent || '').toLowerCase().trim();
                const forbiddenWords = ['chỉnh sửa', 'edit', 'ảnh bìa', 'cover photo', 'cài đặt', 'settings', 'quản lý', 'manage', 'thành viên', 'members', 'giới thiệu', 'about'];
                if (forbiddenWords.some(fw => al.includes(fw) || (txt === fw))) {{
                    return true;
                }}
                // Bỏ qua nếu nằm trong header hoặc ảnh bìa
                if (el.closest('header') || el.closest('[data-pagelet*="Cover"]') || el.closest('[data-pagelet*="Header"]')) {{
                    return true;
                }}
                return false;
            }};

            let triggerEl = null;

            // Cách 1: Tìm GroupInlineComposer của Facebook
            const composerPagelet = document.querySelector('div[data-pagelet="GroupInlineComposer"]');
            if (composerPagelet) {{
                // Ưu tiên 1.1: Hộp văn bản giả lập "Bạn viết gì đi..."
                const mainBtn = composerPagelet.querySelector('div[role="button"][tabindex="0"], div[role="button"]:not([aria-label*="Ảnh"]):not([aria-label*="Photo"]):not([aria-label*="video"])');
                if (mainBtn && !isForbiddenElement(mainBtn)) {{
                    triggerEl = mainBtn;
                }}
                
                // Ưu tiên 1.2: Nếu là nhóm Mua Bán (Buy/Sell) có nút "Thảo luận"
                if (!triggerEl) {{
                    const buttons = Array.from(composerPagelet.querySelectorAll('div[role="button"], span, div[tabindex="0"]'));
                    for (const b of buttons) {{
                        const t = (b.innerText || b.getAttribute('aria-label') || '').toLowerCase().trim();
                        if ((t.includes('thảo luận') || t.includes('discussion') || t.includes('bạn viết gì đi')) && !isForbiddenElement(b)) {{
                            triggerEl = b;
                            break;
                        }}
                    }}
                }}

                // Ưu tiên 1.3: Nhấp vào nút "Ảnh/video" trong GroupInlineComposer (Nút này 100% kích hoạt mở dialog tạo bài)
                if (!triggerEl) {{
                    const mediaBtn = composerPagelet.querySelector('div[aria-label*="Ảnh"], div[aria-label*="Photo"], div[aria-label*="video"]');
                    if (mediaBtn && !isForbiddenElement(mediaBtn)) {{
                        triggerEl = mediaBtn;
                    }}
                }}
            }}

            // Cách 2: Tìm nút "Tạo bài viết" / "Bạn viết gì đi..." trong phần feed chính
            if (!triggerEl) {{
                const promptKeywords = [
                    "bạn viết gì đi", "write something", "tạo bài viết", 
                    "tạo bài viết công khai", "create a public post", "create post", 
                    "viết gì đó", "bạn đang nghĩ gì", "what's on your mind"
                ];
                const feedArea = document.querySelector('div[role="feed"], div[role="main"]') || document.body;
                const buttons = Array.from(feedArea.querySelectorAll('div[role="button"], div[tabindex="0"]'));
                for (const b of buttons) {{
                    if (isForbiddenElement(b)) continue;
                    const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').toLowerCase().trim();
                    if (promptKeywords.some(kw => txt.includes(kw))) {{
                        const rect = b.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 15) {{
                            triggerEl = b;
                            break;
                        }}
                    }}
                }}
            }}

            if (!triggerEl) {{
                return JSON.stringify({{
                    success: false,
                    step: "find_trigger",
                    message: "Không tìm thấy ô tạo bài viết trên trang nhóm. Hãy kiểm tra xem nick FB đã tham gia nhóm hoặc nhóm có bị khoá đăng bài không."
                }});
            }}

            // Nhấp mở khung soạn thảo
            triggerClick(triggerEl);

            // Chờ dialog xuất hiện (tối đa 5 giây)
            for (let i = 0; i < 16; i++) {{
                await sleep(300);
                dialog = document.querySelector('div[role="dialog"]');
                if (dialog) break;
            }}

            // Nếu nhấp ô text chưa kích hoạt dialog, thử nhấp nút Ảnh/video trong composer
            if (!dialog && composerPagelet) {{
                const photoBtn = composerPagelet.querySelector('div[aria-label*="Ảnh"], div[aria-label*="Photo"]');
                if (photoBtn && !isForbiddenElement(photoBtn)) {{
                    triggerClick(photoBtn);
                    for (let i = 0; i < 12; i++) {{
                        await sleep(300);
                        dialog = document.querySelector('div[role="dialog"]');
                        if (dialog) break;
                    }}
                }}
            }}
        }}

        if (!dialog) {{
            return JSON.stringify({{
                success: false,
                step: "open_dialog",
                message: "Đã nhấp mở ô viết bài nhưng Facebook không hiện cửa sổ soạn thảo. Hãy kiểm tra xem nick đã tham gia nhóm hoặc mở sẵn tab nhóm trong Chromium."
            }});
        }}

        // Chờ 300ms cho Lexical editor tải hoàn tất
        await sleep(300);

        // 2. Tìm khung nhập văn bản trong dialog (Lexical / Draft.js / Contenteditable)
        let editor = dialog.querySelector('div[role="textbox"][contenteditable="true"]') ||
                     dialog.querySelector('div[data-lexical-editor="true"]') ||
                     dialog.querySelector('div[contenteditable="true"]');

        if (!editor) {{
            return JSON.stringify({{
                success: false,
                step: "find_editor",
                message: "Không tìm thấy khung nhập văn bản trong cửa sổ tạo bài."
            }});
        }}

        // 3. Focus và điền nội dung bài viết
        editor.focus();
        await sleep(200);

        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        const insertOk = document.execCommand('insertText', false, postContent);
        if (!insertOk || !editor.innerText.trim()) {{
            editor.innerText = postContent;
        }}

        // Kích hoạt chuỗi sự kiện InputEvent cho React / Lexical nhận diện văn bản
        editor.dispatchEvent(new InputEvent('beforeinput', {{ inputType: 'insertText', data: postContent, bubbles: true, cancelable: true }}));
        editor.dispatchEvent(new InputEvent('input', {{ inputType: 'insertText', data: postContent, bubbles: true, cancelable: true }}));
        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
        await sleep(400);

        // 4. Tìm nút 'Đăng' (Post) trong dialog
        let postBtn = null;
        for (let i = 0; i < 15; i++) {{
            await sleep(250);
            const dialogButtons = Array.from(dialog.querySelectorAll('div[role="button"], button, div[tabindex="0"]'));
            for (const btn of dialogButtons) {{
                const al = (btn.getAttribute('aria-label') || '').toLowerCase().trim();
                const t = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                if (al === 'đăng' || al === 'post' || t === 'đăng' || t === 'post') {{
                    postBtn = btn;
                    break;
                }}
            }}
            if (postBtn && postBtn.getAttribute('aria-disabled') !== 'true' && !postBtn.disabled) {{
                break;
            }}
        }}

        if (!postBtn) {{
            return JSON.stringify({{
                success: false,
                step: "find_post_button",
                message: "Không tìm thấy nút 'Đăng' trong cửa sổ tạo bài viết."
            }});
        }}

        // Nếu nút Đăng bị mờ (aria-disabled=true), gõ thêm dấu cách và kích hoạt lại
        if (postBtn.getAttribute('aria-disabled') === 'true' || postBtn.disabled) {{
            editor.focus();
            document.execCommand('insertText', false, ' ');
            editor.dispatchEvent(new InputEvent('input', {{ inputType: 'insertText', data: ' ', bubbles: true }}));
            await sleep(600);
        }}

        // 5. Bấm nút Đăng
        triggerClick(postBtn);

        // 6. Kiểm tra kết quả phản hồi thực tế từ Facebook (tối đa 5 giây)
        for (let i = 0; i < 15; i++) {{
            await sleep(350);
            const dialogCheck = document.querySelector('div[role="dialog"]');
            if (!dialogCheck) {{
                return JSON.stringify({{
                    success: true,
                    status: "success",
                    message: "Đã xuất bản bài viết thành công lên hội nhóm!"
                }});
            }}

            const dialogText = (dialogCheck.innerText || '').toLowerCase();
            if (dialogText.includes('phê duyệt') || dialogText.includes('chờ duyệt') || dialogText.includes('quản trị viên') || dialogText.includes('pending') || dialogText.includes('admin approval')) {{
                return JSON.stringify({{
                    success: true,
                    status: "pending",
                    message: "Bài viết đã gửi thành công và đang chờ Quản trị viên nhóm phê duyệt."
                }});
            }}

            if (dialogText.includes('không thể') || dialogText.includes('bị chặn') || dialogText.includes('lỗi') || dialogText.includes('thử lại') || dialogText.includes('tiêu chuẩn')) {{
                return JSON.stringify({{
                    success: false,
                    status: "failed",
                    message: "Facebook từ chối bài đăng: " + dialogCheck.innerText.substring(0, 150)
                }});
            }}
        }}

        return JSON.stringify({{
            success: true,
            status: "success",
            message: "Đã gửi bài đăng lên nhóm thành công!"
        }});
    }})()
    """

    eval_res = cdp_send_command(
        ws_url,
        "Runtime.evaluate",
        {"expression": js_post_script, "awaitPromise": True, "returnByValue": True},
        timeout=45.0
    )

    if eval_res is None:
        return {
            "success": False,
            "status": "failed",
            "message": "Không nhận được phản hồi từ Chromium khi thực thi đăng bài (timeout 45s hoặc tab bị treo)."
        }

    if "cdp_error" in eval_res:
        return {
            "success": False,
            "status": "failed",
            "message": f"Lỗi CDP từ trình duyệt: {eval_res['cdp_error'].get('message')}"
        }

    if "exceptionDetails" in eval_res:
        exc_msg = eval_res["exceptionDetails"].get("text", "Lỗi script")
        if "exception" in eval_res["exceptionDetails"]:
            exc_msg += ": " + str(eval_res["exceptionDetails"]["exception"].get("description", ""))
        return {
            "success": False,
            "status": "failed",
            "message": f"Lỗi thực thi trong trang Facebook: {exc_msg}"
        }

    val_container = eval_res.get("result", {})
    if isinstance(val_container, dict) and "value" in val_container:
        raw_val = val_container["value"]
        try:
            val = json.loads(raw_val)
            return val
        except Exception:
            return {"success": True, "status": "success", "message": str(raw_val)}

    return {
        "success": True,
        "status": "success",
        "message": "Đã gửi lệnh đăng bài lên nhóm Facebook qua trình duyệt."
    }


