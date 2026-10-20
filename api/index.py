"""
Vercel Serverless Function Entrypoint for KisanSathi FastAPI.
"""

import sys
import os

# Ensure project root is in Python module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.main import app

# Ensure tables and seed data are populated if running on fresh serverless instance
from backend.database import SessionLocal, Base, engine
from backend.seed_data import reset_and_seed_database
from backend.models import Farmer

try:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(Farmer).count() == 0:
        reset_and_seed_database(db)
    db.close()
except Exception as e:
    print(f"Serverless init note: {e}")
