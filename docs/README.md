# 🌱 KrishiSathi (कृषि साथी / कृषी साथी)
### Tiered Irrigation & Crop-Disease Advisory Service for Small and Marginal Farmers in India

KrishiSathi is a working, demo-ready prototype web application designed for small and marginal farmers (owning 0.5 – 2 acres) in India. It bridges the digital divide through a tiered architecture that starts with zero-sensor feature phones and scales up to shared IoT sensors and spatial disease radar.

---

## 🏗️ The 3 Tiers of KrishiSathi

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TIER 2: ANDROID & RADAR                         │
│  - Leaf Photo Disease Classifier (MobileNetV2 / Heuristic)             │
│  - Village Disease Radar (Privacy-Preserving Spatial Outbreak Alerts)   │
│  - Weekly Rupee & Groundwater Savings Tracker                          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                    TIER 1: SHARED COMMUNITY SENSORS                    │
│  - Shared Solar ESP32 Capacitive Probes for Micro-Clusters             │
│  - Telemetry Ingestion (/sensor/readings) & Calibration                │
│  - Automatic Model Deficit (Dr) Correction for Cluster Farmers         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                    TIER 0: UNIVERSAL ZERO-SENSOR PHONE                 │
│  - Works on ANY phone via Toll-Free Missed Call & Spoken Audio / SMS   │
│  - Hargreaves-Samani ET0 + FAO-56 Daily Root-Zone Water Balance        │
│  - Clear Traffic Signal: RED (Irrigate Today), YELLOW (1-2 Days), GREEN│
│  - Refills Deficit Only: Exact Pumping Hours & Water Liters            │
└────────────────────────────────────────────────────────────────────────┘
```

- **Tier 0 (Any Basic Phone)**: Daily "Irrigate or Wait" advice with **NO sensors required**. Uses temperature, latitude, crop stage, and soil properties.
- **Tier 1 (Community Sensor)**: An optional shared soil-moisture sensor placed in a representative pilot field calibrates and overrides the model estimate for all nearby farmers with the same crop and soil type.
- **Tier 2 (Smartphone & Community Radar)**: Leaf photo disease scanner, the **Village Disease Radar** that detects pathogen outbreaks within 10 km, and weekly rupee savings tracking.

> **Core Philosophy**: The farmer always decides; KrishiSathi is advisory only.

---

## ⚡ Quick Start (Run Locally in One Command)

### Prerequisites
- Python 3.9+ (Python 3.11 recommended)
- A modern web browser (Chrome, Edge, Firefox, Safari)

### Run the App
```bash
# Clone or navigate to the repository
cd krishisathi

# Launch with the single-command runner (auto-seeds database on first launch)
./run.sh
# or:
python run.py
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

To run the unit test suite:
```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -v -s
```

---

## 📁 Repository Structure

```
krishisathi/
├── run.py                     # Single-command launcher (seeds db if needed, starts uvicorn)
├── run.sh                     # Bash wrapper launcher
├── requirements.txt           # Python dependencies (FastAPI, SQLAlchemy, Pytest, etc.)
├── backend/
│   ├── main.py                # FastAPI app, REST APIs, static file routing
│   ├── database.py            # SQLite database engine and session
│   ├── models.py              # Privacy-preserving SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic validation schemas
│   ├── seed_data.py           # Seeds 8 farmers, 5 Pune villages, 2 clusters, 14-day weather
│   ├── engine/
│   │   ├── hargreaves.py      # Ra and Hargreaves ET0 mathematical engine
│   │   ├── water_balance.py   # FAO-56 stage Kc, TAW, RAW, Dr deficit, and pumping hours
│   │   └── weather_service.py # Open-Meteo live fetch with offline sample CSV fallback
│   ├── sensors/
│   │   └── sensor_manager.py  # Community cluster calibration and Dr override logic
│   ├── radar/
│   │   └── disease_radar.py   # Privacy-preserving Haversine spatial clustering (<10 km)
│   ├── classifier/
│   │   └── leaf_classifier.py # Mock heuristic + TFLite fallback + Unsure queue routing
│   ├── i18n/
│   │   ├── en.json            # English translations
│   │   ├── hi.json            # Hindi translations (हिंदी)
│   │   └── mr.json            # Marathi translations (मराठी)
│   └── tests/
│       ├── test_engine.py     # 4 worked unit tests for ET0, Kc, Dr, and pump duration
│       ├── test_radar.py      # Spatial distance and 3-report outbreak trigger tests
│       └── test_sensors.py    # Soil moisture ADC calibration & cluster override tests
├── data/
│   ├── crop_soil_config.json  # FAO-56 crop stage days, Kc, root depth, TAW, and tips
│   ├── weather_sample.csv     # 14 days of realistic calibrated Pune weather data
│   └── villages.json          # 5 Pune villages with GPS coordinates
├── ml/
│   ├── train_leaf_model.py    # MobileNetV2 transfer learning training & TFLite exporter
│   └── README.md              # Instructions for downloading PlantVillage dataset
├── docs/
│   ├── README.md              # This document
│   └── demo_script.md         # Step-by-step viva presentation script
└── frontend/
    ├── index.html             # Responsive mobile-first single-page interface
    ├── css/
    │   └── styles.css         # High-contrast, accessible UI with large buttons and icons
    ├── js/
    │   └── app.js             # State controller, SpeechSynthesis voice, and Leaflet map
    └── assets/
        ├── leaflet.css        # Bundled offline Leaflet map stylesheet
        └── leaflet.js         # Bundled offline Leaflet map script
```

---

## 🎓 Viva & Technical Explanation Notes

### 1. Why Hargreaves-Samani instead of Penman-Monteith?
The standard FAO-56 Penman-Monteith equation is the most accurate, but it requires solar radiation sensors, anemometers for wind speed, psychrometers for vapor pressure, and air temperature. Smallholder farmers and rural sub-districts rarely have automated weather stations with these sensors.

The **Hargreaves-Samani (1985)** equation requires ONLY:
1. Latitude of the farm ($\phi$)
2. Day of the year ($J$) to calculate extraterrestrial radiation ($R_a$)
3. Daily maximum and minimum temperatures ($T_{\max}, T_{\min}$)

$$ET_0 = 0.0023 \times (T_{\text{mean}} + 17.8) \times \sqrt{T_{\max} - T_{\min}} \times R_a$$

Where:
- $(T_{\text{mean}} + 17.8)$ models the temperature dependence of vapor pressure deficit.
- $\sqrt{T_{\max} - T_{\min}}$ acts as a proxy for net solar radiation and cloud cover (clear days have wide temperature swings; overcast cloudy days have narrow temperature differences).
- $R_a$ (in mm/day equivalent) is calculated from solar declination $\delta$, relative distance $d_r$, and sunset hour angle $\omega_s$:

$$R_a = \frac{24 \times 60}{\pi} G_{sc} d_r [\omega_s \sin\phi \sin\delta + \cos\phi \cos\delta \sin\omega_s] \times 0.408$$

### 2. FAO-56 Daily Water Balance & Traffic Signals
The root zone is treated as a reservoir holding moisture between **Field Capacity (FC)** and **Wilting Point (WP)**:
- $\text{Total Available Water (TAW)} = \text{TAW}_{\text{soil}} \times Z_r$
- $\text{Readily Available Water (RAW)} = p \times \text{TAW}$ ($p$ is the allowable depletion fraction, ~0.40 for tomato).
- **Daily Deficit Update**:
  $$D_{r, t} = \max(0, \min(\text{TAW}, D_{r, t-1} - P_{\text{eff}} - I + K_c \times ET_0))$$

**Traffic Signals**:
- 🔴 **RED SIGNAL**: $D_r \ge \text{RAW}$. The crop has entered water stress. Irrigate today.
- 🟡 **YELLOW SIGNAL**: $D_r \ge 0.70 \times \text{RAW}$ or projected to deplete in 48h. Irrigate in 1–2 days.
- 🟢 **GREEN SIGNAL**: $D_r < 0.70 \times \text{RAW}$. Soil moisture is sufficient. Wait.

**Pumping Time (Hours)**:
$$\text{Pumping Hours} = \frac{(D_r / 1000) \times \text{Plot Area (m}^2\text{)}}{\text{Pump Discharge (m}^3\text{/hr)}}$$

### 3. Tier 1: Community Sensor Probes
Single-farmer telemetry is financially unfeasible for a marginal farmer owning 1 acre. KrishiSathi implements **Shared Sensor Clusters**:
- Farmers in the same village with the same crop and soil type are linked to one representative IoT probe.
- An ESP32 posts 12-bit ADC capacitive readings to `/api/sensor/readings`.
- If $|D_{r, \text{sensor}} - D_{r, \text{model}}| > 5.0\text{ mm}$, the ground truth from the sensor overrides $D_r$ for all farmers in that cluster, displaying the badge `"Corrected by Sensor"`.

### 4. Village Disease Radar & Privacy Architecture
- **Data Minimization**: Disease reports store ONLY: `{crop, disease, date, village_id}`. No names, phone numbers, or exact field GPS coordinates are stored or displayed.
- **Clustering Rule**: If $\ge 3$ independent reports of the same crop and disease occur within 7 days in villages within 10 km (calculated using the Haversine great-circle formula), a community outbreak alert is raised.
- **Integrated Pest Management (IPM)**: The alert message strictly instructs farmers to **"Inspect your field today"**, NEVER to "spray". Blind pesticide spraying causes chemical resistance and groundwater pollution; visual inspection confirms early localized lesions before any chemical intervention.

### 5. Weekly Rupee Savings Formula
Traditional farmers pump on a rigid 5-day schedule regardless of soil status. KrishiSathi advises irrigating only when $D_r \ge \text{RAW}$:
$$\text{Saving (₹)} = \text{Avoided Irrigations} \times \text{Hours per Session} \times \text{Pump Power (kW)} \times \text{Electricity Rate (₹/kWh)}$$

---

## 📋 Features Status Checklist

| Feature | Status | Implementation Details |
|---|---|---|
| **Farmer Registration** | ✅ Implemented | Stored in SQLite; phone numbers kept private; Krishi Mitra helper mode |
| **Hargreaves ET0 Engine** | ✅ Implemented | Ra derived from latitude + Julian day; FAO-56 calibrated; 4 worked tests |
| **FAO-56 Water Deficit Engine** | ✅ Implemented | Crop stages (Kc interpolation), TAW, RAW, bounded Dr deficit, pumping hours |
| **Signal Triggers** | ✅ Implemented | High-contrast RED / YELLOW / GREEN signals with countdown & check date |
| **Live/Offline Weather** | ✅ Implemented | Open-Meteo free API with automatic fallback to bundled 14-day CSV & SQLite cache |
| **Missed-Call Phone Simulator** | ✅ Implemented | 2-second callback delay, Web SpeechSynthesis audio in MR/HI/EN, SMS bubbles |
| **Tier 1 Shared Sensor Clusters** | ✅ Implemented | ADC calibration, ESP32 `/sensor/readings` API, >5mm cluster override |
| **Leaf Photo Classifier** | ✅ Implemented | Heuristic mock classifier with confidence scores; routes <70% to officer queue |
| **MobileNetV2 Training Script** | ✅ Implemented | `ml/train_leaf_model.py` with PlantVillage transfer learning & TFLite export |
| **Village Disease Radar** | ✅ Implemented | Haversine distance (<10 km), 3-reports in 7-days trigger, strictly privacy-safe |
| **Officer Dashboard & Map** | ✅ Implemented | Local Leaflet.js map, 10-km outbreak radius circle, ranked travel table |
| **Krishi Mitra Helper Mode** | ✅ Implemented | Non-smartphone registration, quick irrigation logging, sensor telemetry monitor |
| **Weekly Rupee Savings** | ✅ Implemented | Computed vs 5-day baseline schedule; displayed on dashboard & spoken via TTS |
| **Water-Saving Tips** | ✅ Implemented | Crop-specific tips: mulching, early/late irrigation, alternate wetting-drying |
| **Scripted Outbreak Simulator** | ✅ Implemented | One-click button adds 3 tomato blight reports in 10 km, fires radar live |
| **Unit Test Suite** | ✅ Implemented | 9 passing tests in `backend/tests/` covering ET0, Kc, Dr, Radar, Sensors |
| **Automatic Pump Relays** | ⏳ Future Work | Hardware relay switching via GSM/MQTT (intentionally excluded: farmer must always decide) |
| **Groundwater Aquifer Tracking** | ⏳ Future Work | Piezometer telemetry and basin-level water table monitoring |

---

## 📸 Screenshots & UI Views

When presenting the application or capturing documentation screenshots, showcase:
1. **Advisory Hero View**: High-visibility RED signal card, depletion gauge, pumping hours, and weather pill.
2. **Phone Simulator**: Feature phone dialer, missed-call countdown, animated sound wave speaking in Marathi/Hindi, and SMS chat bubble.
3. **Leaf Disease Scanner**: Sample leaf presets, confidence score progress bar, first-step advice, and the "Unsure (<70%)" warning box.
4. **Village Disease Radar & Map**: Interactive Leaflet map with 10 km outbreak radius circle around Shivapur-Khed-Saswad and the Extension Officer dispatch list.
5. **Krishi Mitra & Shared Sensor View**: Community ESP32 cluster telemetry card showing ADC counts and the one-tap farmer registration form.
