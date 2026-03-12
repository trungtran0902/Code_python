import os
import geopandas as gpd

def split_multipolygon_to_files():
    # ===== B1 =====
    input_dir = input("Nhập đường dẫn thư mục chứa file GeoJSON: ").strip()

    # ===== B2 =====
    file_name = input("Nhập tên file GeoJSON (vd: data.geojson): ").strip()
    input_path = os.path.join(input_dir, file_name)

    if not os.path.isfile(input_path):
        print("❌ File không tồn tại!")
        return

    # ===== B3 =====
    output_dir = input("Nhập đường dẫn thư mục output: ").strip()
    os.makedirs(output_dir, exist_ok=True)

    # ===== B4: xử lý =====
    try:
        gdf = gpd.read_file(input_path)

        # Tách MultiPolygon → Polygon
        gdf_exploded = gdf.explode(index_parts=False).reset_index(drop=True)

        base_name = os.path.splitext(file_name)[0]

        for idx, row in gdf_exploded.iterrows():
            out_gdf = gpd.GeoDataFrame(
                [row],
                geometry="geometry",
                crs=gdf.crs
            )

            out_file = f"{base_name}_poly_{idx+1:03d}.geojson"
            out_path = os.path.join(output_dir, out_file)

            out_gdf.to_file(out_path, driver="GeoJSON")

        print("✅ Xử lý thành công!")
        print(f"🔢 Tổng số polygon: {len(gdf_exploded)}")
        print(f"📁 Thư mục output: {output_dir}")

    except Exception as e:
        print("❌ Lỗi xử lý:", e)


if __name__ == "__main__":
    split_multipolygon_to_files()
