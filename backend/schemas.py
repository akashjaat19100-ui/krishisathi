"""
Pydantic Schemas for Request Validation and Response Serialization.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FarmerCreate(BaseModel):
    name: str = Field(..., example="Ramesh Shinde")
    phone: str = Field(..., example="9822012345")
    village_id: str = Field(..., example="v_shivapur")
    language: str = Field(default="mr", example="mr")  # 'en', 'hi', 'mr'
    crop: str = Field(..., example="tomato")
    sowing_date: date = Field(..., example="2026-09-01")
    soil_type: str = Field(..., example="loam")
    plot_area_m2: float = Field(default=4000.0, example=4000.0)
    pump_discharge_m3h: float = Field(default=15.0, example=15.0)
    electricity_rate: float = Field(default=4.5, example=4.5)
    pump_power_kw: float = Field(default=3.75, example=3.75)


class FarmerResponse(BaseModel):
    id: int
    name: str
    village_id: str
    village_name: Optional[str] = None
    language: str
    crop: str
    sowing_date: date
    soil_type: str
    plot_area_m2: float
    pump_discharge_m3h: float
    electricity_rate: float
    pump_power_kw: float
    created_at: datetime

    class Config:
        from_attributes = True


class IrrigationAdvisoryResponse(BaseModel):
    farmer_id: int
    farmer_name: str
    language: str
    crop: str
    soil_type: str
    village_id: str
    village_name: str
    signal: str  # RED, YELLOW, GREEN
    action_text: str
    urgency: str
    dr_mm: float
    raw_mm: float
    taw_mm: float
    depletion_pct: float
    pumping_hours: float
    volume_liters: int
    next_check_date: str
    days_until_trigger: int
    weather: Dict[str, Any]
    sensor_corrected: bool
    sensor_cluster_id: Optional[str] = None
    sensor_badge_text: str
    water_saving_tip: str
    weekly_savings: Dict[str, Any]
    active_alerts: List[Dict[str, Any]]
    spoken_message: str
    sms_bubble_message: str


class IrrigationConfirmRequest(BaseModel):
    farmer_id: int
    hours_applied: Optional[float] = None


class SensorReadingCreate(BaseModel):
    cluster_id: str
    raw_adc: int


class DiseaseReportCreate(BaseModel):
    crop: str
    disease: str
    village_id: str
    confidence: float = 0.90
    image_filename: Optional[str] = "leaf.jpg"


class DiseaseAlertResponse(BaseModel):
    id: int
    crop: str
    disease: str
    outbreak_date: date
    village_ids: str
    village_names: List[str]
    status: str
    report_count: int
    officer_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OfficerAlertUpdateRequest(BaseModel):
    alert_id: int
    status: str  # 'Confirmed' or 'Reported'
    officer_notes: Optional[str] = None
