import os
import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Listing, PostLog
from app.services.ai_service import parse_and_refine_listing_ai

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

@router.get("/")
def list_listings(request: Request, db: Session = Depends(get_db)):
    listings = db.query(Listing).order_by(Listing.id.desc()).all()
    # Gắn kèm số lượng bài đã đăng cho từng căn BĐS và phân tích danh sách ảnh
    for item in listings:
        item.group_posts_count = db.query(PostLog).filter(PostLog.listing_id == item.id, PostLog.post_channel == 'group').count()
        item.has_marketplace = db.query(PostLog).filter(PostLog.listing_id == item.id, PostLog.post_channel == 'marketplace').count() > 0
        try:
            item.photo_list = json.loads(item.images) if item.images else []
        except Exception:
            item.photo_list = []
        if not item.photo_list and item.image_url:
            item.photo_list = [item.image_url]

    return templates.TemplateResponse(
        request=request,
        name="listings.html",
        context={
            "request": request,
            "active_page": "listings",
            "page_title": "Kho Bất Động Sản",
            "listings": listings
        }
    )

@router.post("/parse-raw")
async def parse_raw_text(request: Request):
    """
    API nhận 1 đoạn văn bản thô người dùng dán vào,
    gọi Gemini để phân tích bóc tách và biên tập lại chuẩn môi giới.
    """
    try:
        body = await request.json()
        raw_text = body.get("raw_text", "").strip()
        if not raw_text:
            return JSONResponse({"success": False, "message": "Nội dung trống"}, status_code=400)
        
        parsed = parse_and_refine_listing_ai(raw_text)
        return JSONResponse({"success": True, "data": parsed})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.post("/upload-images")
async def upload_multiple_images(files: List[UploadFile] = File(...)):
    """
    API hỗ trợ tải nhiều ảnh cùng lúc, hoặc kéo thả nhiều ảnh từ máy tính
    Lưu vào thư mục /uploads và trả về danh sách URL xem ảnh
    """
    saved_urls = []
    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            ext = ".jpg"
        new_filename = f"bds_{uuid.uuid4().hex[:12]}{ext}"
        target_path = os.path.join(UPLOADS_DIR, new_filename)
        with open(target_path, "wb") as f:
            content = await file.read()
            f.write(content)
        saved_urls.append(f"/uploads/{new_filename}")

    return JSONResponse({"success": True, "urls": saved_urls})

@router.post("/")
async def create_listing(
    raw_content: Optional[str] = Form(""),
    title: Optional[str] = Form(""),
    price: Optional[float] = Form(0.0),
    area: Optional[float] = Form(0.0),
    location: Optional[str] = Form(""),
    description: Optional[str] = Form(""),
    image_url: Optional[str] = Form(""),
    uploaded_images_json: Optional[str] = Form("[]"),
    status: str = Form("available"),
    db: Session = Depends(get_db)
):
    # Nếu người dùng chỉ dán vào ô Text box duy nhất mà chưa bấm AI parse trước
    if raw_content and (not title or not location):
        parsed = parse_and_refine_listing_ai(raw_content)
        title = parsed.get("title") or title or "Bất động sản mới"
        price = parsed.get("price") if (price is None or price == 0) else price
        area = parsed.get("area") if (area is None or area == 0) else area
        location = parsed.get("location") or location or "Hải Phòng"
        description = parsed.get("refined_content") or raw_content

    # Xử lý danh sách ảnh
    images_list = []
    try:
        images_list = json.loads(uploaded_images_json) if uploaded_images_json else []
    except Exception:
        images_list = []

    if image_url and image_url not in images_list:
        images_list.insert(0, image_url)
    
    primary_img = images_list[0] if images_list else (image_url or "")

    new_listing = Listing(
        title=title or "Bất động sản mới",
        price=price or 0.0,
        area=area or 0.0,
        location=location or "Hải Phòng",
        description=description or "",
        image_url=primary_img,
        images=json.dumps(images_list, ensure_ascii=False),
        status=status
    )
    db.add(new_listing)
    db.commit()
    return RedirectResponse(url="/listings", status_code=303)

@router.get("/delete/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    item = db.query(Listing).filter(Listing.id == listing_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/listings", status_code=303)

@router.post("/bulk-delete")
async def bulk_delete_listings(request: Request, db: Session = Depends(get_db)):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            ids = data.get("ids", [])
        else:
            form = await request.form()
            raw_ids = form.get("ids", "[]")
            try:
                ids = json.loads(raw_ids)
            except Exception:
                ids = [x.strip() for x in str(raw_ids).split(",") if x.strip()]
        
        int_ids = [int(i) for i in ids if str(i).isdigit() or isinstance(i, int)]
        if int_ids:
            db.query(Listing).filter(Listing.id.in_(int_ids)).delete(synchronize_session=False)
            db.commit()
            return JSONResponse({"success": True, "count": len(int_ids), "message": f"Đã xóa {len(int_ids)} BĐS thành công!"})
        return JSONResponse({"success": False, "message": "Chưa chọn bất động sản nào để xóa"}, status_code=400)
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.post("/bulk-status")
async def bulk_status_listings(request: Request, db: Session = Depends(get_db)):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            ids = data.get("ids", [])
            status = data.get("status", "available")
        else:
            form = await request.form()
            raw_ids = form.get("ids", "[]")
            status = form.get("status", "available")
            try:
                ids = json.loads(raw_ids)
            except Exception:
                ids = [x.strip() for x in str(raw_ids).split(",") if x.strip()]
        
        int_ids = [int(i) for i in ids if str(i).isdigit() or isinstance(i, int)]
        if int_ids:
            db.query(Listing).filter(Listing.id.in_(int_ids)).update({"status": status}, synchronize_session=False)
            db.commit()
            return JSONResponse({"success": True, "count": len(int_ids), "status": status, "message": f"Đã cập nhật trạng thái {len(int_ids)} BĐS!"})
        return JSONResponse({"success": False, "message": "Chưa chọn bất động sản nào để cập nhật"}, status_code=400)
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
