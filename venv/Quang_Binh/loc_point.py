import os
import geopandas as gpd

def filter_poi_by_name(folder_path, file_name, keywords, output_path):
    # Ghép đường dẫn
    input_path = os.path.join(folder_path, file_name)

    print("📁 Đang mở file:", input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"❌ Không tìm thấy file: {input_path}")

    # Đọc file
    gdf = gpd.read_file(input_path)

    # Chuyển name về chữ thường
    gdf["name_lower"] = gdf["name"].astype(str).str.lower()

    # Chuẩn hóa keyword
    keywords = [kw.strip().lower() for kw in keywords]
    pattern = "|".join(keywords)

    # Lọc
    filtered = gdf[gdf["name_lower"].str.contains(pattern, na=False)]

    # Xóa cột tạm
    filtered = filtered.drop(columns=["name_lower"])

    # Xuất file
    filtered.to_file(output_path, driver="GeoJSON")

    print(f"✅ Xong! Số POI phù hợp: {len(filtered)}")


if __name__ == "__main__":
    print("=== LỌC POI THEO TÊN ===")

    folder_path = input("Nhập đường dẫn thư mục chứa POI: ").strip()
    file_name = input("Nhập tên file POI (vd: poi.geojson): ").strip()
    keyword_str = input("Nhập keyword (vd: thôn, xóm): ").strip()
    output_path = input("Nhập đường dẫn file output: ").strip()

    keywords = keyword_str.split(",")

    filter_poi_by_name(folder_path, file_name, keywords, output_path)
