import geopandas as gpd
import pandas as pd
import os

def merge_one_province(input_folder, output_folder):
    files = sorted([
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.lower().endswith(".geojson")
    ])

    if not files:
        print(f"⚠️  Bỏ qua (không có geojson): {input_folder}")
        return

    province_name = os.path.basename(input_folder)
    print(f"🔹 Đang gộp: {province_name} ({len(files)} file)")

    gdf_list = []
    for f in files:
        try:
            print(f"   📄 {os.path.basename(f)}")
            gdf = gpd.read_file(f)
            gdf_list.append(gdf)
        except Exception as e:
            print(f"   ❌ Lỗi đọc {f}: {e}")

    if not gdf_list:
        print("❌ Không file nào đọc được.")
        return

    merged = gpd.GeoDataFrame(
        pd.concat(gdf_list, ignore_index=True),
        crs=gdf_list[0].crs
    )

    out_file = os.path.join(
        output_folder,
        f"{province_name}_merged.geojson"
    )

    merged.to_file(out_file, driver="GeoJSON")
    print(f"   🎉 Xuất: {out_file} ({len(merged)} dòng)\n")


def merge_all_provinces(parent_folder, output_root):
    parent_folder = parent_folder.replace("\\", "/")
    output_root = output_root.replace("\\", "/")

    if not os.path.isdir(parent_folder):
        print("❌ Thư mục cha không tồn tại.")
        return

    if not os.path.exists(output_root):
        os.makedirs(output_root)
        print(f"📁 Đã tạo thư mục đầu ra: {output_root}")

    subfolders = [
        os.path.join(parent_folder, d)
        for d in os.listdir(parent_folder)
        if os.path.isdir(os.path.join(parent_folder, d))
    ]

    print(f"📁 Phát hiện {len(subfolders)} thư mục tỉnh.\n")

    for folder in subfolders:
        merge_one_province(folder, output_root)

    print("✅ Hoàn tất toàn bộ!")


# ===== RUN =====
if __name__ == "__main__":
    root = input("Nhập đường dẫn thư mục cha (vd: G:/OSM/map4d): ").strip()
    out_root = input("Nhập thư mục đầu ra (vd: G:/OSM/map4d_merged): ").strip()
    merge_all_provinces(root, out_root)
