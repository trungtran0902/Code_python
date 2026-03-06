import os
import json
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.validation import explain_validity


def is_geometry_invalid(geometry):
    try:
        geom = shape(geometry)
        if not geom.is_valid:
            return True, explain_validity(geom)
        return False, ""
    except Exception as e:
        return True, f"Lỗi đọc geometry: {e}"


def fix_invalid_geometry(geometry):
    try:
        geom = shape(geometry)

        # Kiểm tra và sửa lỗi đối với Polygon
        if isinstance(geom, Polygon):
            if not geom.is_valid:
                geom = geom.make_valid()
                geometry = json.loads(geom.to_geojson())

        # Kiểm tra và sửa lỗi đối với MultiPolygon
        elif isinstance(geom, MultiPolygon):
            fixed_polygons = []
            for polygon in geom.geoms:  # Geometries của MultiPolygon là danh sách các Polygon
                if not polygon.is_valid:
                    fixed_polygon = polygon.make_valid()
                    fixed_polygons.append(fixed_polygon)
                else:
                    fixed_polygons.append(polygon)
            geom = MultiPolygon(fixed_polygons)  # Tạo lại MultiPolygon sau khi sửa
            geometry = json.loads(geom.to_geojson())

        return geometry
    except Exception as e:
        print(f"Không thể sửa geometry: {e}")
        return geometry


def find_duplicate_segments(coords):
    seen = set()
    duplicates = []

    def check_ring(ring):
        for i in range(len(ring) - 1):
            segment = (tuple(ring[i]), tuple(ring[i + 1]))
            if segment in seen:
                duplicates.append(segment)
            else:
                seen.add(segment)

    if isinstance(coords[0][0][0], (float, int)):
        for ring in coords:
            check_ring(ring)
    else:
        for polygon in coords:
            for ring in polygon:
                check_ring(ring)

    return duplicates


def remove_duplicate_segments(coords):
    seen = set()
    new_coords = []

    def add_ring(ring):
        new_ring = []
        for i in range(len(ring) - 1):
            segment = (tuple(ring[i]), tuple(ring[i + 1]))
            if segment not in seen:
                seen.add(segment)
                new_ring.append(ring[i])
        new_ring.append(ring[-1])  # thêm điểm cuối của ring
        new_coords.append(new_ring)

    if isinstance(coords[0][0][0], (float, int)):
        add_ring(coords)
    else:
        for polygon in coords:
            for ring in polygon:
                add_ring(ring)

    return new_coords


def check_ring_closed(coords):
    """
    Trả về danh sách các vòng chưa khép kín và tọa độ điểm đầu/cuối
    """
    not_closed = []

    def is_ring_closed(ring):
        return ring[0] == ring[-1]

    if isinstance(coords[0][0][0], (float, int)):
        for ring_index, ring in enumerate(coords):
            if not is_ring_closed(ring):
                not_closed.append({
                    "polygon_index": 0,
                    "ring_index": ring_index,
                    "start": ring[0],
                    "end": ring[-1]
                })
    else:
        for poly_index, polygon in enumerate(coords):
            for ring_index, ring in enumerate(polygon):
                if not is_ring_closed(ring):
                    not_closed.append({
                        "polygon_index": poly_index,
                        "ring_index": ring_index,
                        "start": ring[0],
                        "end": ring[-1]
                    })

    return not_closed


def close_ring(coords):
    """
    Khép kín các vòng tròn chưa hoàn chỉnh bằng cách thêm điểm cuối vào đầu
    """
    if isinstance(coords[0][0][0], (float, int)):
        if coords[0][0] != coords[0][-1]:
            coords[0].append(coords[0][0])  # Khép kín vòng
    else:
        for polygon in coords:
            for ring in polygon:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])  # Khép kín vòng

    return coords


def check_geojson_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'features' in data:
            for idx, feature in enumerate(data['features']):
                geometry = feature.get('geometry')
                if geometry:
                    invalid, reason = is_geometry_invalid(geometry)
                    if invalid:
                        print(f'[INVALID] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        print(f'  -> Geometry type: {geometry.get("type")}')
                        print(f'  -> Lý do: {reason}')
                        print('---')

                    # Sửa hình học không hợp lệ
                    feature['geometry'] = fix_invalid_geometry(geometry)

                    coords = geometry.get("coordinates")

                    # Kiểm tra và loại bỏ đoạn trùng
                    duplicates = find_duplicate_segments(coords)
                    if duplicates:
                        print(f'[DUPLICATE SEGMENTS] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        print(f'  -> Geometry type: {geometry.get("type")}')
                        print(f'  -> Số đoạn trùng: {len(duplicates)}')
                        print(f'  -> Một số đoạn trùng: {duplicates[:5]}{"..." if len(duplicates) > 5 else ""}')
                        print('---')

                    # Loại bỏ đoạn trùng
                    feature['geometry']['coordinates'] = remove_duplicate_segments(coords)

                    # Kiểm tra vòng chưa khép kín và sửa
                    not_closed_rings = check_ring_closed(coords)
                    if not_closed_rings:
                        print(f'[UNCLOSED RINGS] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        for item in not_closed_rings:
                            print(f'     - Polygon {item["polygon_index"]} Ring {item["ring_index"]}:')
                            print(f'         + Start: {item["start"]}')
                            print(f'         + End  : {item["end"]}')
                        print('---')

                    # Khép kín các vòng chưa khép kín
                    feature['geometry']['coordinates'] = close_ring(coords)

        # Lưu lại file sửa lỗi (tùy chọn)
        with open(f"fixed_{os.path.basename(file_path)}", 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Đã lưu file đã sửa tại: fixed_{os.path.basename(file_path)}")

    except Exception as e:
        print(f'[ERROR] Không đọc được {file_path}: {e}')


def scan_directory(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.geojson'):
                file_path = os.path.join(root, file)
                check_geojson_file(file_path)


if __name__ == '__main__':
    folder = input("Nhập đường dẫn thư mục cần quét: ").strip()
    if os.path.isdir(folder):
        scan_directory(folder)
    else:
        print("Thư mục không tồn tại.")
