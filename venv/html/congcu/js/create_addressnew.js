const geojsonInput = document.getElementById('geojsonInput');
const excelInput = document.getElementById('excelInput');
const geojsonStatus = document.getElementById('geojsonStatus');
const columnSelection = document.getElementById('columnSelection');
const colOldAddress = document.getElementById('colOldAddress');
const colLat = document.getElementById('colLat');
const colLng = document.getElementById('colLng');
const btnProcess = document.getElementById('btnProcess');
const loaderProcess = document.getElementById('loaderProcess');
const resultContainer = document.getElementById('resultContainer');
const resultHead = document.getElementById('resultHead');
const resultBody = document.getElementById('resultBody');
const btnDownload = document.getElementById('btnDownload');
const matchCount = document.getElementById('matchCount');

let geojsonFeatures = [];
let excelData = [];
let excelHeaders = [];
let processedData = [];

geojsonInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    geojsonFeatures = [];
    if(files.length === 0) {
        geojsonStatus.textContent = 'Chưa có file nào được chọn.';
        checkReady();
        return;
    }
    
    geojsonStatus.textContent = `Đang đọc ${files.length} file GeoJSON...`;
    
    try {
        for(let i=0; i<files.length; i++) {
            const text = await files[i].text();
            try {
                const sanitized = text.replace(/,\s*([}\]])/g, "$1");
                const data = JSON.parse(sanitized);
                if(data.features && Array.isArray(data.features)) {
                    data.features.forEach(f => {
                        if(f.properties && f.properties.address) {
                            f.properties.ward_address = f.properties.address;
                        }
                        geojsonFeatures.push(f);
                    });
                }
            } catch(err) {
                console.error(`Lỗi đọc file ${files[i].name}:`, err);
            }
        }
        geojsonStatus.textContent = `Đã nạp ${geojsonFeatures.length} vùng polygon từ ${files.length} file.`;
    } catch(err) {
        geojsonStatus.textContent = `Lỗi đọc file: ${err.message}`;
    }
    checkReady();
});

excelInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) {
        columnSelection.classList.add('hidden');
        excelData = [];
        checkReady();
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (ev) => {
        const data = new Uint8Array(ev.target.result);
        const workbook = XLSX.read(data, {type: 'array'});
        const sheetName = workbook.SheetNames[0];
        excelData = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], {defval: ""});
        
        if(excelData.length > 0) {
            excelHeaders = Object.keys(excelData[0]);
            populateSelects();
            columnSelection.classList.remove('hidden');
        } else {
            Swal.fire('Lỗi', 'File Excel trống', 'error');
        }
        checkReady();
    };
    reader.readAsArrayBuffer(file);
});

function normalizeName(val) {
    return String(val).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/g, "");
}

function autoDetect(selectElement, keywords) {
    const options = Array.from(selectElement.options);
    for(let keyword of keywords) {
        const keyNorm = normalizeName(keyword);
        const match = options.find(opt => normalizeName(opt.value) === keyNorm);
        if(match) {
            selectElement.value = match.value;
            return;
        }
    }
}

function populateSelects() {
    [colOldAddress, colLat, colLng].forEach(sel => {
        sel.innerHTML = '';
        excelHeaders.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            sel.appendChild(opt);
        });
    });
    
    autoDetect(colOldAddress, ["Oldaddress", "OldAddress", "Address", "DiaChi", "DiaChiCu"]);
    autoDetect(colLat, ["Latitude", "Lat", "ViDo", "Y"]);
    autoDetect(colLng, ["Longitude", "Lng", "Lon", "KinhDo", "X"]);
}

function checkReady() {
    btnProcess.disabled = geojsonFeatures.length === 0 || excelData.length === 0;
}

btnProcess.addEventListener('click', async () => {
    btnProcess.disabled = true;
    loaderProcess.classList.remove('hidden');
    resultContainer.classList.add('hidden');
    
    setTimeout(() => {
        try {
            processedData = excelData.map(row => {
                let newRow = {...row};
                const oldAddr = newRow[colOldAddress.value] || "";
                let lat = parseFloat(newRow[colLat.value]);
                let lng = parseFloat(newRow[colLng.value]);
                
                let wardAddress = "";
                
                if(!isNaN(lat) && !isNaN(lng)) {
                    const pt = turf.point([lng, lat]);
                    for(let f of geojsonFeatures) {
                        if(f.geometry && (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon')) {
                            if(turf.booleanPointInPolygon(pt, f)) {
                                wardAddress = f.properties.ward_address || "";
                                break;
                            }
                        }
                    }
                }
                
                let housePart = String(oldAddr).split(',')[0].trim();
                if(!wardAddress) {
                    newRow.NewAddress = oldAddr;
                } else if (!housePart) {
                    newRow.NewAddress = wardAddress;
                } else {
                    newRow.NewAddress = `${housePart}, ${wardAddress}`;
                }
                
                newRow.ward_address = wardAddress;
                return newRow;
            });
            
            const matched = processedData.filter(r => r.ward_address).length;
            matchCount.textContent = `${matched}/${processedData.length}`;
            renderResult();
            
            resultContainer.classList.remove('hidden');
            Swal.fire('Thành công', 'Đã xử lý xong dữ liệu.', 'success');
        } catch(err) {
            Swal.fire('Lỗi xử lý', err.message, 'error');
        } finally {
            btnProcess.disabled = false;
            loaderProcess.classList.add('hidden');
        }
    }, 100);
});

function renderResult() {
    if(processedData.length === 0) return;
    const headers = Object.keys(processedData[0]);
    resultHead.innerHTML = `<tr>${headers.map(h => `<th class="px-4 py-2">${h}</th>`).join('')}</tr>`;
    
    const display = processedData.slice(0, 50);
    resultBody.innerHTML = display.map(row => 
        `<tr class="border-b">${headers.map(h => `<td class="px-4 py-2 whitespace-nowrap">${row[h]||''}</td>`).join('')}</tr>`
    ).join('');
}

btnDownload.addEventListener('click', () => {
    const ws = XLSX.utils.json_to_sheet(processedData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Result");
    XLSX.writeFile(wb, "new_address_result.xlsx");
});
