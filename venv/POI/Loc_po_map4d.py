import json
import os
import re
from shapely.geometry import shape, Point

# ========== B1 + B2 ==========
json_dir = input("B1. Nhập đường dẫn thư mục chứa file JSON POI: ").strip()
json_file = input("B2. Nhập tên file JSON (vd: hospitals.json): ").strip()

json_path = os.path.join(json_dir, json_file)
if not os.path.isfile(json_path):
    raise FileNotFoundError(f"Không tìm thấy file: {json_path}")

# ========== B3 + B4 ==========
polygon_dir = input("B3. Nhập đường dẫn thư mục chứa file polygon (.geojson): ").strip()
polygon_file = input("B4. Nhập tên file polygon (vd: hai_chau.geojson): ").strip()

polygon_path = os.path.join(polygon_dir, polygon_file)
if not os.path.isfile(polygon_path):
    raise FileNotFoundError(f"Không tìm thấy file polygon: {polygon_path}")

# ========== B5 ==========
keywords_input = input(
    "B5. Nhập keyword lọc theo name (phân cách bằng dấu phẩy, bỏ trống = không lọc): "
).strip()

keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
regex = None
if keywords:
    pattern = "|".join(map(re.escape, keywords))
    regex = re.compile(pattern, re.IGNORECASE)

# ========== LOAD DATA ==========
with open(json_path, "r", encoding="utf-8") as f:
    pois = json.load(f)

with open(polygon_path, "r", encoding="utf-8") as f:
    polygon_geojson = json.load(f)

# polygon có thể là Feature / FeatureCollection / Geometry
if polygon_geojson.get("type") == "FeatureCollection":
    polygon = shape(polygon_geojson["features"][0]["geometry"])
elif polygon_geojson.get("type") == "Feature":
    polygon = shape(polygon_geojson["geometry"])
else:
    polygon = shape(polygon_geojson)

# ========== FILTER ==========
features = []

for poi in pois:
    geom = poi.get("geometry")
    if not geom or geom.get("type") != "Point":
        continue

    lng, lat = geom.get("coordinates", [None, None])
    if lng is None or lat is None:
        continue

    point = Point(lng, lat)

    # polygon filter
    if not polygon.contains(point):
        continue

    # keyword filter
    if regex:
        name = poi.get("name", "")
        if not isinstance(name, str) or not regex.search(name):
            continue

    # build GeoJSON Feature
    properties = poi.copy()
    properties.pop("geometry", None)  # geometry tách riêng

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat]
        },
        "properties": properties
    }

    features.append(feature)

# ========== OUTPUT GEOJSON ==========
output_file = f"filtered_{os.path.splitext(json_file)[0]}.geojson"
output_path = os.path.join(json_dir, output_file)

geojson_output = {
    "type": "FeatureCollection",
    "features": features
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(geojson_output, f, ensure_ascii=False, indent=2)

print("\n✅ HOÀN THÀNH")
print(f"👉 Số POI tìm được: {len(features)}")
print(f"👉 File GeoJSON: {output_path}")
