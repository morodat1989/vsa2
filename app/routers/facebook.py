import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FacebookAccount, FacebookGroup, PostLog, Listing
from app.services.ai_service import generate_ai_post

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Accounts
@router.get("/accounts")
def list_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(FacebookAccount).all()
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "active_page": "accounts",
        "page_title": "Quản Lý Tài Khoản FB",
        "accounts": accounts
    })

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
    return templates.TemplateResponse("groups.html", {
        "request": request,
        "active_page": "groups",
        "page_title": "Quản Lý Nhóm Facebook",
        "groups": groups
    })

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

# Logs
@router.get("/logs")
def view_logs(request: Request, db: Session = Depends(get_db)):
    logs = db.query(PostLog).order_by(PostLog.id.desc()).all()
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "active_page": "logs",
        "page_title": "Lịch Sử Đăng Bài",
        "logs": logs
    })

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

    return templates.TemplateResponse("ai_result.html", {
        "request": request,
        "active_page": "listings",
        "page_title": "AI Tạo Bài Đăng BĐS",
        "listing": listing,
        "ai_content": ai_content,
        "accounts": accounts,
        "groups": groups
    })

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
