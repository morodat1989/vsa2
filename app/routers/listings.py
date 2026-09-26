from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Listing
from app.services.ai_service import generate_ai_content


router = APIRouter(prefix="/listings", tags=["Listings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_listings(request: Request, db: Session = Depends(get_db)):
    listings = db.query(Listing).all()

    return templates.TemplateResponse(
        request,
        "listings.html",
        {
            "listings": listings
        }
    )


@router.get("/new")
def new_listing_form(request: Request):
    return templates.TemplateResponse(
        request,
        "listing_form.html",
        {}
    )


@router.post("")
def create_listing(
    request: Request,
    title: str = Form(...),
    listing_code: str = Form(...),
    price: str = Form(...),
    area: float = Form(...),
    location: str = Form(...),
    floors: int = Form(1),
    bedrooms: int = Form(1),
    bathrooms: int = Form(1),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    new_item = Listing(
        title=title,
        listing_code=listing_code,
        price=price,
        area=area,
        location=location,
        floors=floors,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        description=description
    )

    db.add(new_item)
    db.commit()

    return RedirectResponse(
        url="/listings",
        status_code=303
    )


@router.get("/{listing_id}/generate-ai")
async def generate_listing_ai(
    listing_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy BĐS"
        )

    ai_result = generate_ai_content(listing)

    return templates.TemplateResponse(
        request,
        "ai_result.html",
        {
            "listing": listing,
            "ai_content": ai_result
        }
    )


@router.post("/{listing_id}/update-from-ai")
async def update_listing_from_ai(
    listing_id: int,
    description: str = Form(...),
    db: Session = Depends(get_db)
):
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy BĐS"
        )

    listing.title = description

    db.add(listing)
    db.commit()
    db.refresh(listing)

    return RedirectResponse(
        url="/listings",
        status_code=303
    )