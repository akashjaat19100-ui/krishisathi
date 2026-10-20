# 🎬 KrishiSathi Viva Demonstration Script
### End-to-End Walkthrough for Examiners and Evaluators

This script guides students through a structured, 5-minute live demonstration of the KrishiSathi prototype during a viva examination or capstone evaluation.

---

## 🛠️ Step 0: Start the Application

In your terminal:
```bash
cd /Users/akashdhillon/.gemini/antigravity/scratch/krishisathi
./run.sh
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

> **Viva Talking Point**: *"KrishiSathi is built with Python FastAPI, SQLite, and vanilla mobile-first HTML/CSS/JS. It runs completely offline with bundled historical weather and local Leaflet mapping assets, requiring zero paid external APIs."*

---

## 🌾 Step 1: Tier 0 Advisory & The Traffic Light Engine

1. Ensure **Ramesh Shinde (Shivapur - Tomato)** is selected in the top bar dropdown.
2. Note the **🔴 RED SIGNAL: IRRIGATE TODAY** card:
   - **Soil Deficit ($D_r$)**: $32.4\text{ mm}$
   - **RAW Trigger**: $30.6\text{ mm}$
   - **Pumping Hours Needed**: $2.5\text{ hours}$ ($\approx 37,500\text{ Liters}$)
   - **Weather Pill**: Displays `Offline (Sample CSV)` with $T_{\max} = 32^\circ\text{C}$ and $ET_0 = 4.5\text{ mm/day}$.
3. Observe the **Weekly Rupee Savings** card:
   - Shows ₹270 saved this week (60 kWh electricity and 240,000 L of groundwater saved) by avoiding calendar-based pumping.

> **Viva Talking Point**: *"Under FAO-56, we calculate reference evapotranspiration ($ET_0$) using the Hargreaves-Samani temperature equation. We track root zone depletion $D_r$. Because $D_r \ge \text{RAW}$, the model triggers a Red Signal to prevent crop moisture stress."*

---

## 📱 Step 2: The Missed-Call & Spoken Phone Simulator

1. Click on the **"📱 Phone"** tab in the navigation bar.
2. Click the green **"📞 Give Missed Call"** button.
3. Observe the simulator:
   - Dialing starts and drops after 1 ring.
   - A 2-second countdown begins (`2... 1... 0`).
   - The phone rings and transitions to the **Incoming Automated Advisory Call** screen.
4. Listen to the browser's audio:
   - The system automatically speaks the localized advisory using the Web SpeechSynthesis API:
     *"नमस्कार रमेश शिंदे. आजचा कृषी साथी सल्ला असा आहे. लाल दिवा. आज पाणी द्या. सुमारे २.५ तास मोटार चालवून पाणी द्या..."*
5. Look at the bottom of the phone screen:
   - An **SMS Chat Bubble** displays the exact concise text message designed for low-literacy farmers with basic feature phones.

> **Viva Talking Point**: *"Marginal farmers in India often do not own smartphones or data plans. With KrishiSathi, any basic \$10 feature phone can give a toll-free missed call to receive an instant automated callback in their mother tongue."*

---

## 💧 Step 3: Confirm Irrigation (One-Tap Feedback)

1. Switch back to the **"🌾 Advisory"** tab.
2. Tap the large button: **"💧 I Irrigated Today (मी आज पाणी दिले)"**.
3. Notice what happens:
   - An alert confirms that irrigation has been logged.
   - The root zone deficit ($D_r$) immediately resets from $32.4\text{ mm}$ to $0.0\text{ mm}$ (refilled to field capacity).
   - The hero card transitions to **🟢 GREEN SIGNAL: WAIT - SUFFICIENT MOISTURE**, instructing the farmer to wait and re-check in 4 days.
   - Pumping hours needed updates to `0.0 hrs`.

> **Viva Talking Point**: *"The farmer always decides. When the farmer confirms irrigation, the soil water balance resets to field capacity, and the log is preserved to compute cumulative rupee and electricity savings."*

---

## 🔍 Step 4: Leaf Disease AI & The "Unsure" Safety Threshold

1. Click on the **"🔍 Leaf Scan"** tab.
2. In the quick-pick preset buttons:
   - Click **"🍅 Tomato Late Blight"**:
     - The AI diagnoses *Tomato Late Blight (Phytophthora infestans)* with **94% confidence**.
     - Actionable first-step IPM advice appears in the farmer's language.
   - Click **"❓ Blurry / Unsure Photo (<70%)"**:
     - The confidence drops to **48%**.
     - Notice that KrishiSathi **refuses to guess**! A warning appears: *"⚠️ Unsure Diagnosis (<70%): Photo has been queued to Extension Officer review. The app will never guess pesticides blindly."*

> **Viva Talking Point**: *"Standard computer vision apps often hallucinate or guess diagnoses on poor-quality images. KrishiSathi implements an explicit confidence cutoff at 70%. Ambiguous photos are sent to a human agricultural officer instead of recommending dangerous chemical sprays."*

---

## 🚨 Step 5: Village Disease Radar (Community Outbreak Detection)

1. With **Tomato Late Blight** selected in the leaf scanner, click **"📢 Confirm & Report Anonymously"**.
2. Notice the privacy notice:
   - No farmer name, phone number, or exact survey coordinates are sent. Only `{crop, disease, date, village_id}`.
3. Now, trigger the live outbreak demonstration:
   - In the top header bar, click the red button: **"🚨 Simulate Outbreak"**.
   - An alert popup confirms:
     *"Added 3 independent Tomato Late Blight reports across neighboring Pune villages (Shivapur, Khed-Shivapur, Saswad within 10 km). The Village Disease Radar has raised an active community alert!"*
4. Click on the **"📡 Radar"** tab:
   - **Interactive Leaflet Map**: Shows a large dashed **red 10-km radius circle** over the Shivapur-Khed cluster.
   - **Priority Dispatch Table**: Shivapur and Khed are ranked at the very top with report counts.
   - **Active Alert**: Shows *"Tomato Late Blight (Phytophthora infestans) - Status: REPORTED"*.
5. Switch back to the **"🌾 Advisory"** tab:
   - A pulsing red **Siren Banner** now appears on top of Ramesh Shinde's advisory:
     *"🚨 Alert: Tomato Late Blight reported in nearby village. Inspect your Tomato field today."*
   - Note the word: **"INSPECT"**, never "spray".

> **Viva Talking Point**: *"Crop diseases spread through wind corridors across village boundaries. KrishiSathi's Disease Radar aggregates anonymous reports using the Haversine great-circle formula. When $\ge 3$ reports emerge within 10 km over 7 days, an outbreak alert triggers. We strictly advise farmers to 'inspect', avoiding premature pesticide run-off."*

---

## 🩺 Step 6: Extension Officer Actions

1. Switch to the **"📡 Radar"** tab.
2. Under **Active Outbreak Alerts**, click the green button: **"✔️ Extension Officer Confirm"**.
   - The status updates from **"REPORTED"** to **"CONFIRMED"**.
3. Under **Extension Officer Review Queue**:
   - The blurry leaf photo from Step 4 is waiting in the queue.
   - The officer clicks **"Verify Blight"** to resolve it with human agronomist verification.

---

## 🤝 Step 7: Krishi Mitra (Helper Mode) & Shared Sensor Nodes

1. Click on the **"🤝 Krishi Mitra"** tab.
2. View the **Shared Soil-Moisture Sensor Clusters (Tier 1)**:
   - Shows **Shivapur North Cluster Probe #1** (Tomato + Loam) with raw ADC count, Volumetric Water Content (VWC %), and deficit mm.
   - Click **"⚡ Simulate ESP32 Telemetry & Sync Cluster Farmers"**:
     - The telemetry updates.
     - The physical sensor measurement synchronizes all farmers in that cluster.
     - Switch to the Advisory tab: the badge now displays: **"📡 Corrected by Sensor (cluster_shivapur_tomato_loam)"**.
3. Scroll down to the **Register New Farmer** form:
   - Shows how an extension worker or village helper registers a non-smartphone farmer.

---

## 🏁 End of Demonstration
Conclude the viva by pointing the examiners to the comprehensive mathematical derivations in **`docs/README.md`** and the unit test suite in **`backend/tests/test_engine.py`**.
