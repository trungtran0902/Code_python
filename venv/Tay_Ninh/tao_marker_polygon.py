import pandas as pd
import json
import os

# Đọc tệp Excel vào DataFrame
df = pd.read_excel('test.xlsx')

# In ra các cột để kiểm tra
print("Danh sách các cột trong DataFrame:")
print(df.columns)

# Đếm tổng số lượng các cột
num_columns = len(df.columns)
print(f"\nTổng số lượng các cột trong DataFrame: {num_columns}")

# Lưu tất cả các tên cột
columns = df.columns.tolist()

# Tạo danh sách chứa các feature GeoJSON
geojson_features = []

# Hàm để phân tách tọa độ từ chuỗi "Định vị toạ độ"
def parse_coordinates(coord_string):
    # Tách các cặp tọa độ, mỗi cặp tọa độ cách nhau bằng dấu ";"
    coords = coord_string.split(';')  # Tách các cặp tọa độ
    lat_lng_pairs = []
    for coord in coords:
        lat, lng = map(float, coord.split(','))  # Chuyển đổi tọa độ thành số
        lat_lng_pairs.append([lng, lat])  # Chú ý, thứ tự là [longitude, latitude]
    return lat_lng_pairs

# Duyệt qua từng hàng trong DataFrame và tạo feature GeoJSON
for index, row in df.iterrows():
    # Kiểm tra giá trị của cột "Trạng Thái Xử Lý Dữ Liệu"
    if row['Trạng Thái Xử Lý Dữ Liệu'] == "Hoàn Thành":
        print(f"Đã bỏ qua dự án {row['Tên dự án']} vì trạng thái là 'Hoàn Thành'.")
        continue  # Bỏ qua hàng này nếu trạng thái là 'Hoàn Thành'

    coord_string = row['Định vị toạ độ']
    if pd.notna(coord_string):
        coordinates = parse_coordinates(coord_string)

        # Nếu có 3 cặp tọa độ trở xuống, tạo Marker từ tọa độ đầu tiên
        if len(coordinates) <= 3:
            geometry = {
                "type": "Point",
                "coordinates": coordinates[0]  # Chỉ lấy cặp tọa độ đầu tiên
            }
        else:
            # Nếu có từ 4 cặp tọa độ trở lên, tạo Polygon
            geometry = {
                "type": "Polygon",
                "coordinates": [coordinates]  # Đưa vào dưới dạng list
            }

        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {}
        }

        # Thêm tất cả các cột vào phần "properties" của GeoJSON
        for column in columns:
            feature["properties"][column] = row[column] if pd.notna(
                row[column]) else None  # Nếu không có dữ liệu, gán là null

        geojson_features.append(feature)

# Chọn cách xuất dữ liệu (Toàn bộ vào 1 file GeoJSON hoặc từng file GeoJSON riêng biệt)
def export_geojson():
    # Yêu cầu người dùng nhập đường dẫn lưu tệp
    path = input("Nhập đường dẫn lưu tệp GeoJSON (ví dụ: C:/DuongDan/): ").strip()

    # Kiểm tra nếu đường dẫn không hợp lệ
    if not os.path.exists(path):
        print("Đường dẫn không hợp lệ. Vui lòng kiểm tra lại.")
        return

    # Hỏi người dùng muốn xuất toàn bộ dữ liệu vào 1 tệp GeoJSON hay từng tệp GeoJSON riêng biệt
    print("\nChọn phương thức xuất:")
    print("1. Xuất toàn bộ vào 1 tệp GeoJSON")
    print("2. Xuất từng tệp GeoJSON riêng biệt")

    choice = input("Nhập lựa chọn (1 hoặc 2): ").strip()

    if choice == "1":
        # Xuất toàn bộ dữ liệu vào 1 tệp GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": geojson_features
        }

        output_file_path = os.path.join(path, "output.geojson")
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=4)
        print(f"Tất cả dữ liệu đã được xuất vào tệp {output_file_path}.")

    elif choice == "2":
        # Xuất từng tệp GeoJSON riêng biệt cho mỗi dự án
        for index, row in df.iterrows():
            project_name = row["Tên dự án"]  # Giả sử "Tên dự án" là tên cột
            coord_string = row['Định vị toạ độ']

            # Kiểm tra giá trị của cột "Trạng Thái Xử Lý Dữ Liệu"
            if row['Trạng Thái Xử Lý Dữ Liệu'] == "Hoàn Thành":
                print(f"Đã bỏ qua dự án {row['Tên dự án']} vì trạng thái là 'Hoàn Thành'.")
                continue  # Bỏ qua nếu trạng thái là 'Hoàn Thành'

            if pd.notna(coord_string):
                coordinates = parse_coordinates(coord_string)

                # Nếu có 3 cặp tọa độ trở xuống, tạo Marker từ tọa độ đầu tiên
                if len(coordinates) <= 3:
                    geometry = {
                        "type": "Point",
                        "coordinates": coordinates[0]  # Chỉ lấy cặp tọa độ đầu tiên
                    }
                else:
                    # Nếu có từ 4 cặp tọa độ trở lên, tạo Polygon
                    geometry = {
                        "type": "Polygon",
                        "coordinates": [coordinates]  # Đưa vào dưới dạng list
                    }

                geojson = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {column: (row[column] if pd.notna(row[column]) else None) for column in columns}
                    }]
                }

                # Đảm bảo tên tệp hợp lệ
                valid_project_name = project_name.replace(" ", "_").replace(",", "").replace("-", "_")
                file_name = f"{valid_project_name}.geojson"
                file_path = os.path.join(path, file_name)  # Đặt đường dẫn tệp với thư mục đã nhập

                # Lưu mỗi tệp GeoJSON riêng biệt
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(geojson, f, ensure_ascii=False, indent=4)

        print(f"Tất cả tệp GeoJSON đã được xuất vào {path}.")
    else:
        print("Lựa chọn không hợp lệ. Vui lòng thử lại.")

# Gọi hàm export_geojson
export_geojson()
