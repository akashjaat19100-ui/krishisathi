"""
Weather Service with Live Open-Meteo Integration and Offline CSV Fallback.

Design:
- First attempts to contact Open-Meteo (free, no API key required).
- If offline, sandbox, or network error occurs, seamlessly falls back to:
  1. Local SQLite cache (WeatherCache table)
  2. Bundled fallback dataset (data/weather_sample.csv)
- Returns an explicit `is_offline` flag and `source` descriptor so the frontend
  can render an "Offline Cached Weather" badge.
"""

import os
import csv
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from backend.models import WeatherCache
from backend.engine.hargreaves import calculate_hargreaves_et0, get_day_of_year

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "weather_sample.csv"
)

# Pune coordinates as default reference
DEFAULT_LATITUDE = 18.3167
DEFAULT_LONGITUDE = 73.8833


def load_sample_csv_data() -> Dict[str, Dict[str, Any]]:
    """Loads bundled 14-day weather CSV into memory."""
    records = {}
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d_str = row["date"].strip()
                tmax = float(row["tmax"])
                tmin = float(row["tmin"])
                tmean = float(row.get("tmean", (tmax + tmin) / 2.0))
                precip = float(row.get("precip_mm", 0.0))
                records[d_str] = {
                    "date": d_str,
                    "tmax": tmax,
                    "tmin": tmin,
                    "tmean": tmean,
                    "precip_mm": precip,
                    "condition": row.get("condition", "Partly Cloudy")
                }
    return records


def get_cached_weather(db: Session, target_date: date) -> Optional[WeatherCache]:
    """Retrieves cached weather from SQLite if available."""
    return db.query(WeatherCache).filter(WeatherCache.date == target_date).first()


def cache_weather_record(
    db: Session,
    record_date: date,
    tmax: float,
    tmin: float,
    tmean: float,
    precip_mm: float,
    ra_mm_day: float,
    source: str
) -> WeatherCache:
    """Inserts or updates a weather record in SQLite."""
    existing = get_cached_weather(db, record_date)
    if existing:
        existing.tmax = tmax
        existing.tmin = tmin
        existing.tmean = tmean
        existing.precip_mm = precip_mm
        existing.ra_mm_day = ra_mm_day
        existing.source = source
        existing.fetched_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    new_record = WeatherCache(
        date=record_date,
        tmax=tmax,
        tmin=tmin,
        tmean=tmean,
        precip_mm=precip_mm,
        ra_mm_day=ra_mm_day,
        source=source,
        fetched_at=datetime.utcnow()
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record


async def fetch_live_open_meteo(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    """
    Attempts to fetch 7-day daily forecast from Open-Meteo API.
    Timeout is set to 2.5 seconds to keep the app responsive even with slow connections.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=auto"
    )
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        # Expected when offline, blocked sandbox, or DNS failure
        pass
    return None


async def get_daily_weather(
    target_date: date,
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE,
    db: Session = None
) -> Dict[str, Any]:
    """
    Gets daily weather for target_date.
    Order of precedence:
      1. Live Open-Meteo fetch (if online)
      2. SQLite WeatherCache (if already fetched or seeded)
      3. Bundled sample CSV (data/weather_sample.csv)
    """
    # 1. Try Live Open-Meteo if today or near future
    days_diff = abs((target_date - date.today()).days)
    if days_diff <= 7:
        live_data = await fetch_live_open_meteo(latitude, longitude)
        if live_data and "daily" in live_data:
            dates = live_data["daily"].get("time", [])
            tmax_list = live_data["daily"].get("temperature_2m_max", [])
            tmin_list = live_data["daily"].get("temperature_2m_min", [])
            precip_list = live_data["daily"].get("precipitation_sum", [])

            target_iso = target_date.isoformat()
            if target_iso in dates:
                idx = dates.index(target_iso)
                tmax = float(tmax_list[idx])
                tmin = float(tmin_list[idx])
                tmean = round((tmax + tmin) / 2.0, 1)
                precip = float(precip_list[idx]) if precip_list[idx] is not None else 0.0

                j_day = get_day_of_year(target_date)
                et0 = calculate_hargreaves_et0(tmax, tmin, latitude, j_day, tmean)

                if db:
                    cache_weather_record(db, target_date, tmax, tmin, tmean, precip, et0, "live_open_meteo")

                return {
                    "date": target_iso,
                    "tmax": tmax,
                    "tmin": tmin,
                    "tmean": tmean,
                    "precip_mm": precip,
                    "et0_mm": et0,
                    "source": "live_open_meteo",
                    "is_offline": False,
                    "badge_text": "Live Weather (Open-Meteo)"
                }

    # 2. Check SQLite cache
    if db:
        cached = get_cached_weather(db, target_date)
        if cached:
            j_day = get_day_of_year(target_date)
            et0 = calculate_hargreaves_et0(cached.tmax, cached.tmin, latitude, j_day, cached.tmean)
            return {
                "date": cached.date.isoformat(),
                "tmax": cached.tmax,
                "tmin": cached.tmin,
                "tmean": cached.tmean,
                "precip_mm": cached.precip_mm,
                "et0_mm": et0,
                "source": cached.source,
                "is_offline": (cached.source != "live_open_meteo"),
                "badge_text": "Offline (Cached DB)"
            }

    # 3. Fallback to bundled sample CSV
    sample_records = load_sample_csv_data()
    target_iso = target_date.isoformat()
    record = sample_records.get(target_iso)

    if not record:
        # Use latest available record from CSV or typical Pune autumn day
        latest_key = sorted(sample_records.keys())[-1] if sample_records else None
        if latest_key:
            record = sample_records[latest_key]
        else:
            record = {"tmax": 32.0, "tmin": 19.5, "tmean": 25.8, "precip_mm": 0.0}

    tmax = float(record["tmax"])
    tmin = float(record["tmin"])
    tmean = float(record.get("tmean", (tmax + tmin) / 2.0))
    precip = float(record.get("precip_mm", 0.0))

    j_day = get_day_of_year(target_date)
    et0 = calculate_hargreaves_et0(tmax, tmin, latitude, j_day, tmean)

    if db:
        cache_weather_record(db, target_date, tmax, tmin, tmean, precip, et0, "cached_sample")

    return {
        "date": target_iso,
        "tmax": tmax,
        "tmin": tmin,
        "tmean": tmean,
        "precip_mm": precip,
        "et0_mm": et0,
        "source": "cached_sample",
        "is_offline": True,
        "badge_text": "Offline (Sample CSV)"
    }
