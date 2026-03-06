import geopandas as gpd
import os
from shapely.geometry import box
import pyproj
import numpy as np


# Hàm chuyển đổi từ độ sang khoảng cách vật lý (mét)
def get_distance_in_meters(lon1, lat1, lon2, lat2):
    # Sử dụng pyproj để tính toán khoảng cách giữa hai điểm
    wgs84 = pyproj.CRS("EPSG:4326")  # Hệ tọa độ WGS84 (Độ)
    utm = pyproj.CRS("EPSG:32648")  # Hệ tọa độ UTM zone 48N (Dùng cho Việt Nam)

    transformer = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True)
    x1, y1 = transformer.transform(lon1, lat1)
    x2, y2 = transformer.transform(lon2, lat2)

    # Tính khoảng cách giữa hai điểm (mét)
    distance = pyproj.Geod(ellps="WGS84").inv(x1, y1, x2, y2)[2]
    print(f"Distance from ({lon1}, {lat1}) to ({lon2}, {lat2}): {distance} meters")
    return distance


# Hàm kiểm tra xem các giá trị có hợp lệ không (không phải NaN)
def check_valid_bbox(bbox):
    return all([not np.isnan(val) for val in bbox])


# Hàm chia bounding box thành các box vuông 252m x 252m
def split_bbox(bbox, width_meters):
    minx, miny, maxx, maxy = bbox

    # Kiểm tra xem bounding box có hợp lệ không
    if not check_valid_bbox(bbox):
        raise ValueError("Bounding box có chứa giá trị NaN, không thể tiếp tục xử lý.")

    print(f"Bounding Box: minx={minx}, miny={miny}, maxx={maxx}, maxy={maxy}")  # In ra để kiểm tra

    # Tính toán số lượng box theo chiều kinh độ (width) và vĩ độ (height)
    distance_x = get_distance_in_meters(minx, miny, maxx, miny)  # Khoảng cách theo kinh độ
    distance_y = get_distance_in_meters(minx, miny, minx, maxy)  # Khoảng cách theo vĩ độ

    print(f"Distance in X direction (longitude): {distance_x} meters")
    print(f"Distance in Y direction (latitude): {distance_y} meters")

    num_boxes_x = int(distance_x // width_meters) + 1
    num_boxes_y = int(distance_y // width_meters) + 1

    print(f"Number of boxes in X: {num_boxes_x}")
    print(f"Number of boxes in Y: {num_boxes_y}")

    # Tạo các box vuông nhỏ
    boxes = []
    for i in range(num_boxes_x):
        for j in range(num_boxes_y):
            x1 = minx + i * (distance_x / num_boxes_x)
            y1 = miny + j * (distance_y / num_boxes_y)
            x2 = x1 + (distance_x / num_boxes_x)
            y2 = y1 + (distance_y / num_boxes_y)
            boxes.append(box(x1, y1, x2, y2))

    return boxes


# Hàm chính xử lý GeoJSON và chia thành các box nhỏ
def process_geojson(input_file, output_dir, width_meters=252):
    # Đọc file GeoJSON
    gdf = gpd.read_file(input_file)

    # Lấy bounding box tổng thể của dữ liệu
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]

    # Kiểm tra giá trị bounding box
    if np.any(np.isnan(bounds)):
        print(f"Bounding box có giá trị NaN: {bounds}")
        print("Dữ liệu không hợp lệ, không thể tiếp tục.")
        return

    print(f"Bounding Box ban đầu: {bounds}")  # In ra bounding box để kiểm tra

    # Chia bounding box tổng thể thành các box vuông nhỏ 252m x 252m
    small_boxes = split_bbox(bounds, width_meters)

    # Tạo các file GeoJSON nhỏ cho mỗi box
    for i, small_box in enumerate(small_boxes):
        # Tạo GeoDataFrame cho box nhỏ
        gdf_small = gdf[gdf.intersects(small_box)]

        if not gdf_small.empty:
            # Định nghĩa tên file output
            output_file = f"box_{i + 1}.geojson"
            output_path = os.path.join(output_dir, output_file)

            # Xuất GeoDataFrame vào file GeoJSON
            gdf_small.to_file(output_path, driver='GeoJSON')
            print(f"File {output_file} đã được tạo thành công.")
        else:
            print(f"Box {i + 1} không có dữ liệu.")


# Hàm để yêu cầu đường dẫn và tên file từ người dùng
def main():
    # Nhập đường dẫn chứa file
    input_dir = input("Nhập đường dẫn chứa file GeoJSON: ")

    # Nhập tên file GeoJSON
    input_file_name = input("Nhập tên file GeoJSON cần xử lý: ")
    input_file = os.path.join(input_dir, input_file_name)

    # Kiểm tra xem file có tồn tại không
    if not os.path.isfile(input_file):
        print("File không tồn tại!")
        return

    # Nhập tên thư mục xuất file GeoJSON (sẽ được tạo trong thư mục chứa file gốc)
    output_folder_name = input("Nhập tên thư mục xuất file GeoJSON (sẽ tạo thư mục này trong thư mục chứa file gốc): ")

    # Định nghĩa đường dẫn thư mục xuất
    output_dir = os.path.join(input_dir, output_folder_name)

    # Kiểm tra nếu thư mục đầu ra không tồn tại thì tạo mới
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Tạo thư mục mới: {output_dir}")

    # Gọi hàm xử lý
    process_geojson(input_file, output_dir)


if __name__ == "__main__":
    main()
