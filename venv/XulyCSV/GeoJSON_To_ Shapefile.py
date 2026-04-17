import geopandas as gpd
import os

# Nhập đường dẫn thư mục chứa file GeoJSON
folder_path = input("Nhập đường dẫn thư mục chứa file GeoJSON: ").strip()
file_name = input("Nhập tên file GeoJSON (vd: poi_an_giang.geojson): ").strip()

input_file = os.path.join(folder_path, file_name)

# Tạo tên folder theo tên file (bỏ đuôi .geojson)
folder_name = file_name.replace(".geojson", "")
output_folder = os.path.join(folder_path, folder_name)
os.makedirs(output_folder, exist_ok=True)

# Tên shapefile xuất ra (trong thư mục)
output_file = os.path.join(output_folder, folder_name + ".shp")

# Đọc GeoJSON
gdf = gpd.read_file(input_file)

# Nếu không cần metadata (tránh lỗi cắt chuỗi)
if "metadata" in gdf.columns:
    gdf = gdf.drop(columns=["metadata"])

# Xuất shapefile
gdf.to_file(output_file, driver="ESRI Shapefile", encoding="utf-8")

print(f"✅ Đã tạo thư mục {output_folder} chứa Shapefile")
