import json
import os
from shapely.geometry import shape, Point


def load_geojson(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_geojson(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def filter_points_in_polygons(points_geojson, polygons_geojson):
    polygons = []

    # Lấy tất cả polygon trong file polygon
    for feature in polygons_geojson["features"]:
        geom = shape(feature["geometry"])
        polygons.append(geom)

    filtered_points = []

    # Lọc point
    for feature in points_geojson["features"]:
        geom = shape(feature["geometry"])  # Point

        for poly in polygons:
            if poly.contains(geom) or poly.touches(geom):
                filtered_points.append(feature)
                break

    return {
        "type": "FeatureCollection",
        "features": filtered_points
    }


def main():
    print("=== LỌC POINT NẰM TRONG POLYGON - GEOJSON TOOL ===\n")

    # B1 – Nhập đường dẫn file Point
    point_path = input("B1: Nhập đường dẫn đến file POINT GeoJSON: ").strip()

    # B2 – Nhập tên file POINT
    point_file = input("B2: Nhập tên file POINT (vd: point.geojson): ").strip()
    point_fullpath = os.path.join(point_path, point_file)

    # B3 – Nhập đường dẫn file Polygon
    poly_path = input("B3: Nhập đường dẫn đến file POLYGON GeoJSON: ").strip()

    # B4 – Nhập tên file POLYGON
    poly_file = input("B4: Nhập tên file POLYGON (vd: polygon.geojson): ").strip()
    poly_fullpath = os.path.join(poly_path, poly_file)

    # B5 – Thư mục xuất file
    out_dir = input("B5: Nhập thư mục xuất dữ liệu: ").strip()

    # Kiểm tra thư mục output
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    print("\nĐang tải dữ liệu...")

    points_geojson = load_geojson(point_fullpath)
    polygons_geojson = load_geojson(poly_fullpath)

    print("Đang xử lý lọc point nằm trong polygon...")

    filtered_geojson = filter_points_in_polygons(points_geojson, polygons_geojson)

    # B7 – Xuất file
    output_path = os.path.join(out_dir, "points_in_polygon.geojson")
    save_geojson(filtered_geojson, output_path)

    print("\n🎉 Hoàn thành!")
    print(f"👉 File kết quả: {output_path}")
    print(f"👉 Số lượng point sau khi lọc: {len(filtered_geojson['features'])}")


if __name__ == "__main__":
    main()
