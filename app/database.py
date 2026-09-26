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
                    print("[Migration] Đã tự động bổ sung cột 'status' vào bảng listings.")
                if "contact" not in existing_cols:
                    conn.execute(text("ALTER TABLE listings ADD COLUMN contact VARCHAR(100) DEFAULT ''"))
                    print("[Migration] Đã tự động bổ sung cột 'contact' vào bảng listings.")
                conn.commit()

            # 2. Bảng fb_accounts
            if "fb_accounts" in table_names:
                acc_cols = [c["name"] for c in inspector.get_columns("fb_accounts")]
                if "status" not in acc_cols:
                    conn.execute(text("ALTER TABLE fb_accounts ADD COLUMN status VARCHAR(50) DEFAULT 'Live'"))
                    conn.commit()
    except Exception as e:
        print(f"[Migration Warning] {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

