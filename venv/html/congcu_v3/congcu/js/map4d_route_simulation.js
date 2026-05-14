/* ================= KEY ALIAS - GIỐNG geocode_map4d.js ================= */
const MAP4D_KEY_ALIAS = {
  dev: "93d393d0f6507ee00b62fe01db7430fa",
  pro: "93d393d0f6507ee00b62fe01db7430fa",
  trung: "93d393d0f6507ee00b62fe01db7430fa",
  test: "PUT_TEST_KEY_HERE"
};

const normalizeKeyInput = s => (s || "").trim().toLowerCase().replace(/\s+/g, "");
const resolveApiKey = input => MAP4D_KEY_ALIAS[normalizeKeyInput(input)] || (input || "").trim();

const MAP4D_SDK_VERSION = "3.0"; // Nếu dự án đang dùng 2.6 thì đổi thành "2.6"
const MAP4D_MAP_ID = "";         // Có mapId thì điền, không có để rỗng
const DEFAULT_AUTOSUGGEST_LOCATION = "10.776889,106.700806";

function getApiKeyValue() {
  return resolveApiKey($("apiKey")?.value || "");
}

function requireApiKey(showAlert = true) {
  const key = getApiKeyValue();
  if (!key || key === "PUT_TEST_KEY_HERE") {
    const message = "Nhập API key hoặc alias hợp lệ trước khi sử dụng AutoSuggest/Route API.";
    logStatus(message, "error");
    if (showAlert) alert(message);
    return "";
  }
  return key;
}

function buildAutoSuggestUrl(text, key = getApiKeyValue()) {
  const params = new URLSearchParams({ key, text, location: getPriorityLocationText(), acronym: "false" });
  return `https://api.map4d.vn/sdk/autosuggest?${params.toString()}`;
}
function buildPlaceDetailUrl(placeId, key = getApiKeyValue()) {
  return `https://api.map4d.vn/sdk/place/detail/${encodeURIComponent(placeId)}?key=${encodeURIComponent(key)}`;
}
function buildRouteUrl(origin, destination, key = getApiKeyValue()) {
  const params = new URLSearchParams({
    key,
    origin: formatLatLng(origin),
    destination: formatLatLng(destination),
    mode: $("modeInput")?.value || "car",
    language: "vi"
  });
  return `https://api.map4d.vn/sdk/route?${params.toString()}`;
}

    let map, projection;
    let mapSdkPromise = null;
    let routePath = [], routeLine = null, originMarker = null, destinationMarker = null, carMarker = null;
    let segments = [], totalDistance = 0, animationId = null, startTime = null, paused = false, pausedAt = 0, totalPausedTime = 0, lastDistanceTravelled = 0;
    let overlayCenter = { lat: 10.776889, lng: 106.700806 }, overlayZoom = 14, mapListenersAttached = false, overlayRefreshScheduled = false, mapClickAttached = false;
    const selectedPoints = {
      origin: { label: "10.776889,106.700806", location: { lat: 10.776889, lng: 106.700806 }, source: "manual" },
      destination: { label: "10.762622,106.660172", location: { lat: 10.762622, lng: 106.660172 }, source: "manual" }
    };
    const suggestState = { origin: { timer: null, controller: null }, destination: { timer: null, controller: null } };

    const $ = id => document.getElementById(id);
    const routeOverlay = () => $("routeOverlay"), routeSvgPath = () => $("routeSvgPath"), routeShadow = () => $("routeShadow"), domPointA = () => $("domPointA"), domPointB = () => $("domPointB"), domCar = () => $("domCar"), mapPanel = () => $("mapPanel");

    function logStatus(message, type = "info") { $("status").textContent = (type === "error" ? "❌ " : type === "success" ? "✅ " : "ℹ️ ") + message; }
    function setStateText(text) { $("stateText").textContent = text; }
    function formatLatLng(p) { return `${Number(p.lat).toFixed(6)},${Number(p.lng).toFixed(6)}`; }
    function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch])); }

    function initializeRouteSimulationPage() {
      setupAutoSuggestInput("origin");
      setupAutoSuggestInput("destination");
      setupVehicleControls();
      syncPointFromInput("origin", false);
      syncPointFromInput("destination", false);

      const apiInput = $("apiKey");
      if (apiInput) {
        apiInput.addEventListener("keydown", event => {
          if (event.key === "Enter") loadMapFromApiKey();
        });
      }

      logStatus("Nhập API key hoặc alias giống Geocode Studio, sau đó gõ Điểm A/B để AutoSuggest hoặc bấm Tìm đường & mô phỏng.");
    }

    async function loadMapFromApiKey() {
      const key = requireApiKey(true);
      if (!key) return;
      try {
        await ensureMapReady(key);
        logStatus("Map4D SDK đã sẵn sàng. Bạn có thể gõ địa điểm A/B để AutoSuggest, chọn POI rồi bấm 'Tìm đường & mô phỏng'.", "success");
      } catch (error) {
        mapSdkPromise = null;
        console.error(error);
        logStatus(error.message || "Không tải được Map4D SDK. Kiểm tra API key, domain whitelist hoặc mạng.", "error");
      }
    }

    function ensureMapSdkLoaded(key) {
      if (window.map4d) return Promise.resolve();
      if (mapSdkPromise) return mapSdkPromise;

      mapSdkPromise = new Promise((resolve, reject) => {
        const cb = "__route_map4d_cb_" + Math.random().toString(16).slice(2);
        window[cb] = () => {
          delete window[cb];
          resolve();
        };

        const sdkUrl = new URL("https://api.map4d.vn/sdk/map/js");
        sdkUrl.searchParams.set("version", MAP4D_SDK_VERSION);
        sdkUrl.searchParams.set("key", key);
        sdkUrl.searchParams.set("callback", cb);
        if (MAP4D_MAP_ID) sdkUrl.searchParams.set("mapId", MAP4D_MAP_ID);

        const script = document.createElement("script");
        script.src = sdkUrl.toString();
        script.async = true;
        script.defer = true;
        script.onerror = () => {
          delete window[cb];
          reject(new Error("Không tải được Map4D SDK. Kiểm tra API key, domain whitelist hoặc mạng."));
        };
        document.head.appendChild(script);
      });

      return mapSdkPromise;
    }

    async function ensureMapReady(key) {
      await ensureMapSdkLoaded(key);
      if (!map) {
        map = new map4d.Map($("map"), { center: overlayCenter, zoom: overlayZoom, controls: true });
        projection = new map4d.Projection(map);
        attachMapListeners();
        attachMapClickPicker();
      }
      return map;
    }

    function setupAutoSuggestInput(kind) {
      const input = $(`${kind}Input`), list = $(`${kind}Suggestions`);
      input.addEventListener("input", () => {
        const value = input.value.trim();
        selectedPoints[kind] = null;
        updateCoordChip(kind, null);
        if (syncPointFromInput(kind, true)) { hideSuggestions(kind); return; }
        clearTimeout(suggestState[kind].timer);
        if (value.length < 2) { hideSuggestions(kind); return; }
        suggestState[kind].timer = setTimeout(() => fetchSuggestions(kind, value), 330);
      });
      input.addEventListener("focus", () => { const value = input.value.trim(); if (value.length >= 2 && !parseLatLngLoose(value)) fetchSuggestions(kind, value); });
      input.addEventListener("keydown", (e) => { if (e.key === "Escape") hideSuggestions(kind); });
      document.addEventListener("click", (e) => { if (!input.contains(e.target) && !list.contains(e.target)) hideSuggestions(kind); });
    }

    async function fetchSuggestions(kind, text) {
      const key = requireApiKey(false);
      if (!key) {
        renderSuggestions(kind, [], "Nhập API key hoặc alias trước khi tìm gợi ý.");
        return;
      }
      const state = suggestState[kind];
      if (state.controller) state.controller.abort();
      state.controller = new AbortController();
      renderSuggestions(kind, [], "Đang tìm gợi ý...");
      try {
        const res = await fetch(buildAutoSuggestUrl(text, key), { signal: state.controller.signal });
        if (!res.ok) throw new Error(`AutoSuggest HTTP ${res.status}`);
        const data = await res.json();
        const suggestions = normalizeSuggestions(data).slice(0, 8);
        renderSuggestions(kind, suggestions, suggestions.length ? "" : "Không tìm thấy gợi ý phù hợp.");
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error(err);
        renderSuggestions(kind, [], "Không gọi được AutoSuggest. Kiểm tra key/CORS/network.");
      }
    }

    function normalizeSuggestions(data) {
      const raw = Array.isArray(data?.result) ? data.result : Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
      return raw.map(item => {
        const location = normalizeLatLng(item?.location || item?.coordinate || item?.geometry?.location || item?.position);
        return { id: item?.id || item?.placeId || item?.place_id || "", name: item?.name || item?.title || item?.text || "Không có tên", address: item?.address || item?.description || item?.formattedAddress || "", types: item?.types || [], location, raw: item };
      }).filter(item => item.name || item.address || item.location);
    }

    function renderSuggestions(kind, suggestions, emptyMessage = "") {
      const list = $(`${kind}Suggestions`);
      if (emptyMessage && !suggestions.length) { list.innerHTML = `<div class="suggestion-empty">${escapeHtml(emptyMessage)}</div>`; list.classList.add("active"); return; }
      list.innerHTML = suggestions.map((item, idx) => {
        const coord = item.location ? formatLatLng(item.location) : (item.id ? `placeId: ${item.id}` : "Chưa có tọa độ");
        return `<button type="button" class="suggestion-item" data-kind="${kind}" data-index="${idx}"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.address || "")}</small><em>${escapeHtml(coord)}</em></button>`;
      }).join("");
      list.__suggestions = suggestions;
      list.classList.toggle("active", suggestions.length > 0);
      list.querySelectorAll(".suggestion-item").forEach(btn => btn.addEventListener("click", () => selectSuggestion(kind, suggestions[Number(btn.dataset.index)])));
    }
    function hideSuggestions(kind) { const list = $(`${kind}Suggestions`); list.classList.remove("active"); }

    async function selectSuggestion(kind, suggestion) {
      hideSuggestions(kind);
      let location = suggestion.location;
      if (!location && suggestion.id) {
        logStatus(`Đang gọi Place Detail để lấy tọa độ cho ${suggestion.name}...`);
        location = await fetchPlaceLocation(suggestion.id);
      }
      if (!location) { logStatus("POI này chưa có tọa độ trong AutoSuggest/Place Detail, không thể truyền vào Route API.", "error"); return; }
      selectedPoints[kind] = { label: suggestion.name, address: suggestion.address, location, id: suggestion.id, source: "autosuggest" };
      $(`${kind}Input`).value = suggestion.address ? `${suggestion.name} - ${suggestion.address}` : suggestion.name;
      updateCoordChip(kind, location, suggestion.name);
      showEndpointMarker(kind, location, suggestion.name);
      panToPoint(location);
      logStatus(`${kind === "origin" ? "Điểm A" : "Điểm B"} đã chọn POI: ${suggestion.name}\nTọa độ truyền vào Route API: ${formatLatLng(location)}`, "success");
    }

    async function fetchPlaceLocation(placeId) {
      const key = requireApiKey(true);
      if (!key) throw new Error("Thiếu API key để gọi Place Detail.");
      const res = await fetch(buildPlaceDetailUrl(placeId, key));
      if (!res.ok) throw new Error(`Place Detail HTTP ${res.status}`);
      const data = await res.json();
      return normalizeLatLng(data?.result?.location || data?.location);
    }

    function syncPointFromInput(kind, showMarker = false) {
      const input = $(`${kind}Input`);
      const point = parseLatLngLoose(input.value.trim());
      if (!point) return false;
      selectedPoints[kind] = { label: input.value.trim(), location: point, source: "manual" };
      updateCoordChip(kind, point);
      if (showMarker) showEndpointMarker(kind, point, kind === "origin" ? "Điểm A" : "Điểm B");
      return true;
    }

    function updateCoordChip(kind, point, label = "") {
      const chip = $(`${kind}Coord`), prefix = kind === "origin" ? "A" : "B";
      if (!point) { chip.textContent = `${prefix}: Chưa chọn tọa độ`; chip.classList.add("empty"); return; }
      chip.classList.remove("empty");
      chip.textContent = `${prefix}: ${formatLatLng(point)}${label ? " · " + label : ""}`;
    }

    function showEndpointMarker(kind, position, title = "") {
      if (!map || !position) return;
      if (kind === "origin") { safeRemove(originMarker); originMarker = createEndpointMarker("A", position, title || "Điểm A"); }
      else { safeRemove(destinationMarker); destinationMarker = createEndpointMarker("B", position, title || "Điểm B"); }
    }
    function createEndpointMarker(label, position, title) {
      let marker = null;
      try { marker = new map4d.Marker({ position, title, label, zIndex: 1000 }); marker.setMap(map); } catch (e) { console.warn("Không tạo được endpoint marker", e); }
      return marker;
    }
    function panToPoint(point) { try { if (map?.panTo) map.panTo(point, { duration: 450, animate: true }); else if (map?.moveCamera) map.moveCamera({ target: point }, { duration: 450, animate: true }); } catch {} setTimeout(scheduleOverlayRefresh, 450); }

    function getRouteEndpoint(kind) {
      if (selectedPoints[kind]?.location) return selectedPoints[kind].location;
      if (syncPointFromInput(kind, false) && selectedPoints[kind]?.location) return selectedPoints[kind].location;
      throw new Error(`${kind === "origin" ? "Điểm A" : "Điểm B"} chưa có tọa độ. Hãy chọn POI từ AutoSuggest hoặc nhập lat,lng.`);
    }

    async function findRouteAndDraw() {
      try {
        const key = requireApiKey(true);
        if (!key) return;
        await ensureMapReady(key);
        resetMapObjects(false); setStateText("Đang tìm đường"); logStatus("Đang gọi Map4D Route API...");
        const origin = getRouteEndpoint("origin"), destination = getRouteEndpoint("destination");
        const url = buildRouteUrl(origin, destination, key);
        console.log("Route URL:", url);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Route API trả về HTTP ${response.status}.`);
        const routeData = await response.json(); console.log("Map4D Route Response:", routeData);
        routePath = extractPathFromRouteResponse(routeData);
        if (!routePath || routePath.length < 2) { routePath = [origin, destination]; logStatus("Không tách được route từ response. Đang dùng đường thẳng demo A-B. Xem Console để chỉnh hàm extractPathFromRouteResponse().", "error"); }
        else logStatus(`Đã tìm được tuyến đường gồm ${routePath.length} điểm.\nOrigin=${formatLatLng(origin)}\nDestination=${formatLatLng(destination)}\nĐang vẽ line và chạy mô phỏng...`, "success");
        setViewportToFitPath(routePath); drawRoute(origin, destination, routePath); prepareSimulation(routePath); startSimulation();
      } catch (error) { console.error(error); logStatus(error.message, "error"); setStateText("Lỗi"); }
    }

    function extractPathFromRouteResponse(data) {
      const candidates = [];
      function normalizePoint(item) { return normalizeLatLng(item); }
      function tryCollectArray(arr) { const path = arr.map(normalizePoint).filter(Boolean); if (path.length >= 2 && isReasonablePath(path)) candidates.push(path); }
      function walk(obj, depth = 0) {
        if (!obj || depth > 12) return;
        if (Array.isArray(obj)) { tryCollectArray(obj); obj.forEach(item => walk(item, depth + 1)); return; }
        if (typeof obj === "object") {
          for (const [key, value] of Object.entries(obj)) {
            const k = key.toLowerCase();
            if (typeof value === "string" && (k.includes("polyline") || k.includes("geometry") || k.includes("encoded") || k === "points")) {
              const decoded = decodePolyline(value); if (decoded.length >= 2 && isReasonablePath(decoded)) candidates.push(decoded);
            }
            walk(value, depth + 1);
          }
        }
      }
      walk(data); if (!candidates.length) return [];
      candidates.sort((a, b) => (b.length * 100000 + calculatePathDistance(b)) - (a.length * 100000 + calculatePathDistance(a)));
      return simplifyDuplicatePoints(candidates[0]);
    }

    function parseLatLngLoose(value) {
      const m = String(value || "").trim().match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (!m) return null;
      const point = { lat: Number(m[1]), lng: Number(m[2]) };
      return isValidLatLng(point) ? point : null;
    }
    function normalizeLatLng(item) {
      if (!item) return null;
      if (Array.isArray(item) && item.length >= 2) {
        const a = Number(item[0]), b = Number(item[1]);
        if (Number.isFinite(a) && Number.isFinite(b)) {
          if (Math.abs(a) > 90 && Math.abs(b) <= 90) return { lat: b, lng: a };
          if (Math.abs(b) > 90 && Math.abs(a) <= 90) return { lat: a, lng: b };
          return isValidLatLng({ lat: a, lng: b }) ? { lat: a, lng: b } : null;
        }
      }
      if (typeof item === "object") {
        const lat = item.lat ?? item.latitude ?? item.y;
        const lng = item.lng ?? item.lon ?? item.long ?? item.longitude ?? item.x;
        if (lat !== undefined && lng !== undefined) { const p = { lat: Number(lat), lng: Number(lng) }; if (isValidLatLng(p)) return p; }
        if (item.location) return normalizeLatLng(item.location);
      }
      return null;
    }
    function isValidLatLng(p) { return !!p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && p.lat >= -90 && p.lat <= 90 && p.lng >= -180 && p.lng <= 180; }
    function isReasonablePath(path) { if (!path.every(isValidLatLng)) return false; const d = calculatePathDistance(path); return d > 5 && d < 2000000; }
    function decodePolyline(encoded) {
      try { let index = 0, lat = 0, lng = 0; const coords = [];
        while (index < encoded.length) { let b, shift = 0, result = 0; do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20); lat += (result & 1) ? ~(result >> 1) : (result >> 1); shift = 0; result = 0; do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20); lng += (result & 1) ? ~(result >> 1) : (result >> 1); const p = { lat: lat / 1e5, lng: lng / 1e5 }; if (isValidLatLng(p)) coords.push(p); }
        return coords;
      } catch { return []; }
    }
    function simplifyDuplicatePoints(path) { const out = []; for (const p of path) { const last = out[out.length - 1]; if (!last || Math.abs(last.lat - p.lat) > 1e-8 || Math.abs(last.lng - p.lng) > 1e-8) out.push(p); } return out; }

    function drawRoute(origin, destination, path) { drawSdkObjects(origin, destination, path); drawDomOverlay(path, path[0], 0); }
    function drawSdkObjects(origin, destination, path) {
      try { safeRemove(originMarker); originMarker = new map4d.Marker({ position: origin, title: "Điểm A", label: "A", zIndex: 1000 }); originMarker.setMap(map); } catch (e) { console.warn("Không tạo được marker A", e); }
      try { safeRemove(destinationMarker); destinationMarker = new map4d.Marker({ position: destination, title: "Điểm B", label: "B", zIndex: 1000 }); destinationMarker.setMap(map); } catch (e) { console.warn("Không tạo được marker B", e); }
      try { routeLine = new map4d.Polyline({ path, strokeWidth: 9, strokeColor: "#0EA5E9", strokeOpacity: 1, zIndex: 999, userInteractionEnabled: false }); routeLine.setMap(map); }
      catch (e1) { console.warn("Polyline {lat,lng} lỗi, thử [lng,lat]", e1); try { routeLine = new map4d.Polyline({ path: path.map(p => [p.lng, p.lat]), strokeWidth: 9, strokeColor: "#0EA5E9", strokeOpacity: 1, zIndex: 999, userInteractionEnabled: false }); routeLine.setMap(map); } catch (e2) { console.warn("Không tạo được Polyline SDK. Dùng overlay.", e2); } }
      createOrRefreshVehicleMarker(path[0], 0);
    }
    function setupVehicleControls() {
      const styleInput = $("vehicleStyleInput"), modeInput = $("modeInput");
      if (styleInput) styleInput.addEventListener("change", () => refreshVehicleAppearance());
      if (modeInput) modeInput.addEventListener("change", () => { if (styleInput?.value === "auto") refreshVehicleAppearance(); });
      refreshVehicleAppearance();
    }
    function getEffectiveVehicleStyle() {
      const chosen = $("vehicleStyleInput")?.value || "auto";
      if (chosen !== "auto") return chosen;
      const mode = $("modeInput")?.value || "car";
      if (mode === "motorcycle") return "moto_blue";
      if (mode === "bike") return "bike_green";
      if (mode === "foot") return "walk_purple";
      return "car_blue";
    }
    function getVehicleLabel(style) {
      return ({moto_blue:"Moto xanh",moto_red:"Moto đỏ",scooter_dark:"Scooter đen",delivery_orange:"Xe giao hàng",car_blue:"Ô tô xanh",bike_green:"Xe đạp",walk_purple:"Người đi bộ"})[style] || "Phương tiện";
    }
    function createVehicleSvg(style) {
      const s = String(style || "car_blue");
      const defs = '<filter id="vShadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="rgba(15,23,42,.28)"/></filter>';
      const wrap = (body) => `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs>${defs}</defs>${body}</svg>`;
      const badge = (fill) => `<circle cx="32" cy="32" r="25" fill="white" opacity=".98" filter="url(#vShadow)"/><circle cx="32" cy="32" r="23" fill="${fill}"/>`;
      if (s === "moto_blue") return wrap(`${badge('#0ea5e9')}<g transform="translate(8 14)"><circle cx="14" cy="28" r="6.4" fill="#1f2937"/><circle cx="38" cy="28" r="6.4" fill="#1f2937"/><path d="M18 14h10l6 6h4c3.5 0 6 2.4 6 5.6V28h-3.8c0-3.2-2.3-5.8-5.4-5.8S29.4 24.8 29.4 28H22.6c0-3.2-2.3-5.8-5.4-5.8S11.8 24.8 11.8 28H8v-1.2c0-4.4 3.3-8 7.6-8h4.2l3-4.8h5.6" fill="none" stroke="#fff" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M26 9l-3.2 5.2" stroke="#fff" stroke-width="2.7" stroke-linecap="round"/></g>`);
      if (s === "moto_red") return wrap(`${badge('#ef4444')}<g transform="translate(8 14)"><circle cx="14" cy="28" r="6.4" fill="#1f2937"/><circle cx="38" cy="28" r="6.4" fill="#1f2937"/><path d="M18 14h10l6 6h4c3.5 0 6 2.4 6 5.6V28h-3.8c0-3.2-2.3-5.8-5.4-5.8S29.4 24.8 29.4 28H22.6c0-3.2-2.3-5.8-5.4-5.8S11.8 24.8 11.8 28H8v-1.2c0-4.4 3.3-8 7.6-8h4.2l3-4.8h5.6" fill="none" stroke="#fff" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M26 9l-3.2 5.2" stroke="#fff" stroke-width="2.7" stroke-linecap="round"/></g>`);
      if (s === "scooter_dark") return wrap(`${badge('#334155')}<g transform="translate(10 15)"><circle cx="11" cy="27" r="6" fill="#111827"/><circle cx="34" cy="27" r="6" fill="#111827"/><path d="M13 14h11l4 4h6c3.3 0 6 2.6 6 5.9V27h-3.6c0-3-2.1-5.5-5-5.5-2.8 0-5 2.5-5 5.5H18c0-3-2.2-5.5-5-5.5-2.9 0-5 2.5-5 5.5H6v-1.1c0-4.1 3.2-7.9 7-7.9z" fill="#fff" opacity=".98"/><path d="M19 10h6" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/></g>`);
      if (s === "delivery_orange") return wrap(`${badge('#f97316')}<g transform="translate(9 16)"><rect x="10" y="10" width="16" height="13" rx="4" fill="#fff"/><rect x="25" y="12" width="11" height="11" rx="2" fill="#fff" opacity=".95"/><circle cx="14" cy="28" r="5.8" fill="#1f2937"/><circle cx="33" cy="28" r="5.8" fill="#1f2937"/><path d="M6 24h4m26 0h4" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><path d="M29 12l5 6" stroke="#f97316" stroke-width="2.4" stroke-linecap="round"/></g>`);
      if (s === "bike_green") return wrap(`${badge('#22c55e')}<g transform="translate(8 15)"><circle cx="12" cy="27" r="6.2" fill="#1f2937"/><circle cx="36" cy="27" r="6.2" fill="#1f2937"/><path d="M12 27l10-12 5 12m-5-12h7l2.2 4.2M22 15l-6 0m8 12h6" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>`);
      if (s === "walk_purple") return wrap(`${badge('#8b5cf6')}<g transform="translate(14 10)" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="8" r="4.8" fill="#fff" stroke="none"/><path d="M18 14v8l-5 7m5-7 7 4 4 10m-11-14-7 6-4 10m11-16 8-4"/></g>`);
      return wrap(`${badge('#2563eb')}<g transform="translate(9 16)"><path d="M8 14c0-3.3 2.7-6 6-6h13c4.4 0 8 3.6 8 8v8H8z" fill="#fff"/><path d="M11 11h9" stroke="#2563eb" stroke-width="2.4" stroke-linecap="round"/><circle cx="14" cy="30" r="6.2" fill="#1f2937"/><circle cx="34" cy="30" r="6.2" fill="#1f2937"/></g>`);
    }
    function createVehicleIconNode(style) {
      const node = document.createElement("div");
      node.className = "vehicle-icon";
      node.innerHTML = createVehicleSvg(style);
      return node;
    }
    function createOrRefreshVehicleMarker(position, rotation = 0) {
      // FIX: Một số version Map4D Web SDK render HTMLElement thành text "[object HTMLElement]"
      // khi truyền trực tiếp vào marker. Vì vậy xe sẽ dùng DOM overlay để tránh lỗi label.
      safeRemove(carMarker);
      carMarker = null;
      refreshVehicleAppearance(position, rotation, false);
    }
    function refreshVehicleAppearance(position = null, rotation = null, recreateMarker = true) {
      const style = getEffectiveVehicleStyle();
      const el = domCar();
      if (el) el.innerHTML = createVehicleSvg(style);
      const current = position ? {position, rotation: rotation ?? 0} : getPositionAtDistance(lastDistanceTravelled);
      if (recreateMarker && map && (routePath.length || current?.position)) createOrRefreshVehicleMarker(current?.position || routePath[0], current?.rotation || 0);
    }

    function setViewportToFitPath(path) {
      const viewport = calculateFitViewport(path, 80); overlayCenter = viewport.center; overlayZoom = viewport.zoom;
      try { const bounds = new map4d.LatLngBounds(); path.forEach(p => bounds.extend(p)); if (map.fitBounds) map.fitBounds(bounds, { top: 80, right: 80, bottom: 80, left: 80 }, { duration: 500, animate: true }); else if (map.moveCamera) map.moveCamera({ target: overlayCenter, zoom: overlayZoom }, { duration: 500, animate: true }); }
      catch (e) { console.warn("fitBounds lỗi, fallback moveCamera", e); try { if (map.moveCamera) map.moveCamera({ target: overlayCenter, zoom: overlayZoom }, { duration: 500, animate: true }); } catch {} }
      setTimeout(scheduleOverlayRefresh, 80); setTimeout(scheduleOverlayRefresh, 520);
    }
    function safeRemove(obj) { if (!obj) return; try { if (obj.setMap) obj.setMap(null); else if (obj.remove) obj.remove(); } catch (e) { console.warn("Không xóa được object", e); } }
    function resetMapObjects(clearLog = true) { pauseSimulation(); safeRemove(routeLine); safeRemove(originMarker); safeRemove(destinationMarker); safeRemove(carMarker); routeLine = originMarker = destinationMarker = carMarker = null; routePath = []; segments = []; totalDistance = 0; startTime = null; paused = false; pausedAt = 0; totalPausedTime = 0; lastDistanceTravelled = 0; clearDomOverlay(); updateStats(0, 0); setStateText("Chưa chạy"); if (clearLog) logStatus("Đã xóa tuyến và reset mô phỏng. Điểm A/B đã chọn vẫn được giữ nguyên."); }

    function drawDomOverlay(path, carPosition = null, rotation = 0) {
      if (!path || path.length < 2) { clearDomOverlay(); return; }
      const panel = mapPanel(), width = panel.clientWidth, height = panel.clientHeight; routeOverlay().setAttribute("viewBox", `0 0 ${width} ${height}`); routeOverlay().classList.add("active");
      const points = path.map(projectPointToMapScreen); const d = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" "); routeSvgPath().setAttribute("d", d); routeShadow().setAttribute("d", d);
      positionDomPoint(domPointA(), path[0]); positionDomPoint(domPointB(), path[path.length - 1]); if (carPosition) updateDomCar(carPosition, rotation);
    }
    function positionDomPoint(el, position) { const p = projectPointToMapScreen(position); el.style.display = "flex"; el.style.left = `${p.x}px`; el.style.top = `${p.y}px`; }
    function updateDomCar(position, rotation) { const p = projectPointToMapScreen(position); const el = domCar(); el.style.display = "block"; el.style.left = `${p.x - 32}px`; el.style.top = `${p.y - 32}px`; el.style.transform = `rotate(${rotation}deg)`; }
    function projectPointToMapScreen(latLng) {
      try { if (!projection && map) projection = new map4d.Projection(map); const point = projection.fromLatLngToScreen(new map4d.LatLng(latLng.lat, latLng.lng)); return { x: point.x, y: point.y }; }
      catch { const panel = mapPanel(); return projectLatLngToScreen(latLng, overlayCenter, overlayZoom, panel.clientWidth, panel.clientHeight); }
    }
    function scheduleOverlayRefresh() { if (!routePath.length || overlayRefreshScheduled) return; overlayRefreshScheduled = true; requestAnimationFrame(() => { overlayRefreshScheduled = false; const current = getPositionAtDistance(lastDistanceTravelled); drawDomOverlay(routePath, current?.position || routePath[0], current?.rotation || 0); }); }
    function attachMapListeners() { if (!map || mapListenersAttached || !map.addListener) return; mapListenersAttached = true; const events = []; if (map4d.MapEvent) events.push(map4d.MapEvent.cameraChanging, map4d.MapEvent.idle, map4d.MapEvent.drag, map4d.MapEvent.dragEnd, map4d.MapEvent.boundsChanged); events.push("cameraChanging", "idle", "drag", "dragEnd", "boundsChanged"); [...new Set(events.filter(e => e !== undefined && e !== null))].forEach(e => { try { map.addListener(e, scheduleOverlayRefresh); } catch {} }); }
    function clearDomOverlay() { routeOverlay().classList.remove("active"); routeSvgPath().setAttribute("d", ""); routeShadow().setAttribute("d", ""); domPointA().style.display = "none"; domPointB().style.display = "none"; domCar().style.display = "none"; }

    function attachMapClickPicker() {
      if (!map || mapClickAttached || !map.addListener) return;
      mapClickAttached = true;
      const candidates = [];
      if (window.map4d?.MapEvent) candidates.push(map4d.MapEvent.click, map4d.MapEvent.clickLocation, map4d.MapEvent.mapClick, map4d.MapEvent.poiClick);
      candidates.push("click", "clickLocation", "mapClick", "poiClick");
      [...new Set(candidates.filter(Boolean))].forEach(evt => { try { map.addListener(evt, handleMapClickPick); } catch {} });
    }
    function handleMapClickPick(event) {
      const point = extractLatLngFromMapEvent(event);
      if (!point) return;
      const kind = $("pickTargetInput").value || "origin";
      selectedPoints[kind] = { label: "Tọa độ click trên map", location: point, source: "map-click" };
      $(`${kind}Input`).value = formatLatLng(point);
      updateCoordChip(kind, point, "click map/POI");
      showEndpointMarker(kind, point, kind === "origin" ? "Điểm A" : "Điểm B");
      logStatus(`${kind === "origin" ? "Điểm A" : "Điểm B"} đã lấy tọa độ từ click map/POI: ${formatLatLng(point)}`, "success");
    }
    function extractLatLngFromMapEvent(e) {
      const candidates = [e?.latLng, e?.location, e?.position, e?.coordinate, e?.data?.location, e?.poi?.location, e?.place?.location, e?.detail?.location, e];
      for (const c of candidates) { const p = normalizeLatLng(c); if (p) return p; }
      return null;
    }

    function getPriorityLocationText() {
      const center = getMapCenter() || overlayCenter || parseLatLngLoose(DEFAULT_AUTOSUGGEST_LOCATION);
      return center ? formatLatLng(center) : DEFAULT_AUTOSUGGEST_LOCATION;
    }
    function getMapCenter() {
      try { if (map?.getCenter) { const p = normalizeLatLng(map.getCenter()); if (p) return p; } } catch {}
      try { if (map?.getCamera) { const camera = map.getCamera(); const p = normalizeLatLng(camera?.target || camera?.center); if (p) return p; } } catch {}
      return null;
    }

    function calculateFitViewport(path, paddingPx = 60) { const panel = mapPanel(); const width = Math.max(320, panel.clientWidth || window.innerWidth - 410), height = Math.max(320, panel.clientHeight || window.innerHeight); const wps = path.map(latLngToWorld); const minX = Math.min(...wps.map(p => p.x)), maxX = Math.max(...wps.map(p => p.x)), minY = Math.min(...wps.map(p => p.y)), maxY = Math.max(...wps.map(p => p.y)); const center = worldToLatLng({ x: (minX + maxX) / 2, y: (minY + maxY) / 2 }); const dx = Math.max(maxX - minX, 1e-9), dy = Math.max(maxY - minY, 1e-9); const zoom = clamp(Math.floor(Math.min(Math.log2((width - paddingPx * 2) / (256 * dx)), Math.log2((height - paddingPx * 2) / (256 * dy)))), 10, 18); return { center, zoom }; }
    function projectLatLngToScreen(latLng, center, zoom, width, height) { const scale = 256 * Math.pow(2, zoom), world = latLngToWorld(latLng), c = latLngToWorld(center); return { x: (world.x - c.x) * scale + width / 2, y: (world.y - c.y) * scale + height / 2 }; }
    function latLngToWorld({ lat, lng }) { const sin = Math.sin(lat * Math.PI / 180), s = Math.min(Math.max(sin, -.9999), .9999); return { x: (lng + 180) / 360, y: .5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI) }; }
    function worldToLatLng({ x, y }) { const lng = x * 360 - 180, n = Math.PI - 2 * Math.PI * y, lat = 180 / Math.PI * Math.atan(.5 * (Math.exp(n) - Math.exp(-n))); return { lat, lng }; }
    function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
    window.addEventListener("resize", scheduleOverlayRefresh);

    function toRad(deg) { return deg * Math.PI / 180; } function toDeg(rad) { return rad * 180 / Math.PI; }
    function haversine(p1, p2) { const R = 6371000, dLat = toRad(p2.lat - p1.lat), dLng = toRad(p2.lng - p1.lng), lat1 = toRad(p1.lat), lat2 = toRad(p2.lat); const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2; return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)); }
    function calculatePathDistance(path) { let d = 0; for (let i = 0; i < path.length - 1; i++) d += haversine(path[i], path[i + 1]); return d; }
    function buildSegments(path) { const result = []; let cumulative = 0; for (let i = 0; i < path.length - 1; i++) { const from = path[i], to = path[i + 1], d = haversine(from, to); if (d > .2) { result.push({ from, to, distance: d, startDistance: cumulative, endDistance: cumulative + d }); cumulative += d; } } return { segments: result, totalDistance: cumulative }; }
    function interpolate(p1, p2, t) { return { lat: p1.lat + (p2.lat - p1.lat) * t, lng: p1.lng + (p2.lng - p1.lng) * t }; }
    function bearing(p1, p2) { const lat1 = toRad(p1.lat), lat2 = toRad(p2.lat), dLng = toRad(p2.lng - p1.lng); const y = Math.sin(dLng) * Math.cos(lat2), x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng); return (toDeg(Math.atan2(y, x)) + 360) % 360; }
    function getPositionAtDistance(distanceTravelled) { if (!segments.length) return null; const d = Math.min(distanceTravelled, totalDistance); for (const seg of segments) { if (d <= seg.endDistance) { const t = (d - seg.startDistance) / seg.distance; return { position: interpolate(seg.from, seg.to, clamp(t, 0, 1)), rotation: bearing(seg.from, seg.to) }; } } const last = segments[segments.length - 1]; return { position: last.to, rotation: bearing(last.from, last.to) }; }
    function updateSdkMarkerPosition(marker, position, rotation) { if (!marker || !position) return; try { marker.setPosition(position); } catch (e) { console.warn("Không cập nhật được marker SDK", e); } try { marker.setRotation(rotation); } catch {} }

    function prepareSimulation(path) { const built = buildSegments(path); segments = built.segments; totalDistance = built.totalDistance; startTime = null; paused = false; pausedAt = 0; totalPausedTime = 0; lastDistanceTravelled = 0; updateStats(0, totalDistance); }
    function startSimulation() { if (!segments.length) return; pauseSimulation(); startTime = null; paused = false; pausedAt = 0; totalPausedTime = 0; lastDistanceTravelled = 0; setStateText("Đang chạy"); animationId = requestAnimationFrame(animate); }
    function pauseSimulation() { if (animationId) { cancelAnimationFrame(animationId); animationId = null; } if (!paused && startTime) { paused = true; pausedAt = performance.now(); setStateText("Tạm dừng"); } }
    function resumeSimulation() { if (!segments.length || animationId) return; if (paused && pausedAt) totalPausedTime += performance.now() - pausedAt; paused = false; pausedAt = 0; setStateText("Đang chạy"); animationId = requestAnimationFrame(animate); }
    function restartSimulation() { if (!routePath.length) return; setViewportToFitPath(routePath); prepareSimulation(routePath); startSimulation(); }
    function animate(timestamp) {
      const speedKmH = Number($("speedInput").value), speedMps = speedKmH * 1000 / 3600; $("speedText").textContent = `${speedKmH} km/h`;
      if (!startTime) startTime = timestamp; const elapsedMs = timestamp - startTime - totalPausedTime, distanceTravelled = Math.max(0, elapsedMs / 1000) * speedMps; lastDistanceTravelled = Math.min(distanceTravelled, totalDistance);
      const current = getPositionAtDistance(lastDistanceTravelled);
      if (current) { updateSdkMarkerPosition(carMarker, current.position, current.rotation); if ($("followCarInput")?.checked) { try { if (map.panTo) map.panTo(current.position, { duration: 0, animate: false }); else if (map.moveCamera) map.moveCamera({ target: current.position }, { duration: 0, animate: false }); } catch {} } drawDomOverlay(routePath, current.position, current.rotation); }
      updateStats(lastDistanceTravelled, totalDistance);
      if (distanceTravelled < totalDistance) animationId = requestAnimationFrame(animate); else { animationId = null; setStateText("Hoàn thành"); logStatus("Xe đã chạy đến điểm B.", "success"); }
    }
    function updateStats(done, total) { $("distanceText").textContent = total > 0 ? formatDistance(total) : "--"; const pct = total > 0 ? Math.min(100, done / total * 100) : 0; $("progressText").textContent = total > 0 ? `${pct.toFixed(1)}%` : "--"; }
    function formatDistance(m) { return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${m.toFixed(0)} m`; }
    window.addEventListener("DOMContentLoaded", initializeRouteSimulationPage);
