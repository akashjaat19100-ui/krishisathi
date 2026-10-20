"""
Shared Soil-Moisture Sensor Node Manager (Tier 1).

Physical Concept:
Single-farmer telemetry (individual capacitive soil moisture probes per field)
is economically prohibitive for smallholders owning 0.5 - 2 acres.
Tier 1 introduces "Community Cluster Probes":
One shared solar-powered ESP32 sensor installed in a representative pilot field
monitors an entire micro-cluster of farmers sharing the same village, crop, and soil type.

Calibration:
Raw 12-bit ADC (e.g. capacitive soil probe 0-4095):
- Dry soil: High ADC value (e.g. ~3200) -> Wilting Point (theta_WP)
- Wet saturated soil: Low ADC value (e.g. ~1300) -> Field Capacity (theta_FC)

Sensor Deficit:
Dr_sensor = (theta_FC - theta_VWC) * Zr * 1000 [mm]

Cluster Correction:
If |Dr_sensor - Dr_model| > margin (default 5.0 mm):
  The physical sensor ground truth overrides the meteorological model Dr.
  A badge "Corrected by sensor" is attached to the farmer advisory.
"""

from datetime import datetime, date
import random
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.models import SensorCluster, SensorReading, Farmer, IrrigationState, IrrigationLog
from backend.engine.water_balance import CROP_SOIL_CONFIG, get_crop_growth_stage


def calibrate_adc_to_deficit(
    raw_adc: int,
    soil_type: str,
    root_depth_m: float
) -> Dict[str, float]:
    """
    Calibrates raw sensor ADC counts to Volumetric Water Content % and millimeter deficit.
    """
    soil_key = soil_type.lower()
    soil_cfg = CROP_SOIL_CONFIG["soils"].get(soil_key, CROP_SOIL_CONFIG["soils"]["loam"])

    adc_dry = float(soil_cfg.get("adc_dry", 3200))
    adc_wet = float(soil_cfg.get("adc_wet", 1300))
    fc_pct = float(soil_cfg.get("field_capacity_pct", 28.0))
    wp_pct = float(soil_cfg.get("wilting_point_pct", 13.0))

    # Calculate wetness fraction (0.0 = completely dry at wilting point, 1.0 = at field capacity)
    if adc_dry == adc_wet:
        fraction_wet = 0.5
    else:
        fraction_wet = (adc_dry - raw_adc) / (adc_dry - adc_wet)
        fraction_wet = max(0.0, min(1.0, fraction_wet))

    # Current Volumetric Water Content (VWC %)
    current_vwc_pct = wp_pct + (fraction_wet * (fc_pct - wp_pct))

    # Soil moisture deficit below Field Capacity [mm]
    # Dr = (FC - VWC) / 100 * Root Depth (m) * 1000 mm/m
    vwc_deficit_fraction = max(0.0, (fc_pct - current_vwc_pct) / 100.0)
    deficit_mm = round(vwc_deficit_fraction * root_depth_m * 1000.0, 2)

    return {
        "raw_adc": raw_adc,
        "fraction_wet": round(fraction_wet, 3),
        "vwc_pct": round(current_vwc_pct, 1),
        "deficit_mm": deficit_mm
    }


def process_sensor_reading(
    cluster_id: str,
    raw_adc: int,
    db: Session,
    margin_threshold_mm: float = 5.0
) -> Dict[str, Any]:
    """
    Ingests an incoming sensor reading (from ESP32 or simulation),
    calibrates to deficit, and synchronizes across all farmers in that cluster.
    """
    cluster = db.query(SensorCluster).filter(SensorCluster.id == cluster_id).first()
    if not cluster:
        raise ValueError(f"Sensor cluster '{cluster_id}' not found.")

    # Approximate root depth from crop
    crop_info = CROP_SOIL_CONFIG["crops"].get(cluster.crop.lower(), {})
    avg_root_depth = crop_info.get("root_depth_max_m", 0.7)

    calib = calibrate_adc_to_deficit(raw_adc, cluster.soil_type, avg_root_depth)
    sensor_deficit_mm = calib["deficit_mm"]

    # Save reading to time-series history
    now = datetime.utcnow()
    reading = SensorReading(
        cluster_id=cluster.id,
        timestamp=now,
        raw_adc=raw_adc,
        vwc_pct=calib["vwc_pct"],
        deficit_mm=sensor_deficit_mm
    )
    db.add(reading)

    # Update cluster head state
    cluster.last_reading_time = now
    cluster.last_raw_adc = raw_adc
    cluster.last_vwc_pct = calib["vwc_pct"]
    cluster.last_deficit_mm = sensor_deficit_mm

    # Find all farmers in this cluster (same village, crop, soil)
    cluster_farmers = db.query(Farmer).filter(
        Farmer.village_id == cluster.village_id,
        Farmer.crop == cluster.crop,
        Farmer.soil_type == cluster.soil_type
    ).all()

    corrected_farmers = []
    for farmer in cluster_farmers:
        # Calculate farmer-specific root depth based on their individual sowing date
        days_sown = (date.today() - farmer.sowing_date).days
        growth = get_crop_growth_stage(farmer.crop, days_sown)
        zr = growth["root_depth_m"]

        f_calib = calibrate_adc_to_deficit(raw_adc, farmer.soil_type, zr)
        target_dr = f_calib["deficit_mm"]

        state = farmer.state
        if not state:
            state = IrrigationState(
                farmer_id=farmer.id,
                current_dr_mm=target_dr,
                last_updated=date.today(),
                sensor_corrected=True,
                sensor_cluster_id=cluster.id
            )
            db.add(state)
            corrected_farmers.append(farmer.id)
        else:
            diff = abs(state.current_dr_mm - target_dr)
            if diff >= margin_threshold_mm:
                old_dr = state.current_dr_mm
                state.current_dr_mm = target_dr
                state.sensor_corrected = True
                state.sensor_cluster_id = cluster.id
                state.last_updated = date.today()

                # Log sensor adjustment
                log_entry = IrrigationLog(
                    farmer_id=farmer.id,
                    log_date=date.today(),
                    action_type="sensor_correction",
                    dr_before_mm=old_dr,
                    dr_after_mm=target_dr,
                    hours_applied=0.0,
                    water_liters_applied=0.0
                )
                db.add(log_entry)
                corrected_farmers.append(farmer.id)

    db.commit()

    return {
        "cluster_id": cluster.id,
        "raw_adc": raw_adc,
        "vwc_pct": calib["vwc_pct"],
        "sensor_deficit_mm": sensor_deficit_mm,
        "farmers_in_cluster": len(cluster_farmers),
        "farmers_corrected": len(corrected_farmers),
        "corrected_farmer_ids": corrected_farmers,
        "timestamp": now.isoformat()
    }


def generate_fake_esp32_reading(cluster: SensorCluster) -> int:
    """
    Simulates a plausible ESP32 12-bit ADC moisture sensor reading.
    ADC values: ~1300 (saturated) to ~3200 (dry soil).
    """
    # Pick a random plausible reading around moderate-to-dry soil
    return random.randint(2200, 3100)
