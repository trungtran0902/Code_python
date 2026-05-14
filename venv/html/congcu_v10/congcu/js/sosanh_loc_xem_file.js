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
    fileStatus.textContent = 'Đang đọc file...';
    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            const data = new Uint8Array(ev.target.result);
            const workbook = XLSX.read(data, {type: 'array'});
            globalData = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {defval: ""});
            
            if(globalData.length > 0) {
                globalHeaders = Object.keys(globalData[0]);
                totalRows.textContent = globalData.length;
                totalCols.textContent = globalHeaders.length;
                populateSelects();
                mainContent.classList.remove('hidden');
                fileStatus.textContent = `Đã nạp ${globalData.length} dòng.`;
            } else {
                fileStatus.textContent = 'File trống';
            }
        } catch(err) {
            fileStatus.textContent = 'Lỗi đọc file';
            Swal.fire('Lỗi', 'Không thể đọc file Excel', 'error');
        }
    };
    reader.readAsArrayBuffer(file);
});

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
    autoDetect(cLat1, ["Latitude", "Lat", "ViDo"]);
    autoDetect(cLat2, ["Lat_Map4D", "Map4D_Lat"]);
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
            ${headers.map(h => `<td class="px-4 py-3 whitespace-nowrap">${row[h]===null?'':row[h]}</td>`).join('')}
        </tr>`;
    }).join('');
    
    resultCount.textContent = `${filteredData.length} dòng`;
}

btnDownload.addEventListener('click', () => {
    if(filteredData.length === 0) return;
    const ws = XLSX.utils.json_to_sheet(filteredData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Filtered_Result");
    XLSX.writeFile(wb, "excel_da_loc.xlsx");
});
