import requests
import pandas as pd
import json
import re


# Hàm gọi API Geocode và lấy kết quả
def geocode(location):
    url = 'https://api.map4d.vn/sdk/v2/geocode'
    params = {
        'location': location,  # Vị trí (latitude, longitude)
        'key': '93d393d0f6507ee00b62fe01db7430fa'  # API key của bạn
    }
    headers = {
        'accept': 'application/json'  # Định dạng phản hồi là JSON
    }

    # Gửi yêu cầu GET đến API
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        return response.json()  # Trả về dữ liệu JSON nếu thành công
    else:
        print(f"Lỗi khi gọi API. Mã lỗi: {response.status_code}")
        return None


# Hàm để chuyển chuỗi Unicode thành ký tự thực
def decode_unicode(data):
    return bytes(data, "utf-8").decode("unicode_escape")


# Hàm tách dữ liệu addressComponents thành các cột riêng
def extract_address_components(data):
    address_data = {}

    if data:
        for component in data:
            types = component.get('types', [])
            name = component.get('name', '')

            for type_ in types:
                # Nếu 'type' đã có trong address_data thì không cần thêm lại
                if type_ not in address_data:
                    address_data[type_] = name
    return address_data


# Đọc file chứa các tọa độ (lat, long)
input_file = 'tach_address.xlsx'  # Thay bằng đường dẫn đúng tới file Excel của bạn
df = pd.read_excel(input_file)

# Duyệt qua từng tọa độ trong file và gọi API
address_components_data = []
old_address_components_data = []

for idx, row in df.iterrows():
    lat = row['Lat']
    long = row['Long']
    location = f"{lat},{long}"

    # Gọi API và lấy kết quả
    result = geocode(location)

    if result:
        # In kết quả trả về để kiểm tra
        print(f"API trả về kết quả cho tọa độ {location}:")
        print(result)  # In toàn bộ dữ liệu trả về

        # Lưu toàn bộ dữ liệu trong addressComponents và oldAddressComponents dưới dạng JSON
        address_components_raw = json.dumps(
            result.get('result', [{}])[0].get('addressComponents', []))  # Chuyển sang chuỗi JSON
        old_address_components_raw = json.dumps(
            result.get('result', [{}])[0].get('oldAddressComponents', []))  # Chuyển sang chuỗi JSON

        # Chuyển chuỗi Unicode thành ký tự thực
        address_components_data.append(decode_unicode(address_components_raw))
        old_address_components_data.append(decode_unicode(old_address_components_raw))

        # Tách các trường trong addressComponents và oldAddressComponents thành các cột
        address_data = extract_address_components(result.get('result', [{}])[0].get('addressComponents', []))
        old_address_data = extract_address_components(result.get('result', [{}])[0].get('oldAddressComponents', []))

        # Cập nhật các cột mới vào DataFrame
        for key, value in address_data.items():
            df.at[idx, key] = value

        for key, value in old_address_data.items():
            df.at[idx, f"old_{key}"] = value
    else:
        # Nếu không có dữ liệu trả về, thêm vào giá trị trống
        address_components_data.append('[]')
        old_address_components_data.append('[]')

# Thêm các cột mới vào DataFrame
df['addressComponents'] = address_components_data
df['oldAddressComponents'] = old_address_components_data

# Lưu kết quả vào file Excel mới với openpyxl
output_file = 'processed_mau_tach_cot_tach_address.xlsx'
df.to_excel(output_file, index=False, engine='openpyxl')
print(f"Đã lưu kết quả vào {output_file}")
