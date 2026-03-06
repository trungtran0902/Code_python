import os
import json
from shapely.geometry import shape
from shapely.validation import explain_validity


def is_geometry_invalid(geometry):
    try:
        geom = shape(geometry)
        if not geom.is_valid:
            return True, explain_validity(geom)
        return False, ""
    except Exception as e:
        return True, f"Lỗi đọc geometry: {e}"


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

                    coords = geometry.get("coordinates")

                    # Kiểm tra đoạn trùng
                    duplicates = find_duplicate_segments(coords)
                    if duplicates:
                        print(f'[DUPLICATE SEGMENTS] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        print(f'  -> Geometry type: {geometry.get("type")}')
                        print(f'  -> Số đoạn trùng: {len(duplicates)}')
                        print(f'  -> Một số đoạn trùng: {duplicates[:5]}{"..." if len(duplicates) > 5 else ""}')
                        print('---')

                    # Kiểm tra vòng chưa khép kín
                    not_closed_rings = check_ring_closed(coords)
                    if not_closed_rings:
                        print(f'[UNCLOSED RINGS] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        for item in not_closed_rings:
                            print(f'     - Polygon {item["polygon_index"]} Ring {item["ring_index"]}:')
                            print(f'         + Start: {item["start"]}')
                            print(f'         + End  : {item["end"]}')
                        print('---')

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
