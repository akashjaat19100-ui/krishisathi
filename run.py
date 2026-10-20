"""
KrishiSathi Local Prototype Launcher.
Run with a single command:
    python run.py
or:
    ./run.sh

Automatically ensures SQLite database is seeded with:
- 8 smallholder farmers across 5 Pune villages
- 2 shared community soil sensor clusters (Tier 1)
- 14 days of calibrated Pune weather
and starts the local web server at http://localhost:8000.
"""

import os
import sys

# Ensure current directory is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from backend.database import engine, Base, SessionLocal
from backend.seed_data import reset_and_seed_database
from backend.models import Farmer

def ensure_database_initialized():
    """Initializes tables and seeds data if running for the first time."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        farmer_count = db.query(Farmer).count()
        if farmer_count == 0:
            print("[*] First-time setup detected. Seeding 8 farmers, 2 clusters, and 14-day weather...")
            reset_and_seed_database(db)
            print("[✓] Seed data created successfully.")
        else:
            print(f"[*] Database ready ({farmer_count} farmers loaded).")
    finally:
        db.close()

def get_local_ip():
    """Finds the local network IP of this machine for phone/device access."""
    import socket, subprocess, sys
    # On macOS, ipconfig getifaddr en0 gives the active Wi-Fi IP
    if sys.platform == "darwin":
        try:
            ip = subprocess.getoutput("ipconfig getifaddr en0").strip()
            if ip and not ip.startswith("ipconfig:"):
                return ip
        except Exception:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.59.157.233"

def main():
    print("=" * 72)
    print("  🌱 KisanSathi: Tiered Irrigation & Crop Disease Radar")
    print("  Rural Agronomy Advisory Prototype for Marginal Farmers in India")
    print("=" * 72)

    ensure_database_initialized()

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    local_ip = get_local_ip()

    print(f"\n[✓] Server is LIVE and accessible across all devices:")
    print(f"    💻 Laptop / Local Browser:    http://localhost:{port}")
    print(f"    📱 Phone / Tablet on Wi-Fi:   http://{local_ip}:{port}")
    print(f"\n    Press Ctrl+C to stop the server.\n")

    import uvicorn
    uvicorn.run("backend.main:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
