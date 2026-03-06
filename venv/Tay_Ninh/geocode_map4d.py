import os
import pandas as pd
import requests
import time
import re
import shutil

# ==== Cấu hình Map4D ====
API_KEY = "93d393d0f6507ee00b62fe01db7430fa"
BASE_URL = "https://api.map4d.vn/sdk/v2/geocode"
AUTOSAVE_EVERY = 20  # Lưu tạm mỗi 20 dòng

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
        return None, None
    except Exception:
        return None, None

# ==== Làm sạch ký tự lỗi ====
def clean_text(text):
    if not isinstance(text, str):
        return None
    try:
        cleaned = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)
        return cleaned.strip() if cleaned.strip() else None
    except Exception:
        return None

# ==== 1️⃣ Nhập thư mục và tên file ====
folder = input("📂 Nhập thư mục chứa file Excel: ").strip()
filename = input("📄 Nhập tên file Excel (ví dụ data.xlsx): ").strip()

input_path = os.path.join(folder, filename)
if not os.path.exists(input_path):
    raise FileNotFoundError(f"❌ Không tìm thấy file: {input_path}")

# ==== 2️⃣ Xác định file output và autosave ====
output_file = os.path.join(folder, "Scan_with_new_address_map4d.xlsx")
temp_file = os.path.join(folder, "Scan_autosave.xlsx")
temp_file_tmp = temp_file + ".tmp"

print(f"\n📄 Input: {input_path}")
print(f"💾 Output: {output_file}")
print(f"⚙️  Autosave: {temp_file}\n")

# ==== 3️⃣ Đọc dữ liệu (ưu tiên autosave nếu có) ====
if os.path.exists(temp_file):
    print(f"⚙️  Phát hiện file tạm '{temp_file}' — tiếp tục xử lý phần còn lại...")
    df = pd.read_excel(temp_file)
else:
    df = pd.read_excel(input_path)

# ==== 4️⃣ Chuẩn hóa tên cột ====
df.columns = [str(c).strip() for c in df.columns]

# ==== 5️⃣ Thêm 2 cột address/oldaddress nếu chưa có ====
if "address" not in df.columns:
    df["address"] = None
if "oldaddress" not in df.columns:
    df["oldaddress"] = None

# ==== 6️⃣ Kiểm tra cột Lat / Long ====
if "Lat" not in df.columns or "Long" not in df.columns:
    raise ValueError("❌ File Excel phải có 2 cột: 'Lat' và 'Long'")

lat_col = "Lat"
lng_col = "Long"

# ==== 7️⃣ Bắt đầu xử lý ====
total = len(df)
print(f"👉 Tìm thấy {total} bản ghi. Bắt đầu xử lý...\n")

for idx, row in df.iterrows():
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

    # ==== Autosave an toàn ====
    if (idx + 1) % AUTOSAVE_EVERY == 0 or (idx + 1) == total:
        try:
            df.to_excel(temp_file_tmp, index=False)
            import shutil
            shutil.move(temp_file_tmp, temp_file)
            print(f"💾 Autosave tại record {idx+1}/{total}")
        except Exception as e:
            print(f"⚠️  Lỗi autosave: {e}")

    time.sleep(0.2)

# ==== Ghi file kết quả ====
df.to_excel(output_file, index=False)
if os.path.exists(temp_file):
    os.remove(temp_file)

print(f"\n🎯 Hoàn tất! File kết quả: {output_file}")
