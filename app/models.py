from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from app.database import Base
import datetime

class Listing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    area = Column(Float, nullable=False, default=0.0)
    location = Column(String(255), nullable=False, default="")
    description = Column(Text, nullable=True, default="")
    image_url = Column(String(500), nullable=True, default="")
    contact = Column(String(100), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class FacebookAccount(Base):
    __tablename__ = "fb_accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True, default="FB User")
    uid = Column(String(50), unique=True, index=True)
    cookie = Column(Text, nullable=True)
    token = Column(Text, nullable=True)
    status = Column(String(50), default="Live")
    last_checked = Column(DateTime, default=datetime.datetime.utcnow)

class FacebookGroup(Base):
    __tablename__ = "fb_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    group_id = Column(String(50), unique=True, index=True)
    members_count = Column(Integer, default=0)
    privacy = Column(String(50), default="PUBLIC")
    account_uid = Column(String(50), nullable=True)

class PostLog(Base):
    __tablename__ = "post_logs"
    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String(100), nullable=True)
    account_uid = Column(String(50), nullable=True)
    group_name = Column(String(255), nullable=True)
    group_id = Column(String(50), nullable=True)
    listing_title = Column(String(255), nullable=True)
    status = Column(String(50), default="success") # success, failed, pending
    message = Column(Text, nullable=True)
    post_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Text, nullable=True)
