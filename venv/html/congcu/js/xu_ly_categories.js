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
        if(sourceData.length > 0 && sourceData[0].categories === undefined && sourceData[0].Categories === undefined) {
            Swal.fire('Lỗi', "File nguồn thiếu cột 'categories'", 'error');
            sourceData = [];
        } else {
            sourceStatus.textContent = `Đã nạp ${sourceData.length} dòng.`;
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
        }
        checkReady();
    };
    reader.readAsArrayBuffer(file);
});

function normalizeText(text) {
    if(!text) return "";
    let str = String(text).trim().toLowerCase();
    str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    str = str.replace(/đ/g, "d");
    str = str.replace(/[\/,\_\-\\]+/g, " ");
    return str.replace(/\s+/g, " ").trim();
}

function tokenSetRatio(s1, s2) {
    if (!s1 || !s2) return 0;
    const tokens1 = new Set(s1.split(' '));
    const tokens2 = new Set(s2.split(' '));
    const intersection = new Set([...tokens1].filter(x => tokens2.has(x)));
    return intersection.size / Math.max(tokens1.size, tokens2.size, 1);
}

function scoreCandidate(normalizedCategory, normalizedName) {
    if(!normalizedCategory || !normalizedName) return 0;
    
    // Simple levenshtein
    const track = Array(normalizedName.length + 1).fill(null).map(() => Array(normalizedCategory.length + 1).fill(null));
    for (let i = 0; i <= normalizedCategory.length; i += 1) track[0][i] = i;
    for (let j = 0; j <= normalizedName.length; j += 1) track[j][0] = j;
    
    for (let j = 1; j <= normalizedName.length; j += 1) {
        for (let i = 1; i <= normalizedCategory.length; i += 1) {
            const indicator = normalizedCategory[i - 1] === normalizedName[j - 1] ? 0 : 1;
            track[j][i] = Math.min(track[j][i - 1] + 1, track[j - 1][i] + 1, track[j - 1][i - 1] + indicator);
        }
    }
    const dist = track[normalizedName.length][normalizedCategory.length];
    const maxLen = Math.max(normalizedCategory.length, normalizedName.length);
    const ratio = maxLen === 0 ? 1 : (maxLen - dist) / maxLen;
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
                    identifier: identifier
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
        identifier: bestRow["Định danh"]
    };
}

btnProcess.addEventListener('click', () => {
    btnProcess.disabled = true;
    loaderProcess.classList.remove('hidden');
    resultContainer.classList.add('hidden');
    
    setTimeout(() => {
        let map4dLookup = {};
        map4dData.forEach(r => map4dLookup[r["Định danh"]] = r);
        
        resultData = sourceData.map(row => {
            let newRow = {...row};
            let catCol = row.categories !== undefined ? row.categories : row.Categories;
            
            let matchedNames = [];
            let matchedIds = [];
            
            if(catCol) {
                let parts = String(catCol).split(',').map(s=>s.trim()).filter(s=>s);
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
        
        renderResult();
        resultContainer.classList.remove('hidden');
        btnProcess.disabled = false;
        loaderProcess.classList.add('hidden');
        Swal.fire('Thành công', 'Đã xử lý xong.', 'success');
    }, 100);
});

function renderResult() {
    if(resultData.length === 0) return;
    const headers = ["categories", "map4d_ten", "map4d_dinh_danh"];
    resultHead.innerHTML = `<tr>${headers.map(h => `<th class="px-4 py-2">${h}</th>`).join('')}</tr>`;
    
    const display = resultData.slice(0, 50);
    resultBody.innerHTML = display.map(row => {
        let catCol = row.categories !== undefined ? row.categories : (row.Categories || '');
        return `<tr class="border-b">
            <td class="px-4 py-2 whitespace-nowrap">${catCol}</td>
            <td class="px-4 py-2 whitespace-nowrap text-green-600">${row.map4d_ten||''}</td>
            <td class="px-4 py-2 whitespace-nowrap text-blue-600">${row.map4d_dinh_danh||''}</td>
        </tr>`;
    }).join('');
}

btnDownload.addEventListener('click', () => {
    const ws = XLSX.utils.json_to_sheet(resultData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "mapped_categories");
    XLSX.writeFile(wb, "mapped_categories_result.xlsx");
});
