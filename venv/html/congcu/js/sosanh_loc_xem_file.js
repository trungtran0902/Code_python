const excelInput = document.getElementById('excelInput');
const totalRows = document.getElementById('totalRows');
const totalCols = document.getElementById('totalCols');
const modeSelection = document.getElementById('modeSelection');
const compareContainer = document.getElementById('compareContainer');
const viewContainer = document.getElementById('viewContainer');
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

const filterCol = document.getElementById('filterCol');
const filterKeyword = document.getElementById('filterKeyword');
const btnFilter = document.getElementById('btnFilter');

let globalData = [];
let globalHeaders = [];
let displayData = [];
let currentMode = 'compare';

nameThr.addEventListener('input', e => nameThrVal.textContent = e.target.value);
addrThr.addEventListener('input', e => addrThrVal.textContent = e.target.value);
distThr.addEventListener('input', e => distThrVal.textContent = e.target.value);

document.getElementsByName('mode').forEach(rad => {
    rad.addEventListener('change', (e) => {
        currentMode = e.target.value;
        if(currentMode === 'compare') {
            compareContainer.classList.remove('hidden');
            viewContainer.classList.add('hidden');
        } else {
            compareContainer.classList.add('hidden');
            viewContainer.classList.remove('hidden');
            displayData = [...globalData];
            renderTable();
            resultContainer.classList.remove('hidden');
        }
    });
});

excelInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        const data = new Uint8Array(ev.target.result);
        const workbook = XLSX.read(data, {type: 'array'});
        globalData = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {defval: ""});
        
        if(globalData.length > 0) {
            globalHeaders = Object.keys(globalData[0]);
            totalRows.textContent = globalData.length;
            totalCols.textContent = globalHeaders.length;
            populateSelects();
            modeSelection.classList.remove('hidden');
            
            // Trigger UI update
            if(currentMode === 'compare') {
                compareContainer.classList.remove('hidden');
                viewContainer.classList.add('hidden');
            } else {
                compareContainer.classList.add('hidden');
                viewContainer.classList.remove('hidden');
                displayData = [...globalData];
                renderTable();
                resultContainer.classList.remove('hidden');
            }
        }
    };
    reader.readAsArrayBuffer(file);
});

function populateSelects() {
    const selects = [cN1, cA1, cLat1, cLng1, cN2, cA2, cLat2, cLng2, filterCol];
    selects.forEach(sel => {
        sel.innerHTML = '';
        globalHeaders.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            sel.appendChild(opt);
        });
    });
}

function normalizeText(text) {
    if(!text) return "";
    let str = String(text).trim().toLowerCase();
    str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
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
    const R = 6371e3; // metres
    const p1 = lat1 * Math.PI/180;
    const p2 = lat2 * Math.PI/180;
    const dp = (lat2-lat1) * Math.PI/180;
    const dl = (lng2-lng1) * Math.PI/180;

    const a = Math.sin(dp/2) * Math.sin(dp/2) +
            Math.cos(p1) * Math.cos(p2) *
            Math.sin(dl/2) * Math.sin(dl/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return Math.round(R * c * 100) / 100;
}

function tokenSetRatio(s1, s2) {
    if (!s1 || !s2) return 0;
    const tokens1 = new Set(s1.split(' '));
    const tokens2 = new Set(s2.split(' '));
    const intersection = new Set([...tokens1].filter(x => tokens2.has(x)));
    return Math.round((intersection.size / Math.max(tokens1.size, tokens2.size, 1)) * 100);
}

btnRunCompare.addEventListener('click', () => {
    btnRunCompare.disabled = true;
    loaderCompare.classList.remove('hidden');
    
    setTimeout(() => {
        let nThr = parseInt(nameThr.value);
        let aThr = parseInt(addrThr.value);
        let dThr = parseInt(distThr.value);
        
        displayData = globalData.map(row => {
            let newRow = {...row};
            let tN1 = normalizeText(row[cN1.value]);
            let tA1 = normalizeText(row[cA1.value]);
            let lt1 = safeFloat(row[cLat1.value]);
            let lg1 = safeFloat(row[cLng1.value]);
            
            let tN2 = normalizeText(row[cN2.value]);
            let tA2 = normalizeText(row[cA2.value]);
            let lt2 = safeFloat(row[cLat2.value]);
            let lg2 = safeFloat(row[cLng2.value]);
            
            let nameScore = tokenSetRatio(tN1, tN2);
            let nameExact = (tN1 === tN2 && tN1 !== "");
            
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
                let addrScore = tokenSetRatio(tA1, tA2);
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
        
        renderTable(true);
        resultContainer.classList.remove('hidden');
        
        btnRunCompare.disabled = false;
        loaderCompare.classList.add('hidden');
        Swal.fire('Thành công', 'Đã hoàn tất so sánh.', 'success');
    }, 100);
});

btnFilter.addEventListener('click', () => {
    let col = filterCol.value;
    let kw = filterKeyword.value.trim().toLowerCase();
    
    if(kw === '') {
        displayData = [...globalData];
    } else {
        displayData = globalData.filter(row => {
            return String(row[col] || '').toLowerCase().includes(kw);
        });
    }
    renderTable(false);
});

function renderTable(isCompare = false) {
    if(displayData.length === 0) {
        resultHead.innerHTML = '';
        resultBody.innerHTML = '';
        resultCount.textContent = 0;
        return;
    }
    
    let headers = Object.keys(displayData[0]);
    resultHead.innerHTML = `<tr>${headers.map(h => `<th class="px-4 py-2">${h}</th>`).join('')}</tr>`;
    
    // limit to 100 rows for performance
    const renderList = displayData.slice(0, 100);
    resultBody.innerHTML = renderList.map(row => {
        let cls = "border-b";
        if(isCompare && row["Ket luan"]) {
            if(row["Ket luan"].includes("Trung quan")) cls += " row-exact";
            else if (row["Ket luan"].includes("Trung dia chi")) cls += " row-address";
            else if (row["Ket luan"].includes("Khac")) cls += " row-diff";
        }
        return `<tr class="${cls}">${headers.map(h => `<td class="px-4 py-2 whitespace-nowrap">${row[h]===null?'':row[h]}</td>`).join('')}</tr>`;
    }).join('');
    
    resultCount.textContent = displayData.length;
}

btnDownload.addEventListener('click', () => {
    const ws = XLSX.utils.json_to_sheet(displayData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Result");
    XLSX.writeFile(wb, "result.xlsx");
});
