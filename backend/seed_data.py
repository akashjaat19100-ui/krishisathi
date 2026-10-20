"""
Seed Data and Outbreak Simulation Script for KrishiSathi Demo.

Contains:
1. reset_and_seed_database(db): Initializes 8 farmers across 5 Pune villages,
   2 community sensor clusters, and 14 days of cached weather.
2. simulate_outbreak_scenario(db): Automatically logs 3 tomato late-blight reports
   in neighboring villages (Shivapur, Khed, Saswad < 10 km), triggering the Disease Radar!
"""

import os
import csv
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session

from backend.database import engine, Base
from backend.models import (
    Farmer, IrrigationState, IrrigationLog,
    SensorCluster, SensorReading,
    DiseaseReport, DiseaseAlert, OfficerQueueItem, WeatherCache
)
from backend.radar.disease_radar import evaluate_radar_outbreak, haversine_distance_km
from backend.sensors.sensor_manager import calibrate_adc_to_deficit
from backend.engine.hargreaves import calculate_hargreaves_et0, get_day_of_year


SAMPLE_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "weather_sample.csv"
)


def seed_weather_data(db: Session):
    """Loads 14-day weather CSV into WeatherCache table."""
    if not os.path.exists(SAMPLE_CSV_PATH):
        return

    db.query(WeatherCache).delete()
    with open(SAMPLE_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec_date = date.fromisoformat(row["date"].strip())
            tmax = float(row["tmax"])
            tmin = float(row["tmin"])
            tmean = float(row.get("tmean", (tmax + tmin) / 2.0))
            precip = float(row.get("precip_mm", 0.0))
            j_day = get_day_of_year(rec_date)
            et0 = calculate_hargreaves_et0(tmax, tmin, 18.32, j_day, tmean)

            w = WeatherCache(
                date=rec_date,
                tmax=tmax,
                tmin=tmin,
                tmean=tmean,
                precip_mm=precip,
                ra_mm_day=et0,
                source="cached_sample",
                fetched_at=datetime.utcnow()
            )
            db.add(w)
    db.commit()


def reset_and_seed_database(db: Session):
    """
    Completely resets the database and seeds 8 realistic farmers across 5 villages,
    2 community sensor clusters, and 14 days of weather data.
    """
    # Drop and recreate all tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    today = date.today()

    # 1. Seed Weather
    seed_weather_data(db)

    # 2. Seed Sensor Clusters (Tier 1)
    cluster1 = SensorCluster(
        id="cluster_shivapur_tomato_loam",
        name="Shivapur North Cluster Probe #1",
        village_id="v_shivapur",
        crop="tomato",
        soil_type="loam",
        last_reading_time=datetime.utcnow(),
        last_raw_adc=2950,
        last_vwc_pct=15.5,
        last_deficit_mm=32.0
    )
    cluster2 = SensorCluster(
        id="cluster_khed_maize_clay",
        name="Khed-Shivapur Valley Probe #2",
        village_id="v_khed",
        crop="maize",
        soil_type="clay",
        last_reading_time=datetime.utcnow(),
        last_raw_adc=2600,
        last_vwc_pct=25.0,
        last_deficit_mm=22.5
    )
    db.add_all([cluster1, cluster2])
    db.commit()

    # Add initial sensor reading
    read1 = SensorReading(
        cluster_id=cluster1.id,
        timestamp=datetime.utcnow(),
        raw_adc=2950,
        vwc_pct=15.5,
        deficit_mm=32.0
    )
    read2 = SensorReading(
        cluster_id=cluster2.id,
        timestamp=datetime.utcnow(),
        raw_adc=2600,
        vwc_pct=25.0,
        deficit_mm=22.5
    )
    db.add_all([read1, read2])
    db.commit()

    # 3. Seed 8 Farmers across 5 villages
    farmers_data = [
        # Farmer 1: Tomato in Shivapur, Loam soil. High deficit -> RED signal ready
        {
            "id": 1,
            "name": "Ramesh Shinde",
            "phone": "9822011111",
            "village_id": "v_shivapur",
            "language": "mr",
            "crop": "tomato",
            "sowing_date": today - timedelta(days=45), # Mid-season, peak Kc
            "soil_type": "loam",
            "plot_area_m2": 4046.0,  # 1 Acre
            "pump_discharge_m3h": 15.0,
            "electricity_rate": 4.5,
            "pump_power_kw": 3.75,  # 5 HP
            "init_dr": 34.5,         # Above RAW trigger (RED)
            "sensor_corrected": True,
            "sensor_cluster_id": "cluster_shivapur_tomato_loam"
        },
        # Farmer 2: Prakash Jadhav: Shivapur, Tomato, Loam
        {
            "id": 2,
            "name": "Prakash Jadhav",
            "phone": "9822022222",
            "village_id": "v_shivapur",
            "language": "mr",
            "crop": "tomato",
            "sowing_date": today - timedelta(days=40),
            "soil_type": "loam",
            "plot_area_m2": 5000.0,
            "pump_discharge_m3h": 18.0,
            "electricity_rate": 4.5,
            "pump_power_kw": 5.0,
            "init_dr": 28.0,        # YELLOW signal
            "sensor_corrected": True,
            "sensor_cluster_id": "cluster_shivapur_tomato_loam"
        },
        # Farmer 3: Dnyaneshwar Pawar: Khed-Shivapur, Tomato, Loam
        {
            "id": 3,
            "name": "Dnyaneshwar Pawar",
            "phone": "9822033333",
            "village_id": "v_khed",
            "language": "mr",
            "crop": "tomato",
            "sowing_date": today - timedelta(days=38),
            "soil_type": "loam",
            "plot_area_m2": 3500.0,
            "pump_discharge_m3h": 12.0,
            "electricity_rate": 4.0,
            "pump_power_kw": 3.75,
            "init_dr": 14.0,        # GREEN signal
            "sensor_corrected": False,
            "sensor_cluster_id": None
        },
        # Farmer 4: Suresh Gaikwad: Saswad, Tomato, Loam
        {
            "id": 4,
            "name": "Suresh Gaikwad",
            "phone": "9822044444",
            "village_id": "v_saswad",
            "language": "mr",
            "crop": "tomato",
            "sowing_date": today - timedelta(days=30),
            "soil_type": "loam",
            "plot_area_m2": 6000.0,
            "pump_discharge_m3h": 20.0,
            "electricity_rate": 4.8,
            "pump_power_kw": 5.5,
            "init_dr": 26.5,        # YELLOW signal
            "sensor_corrected": False,
            "sensor_cluster_id": None
        },
        # Farmer 5: Amit Patil: Khed-Shivapur, Maize, Clay (Cluster 2)
        {
            "id": 5,
            "name": "Amit Patil",
            "phone": "9822055555",
            "village_id": "v_khed",
            "language": "hi",
            "crop": "maize",
            "sowing_date": today - timedelta(days=25),
            "soil_type": "clay",
            "plot_area_m2": 4500.0,
            "pump_discharge_m3h": 15.0,
            "electricity_rate": 4.2,
            "pump_power_kw": 3.75,
            "init_dr": 22.5,        # In sync with cluster 2
            "sensor_corrected": True,
            "sensor_cluster_id": "cluster_khed_maize_clay"
        },
        # Farmer 6: Sunita Thorat: Shivapur, Wheat, Sandy soil
        {
            "id": 6,
            "name": "Sunita Thorat",
            "phone": "9822066666",
            "village_id": "v_shivapur",
            "language": "mr",
            "crop": "wheat",
            "sowing_date": today - timedelta(days=21), # Crown Root Initiation stage!
            "soil_type": "sandy",
            "plot_area_m2": 3000.0,
            "pump_discharge_m3h": 10.0,
            "electricity_rate": 4.5,
            "pump_power_kw": 2.2,
            "init_dr": 18.0,        # RED for sandy (low TAW)
            "sensor_corrected": False,
            "sensor_cluster_id": None
        },
        # Farmer 7: Vilas More: Shirur (far away, >65 km), Cotton, Clay
        {
            "id": 7,
            "name": "Vilas More",
            "phone": "9822077777",
            "village_id": "v_shirur",
            "language": "mr",
            "crop": "cotton",
            "sowing_date": today - timedelta(days=50),
            "soil_type": "clay",
            "plot_area_m2": 8000.0,
            "pump_discharge_m3h": 22.0,
            "electricity_rate": 4.5,
            "pump_power_kw": 7.5,
            "init_dr": 35.0,
            "sensor_corrected": False,
            "sensor_cluster_id": None
        },
        # Farmer 8: Anand Deshmukh: Baramati (far away, >70 km), Wheat, Loam
        {
            "id": 8,
            "name": "Anand Deshmukh",
            "phone": "9822088888",
            "village_id": "v_baramati",
            "language": "en",
            "crop": "wheat",
            "sowing_date": today - timedelta(days=15),
            "soil_type": "loam",
            "plot_area_m2": 4000.0,
            "pump_discharge_m3h": 14.0,
            "electricity_rate": 4.0,
            "pump_power_kw": 3.75,
            "init_dr": 8.0,         # GREEN
            "sensor_corrected": False,
            "sensor_cluster_id": None
        }
    ]

    for item in farmers_data:
        f = Farmer(
            id=item["id"],
            name=item["name"],
            phone=item["phone"],
            village_id=item["village_id"],
            language=item["language"],
            crop=item["crop"],
            sowing_date=item["sowing_date"],
            soil_type=item["soil_type"],
            plot_area_m2=item["plot_area_m2"],
            pump_discharge_m3h=item["pump_discharge_m3h"],
            electricity_rate=item["electricity_rate"],
            pump_power_kw=item["pump_power_kw"],
            created_at=datetime.utcnow()
        )
        db.add(f)
        db.flush()

        # Create initial state
        state = IrrigationState(
            farmer_id=f.id,
            current_dr_mm=item["init_dr"],
            last_updated=today,
            last_irrigation_date=today - timedelta(days=6),
            sensor_corrected=item["sensor_corrected"],
            sensor_cluster_id=item["sensor_cluster_id"]
        )
        db.add(state)

        # Log a past irrigation event
        log = IrrigationLog(
            farmer_id=f.id,
            log_date=today - timedelta(days=6),
            action_type="confirmed_irrigation",
            dr_before_mm=32.0,
            dr_after_mm=0.0,
            hours_applied=2.5,
            water_liters_applied=37500.0,
            created_at=datetime.utcnow() - timedelta(days=6)
        )
        db.add(log)

    # 4. Seed an Officer Review Queue Item (for demoing the "Unsure" queue)
    unsure_item = OfficerQueueItem(
        image_filename="sample_blurry_leaf.jpg",
        crop="tomato",
        village_id="v_khed",
        confidence=0.48,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(unsure_item)

    db.commit()
    return {"status": "success", "farmers_seeded": len(farmers_data), "clusters_seeded": 2}


def simulate_outbreak_scenario(db: Session):
    """
    Simulates a live community outbreak scenario:
    Adds 3 independent anonymous Tomato Late Blight reports:
      - 1 in Shivapur
      - 1 in Khed-Shivapur (4.5 km away)
      - 1 in Saswad (7.2 km away)
    All 3 are within the 10 km spatial clustering threshold and logged within 48 hours!
    Triggers the Village Disease Radar outbreak alert automatically!
    """
    today = date.today()

    # Clear prior alerts for tomato to showcase live triggering
    db.query(DiseaseAlert).filter(DiseaseAlert.crop == "tomato").delete()
    db.query(DiseaseReport).filter(DiseaseReport.crop == "tomato").delete()
    db.commit()

    # 3 independent reports in nearby villages (strictly no farmer PII)
    reports = [
        DiseaseReport(
            crop="tomato",
            disease="Tomato Late Blight (Phytophthora infestans)",
            village_id="v_shivapur",
            report_date=today - timedelta(days=1),
            confidence=0.94,
            image_filename="tomato_late_blight_field1.jpg",
            confirmed_by_officer=False,
            created_at=datetime.utcnow() - timedelta(hours=28)
        ),
        DiseaseReport(
            crop="tomato",
            disease="Tomato Late Blight (Phytophthora infestans)",
            village_id="v_khed",
            report_date=today,
            confidence=0.91,
            image_filename="tomato_late_blight_field2.jpg",
            confirmed_by_officer=False,
            created_at=datetime.utcnow() - timedelta(hours=14)
        ),
        DiseaseReport(
            crop="tomato",
            disease="Tomato Late Blight (Phytophthora infestans)",
            village_id="v_saswad",
            report_date=today,
            confidence=0.93,
            image_filename="tomato_late_blight_field3.jpg",
            confirmed_by_officer=False,
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
    ]

    for r in reports:
        db.add(r)
    db.commit()

    # Trigger radar cluster detection
    alert = evaluate_radar_outbreak("tomato", "Tomato Late Blight (Phytophthora infestans)", db)

    return {
        "status": "outbreak_simulated",
        "reports_added": len(reports),
        "alert_triggered": alert is not None,
        "alert_id": alert.id if alert else None,
        "affected_villages": alert.village_ids if alert else None,
        "advisory_rule": ">= 3 reports within 10 km within 7 days",
        "farmer_action": "Inspect your field today (never spray blindly)"
    }
