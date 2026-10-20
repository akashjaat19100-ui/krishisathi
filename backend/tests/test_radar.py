"""
Unit Tests for KrishiSathi Village Disease Radar and Spatial Clustering.
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import DiseaseReport, DiseaseAlert, Farmer
from backend.radar.disease_radar import (
    haversine_distance_km, get_nearby_villages,
    file_anonymous_disease_report, evaluate_radar_outbreak,
    get_active_alerts_for_farmer
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


def test_haversine_distance_calculation():
    # Shivapur to Khed-Shivapur (~4.5 km)
    dist_khed = haversine_distance_km(18.3167, 73.8833, 18.3500, 73.8580)
    assert 4.0 <= dist_khed <= 5.5, f"Expected ~4.5 km, got {dist_khed}"

    # Shivapur to Saswad (~7.2 km)
    dist_saswad = haversine_distance_km(18.3167, 73.8833, 18.3440, 73.9450)
    assert 6.0 <= dist_saswad <= 8.5, f"Expected ~7.2 km, got {dist_saswad}"

    # Shivapur to Shirur (> 65 km away)
    dist_shirur = haversine_distance_km(18.3167, 73.8833, 18.8270, 74.3780)
    assert dist_shirur > 65.0, f"Expected > 65 km, got {dist_shirur}"


def test_radar_outbreak_rule_triggers_on_third_report(db_session):
    today = date.today()

    # Report 1 in Shivapur
    res1 = file_anonymous_disease_report(
        crop="tomato",
        disease="Tomato Late Blight",
        village_id="v_shivapur",
        confidence=0.92,
        image_filename="t1.jpg",
        db=db_session,
        report_date=today - timedelta(days=2)
    )
    assert res1["outbreak_alert_triggered"] is False

    # Report 2 in Khed (4.5 km away)
    res2 = file_anonymous_disease_report(
        crop="tomato",
        disease="Tomato Late Blight",
        village_id="v_khed",
        confidence=0.95,
        image_filename="t2.jpg",
        db=db_session,
        report_date=today - timedelta(days=1)
    )
    assert res2["outbreak_alert_triggered"] is False

    # Report 3 in Saswad (7.2 km away, within 10 km cluster!)
    res3 = file_anonymous_disease_report(
        crop="tomato",
        disease="Tomato Late Blight",
        village_id="v_saswad",
        confidence=0.90,
        image_filename="t3.jpg",
        db=db_session,
        report_date=today
    )
    # The 3-in-7-days within 10km condition is now satisfied!
    assert res3["outbreak_alert_triggered"] is True

    # Verify Alert status in DB
    alert = db_session.query(DiseaseAlert).filter(DiseaseAlert.id == res3["alert_id"]).first()
    assert alert is not None
    assert alert.status == "Reported"
    assert "v_shivapur" in alert.village_ids
    assert "v_khed" in alert.village_ids
    assert "v_saswad" in alert.village_ids


def test_distant_report_does_not_trigger_cluster(db_session):
    today = date.today()

    # 2 reports in Shivapur
    file_anonymous_disease_report("cotton", "Bacterial Blight", "v_shivapur", 0.9, "c1.jpg", db_session, today)
    file_anonymous_disease_report("cotton", "Bacterial Blight", "v_shivapur", 0.9, "c2.jpg", db_session, today)

    # 1 report far away in Shirur (>65 km)
    res = file_anonymous_disease_report("cotton", "Bacterial Blight", "v_shirur", 0.9, "c3.jpg", db_session, today)

    # Shirur is not within 10 km of Shivapur, so cluster count remains 2 (below threshold 3)
    assert res["outbreak_alert_triggered"] is False
