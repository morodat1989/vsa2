from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Listing

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def list_listings(request: Request, db: Session = Depends(get_db)):
    listings = db.query(Listing).order_by(Listing.id.desc()).all()
    return templates.TemplateResponse("listings.html", {
        "request": request,
        "active_page": "listings",
        "page_title": "Kho Bất Động Sản",
        "listings": listings
    })

@router.post("/")
def create_listing(
    title: str = Form(...),
    price: float = Form(...),
    area: float = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
    db: Session = Depends(get_db)
):
    new_listing = Listing(
        title=title,
        price=price,
        area=area,
        location=location,
        description=description,
        image_url=image_url
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
