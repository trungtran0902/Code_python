import geopandas as gpd
import pandas as pd   # 🔥 bạn đã thiếu dòng này
import os

def merge_geojson_files(input_folder, output_file):
    input_folder = input_folder.replace("\\", "/")

    files = sorted([
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.lower().endswith(".geojson")
    ])

    if not files:
        print("❌ Không tìm thấy file GeoJSON nào.")
        return

    print(f"🔹 Phát hiện {len(files)} file cần gộp...")

    gdf_list = []

    for f in files:
        try:
            print(f"   📄 Đang đọc: {os.path.basename(f)}")
            gdf = gpd.read_file(f)
            gdf_list.append(gdf)
        except Exception as e:
            print(f"   ❌ Lỗi đọc {f}: {e}")

    # Gộp tất cả file
    merged = gpd.GeoDataFrame(
        pd.concat(gdf_list, ignore_index=True),
        crs="EPSG:4326"
    )

    # Xuất ra file
    merged.to_file(output_file, driver="GeoJSON")
    print(f"\n🎉 Đã gộp xong!")
    print(f"📁 File đầu ra: {output_file}")
    print(f"📏 Tổng số line: {len(merged)}")


# ======== RUN =========
if __name__ == "__main__":
    folder = input("Nhập đường dẫn folder chứa các file GeoJSON đã chia nhỏ: ").replace("\\", "/").strip()
    output = input("Nhập đường dẫn file GeoJSON đầu ra (vd: G:/output/QuangBinh_merged.geojson): ").replace("\\", "/").strip()

    merge_geojson_files(folder, output)
