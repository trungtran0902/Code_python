import os
import json
import threading
import time
from flask import Flask, request, jsonify, render_template_string, send_from_directory
import pandas as pd
import requests

# ========================================
# CẤU HÌNH CHUNG
# ========================================
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

GOOGLE_API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"
MAP4D_API_KEY = "93d393d0f6507ee00b62fe01db7430fa"

print("📂 Flask running in:", BASE_DIR)
print("📁 UPLOAD_DIR:", UPLOAD_DIR)
print("📁 OUTPUT_DIR:", OUTPUT_DIR)

# ========================================
# GIAO DIỆN HTML
# ========================================
INDEX_HTML = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Bộ công cụ xử lý Excel</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 30px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 20px; }
    .card { border: 1px solid #ccc; padding: 20px; border-radius: 10px; background: #fff; }
    h2 { margin: 0 0 10px; }
    .out { margin-top: 10px; background: #f8f9fa; padding: 10px; border-radius: 8px; white-space: pre-line; }
    button { padding: 8px 14px; background: #16a34a; color: white; border: none; border-radius: 6px; cursor: pointer; }
    button.cancel { background: #dc2626; margin-left: 8px; }
    select, input[type=file] { width: 100%; margin-top: 5px; }
  </style>
</head>
<body>
<h1>🧰 Bộ công cụ xử lý Excel</h1>

<div class="grid">
  <!-- Nearby -->
  <div class="card">
    <h2>🔍 Nearby Search (Google Places)</h2>
    <input type="file" id="file-nearby" accept=".xlsx,.xls"><br>
    <div id="cols-nearby"></div>
    <button id="run-nearby">Chạy Nearby Search</button>
    <button class="cancel" id="cancel-nearby" disabled>Cancel</button>
    <div id="out-nearby" class="out"></div>
  </div>

  <!-- Geocode -->
  <div class="card">
    <h2>🗺️ Geocode Tách Cột (Map4D)</h2>
    <input type="file" id="file-geocode_tach_cot" accept=".xlsx,.xls"><br>
    <div id="cols-geocode_tach_cot"></div>
    <button id="run-geocode_tach_cot">Chạy Geocode</button>
    <button class="cancel" id="cancel-geocode_tach_cot" disabled>Cancel</button>
    <div id="out-geocode_tach_cot" class="out"></div>
  </div>

  <!-- Building -->
  <div class="card">
    <h2>🏢 Building (Google Places)</h2>
    <input type="file" id="file-building" accept=".xlsx,.xls"><br>
    <div id="cols-building"></div>
    <button id="run-building">Chạy Building</button>
    <button class="cancel" id="cancel-building" disabled>Cancel</button>
    <div id="out-building" class="out"></div>
  </div>
</div>

<script>
async function getColumns(type) {
  console.log("🔍 Kiểm tra input:", document.getElementById("file-" + type));
  const fileInput = document.getElementById("file-" + type);
  const colsDiv = document.getElementById("cols-" + type);
  if (!fileInput.files.length) return;
  console.log("📤 Gửi file đến /preview_columns...");

let controller = {};

async function getColumns(type) {
  const fileInput = document.getElementById("file-" + type);
  const colsDiv = document.getElementById("cols-" + type);
  if (!fileInput.files.length) return;
  colsDiv.innerHTML = "⏳ Đang đọc cột...";
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const res = await fetch("/preview_columns", { method: "POST", body: formData });
  const data = await res.json();
  if (data.error) {
    colsDiv.innerHTML = "❌ " + data.error;
  } else {
    let selects = "";
    if (["nearby","building"].includes(type)) {
      selects = `
        <label>Lat:</label><select id="lat-${type}">${data.columns.map(c=>`<option>${c}</option>`).join("")}</select><br>
        <label>Long:</label><select id="long-${type}">${data.columns.map(c=>`<option>${c}</option>`).join("")}</select><br>
        <label>Keyword:</label><select id="kw-${type}">${data.columns.map(c=>`<option>${c}</option>`).join("")}</select><br>`;
    } else {
      selects = `
        <label>Lat:</label><select id="lat-${type}">${data.columns.map(c=>`<option>${c}</option>`).join("")}</select><br>
        <label>Long:</label><select id="long-${type}">${data.columns.map(c=>`<option>${c}</option>`).join("")}</select><br>`;
    }
    colsDiv.innerHTML = selects;
  }
}

async function runProcess(type) {
  const out = document.getElementById("out-" + type);
  const btn = document.getElementById("run-" + type);
  const cancelBtn = document.getElementById("cancel-" + type);
  const fileInput = document.getElementById("file-" + type);
  if (!fileInput.files.length) { out.textContent = "❗ Vui lòng chọn file."; return; }

  out.textContent = "⏳ Đang xử lý...";
  btn.disabled = true;
  cancelBtn.disabled = false;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("lat_col", document.getElementById("lat-" + type)?.value || "");
  formData.append("long_col", document.getElementById("long-" + type)?.value || "");
  formData.append("kw_col", document.getElementById("kw-" + type)?.value || "");

  controller[type] = new AbortController();
  try {
    const res = await fetch("/run_" + type, { method: "POST", body: formData, signal: controller[type].signal });
    const data = await res.json();
    if (data.error) out.textContent = "❌ " + data.error;
    else out.textContent = data.log + "\\n📁 Tải file: " + data.download_url;
  } catch (e) {
    out.textContent = "⚠️ Đã hủy hoặc lỗi mạng.";
  } finally {
    btn.disabled = false;
    cancelBtn.disabled = true;
  }
}

function cancelProcess(type) {
  if (controller[type]) controller[type].abort();
  document.getElementById("out-" + type).textContent = "⚠️ Đã hủy tiến trình.";
  document.getElementById("run-" + type).disabled = false;
  document.getElementById("cancel-" + type).disabled = true;
}

["nearby","building","geocode_tach_cot"].forEach(t=>{
  document.getElementById("file-"+t).addEventListener("change", ()=>getColumns(t));
  document.getElementById("run-"+t).addEventListener("click", ()=>runProcess(t));
  document.getElementById("cancel-"+t).addEventListener("click", ()=>cancelProcess(t));
});
</script>
</body>
</html>
"""

# ========================================
# API: LẤY DANH SÁCH CỘT EXCEL
# ========================================
@app.route("/preview_columns", methods=["POST"])
def preview_columns():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "Không có file."})
        save_path = os.path.join(UPLOAD_DIR, file.filename)
        file.save(save_path)
        df = pd.read_excel(save_path)
        cols = list(df.columns)
        return jsonify({"columns": cols})
    except Exception as e:
        return jsonify({"error": str(e)})

# ========================================
# API: NEARBY + BUILDING
# ========================================
def run_nearby_like(df, lat_col, long_col, kw_col, key):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    session = requests.Session()
    for i, row in df.iterrows():
        try:
            params = {"location": f"{row[lat_col]},{row[long_col]}", "radius": 50, "keyword": row[kw_col], "key": key}
            r = session.get(url, params=params, timeout=30)
            res = r.json().get("results", [])
            if res:
                df.at[i, "Name"] = res[0].get("name","")
                df.at[i, "Address"] = res[0].get("vicinity","")
        except Exception as e:
            df.at[i, "Error"] = str(e)
    return df

@app.route("/run_nearby", methods=["POST"])
def run_nearby():
    file = request.files.get("file")
    lat_col = request.form.get("lat_col")
    long_col = request.form.get("long_col")
    kw_col = request.form.get("kw_col")
    df = pd.read_excel(file)
    df = run_nearby_like(df, lat_col, long_col, kw_col, GOOGLE_API_KEY)
    out_path = os.path.join(OUTPUT_DIR, "nearby_output.xlsx")
    df.to_excel(out_path, index=False)
    return jsonify({"download_url": "/download/nearby_output.xlsx", "log": "✅ Hoàn tất Nearby"})

@app.route("/run_building", methods=["POST"])
def run_building():
    file = request.files.get("file")
    lat_col = request.form.get("lat_col")
    long_col = request.form.get("long_col")
    kw_col = request.form.get("kw_col")
    df = pd.read_excel(file)
    df = run_nearby_like(df, lat_col, long_col, kw_col, GOOGLE_API_KEY)
    out_path = os.path.join(OUTPUT_DIR, "building_output.xlsx")
    df.to_excel(out_path, index=False)
    return jsonify({"download_url": "/download/building_output.xlsx", "log": "✅ Hoàn tất Building"})

# ========================================
# API: GEOCODE
# ========================================
@app.route("/run_geocode_tach_cot", methods=["POST"])
def run_geocode_tach_cot():
    file = request.files.get("file")
    lat_col = request.form.get("lat_col")
    long_col = request.form.get("long_col")
    df = pd.read_excel(file)
    url = "https://api.map4d.vn/sdk/v2/geocode"
    for i, row in df.iterrows():
        try:
            params = {"location": f"{row[lat_col]},{row[long_col]}", "key": MAP4D_API_KEY}
            r = requests.get(url, params=params, timeout=20)
            result = r.json().get("result", [{}])[0]
            df.at[i, "Address"] = result.get("formattedAddress", "")
        except Exception as e:
            df.at[i, "Address"] = str(e)
    out_path = os.path.join(OUTPUT_DIR, "geocode_output.xlsx")
    df.to_excel(out_path, index=False)
    return jsonify({"download_url": "/download/geocode_output.xlsx", "log": "✅ Hoàn tất Geocode"})

# ========================================
@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# ========================================
import webbrowser
from threading import Timer

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run(host="127.0.0.1", port=5000)
