import os
import sys
import subprocess
import webbrowser
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="FB Tool BĐS & Quản lý Mạng Xã Hội")

# Check if templates directory exists
templates_dir = "app/templates" if os.path.exists("app/templates") else "views"
templates = Jinja2Templates(directory=templates_dir) if os.path.exists(templates_dir) else None

# Routers (loaded if available)
try:
    from app.routers import listings, facebook, settings
    app.include_router(listings.router, prefix="/listings", tags=["Listings"])
    app.include_router(facebook.router, prefix="/facebook", tags=["Facebook"])
    app.include_router(settings.router, prefix="/settings", tags=["Settings"])
except Exception as e:
    pass

@app.get("/")
def home(request: Request):
    if templates and os.path.exists(os.path.join(templates_dir, "dashboard.html")):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return {"status": "ok", "message": "FastAPI Server đang chạy", "port": 8000}

def open_browser():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    profiles_dir = os.path.join(root_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    # Check Ungoogled Chromium
    chromium_candidates = [
        os.path.join(root_dir, "Ungoogled Chromium", "chrome.exe"),
        os.path.join(root_dir, "Ungoogled Chromium", "chromium.exe")
    ]
    
    chrome_exe = None
    for cand in chromium_candidates:
        if os.path.exists(cand):
            chrome_exe = cand
            break
            
    if not chrome_exe:
        # Search recursively in Ungoogled Chromium directory
        base_cr = os.path.join(root_dir, "Ungoogled Chromium")
        if os.path.exists(base_cr):
            for r, d, files in os.walk(base_cr):
                if "chrome.exe" in files:
                    chrome_exe = os.path.join(r, "chrome.exe")
                    break
                elif "chromium.exe" in files:
                    chrome_exe = os.path.join(r, "chromium.exe")
                    break

    urls = ["http://127.0.0.1:8000", "https://www.facebook.com"]
    if chrome_exe and os.path.exists(chrome_exe):
        try:
            cmd = [
                chrome_exe,
                f"--user-data-dir={profiles_dir}",
                "--no-first-run",
                "--no-default-browser-check"
            ] + urls
            subprocess.Popen(cmd)
            print(f"[OK] Đã mở Ungoogled Chromium với profile: {profiles_dir}")
            return
        except Exception as err:
            print(f"[Lỗi] Không thể mở Ungoogled Chromium: {err}")

    # Fallback to default browser
    for u in urls:
        webbrowser.open(u)

if __name__ == "__main__":
    import uvicorn
    import threading
    threading.Timer(2.0, open_browser).start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
