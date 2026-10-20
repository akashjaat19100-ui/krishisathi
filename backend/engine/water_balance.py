"""
FAO-56 Daily Root-Zone Water Deficit Engine.

Reference:
- FAO Irrigation and Drainage Paper No. 56, Chapter 6 & 8:
  "Crop Evapotranspiration - Guidelines for Computing Crop Water Requirements".

Mathematical Model:
1. Root Zone Soil Water Balance:
   Dr,t = Dr,t-1 - (P - RO) - I + ETc + DP
   where:
     Dr,t   = Root zone depletion at the end of day t [mm]
     Dr,t-1 = Root zone depletion at the end of yesterday t-1 [mm]
     P      = Total precipitation [mm]
     RO     = Surface runoff [mm]
     (P - RO) = Effective precipitation Peff [mm]
     I      = Net irrigation depth that refilled the root zone [mm]
     ETc    = Crop evapotranspiration = Kc * ET0 [mm/day]
     DP     = Deep percolation below root zone [mm]

2. Total Available Water (TAW):
   TAW = 1000 * (theta_FC - theta_WP) * Zr = TAW_soil * Zr [mm]
   where:
     theta_FC = Soil water content at Field Capacity [m3/m3]
     theta_WP = Soil water content at Wilting Point [m3/m3]
     Zr       = Current effective rooting depth of the crop [m]

3. Readily Available Water (RAW) - The Irrigation Trigger:
   RAW = p * TAW [mm]
   where:
     p = Fraction of TAW that a crop can extract without water stress (FAO-56 Table 22).
     When Dr >= RAW, crop enters moisture stress. The app triggers RED SIGNAL.
"""

import json
import os
import math
from datetime import date, timedelta
from typing import Dict, Any, Tuple


# Load FAO-56 crop and soil configuration
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "crop_soil_config.json"
)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CROP_SOIL_CONFIG = json.load(f)


def calculate_effective_rain(total_rain_mm: float) -> float:
    """
    Computes effective precipitation (water that actually enters root zone).
    FAO empirical model:
    - Light rains (< 5 mm) are lost to canopy interception and fast soil evaporation.
    - Rains > 5 mm: 80% of excess infiltrates into root zone.
    """
    if total_rain_mm <= 5.0:
        return 0.0
    return max(0.0, round(0.80 * (total_rain_mm - 5.0), 2))


def get_crop_growth_stage(crop_name: str, days_since_sowing: int) -> Dict[str, Any]:
    """
    Determines crop growth stage, current Kc coefficient, and root depth (Zr).
    
    Growth Stages (FAO-56):
    1. Initial stage (L_ini): From sowing until 10% ground cover. Kc is constant (Kc_ini).
    2. Crop Development stage (L_dev): From 10% to full ground cover. Kc increases linearly to Kc_mid.
    3. Mid-Season stage (L_mid): Full cover, flowering, fruiting. Kc is maximum (Kc_mid).
    4. Late Season stage (L_late): Maturation, leaf senescence, harvest. Kc declines to Kc_end.
    """
    crop_info = CROP_SOIL_CONFIG["crops"].get(crop_name.lower())
    if not crop_info:
        raise ValueError(f"Unknown crop '{crop_name}'. Available: {list(CROP_SOIL_CONFIG['crops'].keys())}")

    stage_days = crop_info["stage_days"]
    l_ini = stage_days["initial"]
    l_dev = stage_days["development"]
    l_mid = stage_days["mid"]
    l_late = stage_days["late"]

    kc_ini = crop_info["kc"]["initial"]
    kc_mid = crop_info["kc"]["mid"]
    kc_end = crop_info["kc"]["end"]

    z_min = crop_info["root_depth_min_m"]
    z_max = crop_info["root_depth_max_m"]

    d = max(0, days_since_sowing)

    if d < l_ini:
        stage_name = "Initial (Establishment)"
        kc = kc_ini
        zr = z_min
    elif d < (l_ini + l_dev):
        stage_name = "Crop Development"
        frac = (d - l_ini) / max(1, l_dev)
        kc = kc_ini + frac * (kc_mid - kc_ini)
        zr = z_min + frac * (z_max - z_min)
    elif d < (l_ini + l_dev + l_mid):
        stage_name = "Mid-Season (Peak Water Use)"
        kc = kc_mid
        zr = z_max
    else:
        stage_name = "Late Season (Maturation)"
        frac = min(1.0, (d - (l_ini + l_dev + l_mid)) / max(1, l_late))
        kc = kc_mid - frac * (kc_mid - kc_end)
        zr = z_max

    return {
        "stage_name": stage_name,
        "days_since_sowing": d,
        "kc": round(kc, 2),
        "root_depth_m": round(zr, 2),
        "depletion_fraction_p": crop_info["p"],
        "water_saving_tips": crop_info.get("water_saving_tips", [])
    }


def compute_soil_water_limits(soil_type: str, root_depth_m: float, depletion_p: float) -> Tuple[float, float]:
    """
    Computes TAW (Total Available Water) and RAW (Readily Available Water).
    
    Formula:
      TAW [mm] = TAW_soil [mm/m] * Zr [m]
      RAW [mm] = p * TAW [mm]
    """
    soil_info = CROP_SOIL_CONFIG["soils"].get(soil_type.lower())
    if not soil_info:
        raise ValueError(f"Unknown soil '{soil_type}'. Available: {list(CROP_SOIL_CONFIG['soils'].keys())}")

    taw_soil = soil_info["taw_mm_per_m"]
    taw = round(taw_soil * root_depth_m, 2)
    raw = round(depletion_p * taw, 2)
    return taw, raw


def update_daily_deficit(
    dr_yesterday: float,
    et0: float,
    kc: float,
    rain_mm: float,
    irrigation_applied_mm: float,
    taw: float
) -> Tuple[float, float]:
    """
    Computes today's root zone water deficit Dr_today using FAO-56 daily water balance.
    
    Dr_today = Dr_yesterday - Peff - I + Kc * ET0
    
    Boundary conditions:
    1. If Dr < 0: Excess water percolates below root zone (deep drainage / runoff). Dr clamped to 0.
    2. If Dr > TAW: Severe wilting stress. Clamped to TAW.
    
    Returns:
        Tuple of (dr_today_mm, etc_mm_day)
    """
    peff = calculate_effective_rain(rain_mm)
    etc = round(kc * et0, 2)

    dr_raw = dr_yesterday - peff - irrigation_applied_mm + etc

    # Boundary clamping
    dr_today = max(0.0, min(taw, dr_raw))
    return round(dr_today, 2), etc


def evaluate_irrigation_signal(
    dr_today: float,
    raw: float,
    taw: float,
    etc: float,
    current_date: date
) -> Dict[str, Any]:
    """
    Evaluates tiered irrigation advisory signal:
    - RED: Irrigate today (Dr >= RAW)
    - YELLOW: Irrigate in 1 to 2 days (Dr >= 0.70 * RAW or projected to reach RAW within 48h)
    - GREEN: Soil moisture sufficient, wait.
    """
    # Protect against divide-by-zero
    daily_consumption = max(1.0, etc)
    deficit_to_trigger = raw - dr_today

    if dr_today >= raw:
        signal = "RED"
        action_text = "Irrigate today"
        days_until_next = 0
        urgency = "HIGH"
    elif dr_today >= (0.70 * raw) or (deficit_to_trigger <= (daily_consumption * 1.8)):
        signal = "YELLOW"
        action_text = "Irrigate in 1 to 2 days"
        days_until_next = max(1, math.ceil(deficit_to_trigger / daily_consumption))
        urgency = "MEDIUM"
    else:
        signal = "GREEN"
        action_text = "Wait - soil moisture is adequate"
        days_until_next = max(2, math.ceil(deficit_to_trigger / daily_consumption))
        urgency = "LOW"

    next_check_date = current_date + timedelta(days=days_until_next)

    return {
        "signal": signal,
        "action_text": action_text,
        "urgency": urgency,
        "days_until_trigger": days_until_next,
        "next_check_date": next_check_date.isoformat(),
        "dr_mm": dr_today,
        "raw_mm": raw,
        "taw_mm": taw,
        "depletion_pct": round((dr_today / max(1.0, taw)) * 100.0, 1)
    }


def calculate_pumping_requirement(
    dr_mm: float,
    plot_area_m2: float,
    pump_discharge_m3h: float
) -> Dict[str, Any]:
    """
    Calculates precise pumping duration and water volume to refill the root zone deficit.
    
    Formula:
      Volume to refill [m3] = (Dr [mm] / 1000) * Plot Area [m2]
      Pumping Time [hours]  = Volume [m3] / Pump Discharge [m3/hour]
      Water Volume [Liters] = Volume [m3] * 1000
    """
    if dr_mm <= 0.0 or pump_discharge_m3h <= 0.0 or plot_area_m2 <= 0.0:
        return {
            "pumping_hours": 0.0,
            "volume_m3": 0.0,
            "volume_liters": 0
        }

    volume_m3 = (dr_mm / 1000.0) * plot_area_m2
    pumping_hours = round(volume_m3 / pump_discharge_m3h, 2)
    liters = int(round(volume_m3 * 1000.0))

    return {
        "pumping_hours": pumping_hours,
        "volume_m3": round(volume_m3, 2),
        "volume_liters": liters
    }


def calculate_weekly_savings(
    plot_area_m2: float,
    pump_discharge_m3h: float,
    pump_power_kw: float,
    electricity_rate: float,
    baseline_interval_days: int = 5,
    days_in_period: int = 7,
    actual_irrigations_count: int = 1,
    typical_refill_dr_mm: float = 30.0
) -> Dict[str, Any]:
    """
    Computes Rupee and Electricity Savings compared to standard fixed-calendar irrigation.
    
    Traditional Marginal Farmer Practice:
      Irrigate on a rigid calendar (e.g., every 5 days or whenever electricity is available),
      regardless of whether the crop actually needs water.
    
    KrishiSathi Tiered Advisory:
      Advise irrigating ONLY when root zone depletion reaches RAW.
      Every skipped irrigation directly saves electricity units (kWh), groundwater, and money.
    
    Formula:
      Baseline irrigations in period = days_in_period / baseline_interval_days
      Irrigations avoided = max(0, baseline_irrigations - actual_irrigations)
      Hours per irrigation = (typical_refill_dr / 1000 * area) / pump_discharge
      Hours saved = Irrigations avoided * Hours per irrigation
      kWh saved = Hours saved * pump_power_kw
      Rupee saving (Rs) = kWh saved * electricity_rate
    """
    baseline_count = max(1, round(days_in_period / baseline_interval_days))
    avoided_count = max(0, baseline_count - actual_irrigations_count)

    refill_metrics = calculate_pumping_requirement(typical_refill_dr_mm, plot_area_m2, pump_discharge_m3h)
    hours_per_session = refill_metrics["pumping_hours"]

    hours_saved = round(avoided_count * hours_per_session, 1)
    kwh_saved = round(hours_saved * pump_power_kw, 1)
    rupees_saved = round(kwh_saved * electricity_rate, 2)
    liters_saved = avoided_count * refill_metrics["volume_liters"]

    return {
        "baseline_irrigations": baseline_count,
        "actual_irrigations": actual_irrigations_count,
        "irrigations_avoided": avoided_count,
        "pump_hours_saved": hours_saved,
        "kwh_saved": kwh_saved,
        "rupees_saved": rupees_saved,
        "liters_water_saved": liters_saved
    }
