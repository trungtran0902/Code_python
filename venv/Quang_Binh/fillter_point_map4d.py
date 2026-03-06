import os
import geopandas as gpd

def filter_points_in_polygon(point_folder, point_file, poly_folder, poly_file, output_file):
    # Tạo đường dẫn đầy đủ
    points_path = os.path.join(point_folder, point_file)
    polygon_path = os.path.join(poly_folder, poly_file)

    print("📌 Đang đọc dữ liệu điểm:", points_path)
    gdf_points = gpd.read_file(points_path)

    print("📌 Đang đọc dữ liệu polygon:", polygon_path)
    gdf_poly = gpd.read_file(polygon_path)

    # Đồng bộ CRS
    if gdf_points.crs != gdf_poly.crs:
        gdf_points = gdf_points.to_crs(gdf_poly.crs)

    print("🔍 Đang lọc các điểm nằm trong polygon...")

    # Lọc các điểm nằm trong polygon
    filtered = gpd.sjoin(gdf_points, gdf_poly, how="inner", predicate="within")

    # Xuất file
    filtered.to_file(output_file, driver="GeoJSON")
    print(f"✅ Hoàn tất! Tổng số điểm nằm trong polygon: {len(filtered)}")
    print(f"📁 File kết quả: {output_file}")


if __name__ == "__main__":
    print("=== LỌC POINT NẰM TRONG POLYGON ===")

    # B1
    point_folder = input("Nhập đường dẫn thư mục chứa file POINT: ").strip()
    point_file = input("Nhập tên file POINT (.geojson): ").strip()

    # B2
    poly_folder = input("Nhập đường dẫn thư mục chứa file POLYGON: ").strip()
    poly_file = input("Nhập tên file POLYGON (.geojson): ").strip()

    # File xuất
    output_file = input("Nhập đường dẫn + tên file OUTPUT (.geojson): ").strip()

    filter_points_in_polygon(point_folder, point_file, poly_folder, poly_file, output_file)
