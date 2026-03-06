import json

# ===== B1: Nhập file đầu vào =====
input_file = input("Nhập đường dẫn file đầu vào bao gồm tên file dạng *.geojson: ").strip()

# ===== B2: Nhập file đầu ra =====
output_file = input("Nhập đường dẫn file đầu ra bao gồm tên file dạng *.geojson: ").strip()

# ===== B3: Chọn loại highway =====
highway_options = [
    "motorway",
    "primary",
    "tertiary",
    "residential",
    "trunk",
    "secondary"
]

print("Chọn loại đường (highway):")
for i, h in enumerate(highway_options, start=1):
    print(f"{i}. {h}")

choice = int(input("Nhập số tương ứng: ").strip())
highway_value = highway_options[choice - 1]

# ===== Đọc file =====
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data.get("features", [])

new_features = []
line_id = 1

for feat in features:
    geom = feat.get("geometry")
    props = feat.get("properties", {})

    if not geom:
        continue

    # Chuyển MultiLineString -> LineString
    if geom.get("type") == "MultiLineString":
        coords = geom.get("coordinates", [])
        new_coords = []
        for part in coords:
            if isinstance(part, list):
                new_coords.extend(part)
        geom = {
            "type": "LineString",
            "coordinates": new_coords
        }

    new_props = {
        "way_id": props.get("way_id", ""),
        "highway": highway_value,     # dùng giá trị đã chọn
        "name": props.get("name", ""),
        "stroke": "#ffb380",
        "stroke-width": 24,
        "stroke-opacity": 1,
        "stroke-dasharray": "",
        "__line_id": line_id,
        "poly_name": "Biên Hòa - Vũng Tàu"
    }

    new_features.append({
        "type": "Feature",
        "properties": new_props,
        "geometry": geom
    })

    line_id += 1

new_data = {
    "type": "FeatureCollection",
    "name": "Duong_chuan_hoa",
    "crs": {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    },
    "features": new_features
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)

print("Hoàn thành!")
print("File đầu ra:", output_file)
print("Loại highway đã chọn:", highway_value)
print("Số tuyến:", len(new_features))
