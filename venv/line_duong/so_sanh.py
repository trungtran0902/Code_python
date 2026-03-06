import geopandas as gpd
from shapely.geometry import LineString
import os

def compare_road_files_fuzzy(file1, file2, output_path, buffer_m=3):
    print("🚀 Đang đọc dữ liệu...")
    gdf1 = gpd.read_file(file1)
    gdf2 = gpd.read_file(file2)

    # Đưa về cùng hệ tọa độ (4326)
    gdf1 = gdf1.to_crs(epsg=4326)
    gdf2 = gdf2.to_crs(epsg=4326)

    # Loại bỏ đối tượng rỗng hoặc sai kiểu
    gdf1 = gdf1[gdf1.geometry.notnull()]
    gdf2 = gdf2[gdf2.geometry.notnull()]
    gdf1 = gdf1[gdf1.geometry.type.isin(["LineString", "MultiLineString"])]
    gdf2 = gdf2[gdf2.geometry.type.isin(["LineString", "MultiLineString"])]

    # Chuyển sang hệ mét để tính buffer
    gdf1 = gdf1.to_crs(epsg=3857)
    gdf2 = gdf2.to_crs(epsg=3857)

    print(f"⚙️ Đang tạo vùng đệm {buffer_m} mét quanh đường trong file2...")
    gdf2_buffer = gdf2.copy()
    gdf2_buffer["geometry"] = gdf2_buffer.buffer(buffer_m)

    # Hợp vùng đệm lại thành 1 vùng lớn
    gdf2_union = gdf2_buffer.unary_union

    # Lấy các đường trong file1 KHÔNG giao với vùng đệm file2
    diff = gdf1[~gdf1.geometry.intersects(gdf2_union)]

    print(f"✅ Số đoạn đường chỉ có trong file1 (khác biệt > {buffer_m}m): {len(diff)}")

    # Xuất kết quả
    diff = diff.to_crs(epsg=4326)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    diff.to_file(output_path, driver="GeoJSON", encoding="utf-8")

    print(f"💾 Đã xuất file GeoJSON: {output_path}")


if __name__ == "__main__":
    print("=== SO SÁNH DỮ LIỆU ĐƯỜNG GIỮA HAI FILE GEOJSON (GẦN ĐÚNG) ===")
    file1 = input("📄 Nhập đường dẫn file 1 (VD: D:\\data\\xaA_file1.geojson): ").strip()
    file2 = input("📄 Nhập đường dẫn file 2 (VD: D:\\data\\xaA_file2.geojson): ").strip()
    output = input("💾 Nhập đường dẫn file kết quả (VD: D:\\data\\khac_biet.geojson): ").strip()

    # Bạn có thể đổi buffer_m = 1, 3, 5 tùy độ sai lệch chấp nhận được
    compare_road_files_fuzzy(file1, file2, output, buffer_m=3)
