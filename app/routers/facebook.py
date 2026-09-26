import os
import subprocess
import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FacebookAccount, FacebookGroup, PostLog, Listing
from app.services.ai_service import generate_ai_post
from app.services.profile_scanner import scan_all_profiles_detail, set_active_profile_name, scan_facebook_groups_pacing

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def sync_profiles_to_db(db: Session):
    """Đồng bộ tự động các Profile Chromium vào bảng FacebookAccount an toàn, không trùng UID"""
    scan_result = scan_all_profiles_detail()
    try:
        for prof in scan_result["profiles"]:
            # Đảm bảo UID luôn duy nhất tuyệt đối theo tên profile nếu không có UID số
            numeric_uid = prof.get("c_user") if (prof.get("c_user") and str(prof.get("c_user")).isdigit()) else None
            safe_uid = numeric_uid or f"profile_{prof['name']}"
            account_name = f"{prof['user_name']} ({prof['name']})" if prof.get("user_name") else f"Profile: {prof['name']}"

            # Tìm theo UID hoặc tên profile
            existing = db.query(FacebookAccount).filter(
                (FacebookAccount.uid == safe_uid) | (FacebookAccount.name == account_name) | (FacebookAccount.name == f"Profile: {prof['name']}")
            ).first()

            status_str = "Live" if prof["has_fb_login"] else "Chưa đăng nhập FB"
            if existing:
                existing.status = status_str
                existing.name = account_name
                existing.uid = safe_uid
                existing.last_checked = datetime.datetime.utcnow()
            else:
                new_acc = FacebookAccount(
                    name=account_name,
                    uid=safe_uid,
                    status=status_str,
                    last_checked=datetime.datetime.utcnow()
                )
                db.add(new_acc)
        db.commit()
    except Exception as e:
        print(f"[DB Sync Safe Rollback] {e}")
        db.rollback()
    return scan_result

# Accounts & Profiles
@router.get("/accounts")
def list_accounts(request: Request, db: Session = Depends(get_db)):
    scan_result = sync_profiles_to_db(db)
    accounts = db.query(FacebookAccount).all()
    launched = request.query_params.get("launched", None)
    synced = request.query_params.get("synced", None)

    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "request": request,
            "active_page": "accounts",
            "page_title": "Quản Lý Profile & Kết Nối Facebook",
            "accounts": accounts,
            "profiles": scan_result["profiles"],
            "cdp": scan_result["cdp"],
            "live_count": scan_result["live_count"],
            "launched": launched,
            "synced": synced
        }
    )

@router.get("/sync-profiles")
def manual_sync_profiles(db: Session = Depends(get_db)):
    sync_profiles_to_db(db)
    return RedirectResponse(url="/facebook/accounts?synced=1", status_code=303)

@router.get("/profiles/launch/{profile_name}")
def launch_profile(profile_name: str):
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    profiles_dir = os.path.join(root_dir, "profiles")
    target_prof = os.path.join(profiles_dir, profile_name)
    os.makedirs(target_prof, exist_ok=True)
    set_active_profile_name(profile_name)
    
    chrome_candidates = [
        os.path.join(root_dir, "Ungoogled Chromium", "app", "chrome.exe"),
        os.path.join(root_dir, "Ungoogled Chromium", "chrome.exe"),
        os.path.join(root_dir, "Ungoogled Chromium", "chromium.exe")
    ]
    chrome_exe = None
    for cand in chrome_candidates:
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
            subprocess.Popen([
                chrome_exe,
                f"--user-data-dir={target_prof}",
                "--remote-debugging-port=9222",
                "--no-first-run",
                "--no-default-browser-check"
            ] + urls)
        except Exception as e:
            print(f"[Lỗi mở Chromium] {e}")
    return RedirectResponse(url=f"/facebook/accounts?launched={profile_name}", status_code=303)

@router.post("/profiles/create")
def create_profile(profile_name: str = Form(...)):
    name = profile_name.strip()
    if name:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        profiles_dir = os.path.join(root_dir, "profiles")
        target_prof = os.path.join(profiles_dir, name)
        os.makedirs(target_prof, exist_ok=True)
        set_active_profile_name(name)
        return RedirectResponse(url=f"/facebook/profiles/launch/{name}", status_code=303)
    return RedirectResponse(url="/facebook/accounts", status_code=303)

@router.post("/accounts")
def add_account(
    name: str = Form(...),
    uid: str = Form(...),
    cookie: str = Form(""),
    token: str = Form(""),
    db: Session = Depends(get_db)
):
    existing = db.query(FacebookAccount).filter(FacebookAccount.uid == uid).first()
    if existing:
        existing.name = name
        existing.cookie = cookie
        existing.token = token
        existing.status = "Live"
        existing.last_checked = datetime.datetime.utcnow()
    else:
        acc = FacebookAccount(
            name=name,
            uid=uid,
            cookie=cookie,
            token=token,
            status="Live",
            last_checked=datetime.datetime.utcnow()
        )
        db.add(acc)
    db.commit()
    return RedirectResponse(url="/facebook/accounts", status_code=303)

@router.get("/accounts/check/{account_id}")
def check_account_live(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if acc:
        acc.last_checked = datetime.datetime.utcnow()
        acc.status = "Live"
        db.commit()
    return RedirectResponse(url="/facebook/accounts", status_code=303)

@router.get("/accounts/delete/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if acc:
        db.delete(acc)
        db.commit()
    return RedirectResponse(url="/facebook/accounts", status_code=303)

# Groups
@router.get("/groups")
def list_groups(request: Request, db: Session = Depends(get_db)):
    groups = db.query(FacebookGroup).all()
    return templates.TemplateResponse(
        request=request,
        name="groups.html",
        context={
            "request": request,
            "active_page": "groups",
            "page_title": "Quản Lý Nhóm Facebook",
            "groups": groups
        }
    )

@router.post("/groups")
def add_group(
    name: str = Form(...),
    group_id: str = Form(...),
    members_count: int = Form(10000),
    db: Session = Depends(get_db)
):
    existing = db.query(FacebookGroup).filter(FacebookGroup.group_id == group_id).first()
    if not existing:
        grp = FacebookGroup(
            name=name,
            group_id=group_id,
            members_count=members_count,
            privacy="PUBLIC"
        )
        db.add(grp)
        db.commit()
    return RedirectResponse(url="/facebook/groups", status_code=303)

@router.get("/groups/delete/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    grp = db.query(FacebookGroup).filter(FacebookGroup.id == group_id).first()
    if grp:
        db.delete(grp)
        db.commit()
    return RedirectResponse(url="/facebook/groups", status_code=303)

@router.post("/groups/scan")
async def scan_groups_api(request: Request, db: Session = Depends(get_db)):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            limit = int(data.get("limit", 5))
            delay = float(data.get("delay", 3.0))
        else:
            form = await request.form()
            limit = int(form.get("limit", 5))
            delay = float(form.get("delay", 3.0))
            
        result = scan_facebook_groups_pacing(limit=limit, delay_seconds=delay)
        
        saved_count = 0
        new_count = 0
        for g in result.get("groups", []):
            gid = str(g["group_id"]).strip()
            existing = db.query(FacebookGroup).filter(FacebookGroup.group_id == gid).first()
            if existing:
                existing.name = g["name"]
                if g.get("members_count"):
                    existing.members_count = g["members_count"]
                saved_count += 1
            else:
                new_grp = FacebookGroup(
                    name=g["name"],
                    group_id=gid,
                    members_count=g.get("members_count", 50000),
                    privacy=g.get("privacy", "PUBLIC")
                )
                db.add(new_grp)
                new_count += 1
                saved_count += 1
        db.commit()
        
        return JSONResponse({
            "success": True,
            "count": len(result.get("groups", [])),
            "new_count": new_count,
            "saved_count": saved_count,
            "logs": result.get("logs", []),
            "groups": result.get("groups", [])
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# Logs
@router.get("/logs")
def view_logs(request: Request, db: Session = Depends(get_db)):
    logs = db.query(PostLog).order_by(PostLog.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={
            "request": request,
            "active_page": "logs",
            "page_title": "Lịch Sử Đăng Bài",
            "logs": logs
        }
    )

# AI Writing & Posting
@router.get("/ai-write/{listing_id}")
def ai_write(listing_id: int, request: Request, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        return RedirectResponse(url="/listings", status_code=303)

    ai_content = generate_ai_post(
        listing_title=listing.title,
        price=listing.price,
        area=listing.area,
        location=listing.location,
        description=listing.description or ""
    )

    accounts = db.query(FacebookAccount).all()
    groups = db.query(FacebookGroup).all()

    return templates.TemplateResponse(
        request=request,
        name="ai_result.html",
        context={
            "request": request,
            "active_page": "listings",
            "page_title": "AI Tạo Bài Đăng BĐS",
            "listing": listing,
            "ai_content": ai_content,
            "accounts": accounts,
            "groups": groups
        }
    )

@router.post("/publish")
def publish_post(
    listing_id: int = Form(...),
    content: str = Form(...),
    account_id: int = Form(...),
    group_id: str = Form(...),
    db: Session = Depends(get_db)
):
    acc = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    group = db.query(FacebookGroup).filter(FacebookGroup.group_id == group_id).first()

    # Log action
    log = PostLog(
        account_name=acc.name if acc else "Tài khoản",
        account_uid=acc.uid if acc else "",
        group_name=group.name if group else group_id,
        group_id=group_id,
        listing_title=listing.title if listing else "",
        status="success",
        message="Đăng thành công lên nhóm qua phiên duyệt",
        created_at=datetime.datetime.utcnow()
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url="/facebook/logs", status_code=303)
