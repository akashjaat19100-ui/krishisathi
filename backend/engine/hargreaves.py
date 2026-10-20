"""
Hargreaves-Samani Evapotranspiration (ET0) Engine.

Reference:
- FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998), Chapter 3 & 4.
- Hargreaves, G.H. and Samani, Z.A. (1985). "Reference crop evapotranspiration from temperature".

Why Hargreaves?
Standard Penman-Monteith requires solar radiation, wind speed, relative humidity, and air temperature.
Marginal farmers and rural weather stations rarely have wind or solar sensors.
The Hargreaves method requires ONLY:
  1. Latitude (geographic position)
  2. Day of the year (Julian Day J)
  3. Daily maximum and minimum temperature (Tmax, Tmin)
making it ideal for affordable, offline, or low-bandwidth agricultural advisory.
"""

import math
from datetime import date
from typing import Tuple


def calculate_extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> Tuple[float, float]:
    """
    Computes extraterrestrial radiation (Ra) from latitude and day of year.
    
    Equations from FAO-56, Chapter 3:
    - Solar declination: delta = 0.409 * sin((2*pi/365)*J - 1.39)  [Eq. 24]
    - Inverse relative Earth-Sun distance: dr = 1 + 0.033 * cos((2*pi/365)*J)  [Eq. 23]
    - Sunset hour angle: ws = arccos(-tan(phi) * tan(delta))  [Eq. 25]
    - Solar constant: Gsc = 0.0820 MJ m^-2 min^-1  [Eq. 28]
    - Ra (MJ m^-2 day^-1):
        Ra = (24 * 60 / pi) * Gsc * dr * [ws * sin(phi)*sin(delta) + cos(phi)*cos(delta)*sin(ws)]  [Eq. 21]
    - Conversion to equivalent water depth (mm/day):
        Ra_mm = Ra_MJ * 0.408  (since latent heat of vaporization lambda ~ 2.45 MJ/kg)
    
    Args:
        latitude_deg: Latitude in decimal degrees (positive for North, negative for South).
                      Pune region is approx 18.3° to 18.8° N.
        day_of_year: Julian day J (1 to 365/366).
    
    Returns:
        Tuple of (Ra_MJ_m2_day, Ra_mm_day)
    """
    # 1. Convert latitude to radians (phi)
    phi = math.radians(latitude_deg)

    # 2. Inverse relative distance Earth-Sun (dr)
    dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year)

    # 3. Solar declination (delta, radians)
    delta = 0.409 * math.sin(((2.0 * math.pi / 365.0) * day_of_year) - 1.39)

    # 4. Sunset hour angle (ws, radians)
    # Clamp argument to [-1.0, 1.0] to prevent math domain error in polar regions
    tan_product = -math.tan(phi) * math.tan(delta)
    tan_product_clamped = max(-1.0, min(1.0, tan_product))
    ws = math.acos(tan_product_clamped)

    # 5. Solar constant Gsc in MJ m^-2 min^-1
    g_sc = 0.0820

    # 6. Extraterrestrial radiation Ra in MJ m^-2 day^-1
    term1 = ws * math.sin(phi) * math.sin(delta)
    term2 = math.cos(phi) * math.cos(delta) * math.sin(ws)
    ra_mj = ((24.0 * 60.0) / math.pi) * g_sc * dr * (term1 + term2)

    # 7. Convert Ra from MJ m^-2 day^-1 to equivalent evaporation depth in mm day^-1
    # 1 mm depth of water across 1 m^2 requires ~2.45 MJ to vaporize.
    # Therefore, 1 / 2.45 = 0.408
    ra_mm_day = ra_mj * 0.408

    return ra_mj, ra_mm_day


def calculate_hargreaves_et0(
    tmax: float,
    tmin: float,
    latitude_deg: float,
    day_of_year: int,
    tmean: float = None
) -> float:
    """
    Calculates reference crop evapotranspiration (ET0) using the Hargreaves-Samani equation.

    Formula (FAO-56 Eq. 52):
        ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra
    
    where:
        ET0   = Reference evapotranspiration [mm/day]
        Tmean = Daily mean temperature [°C] (computed as (Tmax + Tmin)/2 if not provided)
        Tmax  = Daily maximum temperature [°C]
        Tmin  = Daily minimum temperature [°C]
        Ra    = Extraterrestrial radiation expressed in equivalent water depth [mm/day]

    Args:
        tmax: Maximum daily temperature in °C
        tmin: Minimum daily temperature in °C
        latitude_deg: Latitude of the farm (e.g., 18.32 for Shivapur, Pune)
        day_of_year: Day of year (1-365)
        tmean: Optional mean daily temperature in °C. Defaults to (tmax + tmin) / 2.

    Returns:
        ET0 in mm/day (clamped to >= 0.0)
    """
    if tmax < tmin:
        tmax, tmin = tmin, tmax

    if tmean is None:
        tmean = (tmax + tmin) / 2.0

    # Compute Ra in mm/day equivalent
    _, ra_mm_day = calculate_extraterrestrial_radiation(latitude_deg, day_of_year)

    # Hargreaves formula:
    # 0.0023 is the empirical calibration constant
    # (Tmean + 17.8) approximates temperature effect on vapor pressure deficit
    # sqrt(Tmax - Tmin) proxies for daily solar radiation and cloudiness
    temp_range = max(0.0, tmax - tmin)
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(temp_range) * ra_mm_day

    return max(0.0, round(et0, 2))


def get_day_of_year(target_date: date) -> int:
    """Returns day of year (1-366) from date object."""
    return target_date.timetuple().tm_yday
