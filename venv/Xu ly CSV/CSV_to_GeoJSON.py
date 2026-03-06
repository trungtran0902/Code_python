import pandas as pd
import json
import os
import ast  # để parse chuỗi geo {"lat":..,"lng":..}

# Nhập thư mục chứa các file CSV
folder_path = input("Nhập đường dẫn thư mục chứa các file CSV: ").strip()

# Lấy danh sách tất cả file .csv trong thư mục
csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]

if not csv_files:
    print("⚠️ Không tìm thấy file CSV nào trong thư mục.")
else:
    for file_name in csv_files:
        input_file = os.path.join(folder_path, file_name)
        output_file = os.path.join(folder_path, file_name.replace(".csv", ".geojson"))

        print(f"⏳ Đang xử lý: {file_name}")

        df = pd.read_csv(input_file)
        df.columns = df.columns.str.strip()

        features = []

        for _, row in df.iterrows():
            try:
                geo_dict = ast.literal_eval(row["geo"])  # parse JSON string
                lat = geo_dict.get("lat")
                lng = geo_dict.get("lng")

                if pd.notna(lat) and pd.notna(lng):
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lng, lat]
                        },
                        "properties": {
                            "name": row.get("name"),
                            "street": row.get("street"),
                            "ward": row.get("ward"),
                            "district": row.get("district"),
                            "province": row.get("province"),
                            "country": row.get("country"),
                            "place_type": row.get("place_type"),
                            "metadata": row.get("metadata")
                        }
                    }
                    features.append(feature)
            except Exception as e:
                print(f"  ⚠️ Lỗi khi xử lý dòng: {row.get('name')} -> {e}")

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        # Ghi file GeoJSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã tạo {output_file} với {len(features)} điểm")
