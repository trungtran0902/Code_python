const excelInput = document.getElementById('excelInput');
const fileStatus = document.getElementById('fileStatus');
const mainContent = document.getElementById('mainContent');
const totalRows = document.getElementById('totalRows');
const totalCols = document.getElementById('totalCols');
const compareMode = document.getElementById('compareMode');
const viewMode = document.getElementById('viewMode');
const resultContainer = document.getElementById('resultContainer');
const resultHead = document.getElementById('resultHead');
const resultBody = document.getElementById('resultBody');
const resultCount = document.getElementById('resultCount');
const btnDownload = document.getElementById('btnDownload');
const jsonHint = document.getElementById('jsonHint');
const btnShowMap = document.getElementById('btnShowMap');
const btnFitMap = document.getElementById('btnFitMap');
const mapPanel = document.getElementById('mapPanel');
const mapSummary = document.getElementById('mapSummary');
const jsonPreviewPanel = document.getElementById('jsonPreviewPanel');
const jsonPreview = document.getElementById('jsonPreview');

const cN1 = document.getElementById('cN1'), cA1 = document.getElementById('cA1'), cLat1 = document.getElementById('cLat1'), cLng1 = document.getElementById('cLng1');
const cN2 = document.getElementById('cN2'), cA2 = document.getElementById('cA2'), cLat2 = document.getElementById('cLat2'), cLng2 = document.getElementById('cLng2');

const nameThr = document.getElementById('nameThr'), nameThrVal = document.getElementById('nameThrVal');
const addrThr = document.getElementById('addrThr'), addrThrVal = document.getElementById('addrThrVal');
const distThr = document.getElementById('distThr'), distThrVal = document.getElementById('distThrVal');
const btnRunCompare = document.getElementById('btnRunCompare');
const loaderCompare = document.getElementById('loaderCompare');

const filterColOnly = document.getElementById('filterColOnly');
const filterKeywordOnly = document.getElementById('filterKeywordOnly');

const filterSection = document.getElementById('filterSection');
const filterConditions = document.getElementById('filterConditions');
const btnAddFilter = document.getElementById('btnAddFilter');

let globalData = [];
let globalHeaders = [];
let resultData = [];
let filteredData = [];
let currentMode = 'compare';
let activeFilters = [];
let currentFileType = 'excel';
let rawJsonData = null;
let coordinatePoints = [];
let jsonMap = null;
let jsonMapMarkers = [];

nameThr.addEventListener('input', e => nameThrVal.textContent = e.target.value);
addrThr.addEventListener('input', e => addrThrVal.textContent = e.target.value);
distThr.addEventListener('input', e => distThrVal.textContent = e.target.value);

document.querySelectorAll('input[name="toolMode"]').forEach(rad => {
    rad.addEventListener('change', (e) => {
        currentMode = e.target.value;
        if(currentMode === 'compare') {
            compareMode.classList.remove('hidden');
            viewMode.classList.add('hidden');
            filterSection.classList.add('hidden');
        } else {
            compareMode.classList.add('hidden');
            viewMode.classList.remove('hidden');
            filterSection.classList.add('hidden');
            resultData = [...globalData];
            applyFilters();
            resultContainer.classList.remove('hidden');
        }
    });
});

excelInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;

    resetFileState();
    const ext = file.name.split('.').pop().toLowerCase();
    currentFileType = ext === 'json' ? 'json' : 'excel';
    fileStatus.textContent = 'Đang đọc file...';
    jsonHint.classList.toggle('hidden', currentFileType !== 'json');

    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            if (currentFileType === 'json') {
                handleJsonFile(ev.target.result, file.name);
            } else {
                handleExcelFile(ev.target.result, file.name);
            }
        } catch(err) {
            console.error(err);
            fileStatus.textContent = 'Lỗi đọc file';
            Swal.fire('Lỗi', currentFileType === 'json' ? 'Không thể đọc file JSON hợp lệ' : 'Không thể đọc file Excel', 'error');
        }
    };

    if (currentFileType === 'json') reader.readAsText(file, 'utf-8');
    else reader.readAsArrayBuffer(file);
});

function resetFileState() {
    globalData = [];
    globalHeaders = [];
    resultData = [];
    filteredData = [];
    activeFilters = [];
    rawJsonData = null;
    coordinatePoints = [];
    filterConditions.innerHTML = '';
    resultHead.innerHTML = '';
    resultBody.innerHTML = '';
    resultCount.textContent = '0 dòng';
    mapPanel.classList.add('hidden');
    jsonPreviewPanel.classList.add('hidden');
    btnShowMap.classList.add('hidden');
    clearJsonMapMarkers();
}

function handleExcelFile(arrayBuffer, fileName) {
    const data = new Uint8Array(arrayBuffer);
    const workbook = XLSX.read(data, {type: 'array'});
    globalData = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {defval: ""});

    if(globalData.length > 0) {
        globalHeaders = Object.keys(globalData[0]);
        totalRows.textContent = globalData.length;
        totalCols.textContent = globalHeaders.length;
        populateSelects();
        mainContent.classList.remove('hidden');
        fileStatus.textContent = `Đã nạp ${globalData.length} dòng từ ${fileName}.`;
    } else {
        fileStatus.textContent = 'File trống';
    }
}

function handleJsonFile(text, fileName) {
    rawJsonData = JSON.parse(text);
    globalData = jsonToRows(rawJsonData);
    coordinatePoints = extractCoordinates(rawJsonData);

    if (globalData.length === 0) {
        globalData = [{ json_preview: JSON.stringify(rawJsonData).slice(0, 3000) }];
    }

    globalHeaders = Array.from(new Set(globalData.flatMap(row => Object.keys(row))));
    totalRows.textContent = globalData.length;
    totalCols.textContent = globalHeaders.length;

    populateSelects();
    switchToViewMode();
    resultData = [...globalData];
    applyFilters();
    mainContent.classList.remove('hidden');
    resultContainer.classList.remove('hidden');
    filterSection.classList.remove('hidden');

    jsonPreview.textContent = JSON.stringify(rawJsonData, null, 2).slice(0, 50000);
    jsonPreviewPanel.classList.remove('hidden');

    if (coordinatePoints.length > 0) {
        btnShowMap.classList.remove('hidden');
        mapPanel.classList.remove('hidden');
        mapSummary.textContent = `Tìm thấy ${coordinatePoints.length} cặp lat/lng hợp lệ trong JSON.`;
        setTimeout(renderJsonMap, 80);
        Swal.fire('Đã quét tọa độ', `Tìm thấy ${coordinatePoints.length} cặp lat/lng hợp lệ và đã overlay lên basemap.`, 'success');
    } else {
        mapSummary.textContent = 'Không tìm thấy cặp lat/lng hợp lệ trong JSON.';
        Swal.fire('Đã đọc JSON', 'Không tìm thấy cặp lat/lng hợp lệ để overlay lên bản đồ.', 'info');
    }

    fileStatus.textContent = `Đã nạp JSON: ${fileName} · ${globalData.length} dòng xem · ${coordinatePoints.length} điểm tọa độ.`;
}

function switchToViewMode() {
    currentMode = 'view';
    const viewRadio = document.querySelector('input[name="toolMode"][value="view"]');
    if (viewRadio) viewRadio.checked = true;
    compareMode.classList.add('hidden');
    viewMode.classList.remove('hidden');
}

function jsonToRows(value) {
    let baseArray = [];
    if (Array.isArray(value)) baseArray = value;
    else if (value && typeof value === 'object') {
        const arrayKey = Object.keys(value).find(k => Array.isArray(value[k]) && value[k].some(item => item && typeof item === 'object'));
        baseArray = arrayKey ? value[arrayKey] : [value];
    } else baseArray = [{ value }];

    return baseArray.map((item, idx) => flattenJson(item, '', { STT: idx + 1 }));
}

function flattenJson(value, prefix = '', out = {}, depth = 0) {
    if (depth > 4) {
        out[prefix || 'value'] = JSON.stringify(value);
        return out;
    }
    if (Array.isArray(value)) {
        if (value.every(v => v === null || ['string', 'number', 'boolean'].includes(typeof v))) {
            out[prefix || 'array'] = value.join(', ');
        } else {
            value.slice(0, 10).forEach((v, i) => flattenJson(v, `${prefix}[${i}]`, out, depth + 1));
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
    const latKeys = ['lat', 'latitude', 'vi_do', 'vido', 'vĩ độ', 'y'];
    const lngKeys = ['lng', 'lon', 'long', 'longitude', 'kinh_do', 'kinhdo', 'kinh độ', 'x'];

    const normKey = key => String(key || '').toLowerCase().trim().replace(/[\s\-]+/g, '_');
    const isLatKey = key => latKeys.includes(normKey(key));
    const isLngKey = key => lngKeys.includes(normKey(key));
    const validLat = v => typeof v === 'number' && isFinite(v) && v >= -90 && v <= 90;
    const validLng = v => typeof v === 'number' && isFinite(v) && v >= -180 && v <= 180;
    const toNum = v => {
        if (v === null || v === undefined || v === '') return null;
        const n = Number(String(v).trim().replace(',', '.'));
        return Number.isFinite(n) ? n : null;
    };
    const addPoint = (lat, lng, path, source = {}) => {
        lat = toNum(lat); lng = toNum(lng);
        if (!validLat(lat) || !validLng(lng)) return;
        const key = `${lat.toFixed(7)},${lng.toFixed(7)},${path}`;
        if (seen.has(key)) return;
        seen.add(key);
        points.push({
            lat, lng, path,
            title: source.name || source.Name || source.title || source.address || source.Address || path,
            raw: source
        });
    };

    const walk = (node, path = '$', parentKey = '') => {
        if (Array.isArray(node)) {
            if (normKey(parentKey) === 'coordinates' && node.length >= 2) {
                // GeoJSON convention: [longitude, latitude]
                addPoint(node[1], node[0], path, {});
            }
            node.forEach((child, i) => walk(child, `${path}[${i}]`, parentKey));
            return;
        }
        if (!node || typeof node !== 'object') return;

        const entries = Object.entries(node);
        let latEntry = entries.find(([k]) => isLatKey(k));
        let lngEntry = entries.find(([k]) => isLngKey(k));
        if (latEntry && lngEntry) addPoint(latEntry[1], lngEntry[1], path, node);

        // GeoJSON Point geometry: { type: 'Point', coordinates: [lng, lat] }
        if (String(node.type || '').toLowerCase() === 'point' && Array.isArray(node.coordinates)) {
            addPoint(node.coordinates[1], node.coordinates[0], `${path}.coordinates`, node.properties || node);
        }

        entries.forEach(([k, v]) => walk(v, path === '$' ? `$.${k}` : `${path}.${k}`, k));
    };

    walk(root);
    return points;
}

function clearJsonMapMarkers() {
    if (jsonMapMarkers.length) {
        jsonMapMarkers.forEach(marker => { try { marker.remove(); } catch(e) {} });
        jsonMapMarkers = [];
    }
}

function renderJsonMap() {
    if (!coordinatePoints.length || !window.L) return;
    mapPanel.classList.remove('hidden');
    if (!jsonMap) {
        jsonMap = L.map('jsonMap').setView([10.762622, 106.660172], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(jsonMap);
    }

    clearJsonMapMarkers();
    const bounds = [];
    coordinatePoints.forEach((p, idx) => {
        const marker = L.marker([p.lat, p.lng]).addTo(jsonMap);
        const title = escapeHtml(p.title || `Point ${idx + 1}`);
        marker.bindPopup(`<b>${title}</b><br>Lat: ${p.lat}<br>Lng: ${p.lng}<br><small>${escapeHtml(p.path)}</small>`);
        jsonMapMarkers.push(marker);
        bounds.push([p.lat, p.lng]);
    });
    if (bounds.length) jsonMap.fitBounds(bounds, { padding: [24, 24] });
    setTimeout(() => jsonMap.invalidateSize(), 120);
}

function fitJsonMap() {
    if (!jsonMap || !coordinatePoints.length) return;
    jsonMap.fitBounds(coordinatePoints.map(p => [p.lat, p.lng]), { padding: [24, 24] });
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

function populateSelects() {
    const selects = [cN1, cA1, cLat1, cLng1, cN2, cA2, cLat2, cLng2, filterColOnly];
    selects.forEach(sel => {
        sel.innerHTML = '';
        globalHeaders.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            sel.appendChild(opt);
        });
    });
    
    // Auto detect
    autoDetect(cN1, ["Ten", "Name", "Nguon1_Ten", "PoiName"]);
    autoDetect(cN2, ["Name_Map4D", "Map4D_Name", "Nguon2_Ten"]);
    autoDetect(cLat1, ["Latitude", "Lat", "ViDo", "Vĩ độ", "Y"]);
    autoDetect(cLng1, ["Longitude", "Lng", "Long", "KinhDo", "Kinh_Do", "Kinh độ", "X"]);
    autoDetect(cLat2, ["Lat_Map4D", "Map4D_Lat", "Latitude_Map4D"]);
    autoDetect(cLng2, ["Lng_Map4D", "Map4D_Lng", "Longitude_Map4D", "Long_Map4D"]);
}

function autoDetect(sel, keywords) {
    const options = Array.from(sel.options);
    for(let k of keywords) {
        let match = options.find(o => o.value.toLowerCase().includes(k.toLowerCase()));
        if(match) {
            sel.value = match.value;
            break;
        }
    }
}

function normalizeText(text) {
    if(!text) return "";
    let str = String(text).trim().toLowerCase();
    // Normalize unicode
    str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    str = str.replace(/đ/g, "d");
    // Replace special chars with space
    str = str.replace(/[,.\-\/\\]+/g, " ");
    return str.replace(/\s+/g, " ").trim();
}

function safeFloat(val) {
    if(!val) return null;
    let numeric = parseFloat(String(val).replace(',', '.'));
    if(isNaN(numeric) || !isFinite(numeric)) return null;
    return numeric;
}

function calcDistance(lat1, lng1, lat2, lng2) {
    if(lat1 === null || lng1 === null || lat2 === null || lng2 === null) return null;
    // Haversine formula
    const R = 6371000; // meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c * 100) / 100;
}

// Levenshtein ratio helper (equivalent to SequenceMatcher.ratio())
function levenshteinRatio(s1, s2) {
    if (s1 === s2) return 1.0;
    const len1 = s1.length, len2 = s2.length;
    if (len1 === 0 || len2 === 0) return 0;
    const matrix = [];
    for (let i = 0; i <= len1; i++) {
        matrix[i] = [i];
        for (let j = 1; j <= len2; j++) {
            if (i === 0) { matrix[i][j] = j; }
            else {
                const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
                matrix[i][j] = Math.min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost
                );
            }
        }
    }
    const dist = matrix[len1][len2];
    return (len1 + len2 - dist) / (len1 + len2);
}

// Matches RapidFuzz fuzz.token_set_ratio:
// 1. Tokenize & create sets
// 2. Find intersection, diff1, diff2
// 3. Build: t0 = sorted(intersection), t1 = t0 + sorted(diff1), t2 = t0 + sorted(diff2)
// 4. Return max(ratio(t0,t1), ratio(t0,t2), ratio(t1,t2)) * 100
function tokenSetRatio(s1, s2) {
    if (!s1 || !s2) return 0;
    const tokens1 = new Set(s1.split(' ').filter(s=>s));
    const tokens2 = new Set(s2.split(' ').filter(s=>s));
    if (tokens1.size === 0 || tokens2.size === 0) return 0;

    const intersect = [...tokens1].filter(x => tokens2.has(x)).sort();
    const diff1 = [...tokens1].filter(x => !tokens2.has(x)).sort();
    const diff2 = [...tokens2].filter(x => !tokens1.has(x)).sort();

    const t0 = intersect.join(' ');
    const t1 = (intersect.concat(diff1)).join(' ');
    const t2 = (intersect.concat(diff2)).join(' ');

    const r1 = t0 ? levenshteinRatio(t0, t1) : 0;
    const r2 = t0 ? levenshteinRatio(t0, t2) : 0;
    const r3 = levenshteinRatio(t1, t2);

    return Math.round(Math.max(r1, r2, r3) * 100);
}

btnRunCompare.addEventListener('click', () => {
    btnRunCompare.disabled = true;
    loaderCompare.classList.remove('hidden');
    resultContainer.classList.add('hidden');
    
    setTimeout(() => {
        const nThr = parseInt(nameThr.value);
        const aThr = parseInt(addrThr.value);
        const dThr = parseInt(distThr.value);
        
        resultData = globalData.map(row => {
            let newRow = {...row};
            let t1 = normalizeText(row[cN1.value]);
            let a1 = normalizeText(row[cA1.value]);
            let lt1 = safeFloat(row[cLat1.value]);
            let lg1 = safeFloat(row[cLng1.value]);
            
            let t2 = normalizeText(row[cN2.value]);
            let a2 = normalizeText(row[cA2.value]);
            let lt2 = safeFloat(row[cLat2.value]);
            let lg2 = safeFloat(row[cLng2.value]);
            
            let nameScore = tokenSetRatio(t1, t2);
            let nameExact = (t1 === t2 && t1 !== "");
            
            if(nameExact) {
                newRow["Ket luan"] = "Trung quan (ten chinh xac)";
                newRow["Do tin cay (%)"] = 100;
                newRow["Diem giong ten"] = nameScore;
                newRow["Khoang cach (m)"] = null;
            } else if (nameScore >= nThr) {
                newRow["Ket luan"] = "Trung quan (ten gan dung)";
                newRow["Do tin cay (%)"] = nameScore;
                newRow["Diem giong ten"] = nameScore;
                newRow["Khoang cach (m)"] = null;
            } else {
                let addrScore = tokenSetRatio(a1, a2);
                if(addrScore >= aThr) {
                    newRow["Ket luan"] = "Trung dia chi";
                    newRow["Do tin cay (%)"] = addrScore;
                    newRow["Diem giong ten"] = nameScore;
                    newRow["Khoang cach (m)"] = null;
                } else {
                    let dist = calcDistance(lt1, lg1, lt2, lg2);
                    if(dist !== null && dist <= dThr) {
                        newRow["Ket luan"] = "Gan nhau nhung khac dia chi";
                        newRow["Do tin cay (%)"] = 40;
                        newRow["Diem giong ten"] = nameScore;
                        newRow["Khoang cach (m)"] = dist;
                    } else if (dist !== null) {
                        newRow["Ket luan"] = "Khac";
                        newRow["Do tin cay (%)"] = 0;
                        newRow["Diem giong ten"] = nameScore;
                        newRow["Khoang cach (m)"] = dist;
                    } else {
                        newRow["Ket luan"] = "Thieu toa do";
                        newRow["Do tin cay (%)"] = 0;
                        newRow["Diem giong ten"] = nameScore;
                        newRow["Khoang cach (m)"] = null;
                    }
                }
            }
            return newRow;
        });
        
        filterSection.classList.remove('hidden');
        applyFilters();
        resultContainer.classList.remove('hidden');
        btnRunCompare.disabled = false;
        loaderCompare.classList.add('hidden');
        Swal.fire('Thành công', 'Đã hoàn tất so sánh.', 'success');
    }, 100);
});

// Filtering Logic
btnAddFilter.addEventListener('click', () => {
    const filterId = Date.now();
    const div = document.createElement('div');
    div.className = "flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200 shadow-sm";
    div.id = `filter-${filterId}`;
    
    let options = globalHeaders;
    if(currentMode === 'compare' && resultData.length > 0) {
        options = Object.keys(resultData[0]);
    }

    div.innerHTML = `
        <select class="flex-1 text-xs border-none focus:ring-0 bg-transparent" onchange="updateFilterOptions(${filterId}, this.value)">
            <option value="">Chọn cột...</option>
            ${options.map(h => `<option value="${h}">${h}</option>`).join('')}
        </select>
        <select class="flex-1 text-xs border-none focus:ring-0 bg-transparent" id="vals-${filterId}" multiple>
        </select>
        <button onclick="removeFilter(${filterId})" class="text-red-500 p-1 hover:bg-red-50 rounded">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
    `;
    filterConditions.appendChild(div);
    activeFilters.push({id: filterId, column: '', values: []});
});

window.updateFilterOptions = (id, col) => {
    const select = document.getElementById(`vals-${id}`);
    select.innerHTML = '';
    if(!col) return;
    
    // Get unique values
    const source = resultData.length > 0 ? resultData : globalData;
    const values = [...new Set(source.map(r => String(r[col] || '').trim()))].filter(s=>s).sort();
    
    values.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        opt.selected = true; // Default select all like Python
        select.appendChild(opt);
    });
    
    const f = activeFilters.find(x => x.id === id);
    if(f) f.column = col;
    
    select.onchange = () => {
        const selected = Array.from(select.selectedOptions).map(o => o.value);
        if(f) f.values = selected;
        applyFilters();
    };
    applyFilters();
};

window.removeFilter = (id) => {
    document.getElementById(`filter-${id}`).remove();
    activeFilters = activeFilters.filter(x => x.id !== id);
    applyFilters();
};

function applyFilters() {
    let data = resultData.length > 0 ? resultData : globalData;
    
    // Mode TH2 single filter
    if(currentMode === 'view') {
        const col = filterColOnly.value;
        const kw = filterKeywordOnly.value.trim().toLowerCase();
        if(kw) {
            data = data.filter(r => String(r[col] || '').toLowerCase().includes(kw));
        }
    }

    // Python-like multi-filters
    activeFilters.forEach(f => {
        if(f.column && f.values.length > 0) {
            data = data.filter(r => f.values.includes(String(r[f.column] || '').trim()));
        }
    });

    filteredData = data;
    renderTable();
}

filterKeywordOnly.addEventListener('input', applyFilters);
filterColOnly.addEventListener('change', applyFilters);

function renderTable() {
    if(filteredData.length === 0) {
        resultHead.innerHTML = '';
        resultBody.innerHTML = '';
        resultCount.textContent = '0 dòng';
        return;
    }
    
    const headers = Object.keys(filteredData[0]);
    resultHead.innerHTML = `<tr>${headers.map(h => `<th class="px-4 py-3">${h}</th>`).join('')}</tr>`;
    
    const display = filteredData.slice(0, 100);
    resultBody.innerHTML = display.map(row => {
        let style = "";
        if(row["Ket luan"]) {
            if(row["Ket luan"].includes("Trung quan")) style = "bg-green-50";
            else if (row["Ket luan"].includes("Trung dia chi")) style = "bg-yellow-50";
            else if (row["Ket luan"].includes("Khac")) style = "bg-red-50";
        }
        return `<tr class="border-b hover:bg-slate-50 transition-colors ${style}">
            ${headers.map(h => `<td class="px-4 py-3 whitespace-nowrap">${escapeHtml(row[h]===null?'':row[h])}</td>`).join('')}
        </tr>`;
    }).join('');
    
    resultCount.textContent = `${filteredData.length} dòng`;
}

if (btnShowMap) btnShowMap.addEventListener('click', renderJsonMap);
if (btnFitMap) btnFitMap.addEventListener('click', fitJsonMap);

btnDownload.addEventListener('click', () => {
    if(filteredData.length === 0) return;
    const ws = XLSX.utils.json_to_sheet(filteredData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Filtered_Result");
    XLSX.writeFile(wb, "excel_da_loc.xlsx");
});
