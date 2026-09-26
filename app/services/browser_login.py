import os
import sys
import json
import time
import socket
import base64
import hashlib
import struct
import subprocess
import urllib.request
from typing import Optional, Dict, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILES_DIR = os.path.join(ROOT_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def find_chromium_executable() -> Optional[str]:
    """Tìm đường dẫn tới Ungoogled Chromium hoặc Chrome"""
    candidates = [
        os.path.join(ROOT_DIR, "Ungoogled Chromium", "chrome.exe"),
        os.path.join(ROOT_DIR, "Ungoogled Chromium", "chromium.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
            
    # Tìm đệ quy trong thư mục Ungoogled Chromium
    base_cr = os.path.join(ROOT_DIR, "Ungoogled Chromium")
    if os.path.exists(base_cr):
        for r, d, files in os.walk(base_cr):
            if "chrome.exe" in files:
                return os.path.join(r, "chrome.exe")
            if "chromium.exe" in files:
                return os.path.join(r, "chromium.exe")

    # Fallback Chrome trên máy Windows
    for env_key in ["ProgramFiles", "ProgramFiles(x86)", "LocalAppData"]:
        base_p = os.environ.get(env_key)
        if base_p:
            chrome_path = os.path.join(base_p, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.exists(chrome_path):
                return chrome_path

    return None

class SimpleWebSocketClient:
    """Lightweight pure-python WebSocket client để giao tiếp với Chrome DevTools Protocol"""
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        # ws://127.0.0.1:9222/devtools/page/...
        parsed = ws_url.replace("ws://", "").split("/", 1)
        host_port = parsed[0].split(":")
        self.host = host_port[0]
        self.port = int(host_port[1]) if len(host_port) > 1 else 9222
        self.path = "/" + (parsed[1] if len(parsed) > 1 else "")
        self.sock = None

    def connect(self, timeout=3.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.host, self.port))

        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        handshake = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(handshake.encode('utf-8'))
        response = self.sock.recv(4096).decode('utf-8', errors='ignore')
        if "101 Switching Protocols" not in response:
            raise Exception("WebSocket handshake failed")

    def send_json(self, payload: dict):
        raw_data = json.dumps(payload).encode('utf-8')
        length = len(raw_data)
        mask_key = os.urandom(4)
        
        # Build frame
        if length <= 125:
            header = struct.pack("!BB", 0x81, 0x80 | length)
        elif length <= 65535:
            header = struct.pack("!BBH", 0x81, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, length)

        masked_payload = bytearray(length)
        for i in range(length):
            masked_payload[i] = raw_data[i] ^ mask_key[i % 4]

        self.sock.sendall(header + mask_key + bytes(masked_payload))

    def recv_json(self, timeout=3.0) -> dict:
        self.sock.settimeout(timeout)
        data = self.sock.recv(8192)
        if not data:
            return {}
        
        # Parse unmasked or masked frame
        second_byte = data[1]
        length = second_byte & 127
        offset = 2
        if length == 126:
            offset = 4
        elif length == 127:
            offset = 10
            
        payload = data[offset:]
        try:
            return json.loads(payload.decode('utf-8', errors='ignore'))
        except Exception:
            return {}

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

current_login_proc = None

def launch_login_browser(profile_name: str = "login_session", port: int = 9222) -> dict:
    """Mở Ungoogled Chromium tại trang đăng nhập Facebook"""
    global current_login_proc
    chrome_exe = find_chromium_executable()
    if not chrome_exe:
        return {"success": False, "error": "Không tìm thấy Ungoogled Chromium (chrome.exe)"}

    session_profile_dir = os.path.join(PROFILES_DIR, profile_name)
    os.makedirs(session_profile_dir, exist_ok=True)

    cmd = [
        chrome_exe,
        f"--user-data-dir={session_profile_dir}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.facebook.com/login"
    ]

    try:
        current_login_proc = subprocess.Popen(cmd)
        return {
            "success": True,
            "profile_dir": session_profile_dir,
            "browser": chrome_exe
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_login_status(port: int = 9222) -> dict:
    """
    Kiểm tra xem người dùng đã đăng nhập Facebook thành công trên Chromium hay chưa.
    Trả về UID, Cookie và tên hiển thị nếu đã đăng nhập.
    """
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            tabs = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return {"logged_in": False, "status": "waiting_browser", "message": "Đang mở trình duyệt..."}

    fb_tab = None
    for tab in tabs:
        url = tab.get("url", "")
        if "facebook.com" in url:
            fb_tab = tab
            break

    if not fb_tab:
        return {"logged_in": False, "status": "opening_fb", "message": "Đang tải trang Facebook..."}

    # Kết nối qua WebSocket CDP để lấy cookie và url
    ws_url = fb_tab.get("webSocketDebuggerUrl")
    if not ws_url:
        return {"logged_in": False, "status": "waiting_ws", "message": "Đang kết nối Facebook..."}

    ws = None
    try:
        ws = SimpleWebSocketClient(ws_url)
        ws.connect(timeout=2.5)

        # Lấy tất cả Cookie của Facebook
        ws.send_json({
            "id": 1,
            "method": "Network.getCookies",
            "params": {"urls": ["https://www.facebook.com", "https://m.facebook.com"]}
        })
        time.sleep(0.3)
        res = ws.recv_json(timeout=2.0)
        cookies_list = res.get("result", {}).get("cookies", [])

        # Kiểm tra cookie c_user
        c_user = None
        cookie_parts = []
        for c in cookies_list:
            cookie_parts.append(f"{c['name']}={c['value']}")
            if c['name'] == "c_user":
                c_user = c['value']

        full_cookie = "; ".join(cookie_parts)

        # Lấy tiêu đề trang để trích tên
        ws.send_json({
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.title"}
        })
        time.sleep(0.2)
        title_res = ws.recv_json(timeout=2.0)
        title = title_res.get("result", {}).get("result", {}).get("value", "")

        # Nếu có c_user tức là đã đăng nhập thành công!
        if c_user:
            name = title.replace(" | Facebook", "").replace(" - Facebook", "").strip()
            if not name or "Facebook" in name or "Log in" in name:
                name = f"FB User {c_user}"

            return {
                "logged_in": True,
                "uid": c_user,
                "name": name,
                "cookie": full_cookie,
                "title": title
            }
        else:
            return {
                "logged_in": False,
                "status": "logging_in",
                "message": "Đang chờ bạn nhập tài khoản và mật khẩu trên cửa sổ Facebook..."
            }

    except Exception as e:
        return {"logged_in": False, "status": "inspecting", "message": f"Đang theo dõi đăng nhập..."}
    finally:
        if ws:
            ws.close()
