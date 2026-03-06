import json

# Đọc file GeoJSON gốc
file_path = 'Htrang_RachTram.geojson'

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Lấy danh sách các features
features = data['features']

# Lưu từng feature vào một file GeoJSON riêng biệt
output_files = []
for i, feature in enumerate(features):
    # Tạo một GeoJSON mới chỉ chứa một feature
    feature_geojson = {
        "type": "FeatureCollection",
        "features": [feature]
    }

    # Đặt tên file xuất
    output_file_path = f'feature_{i + 1}.geojson'

    # Ghi dữ liệu vào file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(feature_geojson, f, ensure_ascii=False, indent=4)

    # Lưu đường dẫn của file xuất vào danh sách
    output_files.append(output_file_path)

# In ra danh sách các file đã được tạo
print(output_files)
