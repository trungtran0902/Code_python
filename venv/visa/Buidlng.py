import pandas as pd
import requests
import os

# Lấy đường dẫn hiện tại của file Python
script_dir = os.path.dirname(os.path.abspath(__file__))

# Đường dẫn tới file Excel cùng thư mục với file Python
excel_file_path = os.path.join(script_dir, 'Building.xlsx')  # Thay 'file_path.xlsx' bằng tên file Excel của bạn

# Đọc dữ liệu từ file Excel
df = pd.read_excel(excel_file_path)

# Loại bỏ dấu cách thừa trong tên cột nếu có
df.columns = df.columns.str.strip()

# Đảm bảo các cột 'Name' và 'Address' có kiểu dữ liệu là string (chuỗi)
df['Name'] = df['Name'].astype(str)
df['Address'] = df['Address'].astype(str)

# API Key từ Google (đã điền sẵn)
API_KEY = 'AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU'  # API key của bạn


# Hàm gọi Google Places API
def get_places_data(lat, long, keyword):
    url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
    params = {
        'location': f'{lat},{long}',
        'radius': 50,  # Bán kính m
        'keyword': keyword,
        'key': API_KEY
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            place = results[0]  # Lấy kết quả đầu tiên
            name = place.get('name', 'Không có tên')
            address = place.get('vicinity', 'Không có địa chỉ')
            location = place.get('geometry', {}).get('location', {})
            lat_res = location.get('lat', 'Không có vĩ độ')
            lng_res = location.get('lng', 'Không có kinh độ')
            return name, address, lat_res, lng_res
    return None, None, None, None


# Đường dẫn lưu file kết quả
output_file_path = os.path.join(script_dir, 'data_2_output_V1.xlsx')  # Kết quả sẽ được lưu vào file này

# Duyệt qua từng dòng dữ liệu trong DataFrame
for index, row in df.iterrows():
    lat = row['Lat_v1']
    long = row['Long_v1']
    keyword = row['Keyword']  # Lấy từ khóa từ cột Keyword

    print(f"Đang xử lý dòng {index + 1}/{len(df)} - Tọa độ: ({lat}, {long}), Từ khóa: {keyword}")

    # Gọi API và lấy kết quả
    name, address, lat_res, long_res = get_places_data(lat, long, keyword)

    # Cập nhật kết quả vào DataFrame
    df.at[index, 'Name'] = name
    df.at[index, 'Address'] = address
    # Gán vĩ độ và kinh độ trả về vào cột Location dưới dạng "lat, long"
    df.at[index, 'Location'] = f'{lat_res}, {long_res}'

    # Lưu dữ liệu liên tục sau mỗi dòng
    df.to_excel(output_file_path, index=False)
    print(f"Dòng {index + 1} đã được cập nhật và lưu.")

# In thông báo hoàn thành
print("Hoàn thành việc cập nhật dữ liệu. Kết quả đã được lưu vào 'output_file.xlsx'.")
