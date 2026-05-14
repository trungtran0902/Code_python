const API_BASE_URL = "https://api-data.map4d.vn/map/manage/place";
const MAX_PARALLEL_REQUESTS = 5; 
const IMPORT_CHUNK_SIZE = 50; 
const DETAIL_API_KEY = '93d393d0f6507ee00b62fe01db7430fa';
const VERIFY_ID_PARALLEL_LIMIT = 10;
const REQUIRED_COLUMNS = ["Name", "Address", "OldAddress", "Latitude", "Longitude", "Type"];

let globalData = [];
let globalHeaders = [];
let candidateRows = [];
let processState = {
    status: 'idle', 
    processedIndices: new Set(),
    results: [],
    total: 0,
    shouldStop: false,
    fileKey: '',
    sourceFileName: ''
};

// DOM Elements
const tokenInput = document.getElementById('tokenInput');
const btnCheckToken = document.getElementById('btnCheckToken');
const tokenStatusMessage = document.getElementById('tokenStatusMessage');
const fileInput = document.getElementById('fileInput');
const checkpointInput = document.getElementById('checkpointInput');
const filePreviewContainer = document.getElementById('filePreviewContainer');
const previewTableHead = document.getElementById('previewTableHead');
const previewTableBody = document.getElementById('previewTableBody');
const totalRowsCount = document.getElementById('totalRowsCount');

const btnStartImport = document.getElementById('btnStartImport');
const btnPauseImport = document.getElementById('btnPauseImport');
const btnResumeImport = document.getElementById('btnResumeImport');
const btnDownloadResult = document.getElementById('btnDownloadResult');
const btnDownloadCheckpoint = document.getElementById('btnDownloadCheckpoint');
const btnClearCheckpoint = document.getElementById('btnClearCheckpoint');
const btnVerifyImportedIds = document.getElementById('btnVerifyImportedIds');
const btnVerifyImportedIdsText = document.getElementById('btnVerifyImportedIdsText');
const btnVerifyImportedIdsLoader = document.getElementById('btnVerifyImportedIdsLoader');

const progressStatusText = document.getElementById('progressStatusText');
const progressCountText = document.getElementById('progressCountText');
const progressBar = document.getElementById('progressBar');
const resultContainer = document.getElementById('resultContainer');
const verifyLogContainer = document.getElementById('verifyLogContainer');
const verifyLogConsole = document.getElementById('verifyLogConsole');
const btnClearVerifyLog = document.getElementById('btnClearVerifyLog');

// Helpers
function getHeaders() {
    return {
        "accept": "text/plain",
        "Content-Type": "application/json",
        "Authorization": tokenInput.value.trim()
    };
}

function setTokenCheckLoading(isLoading) {
    const textEl = document.getElementById('btnCheckTokenText');
    const loaderEl = document.getElementById('btnCheckTokenLoader');
    if(textEl) textEl.classList.toggle('hidden', isLoading);
    if(loaderEl) loaderEl.classList.toggle('hidden', !isLoading);
}

async function checkToken(showPopup = true) {
    const token = tokenInput.value.trim();
    if (!token) {
        if(showPopup) Swal.fire('Lỗi', 'Vui lòng nhập Authorization Token', 'error');
        return false;
    }

    if(showPopup) setTokenCheckLoading(true);

    try {
        const res = await fetch(API_BASE_URL, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({}) 
        });
        
        if (showPopup) setTokenCheckLoading(false);

        if (res.status === 401 || res.status === 403) {
            tokenStatusMessage.textContent = 'Token không hợp lệ hoặc không có quyền (401/403).';
            tokenStatusMessage.className = 'mt-2 text-sm text-red-600 block';
            if(showPopup) Swal.fire('Lỗi', 'Token không hợp lệ hoặc không có quyền.', 'error');
            return false;
        }

        if (!(res.status >= 200 && res.status < 300) && res.status !== 400) {
            const bodyText = await res.text();
            const shortBody = (bodyText || '').trim().slice(0, 200);
            tokenStatusMessage.textContent = `Không thể xác thực token qua API test (HTTP ${res.status}).`;
            tokenStatusMessage.className = 'mt-2 text-sm text-yellow-700 block';
            if(showPopup) Swal.fire('Cảnh báo', `API test trả về HTTP ${res.status}${shortBody ? `: ${shortBody}` : ''}`, 'warning');
            return false;
        }
        
        tokenStatusMessage.textContent = `Token có vẻ hợp lệ (HTTP ${res.status}).`;
        tokenStatusMessage.className = 'mt-2 text-sm text-green-600 block';
        if(showPopup) Swal.fire('Thành công', `Token có vẻ hợp lệ (HTTP ${res.status}).`, 'success');
        return true;

    } catch (err) {
        if (showPopup) setTokenCheckLoading(false);
        tokenStatusMessage.textContent = `Lỗi kết nối: ${err.message}`;
        tokenStatusMessage.className = 'mt-2 text-sm text-red-600 block';
        if(showPopup) Swal.fire('Lỗi Kết Nối', `Không thể kết nối API. Chi tiết: ${err.message}.`, 'error');
        return false;
    }
}

// --- Business Hours Parser ---
function isBlank(value) {
    return value === undefined || value === null || String(value).trim() === '';
}

function normalizeTimeValue(value) {
    if (isBlank(value)) return null;
    let textValue = String(value).trim();
    if (!isNaN(textValue) && Number(textValue) >= 0 && Number(textValue) < 1) {
        let totalMinutes = Math.round(Number(textValue) * 24 * 60);
        let hours = Math.floor(totalMinutes / 60) % 24;
        let minutes = totalMinutes % 60;
        return `${String(hours).padStart(2, '0')}${String(minutes).padStart(2, '0')}`;
    }
    if (textValue.length === 4 && !isNaN(textValue)) return textValue;
    if (textValue.includes(':')) {
        let parts = textValue.split(':');
        if (parts.length >= 2) return `${parts[0].padStart(2, '0')}${parts[1].padStart(2, '0')}`;
    }
    return textValue.replace(/:/g, '').substring(0, 4); 
}

function normalizeDayValue(value) {
    if (isBlank(value)) throw new Error("Thiếu giá trị day cho businessHours.");
    let normalized = String(value).trim().toLowerCase();
    const dayAliases = {
        "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
        "sun": 0, "sunday": 0, "cn": 0, "mon": 1, "monday": 1, "thu2": 1, "t2": 1,
        "tue": 2, "tuesday": 2, "thu3": 2, "t3": 2, "wed": 3, "wednesday": 3, "thu4": 3, "t4": 3,
        "thu": 4, "thursday": 4, "thu5": 4, "t5": 4, "fri": 5, "friday": 5, "thu6": 5, "t6": 5,
        "sat": 6, "saturday": 6, "thu7": 6, "t7": 6
    };
    if (dayAliases[normalized] !== undefined) return dayAliases[normalized];
    let num = parseInt(value, 10);
    if (!isNaN(num)) {
        if (num >= 1 && num <= 7) return num === 7 ? 0 : num;
        if (num === 0) return 0;
    }
    throw new Error(`Giá trị day không hợp lệ: ${value}`);
}

function parseBusinessHoursValue(rawValue) {
    if (isBlank(rawValue)) return [];
    let parsedValue = rawValue;
    if (typeof rawValue === 'string') {
        let textValue = rawValue.trim();
        if (!textValue) return [];
        try {
            textValue = textValue.replace(/'/g, '"');
            parsedValue = JSON.parse(textValue);
        } catch (e) {
            throw new Error("BusinessHours/Time phải là JSON hợp lệ.");
        }
    }
    let parsedItems = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
    let normalizedItems = [];
    for (let item of parsedItems) {
        if (typeof item !== 'object') throw new Error("Mỗi businessHours item phải là object/dict.");
        let dayOpen, dayClose, timeOpen, timeClose;
        if (item.open && item.close) {
            dayOpen = normalizeDayValue(item.open.day);
            dayClose = normalizeDayValue(item.close.day);
            timeOpen = normalizeTimeValue(item.open.time);
            timeClose = normalizeTimeValue(item.close.time);
        } else {
            let day = item.open_day !== undefined ? item.open_day : (item.start_day !== undefined ? item.start_day : (item.day !== undefined ? item.day : item.week_day));
            dayOpen = normalizeDayValue(day);
            let cDay = item.close_day !== undefined ? item.close_day : (item.end_day !== undefined ? item.end_day : (item.day !== undefined ? item.day : item.week_day));
            dayClose = normalizeDayValue(cDay);
            timeOpen = normalizeTimeValue(item.open_time || item.start_time || item.from);
            timeClose = normalizeTimeValue(item.close_time || item.end_time || item.to);
        }
        normalizedItems.push({ open: { day: dayOpen, time: timeOpen }, close: { day: dayClose, time: timeClose } });
    }
    return normalizedItems;
}

function getBusinessHours(row) {
    const cols = ["BusinessHours", "businessHours", "Time", "time", "Hours", "hours"];
    let raw = null;
    for (let c of cols) {
        if (row[c] !== undefined && !isBlank(row[c])) {
            raw = row[c];
            break;
        }
    }
    if (!raw) return [];
    return parseBusinessHoursValue(raw);
}

function parseMultiValue(val) {
    if (isBlank(val)) return [];
    return String(val).split(',').map(v => v.trim()).filter(v => v !== '');
}

function validateRow(row) {
    for (let field of REQUIRED_COLUMNS) {
        if (isBlank(row[field])) return { valid: false, message: `Thiếu dữ liệu bắt buộc ở cột '${field}'.` };
    }
    let lat = parseFloat(row.Latitude);
    let lng = parseFloat(row.Longitude);
    if (isNaN(lat)) return { valid: false, message: `Cột 'Latitude' không phải định dạng số.` };
    if (isNaN(lng)) return { valid: false, message: `Cột 'Longitude' không phải định dạng số.` };
    let bHours = [];
    try { bHours = getBusinessHours(row); } catch (e) { return { valid: false, message: e.message }; }
    return { valid: true, bHours: bHours, lat, lng };
}

async function uploadPlace(row) {
    let val = validateRow(row);
    if (!val.valid) return { status: 'INVALID', placeId: null, message: val.message, stop: false };
    let phone = !isBlank(row.Phone) ? String(row.Phone) : (!isBlank(row.phone) ? String(row.phone) : null);
    let website = !isBlank(row.Website) ? String(row.Website) : (!isBlank(row.website) ? String(row.website) : null);
    let types = parseMultiValue(row.Type);
    let tags = parseMultiValue(row.Tags);
    let place = {
        location: { lng: val.lng, lat: val.lat },
        name: String(row.Name).trim(),
        objectId: null,
        description: null,
        types: types,
        tags: tags,
        address: String(row.Address).trim(),
        oldAddress: String(row.OldAddress).trim(),
        photos: [],
        startDate: new Date().toISOString(),
        endDate: new Date().toISOString(),
        phoneNumber: phone,
        website: website,
        geometry: { type: "Point", coordinates: [val.lng, val.lat] },
        rank: { value: 0 },
        layer: "address",
        source: null,
        metadata: []
    };
    if (val.bHours && val.bHours.length > 0) place.businessHours = val.bHours;
    try {
        const res = await fetch(API_BASE_URL, { method: 'POST', headers: getHeaders(), body: JSON.stringify(place) });
        if (res.status === 200 || res.status === 201) {
            const respJson = await res.json();
            let placeId = (respJson && respJson.result && respJson.result.id) || respJson.id || respJson.placeId;
            if (placeId) return { status: 'OK', placeId: placeId, message: 'Uploaded', stop: false, authError: false };
            else return { status: 'FAIL', placeId: null, message: 'Thành công nhưng không trả về ID', stop: false, authError: false };
        } else {
            const text = await res.text();
            const authError = res.status === 401 || res.status === 403;
            return { status: authError ? 'AUTH_ERROR' : 'FAIL', placeId: null, message: `${res.status} - ${text}`, stop: authError, authError };
        }
    } catch (err) { return { status: 'ERROR', placeId: null, message: err.message, stop: true, authError: false }; }
}

// Event Listeners
if(btnCheckToken) btnCheckToken.addEventListener('click', () => checkToken(true));

if(checkpointInput) checkpointInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            const sanitized = ev.target.result.replace(/\bNaN\b/g, "null");
            let data = JSON.parse(sanitized);
            if(!processState.fileKey) {
                Swal.fire('Lỗi', 'Vui lòng upload file Excel/CSV trước khi nạp checkpoint!', 'error');
                checkpointInput.value = '';
                return;
            }
            // Normalize snake_case keys from Python
            if (data.processed_indices && !data.processedIndices) data.processedIndices = data.processed_indices;
            if (data.total_rows && !data.total) data.total = data.total_rows;

            // Load results into memory (NOT localStorage to avoid 5MB limit)
            const indices = data.processedIndices || [];
            processState.processedIndices = new Set(indices);
            processState.results = (data.results || []).map(r => ({
                source_row: r.source_row || 0,
                Name: r.Name || r.name || '',
                time: r.time || '',
                id: r.id || '',
                status: r.status || '',
                message: r.message || ''
            }));
            processState.status = 'paused';
            processState.total = candidateRows.length || data.total || 0;

            // Only save lightweight indices to localStorage
            try {
                localStorage.removeItem(processState.fileKey); // clear old data first
                localStorage.setItem(processState.fileKey, JSON.stringify({
                    status: 'paused',
                    processedIndices: indices
                }));
            } catch(e) { console.warn('localStorage save skipped'); }

            updateProgressUI(true);
            Swal.fire('Thành công', `Đã nạp checkpoint: ${indices.length} dòng đã xử lý.`, 'success');
        } catch(err) {
            Swal.fire('Lỗi', 'File Checkpoint không hợp lệ: ' + err.message, 'error');
        }
    };
    reader.readAsText(file);
});

if(fileInput) fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) { filePreviewContainer.classList.add('hidden'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, {type: 'array'});
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        const json = XLSX.utils.sheet_to_json(worksheet, { defval: "" });
        globalData = json;
        if (json.length > 0) {
            globalHeaders = Object.keys(json[0]);
            let missing = REQUIRED_COLUMNS.filter(c => !globalHeaders.includes(c));
            if (missing.length > 0) { Swal.fire('Lỗi cấu trúc', `File thiếu các cột: ${missing.join(', ')}`, 'error'); return; }
            renderPreviewTable(globalHeaders, json.slice(0, 5)); 
            candidateRows = json.map((r, i) => ({ originalIndex: i, rowData: r }));
            totalRowsCount.textContent = candidateRows.length;
            processState.total = candidateRows.length;
            filePreviewContainer.classList.remove('hidden');
            const hashStr = file.name + file.size + file.lastModified;
            const hashCode = s => s.split('').reduce((a,b)=>{a=((a<<5)-a)+b.charCodeAt(0);return a&a},0);
            processState.fileKey = `map4d_import_${hashCode(hashStr)}`;
            processState.sourceFileName = file.name;
            loadCheckpoint();
        } else { Swal.fire('Lỗi', 'File không có dữ liệu', 'error'); }
    };
    reader.readAsArrayBuffer(file);
});

function renderPreviewTable(headers, data) {
    previewTableHead.innerHTML = `<tr>${headers.map(h => `<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${h}</th>`).join('')}</tr>`;
    previewTableBody.innerHTML = data.map(row => `<tr>${headers.map(h => `<td class="px-6 py-4 whitespace-nowrap text-gray-700">${row[h] || ''}</td>`).join('')}</tr>`).join('');
}

function loadCheckpoint() {
    const saved = localStorage.getItem(processState.fileKey);
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            processState.status = parsed.status === 'running' ? 'paused' : parsed.status;
            const indices = parsed.processedIndices || parsed.processed_indices || [];
            processState.processedIndices = new Set(indices);
            processState.results = parsed.results || [];
            if (processState.processedIndices.size > 0) {
                Swal.fire({ title: 'Phát hiện tiến trình cũ', text: `Đã xử lý ${processState.processedIndices.size}/${processState.total} dòng.`, icon: 'info', toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
            }
        } catch(e) { console.error(e); }
    } else {
        processState.status = 'idle';
        processState.processedIndices = new Set();
        processState.results = [];
    }
    updateProgressUI();
}

function saveCheckpoint() {
    if(!processState.fileKey) return;
    const data = JSON.stringify({
        status: processState.status,
        processedIndices: Array.from(processState.processedIndices)
    });
    try {
        localStorage.setItem(processState.fileKey, data);
    } catch(e) {
        // Quota exceeded - chỉ xóa checkpoint cũ, không xóa dashboard log
        console.warn('localStorage quota exceeded, clearing old data...');
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('map4d_import_') || key.startsWith('map4d_del_'))) keysToRemove.push(key);
        }
        keysToRemove.forEach(k => localStorage.removeItem(k));
        try {
            localStorage.setItem(processState.fileKey, data);
        } catch(e2) {
            console.warn('localStorage still full after cleanup, checkpoint saved in memory only');
        }
    }
}

function clearCheckpoint() { if(!processState.fileKey) return; localStorage.removeItem(processState.fileKey); }

function setVerifyLogVisible(isVisible) {
    if (!verifyLogContainer) return;
    verifyLogContainer.classList.toggle('hidden', !isVisible);
}

function clearVerifyLog() {
    if (verifyLogConsole) verifyLogConsole.innerHTML = '';
}

function appendVerifyLog(message, type = 'info') {
    if (!verifyLogConsole) return;
    setVerifyLogVisible(true);
    const line = document.createElement('div');
    line.className = `verify-log-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString('vi-VN')}] ${message}`;
    verifyLogConsole.appendChild(line);
    verifyLogConsole.scrollTop = verifyLogConsole.scrollHeight;
}

function getImportedIdsForVerification() {
    const seen = new Set();
    const ids = [];
    for (const row of processState.results) {
        const id = (row && row.id ? String(row.id).trim() : '');
        if (!id || seen.has(id)) continue;
        seen.add(id);
        ids.push(id);
    }
    return ids;
}

async function verifyImportedIds() {
    const ids = getImportedIdsForVerification();
    if (ids.length === 0) {
        Swal.fire('Thông báo', 'Chưa có ID nào để kiểm tra.', 'info');
        return;
    }

    if (btnVerifyImportedIds) btnVerifyImportedIds.disabled = true;
    if (btnVerifyImportedIdsText) btnVerifyImportedIdsText.textContent = 'Đang kiểm tra ID...';
    if (btnVerifyImportedIdsLoader) btnVerifyImportedIdsLoader.classList.remove('hidden');

    clearVerifyLog();
    appendVerifyLog(`Bắt đầu kiểm tra ${ids.length} ID đã import...`, 'info');

    const passedIds = [];
    let checkedCount = 0;
    try {
        let pointer = 0;
        while (pointer < ids.length) {
            const batch = ids.slice(pointer, pointer + VERIFY_ID_PARALLEL_LIMIT);
            pointer += batch.length;
            const batchResults = await Promise.all(batch.map(async (id) => {
                const url = `https://api.map4d.vn/sdk/place/detail/${encodeURIComponent(id)}?key=${encodeURIComponent(DETAIL_API_KEY)}`;
                try {
                    const res = await fetch(url, { method: 'GET', headers: { accept: 'text/plain' } });
                    if (!res.ok) return { id, pass: false };
                    const text = await res.text();
                    if (!text || !text.trim()) return { id, pass: false };
                    try {
                        const data = JSON.parse(text);
                        return { id, pass: !!(data && (data.result || data.code === 'ok' || data.code === 200 || data.id)) };
                    } catch (_) {
                        return { id, pass: true };
                    }
                } catch (_) {
                    return { id, pass: false };
                }
            }));

            checkedCount += batchResults.length;
            batchResults.forEach(item => { if (item.pass) passedIds.push(item.id); });
            appendVerifyLog(`Đã quét ${checkedCount}/${ids.length} ID. Pass hiện tại: ${passedIds.length}.`, 'info');
        }

        if (passedIds.length > 0) {
            appendVerifyLog(`Các id đã được import thành công: ${passedIds.join(', ')}`, 'success');
        } else {
            appendVerifyLog('Không có ID nào pass khi kiểm tra detail API.', 'warn');
        }
        appendVerifyLog(`Hoàn tất kiểm tra. Tổng pass: ${passedIds.length}/${ids.length}.`, 'success');
        Swal.fire('Hoàn tất', `Đã kiểm tra ${ids.length} ID. Danh sách pass hiển thị trong màn hình log.`, 'success');
    } finally {
        if (btnVerifyImportedIds) btnVerifyImportedIds.disabled = false;
        if (btnVerifyImportedIdsText) btnVerifyImportedIdsText.textContent = 'Kiểm tra ID';
        if (btnVerifyImportedIdsLoader) btnVerifyImportedIdsLoader.classList.add('hidden');
    }
}

function hasSavedCheckpoint() {
    return !!(processState.fileKey && localStorage.getItem(processState.fileKey));
}

function resetCurrentProgress({ clearSaved = false } = {}) {
    processState.shouldStop = true;
    processState.status = 'idle';
    processState.processedIndices = new Set();
    processState.results = [];
    processState.total = candidateRows.length;
    if (clearSaved) clearCheckpoint();
    if (checkpointInput) checkpointInput.value = '';
    processState.sourceFileName = fileInput?.files?.[0]?.name || processState.sourceFileName || '';
    if (resultContainer) resultContainer.classList.add('hidden');
    clearVerifyLog();
    setVerifyLogVisible(false);
    const resultTableBody = document.getElementById('resultTableBody');
    if (resultTableBody) resultTableBody.innerHTML = '';
    const resultTableHead = document.getElementById('resultTableHead');
    if (resultTableHead) resultTableHead.innerHTML = '';
}

// Startup: purge old bloated checkpoints (ones with 'results' inside localStorage)
(function purgeOldCheckpoints() {
    const keysToClean = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.startsWith('map4d_import_') || key.startsWith('map4d_del_'))) {
            try {
                const val = localStorage.getItem(key);
                if (val && val.length > 500000) { // > 500KB = old bloated format
                    keysToClean.push(key);
                }
            } catch(e) {}
        }
    }
    if (keysToClean.length > 0) {
        console.log(`Purging ${keysToClean.length} old bloated checkpoint(s) from localStorage`);
        keysToClean.forEach(k => localStorage.removeItem(k));
    }
})();

let _lastUIUpdate = 0;
function updateProgressUI(forceRender = false) {
    const count = processState.processedIndices.size;
    const total = processState.total;
    const percent = total > 0 ? ((count / total) * 100).toFixed(2) : 0;
    if(progressCountText) progressCountText.textContent = `${count}/${total} dòng | ${percent}%`;
    if(progressBar) progressBar.style.width = `${percent}%`;
    let statusText = 'Đang chờ';
    if (processState.status === 'running') statusText = 'Đang chạy';
    else if (processState.status === 'paused') statusText = 'Tạm dừng';
    else if (processState.status === 'completed') statusText = 'Hoàn thành';
    if(progressStatusText) progressStatusText.textContent = `Trạng thái: ${statusText}`;
    if(btnStartImport) {
        btnStartImport.classList.toggle('hidden', processState.status === 'running' || (processState.status === 'paused' && count > 0) || processState.status === 'completed');
        btnStartImport.textContent = count > 0 ? "Restart New" : "Start Import";
    }
    if(btnPauseImport) btnPauseImport.classList.toggle('hidden', processState.status !== 'running');
    if(btnResumeImport) btnResumeImport.classList.toggle('hidden', processState.status !== 'paused' || count === 0);
    const hasCheckpoint = hasSavedCheckpoint() || count > 0 || processState.results.length > 0;
    if(btnClearCheckpoint) btnClearCheckpoint.classList.toggle('hidden', !hasCheckpoint);
    if(btnDownloadResult) btnDownloadResult.classList.toggle('hidden', processState.results.length === 0);
    if(btnDownloadCheckpoint) btnDownloadCheckpoint.classList.toggle('hidden', processState.results.length === 0);
    const verifiedIds = getImportedIdsForVerification();
    const canVerifyIds = processState.status === 'completed' && verifiedIds.length > 0;
    if(btnVerifyImportedIds) btnVerifyImportedIds.classList.toggle('hidden', !canVerifyIds);

    if (processState.results.length > 0) {
        // Only render table per wave or when forced (pause/complete), not per row
        const now = Date.now();
        if (forceRender || now - _lastUIUpdate > 2000) {
            _lastUIUpdate = now;
            renderResultTable();
        }
        if(resultContainer) resultContainer.classList.remove('hidden');
    } else if(resultContainer) {
        resultContainer.classList.add('hidden');
    }
}

if(btnStartImport) btnStartImport.addEventListener('click', async () => {
    const isValid = await checkToken();
    if (!isValid) return;
    if (processState.processedIndices.size > 0) {
        const conf = await Swal.fire({ title: 'Bắt đầu lại?', text: "Tiến trình cũ sẽ bị xóa hết.", icon: 'warning', showCancelButton: true, confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy' });
        if (!conf.isConfirmed) return;
    }
    resetCurrentProgress({ clearSaved: true });
    processState.status = 'running';
    processState.shouldStop = false;
    processState.__actionLogWritten = false;
    updateProgressUI();
    processQueue();
});

if(btnPauseImport) btnPauseImport.addEventListener('click', () => { processState.shouldStop = true; processState.status = 'paused'; saveCheckpoint(); updateProgressUI(); });

if(btnResumeImport) btnResumeImport.addEventListener('click', async () => {
    const isValid = await checkToken();
    if (!isValid) return;
    processState.shouldStop = false;
    processState.status = 'running';
    updateProgressUI();
    processQueue();
});

if(btnClearCheckpoint) btnClearCheckpoint.addEventListener('click', async () => {
    if (!processState.fileKey) return Swal.fire('Lỗi', 'Vui lòng tải file dữ liệu trước.', 'error');
    const hasData = hasSavedCheckpoint() || processState.processedIndices.size > 0 || processState.results.length > 0;
    if (!hasData) return Swal.fire('Thông báo', 'Hiện chưa có checkpoint nào để xóa.', 'info');

    const conf = await Swal.fire({
        title: 'Xóa checkpoint?',
        text: 'Tiến trình đã lưu cho file hiện tại sẽ bị xóa khỏi trình duyệt.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Xóa',
        cancelButtonText: 'Hủy'
    });
    if (!conf.isConfirmed) return;

    resetCurrentProgress({ clearSaved: true });
    updateProgressUI(true);
    Swal.fire('Đã xóa', 'Checkpoint đã lưu đã được xóa.', 'success');
});

function writeImportActionLog() {
    if (!window.Map4DLogStore || processState.__actionLogWritten) return;
    const successCount = processState.results.filter(r => r.status === 'OK').length;
    const errorCount = Math.max(0, processState.results.length - successCount);
    const fileName = processState.sourceFileName || fileInput?.files?.[0]?.name || '';
    const area = Map4DLogStore.inferAreaFromText(fileName);
    Map4DLogStore.addLog({
        action: 'import_poi',
        area,
        poiCount: processState.total || processState.results.length,
        successCount,
        errorCount,
        fileName,
        status: errorCount > 0 ? 'warning' : 'success',
        source: 'import_poi_deploy',
        message: `Import file ${area} ${(processState.total || processState.results.length).toLocaleString('vi-VN')} POI`
    });
    processState.__actionLogWritten = true;
}

async function processQueue() {
    let pending = [];
    candidateRows.forEach((item, index) => { if (!processState.processedIndices.has(index)) pending.push({ ...item, candidateIndex: index }); });
    let pointer = 0;
    let rowsProcessedThisRun = 0;
    while (pointer < pending.length && rowsProcessedThisRun < IMPORT_CHUNK_SIZE && !processState.shouldStop) {
        const waveSize = Math.min(MAX_PARALLEL_REQUESTS, IMPORT_CHUNK_SIZE - rowsProcessedThisRun, pending.length - pointer);
        const wave = pending.slice(pointer, pointer + waveSize);
        pointer += waveSize;
        const promises = wave.map(async (item) => {
            const result = await uploadPlace(item.rowData);
            if (!processState.shouldStop) {
                processState.processedIndices.add(item.candidateIndex);
                rowsProcessedThisRun++;
                // Only store lightweight log (not full rowData) to save memory
                processState.results.push({
                    source_row: item.originalIndex + 2,
                    Name: item.rowData.Name || '',
                    time: new Date().toLocaleString('vi-VN'),
                    id: result.placeId || '',
                    status: result.status,
                    message: result.message
                });
                // Cập nhật UI liên tục
                updateProgressUI(false);
            }
            return { item, result };
        });
        const waveResults = await Promise.all(promises);
        let waveStopped = false; let stopReason = "";
        waveResults.forEach(({ item, result }) => { if (result.stop) { waveStopped = true; stopReason = result.message; } });
        saveCheckpoint();
        if (waveStopped) { const stopTitle = waveResults.some(({ result }) => result.authError) ? 'Lỗi xác thực' : 'Lỗi mạng'; processState.shouldStop = true; processState.status = 'paused'; saveCheckpoint(); updateProgressUI(true); Swal.fire(stopTitle, `Tạm dừng: ${stopReason}`, 'error'); break; }
    }
    if (processState.processedIndices.size >= processState.total) {
        processState.status = 'completed'; saveCheckpoint(); updateProgressUI(true); writeImportActionLog(); Swal.fire('Hoàn thành', 'Xử lý xong! Bạn có thể bấm Kiểm tra ID để rà lại các ID đã import.', 'success');
    } else if (!processState.shouldStop) setTimeout(processQueue, 500); 
}

function renderResultTable() {
    if (processState.results.length === 0) return;
    const logHeaders = ['source_row', 'Name', 'time', 'status', 'id', 'message'];
    const headEl = document.getElementById('resultTableHead');
    if(headEl) headEl.innerHTML = `<tr>${logHeaders.map(h => `<th class="px-4 py-2 bg-gray-50">${h}</th>`).join('')}</tr>`;
    const displayData = [...processState.results].reverse().slice(0, 30);
    const bodyEl = document.getElementById('resultTableBody');
    if(bodyEl) bodyEl.innerHTML = displayData.map(row => `<tr>${logHeaders.map(h => {
        let val = row[h] === undefined || row[h] === null ? '' : row[h];
        let cls = "px-4 py-2 whitespace-nowrap text-gray-700";
        if(h === 'status' && val === 'OK') cls += " text-green-600 font-bold";
        if(h === 'status' && (val === 'FAIL' || val === 'ERROR')) cls += " text-red-600 font-bold";
        return `<td class="${cls}">${val}</td>`;
    }).join('')}</tr>`).join('');
}

if(btnDownloadResult) btnDownloadResult.addEventListener('click', () => {
    if (processState.results.length === 0) return;
    const logHeaders = ['source_row', 'Name', 'time', 'status', 'id', 'message'];
    let csvContent = "\uFEFF" + logHeaders.join(",") + "\n";
    [...processState.results].sort((a,b) => a.source_row - b.source_row).forEach(row => {
        const rowArray = logHeaders.map(h => {
            let val = row[h] === undefined || row[h] === null ? '' : String(row[h]);
            if (val.includes(',') || val.includes('"') || val.includes('\n')) val = `"${val.replace(/"/g, '""')}"`;
            return val;
        });
        csvContent += rowArray.join(",") + "\n";
    });
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.setAttribute("href", url); link.setAttribute("download", "import_result.csv");
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
});

if(btnVerifyImportedIds) btnVerifyImportedIds.addEventListener('click', verifyImportedIds);
if(btnClearVerifyLog) btnClearVerifyLog.addEventListener('click', () => { clearVerifyLog(); setVerifyLogVisible(false); });

if(btnDownloadCheckpoint) btnDownloadCheckpoint.addEventListener('click', () => {
    if(!processState.fileKey) return;
    // Build full checkpoint with results for download
    const fullCheckpoint = {
        status: processState.status,
        processedIndices: Array.from(processState.processedIndices),
        results: processState.results
    };
    const dataStr = JSON.stringify(fullCheckpoint, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = `checkpoint_${processState.fileKey}.json`;
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
});
