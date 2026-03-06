import os
import re
import geopandas as gpd
from collections import defaultdict
import pandas as pd

def merge_geojson_by_prefix(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    # Lấy tất cả file geojson
    files = [f for f in os.listdir(input_folder) if f.endswith(".geojson")]

    # Dictionary nhóm các file theo prefix
    groups = defaultdict(list)

    # Regex lấy "Phường ABC_1234567" và bỏ "_1_filtered"
    pattern = re.compile(r"^(.*?_.*?)(?:_\d+)?_filtered\.geojson$", re.UNICODE)

    for file in files:
        match = pattern.match(file)
        if match:
            group_name = match.group(1)
            groups[group_name].append(file)

    print(f"🔍 Tìm thấy {len(groups)} nhóm file cần gộp")

    # Xử lý từng nhóm
    for group_name, file_list in groups.items():
        print(f"\n📂 Đang gộp nhóm: {group_name} ({len(file_list)} file)")

        merged_parts = []
        crs_used = None

        # Ghép lần lượt
        for file in sorted(file_list):
            path = os.path.join(input_folder, file)
            try:
                gdf = gpd.read_file(path)

                # Lưu CRS chung
                if crs_used is None:
                    crs_used = gdf.crs
                else:
                    if gdf.crs != crs_used:
                        print(f"⚠️ CRS khác nhau → chuyển {file} về CRS chung")
                        gdf = gdf.to_crs(crs_used)

                merged_parts.append(gdf)

            except Exception as e:
                print(f"   ❌ Lỗi đọc file {file}: {e}")

        if not merged_parts:
            print("   ⚠️ Không có file hợp lệ để gộp → bỏ qua.")
            continue

        # Gộp tất cả file
        merged = gpd.GeoDataFrame(
            pd.concat(merged_parts, ignore_index=True),
            crs=crs_used
        )

        # Xuất file
        out_path = os.path.join(output_folder, f"{group_name}.geojson")
        merged.to_file(out_path, driver="GeoJSON")

        print(f"   ✔ Xuất file gộp: {os.path.basename(out_path)} ({len(merged)} đối tượng)")


# ======================= MAIN =========================

if __name__ == "__main__":
    print("=== GỘP CÁC FILE GEOJSON THEO NHÓM TÊN ===")

    input_folder = input("B1️⃣  Nhập đường dẫn chứa các file cần gộp: ").strip()
    output_folder = input("B2️⃣  Nhập đường dẫn thư mục lưu file gộp: ").strip()

    merge_geojson_by_prefix(input_folder, output_folder)

    print("\n🎉 Hoàn tất gộp file GeoJSON!")
