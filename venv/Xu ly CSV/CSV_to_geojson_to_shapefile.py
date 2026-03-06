import os
import json
import ast
import pandas as pd
import geopandas as gpd
from datetime import datetime

def parse_geo(geo_str):
    """Đọc lat/lng từ cột geo"""
    if pd.isna(geo_str):
        return None, None
    try:
        d = json.loads(geo_str) if isinstance(geo_str, str) and geo_str.strip().startswith("{") else ast.literal_eval(geo_str)
        return d.get("lat"), d.get("lng")
    except Exception:
        return None, None

def clean_metadata(meta_str):
    """Rút gọn metadata nếu là Google Maps URL"""
    if not isinstance(meta_str, str) or not meta_str.strip():
        return "{}"
    try:
        d = json.loads(meta_str) if meta_str.strip().startswith("{") else ast.literal_eval(meta_str)
        if isinstance(d, dict) and "url" in d:
            url_val = d["url"]
            if isinstance(url_val, str) and url_val.startswith("https://www.google.com/maps/place/"):
                return '{"url": "https://www.google.com/maps/place/"}'
        return "{}"
    except Exception:
        return "{}"

def shapefile_exists(folder, base):
    """Kiểm tra bộ shapefile có đủ trong folder"""
    required_ext = [".shp", ".shx", ".dbf", ".prj"]
    return all(os.path.exists(os.path.join(folder, base + ext)) for ext in required_ext)

# ======== INPUT ========
folder_path = input("Nhập đường dẫn thư mục chứa file CSV: ").strip()
log_path = os.path.join(folder_path, "export_log.txt")

# Đọc log cũ (nếu có) để biết file nào đã xử lý
processed_files = set()
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                processed_files.add(line.split()[0])  # lấy base_name từ log

# Lấy danh sách file CSV
csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]

if not csv_files:
    print("⚠️ Không tìm thấy file CSV nào để xử lý.")
else:
    for file_name in csv_files:
        base = os.path.splitext(file_name)[0]
        input_file = os.path.join(folder_path, file_name)
        out_dir = os.path.join(folder_path, base)

        # Skip nếu file đã có trong log VÀ folder có đủ shapefile
        if base in processed_files and shapefile_exists(out_dir, base):
            print(f"⏭ Bỏ qua {file_name}, đã xử lý và có đủ shapefile.")
            continue

        os.makedirs(out_dir, exist_ok=True)
        geojson_path = os.path.join(out_dir, base + ".geojson")
        shp_path = os.path.join(out_dir, base + ".shp")

        print(f"⏳ Đang xử lý: {file_name}")

        # Đọc CSV
        df = pd.read_csv(input_file, dtype=str, keep_default_na=False)
        df.columns = df.columns.str.strip()

        features = []
        for _, row in df.iterrows():
            lat, lng = parse_geo(row.get("geo"))
            if lat is None or lng is None:
                continue

            props = {
                "name": row.get("name"),
                "street": row.get("street"),
                "ward": row.get("ward"),
                "district": row.get("district"),
                "province": row.get("province"),
                "country": row.get("country"),
                "place_type": row.get("place_type"),
                "metadata": clean_metadata(row.get("metadata"))
            }

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                "properties": props
            })

        geojson = {"type": "FeatureCollection", "features": features}

        # Ghi GeoJSON
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        # Xuất Shapefile
        gdf = gpd.read_file(geojson_path)
        gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")

        print(f"📂 Đã tạo GeoJSON và Shapefile trong {out_dir}")

        # 🔑 Ghi log ngay sau mỗi file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{base} với {len(features):,} điểm - {timestamp}\n")

        print(f"📝 Đã ghi log cho {base} ({len(features):,} điểm)\n")
