"""
KrishiSathi FastAPI Main Application.

Features:
1. Farmer Registration & Krishi Mitra Helper Mode
2. Tier 0 Irrigation Engine (Hargreaves ET0 + FAO-56 Soil Moisture Balance)
3. Phone Simulator API (Missed-call callback, SpeechSynthesis payloads, SMS bubbles)
4. Tier 1 Shared Sensor Node API (ESP32 telemetry ingestion, cluster Dr correction)
5. Tier 2 Leaf-Photo Disease Check & Unsure Officer Routing
6. Village Disease Radar (Privacy-preserving outbreak clustering)
7. Extension Officer Dashboard APIs
8. One-click Demo Reset & Outbreak Simulator
9. Static file serving for mobile-first web frontend
"""

import os
import json
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from backend.database import engine, get_db, Base
from backend.models import (
    Farmer, IrrigationState, IrrigationLog,
    SensorCluster, SensorReading,
    DiseaseReport, DiseaseAlert, OfficerQueueItem, WeatherCache
)
from backend.schemas import (
    FarmerCreate, FarmerResponse, IrrigationAdvisoryResponse,
    IrrigationConfirmRequest, SensorReadingCreate,
    DiseaseReportCreate, DiseaseAlertResponse, OfficerAlertUpdateRequest
)
from backend.engine.hargreaves import calculate_hargreaves_et0, get_day_of_year
from backend.engine.water_balance import (
    CROP_SOIL_CONFIG, get_crop_growth_stage, compute_soil_water_limits,
    update_daily_deficit, evaluate_irrigation_signal, calculate_pumping_requirement,
    calculate_weekly_savings
)
from backend.engine.weather_service import get_daily_weather
from backend.sensors.sensor_manager import process_sensor_reading, generate_fake_esp32_reading
from backend.radar.disease_radar import (
    file_anonymous_disease_report, evaluate_radar_outbreak,
    get_active_alerts_for_farmer, VILLAGES_MAP, VILLAGES_LIST, haversine_distance_km
)
from backend.classifier.leaf_classifier import inspect_leaf_image
from backend.seed_data import reset_and_seed_database, simulate_outbreak_scenario

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="KisanSathi Advisory API",
    description="Tiered Irrigation & Disease Radar for Smallholder Farmers",
    version="1.0.0"
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load localization files into memory
I18N_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
TRANSLATIONS: Dict[str, Dict[str, Any]] = {}
for lang in ["en", "hi", "mr"]:
    l_path = os.path.join(I18N_DIR, f"{lang}.json")
    if os.path.exists(l_path):
        with open(l_path, "r", encoding="utf-8") as f:
            TRANSLATIONS[lang] = json.load(f)


def get_localized_strings(lang: str) -> Dict[str, Any]:
    return TRANSLATIONS.get(lang.lower(), TRANSLATIONS.get("en", {}))


# ============================================================================
# 1. FARMER REGISTRATION & MANAGEMENT (KRISHI MITRA & FARMER)
# ============================================================================

@app.post("/api/farmers", response_model=FarmerResponse)
def register_farmer(payload: FarmerCreate, db: Session = Depends(get_db)):
    """Registers a new farmer with localized settings and initial irrigation state."""
    farmer = Farmer(
        name=payload.name,
        phone=payload.phone,
        village_id=payload.village_id,
        language=payload.language,
        crop=payload.crop.lower(),
        sowing_date=payload.sowing_date,
        soil_type=payload.soil_type.lower(),
        plot_area_m2=payload.plot_area_m2,
        pump_discharge_m3h=payload.pump_discharge_m3h,
        electricity_rate=payload.electricity_rate,
        pump_power_kw=payload.pump_power_kw,
        created_at=datetime.utcnow()
    )
    db.add(farmer)
    db.commit()
    db.refresh(farmer)

    # Initialize irrigation state at low deficit (moist soil after sowing/irrigation)
    init_state = IrrigationState(
        farmer_id=farmer.id,
        current_dr_mm=5.0,
        last_updated=date.today(),
        last_irrigation_date=payload.sowing_date,
        sensor_corrected=False,
        sensor_cluster_id=None
    )
    db.add(init_state)
    db.commit()

    resp = FarmerResponse.from_orm(farmer)
    resp.village_name = VILLAGES_MAP.get(farmer.village_id, {}).get("name", farmer.village_id)
    return resp


@app.get("/api/farmers", response_model=List[FarmerResponse])
def list_farmers(db: Session = Depends(get_db)):
    """Lists all farmers (personal phone number is hidden for privacy)."""
    farmers = db.query(Farmer).order_by(Farmer.id.asc()).all()
    results = []
    for f in farmers:
        fr = FarmerResponse.from_orm(f)
        fr.village_name = VILLAGES_MAP.get(f.village_id, {}).get("name", f.village_id)
        results.append(fr)
    return results


@app.get("/api/farmers/{farmer_id}", response_model=FarmerResponse)
def get_farmer(farmer_id: int, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    fr = FarmerResponse.from_orm(farmer)
    fr.village_name = VILLAGES_MAP.get(farmer.village_id, {}).get("name", farmer.village_id)
    return fr


# ============================================================================
# 2. IRRIGATION ADVISORY ENGINE (TIER 0)
# ============================================================================

@app.get("/api/irrigation/advisory/{farmer_id}", response_model=IrrigationAdvisoryResponse)
async def get_farmer_advisory(farmer_id: int, db: Session = Depends(get_db)):
    """
    Computes daily irrigation advisory for a farmer:
    - ET0 via Hargreaves formula
    - Crop growth stage & Kc coefficient
    - Soil moisture deficit Dr balance
    - Advisory Signal (RED, YELLOW, GREEN)
    - Pumping hours & refill volume
    - Rupee electricity savings
    - Outbreak alerts
    - Spoken and SMS localization
    """
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    today = date.today()
    village = VILLAGES_MAP.get(farmer.village_id, {"latitude": 18.3167, "longitude": 73.8833, "name": "Shivapur"})
    v_lat = village["latitude"]
    v_lon = village["longitude"]

    # 1. Weather & ET0
    weather = await get_daily_weather(today, latitude=v_lat, longitude=v_lon, db=db)
    et0 = weather["et0_mm"]

    # 2. Crop Growth & Kc
    days_sown = (today - farmer.sowing_date).days
    growth = get_crop_growth_stage(farmer.crop, days_sown)
    kc = growth["kc"]
    zr = growth["root_depth_m"]
    p = growth["depletion_fraction_p"]

    # 3. Soil Limits (TAW, RAW)
    taw, raw = compute_soil_water_limits(farmer.soil_type, zr, p)

    # 4. Current Deficit (Dr)
    state = farmer.state
    if not state:
        state = IrrigationState(
            farmer_id=farmer.id,
            current_dr_mm=round(raw * 0.8, 1),
            last_updated=today,
            sensor_corrected=False
        )
        db.add(state)
        db.commit()
        db.refresh(state)

    # Advance water balance if last updated before today and not already today
    if state.last_updated < today:
        days_gap = (today - state.last_updated).days
        current_dr = state.current_dr_mm
        for _ in range(days_gap):
            current_dr, _ = update_daily_deficit(
                dr_yesterday=current_dr,
                et0=et0,
                kc=kc,
                rain_mm=weather["precip_mm"],
                irrigation_applied_mm=0.0,
                taw=taw
            )
        state.current_dr_mm = current_dr
        state.last_updated = today
        db.commit()

    dr_today = state.current_dr_mm

    # 5. Signal Evaluation
    sig_eval = evaluate_irrigation_signal(dr_today, raw, taw, kc * et0, today)

    # 6. Pumping Requirements
    pump_req = calculate_pumping_requirement(dr_today, farmer.plot_area_m2, farmer.pump_discharge_m3h)

    # 7. Weekly Savings
    # Query confirmed irrigations in the last 7 days
    seven_days_ago = today - timedelta(days=7)
    past_irrigations = db.query(IrrigationLog).filter(
        IrrigationLog.farmer_id == farmer.id,
        IrrigationLog.action_type == "confirmed_irrigation",
        IrrigationLog.log_date >= seven_days_ago
    ).count()

    savings = calculate_weekly_savings(
        plot_area_m2=farmer.plot_area_m2,
        pump_discharge_m3h=farmer.pump_discharge_m3h,
        pump_power_kw=farmer.pump_power_kw,
        electricity_rate=farmer.electricity_rate,
        baseline_interval_days=5,
        days_in_period=7,
        actual_irrigations_count=past_irrigations,
        typical_refill_dr_mm=raw
    )

    # 8. Active Outbreak Alerts (Disease Radar)
    alerts = get_active_alerts_for_farmer(farmer, db)

    # 9. Localized Spoken & SMS Strings
    i18n = get_localized_strings(farmer.language)
    hours_str = str(pump_req["pumping_hours"])
    liters_str = f"{pump_req['volume_liters']:,}"

    if sig_eval["signal"] == "RED":
        signal_msg = i18n["signal_red"].format(hours=hours_str, liters=liters_str)
    elif sig_eval["signal"] == "YELLOW":
        signal_msg = i18n["signal_yellow"].format(hours=hours_str)
    else:
        signal_msg = i18n["signal_green"].format(next_date=sig_eval["next_check_date"])

    # Water saving tip
    tips = growth.get("water_saving_tips", [])
    selected_tip = tips[0] if tips else "Irrigate early morning or evening to reduce evaporation."

    greeting = i18n["greeting"].format(name=farmer.name)
    spoken_message = f"{greeting} {signal_msg} {selected_tip}"

    # If an alert is active, prepend urgent inspect notice
    if alerts:
        first_alert = alerts[0]
        alert_notice = i18n["alert_inspect"].format(
            disease=first_alert["disease"],
            village=village["name"],
            crop=farmer.crop.capitalize()
        )
        spoken_message = f"{alert_notice} {spoken_message}"

    sms_bubble_message = signal_msg

    # Sensor badge
    sensor_badge_text = (
        i18n["sensor_badge"].format(cluster_id=state.sensor_cluster_id or "Cluster Node")
        if state.sensor_corrected
        else i18n["model_badge"]
    )

    return IrrigationAdvisoryResponse(
        farmer_id=farmer.id,
        farmer_name=farmer.name,
        language=farmer.language,
        crop=farmer.crop,
        soil_type=farmer.soil_type,
        village_id=farmer.village_id,
        village_name=village["name"],
        signal=sig_eval["signal"],
        action_text=sig_eval["action_text"],
        urgency=sig_eval["urgency"],
        dr_mm=sig_eval["dr_mm"],
        raw_mm=sig_eval["raw_mm"],
        taw_mm=sig_eval["taw_mm"],
        depletion_pct=sig_eval["depletion_pct"],
        pumping_hours=pump_req["pumping_hours"],
        volume_liters=pump_req["volume_liters"],
        next_check_date=sig_eval["next_check_date"],
        days_until_trigger=sig_eval["days_until_trigger"],
        weather=weather,
        sensor_corrected=bool(state.sensor_corrected),
        sensor_cluster_id=state.sensor_cluster_id,
        sensor_badge_text=sensor_badge_text,
        water_saving_tip=selected_tip,
        weekly_savings=savings,
        active_alerts=alerts,
        spoken_message=spoken_message,
        sms_bubble_message=sms_bubble_message
    )


@app.post("/api/irrigation/confirm")
def confirm_irrigation(payload: IrrigationConfirmRequest, db: Session = Depends(get_db)):
    """
    Farmer or Krishi Mitra confirms 'I irrigated today'.
    Refills Dr deficit back to 0.0 (or applies hours) and records an IrrigationLog.
    """
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    state = farmer.state
    if not state:
        raise HTTPException(status_code=400, detail="Farmer has no irrigation state")

    old_dr = state.current_dr_mm
    today = date.today()

    # Calculate hours applied and volume
    pumping_info = calculate_pumping_requirement(old_dr, farmer.plot_area_m2, farmer.pump_discharge_m3h)
    hours = payload.hours_applied if payload.hours_applied is not None else pumping_info["pumping_hours"]
    liters = hours * farmer.pump_discharge_m3h * 1000.0

    # Reset Dr back to 0 (root zone refilled to field capacity)
    state.current_dr_mm = 0.0
    state.last_irrigation_date = today
    state.last_updated = today
    state.sensor_corrected = False

    log = IrrigationLog(
        farmer_id=farmer.id,
        log_date=today,
        action_type="confirmed_irrigation",
        dr_before_mm=old_dr,
        dr_after_mm=0.0,
        hours_applied=hours,
        water_liters_applied=liters,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {
        "status": "confirmed",
        "farmer_id": farmer.id,
        "dr_before_mm": old_dr,
        "dr_after_mm": 0.0,
        "hours_applied": hours,
        "liters_applied": liters,
        "message": "Irrigation recorded successfully. Deficit refilled to field capacity."
    }


# ============================================================================
# 3. PHONE SIMULATOR (MISSED-CALL / VOICE / SMS)
# ============================================================================

@app.post("/api/phone/missed-call")
async def simulate_missed_call(farmer_id: int = Query(...), db: Session = Depends(get_db)):
    """
    Simulates a missed-call advisory request:
    - Farmer dials KrishiSathi toll-free number and drops call after 1 ring.
    - System waits 2 seconds, then delivers an automated callback voice speech + SMS text.
    """
    advisory = await get_farmer_advisory(farmer_id=farmer_id, db=db)
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()

    # Speech Synthesis voice language tags
    voice_codes = {
        "mr": "mr-IN",
        "hi": "hi-IN",
        "en": "en-IN"
    }
    voice_tag = voice_codes.get(farmer.language, "en-IN")

    return {
        "status": "callback_ready",
        "ring_delay_seconds": 2,
        "farmer_name": farmer.name,
        "masked_phone": f"+91 {farmer.phone[:3]}***{farmer.phone[-3:]}",
        "signal": advisory.signal,
        "spoken_text": advisory.spoken_message,
        "sms_text": advisory.sms_bubble_message,
        "water_tip": advisory.water_saving_tip,
        "voice_tag": voice_tag,
        "weekly_saving_rupees": advisory.weekly_savings["rupees_saved"]
    }


# ============================================================================
# 4. SHARED SENSOR NODE (TIER 1)
# ============================================================================

@app.get("/api/sensor/clusters")
def get_sensor_clusters(db: Session = Depends(get_db)):
    """Lists all community sensor clusters with latest telemetry."""
    clusters = db.query(SensorCluster).all()
    results = []
    for c in clusters:
        v_name = VILLAGES_MAP.get(c.village_id, {}).get("name", c.village_id)
        # Count farmers in this cluster
        f_count = db.query(Farmer).filter(
            Farmer.village_id == c.village_id,
            Farmer.crop == c.crop,
            Farmer.soil_type == c.soil_type
        ).count()
        results.append({
            "id": c.id,
            "name": c.name,
            "village_id": c.village_id,
            "village_name": v_name,
            "crop": c.crop,
            "soil_type": c.soil_type,
            "last_reading_time": c.last_reading_time.isoformat() if c.last_reading_time else None,
            "last_raw_adc": c.last_raw_adc,
            "last_vwc_pct": c.last_vwc_pct,
            "last_deficit_mm": c.last_deficit_mm,
            "farmers_linked_count": f_count
        })
    return results


@app.post("/api/sensor/readings")
def post_sensor_reading(payload: SensorReadingCreate, db: Session = Depends(get_db)):
    """
    Ingests an ESP32 soil moisture sensor reading.
    Calibrates to deficit and overrides Dr for all farmers in that cluster if difference > margin.
    """
    try:
        result = process_sensor_reading(
            cluster_id=payload.cluster_id,
            raw_adc=payload.raw_adc,
            db=db,
            margin_threshold_mm=5.0
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/sensor/simulate-reading/{cluster_id}")
def simulate_sensor_reading(cluster_id: str, db: Session = Depends(get_db)):
    """Simulates an ESP32 reading for testing cluster synchronization."""
    cluster = db.query(SensorCluster).filter(SensorCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    raw_adc = generate_fake_esp32_reading(cluster)
    result = process_sensor_reading(cluster.id, raw_adc, db=db, margin_threshold_mm=5.0)
    return result


# ============================================================================
# 5. DISEASE CHECK (TIER 2)
# ============================================================================

@app.post("/api/disease/check")
async def check_leaf_disease(
    crop: str = Form(...),
    village_id: str = Form(...),
    file: Optional[UploadFile] = File(None),
    filename_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Analyzes uploaded leaf photo:
    - Runs classifier (TFLite or Mock)
    - If confidence < 70%, routes to Officer Queue with status 'Unsure'
    - Farmer can confirm result to broadcast anonymous report
    """
    image_bytes = b""
    fname = "leaf_photo.jpg"

    if file:
        image_bytes = await file.read()
        fname = file.filename or fname
    elif filename_hint:
        fname = filename_hint

    res = inspect_leaf_image(
        image_bytes=image_bytes,
        filename=fname,
        crop=crop,
        village_id=village_id,
        db=db
    )
    return res


@app.post("/api/disease/confirm-report")
def confirm_disease_report(payload: DiseaseReportCreate, db: Session = Depends(get_db)):
    """
    Farmer confirms disease diagnosis.
    Creates an anonymous report (strictly NO farmer personal data) and checks Disease Radar.
    """
    result = file_anonymous_disease_report(
        crop=payload.crop,
        disease=payload.disease,
        village_id=payload.village_id,
        confidence=payload.confidence,
        image_filename=payload.image_filename,
        db=db
    )
    return result


# ============================================================================
# 6. VILLAGE DISEASE RADAR & EXTENSION OFFICER DASHBOARD
# ============================================================================

@app.get("/api/radar/status")
def get_radar_status(db: Session = Depends(get_db)):
    """
    Returns complete Disease Radar overview:
    - Active Outbreak Alerts (Reported / Confirmed)
    - Village Report Counts ranked for Extension Officer visit priority
    - Village coordinates for Leaflet Map visualization
    """
    today = date.today()
    cutoff = today - timedelta(days=7)

    # All active alerts
    alerts = db.query(DiseaseAlert).filter(DiseaseAlert.outbreak_date >= cutoff).all()
    alerts_data = []
    for a in alerts:
        v_ids = [v.strip() for v in a.village_ids.split(",") if v.strip()]
        v_names = [VILLAGES_MAP.get(vid, {}).get("name", vid) for vid in v_ids]
        alerts_data.append({
            "id": a.id,
            "crop": a.crop,
            "disease": a.disease,
            "outbreak_date": a.outbreak_date.isoformat(),
            "village_ids": a.village_ids,
            "village_names": v_names,
            "status": a.status,
            "report_count": a.report_count,
            "officer_notes": a.officer_notes
        })

    # Village report statistics (ranked for officer travel priority)
    reports = db.query(DiseaseReport).filter(DiseaseReport.report_date >= cutoff).all()
    village_stats = {v["id"]: {"count": 0, "diseases": set(), "crops": set()} for v in VILLAGES_LIST}

    for r in reports:
        if r.village_id in village_stats:
            village_stats[r.village_id]["count"] += 1
            village_stats[r.village_id]["diseases"].add(r.disease)
            village_stats[r.village_id]["crops"].add(r.crop)

    ranked_villages = []
    for vid, data in village_stats.items():
        vinfo = VILLAGES_MAP[vid]
        ranked_villages.append({
            "village_id": vid,
            "name": vinfo["name"],
            "latitude": vinfo["latitude"],
            "longitude": vinfo["longitude"],
            "report_count": data["count"],
            "crops": list(data["crops"]),
            "diseases": list(data["diseases"])
        })

    ranked_villages.sort(key=lambda x: x["report_count"], reverse=True)

    return {
        "active_alerts": alerts_data,
        "ranked_villages": ranked_villages,
        "total_active_reports": len(reports),
        "villages": VILLAGES_LIST
    }


@app.post("/api/officer/alert/update")
def update_officer_alert(payload: OfficerAlertUpdateRequest, db: Session = Depends(get_db)):
    """Extension officer confirms an alert ('Confirmed') or marks as visited."""
    alert = db.query(DiseaseAlert).filter(DiseaseAlert.id == payload.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = payload.status
    if payload.officer_notes:
        alert.officer_notes = payload.officer_notes
    db.commit()
    db.refresh(alert)
    return {"status": "success", "alert_id": alert.id, "new_status": alert.status}


@app.get("/api/officer/queue")
def get_officer_queue(db: Session = Depends(get_db)):
    """Lists low-confidence 'unsure' leaf photos awaiting extension officer review."""
    items = db.query(OfficerQueueItem).order_by(OfficerQueueItem.id.desc()).all()
    results = []
    for it in items:
        v_name = VILLAGES_MAP.get(it.village_id, {}).get("name", it.village_id)
        results.append({
            "id": it.id,
            "image_filename": it.image_filename,
            "crop": it.crop,
            "village_id": it.village_id,
            "village_name": v_name,
            "confidence": round(it.confidence * 100.0, 1),
            "status": it.status,
            "officer_verdict": it.officer_verdict,
            "created_at": it.created_at.isoformat()
        })
    return results


@app.post("/api/officer/queue/resolve")
def resolve_officer_queue(
    item_id: int = Form(...),
    verdict: str = Form(...),
    db: Session = Depends(get_db)
):
    """Officer resolves an unsure queue item."""
    item = db.query(OfficerQueueItem).filter(OfficerQueueItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    item.status = "confirmed"
    item.officer_verdict = verdict
    db.commit()

    # Also log an anonymous report if a disease was diagnosed
    if verdict not in ["Healthy", "Unidentifiable"]:
        file_anonymous_disease_report(
            crop=item.crop,
            disease=verdict,
            village_id=item.village_id,
            confidence=0.98,
            image_filename=item.image_filename,
            db=db
        )

    return {"status": "resolved", "item_id": item.id, "verdict": verdict}


# ============================================================================
# 7. DEMO HELPERS & METADATA
# ============================================================================

@app.post("/api/demo/simulate-outbreak")
def api_simulate_outbreak(db: Session = Depends(get_db)):
    """Simulates an outbreak of 3 tomato late-blight reports within 10 km."""
    return simulate_outbreak_scenario(db)


@app.post("/api/demo/reset")
def api_reset_demo(db: Session = Depends(get_db)):
    """Resets database to fresh initial seeded state."""
    return reset_and_seed_database(db)


@app.get("/api/meta/villages")
def get_villages_meta():
    """Returns list of 5 Pune villages with coordinates."""
    return VILLAGES_LIST


@app.get("/api/meta/config")
def get_crop_soil_meta():
    """Returns FAO-56 crop and soil configuration."""
    return CROP_SOIL_CONFIG


@app.get("/api/meta/translations/{lang}")
def get_translations(lang: str):
    """Returns UI and advice strings for the selected language."""
    return get_localized_strings(lang)


# ============================================================================
# 8. STATIC FRONTEND SERVING
# ============================================================================

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_root():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index_path)
