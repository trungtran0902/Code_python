import os
import json
import re
from shapely.geometry import shape, GeometryCollection
from shapely.errors import ShapelyError
from shapely.validation import explain_validity

def extract_coords_from_reason(reason):
    """Cố gắng lấy toạ độ từ chuỗi lỗi."""
    match = re.search(r'at or near point \(([-\d.]+) ([-\d.]+)\)', reason)
    if match:
        lon, lat = match.groups()
        return float(lon), float(lat)
    return None

def flatten_geometries(geom):
    """Tách nhỏ Multi* thành các hình học riêng biệt để kiểm tra từng cái."""
    if geom.geom_type == 'GeometryCollection':
        return [g for g in geom.geoms]
    elif geom.geom_type.startswith("Multi"):
        return list(geom.geoms)
    else:
        return [geom]

def is_geometry_invalid(geometry):
    try:
        geom = shape(geometry)
        invalid_geoms = []
        for g in flatten_geometries(geom):
            if not g.is_valid:
                reason = explain_validity(g)
                coord = extract_coords_from_reason(reason)
                invalid_geoms.append({
                    'geom_type': g.geom_type,
                    'reason': reason,
                    'coords': coord,
                    'raw_coords': list(g.exterior.coords) if hasattr(g, "exterior") else None
                })
        return invalid_geoms
    except Exception as e:
        return [{
            'geom_type': 'Unknown',
            'reason': f"Lỗi đọc geometry: {e}",
            'coords': None,
            'raw_coords': None
        }]

def check_geojson_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'features' in data:
            for idx, feature in enumerate(data['features']):
                geometry = feature.get('geometry')
                if geometry:
                    invalid_list = is_geometry_invalid(geometry)
                    for issue in invalid_list:
                        print(f'[INVALID] File: {file_path}')
                        print(f'  -> Feature index: {idx}')
                        print(f'  -> Geometry type: {issue["geom_type"]}')
                        if issue["coords"]:
                            print(f'  -> Tọa độ lỗi: {issue["coords"]}')
                        if issue["raw_coords"]:
                            print(f'  -> Hình học (cắt ngắn): {str(issue["raw_coords"])[:300]}...')
                        print(f'  -> Lý do: {issue["reason"]}')
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
