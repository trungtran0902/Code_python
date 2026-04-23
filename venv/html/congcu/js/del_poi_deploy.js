const API_BASE_URL = "https://api-data.map4d.vn/map/manage/place/delete/";
const MAX_PARALLEL_REQUESTS = 20; 
const DELETE_CHUNK_SIZE = 100; 

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
const modeRadios = document.getElementsByName('mode');
const manualModeContainer = document.getElementById('manualModeContainer');
const fileModeContainer = document.getElementById('fileModeContainer');
const manualIdInput = document.getElementById('manualIdInput');
const btnDeleteManual = document.getElementById('btnDeleteManual');
const fileInput = document.getElementById('fileInput');
const checkpointInput = document.getElementById('checkpointInput');
const filePreviewContainer = document.getElementById('filePreviewContainer');
const previewTableHead = document.getElementById('previewTableHead');
const previewTableBody = document.getElementById('previewTableBody');
const idColumnSelect = document.getElementById('idColumnSelect');
const validRowsCount = document.getElementById('validRowsCount');

const btnStartDelete = document.getElementById('btnStartDelete');
const btnPauseDelete = document.getElementById('btnPauseDelete');
const btnResumeDelete = document.getElementById('btnResumeDelete');
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
        const textEl = document.getElementById('btnCheckTokenText');
        const loaderEl = document.getElementById('btnCheckTokenLoader');
        if(textEl) textEl.classList.add('hidden');
        if(loaderEl) loaderEl.classList.remove('hidden');
    }

    try {
        const res = await fetch(`${API_BASE_URL}test_invalid_id`, {
            method: 'POST',
            headers: getHeaders()
        });
        
        if (showPopup) {
            const textEl = document.getElementById('btnCheckTokenText');
            const loaderEl = document.getElementById('btnCheckTokenLoader');
            if(textEl) textEl.classList.remove('hidden');
            if(loaderEl) loaderEl.classList.add('hidden');
        }

        if (res.status === 401) {
            tokenStatusMessage.textContent = 'Token không hợp lệ hoặc đã hết hạn (401).';
            tokenStatusMessage.className = 'mt-2 text-sm text-red-600 block';
            if(showPopup) Swal.fire('Lỗi', 'Token không hợp lệ hoặc đã hết hạn.', 'error');
            return false;
        }
        
        tokenStatusMessage.textContent = 'Token hợp lệ.';
        tokenStatusMessage.className = 'mt-2 text-sm text-green-600 block';
        if(showPopup) Swal.fire('Thành công', 'Token hợp lệ.', 'success');
        return true;

    } catch (err) {
        if (showPopup) {
            const textEl = document.getElementById('btnCheckTokenText');
            const loaderEl = document.getElementById('btnCheckTokenLoader');
            if(textEl) textEl.classList.remove('hidden');
            if(loaderEl) loaderEl.classList.add('hidden');
        }
        tokenStatusMessage.textContent = `Lỗi kết nối: ${err.message}`;
        tokenStatusMessage.className = 'mt-2 text-sm text-red-600 block';
        if(showPopup) Swal.fire('Lỗi Kết Nối', `Không thể kết nối API. Chi tiết: ${err.message}.`, 'error');
        return false;
    }
}

async function deletePlace(id) {
    try {
        const res = await fetch(`${API_BASE_URL}${id}`, {
            method: 'POST',
            headers: getHeaders()
        });
        if (res.ok) {
            return { success: true, message: 'Deleted successfully', stop: false };
        }
        const text = await res.text();
        return { success: false, message: `${res.status} - ${text}`, stop: false };
    } catch (err) {
        return { success: false, message: err.message, stop: true }; 
    }
}

// Event Listeners
if(btnCheckToken) btnCheckToken.addEventListener('click', () => checkToken(true));

modeRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
        if (e.target.value === 'manual') {
            manualModeContainer.classList.remove('hidden');
            fileModeContainer.classList.add('hidden');
        } else {
            manualModeContainer.classList.add('hidden');
            fileModeContainer.classList.remove('hidden');
        }
    });
});

if(btnDeleteManual) btnDeleteManual.addEventListener('click', async () => {
    const id = manualIdInput.value.trim();
    if (!id) return Swal.fire('Lỗi', 'Vui lòng nhập Place ID', 'error');
    const isValid = await checkToken(false);
    if (!isValid) return Swal.fire('Lỗi', 'Token không hợp lệ', 'error');

    const btn = btnDeleteManual;
    btn.disabled = true;
    btn.innerHTML = '<div class="loader"></div> Đang xóa...';

    const result = await deletePlace(id);
    
    btn.disabled = false;
    btn.innerHTML = 'Xóa POI';

    if (result.success) {
        Swal.fire('Thành công', `Đã xóa POI: ${id}`, 'success');
        manualIdInput.value = '';
    } else {
        Swal.fire('Thất bại', `Lỗi xóa POI: ${result.message}`, 'error');
    }
});

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
            if (data.processed_indices && !data.processedIndices) data.processedIndices = data.processed_indices;
            if (data.total_rows && !data.total) data.total = data.total_rows;

            // Load into memory directly (NOT localStorage to avoid 5MB limit)
            const indices = data.processedIndices || [];
            processState.processedIndices = new Set(indices);
            processState.results = (data.results || []).map(r => ({
                source_row: r.source_row || 0,
                id: r.id || '',
                time: r.time || '',
                status: r.status || '',
                message: r.message || ''
            }));
            processState.status = 'paused';
            processState.total = candidateRows.length || data.total || 0;

            try {
                localStorage.removeItem(processState.fileKey);
                localStorage.setItem(processState.fileKey, JSON.stringify({
                    status: 'paused',
                    processedIndices: indices
                }));
            } catch(e) { console.warn('localStorage save skipped'); }

            updateProgressUI(true);
            Swal.fire('Thành công', `Đã nạp checkpoint: ${indices.length} dòng đã xử lý.`, 'success');
        } catch(err) {
            console.error("Checkpoint Load Error:", err);
            Swal.fire('Lỗi', 'File Checkpoint không hợp lệ: ' + err.message, 'error');
        }
    };
    reader.readAsText(file);
});

if(fileInput) fileInput.addEventListener('change', (e) => {
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
            renderPreviewTable(globalHeaders, json.slice(0, 5)); 
            
            idColumnSelect.innerHTML = '';
            let hasIdCol = false;
            globalHeaders.forEach(h => {
                const option = document.createElement('option');
                option.value = h;
                option.textContent = h;
                idColumnSelect.appendChild(option);
                if (h.toLowerCase().includes('id') && !hasIdCol) {
                    option.selected = true;
                    hasIdCol = true;
                }
            });

            updateCandidateCount();
            filePreviewContainer.classList.remove('hidden');
            
            const hashStr = file.name + file.size + file.lastModified;
            const hashCode = s => s.split('').reduce((a,b)=>{a=((a<<5)-a)+b.charCodeAt(0);return a&a},0);
            processState.fileKey = `map4d_del_${hashCode(hashStr)}`;
            
            loadCheckpoint();
        } else {
            Swal.fire('Lỗi', 'File không có dữ liệu', 'error');
        }
    };
    reader.readAsArrayBuffer(file);
});

if(idColumnSelect) idColumnSelect.addEventListener('change', updateCandidateCount);

function updateCandidateCount() {
    const col = idColumnSelect.value;
    candidateRows = [];
    globalData.forEach((row, idx) => {
        const idVal = row[col];
        if (idVal !== undefined && idVal !== null && String(idVal).trim() !== '' && String(idVal).trim().toLowerCase() !== 'nan') {
            candidateRows.push({ originalIndex: idx, rowData: row, id: String(idVal).trim() });
        }
    });
    validRowsCount.value = candidateRows.length;
    processState.total = candidateRows.length;
    updateProgressUI();
}

function renderPreviewTable(headers, data) {
    previewTableHead.innerHTML = `<tr>${headers.map(h => `<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${h}</th>`).join('')}</tr>`;
    previewTableBody.innerHTML = data.map(row => 
        `<tr>${headers.map(h => `<td class="px-6 py-4 whitespace-nowrap text-gray-700">${row[h] || ''}</td>`).join('')}</tr>`
    ).join('');
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
        } catch(e) {
            console.error("Error loading checkpoint from localStorage:", e);
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
    const data = JSON.stringify({
        status: processState.status,
        processedIndices: Array.from(processState.processedIndices)
    });
    try {
        localStorage.setItem(processState.fileKey, data);
    } catch(e) {
        console.warn('localStorage quota exceeded, clearing old data...');
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('map4d_')) keysToRemove.push(key);
        }
        keysToRemove.forEach(k => localStorage.removeItem(k));
        try { localStorage.setItem(processState.fileKey, data); } catch(e2) {}
    }
}

function clearCheckpoint() {
    if(!processState.fileKey) return;
    localStorage.removeItem(processState.fileKey);
}

// Startup: purge old bloated checkpoints
(function purgeOldCheckpoints() {
    for (let i = localStorage.length - 1; i >= 0; i--) {
        const key = localStorage.key(i);
        if (key && key.startsWith('map4d_')) {
            try {
                const val = localStorage.getItem(key);
                if (val && val.length > 500000) localStorage.removeItem(key);
            } catch(e) {}
        }
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

    if(btnStartDelete) {
        btnStartDelete.classList.toggle('hidden', processState.status === 'running' || (processState.status === 'paused' && count > 0) || processState.status === 'completed');
        if (count > 0 && processState.status !== 'completed' && processState.status !== 'running') {
            btnStartDelete.classList.remove('hidden');
            btnStartDelete.textContent = "Restart New";
        } else {
            btnStartDelete.textContent = "Start Delete";
        }
    }

    if(btnPauseDelete) btnPauseDelete.classList.toggle('hidden', processState.status !== 'running');
    if(btnResumeDelete) btnResumeDelete.classList.toggle('hidden', processState.status !== 'paused' || count === 0);
    
    if (processState.results.length > 0) {
        if(btnDownloadResult) btnDownloadResult.classList.remove('hidden');
        if(btnDownloadCheckpoint) btnDownloadCheckpoint.classList.remove('hidden');
        const now = Date.now();
        if (forceRender || now - _lastUIUpdate > 2000) {
            _lastUIUpdate = now;
            renderResultTable();
        }
        if(resultContainer) resultContainer.classList.remove('hidden');
    }
}

if(btnStartDelete) btnStartDelete.addEventListener('click', async () => {
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

if(btnPauseDelete) btnPauseDelete.addEventListener('click', () => {
    processState.shouldStop = true;
    processState.status = 'paused';
    saveCheckpoint();
    updateProgressUI();
});

if(btnResumeDelete) btnResumeDelete.addEventListener('click', async () => {
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

    while (pointer < pending.length && rowsProcessedThisRun < DELETE_CHUNK_SIZE && !processState.shouldStop) {
        const waveSize = Math.min(MAX_PARALLEL_REQUESTS, DELETE_CHUNK_SIZE - rowsProcessedThisRun, pending.length - pointer);
        const wave = pending.slice(pointer, pointer + waveSize);
        pointer += waveSize;

        const promises = wave.map(async (item) => {
            const result = await deletePlace(item.id);
            if (!processState.shouldStop) {
                processState.processedIndices.add(item.candidateIndex);
                rowsProcessedThisRun++;
                processState.results.push({
                    source_row: item.originalIndex + 2, 
                    time: new Date().toLocaleString('vi-VN'),
                    id: item.id,
                    status: result.success ? 'success' : 'error',
                    message: result.message
                });
            }
            return { item, result };
        });

        const waveResults = await Promise.all(promises);
        let waveStopped = false;
        let stopReason = "";
        waveResults.forEach(({ item, result }) => {
            if (result.stop) { waveStopped = true; stopReason = result.message; }
        });

        updateProgressUI(false);
        saveCheckpoint();

        if (waveStopped) {
            processState.shouldStop = true;
            processState.status = 'paused';
            saveCheckpoint();
            updateProgressUI(true);
            Swal.fire('Lỗi mạng', `Tạm dừng: ${stopReason}`, 'error');
            break;
        }
    }

    if (processState.processedIndices.size >= processState.total) {
        processState.status = 'completed';
        saveCheckpoint();
        updateProgressUI(true);
        Swal.fire('Hoàn thành', 'Đã xử lý xong tất cả!', 'success');
    } else if (!processState.shouldStop) {
        setTimeout(processQueue, 50); 
    }
}

function renderResultTable() {
    if (processState.results.length === 0) return;
    const logHeaders = ['source_row', 'time', 'id', 'status', 'message'];
    const headEl = document.getElementById('resultTableHead');
    if(headEl) headEl.innerHTML = `<tr>${logHeaders.map(h => `<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50">${h}</th>`).join('')}</tr>`;
    const displayData = [...processState.results].reverse().slice(0, 30);
    const bodyEl = document.getElementById('resultTableBody');
    if(bodyEl) bodyEl.innerHTML = displayData.map(row => 
        `<tr>${logHeaders.map(h => {
            let val = row[h] === undefined || row[h] === null ? '' : row[h];
            let cls = "px-4 py-2 whitespace-nowrap text-gray-700";
            if(h === 'status' && val === 'success') cls += " text-green-600 font-bold";
            if(h === 'status' && val === 'error') cls += " text-red-600 font-bold";
            return `<td class="${cls}">${val}</td>`;
        }).join('')}</tr>`
    ).join('');
}

if(btnDownloadResult) btnDownloadResult.addEventListener('click', () => {
    if (processState.results.length === 0) return;
    const logHeaders = ['source_row', 'time', 'id', 'status', 'message'];
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
    const link = document.createElement("a"); link.setAttribute("href", url); link.setAttribute("download", "delete_result.csv");
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
});

if(btnDownloadCheckpoint) btnDownloadCheckpoint.addEventListener('click', () => {
    if(!processState.fileKey) return;
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
