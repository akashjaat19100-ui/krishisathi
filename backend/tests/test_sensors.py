"""
Unit Tests for KrishiSathi Shared Soil Moisture Sensor Node (Tier 1).
"""

import pytest
from datetime import date, timedelta, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Farmer, IrrigationState, SensorCluster, SensorReading
from backend.sensors.sensor_manager import (
    calibrate_adc_to_deficit,
    process_sensor_reading,
    generate_fake_esp32_reading
)

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_adc_calibration_loam_soil():
    # Loam: adc_dry = 3200 (VWC = 13%), adc_wet = 1300 (VWC = 28%), Zr = 0.6 m
    # Case A: Sensor completely dry (raw_adc = 3200)
    dry_res = calibrate_adc_to_deficit(raw_adc=3200, soil_type="loam", root_depth_m=0.6)
    assert dry_res["vwc_pct"] == pytest.approx(13.0, abs=0.5)
    # Deficit = (28 - 13)/100 * 0.6 * 1000 = 0.15 * 600 = 90 mm
    assert dry_res["deficit_mm"] == pytest.approx(90.0, abs=1.0)

    # Case B: Sensor completely saturated / field capacity (raw_adc = 1300)
    wet_res = calibrate_adc_to_deficit(raw_adc=1300, soil_type="loam", root_depth_m=0.6)
    assert wet_res["vwc_pct"] == pytest.approx(28.0, abs=0.5)
    assert wet_res["deficit_mm"] == pytest.approx(0.0, abs=0.1)

    # Case C: Mid-point (raw_adc = 2250)
    mid_res = calibrate_adc_to_deficit(raw_adc=2250, soil_type="loam", root_depth_m=0.6)
    assert mid_res["deficit_mm"] == pytest.approx(45.0, abs=2.0)


def test_sensor_reading_overrides_cluster_farmers(db_session):
    today = date.today()

    # 1. Setup Cluster in Shivapur for Tomato + Loam
    cluster = SensorCluster(
        id="cluster_shivapur_tomato_loam",
        name="Shivapur North Cluster Probe",
        village_id="v_shivapur",
        crop="tomato",
        soil_type="loam"
    )
    db_session.add(cluster)

    # 2. Add two farmers sharing this cluster
    f1 = Farmer(
        name="Farmer A",
        phone="9999900001",
        village_id="v_shivapur",
        language="mr",
        crop="tomato",
        sowing_date=today - timedelta(days=40),
        soil_type="loam",
        plot_area_m2=4000.0,
        pump_discharge_m3h=15.0
    )
    f2 = Farmer(
        name="Farmer B",
        phone="9999900002",
        village_id="v_shivapur",
        language="mr",
        crop="tomato",
        sowing_date=today - timedelta(days=40),
        soil_type="loam",
        plot_area_m2=5000.0,
        pump_discharge_m3h=18.0
    )
    db_session.add_all([f1, f2])
    db_session.commit()

    # Both farmers start with low model Dr = 10.0 mm
    s1 = IrrigationState(farmer_id=f1.id, current_dr_mm=10.0, last_updated=today, sensor_corrected=False)
    s2 = IrrigationState(farmer_id=f2.id, current_dr_mm=10.0, last_updated=today, sensor_corrected=False)
    db_session.add_all([s1, s2])
    db_session.commit()

    # 3. Simulate an ESP32 sensor reading indicating dry soil (e.g. raw_adc = 2900)
    res = process_sensor_reading(
        cluster_id="cluster_shivapur_tomato_loam",
        raw_adc=2900,
        db=db_session,
        margin_threshold_mm=5.0
    )

    # Deficit should have been overridden for both farmers
    assert res["farmers_in_cluster"] == 2
    assert res["farmers_corrected"] == 2

    db_session.refresh(s1)
    db_session.refresh(s2)
    assert s1.sensor_corrected is True
    assert s1.sensor_cluster_id == "cluster_shivapur_tomato_loam"
    assert s1.current_dr_mm > 25.0  # Deficit updated from sensor
    assert s2.sensor_corrected is True
