const sourceInput = document.getElementById('sourceInput');
const map4dInput = document.getElementById('map4dInput');
const btnProcess = document.getElementById('btnProcess');
const loaderProcess = document.getElementById('loaderProcess');
const resultContainer = document.getElementById('resultContainer');
const resultHead = document.getElementById('resultHead');
const resultBody = document.getElementById('resultBody');
const btnDownload = document.getElementById('btnDownload');
const sourceStatus = document.getElementById('sourceStatus');
const map4dStatus = document.getElementById('map4dStatus');

const MANUAL_CATEGORY_MAP = {
    "an vat via he": "food_service",
    "an vat": "food_service",
    "via he": "food_service",
    "quan an": "eatery",
    "nha hang": "restaurant",
    "cafe dessert": "cafe",
    "cafe": "cafe",
    "ca phe dessert": "cafe",
    "ca phe": "cafe",
    "tra sua": "milk_tea",
    "tiem banh": "bakery",
    "giao com van phong": "food_service",
    "an chay": "food_service",
    "do an nhanh": "fast_food",
    "shop cua hang": "store",
    "shop online": "store",
    "mua sam online": "store",
    "cho": "local_market",
    "nha thuoc": "pharmacy",
    "khu am thuc": "food_service",
};

let sourceData = [];
let map4dData = [];
let resultData = [];
let sourceHeaders = [];

function checkReady() {
    btnProcess.disabled = sourceData.length === 0 || map4dData.length === 0;
}

sourceInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        const data = new Uint8Array(ev.target.result);
        const workbook = XLSX.read(data, {type: 'array'});
        sourceData = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {defval: ""});
        if(sourceData.length > 0) {
            sourceHeaders = Object.keys(sourceData[0]);
            // Check for 'categories' (case insensitive)
            const hasCat = sourceHeaders.some(h => h.toLowerCase() === 'categories');
            if(!hasCat) {
                Swal.fire('Lỗi', "File nguồn thiếu cột 'categories'", 'error');
                sourceData = [];
                sourceStatus.textContent = "Thiếu cột 'categories'";
            } else {
                sourceStatus.textContent = `Đã nạp ${sourceData.length} dòng.`;
            }
        }
        checkReady();
    };
    reader.readAsArrayBuffer(file);
});

map4dInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        const data = new Uint8Array(ev.target.result);
        const workbook = XLSX.read(data, {type: 'array'});
        let rawMap4d = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {defval: ""});
        
        map4dData = [];
        for(let r of rawMap4d) {
            if(r["Tên"] && r["Định danh"]) {
                map4dData.push({
                    "Tên": String(r["Tên"]),
                    "Định danh": String(r["Định danh"]),
                    "normalized_name": normalizeText(r["Tên"])
                });
            }
        }
        if(map4dData.length > 0) {
            map4dStatus.textContent = `Đã nạp ${map4dData.length} danh mục Map4D.`;
        } else {
            Swal.fire('Lỗi', "File Type Map4D thiếu cột 'Tên' hoặc 'Định danh'", 'error');
            map4dStatus.textContent = "Sai định dạng cột.";
        }
        checkReady();
    };
    reader.readAsArrayBuffer(file);
});

function normalizeText(text) {
    if(!text) return "";
    let str = String(text).trim().toLowerCase();
    // Normalize unicode (loại bỏ dấu)
    str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    str = str.replace(/đ/g, "d");
    // Thay thế ký tự đặc biệt bằng dấu cách
    str = str.replace(/[\/,\_\-\\]+/g, " ");
    return str.replace(/\s+/g, " ").trim();
}

// Levenshtein / SequenceMatcher equivalent
function getSimilarity(s1, s2) {
    if (!s1 || !s2) return 0;
    const len1 = s1.length;
    const len2 = s2.length;
    const matrix = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(0));
    for (let i = 0; i <= len1; i++) matrix[i][0] = i;
    for (let j = 0; j <= len2; j++) matrix[0][j] = j;
    for (let i = 1; i <= len1; i++) {
        for (let j = 1; j <= len2; j++) {
            const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
            matrix[i][j] = Math.min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + cost);
        }
    }
    const dist = matrix[len1][len2];
    return 1 - (dist / Math.max(len1, len2));
}

// Matches RapidFuzz fuzz.token_set_ratio (returns 0-1 scale for scoreCandidate)
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

    const r1 = t0 ? getSimilarity(t0, t1) : 0;
    const r2 = t0 ? getSimilarity(t0, t2) : 0;
    const r3 = getSimilarity(t1, t2);

    return Math.max(r1, r2, r3); // 0-1 scale (scoreCandidate expects this)
}

function scoreCandidate(normalizedCategory, normalizedName) {
    if(!normalizedCategory || !normalizedName) return 0;
    
    const ratio = getSimilarity(normalizedCategory, normalizedName);
    const tScore = tokenSetRatio(normalizedCategory, normalizedName);
    const containsBonus = (normalizedCategory.includes(normalizedName) || normalizedName.includes(normalizedCategory)) ? 0.15 : 0;
    
    return ratio * 0.65 + tScore * 0.35 + containsBonus;
}

function findManualMatch(normCat, map4dLookup) {
    for(let kw in MANUAL_CATEGORY_MAP) {
        if(normCat.includes(kw)) {
            let identifier = MANUAL_CATEGORY_MAP[kw];
            if(map4dLookup[identifier]) {
                return {
                    matched_name: map4dLookup[identifier]["Tên"],
                    identifier: identifier,
                    score: 1.0,
                    match_type: "manual"
                };
            }
        }
    }
    return null;
}

function mapSingleCategory(categoryValue, map4dLookup) {
    let norm = normalizeText(categoryValue);
    if(!norm) return null;
    
    let manual = findManualMatch(norm, map4dLookup);
    if(manual) return manual;
    
    let bestRow = null;
    let bestScore = -1;
    for(let row of map4dData) {
        let score = scoreCandidate(norm, row.normalized_name);
        if(score > bestScore) {
            bestScore = score;
            bestRow = row;
        }
    }
    if(!bestRow) return null;
    return {
        matched_name: bestRow["Tên"],
        identifier: bestRow["Định danh"],
        score: bestScore,
        match_type: "fuzzy"
    };
}

btnProcess.addEventListener('click', () => {
    btnProcess.disabled = true;
    loaderProcess.classList.remove('hidden');
    resultContainer.classList.add('hidden');
    
    setTimeout(() => {
        let map4dLookup = {};
        map4dData.forEach(r => map4dLookup[r["Định danh"]] = r);
        
        // Find column name for categories (case insensitive)
        const catColName = sourceHeaders.find(h => h.toLowerCase() === 'categories');

        resultData = sourceData.map(row => {
            let newRow = {...row};
            let catVal = row[catColName];
            
            let matchedNames = [];
            let matchedIds = [];
            
            if(catVal) {
                // Split by comma
                let parts = String(catVal).split(',').map(s=>s.trim()).filter(s=>s);
                parts.forEach(p => {
                    let mapped = mapSingleCategory(p, map4dLookup);
                    if(mapped && !matchedIds.includes(mapped.identifier)) {
                        matchedNames.push(mapped.matched_name);
                        matchedIds.push(mapped.identifier);
                    }
                });
            }
            
            newRow.map4d_ten = matchedNames.join(', ');
            newRow.map4d_dinh_danh = matchedIds.join(', ');
            return newRow;
        });
        
        renderResult(catColName);
        resultContainer.classList.remove('hidden');
        btnProcess.disabled = false;
        loaderProcess.classList.add('hidden');
        Swal.fire('Thành công', 'Đã xử lý xong.', 'success');
    }, 100);
});

function renderResult(catColName) {
    if(resultData.length === 0) return;
    const headers = ["categories", "map4d_ten", "map4d_dinh_danh"];
    resultHead.innerHTML = `<tr>${headers.map(h => `<th class="px-6 py-4">${h}</th>`).join('')}</tr>`;
    
    const display = resultData.slice(0, 50);
    resultBody.innerHTML = display.map(row => {
        let catVal = row[catColName] || '';
        return `<tr>
            <td class="px-6 py-4">${catVal}</td>
            <td class="px-6 py-4 font-semibold text-green-600">${row.map4d_ten||''}</td>
            <td class="px-6 py-4 text-blue-600">${row.map4d_dinh_danh||''}</td>
        </tr>`;
    }).join('');
}

btnDownload.addEventListener('click', () => {
    const ws = XLSX.utils.json_to_sheet(resultData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "mapped_categories");
    XLSX.writeFile(wb, "mapped_categories_result.xlsx");
});
