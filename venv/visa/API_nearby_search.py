import pandas as pd
import requests
import os
import time
import sys
import json

# ==================== CẤU HÌNH ====================
script_dir = os.path.dirname(os.path.abspath(__file__))
excel_file_path = os.path.join(script_dir, 'data_3.xlsx')
output_file_path = os.path.join(script_dir, 'data_3_output_V3.xlsx')
geojson_output_path = os.path.join(script_dir, 'data_3_output_V3.geojson')

API_KEY = os.getenv("GOOGLE_API_KEY") or input("🔑 Nhập Google API Key: ").strip()

SAVE_EVERY = 10              # Ghi file Excel sau mỗi 10 dòng
SLEEP_BETWEEN_CALLS = 0.3    # giây
# =================================================

def get_places_data(lat, long, keyword):
    """Gọi Google Places API để lấy dữ liệu địa điểm."""
    url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
    params = {
        'location': f'{lat},{long}',
        'radius': 50,
        'keyword': keyword,
        'language': 'vi',
        'key': API_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        status = data.get('status', '')
        if status == 'OK' and data.get('results'):
            place = data['results'][0]
            name = place.get('name', '')
            address = place.get('vicinity', '')
            loc = place.get('geometry', {}).get('location', {})
            return name, address, loc.get('lat'), loc.get('lng')
        elif status == 'ZERO_RESULTS':
            return None, None, None, None
        else:
            print(f"⚠️ API trả về lỗi: {status}")
            return None, None, None, None

    except Exception as e:
        print(f"❌ Lỗi khi gọi API: {e}")
        return None, None, None, None


def export_geojson(df, lat_col="Lat_v1", long_col="Long_v1", name_col="Name", address_col="Address", location_col="Location", output_path=None):
    """Xuất DataFrame ra file GeoJSON."""
    features = []

    for _, row in df.iterrows():
        try:
            # Ưu tiên toạ độ mới nếu có
            if pd.notna(row.get(location_col)) and "," in str(row[location_col]):
                parts = [x.strip() for x in str(row[location_col]).split(",")]
                lat, lng = float(parts[0]), float(parts[1])
            else:
                lat, lng = float(row[lat_col]), float(row[long_col])
        except Exception:
            continue  # bỏ dòng lỗi toạ độ

        props = {
            "Name": row.get(name_col, ""),
            "Address": row.get(address_col, ""),
            "Keyword": row.get("Keyword", ""),
            "Original_Lat": row.get(lat_col),
            "Original_Long": row.get(long_col),
        }

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props
        })

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"🌍 Đã xuất GeoJSON → {output_path} ({len(features)} điểm)")


def main():
    if not os.path.exists(excel_file_path):
        print(f"❌ Không tìm thấy file: {excel_file_path}")
        sys.exit(1)

    df = pd.read_excel(excel_file_path)
    df.columns = df.columns.str.strip()

    # Tạo cột nếu chưa có
    for col in ["Name", "Address", "Location"]:
        if col not in df.columns:
            df[col] = ""

    for idx, row in df.iterrows():
        lat, long, keyword = row["Lat_v1"], row["Long_v1"], str(row["Keyword"])
        print(f"▶️ Dòng {idx + 1}/{len(df)} → ({lat},{long}) | {keyword}")

        name, addr, lat_res, lng_res = get_places_data(lat, long, keyword)
        df.at[idx, "Name"] = name or ""
        df.at[idx, "Address"] = addr or ""
        df.at[idx, "Location"] = f"{lat_res}, {lng_res}" if lat_res and lng_res else ""

        if (idx + 1) % SAVE_EVERY == 0:
            df.to_excel(output_file_path, index=False)
            print(f"💾 Đã lưu tạm sau {idx + 1} dòng.")

        time.sleep(SLEEP_BETWEEN_CALLS)

    # Lưu file Excel hoàn chỉnh
    df.to_excel(output_file_path, index=False)
    print(f"\n✅ Hoàn thành Excel → {output_file_path}")

    # Xuất thêm file GeoJSON
    export_geojson(df, output_path=geojson_output_path)
    print("\n🎉 Hoàn tất toàn bộ quá trình!")


if __name__ == "__main__":
    main()
