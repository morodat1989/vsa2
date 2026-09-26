import os
import shutil
import sqlite3
import tempfile
import urllib.request
import json
import datetime

def get_profiles_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    profiles_dir = os.path.join(root_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    return profiles_dir

def check_cdp_status():
    """Kiểm tra xem Ungoogled Chromium có đang bật qua cổng Remote Debugging (9222) không"""
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
                return {
                    "running": True,
                    "tabs_count": len(data),
                    "fb_tab_open": fb_tab is not None,
                    "fb_tab_title": fb_tab.get("title", "") if fb_tab else None,
                    "fb_tab_url": fb_tab.get("url", "") if fb_tab else None
                }
    except Exception:
        pass
    return {
        "running": False,
        "tabs_count": 0,
        "fb_tab_open": False,
        "fb_tab_title": None,
        "fb_tab_url": None
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
        return {
            "has_cookie_db": False,
            "has_fb_login": False,
            "c_user": None,
            "status": "Chưa có dữ liệu duyệt web"
        }

    # Sao chép ra temp file để tránh Chromium khóa file SQLite khi đang chạy
    temp_dir = tempfile.gettempdir()
    temp_copy = os.path.join(temp_dir, f"ck_{os.path.basename(profile_path)}_{os.getpid()}.sqlite")

    c_user_val = None
    has_fb = False

    try:
        shutil.copy2(cookie_file, temp_copy)
        conn = sqlite3.connect(temp_copy)
        cursor = conn.cursor()
        
        # Tìm c_user trong các domain facebook.com
        cursor.execute("""
            SELECT name, value 
            FROM cookies 
            WHERE host_key LIKE '%facebook.com%' AND name IN ('c_user', 'xs')
        """)
        rows = cursor.fetchall()
        for name, value in rows:
            if name == "c_user":
                has_fb = True
                if value and value.strip():
                    c_user_val = value.strip()
            elif name == "xs":
                has_fb = True
                
        conn.close()
    except Exception as e:
        print(f"[Cookie Read Warning] {profile_path}: {e}")
    finally:
        if os.path.exists(temp_copy):
            try:
                os.remove(temp_copy)
            except Exception:
                pass

    if c_user_val:
        return {
            "has_cookie_db": True,
            "has_fb_login": True,
            "c_user": c_user_val,
            "status": "Live"
        }
    elif has_fb:
        return {
            "has_cookie_db": True,
            "has_fb_login": True,
            "c_user": "Đã đăng nhập",
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
    """Quét toàn bộ danh sách profile và thông tin kết nối Facebook"""
    profiles_dir = get_profiles_dir()
    profiles = []
    
    cdp = check_cdp_status()

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

                # Trạng thái Live nếu tìm thấy c_user hoặc nếu CDP đang mở tab FB
                is_live = cookie_info["has_fb_login"]
                
                profiles.append({
                    "name": name,
                    "path": item_path,
                    "mtime": mtime_str,
                    "has_cookie_db": cookie_info["has_cookie_db"],
                    "has_fb_login": is_live,
                    "c_user": cookie_info["c_user"],
                    "status": "Live" if is_live else "Chưa đăng nhập"
                })

    return {
        "profiles": profiles,
        "cdp": cdp,
        "live_count": len([p for p in profiles if p["has_fb_login"]])
    }
