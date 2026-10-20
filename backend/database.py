"""
KrishiSathi Database Engine and Session Management.
Uses SQLite for zero-configuration, fully offline operation.
"""

import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Path to SQLite database file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# On Vercel serverless environments, the filesystem is read-only except /tmp
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/krishisathi.db"
    ORIGINAL_DB = os.path.join(BASE_DIR, "krishisathi.db")
    if not os.path.exists(DB_PATH) and os.path.exists(ORIGINAL_DB):
        try:
            shutil.copyfile(ORIGINAL_DB, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = os.path.join(BASE_DIR, "krishisathi.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite connection args (check_same_thread=False allows multi-threaded access in FastAPI)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI Dependency for database session injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
