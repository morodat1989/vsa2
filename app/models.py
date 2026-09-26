from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    listing_code = Column(String, index=True)
    title = Column(String)
    category = Column(String, default="Bán nhà")
    price = Column(String)
    area = Column(String)
    location = Column(String)
    floors = Column(Integer, default=1)
    bedrooms = Column(Integer, default=1)
    bathrooms = Column(Integer, default=1)
    description = Column(Text, default="")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, index=True)
    cookie = Column(Text, nullable=True)
    status = Column(String, default="Hoạt động")

    fb_name = Column(String, nullable=True)
    avatar_url = Column(Text, nullable=True)
    profile_name = Column(String, nullable=True)
    cdp_port = Column(Integer, nullable=True)

FBAccount = Account

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String)
    url = Column(String, unique=True)
    category = Column(String, default="Bất động sản")

class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    body = Column(Text)