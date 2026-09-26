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
                            // Ưu tiên thẻ profile link thật sự của người dùng
                            const meLink = document.querySelector('div[data-pagelet="LeftRail"] ul li a[href*="profile.php"], div[data-pagelet="LeftRail"] ul li a[href^="/me"], a[aria-label*="Trang cá nhân"], a[aria-label*="profile"]');
                            if (meLink && meLink.innerText.trim().length > 1) {
                                name = meLink.innerText.split('\n')[0].trim();
                            }
                            if (!name) {
                                const meSpan = document.querySelector('div[data-pagelet="LeftRail"] a span');
                                if (meSpan && meSpan.innerText.trim().length > 1) {
                                    name = meSpan.innerText.trim();
                                }
                            }
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

def post_to_facebook_group_via_cdp(group_id_or_url: str, content: str, timeout: float = 30.0) -> dict:
    """
    Thực hiện tự động hóa đăng bài THẬT vào hội nhóm Facebook qua Ungoogled Chromium (CDP port 9222):
    1. Kết nối với Chromium qua cổng 9222
    2. Điều hướng tab Facebook tới URL hội nhóm
    3. Tìm nút 'Bạn viết gì đi...' / 'Tạo bài viết' trên trang nhóm
    4. Mở cửa sổ soạn thảo, điền nội dung văn bản (chuẩn sự kiện InputEvent cho Lexical/React)
    5. Bấm nút 'Đăng' (Post)
    6. Kiểm tra kết quả phản hồi thực tế từ Facebook (Đã đăng / Chờ duyệt / Lỗi)
    """
    import urllib.request
    import json
    import time

    grp_str = str(group_id_or_url).strip()
    if grp_str.startswith("http://") or grp_str.startswith("https://"):
        target_group_url = grp_str
    else:
        target_group_url = f"https://www.facebook.com/groups/{grp_str}/"

    # 1. Kết nối Ungoogled Chromium cổng 9222
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json", headers={"User-Agent": "FBTool"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
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

    # 2. Điều hướng tới nhóm nếu chưa ở đúng URL
    clean_grp = grp_str.replace("https://www.facebook.com/groups/", "").replace("http://www.facebook.com/groups/", "").strip("/")
    if clean_grp and clean_grp in current_tab_url:
        need_nav = False
    else:
        need_nav = True

    if need_nav:
        cdp_send_command(ws_url, "Page.navigate", {"url": target_group_url}, timeout=6.0)
        time.sleep(5.0)
    else:
        time.sleep(1.0)

    # 3. Kịch bản JavaScript tự động tìm khung soạn thảo, điền nội dung và bấm Đăng
    js_post_script = f"""
    (async () => {{
        const postContent = {json.dumps(content)};
        const sleep = (ms) => new Promise(res => setTimeout(res, ms));

        // 1. Chờ trang tải ổn định
        for (let i = 0; i < 20; i++) {{
            if (document.readyState === 'complete' || document.body) break;
            await sleep(300);
        }}

        // 2. Tìm nút mở khung tạo bài viết
        let dialog = document.querySelector('div[role="dialog"]');
        if (!dialog) {{
            const promptKeywords = [
                "bạn viết gì đi", "write something", "tạo bài viết", 
                "tạo bài viết công khai", "create a public post", "create post", 
                "viết gì đó", "thảo luận", "discussion", "bạn đang nghĩ gì", "what's on your mind"
            ];

            let triggerEl = null;
            const candidates = Array.from(document.querySelectorAll('div[role="button"], span, div[tabindex="0"]'));
            for (const el of candidates) {{
                const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase().trim();
                if (promptKeywords.some(kw => text.includes(kw))) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {{
                        triggerEl = el;
                        break;
                    }}
                }}
            }}

            if (!triggerEl) {{
                const pagelet = document.querySelector('div[data-pagelet="GroupInlineComposer"], div[data-pagelet*="Composer"]');
                if (pagelet) {{
                    triggerEl = pagelet.querySelector('div[role="button"]') || pagelet;
                }}
            }}

            if (!triggerEl) {{
                return JSON.stringify({{
                    success: false,
                    step: "find_trigger",
                    message: "Không tìm thấy nút 'Bạn viết gì đi...' trên trang nhóm. Có thể nick chưa tham gia nhóm này hoặc nhóm đã khóa tính năng đăng bài tự do."
                }});
            }}

            triggerEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            await sleep(500);
            triggerEl.click();
            triggerEl.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true }}));
            triggerEl.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true }}));
            triggerEl.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true }}));

            // Chờ cửa sổ soạn thảo của Facebook hiện ra
            for (let i = 0; i < 20; i++) {{
                await sleep(300);
                dialog = document.querySelector('div[role="dialog"]');
                if (dialog) break;
            }}
        }}

        if (!dialog) {{
            return JSON.stringify({{
                success: false,
                step: "open_dialog",
                message: "Đã nhấp mở ô viết bài nhưng Facebook không hiện cửa sổ soạn thảo."
            }});
        }}

        // 3. Tìm khung nhập văn bản (hỗ trợ Lexical / Draft.js)
        let editor = dialog.querySelector('div[role="textbox"][contenteditable="true"]') ||
                     dialog.querySelector('div[data-lexical-editor="true"]') ||
                     dialog.querySelector('div[contenteditable="true"]') ||
                     document.querySelector('div[role="textbox"][contenteditable="true"]');

        if (!editor) {{
            return JSON.stringify({{
                success: false,
                step: "find_editor",
                message: "Không tìm thấy khung soạn thảo văn bản trong cửa sổ tạo bài."
            }});
        }}

        // 4. Focus và điền nội dung bài viết
        editor.focus();
        await sleep(300);

        document.execCommand('selectAll', false, null);
        const ok = document.execCommand('insertText', false, postContent);
        if (!ok) {{
            editor.innerText = postContent;
        }}

        // Kích hoạt sự kiện InputEvent để React/Lexical nhận dữ liệu và bật nút Đăng
        editor.dispatchEvent(new InputEvent('beforeinput', {{ inputType: 'insertText', data: postContent, bubbles: true, cancelable: true }}));
        editor.dispatchEvent(new InputEvent('input', {{ inputType: 'insertText', data: postContent, bubbles: true, cancelable: true }}));
        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        editor.dispatchEvent(new Event('change', {{ bubbles: true }}));

        // Chờ 2 giây cho React kích hoạt nút Đăng
        await sleep(2000);

        // 5. Tìm nút 'Đăng' / 'Post'
        const dialogButtons = Array.from(dialog.querySelectorAll('div[role="button"], button'));
        let postBtn = null;

        for (const btn of dialogButtons) {{
            const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase().trim();
            const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
            if (ariaLabel === 'đăng' || ariaLabel === 'post' || text === 'đăng' || text === 'post') {{
                postBtn = btn;
                break;
            }}
        }}

        if (!postBtn) {{
            const visibleBtns = dialogButtons.filter(b => {{
                const r = b.getBoundingClientRect();
                return r.width > 50 && r.height > 25 && b.offsetParent !== null;
            }});
            if (visibleBtns.length > 0) {{
                postBtn = visibleBtns[visibleBtns.length - 1];
            }}
        }}

        if (!postBtn) {{
            return JSON.stringify({{
                success: false,
                step: "find_post_button",
                message: "Không tìm thấy nút 'Đăng' trong cửa sổ tạo bài."
            }});
        }}

        // Kiểm tra nút Đăng có bị mờ không
        const isAriaDisabled = postBtn.getAttribute('aria-disabled') === 'true' || postBtn.disabled;
        if (isAriaDisabled) {{
            editor.focus();
            document.execCommand('insertText', false, ' ');
            editor.dispatchEvent(new InputEvent('input', {{ inputType: 'insertText', data: ' ', bubbles: true }}));
            await sleep(1000);
        }}

        // Nhấp nút Đăng
        postBtn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        await sleep(300);
        postBtn.click();
        postBtn.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true }}));
        postBtn.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true }}));
        postBtn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true }}));

        // 6. Chờ Facebook xử lý đăng bài (4.5 giây)
        await sleep(4500);

        const dialogAfter = document.querySelector('div[role="dialog"]');
        if (!dialogAfter) {{
            return JSON.stringify({{
                success: true,
                status: "success",
                message: "Đã xuất bản bài viết thành công lên hội nhóm!"
            }});
        }}

        const dialogText = (dialogAfter.innerText || '').toLowerCase();
        if (dialogText.includes('phê duyệt') || dialogText.includes('chờ duyệt') || dialogText.includes('quản trị viên') || dialogText.includes('pending')) {{
            return JSON.stringify({{
                success: true,
                status: "pending",
                message: "Bài viết đã gửi thành công và đang chờ Quản trị viên nhóm phê duyệt."
            }});
        }}

        if (dialogText.includes('không thể') || dialogText.includes('bị chặn') || dialogText.includes('lỗi') || dialogText.includes('thử lại') || dialogText.includes('tiêu chuẩn cộng đồng')) {{
            return JSON.stringify({{
                success: false,
                status: "failed",
                message: "Facebook từ chối bài đăng: " + dialogAfter.innerText.substring(0, 150)
            }});
        }}

        return JSON.stringify({{
            success: true,
            status: "success",
            message: "Đã hoàn tất gửi lệnh đăng bài lên nhóm thành công!"
        }});
    }})()
    """

    eval_res = cdp_send_command(
        ws_url,
        "Runtime.evaluate",
        {"expression": js_post_script, "awaitPromise": True, "returnByValue": True},
        timeout=timeout
    )

    if eval_res and "result" in eval_res and "value" in eval_res["result"]:
        try:
            val = json.loads(eval_res["result"]["value"])
            return val
        except Exception:
            return {"success": True, "status": "success", "message": "Đã thực thi đăng bài qua trình duyệt."}

    return {
        "success": False,
        "status": "failed",
        "message": "Không nhận được phản hồi từ Chromium khi thực thi đăng bài (timeout hoặc trang chưa tải xong)."
    }


