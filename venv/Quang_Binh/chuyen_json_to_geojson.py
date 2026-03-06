import json
import os

# ---- 1. Nhập đường dẫn thư mục JSON ----
input_dir = input("Nhập đường dẫn thư mục chứa các file JSON: ").strip()

# ---- 2. Đường dẫn thư mục xuất GeoJSON (tự tạo nếu chưa có) ----
output_dir = os.path.join(input_dir, "geojson_output")
os.makedirs(output_dir, exist_ok=True)

# ---- 3. Lặp qua từng file JSON trong thư mục ----
for filename in os.listdir(input_dir):
    if filename.endswith(".json"):
        json_path = os.path.join(input_dir, filename)

        # Đọc file JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        info = data.get("result", {})
        loc = info.get("location", {})

        # Kiểm tra tọa độ
        if "lng" not in loc or "lat" not in loc:
            print(f"Bỏ qua {filename}: không có tọa độ")
            continue

        # Tạo GeoJSON
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [loc["lng"], loc["lat"]]
            },
            "properties": {
                "id": info.get("id"),
                "name": info.get("name"),
                "address": info.get("address"),
                "types": info.get("types", []),
                "admin": info.get("addressComponents", [])
            }
        }

        # Xuất file GeoJSON
        geojson_filename = filename.replace(".json", ".geojson")
        geojson_path = os.path.join(output_dir, geojson_filename)

        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=4)

        print(f"✔ Đã tạo: {geojson_filename}")

print("\nHoàn tất! Các file GeoJSON nằm trong thư mục:", output_dir)
