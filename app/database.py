import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'vsa.db')}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def run_migrations():
    """Tự động kiểm tra và thêm các cột mới vào SQLite hiện có mà không làm mất dữ liệu cũ"""
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()
            
            # 1. Bảng listings
            if "listings" in table_names:
                existing_cols = [c["name"] for c in inspector.get_columns("listings")]
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN status VARCHAR(50) DEFAULT 'available'"))
                if "contact" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN contact VARCHAR(100) DEFAULT ''"))
                if "marketplace_status" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN marketplace_status VARCHAR(50) DEFAULT 'not_posted'"))
                if "marketplace_url" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN marketplace_url VARCHAR(500) DEFAULT ''"))
                if "marketplace_posted_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN marketplace_posted_at DATETIME"))
                conn.commit()

            # 2. Bảng fb_accounts
            if "fb_accounts" in table_names:
                acc_cols = [c["name"] for c in inspector.get_columns("fb_accounts")]
                if "status" not in acc_cols:
                    conn.execute(text("ALTER TABLE fb_accounts ADD COLUMN status VARCHAR(50) DEFAULT 'Live'"))
                    conn.commit()

            # 3. Bảng post_logs
            if "post_logs" in table_names:
                log_cols = [c["name"] for c in inspector.get_columns("post_logs")]
                if "listing_id" not in log_cols:
                    conn.execute(text("ALTER TABLE post_logs ADD COLUMN listing_id INTEGER"))
                if "post_channel" not in log_cols:
                    conn.execute(text("ALTER TABLE post_logs ADD COLUMN post_channel VARCHAR(50) DEFAULT 'group'"))
                if "members_count" not in log_cols:
                    conn.execute(text("ALTER TABLE post_logs ADD COLUMN members_count INTEGER DEFAULT 0"))
                conn.commit()
    except Exception as e:
        print(f"[Migration Warning] {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

