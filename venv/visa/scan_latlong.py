import pandas as pd
import requests
import time
import os
import re

# ==== Cấu hình ====
API_KEY = "93d393d0f6507ee00b62fe01db7430fa"
INPUT_FILE = "addr_map4d.xlsx"                    # File đầu vào
OUTPUT_FILE = "Scan_with_new_address_map4d.xlsx"  # File đầu ra
TEMP_FILE = "Scan_autosave.xlsx"            # File autosave
BASE_URL = "https://api.map4d.vn/sdk/v2/geocode"
AUTOSAVE_EVERY = 20                         # Lưu tạm sau mỗi 20 dòng

# ==== Hàm gọi API Map4D ====
def get_address_pair(lat, lng):
    url = f"{BASE_URL}?location={lat}%2C{lng}&key={API_KEY}"
    try:
        response = requests.get(url, headers={"accept": "application/json"}, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and len(data["result"]) > 0:
                res = data["result"][0]
                new_addr = res.get("address", "")
                old_addr = res.get("oldAddress", "")
                return new_addr or None, old_addr or None
            else:
                return None, None
        else:
            return None, None
    except Exception:
        return None, None

# ==== Làm sạch ký tự lỗi (Excel không chấp nhận) ====
def clean_text(text):
    if not isinstance(text, str):
        return None
    try:
        cleaned = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)
        cleaned.encode("utf-8").decode("utf-8")
        return cleaned.strip() if cleaned.strip() else None
    except Exception:
        return None

# ==== Đọc file (ưu tiên autosave nếu có) ====
if os.path.exists(TEMP_FILE):
    print(f"⚙️  Phát hiện file tạm '{TEMP_FILE}' — tiếp tục xử lý phần còn lại...")
    df = pd.read_excel(TEMP_FILE)
else:
    df = pd.read_excel(INPUT_FILE)

# ==== Chuẩn hóa tên cột ====
df.columns = [str(c).strip().lower() for c in df.columns]

# ==== Kiểm tra các cột cần thiết ====
if "address" not in df.columns:
    raise ValueError("❌ File Excel phải có cột 'address'")
if "oldaddress" not in df.columns:
    raise ValueError("❌ File Excel phải có cột 'oldaddress'")

# ==== Ép kiểu 2 cột sang text (object) ====
df["address"] = df["address"].astype("object")
df["oldaddress"] = df["oldaddress"].astype("object")

# ==== Xác định cột lat/long ====
lat_candidates = ["lat", "latitude", "derived_lat_v2", "derived_lat_v1"]
lng_candidates = ["long", "lng", "longitude", "derived_long_v2", "derived_long_v1"]

lat_col = next((c for c in df.columns if c.lower() in lat_candidates), None)
lng_col = next((c for c in df.columns if c.lower() in lng_candidates), None)

if not lat_col or not lng_col:
    raise ValueError(f"❌ Không tìm thấy cột lat/long. Các cột có: {list(df.columns)}")

print(f"👉 Dùng cột: {lat_col} / {lng_col}")

# ==== Xử lý từng record ====
total = len(df)
print(f"\n🔄 Bắt đầu xử lý {total} records...\n")

for idx, row in df.iterrows():
    # Bỏ qua nếu đã có dữ liệu hợp lệ
    if pd.notna(row.get("address")) and str(row["address"]).strip() not in ("", "Không tìm thấy địa chỉ"):
        continue

    try:
        lat = float(row[lat_col])
        lng = float(row[lng_col])
        if lat == 0 or lng == 0:
            raise ValueError("Tọa độ không hợp lệ (0,0)")
    except Exception:
        df.at[idx, "address"] = None
        df.at[idx, "oldaddress"] = None
        print(f"⚠️  Bỏ qua record {idx+1}/{total}: tọa độ không hợp lệ\n")
        continue

    print(f"➡️  Đang xử lý record {idx+1}/{total}: ({lat}, {lng})", flush=True)
    addr, old_addr = get_address_pair(lat, lng)
    addr = clean_text(addr)
    old_addr = clean_text(old_addr)

    df.at[idx, "address"] = addr
    df.at[idx, "oldaddress"] = old_addr

    print(f"✅  -> address: {addr if addr else 'NULL'}")
    print(f"🏠  -> oldaddress: {old_addr if old_addr else 'NULL'}\n", flush=True)

    # ==== Autosave theo chu kỳ ====
    if (idx + 1) % AUTOSAVE_EVERY == 0 or (idx + 1) == total:
        try:
            df.to_excel(TEMP_FILE, index=False)
            print(f"💾 Autosave tại record {idx+1}/{total}")
        except Exception as e:
            print(f"⚠️  Lỗi khi ghi autosave (bỏ qua): {e}")

    time.sleep(0.2)  # tránh giới hạn API

# ==== Khi hoàn tất, ghi file kết quả chính ====
df.to_excel(OUTPUT_FILE, index=False)
if os.path.exists(TEMP_FILE):
    os.remove(TEMP_FILE)

print(f"\n🎯 Hoàn tất! File kết quả: {OUTPUT_FILE}")
