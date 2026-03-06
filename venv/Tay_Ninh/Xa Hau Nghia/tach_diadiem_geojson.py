import pandas as pd
import json
from pathlib import Path
import unicodedata
import re
import sys

# =================== HÀM TIỆN ÍCH ===================

def make_safe_filename(name):
    """Chuyển tên tiếng Việt có dấu -> không dấu, chỉ giữ ký tự an toàn."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    no_diacritics = "".join([c for c in nfkd if not unicodedata.combining(c)])
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", no_diacritics.strip())
    safe = re.sub(r"_+", "_", safe)
    return safe.lower()

def detect_column(df, possible_names):
    """Tìm tên cột thực tế trong DataFrame, không phân biệt hoa/thường."""
    lower_map = {c.lower().strip(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None

def create_geojson_from_df(df, lat_col, lng_col, output_path):
    """Tạo file GeoJSON từ DataFrame có cột lat/lng."""
    features = []

    for _, row in df.iterrows():
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
        except Exception:
            continue  # bỏ qua nếu không hợp lệ

        # Loại bỏ các giá trị NaN khỏi thuộc tính
        props = {k: (None if pd.isna(v) else v) for k, v in row.drop([lat_col, lng_col]).to_dict().items()}

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

# =================== SCRIPT CHÍNH ===================

def main():
    print("📂 Chuyển đổi Excel → GeoJSON theo cột 'Loại Địa Điểm'\n")

    folder = input("Nhập đường dẫn chứa file Excel: ").strip()
    file_name = input("Nhập tên file Excel (ví dụ: data.xlsx): ").strip()

    file_path = Path(folder) / file_name
    if not file_path.exists():
        print(f"❌ Không tìm thấy file: {file_path}")
        sys.exit(1)

    # Đọc file Excel và loại bỏ cột "Unnamed"
    try:
        df = pd.read_excel(file_path)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]  # loại bỏ mọi cột Unnamed
    except Exception as e:
        print(f"❌ Lỗi đọc file Excel: {e}")
        sys.exit(1)

    # Phát hiện cột toạ độ
    lat_col = detect_column(df, ["lat", "latitude", "Lat", "LAT"])
    lng_col = detect_column(df, ["lng", "long", "longitude", "Long", "LONG"])

    if not lat_col or not lng_col:
        print("❌ Không tìm thấy cột tọa độ. Vui lòng kiểm tra các cột Lat/Long trong file.")
        sys.exit(1)

    # Phát hiện cột Loại Địa Điểm
    loai_col = detect_column(df, ["Loại Địa Điểm", "Loai Dia Diem", "loai_dia_diem"])
    if not loai_col:
        print("❌ Không tìm thấy cột 'Loại Địa Điểm' trong file.")
        sys.exit(1)

    # Tạo thư mục xuất file
    output_dir = Path(folder) / "geojson_output"
    output_dir.mkdir(exist_ok=True)

    # Lấy danh sách loại địa điểm duy nhất
    unique_types = df[loai_col].dropna().unique()
    print(f"🔍 Phát hiện {len(unique_types)} loại địa điểm.\n")

    for loai in unique_types:
        df_subset = df[df[loai_col] == loai]
        safe_name = make_safe_filename(str(loai))
        output_file = output_dir / f"{safe_name}.geojson"

        create_geojson_from_df(df_subset, lat_col, lng_col, output_file)
        print(f"✅ Xuất: {output_file.name} ({len(df_subset)} bản ghi)")

    print(f"\n🎉 Hoàn tất! Tất cả GeoJSON nằm trong thư mục: {output_dir}")

# ====================================================

if __name__ == "__main__":
    main()
