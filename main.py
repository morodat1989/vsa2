import os
import sys
import subprocess
import webbrowser
import threading
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Listing, FacebookAccount, FacebookGroup, PostLog, Setting
from app.routers import listings, facebook, settings

# Tạo bảng database nếu chưa có
Base.metadata.create_all(bind=engine)

# Khởi tạo dữ liệu mẫu nếu database đang trống
def init_sample_data():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(Listing).count() == 0:
            db.add_all([
                Listing(
                    title="Bán nhà mặt phố Cầu Giấy 65m2 x 5 tầng thang máy",
                    price=14.5,
                    area=65.0,
                    location="Phường Dịch Vọng Hậu, Cầu Giấy, Hà Nội",
                    description="Vị trí đắc địa kinh doanh sầm uất ngày đêm, đường 2 ô tô tránh nhau, sổ đỏ vuông vắn chính chủ sẵn sàng giao dịch.",
                    image_url="https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&auto=format&fit=crop&q=80"
                ),
                Listing(
                    title="Căn hộ cao cấp 3PN Vinhomes Ocean Park view hồ điều hòa",
                    price=4.2,
                    area=98.0,
                    location="Gia Lâm, Hà Nội",
                    description="Full nội thất cao cấp nhập khẩu châu Âu, tầng trung thoáng mát, tiện ích bạt ngàn gồm bể bơi vô cực và công viên biển hồ.",
                    image_url="https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&auto=format&fit=crop&q=80"
                )
            ])
        if db.query(FacebookAccount).count() == 0:
            db.add(FacebookAccount(
                name="Nguyễn Văn BĐS (Profile 1)",
                uid="1000839281928",
                status="Live"
            ))
        if db.query(FacebookGroup).count() == 0:
            db.add_all([
                FacebookGroup(name="Hội Mua Bán Nhà Đất Hà Nội Chính Chủ", group_id="1029384756", members_count=125000),
                FacebookGroup(name="Bất Động Sản Cầu Giấy & Nam Từ Liêm", group_id="2938475610", members_count=68000)
            ])
        db.commit()
    except Exception as e:
        print(f"[Init DB Error] {e}")
    finally:
        db.close()

init_sample_data()

app = FastAPI(title="FB Tool Quản Lý BĐS & Mạng Xã Hội")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Mount Routers
app.include_router(listings.router, prefix="/listings", tags=["Listings"])
app.include_router(facebook.router, prefix="/facebook", tags=["Facebook"])
app.include_router(settings.router, prefix="/settings", tags=["Settings"])

# ================= URL ALIASES (Tránh 404 khi gõ trực tiếp) ================= #
@app.get("/accounts")
def redirect_accounts():
    return RedirectResponse(url="/facebook/accounts", status_code=302)

@app.get("/groups")
def redirect_groups():
    return RedirectResponse(url="/facebook/groups", status_code=302)

@app.get("/logs")
def redirect_logs():
    return RedirectResponse(url="/facebook/logs", status_code=302)

# ================= TRANG TỔNG QUAN (DASHBOARD) ================= #
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    all_listings = db.query(Listing).order_by(Listing.id.desc()).all()
    all_accounts = db.query(FacebookAccount).all()
    all_groups = db.query(FacebookGroup).all()
    all_logs = db.query(PostLog).order_by(PostLog.id.desc()).all()

    stats = {
        "totalListings": len(all_listings),
        "totalAccounts": len(all_accounts),
        "liveAccounts": len([a for a in all_accounts if (a.status or "").lower() == "live"]),
        "totalGroups": len(all_groups),
        "successfulPosts": len([l for l in all_logs if l.status == "success"])
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "page_title": "Tổng Quan Hệ Thống BĐS",
        "stats": stats,
        "recentListings": all_listings[:5]
    })

# ================= HỖ TRỢ MỞ UNGOOGLED CHROMIUM KHI CHẠY LOCAL ================= #
def open_browser():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    profiles_dir = os.path.join(root_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    # Tim Ungoogled Chromium
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
            print(f"[OK] Đã mở Ungoogled Chromium với Profile: {profiles_dir}")
            return
        except Exception as err:
            print(f"[Lỗi mở Chromium] {err}")

    for u in urls:
        webbrowser.open(u)

if __name__ == "__main__":
    import uvicorn
    threading.Timer(2.0, open_browser).start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
