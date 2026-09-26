import json
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Listing, PostLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def list_listings(request: Request, db: Session = Depends(get_db)):
    listings = db.query(Listing).order_by(Listing.id.desc()).all()
    # Gắn kèm số lượng bài đã đăng cho từng căn BĐS
    for item in listings:
        item.group_posts_count = db.query(PostLog).filter(PostLog.listing_id == item.id, PostLog.post_channel == 'group').count()
        item.has_marketplace = db.query(PostLog).filter(PostLog.listing_id == item.id, PostLog.post_channel == 'marketplace').count() > 0
    
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

@router.post("/")
def create_listing(
    title: str = Form(...),
    price: float = Form(...),
    area: float = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
    status: str = Form("available"),
    db: Session = Depends(get_db)
):
    new_listing = Listing(
        title=title,
        price=price,
        area=area,
        location=location,
        description=description,
        image_url=image_url,
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
