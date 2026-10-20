"""
Village Disease Radar Engine.

Key Innovation:
Traditional agricultural advisory is siloed: each farmer suffers or acts alone.
Pests and fungal airborne spores (e.g. Phytophthora infestans / Late Blight)
do not respect field boundaries. They spread along micro-climatic wind corridors.

Privacy-by-Design Architecture:
- Reports hold ONLY: {crop, disease, date, village_id}.
- No farmer name, phone number, or exact survey/GPS coordinates are ever stored or exposed.
- Reports are anonymized and aggregated at the village centroid level.

Outbreak Clustering Algorithm:
1. Window: Reports within the last 7 days.
2. Distance metric: Great-circle distance using Haversine formula (Earth radius R = 6371 km).
3. Spatial threshold: Distance <= 10.0 km.
4. Density threshold: >= 3 independent reports of the same (crop, disease) within the 10-km radius.
5. Action: Triggers a Community Outbreak Alert.
   Advisory message strictly advises:
   "Disease X reported near you. INSPECT your field today."
   (CRITICAL RULE: Always use "inspect", NEVER "spray" to avoid unnecessary pesticide runoff).
"""

import json
import os
import math
from datetime import date, timedelta, datetime
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from backend.models import DiseaseReport, DiseaseAlert, Farmer

VILLAGES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "villages.json"
)

with open(VILLAGES_PATH, "r", encoding="utf-8") as f:
    VILLAGES_LIST = json.load(f)

VILLAGES_MAP = {v["id"]: v for v in VILLAGES_LIST}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two geographic coordinates in kilometers.
    
    Formula:
      a = sin^2(delta_lat/2) + cos(lat1) * cos(lat2) * sin^2(delta_lon/2)
      c = 2 * atan2(sqrt(a), sqrt(1-a))
      d = R * c  (Earth radius R = 6371 km)
    """
    radius = 6371.0  # Earth mean radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2) + \
        math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)

    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(radius * c, 2)


def get_nearby_villages(center_village_id: str, max_radius_km: float = 10.0) -> List[Dict[str, Any]]:
    """
    Returns list of all villages within max_radius_km from the center village.
    """
    center = VILLAGES_MAP.get(center_village_id)
    if not center:
        return []

    nearby = []
    for vid, vdata in VILLAGES_MAP.items():
        dist = haversine_distance_km(center["latitude"], center["longitude"], vdata["latitude"], vdata["longitude"])
        if dist <= max_radius_km:
            nearby.append({
                "village_id": vid,
                "name": vdata["name"],
                "distance_km": dist,
                "latitude": vdata["latitude"],
                "longitude": vdata["longitude"]
            })
    return nearby


def file_anonymous_disease_report(
    crop: str,
    disease: str,
    village_id: str,
    confidence: float,
    image_filename: str,
    db: Session,
    report_date: date = None
) -> Dict[str, Any]:
    """
    Records an anonymous observation report and checks if an outbreak cluster alert is triggered.
    Strictly verifies that no farmer PII is accepted or stored.
    """
    if report_date is None:
        report_date = date.today()

    new_report = DiseaseReport(
        crop=crop.lower(),
        disease=disease,
        village_id=village_id,
        report_date=report_date,
        confidence=confidence,
        image_filename=image_filename,
        confirmed_by_officer=False,
        created_at=datetime.utcnow()
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # Evaluate if this new report triggers a Village Disease Radar outbreak alert
    alert = evaluate_radar_outbreak(crop.lower(), disease, db)

    return {
        "report_id": new_report.id,
        "crop": new_report.crop,
        "disease": new_report.disease,
        "village_id": new_report.village_id,
        "report_date": new_report.report_date.isoformat(),
        "outbreak_alert_triggered": alert is not None,
        "alert_id": alert.id if alert else None
    }


def evaluate_radar_outbreak(
    crop: str,
    disease: str,
    db: Session,
    window_days: int = 7,
    max_radius_km: float = 10.0,
    min_reports_trigger: int = 3
) -> DiseaseAlert:
    """
    Evaluates whether the 3-in-7-days within 10 km rule is met.
    If met, creates or updates a DiseaseAlert.
    """
    today = date.today()
    cutoff_date = today - timedelta(days=window_days)

    # Fetch all reports of this crop & disease within the time window
    recent_reports = db.query(DiseaseReport).filter(
        DiseaseReport.crop == crop.lower(),
        DiseaseReport.disease == disease,
        DiseaseReport.report_date >= cutoff_date
    ).all()

    if len(recent_reports) < min_reports_trigger:
        return None

    # Group reports by village
    village_report_counts = {}
    for r in recent_reports:
        village_report_counts[r.village_id] = village_report_counts.get(r.village_id, 0) + 1

    # For each village with reports, calculate the spatial cluster count within 10 km
    for v_id in village_report_counts.keys():
        nearby_nodes = get_nearby_villages(v_id, max_radius_km=max_radius_km)
        cluster_vids = [n["village_id"] for n in nearby_nodes]

        # Count total reports across this 10-km cluster
        cluster_count = sum(village_report_counts.get(vid, 0) for vid in cluster_vids)

        if cluster_count >= min_reports_trigger:
            cluster_vids_sorted = sorted(list(set(cluster_vids)))
            vids_str = ",".join(cluster_vids_sorted)

            # Check if active alert already exists
            existing_alert = db.query(DiseaseAlert).filter(
                DiseaseAlert.crop == crop.lower(),
                DiseaseAlert.disease == disease,
                DiseaseAlert.outbreak_date >= cutoff_date
            ).first()

            if existing_alert:
                existing_alert.report_count = cluster_count
                existing_alert.village_ids = vids_str
                db.commit()
                db.refresh(existing_alert)
                return existing_alert

            # Create new Alert
            new_alert = DiseaseAlert(
                crop=crop.lower(),
                disease=disease,
                outbreak_date=today,
                village_ids=vids_str,
                status="Reported",
                report_count=cluster_count,
                officer_notes="Radar detection: >= 3 reports in 10 km cluster. Initial status: Reported.",
                created_at=datetime.utcnow()
            )
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)
            return new_alert

    return None


def get_active_alerts_for_farmer(farmer: Farmer, db: Session) -> List[Dict[str, Any]]:
    """
    Checks if there are any active outbreak alerts affecting this farmer's village and crop.
    Message strictly says "Inspect your field today", never "spray".
    """
    today = date.today()
    cutoff_date = today - timedelta(days=7)

    alerts = db.query(DiseaseAlert).filter(
        DiseaseAlert.crop == farmer.crop.lower(),
        DiseaseAlert.outbreak_date >= cutoff_date
    ).all()

    farmer_alerts = []
    for a in alerts:
        affected_villages = [v.strip() for v in a.village_ids.split(",")]
        if farmer.village_id in affected_villages:
            v_name = VILLAGES_MAP.get(farmer.village_id, {}).get("name", farmer.village_id)
            farmer_alerts.append({
                "alert_id": a.id,
                "disease": a.disease,
                "crop": a.crop,
                "status": a.status,
                "report_count": a.report_count,
                "advisory_message": (
                    f"Warning: {a.disease} reported near your village ({v_name}). "
                    f"Inspect your {farmer.crop.capitalize()} field today. "
                    f"Do not spray chemicals without confirming symptoms."
                ),
                "is_confirmed_by_officer": (a.status == "Confirmed")
            })

    return farmer_alerts
