const geojsonInput = document.getElementById('geojsonInput');
const excelInput = document.getElementById('excelInput');
const geojsonStatus = document.getElementById('geojsonStatus');
const excelStatus = document.getElementById('excelStatus');
const columnMapping = document.getElementById('columnMapping');
const addrCol = document.getElementById('addrCol');
const latCol = document.getElementById('latCol');
const lngCol = document.getElementById('lngCol');
const processBtn = document.getElementById('processBtn');
const resultCard = document.getElementById('resultCard');
const tableHead = document.getElementById('tableHead');
const tableBody = document.getElementById('tableBody');
const downloadBtn = document.getElementById('downloadBtn');

let geojsonFeatures = [];
let excelData = [];
let excelHeaders = [];
let processedData = [];

geojsonInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    geojsonFeatures = [];
    if(files.length === 0) {
        geojsonStatus.textContent = 'Chưa chọn file';
        checkReady();
        return;
    }
    
    geojsonStatus.textContent = `Đang đọc ${files.length} file...`;
    
    try {
        for(let i=0; i<files.length; i++) {
            const text = await files[i].text();
            try {
                // Remove trailing commas in JSON if any (common in some exports)
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
        geojsonStatus.textContent = `Đã nạp ${geojsonFeatures.length} vùng polygon.`;
    } catch(err) {
        geojsonStatus.textContent = `Lỗi: ${err.message}`;
    }
    checkReady();
});

excelInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if(!file) {
        columnMapping.classList.add('hidden');
        excelData = [];
        excelStatus.textContent = 'Chưa chọn file';
        checkReady();
        return;
    }
    
    excelStatus.textContent = 'Đang đọc file...';
    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            const data = new Uint8Array(ev.target.result);
            const workbook = XLSX.read(data, {type: 'array'});
            const sheetName = workbook.SheetNames[0];
            excelData = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], {defval: ""});
            
            if(excelData.length > 0) {
                excelHeaders = Object.keys(excelData[0]);
                populateSelects();
                columnMapping.classList.remove('hidden');
                excelStatus.textContent = `Đã nạp ${excelData.length} dòng.`;
            } else {
                excelStatus.textContent = 'File trống';
                Swal.fire('Lỗi', 'File Excel trống', 'error');
            }
        } catch(err) {
            excelStatus.textContent = 'Lỗi đọc file';
            Swal.fire('Lỗi', 'Không thể đọc file Excel', 'error');
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
    [addrCol, latCol, lngCol].forEach(sel => {
        sel.innerHTML = '';
        excelHeaders.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            sel.appendChild(opt);
        });
    });
    
    autoDetect(addrCol, ["Oldaddress", "OldAddress", "Address", "DiaChi", "DiaChiCu", "FullAddress"]);
    autoDetect(latCol, ["Latitude", "Lat", "ViDo", "Y"]);
    autoDetect(lngCol, ["Longitude", "Lng", "Lon", "KinhDo", "X"]);
}

function checkReady() {
    processBtn.disabled = geojsonFeatures.length === 0 || excelData.length === 0;
}

processBtn.addEventListener('click', async () => {
    processBtn.disabled = true;
    const originalText = processBtn.textContent;
    processBtn.textContent = 'Đang xử lý...';
    resultCard.classList.add('hidden');
    
    setTimeout(() => {
        try {
            processedData = excelData.map(row => {
                let newRow = {...row};
                const oldAddr = newRow[addrCol.value] || "";
                let lat = parseFloat(newRow[latCol.value]);
                let lng = parseFloat(newRow[lngCol.value]);
                
                let wardAddress = "";
                
                if(!isNaN(lat) && !isNaN(lng)) {
                    const pt = turf.point([lng, lat]);
                    for(let f of geojsonFeatures) {
                        if(f.geometry && (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon')) {
                            try {
                                if(turf.booleanPointInPolygon(pt, f)) {
                                    wardAddress = f.properties.ward_address || f.properties.address || "";
                                    break;
                                }
                            } catch(e) {}
                        }
                    }
                }
                
                let housePart = String(oldAddr).split(',')[0].trim();
                if(!wardAddress) {
                    newRow.NewAddress = oldAddr;
                } else if (!housePart || housePart.toLowerCase() === 'null') {
                    newRow.NewAddress = wardAddress;
                } else {
                    newRow.NewAddress = `${housePart}, ${wardAddress}`;
                }
                
                newRow.ward_address = wardAddress;
                return newRow;
            });
            
            renderResult();
            resultCard.classList.remove('hidden');
            Swal.fire('Thành công', `Đã xử lý xong ${processedData.length} dòng.`, 'success');
        } catch(err) {
            Swal.fire('Lỗi xử lý', err.message, 'error');
        } finally {
            processBtn.disabled = false;
            processBtn.textContent = originalText;
        }
    }, 100);
});

function renderResult() {
    if(processedData.length === 0) return;
    const headers = Object.keys(processedData[0]);
    tableHead.innerHTML = `<tr>${headers.map(h => `<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${h}</th>`).join('')}</tr>`;
    
    const display = processedData.slice(0, 50);
    tableBody.innerHTML = display.map(row => 
        `<tr class="border-b">${headers.map(h => `<td class="px-6 py-4 whitespace-nowrap text-gray-700">${row[h]||''}</td>`).join('')}</tr>`
    ).join('');
}

downloadBtn.addEventListener('click', () => {
    const ws = XLSX.utils.json_to_sheet(processedData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Result");
    XLSX.writeFile(wb, "new_address_result.xlsx");
});
