# ========== excel_tool.py — FULL FINAL VERSION (Giao diện đẹp + Autosave Geocode) ==========

import os
import sys
import json
import requests
import pandas as pd
import webbrowser
from threading import Timer
from flask import Flask, request, jsonify, render_template_string, send_from_directory

# ========================================
# CẤU HÌNH LINH ĐỘNG CHO EXE
# ========================================
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RUN_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
UPLOAD_DIR = os.path.join(RUN_DIR, "uploads")
OUTPUT_DIR = os.path.join(RUN_DIR, "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

GOOGLE_API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"
MAP4D_API_KEY  = "93d393d0f6507ee00b62fe01db7430fa"

app = Flask(__name__)

# =========================================================
# GIAO DIỆN HTML — BẢN MỚI ĐẸP
# =========================================================
INDEX_HTML = """
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Excel Tool</title>
<style>
:root {
  --bg: #eef2f7;
  --card-bg: #ffffff;
  --border: #d8dee4;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --danger: #dc2626;
  --danger-hover: #b91c1c;
  --text: #1f2937;
  --sub: #6b7280;
  --radius: 14px;
  --shadow: 0 4px 16px rgba(0,0,0,0.08);
}

body {
  margin: 0;
  padding: 30px;
  background: var(--bg);
  font-family: "Segoe UI", Arial, sans-serif;
  color: var(--text);
}

h2 {
  margin-bottom: 20px;
  font-size: 26px;
  font-weight: 700;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit,minmax(360px,1fr));
  gap: 24px;
}

.card {
  background: var(--card-bg);
  padding: 22px;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  transition: transform 0.2s;
}

.card:hover {
  transform: translateY(-4px);
}

.card h3 {
  margin: 0 0 14px;
  font-size: 20px;
  font-weight: 600;
}

label {
  display: block;
  margin-top: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--sub);
}

input[type="file"],
input[type="text"],
select {
  width: 100%;
  margin-top: 6px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  font-size: 14px;
  transition: border 0.2s, background 0.2s;
}

input[type="text"]:focus,
select:focus {
  border-color: var(--primary);
  background: #fff;
}

button {
  padding: 10px 18px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  margin-top: 14px;
}

.primary {
  background: var(--primary);
  color: white;
}

.primary:hover {
  background: var(--primary-hover);
}

.cancel {
  background: var(--danger);
  color: white;
}

.cancel:hover {
  background: var(--danger-hover);
}

.out {
  margin-top: 14px;
  padding: 12px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
  min-height: 36px;
  white-space: pre-line;
}
</style>

</head>
<body>

<h2>🧰 Bộ công cụ xử lý Excel</h2>

<div class="grid">

  <div class="card">
    <h3>🔍 Nearby Search</h3>
    <input type="file" id="file-nearby">
    <div id="cols-nearby"></div>
    <button id="run-nearby" class="primary">Chạy Nearby</button>
    <button id="cancel-nearby" class="cancel" disabled>Hủy</button>
    <div id="out-nearby" class="out"></div>
  </div>

  <div class="card">
    <h3>🏢 Building Search</h3>
    <input type="file" id="file-building">
    <div id="cols-building"></div>
    <label>Keyword chung:</label>
    <input type="text" id="kw-building">
    <button id="run-building" class="primary">Chạy Building</button>
    <button id="cancel-building" class="cancel" disabled>Hủy</button>
    <div id="out-building" class="out"></div>
  </div>

  <div class="card">
    <h3>🗺️ Geocode Map4D</h3>
    <input type="file" id="file-geocode_tach_cot">
    <div id="cols-geocode_tach_cot"></div>
    <button id="run-geocode_tach_cot" class="primary">Chạy Geocode</button>
    <button id="cancel-geocode_tach_cot" class="cancel" disabled>Hủy</button>
    <div id="out-geocode_tach_cot" class="out"></div>
  </div>

</div>

<script>
// GIỮ NGUYÊN JS — 100% tương thích giao diện mới
let controller = {};

async function getColumns(type) {
  const file = document.getElementById("file-"+type).files[0];
  const div = document.getElementById("cols-"+type);
  if (!file) { div.innerHTML = ""; return; }

  div.innerHTML = "⏳ Đang đọc cột...";

  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/preview_columns", { method:"POST", body:form });
  const data = await res.json();

  if (data.error) { div.innerHTML = "❌ " + data.error; return; }

  let opt = data.columns.map(c=>`<option>${c}</option>`).join("");

  div.innerHTML = `
    <label>Lat:</label><select id="lat-${type}">${opt}</select>
    <label>Long:</label><select id="long-${type}">${opt}</select>
    ${type==="nearby" ? `<label>Keyword (cột):</label><select id="kwcol-nearby">${opt}</select>` : ""}
  `;
}

async function runProcess(type) {
  const file = document.getElementById("file-"+type).files[0];
  const out = document.getElementById("out-"+type);
  if (!file) { out.textContent = "❗ Chưa chọn file"; return; }

  const form = new FormData();
  form.append("file", file);
  form.append("lat_col", document.getElementById("lat-"+type)?.value || "");
  form.append("long_col", document.getElementById("long-"+type)?.value || "");
  if (type==="building") form.append("kw_col", document.getElementById("kw-building").value);
  if (type==="nearby") form.append("kw_col", document.getElementById("kwcol-nearby")?.value || "");

  out.textContent = "⏳ Đang xử lý...";

  controller[type] = new AbortController();
  try {
    const res = await fetch("/run_"+type,{ method:"POST", body:form, signal:controller[type].signal });
    const data = await res.json();
    if (data.error) out.textContent = "❌ "+data.error;
    else out.textContent = data.log + "\\n📁 " + data.download_url;
  } catch { out.textContent = "⚠ Đã hủy."; }
}

function cancelProcess(type){
  controller[type]?.abort();
  document.getElementById("out-"+type).textContent="⚠ Hủy.";
}

["nearby","building","geocode_tach_cot"].forEach(t=>{
  document.getElementById("file-"+t).onchange=()=>getColumns(t);
  document.getElementById("run-"+t).onclick=()=>runProcess(t);
  document.getElementById("cancel-"+t).onclick=()=>cancelProcess(t);
});
</script>

</body>
</html>
"""

# =========================================================
# API: LẤY CỘT — TỐI ƯU: chỉ đọc header
# =========================================================
@app.route("/preview_columns", methods=["POST"])
def preview_columns():
    try:
        file = request.files["file"]
        df = pd.read_excel(file, nrows=0)
        return jsonify({"columns": list(df.columns)})
    except Exception as e:
        return jsonify({"error": str(e)})

# =========================================================
# GOOGLE NEARBY / BUILDING — GIỮ NGUYÊN
# =========================================================
def run_nearby_like(df, lat_col, long_col, kw_col, key, suffix=""):
    session = requests.Session()
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    for c in [f"Name{suffix}", f"Address{suffix}", f"latitude{suffix}", f"longtitude{suffix}", f"Status{suffix}"]:
        if c not in df.columns:
            df[c] = ""

    for i, row in df.iterrows():
        try:
            lat = float(str(row[lat_col]).replace(",", "."))
            lon = float(str(row[long_col]).replace(",", "."))
        except:
            df.at[i, f"Status{suffix}"] = "Invalid lat/lon"
            continue

        kw = str(row[kw_col]) if kw_col else ""

        params = {"location": f"{lat},{lon}", "radius": 700, "key": key}
        if kw: params["keyword"] = kw

        js = session.get(url, params=params).json()
        results = js.get("results", [])

        if results:
            r = results[0]
            df.at[i, f"Name{suffix}"] = r.get("name","")
            df.at[i, f"Address{suffix}"] = r.get("vicinity","")
            loc = r.get("geometry",{}).get("location",{})
            df.at[i, f"latitude{suffix}"] = loc.get("lat","")
            df.at[i, f"longtitude{suffix}"] = loc.get("lng","")
            df.at[i, f"Status{suffix}"] = "OK"
        else:
            df.at[i, f"Status{suffix}"] = js.get("status","ZERO_RESULTS")

    return df

@app.route("/run_nearby", methods=["POST"])
def run_nearby():
    df = pd.read_excel(request.files["file"])
    df = run_nearby_like(
        df,
        request.form["lat_col"],
        request.form["long_col"],
        request.form["kw_col"],
        GOOGLE_API_KEY,
        "_nearby"
    )
    out = os.path.join(OUTPUT_DIR, "nearby_output.xlsx")
    df.to_excel(out, index=False)
    return jsonify({"download_url": "/download/nearby_output.xlsx", "log": "Done Nearby"})

@app.route("/run_building", methods=["POST"])
def run_building():
    df = pd.read_excel(request.files["file"])
    df["_kw"] = request.form["kw_col"]
    df = run_nearby_like(
        df,
        request.form["lat_col"],
        request.form["long_col"],
        "_kw",
        GOOGLE_API_KEY,
        "_building"
    )
    out = os.path.join(OUTPUT_DIR, "building_output.xlsx")
    df.to_excel(out, index=False)
    return jsonify({"download_url": "/download/building_output.xlsx", "log": "Done Building"})

# =========================================================
# GEOCODE MAP4D — FULL VERSION + AUTOSAVE
# =========================================================
@app.route("/run_geocode_tach_cot", methods=["POST"])
def run_geocode_tach_cot():
    try:
        df = pd.read_excel(request.files["file"])
        lat_col = request.form["lat_col"]
        long_col = request.form["long_col"]

        session = requests.Session()
        url = "https://api.map4d.vn/sdk/v2/geocode"

        ac_list = []
        ac_old_list = []

        autosave_path = os.path.join(OUTPUT_DIR, "autosave_geocode.xlsx")

        for idx, row in df.iterrows():
            lat = row[lat_col]
            lon = row[long_col]

            if pd.isna(lat) or pd.isna(lon):
                ac_list.append("[]")
                ac_old_list.append("[]")
                continue

            try:
                resp = session.get(url, params={"location": f"{lat},{lon}", "key": MAP4D_API_KEY}, timeout=10)
                js = resp.json()
                result = js.get("result",[{}])[0]

                addr = result.get("addressComponents",[])
                addr_old = result.get("oldAddressComponents",[])

                ac_list.append(json.dumps(addr, ensure_ascii=False))
                ac_old_list.append(json.dumps(addr_old, ensure_ascii=False))

                # TÁCH CỘT CHUẨN
                for comp in addr:
                    name = comp.get("name","")
                    for t in comp.get("types",[]):
                        df.at[idx, t] = name

                for comp in addr_old:
                    name = comp.get("name","")
                    for t in comp.get("types",[]):
                        df.at[idx, f"old_{t}"] = name

            except Exception as e:
                ac_list.append(str(e))
                ac_old_list.append(str(e))

            # AUTOSAVE mỗi 10 dòng
            if (idx+1) % 10 == 0:
                try:
                    df["addressComponents"] = ac_list + [""] * (len(df)-len(ac_list))
                    df["oldAddressComponents"] = ac_old_list + [""] * (len(df)-len(ac_old_list))
                    df.to_excel(autosave_path, index=False)
                except:
                    pass

        # Hoàn tất padding
        df["addressComponents"] = ac_list + [""] * (len(df)-len(ac_list))
        df["oldAddressComponents"] = ac_old_list + [""] * (len(df)-len(ac_old_list))

        out = os.path.join(OUTPUT_DIR, "geocode_output.xlsx")
        df.to_excel(out, index=False)

        return jsonify({"download_url": "/download/geocode_output.xlsx", "log": "Done Geocode"})

    except Exception as e:
        return jsonify({"error": str(e)})

# =========================================================
# TẢI FILE
# =========================================================
@app.route("/download/<path:f>")
def download_file(f):
    return send_from_directory(OUTPUT_DIR, f, as_attachment=True)

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

def open_browser():
    try: webbrowser.open("http://127.0.0.1:5000")
    except: pass

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run()
