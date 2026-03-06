import geopandas as gpd
import pandas as pd
from pathlib import Path
import sys

# ---------------------------------------
# 1. Hỏi đường dẫn gốc chứa 63 thư mục tỉnh
# ---------------------------------------
root = input("Nhập đường dẫn tới thư mục gốc chứa các tỉnh: ").strip()

if not root:
    root = "."

root_dir = Path(root)
if not root_dir.exists() or not root_dir.is_dir():
    print(f"❗ Thư mục '{root_dir}' không tồn tại hoặc không phải là thư mục.")
    sys.exit(1)

output_xlsx = root_dir / "centroid_log.xlsx"
results = []
folder_stats = {}       # 👈 lưu số lượng file geojson mỗi tỉnh

print(f"👉 Đang quét thư mục gốc: {root_dir.resolve()}\n")

# ---------------------------------------
# 2. Quét qua tất cả thư mục con (các tỉnh)
# ---------------------------------------
for province_dir in sorted(root_dir.iterdir()):
    if province_dir.is_dir():
        province_name = province_dir.name
        file_count = 0
        print(f"📂 Đang xử lý tỉnh: {province_name}")

        # Quét toàn bộ file geojson trong thư mục tỉnh
        for file in province_dir.glob("*.geojson"):
            file_count += 1
            try:
                gdf = gpd.read_file(file)

                if gdf.empty:
                    print(f"   {file.name}: ❗ Không có dữ liệu")
                    continue

                # Nếu chưa có CRS thì gán mặc định WGS84
                if gdf.crs is None:
                    gdf = gdf.set_crs(epsg=4326)

                # Chuyển sang CRS phẳng (ví dụ UTM zone 48N)
                gdf_proj = gdf.to_crs(epsg=32648)

                # Tính centroid trên CRS phẳng
                gdf_proj['centroid'] = gdf_proj.geometry.centroid

                # Chuyển centroid về lại WGS84
                centroids_geo = gdf_proj['centroid'].to_crs(epsg=4326)

                # Lưu kết quả
                for idx, point in enumerate(centroids_geo):
                    results.append({
                        "province": province_name,      # tên tỉnh từ folder
                        "filename": file.name,          # tên file geojson
                        "feature_index": idx,
                        "lat": round(point.y, 6),       # latitude
                        "lon": round(point.x, 6)        # longitude
                    })

                print(f"   ✅ {file.name}: {len(gdf)} feature")

            except Exception as e:
                print(f"   ⚠️ Lỗi với {file.name}: {e}")

        folder_stats[province_name] = file_count

# ---------------------------------------
# 3. Xuất kết quả ra Excel
# ---------------------------------------
if results:
    df = pd.DataFrame(results)
    df.to_excel(output_xlsx, index=False, engine='openpyxl')
    print(f"\n📄 Đã ghi kết quả centroid vào: {output_xlsx.resolve()}")
else:
    print("\n❗ Không có dữ liệu hợp lệ để xuất.")

# ---------------------------------------
# 4. Hiển thị thống kê số file mỗi tỉnh
# ---------------------------------------
print("\n📊 Thống kê số lượng file GeoJSON mỗi tỉnh:")
for prov, count in folder_stats.items():
    print(f"   {prov}: {count} file GeoJSON")

print(f"\n✅ Tổng số tỉnh quét: {len(folder_stats)}")
print(f"✅ Tổng số file GeoJSON: {sum(folder_stats.values())}")
