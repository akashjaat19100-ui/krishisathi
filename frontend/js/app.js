/**
 * KrishiSathi Mobile-First Application Controller.
 * Handles Tier 0 (Advisory & Water Balance), Tier 1 (Sensor Telemetry),
 * Tier 2 (Disease Radar & Classifier), Phone Simulator, and Leaflet Map.
 */

// Global State
let gFarmers = [];
let gCurrentFarmerId = 1;
let gCurrentAdvisory = null;
let gCurrentLang = "mr";
let gRadarMap = null;
let gMapLayers = [];
let gCurrentSpeechUtterance = null;
let gCurrentDiagnosis = null;

// Initialization on DOM Loaded
document.addEventListener("DOMContentLoaded", () => {
  // Set default sowing date in Krishi Mitra form to 45 days ago
  const defaultSow = new Date();
  defaultSow.setDate(defaultSow.getDate() - 45);
  const sowInput = document.getElementById("reg-sowing-date");
  if (sowInput) {
    sowInput.value = defaultSow.toISOString().split("T")[0];
  }

  // Update phone clock
  updateClock();
  setInterval(updateClock, 30000);

  // Load Initial Data
  loadFarmers();
  loadSensorClusters();
});

function updateClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const clockEl = document.getElementById("phone-clock");
  if (clockEl) clockEl.innerText = timeStr;
}

// ============================================================================
// TAB NAVIGATION
// ============================================================================
function switchTab(tabName) {
  // Update nav buttons
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach(btn => btn.classList.remove("active"));
  
  const activeBtn = Array.from(buttons).find(b => b.innerText.toLowerCase().includes(tabName) || b.onclick.toString().includes(tabName));
  if (activeBtn) activeBtn.classList.add("active");

  // Show target section
  const panes = document.querySelectorAll(".tab-pane");
  panes.forEach(pane => pane.classList.remove("active"));
  
  const targetPane = document.getElementById(`tab-${tabName}`);
  if (targetPane) targetPane.classList.add("active");

  // If radar tab, ensure map renders properly
  if (tabName === "radar") {
    setTimeout(() => {
      initRadarMap();
      loadRadarStatus();
    }, 100);
  } else if (tabName === "mitra") {
    loadSensorClusters();
  }
}

// ============================================================================
// 1. FARMER SELECTION & ADVISORY LOADING (TIER 0)
// ============================================================================
async function loadFarmers() {
  try {
    const resp = await fetch("/api/farmers");
    gFarmers = await resp.json();

    const select = document.getElementById("farmer-select");
    select.innerHTML = "";

    gFarmers.forEach(f => {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.text = `${f.name} - ${f.village_name || f.village_id} (${f.crop.toUpperCase()})`;
      select.appendChild(opt);
    });

    if (gFarmers.length > 0) {
      gCurrentFarmerId = gFarmers[0].id;
      select.value = gCurrentFarmerId;
      loadAdvisory(gCurrentFarmerId);
    }
  } catch (err) {
    console.error("Error loading farmers:", err);
  }
}

function onFarmerChange(farmerId) {
  gCurrentFarmerId = parseInt(farmerId);
  const farmer = gFarmers.find(f => f.id === gCurrentFarmerId);
  if (farmer && farmer.language) {
    document.getElementById("lang-select").value = farmer.language;
    gCurrentLang = farmer.language;
  }
  loadAdvisory(gCurrentFarmerId);
}

function onLanguageChange(lang) {
  gCurrentLang = lang;
  loadAdvisory(gCurrentFarmerId);
}

async function loadAdvisory(farmerId) {
  try {
    const resp = await fetch(`/api/irrigation/advisory/${farmerId}`);
    if (!resp.ok) return;

    gCurrentAdvisory = await resp.json();
    renderAdvisoryUI(gCurrentAdvisory);
  } catch (err) {
    console.error("Error loading advisory:", err);
  }
}

function renderAdvisoryUI(adv) {
  // 1. Weather Badge
  const weatherBadge = document.getElementById("weather-badge");
  const weatherBadgeText = document.getElementById("weather-badge-text");
  if (adv.weather.is_offline) {
    weatherBadge.className = "badge-pill badge-offline";
    weatherBadgeText.innerText = adv.weather.badge_text || "Offline (Cached)";
  } else {
    weatherBadge.className = "badge-pill badge-online";
    weatherBadgeText.innerText = adv.weather.badge_text || "Live (Open-Meteo)";
  }

  // 2. Outbreak Alert Banner
  const banner = document.getElementById("outbreak-banner");
  if (adv.active_alerts && adv.active_alerts.length > 0) {
    const alert = adv.active_alerts[0];
    document.getElementById("banner-title").innerText = `⚠️ Outbreak Alert: ${alert.disease}`;
    document.getElementById("banner-msg").innerText = alert.advisory_message;
    banner.style.display = "flex";
  } else {
    banner.style.display = "none";
  }

  // 3. Signal Hero Card
  const hero = document.getElementById("signal-hero");
  const icon = document.getElementById("signal-icon");
  const title = document.getElementById("signal-title");
  const desc = document.getElementById("signal-desc");

  hero.className = `signal-card signal-${adv.signal}`;
  if (adv.signal === "RED") {
    icon.innerText = "🔴";
    title.innerText = "RED SIGNAL: IRRIGATE TODAY";
    desc.innerText = `Refill root deficit with about ${adv.pumping_hours} hours of pumping (${adv.volume_liters.toLocaleString()} Liters).`;
  } else if (adv.signal === "YELLOW") {
    icon.innerText = "🟡";
    title.innerText = "YELLOW SIGNAL: IRRIGATE IN 1-2 DAYS";
    desc.innerText = `Soil moisture is depleting. Plan for about ${adv.pumping_hours} hours of pumping soon.`;
  } else {
    icon.innerText = "🟢";
    title.innerText = "GREEN SIGNAL: WAIT - SUFFICIENT MOISTURE";
    desc.innerText = `Soil moisture is adequate. No irrigation needed today. Check back on ${adv.next_check_date}.`;
  }

  // Badges on Hero
  document.getElementById("sensor-source-badge").innerText = adv.sensor_badge_text;
  document.getElementById("crop-stage-badge").innerText = `${adv.crop.toUpperCase()} | ${adv.soil_type.toUpperCase()} SOIL`;

  // 4. Metrics Grid
  document.getElementById("metric-dr").innerText = `${adv.dr_mm} mm`;
  document.getElementById("metric-raw").innerText = `RAW Trigger: ${adv.raw_mm} mm`;
  document.getElementById("metric-hours").innerText = `${adv.pumping_hours} hrs`;
  document.getElementById("metric-volume").innerText = `~${adv.volume_liters.toLocaleString()} L`;
  document.getElementById("metric-next").innerText = (adv.days_until_trigger === 0) ? "Today" : `In ${adv.days_until_trigger} Days`;
  document.getElementById("metric-date").innerText = adv.next_check_date;
  document.getElementById("metric-et0").innerText = `${adv.weather.et0_mm} mm/d`;
  document.getElementById("metric-weather").innerText = `Tmax: ${adv.weather.tmax}°C | Rain: ${adv.weather.precip_mm}mm`;

  // 5. Depletion Gauge
  const depletionPct = Math.min(100, Math.max(0, adv.depletion_pct));
  const fillBar = document.getElementById("depletion-bar-fill");
  fillBar.style.width = `${depletionPct}%`;
  if (adv.signal === "RED") fillBar.style.background = "var(--signal-red)";
  else if (adv.signal === "YELLOW") fillBar.style.background = "var(--signal-yellow)";
  else fillBar.style.background = "var(--signal-green)";

  const rawFraction = Math.round((adv.raw_mm / Math.max(1, adv.taw_mm)) * 100);
  document.getElementById("label-raw-threshold").innerText = `RAW Trigger (${rawFraction}%)`;

  // 6. Savings Card
  const sav = adv.weekly_savings;
  document.getElementById("savings-rupees").innerText = `₹${sav.rupees_saved}`;
  document.getElementById("savings-kwh").innerText = `${sav.kwh_saved} kWh`;
  document.getElementById("savings-hours").innerText = `${sav.pump_hours_saved} hrs`;
  document.getElementById("savings-liters").innerText = `${sav.liters_water_saved.toLocaleString()} L`;

  // 7. Agronomic Tip
  document.getElementById("water-saving-tip-text").innerText = adv.water_saving_tip;

  // 8. Update Phone Simulator pre-loaded text
  document.getElementById("phone-sms-bubble-text").innerText = adv.sms_bubble_message;
  document.getElementById("phone-farmer-tag").innerText = `Farmer: ${adv.farmer_name} (${adv.village_name})`;
}

// Confirm Irrigation Action
async function confirmFarmerIrrigation() {
  if (!gCurrentAdvisory) return;

  try {
    const resp = await fetch("/api/irrigation/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        farmer_id: gCurrentFarmerId,
        hours_applied: null
      })
    });

    if (resp.ok) {
      alert("✅ Irrigation recorded! Soil root deficit has been refilled to field capacity.");
      loadAdvisory(gCurrentFarmerId);
    }
  } catch (err) {
    console.error("Error confirming irrigation:", err);
  }
}

// ============================================================================
// 2. PHONE SIMULATOR (MISSED-CALL / VOICE / SMS)
// ============================================================================
let gCountdownTimer = null;

async function triggerMissedCall() {
  document.getElementById("phone-state-idle").style.display = "none";
  document.getElementById("phone-state-calling").style.display = "block";
  document.getElementById("phone-state-active").style.display = "none";

  let countdown = 2;
  const countEl = document.getElementById("callback-countdown");
  countEl.innerText = countdown;

  if (gCountdownTimer) clearInterval(gCountdownTimer);
  gCountdownTimer = setInterval(() => {
    countdown--;
    countEl.innerText = countdown;
    if (countdown <= 0) {
      clearInterval(gCountdownTimer);
      executePhoneCallback();
    }
  }, 1000);
}

async function executePhoneCallback() {
  try {
    const resp = await fetch(`/api/phone/missed-call?farmer_id=${gCurrentFarmerId}`, {
      method: "POST"
    });
    const data = await resp.json();

    document.getElementById("phone-state-calling").style.display = "none";
    document.getElementById("phone-state-active").style.display = "flex";

    // Update SMS Bubble
    document.getElementById("phone-sms-bubble-text").innerText = data.sms_text;
    document.getElementById("phone-sms-time").innerText = "Just now";

    // Play Voice Speech using Browser SpeechSynthesis API
    speakText(data.spoken_text, data.voice_tag);
  } catch (err) {
    console.error("Error executing callback:", err);
  }
}

function speakText(text, voiceTag) {
  if (!("speechSynthesis" in window)) {
    console.warn("SpeechSynthesis not supported on this browser.");
    return;
  }

  window.speechSynthesis.cancel(); // Stop prior speech

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = voiceTag || "hi-IN";
  utterance.rate = 0.95; // Slightly slower, clear cadence for rural farmers
  utterance.pitch = 1.0;

  // Animate sound waves while speaking
  const waveEl = document.getElementById("audio-wave");
  utterance.onstart = () => {
    if (waveEl) waveEl.style.opacity = "1";
  };
  utterance.onend = () => {
    if (waveEl) waveEl.style.opacity = "0.2";
  };
  utterance.onerror = () => {
    if (waveEl) waveEl.style.opacity = "0.2";
  };

  gCurrentSpeechUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

function replayVoiceMessage() {
  if (gCurrentAdvisory) {
    const voiceCodes = { "mr": "mr-IN", "hi": "hi-IN", "en": "en-IN" };
    speakText(gCurrentAdvisory.spoken_message, voiceCodes[gCurrentLang] || "hi-IN");
  }
}

function hangupPhone() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  document.getElementById("phone-state-active").style.display = "none";
  document.getElementById("phone-state-calling").style.display = "none";
  document.getElementById("phone-state-idle").style.display = "block";
}

// ============================================================================
// 3. LEAF DISEASE SCAN (TIER 2)
// ============================================================================
async function testLeafSample(filename, crop) {
  const farmer = gFarmers.find(f => f.id === gCurrentFarmerId) || { village_id: "v_shivapur", crop: "tomato" };
  const villageId = farmer.village_id;

  const formData = new FormData();
  formData.append("crop", crop || farmer.crop);
  formData.append("village_id", villageId);
  formData.append("filename_hint", filename);

  try {
    const resp = await fetch("/api/disease/check", {
      method: "POST",
      body: formData
    });
    const result = await resp.json();
    displayDiagnosis(result, filename, crop || farmer.crop, villageId);
  } catch (err) {
    console.error("Error analyzing leaf:", err);
  }
}

async function onLeafFileSelected(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const farmer = gFarmers.find(f => f.id === gCurrentFarmerId) || { village_id: "v_shivapur", crop: "tomato" };

  const formData = new FormData();
  formData.append("crop", farmer.crop);
  formData.append("village_id", farmer.village_id);
  formData.append("file", file);

  try {
    const resp = await fetch("/api/disease/check", {
      method: "POST",
      body: formData
    });
    const result = await resp.json();
    displayDiagnosis(result, file.name, farmer.crop, farmer.village_id);
  } catch (err) {
    console.error("Error analyzing uploaded file:", err);
  }
}

function displayDiagnosis(res, filename, crop, villageId) {
  gCurrentDiagnosis = {
    crop: crop,
    disease: res.disease_name,
    confidence: res.confidence_pct / 100.0,
    village_id: villageId,
    image_filename: filename
  };

  const container = document.getElementById("disease-result-container");
  container.style.display = "block";

  document.getElementById("disease-name").innerText = res.disease_name;
  document.getElementById("disease-conf-badge").innerText = `${res.confidence_pct}% Match`;
  
  const confBar = document.getElementById("disease-conf-bar");
  confBar.style.width = `${res.confidence_pct}%`;

  const unsureBox = document.getElementById("disease-unsure-box");
  const reportBtn = document.getElementById("report-btn-wrapper");

  // Localized advice text
  const adviceObj = res.advice || {};
  const adviceText = adviceObj[gCurrentLang] || adviceObj["en"] || "Inspect your crop field carefully.";
  document.getElementById("disease-advice-text").innerText = adviceText;

  if (res.is_unsure) {
    unsureBox.style.display = "block";
    reportBtn.style.display = "none";
    confBar.style.background = "#ffc107";
  } else {
    unsureBox.style.display = "none";
    reportBtn.style.display = "block";
    confBar.style.background = (res.disease_name.includes("Healthy")) ? "var(--signal-green)" : "#b7094c";
  }
}

async function confirmAndReportDisease() {
  if (!gCurrentDiagnosis) return;

  try {
    const resp = await fetch("/api/disease/confirm-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(gCurrentDiagnosis)
    });
    const data = await resp.json();

    if (data.outbreak_alert_triggered) {
      alert("🚨 OUTBREAK ALERT TRIGGERED!\n\n3 or more independent reports of this disease have occurred within 10 km in the last 7 days.\nNearby farmers are now receiving an 'Inspect Field' alert!");
      switchTab("radar");
    } else {
      alert("✅ Report logged anonymously to Village Radar.\nNo personal data was shared.");
    }

    loadAdvisory(gCurrentFarmerId);
  } catch (err) {
    console.error("Error confirming report:", err);
  }
}

// ============================================================================
// 4. VILLAGE DISEASE RADAR & EXTENSION OFFICER (LEAFLET MAP)
// ============================================================================
function initRadarMap() {
  if (gRadarMap) return;

  const mapEl = document.getElementById("radar-map");
  if (!mapEl) return;

  // Center around Pune cluster (Shivapur / Khed)
  gRadarMap = L.map("radar-map").setView([18.34, 73.90], 10);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap contributors"
  }).addTo(gRadarMap);
}

async function loadRadarStatus() {
  try {
    const resp = await fetch("/api/radar/status");
    const data = await resp.json();

    renderMapMarkers(data.villages, data.active_alerts, data.ranked_villages);
    renderRankedVillages(data.ranked_villages);
    renderActiveAlerts(data.active_alerts);
    loadOfficerQueue();
  } catch (err) {
    console.error("Error loading radar status:", err);
  }
}

function renderMapMarkers(villages, alerts, rankedVillages) {
  if (!gRadarMap) return;

  // Clear existing markers
  gMapLayers.forEach(layer => gRadarMap.removeLayer(layer));
  gMapLayers = [];

  const countsMap = {};
  rankedVillages.forEach(r => countsMap[r.village_id] = r.report_count);

  villages.forEach(v => {
    const count = countsMap[v.id] || 0;
    const isOutbreak = (count >= 3);

    // Marker Pin
    const marker = L.circleMarker([v.latitude, v.longitude], {
      radius: isOutbreak ? 12 : 8,
      fillColor: isOutbreak ? "#d90429" : "#2a9d8f",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    }).addTo(gRadarMap);

    marker.bindPopup(`
      <b>${v.name}</b><br>
      Reports: <b>${count}</b><br>
      <i>${v.description}</i>
    `);
    gMapLayers.push(marker);

    // If Outbreak active, draw 10 km radius circle around village cluster
    if (isOutbreak) {
      const circle = L.circle([v.latitude, v.longitude], {
        radius: 10000, // 10 km in meters
        color: "#d90429",
        fillColor: "#ff4d6d",
        fillOpacity: 0.15,
        weight: 1.5,
        dashArray: "6, 6"
      }).addTo(gRadarMap);
      circle.bindTooltip(`10 km Outbreak Radius (${v.name})`, { sticky: true });
      gMapLayers.push(circle);
    }
  });
}

function renderRankedVillages(rankedList) {
  const tbody = document.getElementById("ranked-villages-tbody");
  tbody.innerHTML = "";

  rankedList.forEach((item, index) => {
    const tr = document.createElement("tr");
    const isHigh = item.report_count >= 3;
    const badgeHtml = isHigh 
      ? `<span class="badge-pill badge-offline" style="background:#e63946; color:white;">🚨 Outbreak</span>`
      : `<span class="badge-pill badge-online">Normal</span>`;

    tr.innerHTML = `
      <td><b>#${index + 1}</b></td>
      <td><b>${item.name}</b></td>
      <td><b>${item.report_count}</b></td>
      <td>${item.crops.join(", ") || "Vegetables"}</td>
      <td>${badgeHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderActiveAlerts(alerts) {
  const container = document.getElementById("active-alerts-list");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `<p style="font-size: 13px; color: var(--text-muted);">No active outbreaks currently recorded. Surveillance is normal.</p>`;
    return;
  }

  container.innerHTML = "";
  alerts.forEach(a => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.borderLeft = (a.status === "Confirmed") ? "5px solid #2a9d8f" : "5px solid #d90429";

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h4 style="font-size: 15px; font-weight:700;">🚨 ${a.disease} (${a.crop.toUpperCase()})</h4>
          <p style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
            Affected Villages: <b>${a.village_names.join(", ")}</b> | Reports: <b>${a.report_count} in 7 days</b>
          </p>
        </div>
        <span class="badge-tag" style="background:${a.status === 'Confirmed' ? '#2a9d8f' : '#d90429'}; color:white;">
          ${a.status.toUpperCase()}
        </span>
      </div>
      <div style="display:flex; gap:8px; margin-top:12px;">
        ${a.status !== 'Confirmed' ? `
          <button class="btn-xs btn-primary" style="background:var(--primary); color:white;" onclick="confirmOfficerAlert(${a.id}, 'Confirmed')">
            ✔️ Extension Officer Confirm
          </button>
        ` : `
          <span style="font-size:11px; color:var(--primary); font-weight:600;">✅ Confirmed by Agricultural Extension Officer</span>
        `}
      </div>
    `;
    container.appendChild(card);
  });
}

async function confirmOfficerAlert(alertId, newStatus) {
  try {
    const resp = await fetch("/api/officer/alert/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        alert_id: alertId,
        status: newStatus,
        officer_notes: "Field verified by taluka extension team."
      })
    });
    if (resp.ok) {
      alert("Alert status confirmed! Extension advisory broadcast to all cluster farmers.");
      loadRadarStatus();
      loadAdvisory(gCurrentFarmerId);
    }
  } catch (err) {
    console.error("Error updating alert:", err);
  }
}

async function loadOfficerQueue() {
  try {
    const resp = await fetch("/api/officer/queue");
    const items = await resp.json();
    const container = document.getElementById("officer-queue-list");

    if (!items || items.length === 0) {
      container.innerHTML = `<p style="font-size: 12px; color: var(--text-muted);">Queue is empty. No unsure photos pending review.</p>`;
      return;
    }

    container.innerHTML = "";
    items.forEach(it => {
      const card = document.createElement("div");
      card.className = "officer-card-item";
      card.innerHTML = `
        <div>
          <b>${it.image_filename}</b> (${it.crop.toUpperCase()}) - ${it.village_name}
          <div style="font-size:11px; color:var(--text-muted);">Confidence: ${it.confidence}% | Status: <b>${it.status}</b></div>
        </div>
        <div style="display:flex; gap:6px;">
          ${it.status === 'pending' ? `
            <button class="btn-xs btn-primary" style="background:#28a745; color:white;" onclick="resolveOfficerItem(${it.id}, 'Tomato Late Blight (Phytophthora infestans)')">
              Verify Blight
            </button>
            <button class="btn-xs btn-reset" style="background:#6c757d; color:white;" onclick="resolveOfficerItem(${it.id}, 'Healthy')">
              Mark Healthy
            </button>
          ` : `
            <span style="font-size:11px; color:#28a745; font-weight:700;">Verdict: ${it.officer_verdict}</span>
          `}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading officer queue:", err);
  }
}

async function resolveOfficerItem(itemId, verdict) {
  const formData = new FormData();
  formData.append("item_id", itemId);
  formData.append("verdict", verdict);

  try {
    const resp = await fetch("/api/officer/queue/resolve", {
      method: "POST",
      body: formData
    });
    if (resp.ok) {
      alert(`Item #${itemId} diagnosed as '${verdict}'. Anonymous record logged.`);
      loadRadarStatus();
    }
  } catch (err) {
    console.error("Error resolving queue item:", err);
  }
}

// ============================================================================
// 5. KRISHI MITRA & SHARED SENSOR NODES (TIER 1)
// ============================================================================
async function loadSensorClusters() {
  try {
    const resp = await fetch("/api/sensor/clusters");
    const clusters = await resp.json();
    const container = document.getElementById("sensor-clusters-container");
    if (!container) return;

    container.innerHTML = "";
    clusters.forEach(c => {
      const box = document.createElement("div");
      box.className = "card";
      box.style.background = "#ffffff";
      box.style.marginBottom = "10px";
      box.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">📡 ${c.name}</h4>
            <p style="font-size:11px; color:var(--text-muted);">
              Village: <b>${c.village_name}</b> | Crop: <b>${c.crop}</b> | Soil: <b>${c.soil_type}</b>
            </p>
          </div>
          <span class="badge-tag" style="background:#0d47a1; color:white;">
            Linked: ${c.farmers_linked_count} Farmers
          </span>
        </div>
        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin: 10px 0; font-size:12px;">
          <div>ADC Count: <b>${c.last_raw_adc || 2800}</b></div>
          <div>VWC Moisture: <b>${c.last_vwc_pct || 18.5}%</b></div>
          <div>Deficit: <b>${c.last_deficit_mm || 30.0} mm</b></div>
        </div>
        <button class="btn-xs btn-primary" style="background:#1565c0; color:white; width:100%; padding:8px;" onclick="simulateClusterTelemetry('${c.id}')">
          ⚡ Simulate ESP32 Telemetry & Sync Cluster Farmers
        </button>
      `;
      container.appendChild(box);
    });
  } catch (err) {
    console.error("Error loading clusters:", err);
  }
}

async function simulateClusterTelemetry(clusterId) {
  try {
    const resp = await fetch(`/api/sensor/simulate-reading/${clusterId}`, {
      method: "POST"
    });
    const data = await resp.json();
    alert(`📡 ESP32 Telemetry Received!\n\nSensor Deficit: ${data.sensor_deficit_mm} mm\nFarmers Synchronized in Cluster: ${data.farmers_corrected}\nAll linked farmers now bear the 'Corrected by Sensor' badge.`);
    loadSensorClusters();
    loadAdvisory(gCurrentFarmerId);
  } catch (err) {
    console.error("Error simulating reading:", err);
  }
}

async function handleFarmerRegistration(e) {
  e.preventDefault();

  const payload = {
    name: document.getElementById("reg-name").value,
    phone: document.getElementById("reg-phone").value,
    village_id: document.getElementById("reg-village").value,
    language: document.getElementById("reg-language").value,
    crop: document.getElementById("reg-crop").value,
    sowing_date: document.getElementById("reg-sowing-date").value,
    soil_type: document.getElementById("reg-soil").value,
    plot_area_m2: parseFloat(document.getElementById("reg-area").value || "4046"),
    pump_discharge_m3h: parseFloat(document.getElementById("reg-pump-discharge").value || "15"),
    pump_power_kw: parseFloat(document.getElementById("reg-pump-power").value || "3.75"),
    electricity_rate: parseFloat(document.getElementById("reg-elec-rate").value || "4.5")
  };

  try {
    const resp = await fetch("/api/farmers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const newFarmer = await resp.json();

    alert(`✅ Farmer ${newFarmer.name} registered successfully in ${newFarmer.village_name}!\nIrrigation model initialized.`);
    document.getElementById("farmer-register-form").reset();
    
    await loadFarmers();
    document.getElementById("farmer-select").value = newFarmer.id;
    onFarmerChange(newFarmer.id);
    switchTab("advisory");
  } catch (err) {
    console.error("Error registering farmer:", err);
  }
}

// ============================================================================
// 6. SCRIPTED DEMO CONTROLS (OUTBREAK & RESET)
// ============================================================================
async function triggerOutbreakSimulation() {
  try {
    const resp = await fetch("/api/demo/simulate-outbreak", { method: "POST" });
    const data = await resp.json();

    alert("🚨 SCRIPTED OUTBREAK TRIGGERED!\n\nAdded 3 independent Tomato Late Blight reports across neighboring Pune villages (Shivapur, Khed-Shivapur, Saswad within 10 km).\n\nThe Village Disease Radar has raised an active community alert!");
    
    // Switch to advisory to show alert banner, then radar
    await loadAdvisory(gCurrentFarmerId);
    switchTab("radar");
  } catch (err) {
    console.error("Error triggering outbreak simulation:", err);
  }
}

async function resetDemoData() {
  if (!confirm("Reset all database tables to initial demo seed state?")) return;

  try {
    const resp = await fetch("/api/demo/reset", { method: "POST" });
    if (resp.ok) {
      alert("🔄 Database reset to clean seed state (8 farmers, 2 clusters, 14 days weather).");
      await loadFarmers();
      loadAdvisory(gCurrentFarmerId);
      loadSensorClusters();
      if (gRadarMap) loadRadarStatus();
      switchTab("advisory");
    }
  } catch (err) {
    console.error("Error resetting data:", err);
  }
}
