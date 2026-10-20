"""
SQLAlchemy ORM Models for KrishiSathi.
Designed with strict data privacy:
- Farmer personal identifiers (name, phone) are stored locally in Farmer table.
- Disease radar reports (DiseaseReport) store ONLY crop, disease, date, village_id.
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, Float, String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)  # Kept private, never shown on public radar
    village_id = Column(String(50), nullable=False, index=True)
    language = Column(String(10), default="en")  # 'en', 'hi', 'mr'
    crop = Column(String(50), nullable=False)     # 'tomato', 'wheat', 'maize', 'cotton'
    sowing_date = Column(Date, nullable=False)
    soil_type = Column(String(50), nullable=False)  # 'sandy', 'loam', 'clay'
    plot_area_m2 = Column(Float, default=4000.0)    # e.g., 1 acre ~ 4046 m2
    pump_discharge_m3h = Column(Float, default=15.0) # Pump capacity in m3/hr
    electricity_rate = Column(Float, default=4.5)    # Rs per kWh
    pump_power_kw = Column(Float, default=3.75)      # 5 HP pump ~ 3.73 kW
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    state = relationship("IrrigationState", back_populates="farmer", uselist=False, cascade="all, delete-orphan")
    logs = relationship("IrrigationLog", back_populates="farmer", cascade="all, delete-orphan")


class IrrigationState(Base):
    __tablename__ = "irrigation_states"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), unique=True, nullable=False)
    current_dr_mm = Column(Float, default=0.0)      # Current soil moisture depletion / deficit
    last_updated = Column(Date, default=date.today)
    last_irrigation_date = Column(Date, nullable=True)
    sensor_corrected = Column(Boolean, default=False)
    sensor_cluster_id = Column(String(50), nullable=True)

    farmer = relationship("Farmer", back_populates="state")


class IrrigationLog(Base):
    __tablename__ = "irrigation_logs"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    log_date = Column(Date, nullable=False, default=date.today)
    action_type = Column(String(50), nullable=False)  # 'confirmed_irrigation', 'skipped', 'sensor_correction'
    dr_before_mm = Column(Float, default=0.0)
    dr_after_mm = Column(Float, default=0.0)
    hours_applied = Column(Float, default=0.0)
    water_liters_applied = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("Farmer", back_populates="logs")


class SensorCluster(Base):
    __tablename__ = "sensor_clusters"

    id = Column(String(50), primary_key=True, index=True) # e.g. "cluster_shivapur_tomato_loam"
    name = Column(String(100), nullable=False)
    village_id = Column(String(50), nullable=False)
    crop = Column(String(50), nullable=False)
    soil_type = Column(String(50), nullable=False)
    last_reading_time = Column(DateTime, nullable=True)
    last_raw_adc = Column(Integer, nullable=True)
    last_vwc_pct = Column(Float, nullable=True)      # Volumetric Water Content %
    last_deficit_mm = Column(Float, nullable=True)

    readings = relationship("SensorReading", back_populates="cluster", cascade="all, delete-orphan")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(String(50), ForeignKey("sensor_clusters.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    raw_adc = Column(Integer, nullable=False)
    vwc_pct = Column(Float, nullable=False)
    deficit_mm = Column(Float, nullable=False)

    cluster = relationship("SensorCluster", back_populates="readings")


class DiseaseReport(Base):
    """
    Privacy-Preserving Disease Observation Report.
    DOES NOT store farmer name, phone number, or exact geolocation.
    Stores ONLY crop, disease, report_date, village_id.
    """
    __tablename__ = "disease_reports"

    id = Column(Integer, primary_key=True, index=True)
    crop = Column(String(50), nullable=False, index=True)
    disease = Column(String(100), nullable=False, index=True)
    report_date = Column(Date, nullable=False, default=date.today, index=True)
    village_id = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, default=0.90)
    confirmed_by_officer = Column(Boolean, default=False)
    image_filename = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiseaseAlert(Base):
    __tablename__ = "disease_alerts"

    id = Column(Integer, primary_key=True, index=True)
    crop = Column(String(50), nullable=False)
    disease = Column(String(100), nullable=False)
    outbreak_date = Column(Date, nullable=False, default=date.today)
    village_ids = Column(String(255), nullable=False)  # Comma-separated list of affected village IDs
    status = Column(String(20), default="Reported")    # 'Reported' or 'Confirmed'
    report_count = Column(Integer, default=3)
    officer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OfficerQueueItem(Base):
    """Queue for low-confidence leaf photos that require extension officer review."""
    __tablename__ = "officer_queue"

    id = Column(Integer, primary_key=True, index=True)
    image_filename = Column(String(200), nullable=False)
    crop = Column(String(50), nullable=False)
    village_id = Column(String(50), nullable=False)
    confidence = Column(Float, default=0.50)
    officer_verdict = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # 'pending', 'confirmed', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)


class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    tmax = Column(Float, nullable=False)
    tmin = Column(Float, nullable=False)
    tmean = Column(Float, nullable=False)
    precip_mm = Column(Float, default=0.0)
    ra_mm_day = Column(Float, nullable=False)
    source = Column(String(50), default="cached_sample") # 'live_open_meteo' or 'cached_sample'
    fetched_at = Column(DateTime, default=datetime.utcnow)
