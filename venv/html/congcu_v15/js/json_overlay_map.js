
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
const exportGeoJsonBtn = document.getElementById('exportGeoJsonBtn');
const exportShapefileBtn = document.getElementById('exportShapefileBtn');
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

const MAX_RENDER_POINTS = 20000;
const MAX_TABLE_ROWS = 500;
const MAX_DATA_ROWS = 200;
const MAX_PREVIEW_CHARS = 120000;

let map;
let currentLayer;
let markersLayer;
let parserWorker;
let rawTextPreview = '';
let tableRows = [];
let tableHeaders = [];
let coordinatePoints = [];
let geoJsonForMap = null;
let totalCoordinateCount = 0;
let isCoordinateTruncated = false;

const canvasRenderer = L.canvas({ padding: 0.5 });

const baseLayers = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }
  },
  map4d: {
    url: 'https://rtile.map4d.vn/all/2d/{z}/{x}/{y}.png',
    options: { maxZoom: 20, attribution: '&copy; Map4D' }
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
    const text = String(e.target.result || '');
    rawTextPreview = text.slice(0, MAX_PREVIEW_CHARS);
    jsonPreview.textContent = rawTextPreview;
    fileInfo.textContent = `Đã đọc file. Đang parse và chuyển sang GeoJSON trong background...`;
    appendLog(`Kích thước text: ${formatBytes(text.length)} ký tự.`);
    appendLog('Đang xử lý bằng Web Worker để tránh treo giao diện...');
    mapStateText.textContent = 'Đang xử lý';
    startWorker(text, file.name);
  };
  reader.onerror = () => {
    fileInfo.textContent = 'Không thể đọc file.';
    appendLog('Lỗi FileReader: không thể đọc file.');
  };
  reader.readAsText(file, 'utf-8');
});

fitMapBtn.addEventListener('click', fitAllPoints);
clearMapBtn.addEventListener('click', clearMarkers);
if (exportGeoJsonBtn) exportGeoJsonBtn.addEventListener('click', downloadGeoJson);
if (exportShapefileBtn) exportShapefileBtn.addEventListener('click', downloadShapefileZip);
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
  map = L.map('map', { zoomControl: true, preferCanvas: true }).setView([10.762622, 106.660172], 11);
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
  if (parserWorker) parserWorker.terminate();
  parserWorker = null;
  rawTextPreview = '';
  tableRows = [];
  tableHeaders = [];
  coordinatePoints = [];
  geoJsonForMap = null;
  totalCoordinateCount = 0;
  isCoordinateTruncated = false;
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

function startWorker(text, fileName) {
  parserWorker = createParserWorker();
  parserWorker.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type === 'done') {
      parserWorker.terminate();
      parserWorker = null;
      tableRows = msg.rows || [];
      tableHeaders = msg.headers || [];
      coordinatePoints = msg.points || [];
      geoJsonForMap = msg.geojson || { type: 'FeatureCollection', features: [] };
      totalCoordinateCount = msg.totalCoordinateCount || coordinatePoints.length;
      isCoordinateTruncated = Boolean(msg.truncated);
      renderAll(fileName, msg);
    } else if (msg.type === 'error') {
      parserWorker.terminate();
      parserWorker = null;
      console.error(msg.error);
      fileInfo.textContent = 'Lỗi đọc file JSON.';
      appendLog(`Lỗi: ${msg.error}`);
      mapStateText.textContent = 'Lỗi JSON';
      alert('Không thể đọc file JSON. File có thể sai cấu trúc hoặc quá lớn để trình duyệt xử lý an toàn.');
    }
  };
  parserWorker.onerror = (err) => {
    if (parserWorker) parserWorker.terminate();
    parserWorker = null;
    console.error(err);
    fileInfo.textContent = 'Lỗi xử lý file JSON.';
    appendLog(`Worker error: ${err.message || err}`);
    mapStateText.textContent = 'Lỗi xử lý';
  };
  parserWorker.postMessage({ text, maxRenderPoints: MAX_RENDER_POINTS, maxTableRows: MAX_TABLE_ROWS });
}

function renderAll(fileName, meta = {}) {
  rowCount.textContent = meta.totalRows || tableRows.length;
  pointCount.textContent = totalCoordinateCount;
  columnCount.textContent = tableHeaders.length;
  resultSectionLabel.classList.remove('hidden');
  summaryCard.classList.remove('hidden');
  controlCard.classList.remove('hidden');
  tableCard.classList.remove('hidden');
  logCard.classList.remove('hidden');
  dataPanel.classList.remove('hidden');

  renderPointsTable();
  renderDataTable();
  renderGeoJsonLayer();

  const renderedText = coordinatePoints.length === totalCoordinateCount
    ? `${coordinatePoints.length} điểm`
    : `${coordinatePoints.length}/${totalCoordinateCount} điểm`;
  fileInfo.textContent = `Đã nạp ${fileName} · ${meta.totalRows || tableRows.length} dòng xem · ${renderedText} tọa độ.`;
  mapSubtitle.textContent = totalCoordinateCount
    ? `Đã convert sang GeoJSON và overlay ${renderedText}. ${isCoordinateTruncated ? 'Đang giới hạn render để tránh treo trình duyệt.' : ''}`
    : 'Không tìm thấy lat/long hợp lệ trong file JSON.';
  mapStateText.textContent = totalCoordinateCount ? 'Đã overlay GeoJSON' : 'Không có tọa độ';
  appendLog(`Đã parse JSON thành công trong background.`);
  appendLog(`Dòng dữ liệu phát hiện: ${meta.totalRows || tableRows.length}. Bảng chỉ lấy mẫu ${tableRows.length} dòng.`);
  appendLog(`Cột bảng: ${tableHeaders.length}`);
  appendLog(`Điểm tọa độ hợp lệ: ${totalCoordinateCount}. Overlay thực tế: ${coordinatePoints.length}.`);
  if (isCoordinateTruncated) appendLog(`Đã giới hạn overlay ${MAX_RENDER_POINTS} điểm để tránh Page Unresponsive. Có thể tăng MAX_RENDER_POINTS trong js/json_overlay_map.js nếu máy đủ mạnh.`);
}

function renderGeoJsonLayer() {
  clearMarkers();
  if (!geoJsonForMap || !geoJsonForMap.features || !geoJsonForMap.features.length) return;

  // Render bằng Canvas + CircleMarker thay vì Marker DOM để giảm treo khi dữ liệu lớn.
  const layer = L.geoJSON(geoJsonForMap, {
    pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
      renderer: canvasRenderer,
      radius: 4,
      weight: 1,
      opacity: 0.85,
      fillOpacity: 0.65
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindPopup(`<b>${escapeHtml(p.title || 'Point')}</b><br>Lat: ${escapeHtml(p.lat)}<br>Lng: ${escapeHtml(p.lng)}${p.address ? `<br>${escapeHtml(p.address)}` : ''}<br><small>${escapeHtml(p.path || '')}</small>`);
    }
  });
  markersLayer.addLayer(layer);
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
  pointsBody.innerHTML = coordinatePoints.slice(0, MAX_TABLE_ROWS).map(point => `
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
  dataBody.innerHTML = rows.slice(0, MAX_DATA_ROWS).map(row => `
    <tr>${headers.map(h => `<td>${escapeHtml(row[h] ?? '')}</td>`).join('')}</tr>
  `).join('');
}

function downloadGeoJson() {
  if (!geoJsonForMap || !geoJsonForMap.features || !geoJsonForMap.features.length) {
    alert('Chưa có điểm tọa độ để xuất GeoJSON.');
    return;
  }
  const blob = new Blob([JSON.stringify(geoJsonForMap, null, 2)], { type: 'application/geo+json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = isCoordinateTruncated ? 'json_overlay_render_sample.geojson' : 'json_overlay_points.geojson';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}


async function downloadShapefileZip() {
  if (!geoJsonForMap || !geoJsonForMap.features || !geoJsonForMap.features.length) {
    alert('Chưa có điểm tọa độ để xuất Shapefile.');
    return;
  }
  if (typeof JSZip === 'undefined') {
    alert('Thiếu thư viện JSZip. Hãy kiểm tra kết nối Internet hoặc file jszip.min.js.');
    return;
  }
  try {
    const baseName = isCoordinateTruncated ? 'json_overlay_render_sample' : 'json_overlay_points';
    appendLog('Đang convert GeoJSON Point sang bộ Shapefile (.shp, .shx, .dbf, .prj, .cpg)...');
    const files = buildPointShapefile(geoJsonForMap.features, baseName);
    const zip = new JSZip();
    Object.entries(files).forEach(([name, data]) => zip.file(name, data));
    const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${baseName}_shapefile.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    appendLog(`Đã xuất Shapefile: ${baseName}_shapefile.zip`);
    if (isCoordinateTruncated) appendLog('Lưu ý: file Shapefile chỉ chứa số điểm đang được render/sample để tránh treo trình duyệt.');
  } catch (err) {
    console.error(err);
    appendLog(`Lỗi xuất Shapefile: ${err.message || err}`);
    alert('Không thể xuất Shapefile. Xem Console/Log để biết chi tiết.');
  }
}

function buildPointShapefile(features, baseName) {
  const validFeatures = features
    .filter(f => f && f.geometry && f.geometry.type === 'Point' && Array.isArray(f.geometry.coordinates))
    .map((f, idx) => {
      const x = Number(f.geometry.coordinates[0]);
      const y = Number(f.geometry.coordinates[1]);
      const p = f.properties || {};
      return {
        no: Number(p.no || idx + 1),
        title: String(p.title || `Point ${idx + 1}`),
        address: String(p.address || ''),
        lat: y,
        lng: x,
        path: String(p.path || '')
      };
    })
    .filter(p => Number.isFinite(p.lng) && Number.isFinite(p.lat));

  if (!validFeatures.length) throw new Error('Không có Point hợp lệ để ghi Shapefile.');

  return {
    [`${baseName}.shp`]: buildShp(validFeatures),
    [`${baseName}.shx`]: buildShx(validFeatures),
    [`${baseName}.dbf`]: buildDbf(validFeatures),
    [`${baseName}.prj`]: 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]',
    [`${baseName}.cpg`]: 'UTF-8'
  };
}

function buildShp(points) {
  const recordContentBytes = 20;
  const recordTotalBytes = 8 + recordContentBytes;
  const totalBytes = 100 + points.length * recordTotalBytes;
  const buffer = new ArrayBuffer(totalBytes);
  const view = new DataView(buffer);
  writeShapeHeader(view, totalBytes, points);
  let offset = 100;
  points.forEach((p, idx) => {
    view.setInt32(offset, idx + 1, false); offset += 4;
    view.setInt32(offset, recordContentBytes / 2, false); offset += 4;
    view.setInt32(offset, 1, true); offset += 4;
    view.setFloat64(offset, p.lng, true); offset += 8;
    view.setFloat64(offset, p.lat, true); offset += 8;
  });
  return buffer;
}

function buildShx(points) {
  const recordContentBytes = 20;
  const totalBytes = 100 + points.length * 8;
  const buffer = new ArrayBuffer(totalBytes);
  const view = new DataView(buffer);
  writeShapeHeader(view, totalBytes, points);
  let offset = 100;
  let shpOffsetWords = 50;
  points.forEach(() => {
    view.setInt32(offset, shpOffsetWords, false); offset += 4;
    view.setInt32(offset, recordContentBytes / 2, false); offset += 4;
    shpOffsetWords += (8 + recordContentBytes) / 2;
  });
  return buffer;
}

function writeShapeHeader(view, totalBytes, points) {
  const xs = points.map(p => p.lng);
  const ys = points.map(p => p.lat);
  const xmin = Math.min(...xs), ymin = Math.min(...ys), xmax = Math.max(...xs), ymax = Math.max(...ys);
  view.setInt32(0, 9994, false);
  for (let i = 4; i <= 20; i += 4) view.setInt32(i, 0, false);
  view.setInt32(24, totalBytes / 2, false);
  view.setInt32(28, 1000, true);
  view.setInt32(32, 1, true);
  view.setFloat64(36, xmin, true);
  view.setFloat64(44, ymin, true);
  view.setFloat64(52, xmax, true);
  view.setFloat64(60, ymax, true);
  view.setFloat64(68, 0, true);
  view.setFloat64(76, 0, true);
  view.setFloat64(84, 0, true);
  view.setFloat64(92, 0, true);
}

function buildDbf(points) {
  const fields = [
    { name: 'NO', type: 'N', length: 10, decimals: 0 },
    { name: 'TITLE', type: 'C', length: 120, decimals: 0 },
    { name: 'ADDRESS', type: 'C', length: 180, decimals: 0 },
    { name: 'LAT', type: 'N', length: 18, decimals: 8 },
    { name: 'LNG', type: 'N', length: 18, decimals: 8 },
    { name: 'PATH', type: 'C', length: 254, decimals: 0 }
  ];
  const headerLength = 32 + fields.length * 32 + 1;
  const recordLength = 1 + fields.reduce((sum, f) => sum + f.length, 0);
  const totalBytes = headerLength + points.length * recordLength + 1;
  const buffer = new ArrayBuffer(totalBytes);
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  const now = new Date();

  bytes.fill(0x20);
  view.setUint8(0, 0x03);
  view.setUint8(1, now.getFullYear() - 1900);
  view.setUint8(2, now.getMonth() + 1);
  view.setUint8(3, now.getDate());
  view.setUint32(4, points.length, true);
  view.setUint16(8, headerLength, true);
  view.setUint16(10, recordLength, true);

  let pos = 32;
  fields.forEach(field => {
    writeAscii(bytes, pos, field.name, 11); pos += 11;
    bytes[pos] = field.type.charCodeAt(0); pos += 1;
    pos += 4;
    bytes[pos] = field.length; pos += 1;
    bytes[pos] = field.decimals || 0; pos += 1;
    pos += 14;
  });
  bytes[pos] = 0x0D;

  let recPos = headerLength;
  const encoder = new TextEncoder();
  points.forEach(point => {
    bytes[recPos] = 0x20;
    let fieldPos = recPos + 1;
    writeDbfField(bytes, fieldPos, fields[0], point.no, encoder); fieldPos += fields[0].length;
    writeDbfField(bytes, fieldPos, fields[1], point.title, encoder); fieldPos += fields[1].length;
    writeDbfField(bytes, fieldPos, fields[2], point.address, encoder); fieldPos += fields[2].length;
    writeDbfField(bytes, fieldPos, fields[3], point.lat, encoder); fieldPos += fields[3].length;
    writeDbfField(bytes, fieldPos, fields[4], point.lng, encoder); fieldPos += fields[4].length;
    writeDbfField(bytes, fieldPos, fields[5], point.path, encoder);
    recPos += recordLength;
  });
  bytes[totalBytes - 1] = 0x1A;
  return buffer;
}

function writeAscii(bytes, start, value, length) {
  const text = String(value || '').slice(0, length);
  for (let i = 0; i < text.length; i++) bytes[start + i] = text.charCodeAt(i) & 0x7F;
}

function writeDbfField(bytes, start, field, value, encoder) {
  bytes.fill(0x20, start, start + field.length);
  if (field.type === 'N') {
    const num = Number(value);
    const text = Number.isFinite(num)
      ? (field.decimals ? num.toFixed(field.decimals) : String(Math.round(num)))
      : '';
    const clipped = text.length > field.length ? text.slice(0, field.length) : text;
    for (let i = 0; i < clipped.length; i++) bytes[start + field.length - clipped.length + i] = clipped.charCodeAt(i);
    return;
  }
  let encoded = encoder.encode(String(value ?? ''));
  if (encoded.length > field.length) encoded = encoded.slice(0, field.length);
  bytes.set(encoded, start);
}

function appendLog(message) {
  const time = new Date().toLocaleTimeString('vi-VN');
  statusLog.textContent += `[${time}] ${message}\n`;
  statusLog.scrollTop = statusLog.scrollHeight;
}

function formatBytes(n) {
  if (!Number.isFinite(n)) return '0';
  if (n < 1024) return String(n);
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}K`;
  return `${(n / 1024 / 1024).toFixed(1)}M`;
}

function createParserWorker() {
  const workerCode = `
    self.onmessage = function(event) {
      try {
        const { text, maxRenderPoints, maxTableRows } = event.data;
        const clean = String(text || '').replace(/^\\uFEFF/, '').trim();
        if (!clean) throw new Error('File rỗng.');
        const root = parseJsonFlexible(clean);
        const rowsInfo = jsonToRows(root, maxTableRows || 500);
        const coordInfo = extractCoordinatesAsGeoJson(root, maxRenderPoints || 20000);
        self.postMessage({
          type: 'done',
          rows: rowsInfo.rows,
          totalRows: rowsInfo.totalRows,
          headers: rowsInfo.headers,
          points: coordInfo.points,
          totalCoordinateCount: coordInfo.totalCoordinateCount,
          truncated: coordInfo.truncated,
          geojson: coordInfo.geojson
        });
      } catch (err) {
        self.postMessage({ type: 'error', error: err && err.message ? err.message : String(err) });
      }
    };

    function parseJsonFlexible(text) {
      try { return JSON.parse(text); }
      catch (firstError) {
        const ndjson = parseNdjson(text);
        if (ndjson) return ndjson;
        const multiple = parseConcatenatedJson(text);
        if (multiple) return multiple;
        throw firstError;
      }
    }

    function parseNdjson(text) {
      const lines = text.split(/\\r?\\n/).map(line => line.trim()).filter(Boolean);
      if (lines.length <= 1) return null;
      const rows = [];
      try {
        for (const line of lines) rows.push(JSON.parse(line));
        return rows;
      } catch (_) { return null; }
    }

    function parseConcatenatedJson(text) {
      const chunks = [];
      let start = -1, depth = 0, inString = false, escape = false;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (inString) {
          if (escape) escape = false;
          else if (ch === '\\\\') escape = true;
          else if (ch === '"') inString = false;
          continue;
        }
        if (ch === '"') { inString = true; continue; }
        if (ch === '{' || ch === '[') { if (depth === 0) start = i; depth++; }
        else if (ch === '}' || ch === ']') {
          depth--;
          if (depth === 0 && start >= 0) { chunks.push(text.slice(start, i + 1)); start = -1; }
          if (depth < 0) return null;
        }
      }
      if (depth !== 0 || chunks.length <= 1) return null;
      try { return chunks.map(chunk => JSON.parse(chunk)); }
      catch (_) { return null; }
    }

    function getPrimaryRows(value) {
      if (Array.isArray(value)) return value;
      if (value && typeof value === 'object') {
        if (Array.isArray(value.features)) return value.features;
        const priorityKeys = ['data', 'items', 'results', 'records', 'rows', 'pois', 'locations'];
        for (const key of priorityKeys) if (Array.isArray(value[key])) return value[key];
        const arrayKey = Object.keys(value).find(k => Array.isArray(value[k]) && value[k].some(x => x && typeof x === 'object'));
        return arrayKey ? value[arrayKey] : [value];
      }
      return [{ value }];
    }

    function jsonToRows(value, maxRows) {
      const candidates = getPrimaryRows(value);
      const totalRows = candidates.length;
      const rows = [];
      for (let idx = 0; idx < Math.min(candidates.length, maxRows); idx++) {
        const item = candidates[idx];
        if (item && item.type === 'Feature') rows.push(flattenJson({ STT: idx + 1, ...(item.properties || {}), geometry: item.geometry || '' }));
        else rows.push(flattenJson(item, '', { STT: idx + 1 }));
      }
      if (!rows.length) rows.push({ preview: safeString(value).slice(0, 3000) });
      const headers = Array.from(new Set(rows.flatMap(row => Object.keys(row))));
      return { rows, headers, totalRows };
    }

    function flattenJson(value, prefix = '', out = {}, depth = 0) {
      if (depth > 4) { out[prefix || 'value'] = safeString(value); return out; }
      if (Array.isArray(value)) {
        if (value.every(v => v === null || ['string', 'number', 'boolean'].includes(typeof v))) out[prefix || 'array'] = value.join(', ');
        else value.slice(0, 8).forEach((v, i) => flattenJson(v, prefix ? prefix + '[' + i + ']' : '[' + i + ']', out, depth + 1));
        return out;
      }
      if (value && typeof value === 'object') {
        Object.entries(value).forEach(([k, v]) => {
          const key = prefix ? prefix + '.' + k : k;
          if (v && typeof v === 'object') flattenJson(v, key, out, depth + 1);
          else out[key] = v ?? '';
        });
        return out;
      }
      out[prefix || 'value'] = value ?? '';
      return out;
    }

    function extractCoordinatesAsGeoJson(root, maxPoints) {
      const points = [];
      const features = [];
      const seen = new Set();
      let totalCoordinateCount = 0;
      let truncated = false;
      const latKeys = ['lat', 'latitude', 'vi_do', 'vido', 'vĩ_độ', 'vĩ độ', 'y'];
      const lngKeys = ['lng', 'lon', 'long', 'longitude', 'kinh_do', 'kinhdo', 'kinh_độ', 'kinh độ', 'x'];
      const normKey = key => String(key || '').toLowerCase().trim().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/đ/g, 'd').replace(/[\\s\\-]+/g, '_');
      const latNorm = latKeys.map(normKey);
      const lngNorm = lngKeys.map(normKey);
      const isLatKey = key => latNorm.includes(normKey(key));
      const isLngKey = key => lngNorm.includes(normKey(key));
      const toNum = value => {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(String(value).trim().replace(',', '.'));
        return Number.isFinite(n) ? n : null;
      };
      const validLat = value => typeof value === 'number' && value >= -90 && value <= 90;
      const validLng = value => typeof value === 'number' && value >= -180 && value <= 180;
      const makeTitle = source => source.name || source.Name || source.title || source.Title || source.address || source.Address || 'Point ' + (totalCoordinateCount + 1);
      const makeAddress = source => source.address || source.Address || source.oldaddress || source.OldAddress || source.old_address || '';

      function addPoint(latValue, lngValue, path, source = {}) {
        const lat = toNum(latValue);
        const lng = toNum(lngValue);
        if (!validLat(lat) || !validLng(lng)) return;
        const key = lat.toFixed(7) + ',' + lng.toFixed(7) + ',' + path;
        if (seen.has(key)) return;
        seen.add(key);
        totalCoordinateCount++;
        if (points.length >= maxPoints) { truncated = true; return; }
        const title = makeTitle(source);
        const address = makeAddress(source);
        const point = { no: points.length + 1, lat, lng, path, title, address };
        points.push(point);
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lng, lat] },
          properties: { no: point.no, title, address, lat, lng, path }
        });
      }

      function scanCoordinateArray(arr, path, source) {
        if (!Array.isArray(arr)) return;
        if (arr.length >= 2) {
          const a = toNum(arr[0]);
          const b = toNum(arr[1]);
          if (validLng(a) && validLat(b)) addPoint(b, a, path, source);
          else if (validLat(a) && validLng(b)) addPoint(a, b, path, source);
        }
        for (let idx = 0; idx < arr.length; idx++) if (Array.isArray(arr[idx])) scanCoordinateArray(arr[idx], path + '[' + idx + ']', source);
      }

      function walk(node, path = '$', parent = {}) {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) {
          scanCoordinateArray(node, path, parent);
          for (let idx = 0; idx < node.length; idx++) walk(node[idx], path + '[' + idx + ']', parent);
          return;
        }
        const source = node.properties && typeof node.properties === 'object' ? Object.assign({}, node.properties, node) : node;
        const entries = Object.entries(node);
        const latEntry = entries.find(([key]) => isLatKey(key));
        const lngEntry = entries.find(([key]) => isLngKey(key));
        if (latEntry && lngEntry) addPoint(latEntry[1], lngEntry[1], path, source);
        if (String(node.type || '').toLowerCase() === 'point' && Array.isArray(node.coordinates)) scanCoordinateArray(node.coordinates, path + '.coordinates', source);
        if (node.geometry && node.geometry.coordinates) scanCoordinateArray(node.geometry.coordinates, path + '.geometry.coordinates', source);
        if (Array.isArray(node.coordinates)) scanCoordinateArray(node.coordinates, path + '.coordinates', source);
        for (const [key, value] of entries) walk(value, path === '$' ? '$.' + key : path + '.' + key, source);
      }

      walk(root);
      return { points, totalCoordinateCount, truncated, geojson: { type: 'FeatureCollection', features } };
    }

    function safeString(value) { try { return JSON.stringify(value); } catch (_) { return String(value); } }
  `;
  const blob = new Blob([workerCode], { type: 'application/javascript' });
  return new Worker(URL.createObjectURL(blob));
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}
