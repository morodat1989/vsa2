from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn

from app.database import Base, engine, get_db
from app.models import Account, Group, Listing
from app.routers import facebook, listings

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FB Tool Management")
app.include_router(listings.router)
app.include_router(facebook.router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/")
def dashboard_view(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).order_by(Account.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "accounts": accounts,
            "accounts_count": len(accounts),
            "groups_count": db.query(Group).count(),
            "listings_count": db.query(Listing).count(),
        },
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
