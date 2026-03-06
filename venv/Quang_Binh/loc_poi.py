import geopandas as gpd
import os


def process_geojson(file_path, output_dir):
    # Đọc file GeoJSON vào GeoDataFrame
    gdf = gpd.read_file(file_path)

    # Kiểm tra dữ liệu đầu vào (tuỳ chọn)
    print(f"Đọc dữ liệu từ file: {file_path}")
    print(gdf.head())

    # Lấy danh sách các nhóm trong cột 'name'
    groups = gdf['Name'].unique()

    # Nếu thư mục output không tồn tại, tạo mới
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Phân loại và lưu từng nhóm vào các file GeoJSON và Shapefile
    for group in groups:
        # Lọc các điểm thuộc nhóm hiện tại
        group_gdf = gdf[gdf['Name'] == group]

        # Lưu nhóm vào file GeoJSON
        geojson_output_file = os.path.join(output_dir, f"{group}.geojson")
        group_gdf.to_file(geojson_output_file, driver='GeoJSON')
        print(f"Đã lưu nhóm '{group}' vào file GeoJSON: {geojson_output_file}")

        # Lưu nhóm vào file Shapefile
        shapefile_output_file = os.path.join(output_dir, f"{group}.shp")
        group_gdf.to_file(shapefile_output_file, driver='ESRI Shapefile')
        print(f"Đã lưu nhóm '{group}' vào file Shapefile: {shapefile_output_file}")

    print("Hoàn thành việc phân loại và lưu các file GeoJSON và Shapefile.")


# Nhập đường dẫn file GeoJSON từ người dùng
file_path = input("Nhập đường dẫn đến file GeoJSON (ví dụ: C:/Users/YourName/Documents/file.geojson): ")

# Nhập đường dẫn thư mục đầu ra từ người dùng
output_dir = input("Nhập đường dẫn thư mục để lưu các file phân loại (ví dụ: C:/Users/YourName/Documents/output): ")

# Gọi hàm xử lý với các tham số đã nhập
process_geojson(file_path, output_dir)
