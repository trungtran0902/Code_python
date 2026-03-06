import requests
import pandas as pd
import json
import os

# ====== HÀM GỌI API GEO CODE ======
def geocode(location):
    url = 'https://api.map4d.vn/sdk/v2/geocode'
    params = {
        'location': location,
        'key': '93d393d0f6507ee00b62fe01db7430fa'  # ⚠️ Thay bằng API key của bạn
    }
    headers = {'accept': 'application/json'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Lỗi API {response.status_code} cho tọa độ {location}")
            return None
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
        return None


# ====== HÀM GIẢI MÃ UNICODE ======
def decode_unicode(data):
    return bytes(data, "utf-8").decode("unicode_escape")


# ====== NHẬP THÔNG TIN FILE ======
input_dir = input("Nhập đường dẫn tới thư mục chứa file Excel (vd: C:\\Users\\Admin\\Documents): ").strip()
file_name = input("Nhập tên file Excel (vd: mau.xlsx): ").strip()

# Ghép thành đường dẫn đầy đủ
input_path = os.path.join(input_dir, file_name)

# Kiểm tra tồn tại file
if not os.path.exists(input_path):
    print(f"❌ Không tìm thấy file: {input_path}")
    exit()

# ====== ĐỌC FILE EXCEL ======
df = pd.read_excel(input_path)
if 'Lat' not in df.columns or 'Long' not in df.columns:
    print("❌ File Excel phải có cột 'Lat' và 'Long'.")
    exit()

# ====== GỌI API CHO TỪNG DÒNG ======
address_components_data = []
old_address_components_data = []

for idx, row in df.iterrows():
    lat = row['Lat']
    long = row['Long']
    location = f"{lat},{long}"

    print(f"🔹 Đang xử lý tọa độ {location} ({idx + 1}/{len(df)})...")
    result = geocode(location)

    if result:
        address_components_raw = json.dumps(
            result.get('result', [{}])[0].get('addressComponents', [])
        )
        old_address_components_raw = json.dumps(
            result.get('result', [{}])[0].get('oldAddressComponents', [])
        )
        address_components_data.append(decode_unicode(address_components_raw))
        old_address_components_data.append(decode_unicode(old_address_components_raw))
    else:
        address_components_data.append('[]')
        old_address_components_data.append('[]')

# ====== GHI RA FILE KẾT QUẢ ======
df['addressComponents'] = address_components_data
df['oldAddressComponents'] = old_address_components_data

# Tạo tên file mới trong cùng thư mục
output_name = f"processed_{file_name}"
output_path = os.path.join(input_dir, output_name)

df.to_excel(output_path, index=False, engine='openpyxl')
print(f"\n✅ Đã xử lý xong! Kết quả được lưu tại:\n{output_path}")
