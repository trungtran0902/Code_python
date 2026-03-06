# ========== excel_tool.py — FULL FINAL VERSION (Nearby + Details + Building + Geocode + Fix Excel Corruption) ==========

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

# ====== API KEY — NHỚ THAY ======
GOOGLE_API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"
MAP4D_API_KEY  = "93d393d0f6507ee00b62fe01db7430fa"

app = Flask(__name__)

# =====================================================================
# FIX LỖI HỎNG FILE EXCEL (KÝ TỰ XML KHÔNG HỢP LỆ)
# =====================================================================
def clean_excel_value(value):
    """Loại bỏ ký tự không hợp lệ khiến Excel bị corrupt."""
    if value is None:
        return ""

    text = str(value)

    invalid_chars = [
        "\x00","\x01","\x02","\x03","\x04","\x05","\x06",
        "\x07","\x08","\x0B","\x0C","\x0E","\x0F",
        "\x10","\x11","\x12","\x13","\x14","\x15",
        "\x16","\x17","\x18","\x19","\x1A","\x1B",
        "\x1C","\x1D","\x1E","\x1F"
    ]
    for ch in invalid_chars:
        text = text.replace(ch, "")

    # Loại bỏ xuống dòng cứng gây lỗi
    text = text.replace("\r", " ").replace("\n", " ")

    return text


# =========================================================
# GIAO DIỆN HTML — UI ĐẸP (FINAL)
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
let controller = {};

async function getColumns(type) {
  const f = document.getElementById("file-"+type).files[0];
  const d = document.getElementById("cols-"+type);
  if (!f) { d.innerHTML=""; return; }

  d.innerHTML="⏳ Đang đọc cột...";

  const form = new FormData();
  form.append("file", f);

  const res = await fetch("/preview_columns", { method:"POST", body:form });
  const data = await res.json();

  if (data.error) { d.innerHTML = "❌ " + data.error; return; }

  let opt = data.columns.map(c=>`<option>${c}</option>`).join("");

  d.innerHTML = `
    <label>Lat:</label><select id="lat-${type}">${opt}</select>
    <label>Long:</label><select id="long-${type}">${opt}</select>
    ${type==="nearby" ? `<label>Từ khóa (cột):</label><select id="kwcol-nearby">${opt}</select>` : ""}
  `;
}

async function runProcess(type) {
  const file = document.getElementById("file-"+type).files[0];
  const out = document.getElementById("out-"+type);
  if (!file) { out.textContent="❗ Chưa chọn file"; return; }

  const form = new FormData();
  form.append("file", file);
  form.append("lat_col", document.getElementById("lat-"+type)?.value || "");
  form.append("long_col", document.getElementById("long-"+type)?.value || "");

  if (type==="building") form.append("kw_col", document.getElementById("kw-building").value);
  if (type==="nearby") form.append("kw_col", document.getElementById("kwcol-nearby")?.value || "");

  out.textContent="⏳ Đang xử lý...";

  controller[type] = new AbortController();

  try {
    const res = await fetch("/run_"+type, { method:"POST", body:form, signal:controller[type].signal });
    const data = await res.json();
    out.textContent = data.error ? ("❌ "+data.error) : (data.log + "\\n📁 " + data.download_url);
  } catch {
    out.textContent="⚠ Đã hủy.";
  }
}

function cancelProcess(type){
  controller[type]?.abort();
  document.getElementById("out-"+type).textContent="⚠ Đã hủy.";
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
# API: LẤY CỘT — tối ưu chỉ đọc header
# =========================================================
@app.route("/preview_columns", methods=["POST"])
def preview_columns():
    try:
        file = request.files["file"]
        df = pd.read_excel(file, nrows=0)  # đọc header thôi → cực nhanh
        return jsonify({"columns": list(df.columns)})
    except Exception as e:
        return jsonify({"error": str(e)})



# =========================================================
# HÀM CHÍNH: Nearby Search + Place Details
# =========================================================
def run_nearby_like(df, lat_col, long_col, kw_col, key, suffix=""):

    session = requests.Session()

    url_nearby = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    url_detail = "https://maps.googleapis.com/maps/api/place/details/json"

    # ====== tạo cột đầu ra ======
    output_cols = [
        f"Name{suffix}",
        f"Address{suffix}",
        f"latitude{suffix}",
        f"longtitude{suffix}",
        f"Status{suffix}",
        f"Phone{suffix}",
        f"Website{suffix}",
        f"OpeningHours{suffix}"
    ]

    for c in output_cols:
        if c not in df.columns:
            df[c] = ""

    # ====== xử lý từng dòng ======
    for i, row in df.iterrows():

        print("\n==============================")
        print(f"🟦 Nearby Row {i}")

        # ----------- xử lý lat/long ----------
        try:
            lat = float(str(row[lat_col]).replace(",", ".").strip())
            lon = float(str(row[long_col]).replace(",", ".").strip())
        except:
            print("❌ Sai lat/lon")
            df.at[i, f"Status{suffix}"] = "Invalid Lat/Lon"
            continue

        kw = str(row[kw_col]).strip() if kw_col else ""

        print("Lat:", lat, "| Lon:", lon, "| Kw:", kw)

        # ----------- gọi Nearby Search ----------
        params = {
            "location": f"{lat},{lon}",
            "radius": 700,
            "key": key,
            "language": "vi"
        }
        if kw:
            params["keyword"] = kw

        try:
            res = session.get(url_nearby, params=params, timeout=15)
            near = res.json()
            results = near.get("results", [])
        except Exception as e:
            df.at[i, f"Status{suffix}"] = clean_excel_value(f"Error nearby: {e}")
            continue

        if not results:
            status_txt = near.get("status", "ZERO_RESULTS")
            df.at[i, f"Status{suffix}"] = clean_excel_value(status_txt)
            print("⚠ Nearby:", status_txt)
            continue

        first = results[0]

        # ========== GHI KẾT QUẢ NEARBY ==========
        df.at[i, f"Name{suffix}"]       = clean_excel_value(first.get("name", ""))
        df.at[i, f"Address{suffix}"]    = clean_excel_value(first.get("vicinity", ""))
        df.at[i, f"latitude{suffix}"]   = clean_excel_value(first.get("geometry", {}).get("location", {}).get("lat", ""))
        df.at[i, f"longtitude{suffix}"] = clean_excel_value(first.get("geometry", {}).get("location", {}).get("lng", ""))
        df.at[i, f"Status{suffix}"]     = "OK"

        # ========== GỌI PLACE DETAILS ==========
        place_id = first.get("place_id")

        if not place_id:
            print("⚠ Không có place_id → bỏ qua Details")
            continue

        print("🔍 place_id:", place_id)

        detail_params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,international_phone_number,website,opening_hours",
            "key": key,
            "language": "vi"
        }

        try:
            detail_res = session.get(url_detail, params=detail_params, timeout=15).json()
            detail = detail_res.get("result", {})
        except Exception as e:
            print("❌ Lỗi gọi Place Details:", e)
            continue

        # ------ phone ------
        phone = detail.get("formatted_phone_number") or detail.get("international_phone_number")

        # ------ website ------
        website = detail.get("website", "")

        # ------ opening hours ------
        oh = ""
        try:
            if detail.get("opening_hours") and detail["opening_hours"].get("weekday_text"):
                oh_list = detail["opening_hours"]["weekday_text"]
                oh = clean_excel_value(" | ".join(oh_list))
        except:
            oh = ""

        # ------ lưu vào dataframe ------
        df.at[i, f"Phone{suffix}"]        = clean_excel_value(phone)
        df.at[i, f"Website{suffix}"]      = clean_excel_value(website)
        df.at[i, f"OpeningHours{suffix}"] = oh

        print("✓ Lấy Details: phone, website, opening hours")

    return df




# =========================================================
# API: RUN NEARBY
# =========================================================
@app.route("/run_nearby", methods=["POST"])
def run_nearby():
    try:
        df = pd.read_excel(request.files["file"])

        df = run_nearby_like(
            df,
            request.form["lat_col"],
            request.form["long_col"],
            request.form["kw_col"],
            GOOGLE_API_KEY,
            "_nearby"
        )

        out_path = os.path.join(OUTPUT_DIR, "nearby_output.xlsx")
        df.to_excel(out_path, index=False, engine="openpyxl")

        return jsonify({
            "download_url": "/download/nearby_output.xlsx",
            "log": "Hoàn tất Nearby Search"
        })

    except Exception as e:
        return jsonify({"error": str(e)})



# =========================================================
# API: RUN BUILDING (GIỮ NGUYÊN, CHỈ CLEAN VALUE)
# =========================================================
@app.route("/run_building", methods=["POST"])
def run_building():
    try:
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

        out_path = os.path.join(OUTPUT_DIR, "building_output.xlsx")
        df.to_excel(out_path, index=False, engine="openpyxl")

        return jsonify({
            "download_url": "/download/building_output.xlsx",
            "log": "Hoàn tất Building"
        })

    except Exception as e:
        return jsonify({"error": str(e)})
# =========================================================
# GEOCODE MAP4D — TÁCH CỘT + AUTOSAVE + CLEAN
# =========================================================
@app.route("/run_geocode_tach_cot", methods=["POST"])
def run_geocode_tach_cot():
    try:
        df = pd.read_excel(request.files["file"])
        lat_col  = request.form["lat_col"]
        long_col = request.form["long_col"]

        if lat_col not in df.columns or long_col not in df.columns:
            return jsonify({"error": "Cột lat/long không hợp lệ."})

        session = requests.Session()
        url = "https://api.map4d.vn/sdk/v2/geocode"

        ac_list = []       # lưu JSON addressComponents
        ac_old_list = []   # lưu JSON oldAddressComponents

        autosave_path = os.path.join(OUTPUT_DIR, "autosave_geocode.xlsx")

        print("\n===== BẮT ĐẦU GEOCODE MAP4D =====")

        for idx, row in df.iterrows():
            lat = row[lat_col]
            lon = row[long_col]

            print(f"\n--- Row {idx} ---")
            print("Lat:", lat, "| Lon:", lon)

            if pd.isna(lat) or pd.isna(lon):
                ac_list.append("[]")
                ac_old_list.append("[]")
                print("⚠ Thiếu lat/lon, bỏ qua.")
                continue

            try:
                resp = session.get(
                    url,
                    params={"location": f"{lat},{lon}", "key": MAP4D_API_KEY},
                    timeout=10
                )
                js = resp.json()
                result = js.get("result", [{}])[0]

                addr = result.get("addressComponents", [])
                addr_old = result.get("oldAddressComponents", [])

                # Lưu JSON gốc (được clean trước khi ghi vào Excel)
                ac_list.append(clean_excel_value(json.dumps(addr, ensure_ascii=False)))
                ac_old_list.append(clean_excel_value(json.dumps(addr_old, ensure_ascii=False)))

                # TÁCH CỘT MỚI THEO types
                for comp in addr:
                    name = clean_excel_value(comp.get("name", ""))
                    for t in comp.get("types", []):
                        df.at[idx, t] = name

                # TÁCH CỘT ĐỊA CHỈ CŨ
                for comp in addr_old:
                    name = clean_excel_value(comp.get("name", ""))
                    for t in comp.get("types", []):
                        df.at[idx, f"old_{t}"] = name

                print("✓ Đã parse", len(addr), "components, old:", len(addr_old))

            except Exception as e:
                err_txt = clean_excel_value(f"Error geocode: {e}")
                ac_list.append(err_txt)
                ac_old_list.append(err_txt)
                print("Lỗi geocode:", e)

            # AUTOSAVE mỗi 10 dòng
            if (idx + 1) % 10 == 0:
                try:
                    tmp_ac = ac_list + [""] * (len(df) - len(ac_list))
                    tmp_old_ac = ac_old_list + [""] * (len(df) - len(ac_old_list))
                    df["addressComponents"] = [clean_excel_value(v) for v in tmp_ac]
                    df["oldAddressComponents"] = [clean_excel_value(v) for v in tmp_old_ac]
                    df.to_excel(autosave_path, index=False, engine="openpyxl")
                    print("💾 Autosave tại dòng", idx + 1)
                except Exception as e:
                    print("Autosave lỗi:", e)

        # Padding cuối, đảm bảo độ dài khớp số dòng
        ac_list.extend([""] * (len(df) - len(ac_list)))
        ac_old_list.extend([""] * (len(df) - len(ac_old_list)))

        df["addressComponents"] = [clean_excel_value(v) for v in ac_list]
        df["oldAddressComponents"] = [clean_excel_value(v) for v in ac_old_list]

        out_path = os.path.join(OUTPUT_DIR, "geocode_output.xlsx")
        df.to_excel(out_path, index=False, engine="openpyxl")

        print("===== HOÀN TẤT GEOCODE MAP4D =====")

        return jsonify({
            "download_url": "/download/geocode_output.xlsx",
            "log": "Hoàn tất Geocode Map4D"
        })

    except Exception as e:
        return jsonify({"error": str(e)})



# =========================================================
# TẢI FILE & INDEX
# =========================================================
@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)



# =========================================================
# TỰ ĐỘNG MỞ TRÌNH DUYỆT & CHẠY APP
# =========================================================
def open_browser():
    try:
        webbrowser.open("http://127.0.0.1:5000")
    except:
        pass


if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run(host="127.0.0.1", port=5000)
