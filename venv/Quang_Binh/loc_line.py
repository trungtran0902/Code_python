import os
import re
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString

def filter_line_by_name(folder_path, file_name, keywords, output_path):
    # Ghép đường dẫn file
    input_path = os.path.join(folder_path, file_name)

    print("📁 Đang mở file:", input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"❌ Không tìm thấy file: {input_path}")

    # Đọc dữ liệu GIS
    gdf = gpd.read_file(input_path)

    # Kiểm tra trường name
    if "name" not in gdf.columns:
        raise KeyError("❌ Không tìm thấy trường 'name' trong dữ liệu!")

    # Giữ lại LINE
    line_gdf = gdf[
        gdf.geometry.apply(lambda geom: isinstance(geom, (LineString, MultiLineString)))
    ]

    print(f"📏 Tổng số đối tượng LINE: {len(line_gdf)}")

    # Chuẩn hóa name thành chữ thường
    line_gdf["name_lower"] = line_gdf["name"].astype(str).str.lower()

    # Chuẩn hóa keyword
    keywords = [re.escape(kw.strip().lower()) for kw in keywords if kw.strip()]
    pattern = "|".join(keywords)

    # Lọc theo keyword trong name
    filtered = line_gdf[
        line_gdf["name_lower"].str.contains(pattern, na=False, regex=True)
    ]

    # Xóa cột tạm
    filtered = filtered.drop(columns=["name_lower"])

    # Xuất file GeoJSON
    filtered.to_file(output_path, driver="GeoJSON")

    print(f"✅ Lọc xong! Số LINE phù hợp: {len(filtered)}")
    print(f"📤 Đã xuất file tại: {output_path}")


# ---------------------------
# 🔧 Chạy trực tiếp
# ---------------------------
if __name__ == "__main__":
    print("=== LỌC LINE THEO KEYWORD TRONG TRƯỜNG NAME ===")

    folder_path = input("📂 Nhập đường dẫn thư mục chứa file: ").strip()
    file_name = input("📄 Nhập tên file (vd: roads.geojson): ").strip()
    keyword_str = input("🔎 Nhập keyword (vd: quốc lộ, tỉnh lộ, đường): ").strip()
    output_path = input("📤 Nhập đường dẫn file output (vd: output.geojson): ").strip()

    # Tách keyword theo dấu phẩy
    keywords = keyword_str.split(",")

    filter_line_by_name(folder_path, file_name, keywords, output_path)
