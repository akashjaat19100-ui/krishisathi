"""
Unit Tests for KrishiSathi Tier 0 Irrigation Engine.
Contains 4 Worked Examples with step-by-step mathematical validation for student viva.
"""

import pytest
import math
from datetime import date, timedelta
from backend.engine.hargreaves import (
    calculate_extraterrestrial_radiation,
    calculate_hargreaves_et0
)
from backend.engine.water_balance import (
    get_crop_growth_stage,
    compute_soil_water_limits,
    update_daily_deficit,
    evaluate_irrigation_signal,
    calculate_pumping_requirement,
    calculate_effective_rain,
    calculate_weekly_savings
)


class TestWorkedExample1HargreavesET0:
    """
    WORKED EXAMPLE 1: Extraterrestrial Radiation (Ra) and Hargreaves ET0
    Location: Shivapur, Pune (Latitude: 18.32° N)
    Date: October 20 (Julian Day J = 293)
    Temperature: Tmax = 32.0°C, Tmin = 20.0°C, Tmean = 26.0°C
    """

    def test_ra_and_et0_manual_verification(self):
        lat = 18.32
        j_day = 293
        tmax = 32.0
        tmin = 20.0
        tmean = 26.0

        # Step 1: Solar declination delta
        # delta = 0.409 * sin((2*pi/365)*293 - 1.39)
        # Expected delta is negative in late October (Sun over southern hemisphere)
        phi = math.radians(lat)
        dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * j_day)
        delta = 0.409 * math.sin(((2.0 * math.pi / 365.0) * j_day) - 1.39)
        ws = math.acos(-math.tan(phi) * math.tan(delta))

        ra_mj, ra_mm = calculate_extraterrestrial_radiation(lat, j_day)

        # Ra in tropical latitude in October is typically ~30 - 34 MJ/m2/day
        assert 28.0 <= ra_mj <= 35.0, f"Ra_MJ={ra_mj} outside physical range"
        # In mm/day equivalent (Ra_MJ * 0.408): ~11.5 - 14.0 mm/day
        assert 11.0 <= ra_mm <= 15.0, f"Ra_mm={ra_mm} outside physical range"

        # Step 2: Hargreaves equation
        # ET0 = 0.0023 * (26.0 + 17.8) * sqrt(32.0 - 20.0) * Ra_mm
        # (26.0 + 17.8) = 43.8
        # sqrt(12) = 3.464
        # Constant = 0.0023 * 43.8 * 3.464 = 0.349
        # ET0 = 0.349 * ~13.0 mm/day ~= 4.5 - 5.0 mm/day
        et0 = calculate_hargreaves_et0(tmax, tmin, lat, j_day, tmean)

        assert 4.0 <= et0 <= 5.5, f"ET0={et0} should be realistic tropical evapotranspiration"
        print(f"\n[Worked Example 1] Ra={ra_mj:.2f} MJ/m2/d ({ra_mm:.2f} mm/d), ET0={et0:.2f} mm/day")


class TestWorkedExample2CropGrowthStageAndKc:
    """
    WORKED EXAMPLE 2: Dynamic Growth Stage & Kc Interpolation
    Crop: Tomato
    Configured stages: Initial (25 d, Kc=0.60), Dev (35 d, to Kc=1.15), Mid (45 d, Kc=1.15), Late (30 d, Kc=0.80)
    Test at: Day 45 (20 days into development stage)
    """

    def test_tomato_development_stage(self):
        days_sown = 45
        growth = get_crop_growth_stage("tomato", days_sown)

        assert growth["stage_name"] == "Crop Development"

        # Fractional progress into development: (45 - 25) / 35 = 20/35 = 0.5714
        # Expected Kc = 0.60 + 0.5714 * (1.15 - 0.60) = 0.60 + 0.3143 = 0.914 => 0.91
        expected_kc = 0.91
        assert growth["kc"] == pytest.approx(expected_kc, abs=0.02)

        # Root depth: 0.25m + 0.5714 * (0.70m - 0.25m) = 0.25 + 0.257 = 0.51m
        expected_zr = 0.51
        assert growth["root_depth_m"] == pytest.approx(expected_zr, abs=0.02)
        print(f"\n[Worked Example 2] Tomato Day 45: Stage={growth['stage_name']}, Kc={growth['kc']}, Zr={growth['root_depth_m']}m")


class TestWorkedExample3DeficitBalanceAndRedTrigger:
    """
    WORKED EXAMPLE 3: Daily Root-Zone Water Deficit and RED Signal Trigger
    Soil: Loam (TAW_soil = 150 mm/m)
    Crop: Tomato at Day 45 (Root depth Zr = 0.51 m, p = 0.40)
    TAW = 150 * 0.51 = 76.5 mm
    RAW = 0.40 * 76.5 = 30.6 mm
    Yesterday Deficit Dr_yesterday = 28.0 mm
    Today: Rain = 0 mm, ET0 = 4.8 mm, Kc = 0.91 => ETc = 4.37 mm
    Dr_today = 28.0 - 0 + 4.37 = 32.37 mm
    Trigger Condition: Dr_today (32.37) >= RAW (30.6) => RED SIGNAL (Irrigate Today)
    """

    def test_water_balance_red_trigger(self):
        taw, raw = compute_soil_water_limits(soil_type="loam", root_depth_m=0.51, depletion_p=0.40)
        assert taw == pytest.approx(76.5, abs=0.5)
        assert raw == pytest.approx(30.6, abs=0.5)

        dr_yesterday = 28.0
        et0 = 4.8
        kc = 0.91
        dr_today, etc = update_daily_deficit(
            dr_yesterday=dr_yesterday,
            et0=et0,
            kc=kc,
            rain_mm=0.0,
            irrigation_applied_mm=0.0,
            taw=taw
        )

        assert etc == pytest.approx(4.37, abs=0.05)
        assert dr_today == pytest.approx(32.37, abs=0.1)

        # Check Signal Evaluation
        today = date(2026, 10, 20)
        eval_result = evaluate_irrigation_signal(dr_today, raw, taw, etc, today)
        assert eval_result["signal"] == "RED"
        assert eval_result["urgency"] == "HIGH"

        # Check Pumping Calculation for 1 Acre (4046 m2) with 15 m3/h pump
        pumping = calculate_pumping_requirement(dr_today, plot_area_m2=4046.0, pump_discharge_m3h=15.0)
        # Refill volume: (32.37 / 1000) * 4046 = 130.97 m3
        # Hours = 130.97 / 15 = 8.73 hours
        assert pumping["volume_m3"] == pytest.approx(130.97, abs=1.0)
        assert pumping["pumping_hours"] == pytest.approx(8.73, abs=0.1)
        print(f"\n[Worked Example 3] Dr={dr_today}mm >= RAW={raw}mm -> Signal={eval_result['signal']}, Pumping={pumping['pumping_hours']} hrs")


class TestWorkedExample4RainfallEventAndSavings:
    """
    WORKED EXAMPLE 4: Rainfall Deficit Reduction and Rupee Electricity Savings
    Yesterday Deficit = 25.0 mm.
    Rainfall = 22.0 mm.
    Effective rain = 0.80 * (22.0 - 5.0) = 13.6 mm.
    ETc = 3.6 mm.
    Dr_today = 25.0 - 13.6 + 3.6 = 15.0 mm.
    Since 15.0 mm < 0.70 * 30.6 (21.4 mm), signal transitions to GREEN (Wait).
    """

    def test_rain_reset_and_weekly_savings(self):
        peff = calculate_effective_rain(22.0)
        assert peff == pytest.approx(13.6, abs=0.05)

        taw = 76.5
        raw = 30.6
        dr_today, etc = update_daily_deficit(
            dr_yesterday=25.0,
            et0=4.0,
            kc=0.90,
            rain_mm=22.0,
            irrigation_applied_mm=0.0,
            taw=taw
        )
        assert dr_today == pytest.approx(15.0, abs=0.1)

        today = date(2026, 10, 20)
        sig = evaluate_irrigation_signal(dr_today, raw, taw, etc, today)
        assert sig["signal"] == "GREEN"

        # Savings: Farmer only irrigated 0 times this week vs baseline 5-day cycle (1 irrigation)
        # Avoided 1 irrigation event
        savings = calculate_weekly_savings(
            plot_area_m2=4046.0,
            pump_discharge_m3h=15.0,
            pump_power_kw=3.75,
            electricity_rate=4.5,
            baseline_interval_days=5,
            days_in_period=7,
            actual_irrigations_count=0,
            typical_refill_dr_mm=30.6
        )

        assert savings["irrigations_avoided"] >= 1
        assert savings["pump_hours_saved"] > 0
        assert savings["rupees_saved"] > 0
        print(f"\n[Worked Example 4] Rain reduced deficit to {dr_today}mm -> Signal=GREEN. Savings: ₹{savings['rupees_saved']:.2f}")
