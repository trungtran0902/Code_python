/* ================= KEY ALIAS ================= */
const MAP4D_KEY_ALIAS = {
  dev: "93d393d0f6507ee00b62fe01db7430fa",
  pro: "93d393d0f6507ee00b62fe01db7430fa",
  trung: "93d393d0f6507ee00b62fe01db7430fa",
  test: "PUT_TEST_KEY_HERE"
};

const normalizeKeyInput = s => (s || "").trim().toLowerCase().replace(/\s+/g, "");
const resolveApiKey = input => MAP4D_KEY_ALIAS[normalizeKeyInput(input)] || input;

/* ================= MAP ================= */
let map = null;
let markers = [];
let mapSdkPromise = null;
let markerClusterer = null;

// ===== POI OVERLAY =====
let poiOverlay = null;

function clearMarkers() {
  // remove clusterer if present
  try {
    if (markerClusterer && typeof markerClusterer.setMap === 'function') {
      markerClusterer.setMap(null);
      markerClusterer = null;
    }
  } catch (e) { /* ignore */ }

  markers.forEach(m => { try { m.setMap(null); } catch (e) {} });
  markers = [];
}

function clearPoiOverlay() {
  if (poiOverlay) {
    poiOverlay.setMap(null);
    poiOverlay = null;
  }
}

function drawMarker(lat, lng, title, snippet) {
  if (!map || lat == null || lng == null) return;

  // Build marker options (position only); some SDK versions prefer setMap()
  const markerOpts = {
    position: { lat: Number(lat), lng: Number(lng) },
    title: title || "",
    zIndex: 1000
  };

  const iconUrl = "https://api.map4d.vn/sdk/map/images/marker-default.png";
  // NOTE: the previous hardcoded icon URL may not exist. Omit custom icon
  // and allow Map4D SDK to use its default marker to ensure markers render.

  const marker = new map4d.Marker(markerOpts);
  try { marker.setMap(map); } catch (e) { /* some SDKs accept map in ctor; ignore errors */ }
  markers.push(marker);
  console.log("drawMarker created", { lat, lng, title, snippet, markerOpts, marker });

  // Attach InfoWindow / popup showing title + snippet when marker clicked
  try {
    if (map4d && typeof map4d.InfoWindow === 'function') {
      const esc = s => String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
      const content = `<div style="font-size:13px"><strong>${esc(title)}</strong>${snippet ? `<div style=\"margin-top:6px\">${esc(snippet)}</div>` : ''}</div>`;
      const info = new map4d.InfoWindow({ content });

      const openInfo = () => {
        try { info.open(map, marker); } catch (e) { console.warn('InfoWindow open failed', e); }
      };

      if (typeof marker.addListener === 'function') marker.addListener('click', openInfo);
      else if (map4d.event && typeof map4d.event.addListener === 'function') map4d.event.addListener(marker, 'click', openInfo);
      else if (typeof marker.on === 'function') marker.on('click', openInfo);
      else marker.__openInfo = openInfo;
    }
  } catch (e) {
    console.warn('InfoWindow not supported by Map4D SDK in this environment', e);
  }
}

// create a marker object (not necessarily added to map) with nicer SVG icon and InfoWindow
function createMarkerObject(lat, lng, title, snippet) {
  const markerOpts = { position: { lat: Number(lat), lng: Number(lng) }, title: title || "" };

  // Use Map4D's default marker (no custom icon to avoid URL issues)

  const marker = new map4d.Marker(markerOpts);

  // attach InfoWindow if available
  try {
    if (map4d && typeof map4d.InfoWindow === 'function') {
      const esc = s => String(s || '').replace(/[&<>"]+/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c] || '');
      const content = `<div style="font-size:13px"><strong>${esc(title)}</strong>${snippet ? `<div style=\"margin-top:6px\">${esc(snippet)}</div>` : ''}</div>`;
      const info = new map4d.InfoWindow({ content });
      const openInfo = () => { try { info.open(map, marker); } catch (e) {} };
      if (typeof marker.addListener === 'function') marker.addListener('click', openInfo);
      else if (map4d.event && typeof map4d.event.addListener === 'function') map4d.event.addListener(marker, 'click', openInfo);
      else if (typeof marker.on === 'function') marker.on('click', openInfo);
    }
  } catch (e) {
    console.warn('InfoWindow/attach failed', e);
  }

  return marker;
}


function drawNearbyPOIs(rows) {
  if (!map) return;

  clearPoiOverlay();

  const pois = rows
    .filter(r => r.lat != null && r.lng != null && r.place_name)
    .map((r, i) => ({
      id: r.place_id || `poi_${i}`,
      name: r.place_name,
      position: {
        lat: Number(r.lat),
        lng: Number(r.lng)
      },
      address: r.place_address || ""
    }));

  if (!pois.length) {
    log("Khong co POI hop le de ve", "warn");
    return;
  }

  poiOverlay = new map4d.PoiOverlay({
    map,
    data: pois
  });

  log(`Da ve ${pois.length} POI`);
}

function fitMap() {
  if (!markers.length) return;
  const bounds = new map4d.LatLngBounds();
  markers.forEach(m => bounds.extend(m.getPosition()));
  map.fitBounds(bounds);
}

function setMapState(text, active = false) {
  if (mapStateText) mapStateText.textContent = text;
  if (mapState) mapState.classList.toggle("active", Boolean(active));
}

function ensureMapSdkLoaded(key) {
  if (window.map4d) return Promise.resolve();
  if (mapSdkPromise) return mapSdkPromise;

  mapSdkPromise = new Promise((resolve, reject) => {
    const cb = "__map4d_cb_" + Math.random().toString(16).slice(2);
    window[cb] = () => { delete window[cb]; resolve(); };

    const s = document.createElement("script");
    s.defer = true;
    s.src = `https://api.map4d.vn/sdk/map/js?version=3.0&key=${encodeURIComponent(key)}&callback=${cb}`;
    s.onerror = () => reject(new Error("Khong load duoc Map4D SDK"));
    document.head.appendChild(s);
  });

  return mapSdkPromise;
}

async function ensureMapReady(key) {
  await ensureMapSdkLoaded(key);
  document.getElementById("mapOverlay").classList.add("hidden");
  if (!map) {
    map = new map4d.Map(document.getElementById("map"), {
      center: { lat: 16.200088, lng: 107.733920 },
      zoom: 6
    });
  }
  setMapState("Bản đồ đã sẵn sàng", true);
}

/* ================= STATE ================= */
let rows = [];
let workbook, sheetName;
let isRunning = false;
let isPaused = false;
let currentRowIndex = 0;
let processedCount = 0;
let successCount = 0;
let errorCountValue = 0;
let hasCompletedRun = false;
let currentRunMode = null;
let currentForwardColumns = [];
let currentFileSignature = null;
let currentFileMeta = null;

// GHI NHO MODE LAN RUN CUOI
let lastRunMode = null;

const CHECKPOINT_DB_NAME = "map4d_excel_checkpoint_db";
const CHECKPOINT_STORE_NAME = "checkpoints";
const CHECKPOINT_VERSION = 1;
const CHECKPOINT_EVERY_ROWS = 20;
const REQUEST_CONCURRENCY = 3;

const MODE_OUTPUT_FIELDS = {
  forward: ["id", "name", "address", "oldaddress", "lat", "lng", "status", "error"],
  reverse: ["id", "name", "address", "oldaddress", "lat", "lng", "status", "error"],
  nearby: [
    "id", "name", "address", "oldaddress", "lat", "lng",
    "distance", "place_id", "place_name", "place_address", "status", "error"
  ]
};

const fileInput = document.getElementById("fileInput");
const sheetContainer = document.getElementById("sheetContainer");
const sheetSelect = document.getElementById("sheetSelect");
const fileInfo = document.getElementById("fileInfo");
const columnsContainer = document.getElementById("columnsContainer");
const latColumn = document.getElementById("latColumn");
const lngColumn = document.getElementById("lngColumn");
const keywordColumn = document.getElementById("keywordColumn");
const nearbyLatColumn = document.getElementById("nearbyLatColumn");
const nearbyLngColumn = document.getElementById("nearbyLngColumn");
const nearbyRadius = document.getElementById("nearbyRadius");
const forwardCard = document.getElementById("forwardCard");
const reverseCard = document.getElementById("reverseCard");
const nearbyCard = document.getElementById("nearbyCard");
const runCard = document.getElementById("runCard");
const logCard = document.getElementById("logCard");
const runBtn = document.getElementById("runBtn");
const drawBtn = document.getElementById("drawBtn");
const downloadBtn = document.getElementById("downloadBtn");
const clearCheckpointBtn = document.getElementById("clearCheckpointBtn");
const checkpointInfo = document.getElementById("checkpointInfo");
const delayMs = document.getElementById("delayMs");
const apiKey = document.getElementById("apiKey");
const totalRows = document.getElementById("totalRows");
const processedRows = document.getElementById("processedRows");
const successRows = document.getElementById("successRows");
const errorRows = document.getElementById("errorRows");
const progressText = document.getElementById("progressText");
const progressFill = document.getElementById("progressFill");
const mapState = document.getElementById("mapState");
const mapStateText = document.getElementById("mapStateText");
const actionSectionLabel = document.getElementById("actionSectionLabel");

/* ================= HELPERS ================= */
const logEl = document.getElementById("status");
const pauseBtn = document.getElementById("pauseBtn");
const mojibakePattern = /(?:Ãƒ.|Ã‚.|Ã„.|Ã….|Ã†.|Ã.|Ã‘.|Ã¡Â»|Ã¢.|Ã°Å¸)/;
function normalizeText(value) {
  if (typeof value !== "string") return value;
  const input = value.trim() ? value : value;
  if (!mojibakePattern.test(input)) return input;
  try {
    const bytes = Uint8Array.from(Array.from(input, ch => ch.charCodeAt(0) & 0xff));
    const decoded = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    return decoded.includes("\uFFFD") ? input : decoded;
  } catch {
    return input;
  }
}
const log = (m, type = "info") => {
  const text = normalizeText(String(m));
  logEl.textContent += text + "\n";
  logEl.scrollTop = logEl.scrollHeight;

  if (type === "error") console.error(text);
  else if (type === "warn") console.warn(text);
  else console.log(text);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
setMapState("Chưa tải bản đồ", false);
const toNumber = v => {
  const n = Number(String(v).trim().replace(",", "."));
  return Number.isFinite(n) ? n : null;
};
const checkpointTimeFormatter = new Intl.DateTimeFormat("vi-VN", {
  dateStyle: "short",
  timeStyle: "medium"
});

function buildFileSignature(file) {
  if (!file) return null;
  return `${file.name}__${file.size}__${file.lastModified}`;
}

function updateCheckpointInfo(message, hasCheckpoint = false) {
  checkpointInfo.textContent = normalizeText(message);
  clearCheckpointBtn.disabled = !hasCheckpoint;
}

function openCheckpointDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(CHECKPOINT_DB_NAME, CHECKPOINT_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(CHECKPOINT_STORE_NAME)) {
        db.createObjectStore(CHECKPOINT_STORE_NAME, { keyPath: "fileSignature" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Khong mo duoc IndexedDB"));
  });
}

async function getCheckpoint(fileSignature) {
  if (!fileSignature) return null;
  const db = await openCheckpointDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CHECKPOINT_STORE_NAME, "readonly");
    const store = tx.objectStore(CHECKPOINT_STORE_NAME);
    const request = store.get(fileSignature);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error || new Error("Khong doc duoc checkpoint"));
    tx.oncomplete = () => db.close();
  });
}

async function putCheckpoint(payload) {
  const db = await openCheckpointDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CHECKPOINT_STORE_NAME, "readwrite");
    const store = tx.objectStore(CHECKPOINT_STORE_NAME);
    store.put(payload);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error || new Error("Khong ghi duoc checkpoint"));
  });
}

async function deleteCheckpoint(fileSignature) {
  if (!fileSignature) return;
  const db = await openCheckpointDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CHECKPOINT_STORE_NAME, "readwrite");
    const store = tx.objectStore(CHECKPOINT_STORE_NAME);
    store.delete(fileSignature);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error || new Error("Khong xoa duoc checkpoint"));
  });
}

function buildCheckpointPayload(reason = "autosave") {
  return {
    fileSignature: currentFileSignature,
    fileName: currentFileMeta?.name || "",
    fileSize: currentFileMeta?.size || 0,
    sheetName,
    rows,
    currentRowIndex,
    processedCount,
    successCount,
    errorCountValue,
    hasCompletedRun,
    currentRunMode,
    currentForwardColumns,
    lastRunMode,
    latColumnValue: latColumn.value,
    lngColumnValue: lngColumn.value,
    keywordColumnValue: keywordColumn.value,
    nearbyLatColumnValue: nearbyLatColumn.value,
    nearbyLngColumnValue: nearbyLngColumn.value,
    nearbyRadiusValue: nearbyRadius.value,
    delayMsValue: delayMs.value,
    logText: logEl.textContent,
    updatedAt: Date.now(),
    reason
  };
}

async function saveCheckpoint(reason = "autosave") {
  if (!currentFileSignature || !rows.length) return;
  const payload = buildCheckpointPayload(reason);
  await putCheckpoint(payload);
  updateCheckpointInfo(
    `Checkpoint: ${processedCount}/${rows.length} dong, cap nhat luc ${checkpointTimeFormatter.format(new Date(payload.updatedAt))}.`,
    true
  );
}

function applyCheckpointData(checkpoint) {
  rows = checkpoint.rows || [];
  sheetName = checkpoint.sheetName || sheetName;
  currentRowIndex = checkpoint.currentRowIndex || 0;
  processedCount = checkpoint.processedCount || 0;
  successCount = checkpoint.successCount || 0;
  errorCountValue = checkpoint.errorCountValue || 0;
  hasCompletedRun = Boolean(checkpoint.hasCompletedRun);
  currentRunMode = checkpoint.currentRunMode || null;
  currentForwardColumns = checkpoint.currentForwardColumns || [];
  lastRunMode = checkpoint.lastRunMode || currentRunMode;
  if (checkpoint.latColumnValue) latColumn.value = checkpoint.latColumnValue;
  if (checkpoint.lngColumnValue) lngColumn.value = checkpoint.lngColumnValue;
  if (checkpoint.keywordColumnValue) keywordColumn.value = checkpoint.keywordColumnValue;
  if (checkpoint.nearbyLatColumnValue) nearbyLatColumn.value = checkpoint.nearbyLatColumnValue;
  if (checkpoint.nearbyLngColumnValue) nearbyLngColumn.value = checkpoint.nearbyLngColumnValue;
  if (checkpoint.nearbyRadiusValue) nearbyRadius.value = checkpoint.nearbyRadiusValue;
  if (checkpoint.delayMsValue) delayMs.value = checkpoint.delayMsValue;
  if (checkpoint.currentRunMode) {
    const modeInput = document.querySelector(`input[name="mode"][value="${checkpoint.currentRunMode}"]`);
    if (modeInput) modeInput.checked = true;
    updateModeUI();
  }
  if (Array.isArray(checkpoint.currentForwardColumns) && checkpoint.currentForwardColumns.length) {
    [...columnsContainer.querySelectorAll("input[type=checkbox]")].forEach(input => {
      input.checked = checkpoint.currentForwardColumns.includes(input.value);
    });
  }
  totalRows.textContent = rows.length;
  fileInfo.textContent = `Đã khôi phục sheet "${sheetName}" — ${rows.length} dòng`;
  logEl.textContent = checkpoint.logText || "";
  refreshProgress();
  downloadBtn.disabled = processedCount === 0;
  runBtn.textContent = hasCompletedRun ? "Chạy lại" : (currentRowIndex > 0 ? "Tiếp tục" : "Bắt đầu xử lý");
  updateCheckpointInfo(
    `Da phuc hoi checkpoint: ${processedCount}/${rows.length} dong, luu luc ${checkpointTimeFormatter.format(new Date(checkpoint.updatedAt))}.`,
    true
  );
}

const FETCH_TIMEOUT_MS = 20000;

async function fetchJsonWithTimeout(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      headers: { accept: "application/json" },
      signal: controller.signal
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (e) {
      throw new Error(`JSON parse error: ${text.slice(0, 300)}`);
    }
    return { res, data };
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(`Request timeout sau ${FETCH_TIMEOUT_MS / 1000} giay`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/* ================= API ================= */
async function geocodeAddress(address, key) {
  const url = `https://api.map4d.vn/sdk/v2/geocode?address=${encodeURIComponent(address)}&key=${key}`;  const { res, data } = await fetchJsonWithTimeout(url);  return data?.result?.[0] || null;
}

async function reverseGeocode(lat, lng, key) {
  const url = `https://api.map4d.vn/sdk/v2/geocode?location=${lat},${lng}&key=${key}`;  const { res, data } = await fetchJsonWithTimeout(url);  return data?.result?.[0] || null;
}
async function nearbySearch(lat, lng, text, radius, key) {
  const url =
    `https://api.map4d.vn/sdk/place/nearby-search` +
    `?location=${lat},${lng}` +
    `&radius=${radius}` +
    `&text=${encodeURIComponent(text)}` +
    `&key=${encodeURIComponent(key)}`;
  const res = await fetch(url, {
    headers: { accept: "application/json" }
  });

  const data = await res.json();

  if (!res.ok || !data?.result?.length) {
    return { error: normalizeText("Khong co dia diem phu hop") };
  }

  const p = data.result[0];

  return {
    id: p.id || "",
    name: normalizeText(p.name || ""),
    address: normalizeText(p.address || ""),
    oldaddress: normalizeText(p.oldaddress || p.oldAddress || ""),
    lat: p.location?.lat ?? null,
    lng: p.location?.lng ?? null,
    distance: p.distance ?? null,
    error: null
  };
}

function outputField(mode, field) {
  return `${field}_${mode}`;
}

function ensureOutputFields(row, mode) {
  (MODE_OUTPUT_FIELDS[mode] || []).forEach(field => {
    const key = outputField(mode, field);
    if (!Object.prototype.hasOwnProperty.call(row, key)) row[key] = "";
  });
}

function setOutputValue(row, mode, field, value) {
  const key = outputField(mode, field);
  row[key] = value ?? "";
}

function getOutputValue(row, mode, field) {
  return row[outputField(mode, field)] ?? "";
}
/* ================= FILE ================= */
function loadSheetData(idx) {
  sheetName = workbook.SheetNames[idx];
  rows = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], { defval: "" });

  fileInfo.textContent = `Đã tải sheet "${sheetName}" — ${rows.length} dòng`;
  totalRows.textContent = rows.length;
  processedCount = 0;
  successCount = 0;
  errorCountValue = 0;
  currentRowIndex = 0;
  hasCompletedRun = false;
  refreshProgress();

  const cols = Object.keys(rows[0] || {});
  columnsContainer.innerHTML = cols.map(c => `<label><input type="checkbox" value="${c}"> ${c}</label>`).join("");
  latColumn.innerHTML = lngColumn.innerHTML =
  keywordColumn.innerHTML = nearbyLatColumn.innerHTML = nearbyLngColumn.innerHTML =
    cols.map(c => `<option>${c}</option>`).join("");

  updateModeUI();
  runCard.classList.remove("hidden");
  logCard.classList.remove("hidden");
  if(actionSectionLabel) actionSectionLabel.classList.remove("hidden");
  setMapState("Sẵn sàng xử lý", false);
}

fileInput.onchange = e => {
  const selectedFile = e.target.files[0];
  if (!selectedFile) return;
  currentFileMeta = selectedFile || null;
  currentFileSignature = buildFileSignature(selectedFile);
  const reader = new FileReader();
  reader.onload = async evt => {
    workbook = XLSX.read(evt.target.result, { type: "array" });
    
    if (workbook.SheetNames.length > 1) {
      if (sheetContainer) sheetContainer.classList.remove("hidden");
      if (sheetSelect) {
        sheetSelect.innerHTML = workbook.SheetNames.map((name, i) => `<option value="${i}">${name}</option>`).join("");
        sheetSelect.value = "0";
        sheetSelect.onchange = () => loadSheetData(parseInt(sheetSelect.value));
      }
    } else {
      if (sheetContainer) sheetContainer.classList.add("hidden");
    }

    loadSheetData(0);

    try {
      const checkpoint = await getCheckpoint(currentFileSignature);
      if (checkpoint && checkpoint.rows?.length) {
        const shouldRestore = confirm(
          normalizeText(
            `Tim thay checkpoint cho file "${selectedFile.name}".\n` +
            `Da xu ly ${checkpoint.processedCount || 0}/${checkpoint.rows.length} dong.\n\n` +
            `Ban co muon phuc hoi de tiep tuc khong?`
          )
        );
        if (shouldRestore) {
          if (sheetSelect && checkpoint.sheetName) {
            const sheetIdx = workbook.SheetNames.indexOf(checkpoint.sheetName);
            if (sheetIdx > -1) sheetSelect.value = sheetIdx.toString();
          }
          applyCheckpointData(checkpoint);
        } else {
          updateCheckpointInfo(
            `Da bo qua checkpoint cu. File moi gom ${rows.length} dong.`,
            true
          );
        }
      } else {
        updateCheckpointInfo("Chua co checkpoint cho file nay.", false);
      }
    } catch (error) {
      updateCheckpointInfo(`Khong doc duoc checkpoint: ${error.message}`, false);
    }
  };
  reader.readAsArrayBuffer(selectedFile);
};

/* ================= MODE ================= */
function updateModeUI() {
  forwardCard.classList.add("hidden");
  reverseCard.classList.add("hidden");
  nearbyCard.classList.add("hidden");

  const m = document.querySelector("input[name=mode]:checked").value;
  if (m === "forward") forwardCard.classList.remove("hidden");
  if (m === "reverse") reverseCard.classList.remove("hidden");
  if (m === "nearby") nearbyCard.classList.remove("hidden");
}
document.querySelectorAll("input[name=mode]").forEach(r => r.onchange = updateModeUI);

function refreshProgress() {
  processedRows.textContent = processedCount;
  successRows.textContent = successCount;
  errorRows.textContent = errorCountValue;
  const total = Number(totalRows.textContent || rows.length || 0) || 0;
  const pct = total > 0 ? Math.min(100, Math.round((processedCount / total) * 100)) : 0;
  if (progressText) progressText.textContent = `${pct}%`;
  if (progressFill) progressFill.style.width = `${pct}%`;
}

function getRowsForExport() {
  return hasCompletedRun ? rows : rows.slice(0, processedCount);
}

async function processRowAtIndex(i, key, mode) {
  const row = rows[i];
  let rowSucceeded = false;

  try {
    let r = null;

    if (mode === "forward") {
      const addr = currentForwardColumns.map(c => row[c]).filter(Boolean).join(", ");
      log(`Row ${i + 1}: ${addr}`);

      r = await geocodeAddress(addr, key);
      if (!r) throw new Error("No result");
      setOutputValue(row, mode, "id", r.id || "");
      setOutputValue(row, mode, "name", r.name || "");
      setOutputValue(row, mode, "address", r.address || r.formatted_address || "");
      setOutputValue(row, mode, "oldaddress", r.oldaddress || r.oldAddress || "");
      setOutputValue(row, mode, "lat", r.location.lat);
      setOutputValue(row, mode, "lng", r.location.lng);
      setOutputValue(row, mode, "status", "OK");
      setOutputValue(row, mode, "error", "");

      log(`Row ${i + 1}: ${getOutputValue(row, mode, "name")} - ${getOutputValue(row, mode, "address")}`);
      rowSucceeded = true;
    }

    if (mode === "nearby") {
      const lat = toNumber(row[nearbyLatColumn.value]);
      const lng = toNumber(row[nearbyLngColumn.value]);
      const keyword = row[keywordColumn.value];
      const radius = +nearbyRadius.value;

      r = await nearbySearch(lat, lng, keyword, radius, key);

      if (r.error) {
        setOutputValue(row, mode, "status", "ERROR");
        setOutputValue(row, mode, "error", r.error);
        log(`Row ${i + 1}: ${keyword || "Khong co ket qua"} - ${r.error}`, "warn");
      } else {
        setOutputValue(row, mode, "id", r.id || "");
        setOutputValue(row, mode, "name", r.name || "");
        setOutputValue(row, mode, "address", r.address || "");
        setOutputValue(row, mode, "oldaddress", r.oldaddress || r.oldAddress || "");
        setOutputValue(row, mode, "place_id", r.id || "");
        setOutputValue(row, mode, "place_name", r.name || "");
        setOutputValue(row, mode, "place_address", r.address || "");
        setOutputValue(row, mode, "lat", r.lat);
        setOutputValue(row, mode, "lng", r.lng);
        setOutputValue(row, mode, "distance", r.distance ?? "");
        setOutputValue(row, mode, "status", "OK");
        setOutputValue(row, mode, "error", "");

        log(`Row ${i + 1}: ${getOutputValue(row, mode, "place_name")} - ${getOutputValue(row, mode, "place_address")}`);
        rowSucceeded = true;
      }
    }

    if (mode === "reverse") {
      const lat = toNumber(row[latColumn.value]);
      const lng = toNumber(row[lngColumn.value]);

      r = await reverseGeocode(lat, lng, key);
      if (!r) throw new Error("No result");

      const address =
        r.formatted_address ||
        r.address ||
        r.name ||
        "(Khong co dia chi)";

      setOutputValue(row, mode, "id", r.id || "");
      setOutputValue(row, mode, "name", r.name || r.place_name || "");
      setOutputValue(row, mode, "address", address);
      setOutputValue(row, mode, "oldaddress", r.oldaddress || r.oldAddress || "");
      setOutputValue(row, mode, "lat", r.location.lat);
      setOutputValue(row, mode, "lng", r.location.lng);
      setOutputValue(row, mode, "status", "OK");
      setOutputValue(row, mode, "error", "");

      log(`Row ${i + 1}: ${getOutputValue(row, mode, "name")} - ${getOutputValue(row, mode, "address")}`);
      rowSucceeded = true;
    }
  } catch (e) {
    setOutputValue(row, mode, "status", "ERROR");
    setOutputValue(row, mode, "error", e.message || "Loi khong xac dinh");
    log(`Row ${i + 1}: ${row.name || row.address || "Loi"} - ${e.message || "Loi khong xac dinh"}`, "error");
  }

  return { success: rowSucceeded };
}

clearCheckpointBtn.onclick = async () => {
  if (!currentFileSignature) return;
  try {
    await deleteCheckpoint(currentFileSignature);
    updateCheckpointInfo("Da xoa checkpoint cua file hien tai.", false);
  } catch (error) {
    updateCheckpointInfo(`Khong xoa duoc checkpoint: ${error.message}`, true);
  }
};

/* ================= RUN ================= */
runBtn.onclick = async () => {
  const key = resolveApiKey(apiKey.value);
  if (!key) return alert("Nhap API key");

  const mode = document.querySelector("input[name=mode]:checked").value;
  const fcols = [...columnsContainer.querySelectorAll("input:checked")].map(e => e.value);
  if (mode === "forward" && !fcols.length) {
    return alert("Chọn ít nhất 1 cột địa chỉ");
  }

  if (isRunning) return;

  if (hasCompletedRun || currentRowIndex >= rows.length || currentRunMode !== mode) {
    currentRowIndex = 0;
    processedCount = 0;
    successCount = 0;
    errorCountValue = 0;
    hasCompletedRun = false;
    logEl.textContent = "";
    clearMarkers();
    clearPoiOverlay();
  }

  isRunning = true;
  isPaused = false;
  currentRunMode = mode;
  currentForwardColumns = fcols;
  lastRunMode = mode;
  runBtn.disabled = true;
  runBtn.textContent = currentRowIndex === 0 ? "Đang chạy..." : "Tiếp tục";
  pauseBtn.disabled = false;
  pauseBtn.textContent = "Tạm dừng";
  downloadBtn.disabled = processedCount === 0;

  rows.forEach(row => ensureOutputFields(row, mode));

  const delay = +delayMs.value;
  for (let i = currentRowIndex; i < rows.length; i += REQUEST_CONCURRENCY) {
    if (isPaused) {
      currentRowIndex = i;
      isRunning = false;
      runBtn.disabled = false;
      runBtn.textContent = "Tiếp tục";
      pauseBtn.disabled = false;
      pauseBtn.textContent = "Tiếp tục";
      downloadBtn.disabled = processedCount === 0;
      log("⏸️ Đã tạm dừng. Bạn có thể tải kết quả tạm thời.");
      try { await saveCheckpoint("paused"); } catch (error) { log(`Checkpoint loi: ${error.message}`, "warn"); }
      return;
    }

    const batchIndexes = [];
    for (let offset = 0; offset < REQUEST_CONCURRENCY && i + offset < rows.length; offset++) {
      batchIndexes.push(i + offset);
    }

    const batchResults = await Promise.all(batchIndexes.map(index => processRowAtIndex(index, key, mode)));

    batchResults.forEach(result => {
      if (result.success) successCount++;
      else errorCountValue++;
      processedCount++;
    });

    currentRowIndex = Math.min(i + REQUEST_CONCURRENCY, rows.length);
    refreshProgress();
    downloadBtn.disabled = false;

    if (processedCount % CHECKPOINT_EVERY_ROWS === 0 || currentRowIndex >= rows.length) {
      try { await saveCheckpoint("autosave"); } catch (error) { log(`Checkpoint loi: ${error.message}`, "warn"); }
    }

    if (delay && currentRowIndex < rows.length) {
      await sleep(delay);
    }
  }

  isRunning = false;
  isPaused = false;
  currentRowIndex = rows.length;
  hasCompletedRun = true;
  runBtn.disabled = false;
  runBtn.textContent = "Chạy lại";
  pauseBtn.disabled = true;
  pauseBtn.textContent = "Tạm dừng";

  downloadBtn.disabled = false;
  try { await saveCheckpoint("completed"); } catch (error) { log(`Checkpoint loi: ${error.message}`, "warn"); }

  log("================ HOAN TAT ================");
  log(`Tong dong: ${rows.length}`);
  log(`Da xu ly: ${processedCount}`);
  log(`Thanh cong: ${successCount}`);
  log(`Loi: ${errorCountValue}`);
  log("==========================================");
  console.log("================ HOAN TAT ================");
  console.log(`Tong dong: ${rows.length}`);
  console.log(`Da xu ly: ${processedCount}`);
  console.log(`Thanh cong: ${successCount}`);
  console.log(`Loi: ${errorCountValue}`);
  console.log("==========================================");
};

pauseBtn.onclick = async () => {
  if (isRunning) {
    isPaused = true;
    pauseBtn.disabled = true;
    pauseBtn.textContent = "Đang tạm dừng...";
    return;
  }

  if (processedCount > 0 && currentRowIndex < rows.length) {
    await runBtn.onclick();
  }
};

window.addEventListener("beforeunload", event => {
  if (!isRunning || !currentFileSignature || !rows.length) return;
  event.preventDefault();
  event.returnValue = "";
});

/* ================= DRAW MARKER ================= */
drawBtn.onclick = async () => {
  const key = resolveApiKey(apiKey.value);
  if (!key) return;
  await ensureMapReady(key);

  clearMarkers();
  clearPoiOverlay();

  let markerCount = 0;
  let poiCount = 0;

  const poiData = [];
  const markersArr = [];

  const drawMode = lastRunMode || currentRunMode || document.querySelector("input[name=mode]:checked").value;

  rows.forEach((r, i) => {
    const lat = toNumber(getOutputValue(r, drawMode, "lat"));
    const lng = toNumber(getOutputValue(r, drawMode, "lng"));
    if (lat == null || lng == null) return;

    const nearbyPlaceName = getOutputValue(r, drawMode, "place_name");
    const nearbyPlaceAddress = getOutputValue(r, drawMode, "place_address");
    const outputName = getOutputValue(r, drawMode, "name");
    const outputAddress = getOutputValue(r, drawMode, "address");

    if (drawMode === "nearby" && nearbyPlaceName) {
      const m = createMarkerObject(lat, lng, nearbyPlaceName, nearbyPlaceAddress || "");
      markersArr.push(m);
      poiCount++;
    } else {
      const title = outputName || r.name || `Row ${i + 1}`;
      const m = createMarkerObject(lat, lng, title, outputAddress || "");
      markersArr.push(m);
      markerCount++;
    }
  });

  if (poiData.length) {
    poiOverlay = new map4d.PoiOverlay({ map, data: poiData });
  }

  // If MarkerClusterer exists, use it; otherwise add markers to the map individually
  if (markersArr.length) {
    try {
      // Disable clustering for now (SDK clusterIcon format issues)
      // Just add markers individually instead
      markersArr.forEach(m => { try { m.setMap(map); } catch (e) {} });
      markers = markersArr.slice();
    } catch (e) {
      console.warn('setMap failed', e);
    }
  }

  fitMap();

  log(`🗺️ Marker: ${markerCount} | POI: ${poiCount}`);
};


/* ================= EXPORT ================= */
downloadBtn.onclick = () => {
  const exportRows = getRowsForExport();
  if (!exportRows.length) return;
  const ws = XLSX.utils.json_to_sheet(exportRows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Result");
  XLSX.writeFile(wb, hasCompletedRun ? "result.xlsx" : `result_partial_${exportRows.length}_rows.xlsx`);
};
