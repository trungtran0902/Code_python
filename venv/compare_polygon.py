import os
import geopandas as gpd
from shapely.geometry import Polygon


# Hàm xử lý và lưu kết quả
def process_polygons(input_file1, input_file2, output_file_intersection, output_file_difference):
    # Kiểm tra và tạo thư mục nếu không tồn tại
    output_dir_intersection = os.path.dirname(output_file_intersection)
    output_dir_difference = os.path.dirname(output_file_difference)

    if not os.path.exists(output_dir_intersection):
        os.makedirs(output_dir_intersection)
    if not os.path.exists(output_dir_difference):
        os.makedirs(output_dir_difference)

    # Đọc dữ liệu từ các file input
    gdf1 = gpd.read_file(input_file1)
    gdf2 = gpd.read_file(input_file2)

    # Kiểm tra và đồng bộ CRS
    if gdf1.crs != gdf2.crs:
        print("CRS không đồng nhất, chuyển đổi CRS của file 2 sang CRS của file 1.")
        gdf2 = gdf2.to_crs(gdf1.crs)

    # Giả sử mỗi file chứa một Polygon duy nhất, nếu không thì sẽ phải xử lý từng đối tượng
    polygon1 = gdf1.geometry.iloc[0]
    polygon2 = gdf2.geometry.iloc[0]

    # Kiểm tra tính hợp lệ của các polygon
    if not polygon1.is_valid:
        print("Polygon 1 không hợp lệ. Đang sửa chữa...")
        polygon1 = polygon1.buffer(0)  # Sửa chữa polygon không hợp lệ

    if not polygon2.is_valid:
        print("Polygon 2 không hợp lệ. Đang sửa chữa...")
        polygon2 = polygon2.buffer(0)  # Sửa chữa polygon không hợp lệ

    # Tính phần giao nhau
    intersection = polygon1.intersection(polygon2)

    # Tính phần còn lại sau khi cắt
    difference = polygon1.difference(polygon2)

    # Tạo GeoDataFrame cho phần giao nhau
    intersection_gdf = gpd.GeoDataFrame(geometry=[intersection], crs=gdf1.crs)

    # Tạo GeoDataFrame cho phần còn lại
    difference_gdf = gpd.GeoDataFrame(geometry=[difference], crs=gdf1.crs)

    # Lưu phần giao nhau vào file GeoJSON
    intersection_gdf.to_file(output_file_intersection, driver='GeoJSON')

    # Lưu phần còn lại vào file GeoJSON
    difference_gdf.to_file(output_file_difference, driver='GeoJSON')

    print(f"Phần giao nhau đã lưu tại: {output_file_intersection}")
    print(f"Phần còn lại sau khi cắt đã lưu tại: {output_file_difference}")


# Nhập thông tin từ người dùng
input_file1 = input("Nhập đường dẫn và tên file GeoJSON 1: ")  # Ví dụ: "path/to/polygon1.geojson"
input_file2 = input("Nhập đường dẫn và tên file GeoJSON 2: ")  # Ví dụ: "path/to/polygon2.geojson"
output_file_intersection = input(
    "Nhập đường dẫn và tên file GeoJSON lưu phần giao nhau: ")  # Ví dụ: "path/to/intersection.geojson"
output_file_difference = input(
    "Nhập đường dẫn và tên file GeoJSON lưu phần còn lại sau khi cắt: ")  # Ví dụ: "path/to/difference.geojson"

# Gọi hàm xử lý
process_polygons(input_file1, input_file2, output_file_intersection, output_file_difference)
