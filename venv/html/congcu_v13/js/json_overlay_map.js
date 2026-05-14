const jsonFileInput = document.getElementById('jsonFileInput');
const fileInfo = document.getElementById('fileInfo');
const resultSectionLabel = document.getElementById('resultSectionLabel');
const summaryCard = document.getElementById('summaryCard');
const controlCard = document.getElementById('controlCard');
const tableCard = document.getElementById('tableCard');
const logCard = document.getElementById('logCard');
const statusLog = document.getElementById('statusLog');
const rowCount = document.getElementById('rowCount');
const pointCount = document.getElementById('pointCount');
const columnCount = document.getElementById('columnCount');
const fitMapBtn = document.getElementById('fitMapBtn');
const clearMapBtn = document.getElementById('clearMapBtn');
const baseLayerSelect = document.getElementById('baseLayerSelect');
const searchInput = document.getElementById('searchInput');
const dataPanel = document.getElementById('dataPanel');
const pointsHead = document.getElementById('pointsHead');
const pointsBody = document.getElementById('pointsBody');
const dataHead = document.getElementById('dataHead');
const dataBody = document.getElementById('dataBody');
const jsonPreview = document.getElementById('jsonPreview');
const mapSubtitle = document.getElementById('mapSubtitle');
const mapStateText = document.getElementById('mapStateText');

let map;
let currentLayer;
let markersLayer;
let rawJsonData = null;
let tableRows = [];
let tableHeaders = [];
let coordinatePoints = [];

const baseLayers = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }
  },
  googleRoad: {
    url: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    options: { maxZoom: 20, attribution: '&copy; Google' }
  },
  googleSatellite: {
    url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    options: { maxZoom: 20, attribution: '&copy; Google' }
  }
};

initMap();

jsonFileInput.addEventListener('change', (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  resetState();
  fileInfo.textContent = `Đang đọc file: ${file.name}...`;
  appendLog(`Đang đọc file: ${file.name}`);

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const text = String(e.target.result || '');
      rawJsonData = parseJsonFlexible(text);
      tableRows = jsonToRows(rawJsonData);
      coordinatePoints = extractCoordinates(rawJsonData);
      tableHeaders = Array.from(new Set(tableRows.flatMap(row => Object.keys(row))));
      if (!tableRows.length) {
        tableRows = [{ preview: JSON.stringify(rawJsonData).slice(0, 3000) }];
        tableHeaders = ['preview'];
      }
      renderAll(file.name);
    } catch (err) {
      console.error(err);
      fileInfo.textContent = 'Lỗi đọc file JSON.';
      appendLog(`Lỗi: ${err.message}`);
      mapStateText.textContent = 'Lỗi JSON';
      alert('Không thể đọc file JSON. File có thể sai cấu trúc hoặc không phải JSON/GeoJSON hợp lệ.');
    }
  };
  reader.onerror = () => {
    fileInfo.textContent = 'Không thể đọc file.';
    appendLog('Lỗi FileReader: không thể đọc file.');
  };
  reader.readAsText(file, 'utf-8');
});

fitMapBtn.addEventListener('click', fitAllPoints);
clearMapBtn.addEventListener('click', clearMarkers);
baseLayerSelect.addEventListener('change', () => switchBaseLayer(baseLayerSelect.value));
searchInput.addEventListener('input', () => renderDataTable());

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
  });
});

function initMap() {
  map = L.map('map', { zoomControl: true }).setView([10.762622, 106.660172], 11);
  markersLayer = L.layerGroup().addTo(map);
  switchBaseLayer('osm');
  setTimeout(() => map.invalidateSize(), 200);
}

function switchBaseLayer(layerName) {
  const cfg = baseLayers[layerName] || baseLayers.osm;
  if (currentLayer) currentLayer.remove();
  currentLayer = L.tileLayer(cfg.url, cfg.options).addTo(map);
}

function resetState() {
  rawJsonData = null;
  tableRows = [];
  tableHeaders = [];
  coordinatePoints = [];
  pointsHead.innerHTML = '';
  pointsBody.innerHTML = '';
  dataHead.innerHTML = '';
  dataBody.innerHTML = '';
  jsonPreview.textContent = '';
  searchInput.value = '';
  clearMarkers();
  resultSectionLabel.classList.add('hidden');
  summaryCard.classList.add('hidden');
  controlCard.classList.add('hidden');
  tableCard.classList.add('hidden');
  logCard.classList.remove('hidden');
  dataPanel.classList.add('hidden');
  rowCount.textContent = '0';
  pointCount.textContent = '0';
  columnCount.textContent = '0';
  mapSubtitle.textContent = 'Marker sẽ hiển thị sau khi chọn file JSON có lat/long hợp lệ.';
  mapStateText.textContent = 'Đang đọc';
  statusLog.textContent = '';
}

function renderAll(fileName) {
  rowCount.textContent = tableRows.length;
  pointCount.textContent = coordinatePoints.length;
  columnCount.textContent = tableHeaders.length;
  resultSectionLabel.classList.remove('hidden');
  summaryCard.classList.remove('hidden');
  controlCard.classList.remove('hidden');
  tableCard.classList.remove('hidden');
  logCard.classList.remove('hidden');
  dataPanel.classList.remove('hidden');

  jsonPreview.textContent = JSON.stringify(rawJsonData, null, 2).slice(0, 100000);
  renderPointsTable();
  renderDataTable();
  renderMarkers();

  fileInfo.textContent = `Đã nạp ${fileName} · ${tableRows.length} dòng xem · ${coordinatePoints.length} điểm tọa độ.`;
  mapSubtitle.textContent = coordinatePoints.length
    ? `Đã overlay ${coordinatePoints.length} điểm từ file JSON.`
    : 'Không tìm thấy lat/long hợp lệ trong file JSON.';
  mapStateText.textContent = coordinatePoints.length ? 'Đã overlay' : 'Không có tọa độ';
  appendLog(`Đã parse JSON thành công.`);
  appendLog(`Dòng xem: ${tableRows.length}`);
  appendLog(`Cột bảng: ${tableHeaders.length}`);
  appendLog(`Điểm tọa độ hợp lệ: ${coordinatePoints.length}`);
}

function parseJsonFlexible(text) {
  const clean = text.replace(/^\uFEFF/, '').trim();
  if (!clean) throw new Error('File rỗng.');

  try {
    return JSON.parse(clean);
  } catch (firstError) {
    const ndjson = parseNdjson(clean);
    if (ndjson) return ndjson;
    const multiple = parseConcatenatedJson(clean);
    if (multiple) return multiple;
    throw firstError;
  }
}

function parseNdjson(text) {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (lines.length <= 1) return null;
  const rows = [];
  try {
    for (const line of lines) rows.push(JSON.parse(line));
    return rows;
  } catch (_) {
    return null;
  }
}

function parseConcatenatedJson(text) {
  const chunks = [];
  let start = -1, depth = 0, inString = false, escape = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inString) {
      if (escape) escape = false;
      else if (ch === '\\') escape = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') { inString = true; continue; }
    if (ch === '{' || ch === '[') {
      if (depth === 0) start = i;
      depth++;
    } else if (ch === '}' || ch === ']') {
      depth--;
      if (depth === 0 && start >= 0) {
        chunks.push(text.slice(start, i + 1));
        start = -1;
      }
      if (depth < 0) return null;
    }
  }
  if (depth !== 0 || chunks.length <= 1) return null;
  try {
    return chunks.map(chunk => JSON.parse(chunk));
  } catch (_) {
    return null;
  }
}

function jsonToRows(value) {
  const rows = [];
  const candidates = getPrimaryRows(value);
  candidates.forEach((item, idx) => {
    if (item && item.type === 'Feature') {
      rows.push(flattenJson({ STT: idx + 1, ...(item.properties || {}), geometry: item.geometry || '' }));
    } else {
      rows.push(flattenJson(item, '', { STT: idx + 1 }));
    }
  });
  return rows;
}

function getPrimaryRows(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') {
    if (Array.isArray(value.features)) return value.features;
    const priorityKeys = ['data', 'items', 'results', 'records', 'rows', 'pois', 'locations'];
    for (const key of priorityKeys) {
      if (Array.isArray(value[key])) return value[key];
    }
    const arrayKey = Object.keys(value).find(k => Array.isArray(value[k]) && value[k].some(x => x && typeof x === 'object'));
    return arrayKey ? value[arrayKey] : [value];
  }
  return [{ value }];
}

function flattenJson(value, prefix = '', out = {}, depth = 0) {
  if (depth > 5) {
    out[prefix || 'value'] = safeString(value);
    return out;
  }
  if (Array.isArray(value)) {
    if (value.every(v => v === null || ['string', 'number', 'boolean'].includes(typeof v))) {
      out[prefix || 'array'] = value.join(', ');
    } else {
      value.slice(0, 12).forEach((v, i) => flattenJson(v, `${prefix}[${i}]`, out, depth + 1));
    }
    return out;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([k, v]) => {
      const key = prefix ? `${prefix}.${k}` : k;
      if (v && typeof v === 'object') flattenJson(v, key, out, depth + 1);
      else out[key] = v ?? '';
    });
    return out;
  }
  out[prefix || 'value'] = value ?? '';
  return out;
}

function extractCoordinates(root) {
  const points = [];
  const seen = new Set();
  const latKeys = ['lat', 'latitude', 'vi_do', 'vido', 'vĩ_độ', 'vĩ độ', 'y'];
  const lngKeys = ['lng', 'lon', 'long', 'longitude', 'kinh_do', 'kinhdo', 'kinh_độ', 'kinh độ', 'x'];

  const normKey = key => String(key || '').toLowerCase().trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[\s\-]+/g, '_');
  const isLatKey = key => latKeys.map(normKey).includes(normKey(key));
  const isLngKey = key => lngKeys.map(normKey).includes(normKey(key));
  const toNum = value => {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(String(value).trim().replace(',', '.'));
    return Number.isFinite(n) ? n : null;
  };
  const validLat = value => typeof value === 'number' && value >= -90 && value <= 90;
  const validLng = value => typeof value === 'number' && value >= -180 && value <= 180;

  const addPoint = (latValue, lngValue, path, source = {}) => {
    const lat = toNum(latValue);
    const lng = toNum(lngValue);
    if (!validLat(lat) || !validLng(lng)) return;
    const key = `${lat.toFixed(7)},${lng.toFixed(7)},${path}`;
    if (seen.has(key)) return;
    seen.add(key);
    points.push({
      no: points.length + 1,
      lat,
      lng,
      path,
      title: source.name || source.Name || source.title || source.address || source.Address || `Point ${points.length + 1}`,
      address: source.address || source.Address || source.oldaddress || source.OldAddress || ''
    });
  };

  const scanCoordinateArray = (arr, path, source) => {
    if (!Array.isArray(arr)) return;
    if (arr.length >= 2 && typeof toNum(arr[0]) === 'number' && typeof toNum(arr[1]) === 'number') {
      const a = toNum(arr[0]);
      const b = toNum(arr[1]);
      // GeoJSON order is [lng, lat]. If first value looks like lng and second looks like lat, use that.
      if (validLng(a) && validLat(b)) addPoint(b, a, path, source);
      else if (validLat(a) && validLng(b)) addPoint(a, b, path, source);
    }
    arr.forEach((item, idx) => {
      if (Array.isArray(item)) scanCoordinateArray(item, `${path}[${idx}]`, source);
    });
  };

  const walk = (node, path = '$', parent = {}) => {
    if (!node || typeof node !== 'object') return;

    if (Array.isArray(node)) {
      scanCoordinateArray(node, path, parent);
      node.forEach((item, idx) => walk(item, `${path}[${idx}]`, parent));
      return;
    }

    const source = node.properties && typeof node.properties === 'object' ? { ...node.properties, ...node } : node;
    const entries = Object.entries(node);
    const latEntry = entries.find(([key]) => isLatKey(key));
    const lngEntry = entries.find(([key]) => isLngKey(key));
    if (latEntry && lngEntry) addPoint(latEntry[1], lngEntry[1], path, source);

    if (String(node.type || '').toLowerCase() === 'point' && Array.isArray(node.coordinates)) {
      scanCoordinateArray(node.coordinates, `${path}.coordinates`, source);
    }
    if (node.geometry && node.geometry.coordinates) {
      scanCoordinateArray(node.geometry.coordinates, `${path}.geometry.coordinates`, source);
    }
    if (Array.isArray(node.coordinates)) {
      scanCoordinateArray(node.coordinates, `${path}.coordinates`, source);
    }

    entries.forEach(([key, value]) => walk(value, path === '$' ? `$.${key}` : `${path}.${key}`, source));
  };

  walk(root);
  return points;
}

function renderMarkers() {
  clearMarkers();
  if (!coordinatePoints.length) return;
  coordinatePoints.forEach(point => {
    const marker = L.marker([point.lat, point.lng]);
    marker.bindPopup(`<b>${escapeHtml(point.title)}</b><br>Lat: ${point.lat}<br>Lng: ${point.lng}${point.address ? `<br>${escapeHtml(point.address)}` : ''}<br><small>${escapeHtml(point.path)}</small>`);
    marker.addTo(markersLayer);
  });
  fitAllPoints();
}

function clearMarkers() {
  if (markersLayer) markersLayer.clearLayers();
}

function fitAllPoints() {
  if (!coordinatePoints.length) return;
  const bounds = L.latLngBounds(coordinatePoints.map(p => [p.lat, p.lng]));
  map.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
  setTimeout(() => map.invalidateSize(), 150);
}

function renderPointsTable() {
  const headers = ['no', 'title', 'lat', 'lng', 'address', 'path'];
  pointsHead.innerHTML = `<tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`;
  pointsBody.innerHTML = coordinatePoints.slice(0, 500).map(point => `
    <tr data-lat="${point.lat}" data-lng="${point.lng}">
      ${headers.map(h => `<td>${escapeHtml(point[h] ?? '')}</td>`).join('')}
    </tr>
  `).join('');
  pointsBody.querySelectorAll('tr').forEach(row => {
    row.addEventListener('click', () => {
      const lat = Number(row.dataset.lat);
      const lng = Number(row.dataset.lng);
      map.setView([lat, lng], Math.max(map.getZoom(), 16));
    });
  });
}

function renderDataTable() {
  const keyword = searchInput.value.trim().toLowerCase();
  let rows = tableRows;
  if (keyword) {
    rows = rows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(keyword)));
  }
  const headers = tableHeaders.slice(0, 40);
  dataHead.innerHTML = `<tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`;
  dataBody.innerHTML = rows.slice(0, 200).map(row => `
    <tr>${headers.map(h => `<td>${escapeHtml(row[h] ?? '')}</td>`).join('')}</tr>
  `).join('');
}

function appendLog(message) {
  const time = new Date().toLocaleTimeString('vi-VN');
  statusLog.textContent += `[${time}] ${message}\n`;
  statusLog.scrollTop = statusLog.scrollHeight;
}

function safeString(value) {
  try { return JSON.stringify(value); }
  catch (_) { return String(value); }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}
