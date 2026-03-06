import json
import os
from pathlib import Path

# Đường dẫn tới file geojson gốc
input_file = "tonghop_update_join.geojson"  # thay bằng file của bạn
output_dir = Path("split_geojson")
output_dir.mkdir(exist_ok=True)

# Đọc file geojson gốc
with open(input_file, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# Tách từng feature ra thành file riêng
for feature in geojson_data["features"]:
    # Lấy tên dự án
    project_name = feature["properties"].get("tenduan", "unknown").strip()

    # Làm sạch tên file (tránh ký tự đặc biệt)
    safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in project_name)
    safe_name = safe_name.replace(" ", "_")

    # Tạo cấu trúc GeoJSON riêng cho feature này
    single_geojson = {
        "type": "FeatureCollection",
        "features": [feature]
    }

    # Ghi ra file mới
    output_file = output_dir / f"{safe_name}.geojson"
    with open(output_file, "w", encoding="utf-8") as f_out:
        json.dump(single_geojson, f_out, ensure_ascii=False, indent=2)

print(f"✅ Đã tách thành {len(geojson_data['features'])} file, lưu trong thư mục: {output_dir}")
