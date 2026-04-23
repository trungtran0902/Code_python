const API_BASE_URL = "https://api-data.map4d.vn/map/manage/place";
const MAX_PARALLEL_REQUESTS = 20; 
const IMPORT_CHUNK_SIZE = 100; 
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
    fileKey: ''
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

const progressStatusText = document.getElementById('progressStatusText');
const progressCountText = document.getElementById('progressCountText');
const progressBar = document.getElementById('progressBar');
const resultContainer = document.getElementById('resultContainer');

// Helpers
function getHeaders() {
    return {
        "accept": "text/plain",
        "Content-Type": "application/json",
        "Authorization": tokenInput.value.trim()
    };
}

async function checkToken(showPopup = true) {
    const token = tokenInput.value.trim();
    if (!token) {
        if(showPopup) Swal.fire('Lỗi', 'Vui lòng nhập Authorization Token', 'error');
        return false;
    }

    if(showPopup) {
        document.getElementById('btnCheckTokenText').classList.add('hidden');
        document.getElementById('btnCheckTokenLoader').classList.remove('hidden');
    }

    try {
        const res = await fetch(API_BASE_URL, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({}) // Empty body to test token
        });
        
        if (showPopup) {
            document.getElementById('btnCheckTokenText').classList.remove('hidden');
            document.getElementById('btnCheckTokenLoader').classList.add('hidden');
        }

        if (res.status === 401 || res.status === 403) {
            tokenStatusMessage.textContent = 'Token không hợp lệ hoặc đã hết hạn (401/403).';
            tokenStatusMessage.className = 'mt-2 text-sm text-red-600 block';
            if(showPopup) Swal.fire('Lỗi', 'Token không hợp lệ hoặc không có quyền.', 'error');
            return false;
        }
        
        tokenStatusMessage.textContent = 'Token hợp lệ.';
        tokenStatusMessage.className = 'mt-2 text-sm text-green-600 block';
        if(showPopup) Swal.fire('Thành công', 'Token hợp lệ.', 'success');
        return true;

    } catch (err) {
        if (showPopup) {
            document.getElementById('btnCheckTokenText').classList.remove('hidden');
            document.getElementById('btnCheckTokenLoader').classList.add('hidden');
        }
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
        if (parts.length >= 2) {
            return `${parts[0].padStart(2, '0')}${parts[1].padStart(2, '0')}`;
        }
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
        
        normalizedItems.push({
            open: { day: dayOpen, time: timeOpen },
            close: { day: dayClose, time: timeClose }
        });
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

// --- Row Validation & Upload ---
function parseMultiValue(val) {
    if (isBlank(val)) return [];
    return String(val).split(',').map(v => v.trim()).filter(v => v !== '');
}

function validateRow(row) {
    for (let field of REQUIRED_COLUMNS) {
        if (isBlank(row[field])) {
            return { valid: false, message: `Thiếu dữ liệu bắt buộc ở cột '${field}'.`, type: 'missing_required_value' };
        }
    }

    let lat = parseFloat(row.Latitude);
    let lng = parseFloat(row.Longitude);
    if (isNaN(lat)) return { valid: false, message: `Cột 'Latitude' không phải định dạng số.`, type: 'invalid_number' };
    if (isNaN(lng)) return { valid: false, message: `Cột 'Longitude' không phải định dạng số.`, type: 'invalid_number' };
    if (lat < -90 || lat > 90) return { valid: false, message: `Latitude phải từ -90 đến 90.`, type: 'out_of_range' };
    if (lng < -180 || lng > 180) return { valid: false, message: `Longitude phải từ -180 đến 180.`, type: 'out_of_range' };

    let bHours = [];
    try {
        bHours = getBusinessHours(row);
    } catch (e) {
        return { valid: false, message: e.message, type: 'invalid_structure' };
    }

    return { valid: true, bHours: bHours, lat, lng };
}

async function uploadPlace(row) {
    let val = validateRow(row);
    if (!val.valid) {
        return { status: 'INVALID', placeId: null, message: val.message, stop: false };
    }

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
        geometry: {
            type: "Point",
            coordinates: [val.lng, val.lat]
        },
        rank: { value: 0 },
        layer: "address",
        source: null,
        metadata: []
    };

    if (val.bHours && val.bHours.length > 0) {
        place.businessHours = val.bHours;
    }

    try {
        const res = await fetch(API_BASE_URL, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(place)
        });
        
        if (res.status === 200 || res.status === 201) {
            const respJson = await res.json();
            let placeId = null;
            if (respJson && respJson.result && respJson.result.id) placeId = respJson.result.id;
            if (!placeId && respJson.id) placeId = respJson.id;
            if (!placeId && respJson.placeId) placeId = respJson.placeId;
            
            if (placeId) {
                return { status: 'OK', placeId: placeId, message: 'Uploaded', stop: false };
            } else {
                return { status: 'FAIL', placeId: null, message: 'Thành công nhưng không trả về ID', stop: false };
            }
        } else {
            const text = await res.text();
            return { status: 'FAIL', placeId: null, message: `${res.status} - ${text}`, stop: false };
        }
    } catch (err) {
        return { status: 'ERROR', placeId: null, message: err.message, stop: true };
    }
}

// Event Listeners
btnCheckToken.addEventListener('click', () => checkToken(true));

checkpointInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            const data = JSON.parse(ev.target.result);
            if(!processState.fileKey) {
                Swal.fire('Lỗi', 'Vui lòng upload file Excel/CSV trước khi nạp checkpoint!', 'error');
                checkpointInput.value = '';
                return;
            }
            localStorage.setItem(processState.fileKey, JSON.stringify(data));
            loadCheckpoint();
            Swal.fire('Thành công', 'Đã nạp checkpoint thành công!', 'success');
        } catch(err) {
            Swal.fire('Lỗi', 'File Checkpoint không hợp lệ!', 'error');
        }
    };
    reader.readAsText(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) {
        filePreviewContainer.classList.add('hidden');
        return;
    }

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
            if (missing.length > 0) {
                Swal.fire('Lỗi cấu trúc', `File thiếu các cột bắt buộc: ${missing.join(', ')}`, 'error');
                fileInput.value = '';
                return;
            }

            renderPreviewTable(globalHeaders, json.slice(0, 5)); 
            
            candidateRows = json.map((r, i) => ({ originalIndex: i, rowData: r }));
            totalRowsCount.textContent = candidateRows.length;
            processState.total = candidateRows.length;
            filePreviewContainer.classList.remove('hidden');
            
            const hashStr = file.name + file.size + file.lastModified;
            const hashCode = s => s.split('').reduce((a,b)=>{a=((a<<5)-a)+b.charCodeAt(0);return a&a},0);
            processState.fileKey = `map4d_import_${hashCode(hashStr)}`;
            
            loadCheckpoint();
        } else {
            Swal.fire('Lỗi', 'File không có dữ liệu', 'error');
        }
    };
    reader.readAsArrayBuffer(file);
});

function renderPreviewTable(headers, data) {
    previewTableHead.innerHTML = `<tr>${headers.map(h => `<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${h}</th>`).join('')}</tr>`;
    previewTableBody.innerHTML = data.map(row => 
        `<tr>${headers.map(h => `<td class="px-6 py-4 whitespace-nowrap text-gray-700">${row[h] || ''}</td>`).join('')}</tr>`
    ).join('');
}

function loadCheckpoint() {
    const saved = localStorage.getItem(processState.fileKey);
    if (saved) {
        const parsed = JSON.parse(saved);
        processState.status = parsed.status === 'running' ? 'paused' : parsed.status;
        processState.processedIndices = new Set(parsed.processedIndices);
        processState.results = parsed.results || [];
        
        if (processState.processedIndices.size > 0) {
            Swal.fire({
                title: 'Phát hiện tiến trình cũ',
                text: `Bạn đã xử lý ${processState.processedIndices.size}/${processState.total} dòng trước đó.`,
                icon: 'info',
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 3000
            });
        }
    } else {
        processState.status = 'idle';
        processState.processedIndices = new Set();
        processState.results = [];
    }
    updateProgressUI();
}

function saveCheckpoint() {
    if(!processState.fileKey) return;
    localStorage.setItem(processState.fileKey, JSON.stringify({
        status: processState.status,
        processedIndices: Array.from(processState.processedIndices),
        results: processState.results
    }));
}

function clearCheckpoint() {
    if(!processState.fileKey) return;
    localStorage.removeItem(processState.fileKey);
}

function updateProgressUI() {
    const count = processState.processedIndices.size;
    const total = processState.total;
    const percent = total > 0 ? ((count / total) * 100).toFixed(2) : 0;
    
    progressCountText.textContent = `${count}/${total} dòng | ${percent}%`;
    progressBar.style.width = `${percent}%`;
    
    let statusText = 'Đang chờ';
    if (processState.status === 'running') statusText = 'Đang chạy';
    else if (processState.status === 'paused') statusText = 'Tạm dừng';
    else if (processState.status === 'completed') statusText = 'Hoàn thành';
    
    progressStatusText.textContent = `Trạng thái: ${statusText}`;

    btnStartImport.classList.toggle('hidden', processState.status === 'running' || (processState.status === 'paused' && count > 0) || processState.status === 'completed');
    if (count > 0 && processState.status !== 'completed' && processState.status !== 'running') {
        btnStartImport.classList.remove('hidden');
        btnStartImport.textContent = "Restart New";
    } else {
        btnStartImport.textContent = "Start Import";
    }

    btnPauseImport.classList.toggle('hidden', processState.status !== 'running');
    btnResumeImport.classList.toggle('hidden', processState.status !== 'paused' || count === 0);
    
    if (processState.results.length > 0) {
        btnDownloadResult.classList.remove('hidden');
        btnDownloadCheckpoint.classList.remove('hidden');
        renderResultTable();
        resultContainer.classList.remove('hidden');
    }
}

btnStartImport.addEventListener('click', async () => {
    const isValid = await checkToken();
    if (!isValid) return;

    if (processState.processedIndices.size > 0) {
        const conf = await Swal.fire({
            title: 'Bắt đầu lại?',
            text: "Tiến trình cũ sẽ bị xóa hết.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Đồng ý',
            cancelButtonText: 'Hủy'
        });
        if (!conf.isConfirmed) return;
    }
    
    clearCheckpoint();
    processState.processedIndices = new Set();
    processState.results = [];
    processState.status = 'running';
    processState.shouldStop = false;
    updateProgressUI();
    processQueue();
});

btnPauseImport.addEventListener('click', () => {
    processState.shouldStop = true;
    processState.status = 'paused';
    saveCheckpoint();
    updateProgressUI();
});

btnResumeImport.addEventListener('click', async () => {
    const isValid = await checkToken();
    if (!isValid) return;

    processState.shouldStop = false;
    processState.status = 'running';
    updateProgressUI();
    processQueue();
});

async function processQueue() {
    let pending = [];
    candidateRows.forEach((item, index) => {
        if (!processState.processedIndices.has(index)) {
            pending.push({ ...item, candidateIndex: index });
        }
    });

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
                
                const logRow = {
                    source_row: item.originalIndex + 2,
                    time: new Date().toLocaleString('vi-VN'),
                    id: result.placeId || '',
                    status: result.status,
                    message: result.message
                };
                
                processState.results.push({ ...item.rowData, ...logRow });
                updateProgressUI();
            }

            return { item, result };
        });

        const waveResults = await Promise.all(promises);
        
        let waveStopped = false;
        let stopReason = "";

        waveResults.forEach(({ item, result }) => {
            if (result.stop) {
                waveStopped = true;
                stopReason = result.message;
            }
        });

        saveCheckpoint();

        if (waveStopped) {
            processState.shouldStop = true;
            processState.status = 'paused';
            saveCheckpoint();
            updateProgressUI();
            Swal.fire('Lỗi mạng', `Tiến trình đã tạm dừng do lỗi: ${stopReason}`, 'error');
            break;
        }
    }

    if (processState.processedIndices.size >= processState.total) {
        processState.status = 'completed';
        saveCheckpoint();
        updateProgressUI();
        Swal.fire('Hoàn thành', 'Đã xử lý xong tất cả dữ liệu!', 'success');
    } else if (!processState.shouldStop) {
        setTimeout(processQueue, 50); 
    }
}

function renderResultTable() {
    if (processState.results.length === 0) return;
    
    const logCols = ['source_row', 'time', 'status', 'id', 'message'];
    const allHeaders = [...globalHeaders, ...logCols.filter(c => !globalHeaders.includes(c))];
    
    document.getElementById('resultTableHead').innerHTML = `<tr>${allHeaders.map(h => `<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50">${h}</th>`).join('')}</tr>`;
    
    const displayData = [...processState.results].reverse().slice(0, 50);
    
    document.getElementById('resultTableBody').innerHTML = displayData.map(row => 
        `<tr>${allHeaders.map(h => {
            let val = row[h] === undefined || row[h] === null ? '' : row[h];
            let cls = "px-4 py-2 whitespace-nowrap text-gray-700";
            if(h === 'status' && val === 'OK') cls += " text-green-600 font-bold";
            if(h === 'status' && (val === 'ERROR' || val === 'FAIL' || val === 'INVALID')) cls += " text-red-600 font-bold";
            return `<td class="${cls}">${val}</td>`;
        }).join('')}</tr>`
    ).join('');
}

btnDownloadResult.addEventListener('click', () => {
    if (processState.results.length === 0) return;
    
    const logCols = ['source_row', 'time', 'status', 'id', 'message'];
    const allHeaders = [...globalHeaders, ...logCols.filter(c => !globalHeaders.includes(c))];
    
    let csvContent = "\uFEFF"; 
    csvContent += allHeaders.join(",") + "\n";
    
    processState.results.sort((a,b) => a.source_row - b.source_row).forEach(row => {
        const rowArray = allHeaders.map(h => {
            let val = row[h] === undefined || row[h] === null ? '' : String(row[h]);
            if (val.includes(',') || val.includes('"') || val.includes('\n')) {
                val = `"${val.replace(/"/g, '""')}"`;
            }
            return val;
        });
        csvContent += rowArray.join(",") + "\n";
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "import_result.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

btnDownloadCheckpoint.addEventListener('click', () => {
    if(!processState.fileKey) return;
    const dataStr = localStorage.getItem(processState.fileKey);
    if(!dataStr) return;
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `checkpoint_${processState.fileKey}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});
