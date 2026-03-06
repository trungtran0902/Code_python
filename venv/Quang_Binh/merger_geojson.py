import os
import geojson
import geopandas as gpd
from shapely.geometry import MultiPolygon, shape

# Bước 1: Nhập đường dẫn thư mục chứa các file geojson cần gộp
folder_path = input("Nhập đường dẫn chứa các file GeoJSON cần gộp: ")

# Bước 2: Nhập đường dẫn thư mục đầu ra
output_path = input("Nhập đường dẫn thư mục đầu ra: ")

# Bước 3: Tìm tất cả các file geojson trong thư mục
geojson_files = [f for f in os.listdir(folder_path) if f.endswith('.geojson')]

# Khởi tạo danh sách chứa tất cả các features
all_features = []

# Đọc và gộp các file GeoJSON lại
for file in geojson_files:
    file_path = os.path.join(folder_path, file)
    with open(file_path, 'r', encoding='utf-8') as f:  # Đảm bảo sử dụng mã hóa UTF-8
        data = geojson.load(f)
        all_features.extend(data['features'])

# Tạo một GeoDataFrame từ danh sách features
gdf = gpd.GeoDataFrame.from_features(all_features)

# Giữ nguyên tất cả các đối tượng Polygon hoặc MultiPolygon
# Nếu đối tượng là Polygon, chuyển nó thành một MultiPolygon chứa nó
gdf['geometry'] = gdf['geometry'].apply(lambda geom: MultiPolygon([geom]) if geom.geom_type == 'Polygon' else geom)

# Tạo một MultiPolygon chứa tất cả các vùng (giữ nguyên các vùng nhỏ)
merged_gdf = MultiPolygon([geom for geom in gdf.geometry])

# Tạo GeoJSON từ các đối tượng đã gộp
merged_geojson = geojson.FeatureCollection([geojson.Feature(geometry=shape(merged_gdf))])

# Lưu file GeoJSON ra file đầu ra
output_geojson_path = os.path.join(output_path, "merged_output.geojson")
with open(output_geojson_path, 'w', encoding='utf-8') as f:  # Thêm encoding='utf-8'
    geojson.dump(merged_geojson, f)

# Lưu file shapefile
output_shapefile_path = os.path.join(output_path, "merged_output.shp")
gdf_merged = gpd.GeoDataFrame(geometry=[merged_gdf], crs="EPSG:4326")
gdf_merged.to_file(output_shapefile_path)

print(f"Đã gộp các file và lưu tại {output_geojson_path} và {output_shapefile_path}")
