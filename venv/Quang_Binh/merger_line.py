import geopandas as gpd
from shapely.geometry import MultiLineString
import os

# Bước 1: Nhập đường dẫn chứa file
input_directory = input("Nhập đường dẫn chứa file GeoJSON: ")

# Bước 2: Nhập tên file
input_filename = input("Nhập tên file GeoJSON: ")

# Bước 3: Nhập đường dẫn đầu ra
output_directory = input("Nhập đường dẫn đầu ra: ")

# Kết hợp đường dẫn đầy đủ
input_file_path = os.path.join(input_directory, input_filename)

# Kiểm tra xem file có tồn tại không
if not os.path.exists(input_file_path):
    print(f"File không tồn tại: {input_file_path}")
else:
    # Đọc file GeoJSON
    gdf = gpd.read_file(input_file_path)

    # Kiểm tra loại geometry trong GeoDataFrame
    print("Kiểm tra loại geometry trong GeoDataFrame:")
    print(gdf.geometry.type)

    # Sử dụng unary_union để hợp nhất tất cả các line trong GeoDataFrame thành một MultiLineString
    merged = gdf.geometry.unary_union

    # Kiểm tra xem kết quả có phải là một MultiLineString hay không
    print(f"Kiểu đối tượng hợp nhất: {type(merged)}")

    # Nếu merged là MultiLineString, chuyển nó thành LineString duy nhất
    if isinstance(merged, MultiLineString):
        merged = merged.geoms[0]  # Chọn một geometry duy nhất từ MultiLineString

    # Tạo GeoDataFrame mới chứa line đã hợp nhất
    merged_gdf = gpd.GeoDataFrame(geometry=[merged], crs=gdf.crs)

    # Lưu kết quả vào file mới
    output_file_path = os.path.join(output_directory, "merged_line.geojson")
    merged_gdf.to_file(output_file_path, driver='GeoJSON')

    print(f"Đã hợp nhất line và lưu vào {output_file_path}")
