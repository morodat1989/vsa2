from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Setting
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def view_settings(request: Request, db: Session = Depends(get_db)):
    settings_dict = {}
    rows = db.query(Setting).all()
    for r in rows:
        settings_dict[r.key] = r.value

    if "gemini_api_key" not in settings_dict and os.environ.get("GEMINI_API_KEY"):
        settings_dict["gemini_api_key"] = os.environ.get("GEMINI_API_KEY")

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "request": request,
            "active_page": "settings",
            "page_title": "Cài Đặt Hệ Thống",
            "settings": settings_dict
        }
    )

@router.post("/")
def save_settings(
    gemini_api_key: str = Form(""),
    post_delay: str = Form("60"),
    max_posts_per_account: str = Form("20"),
    db: Session = Depends(get_db)
):
    updates = {
        "gemini_api_key": gemini_api_key,
        "post_delay": post_delay,
        "max_posts_per_account": max_posts_per_account
    }
    for k, v in updates.items():
        row = db.query(Setting).filter(Setting.key == k).first()
        if row:
            row.value = v
        else:
            db.add(Setting(key=k, value=v))
    db.commit()
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
    return RedirectResponse(url="/settings?success=1", status_code=303)
