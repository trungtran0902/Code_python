import zipfile
import os
import tempfile
import geopandas as gpd

def kmz_to_shapefile(folder_path, kmz_filename, output_name):
    # Ghép đường dẫn đầy đủ tới file KMZ
    kmz_path = os.path.join(folder_path, kmz_filename)

    if not os.path.exists(kmz_path):
        raise FileNotFoundError(f"Không tìm thấy file: {kmz_path}")

    # 1. Giải nén KMZ (thực chất là ZIP)
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(kmz_path, 'r') as zf:
        zf.extractall(temp_dir)

    # 2. Tìm file KML trong thư mục giải nén
    kml_file = None
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if file.endswith(".kml"):
                kml_file = os.path.join(root, file)
                break

    if not kml_file:
        raise FileNotFoundError("Không tìm thấy file KML trong KMZ.")

    # 3. Đọc KML bằng geopandas
    gdf = gpd.read_file(kml_file, driver='KML')

    # 4. Xuất ra shapefile (lưu cùng thư mục KMZ)
    output_shapefile = os.path.join(folder_path, f"{output_name}.shp")
    gdf.to_file(output_shapefile, driver='ESRI Shapefile')

    print(f"✅ Đã convert {kmz_filename} → {output_shapefile}")

if __name__ == "__main__":
    folder = input("Nhập đường dẫn thư mục chứa file KMZ: ").strip()
    kmz_file = input("Nhập tên file KMZ (kèm .kmz): ").strip()
    output_name = input("Nhập tên shapefile đầu ra (không cần .shp): ").strip()

    kmz_to_shapefile(folder, kmz_file, output_name)
