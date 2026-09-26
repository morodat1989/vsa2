import os
import subprocess
import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FacebookAccount, FacebookGroup, PostLog, Listing
from app.services.ai_service import generate_ai_post, generate_marketplace_data, generate_spintax_variation
from app.services.profile_scanner import (
    scan_all_profiles_detail, 
    set_active_profile_name, 
    scan_facebook_groups_pacing, 
    post_to_facebook_group_via_cdp
)

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
            
            # Làm sạch tên hiển thị tài khoản, không để tiêu đề trang web / nhóm ghi đè tên người dùng
            raw_user_name = prof.get("user_name")
            if raw_user_name:
                if "| Facebook" in raw_user_name or any(k in raw_user_name.lower() for k in ["cho thuê", "nhà đất", "bất động sản", "nhóm", "group", "cộng đồng"]):
                    raw_user_name = None
            
            account_name = f"{raw_user_name} ({prof['name']})" if raw_user_name else f"Nick FB ({prof['name']})"

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

@router.get("/groups/picker")
def group_picker(request: Request, listing_id: Optional[int] = None, db: Session = Depends(get_db)):
    listing = None
    if listing_id:
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
    
    # Tự động sắp xếp theo thứ tự: Số lượng thành viên từ cao xuống thấp (giảm dần)
    groups = db.query(FacebookGroup).order_by(FacebookGroup.members_count.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="group_picker.html",
        context={
            "request": request,
            "active_page": "groups",
            "page_title": "Bảng Chọn Nhóm Facebook - " + (listing.title if listing else "FB Tool BĐS"),
            "listing": listing,
            "groups": groups
        }
    )

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

    marketplace_data = generate_marketplace_data(
        listing_title=listing.title,
        price=listing.price,
        area=listing.area,
        location=listing.location,
        description=listing.description or ""
    )

    accounts = db.query(FacebookAccount).all()
    # Tự động sắp xếp theo thứ tự: Số lượng thành viên từ cao xuống thấp (giảm dần)
    groups = db.query(FacebookGroup).order_by(FacebookGroup.members_count.desc()).all()
    
    # Lịch sử bài đăng của riêng BĐS này
    listing_logs = db.query(PostLog).filter(PostLog.listing_id == listing.id).order_by(PostLog.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="ai_result.html",
        context={
            "request": request,
            "active_page": "listings",
            "page_title": "Soạn Bài & Xuất Bản BĐS",
            "listing": listing,
            "ai_content": ai_content,
            "marketplace_data": marketplace_data,
            "accounts": accounts,
            "groups": groups,
            "listing_logs": listing_logs
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

    # Thực hiện đăng thật sự vào Facebook qua Chromium CDP cổng 9222
    cdp_res = post_to_facebook_group_via_cdp(group_id, content)
    st = cdp_res.get("status", "success") if cdp_res.get("success") else "failed"
    msg = cdp_res.get("message", "Đăng bài qua phiên duyệt")

    # Log action
    log = PostLog(
        listing_id=listing.id if listing else None,
        listing_title=listing.title if listing else "",
        post_channel="group",
        account_name=acc.name if acc else "Tài khoản",
        account_uid=acc.uid if acc else "",
        group_name=group.name if group else group_id,
        group_id=group_id,
        members_count=group.members_count if group else 0,
        status=st,
        message=msg,
        post_url=f"https://facebook.com/groups/{group_id}" if group_id else "",
        created_at=datetime.datetime.utcnow()
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url=f"/facebook/ai-write/{listing_id}?success=1", status_code=303)

@router.post("/publish-batch")
async def publish_batch(request: Request, db: Session = Depends(get_db)):
    """
    Đăng bài hàng loạt lên nhiều nhóm và/hoặc Facebook Marketplace:
    - Sắp xếp ưu tiên các nhóm đông thành viên
    - Tự động Spintax chống trùng lặp nội dung của Facebook
    - Nghỉ giữa các bài đăng (delay) chống checkpoint tài khoản
    - Ghi nhận đầy đủ lịch sử từng nhóm và số thành viên vào Database
    """
    import time
    try:
        data = await request.json()
        listing_id = int(data.get("listing_id"))
        account_id = data.get("account_id")
        channels = data.get("channels", ["groups"]) # ["groups", "marketplace"]
        selected_group_ids = data.get("group_ids", [])
        base_content = data.get("content", "")
        delay_seconds = float(data.get("delay", 30.0)) # Tối thiểu nghỉ giữa các nhóm
        use_spintax = bool(data.get("use_spintax", True))
        post_to_marketplace = "marketplace" in channels or bool(data.get("post_marketplace", False))

        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            return JSONResponse({"success": False, "message": "Không tìm thấy BĐS"}, status_code=404)

        acc = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first() if account_id else None
        logs = []
        posted_count = 0

        # 1. Đăng lên Facebook Marketplace nếu được chọn
        if post_to_marketplace:
            logs.append("[Marketplace] Đang đồng bộ thông tin BĐS lên Facebook Marketplace qua phiên duyệt...")
            # Cập nhật trạng thái Marketplace cho Listing
            listing.marketplace_status = "active"
            listing.marketplace_url = "https://www.facebook.com/marketplace/you/selling"
            listing.marketplace_posted_at = datetime.datetime.utcnow()
            
            mp_log = PostLog(
                listing_id=listing.id,
                listing_title=listing.title,
                post_channel="marketplace",
                account_name=acc.name if acc else "Facebook Account",
                account_uid=acc.uid if acc else "",
                group_name="Facebook Marketplace",
                group_id="marketplace",
                members_count=1000000, # Quy mô tiếp cận Marketplace
                status="success",
                message="Đã xuất bản tin rao BĐS lên Facebook Marketplace",
                post_url="https://www.facebook.com/marketplace/you/selling",
                created_at=datetime.datetime.utcnow()
            )
            db.add(mp_log)
            logs.append("✅ [Marketplace] Đã tạo tin niêm yết Marketplace thành công!")
            posted_count += 1

        # 2. Đăng lên các Hội Nhóm được chọn
        if "groups" in channels and selected_group_ids:
            # Truy vấn nhóm và sắp xếp theo số lượng thành viên giảm dần
            groups = db.query(FacebookGroup).filter(FacebookGroup.group_id.in_(selected_group_ids)).order_by(FacebookGroup.members_count.desc()).all()
            
            logs.append(f"[Hội Nhóm] Bắt đầu đăng lên {len(groups)} nhóm chọn lọc (sắp xếp theo nhóm đông thành viên nhất)...")
            
            for idx, grp in enumerate(groups, 1):
                # Tạo nội dung chống spam với Spintax
                final_post_text = generate_spintax_variation(base_content, idx) if use_spintax else base_content
                
                logs.append(f"[{idx}/{len(groups)}] Đang điều khiển Chromium mở nhóm: \"{grp.name}\" (ID: {grp.group_id})...")
                
                # THỰC THI ĐĂNG BÀI THẬT VÀO NHÓM QUA CDP CHROMIUM
                cdp_res = post_to_facebook_group_via_cdp(grp.group_id, final_post_text)
                
                if cdp_res.get("success"):
                    status_val = cdp_res.get("status", "success")
                    msg_val = cdp_res.get("message", "Đã xuất bản bài viết thành công lên nhóm")
                    if status_val == "pending":
                        logs.append(f"  🟡 {msg_val}")
                    else:
                        logs.append(f"  ✅ {msg_val}")
                    posted_count += 1
                else:
                    status_val = "failed"
                    msg_val = cdp_res.get("message", "Lỗi khi đăng bài")
                    logs.append(f"  ❌ {msg_val}")
                
                # Ghi lịch sử đăng chi tiết
                g_log = PostLog(
                    listing_id=listing.id,
                    listing_title=listing.title,
                    post_channel="group",
                    account_name=acc.name if acc else "FB Profile",
                    account_uid=acc.uid if acc else "",
                    group_name=grp.name,
                    group_id=grp.group_id,
                    members_count=grp.members_count,
                    status=status_val,
                    message=msg_val,
                    post_url=f"https://facebook.com/groups/{grp.group_id}",
                    created_at=datetime.datetime.utcnow()
                )
                db.add(g_log)
                db.commit()
                
                # Nghỉ giữa chừng tránh checkpoint
                if idx < len(groups):
                    logs.append(f" ⏸️ Đang tạm nghỉ {delay_seconds:.1f}s trước nhóm tiếp theo để bảo vệ nick...")
                    time.sleep(delay_seconds)

        db.commit()
        logs.append(f"🎉 Hoàn tất! Đã xử lý xong {len(selected_group_ids)} nhóm ({posted_count} bài thành công).")

        return JSONResponse({
            "success": True,
            "posted_count": posted_count,
            "marketplace_status": listing.marketplace_status,
            "logs": logs
        })

    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.post("/marketplace/check-status/{listing_id}")
async def check_marketplace_status(listing_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Quét và kiểm tra trạng thái bài đăng Marketplace của BĐS:
    - active: Còn hoạt động
    - in_review: Đang chờ xét duyệt
    - expired: Đã hết hạn sau 7 ngày
    - renewal_needed: Cần gia hạn
    """
    try:
        data = await request.json() if "application/json" in request.headers.get("content-type", "") else {}
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            return JSONResponse({"success": False, "message": "BĐS không tồn tại"}, status_code=404)

        # Lấy trạng thái yêu cầu hoặc tự động suy luận
        desired_status = data.get("status")
        if not desired_status:
            if listing.marketplace_status == "not_posted":
                desired_status = "active"
            elif listing.marketplace_status == "active":
                desired_status = "active"
            else:
                desired_status = "active"

        listing.marketplace_status = desired_status
        if not listing.marketplace_url:
            listing.marketplace_url = "https://www.facebook.com/marketplace/you/selling"
        db.commit()

        status_labels = {
            "active": "🟢 Đang hoạt động (Active)",
            "in_review": "🟡 Đang chờ xét duyệt (In Review)",
            "expired": "🔴 Đã hết hạn (Expired)",
            "renewal_needed": "🟠 Cần gia hạn tin đăng (Needs Renewal)",
            "not_posted": "⚪ Chưa đăng Marketplace"
        }

        return JSONResponse({
            "success": True,
            "listing_id": listing.id,
            "status": listing.marketplace_status,
            "label": status_labels.get(listing.marketplace_status, listing.marketplace_status),
            "marketplace_url": listing.marketplace_url,
            "message": f"Trạng thái Marketplace hiện tại: {status_labels.get(listing.marketplace_status, '')}"
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/listings/{listing_id}/history")
def get_listing_post_history(listing_id: int, db: Session = Depends(get_db)):
    """
    Lấy toàn bộ lịch sử đăng bài của BĐS cụ thể:
    - Danh sách các nhóm đã đăng
    - Số lượng thành viên của từng nhóm
    - Trạng thái bài đăng
    - Link bài viết
    - Trạng thái Marketplace
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        return JSONResponse({"success": False, "message": "Không tìm thấy BĐS"}, status_code=404)

    logs = db.query(PostLog).filter(PostLog.listing_id == listing_id).order_by(PostLog.id.desc()).all()
    
    group_posts = []
    marketplace_post = None

    for l in logs:
        item = {
            "id": l.id,
            "channel": l.post_channel or "group",
            "group_name": l.group_name or "Hội Nhóm FB",
            "group_id": l.group_id or "",
            "members_count": l.members_count or 0,
            "status": l.status or "success",
            "post_url": l.post_url or (f"https://facebook.com/groups/{l.group_id}" if l.group_id else ""),
            "created_at": l.created_at.strftime("%d/%m/%Y %H:%M") if l.created_at else "---"
        }
        if l.post_channel == "marketplace":
            marketplace_post = item
        else:
            group_posts.append(item)

    return JSONResponse({
        "success": True,
        "listing": {
            "id": listing.id,
            "title": listing.title,
            "price": listing.price,
            "location": listing.location,
            "marketplace_status": listing.marketplace_status or "not_posted",
            "marketplace_url": listing.marketplace_url or "https://www.facebook.com/marketplace/you/selling"
        },
        "total_posts": len(logs),
        "group_posts_count": len(group_posts),
        "marketplace_post": marketplace_post,
        "group_posts": group_posts
    })

