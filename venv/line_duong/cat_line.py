import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
import os
import time


def load_geojson_preserve_properties(path):
    """Đọc GeoJSON và giữ nguyên mọi properties"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = []
    for feat in data["features"]:
        geom = shape(feat["geometry"])
        props = feat.get("properties", {})
        props["geometry"] = geom
        features.append(props)

    gdf = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")
    return gdf


def spatial_split_by_province(lines_path, xa_phuong_root, output_root):
    start_time = time.time()

    # 1️⃣ Đọc file line (giữ nguyên thuộc tính)
    print("🔹 Đang đọc dữ liệu line (giữ nguyên thuộc tính gốc)...")
    gdf_lines = load_geojson_preserve_properties(lines_path)
    gdf_lines["__line_id"] = range(len(gdf_lines))  # gán ID duy nhất

    total_lines = len(gdf_lines)
    print(f"📏 Tổng số line trong file gốc: {total_lines:,}")
    print(f"📋 Các cột thuộc tính: {list(gdf_lines.columns)}")

    # 2️⃣ Biến thống kê
    total_files = 0
    files_with_lines = 0
    files_without_lines = 0
    summary = []
    processed_ids = set()  # lưu các ID line duy nhất đã xuất hiện

    # 3️⃣ Duyệt qua từng tỉnh
    provinces = [p for p in os.listdir(xa_phuong_root) if os.path.isdir(os.path.join(xa_phuong_root, p))]
    print(f"🔹 Phát hiện {len(provinces)} tỉnh/thành để xử lý...")

    for province in provinces:
        province_path = os.path.join(xa_phuong_root, province)
        print(f"\n🏙️ Đang xử lý tỉnh: {province}")

        province_output = os.path.join(output_root, province)
        os.makedirs(province_output, exist_ok=True)

        for file in os.listdir(province_path):
            if file.lower().endswith(".geojson"):
                total_files += 1
                poly_path = os.path.join(province_path, file)

                try:
                    # Đọc polygon (xã/phường)
                    gdf_poly = gpd.read_file(poly_path)

                    # Nếu mất geometry thì khôi phục
                    if gdf_poly.geometry is None:
                        if "geometry" in gdf_poly.columns:
                            gdf_poly = gdf_poly.set_geometry("geometry")
                        else:
                            raise ValueError(f"{file}: Không tìm thấy cột geometry.")

                    # Chuẩn hoá CRS về EPSG:4326
                    if gdf_poly.crs != "EPSG:4326":
                        gdf_poly = gdf_poly.to_crs(epsg=4326)

                    # ⚙️ Đổi tên các cột trùng với layer line (trừ geometry)
                    geom_name = gdf_poly.geometry.name
                    rename_map = {
                        c: f"poly_{c}"
                        for c in gdf_poly.columns
                        if c in gdf_lines.columns and c != geom_name
                    }
                    if rename_map:
                        gdf_poly = gdf_poly.rename(columns=rename_map)

                    # (Tuỳ chọn) Sửa hình học không hợp lệ
                    gdf_poly["geometry"] = gdf_poly.buffer(0)

                    # ⚙️ Cắt line theo polygon bằng overlay (chính xác theo ranh giới)
                    selected = gpd.overlay(gdf_lines, gdf_poly, how="intersection")

                    # 🩹 Giữ nguyên tên cột line gốc, xử lý các trường bị "_1"
                    cols = list(selected.columns)
                    for col in cols:
                        if col.endswith("_1"):
                            base = col[:-2]
                            if base in selected.columns:
                                selected = selected.drop(columns=[col])
                            else:
                                selected = selected.rename(columns={col: base})

                    count_line = len(selected)
                    selected = selected.fillna("")  # làm sạch NaN

                    if "__line_id" in selected.columns:
                        processed_ids.update(selected["__line_id"].tolist())

                    base_name = os.path.splitext(file)[0]
                    output_path = os.path.join(province_output, file)

                    if count_line > 0:
                        if count_line > 20:
                            # Chia nhỏ nếu >20 line
                            chunks = [selected.iloc[i:i + 20] for i in range(0, count_line, 20)]
                            for idx, chunk in enumerate(chunks, start=1):
                                chunk_output_path = os.path.join(province_output, f"{base_name}_{idx}.geojson")
                                chunk.to_file(chunk_output_path, driver="GeoJSON")
                                print(f"   🔹 {base_name}_{idx}.geojson: {len(chunk)} line")

                                summary.append({
                                    "province": province,
                                    "file": f"{base_name}_{idx}.geojson",
                                    "line_count": len(chunk),
                                    "is_split": True
                                })
                            files_with_lines += 1
                        else:
                            selected.to_file(output_path, driver="GeoJSON")
                            files_with_lines += 1
                            print(f"   ✅ {file}: {count_line} line")
                            summary.append({
                                "province": province,
                                "file": file,
                                "line_count": count_line,
                                "is_split": False
                            })
                    else:
                        files_without_lines += 1
                        print(f"   ⚠️ {file}: không có line nào")
                        summary.append({
                            "province": province,
                            "file": file,
                            "line_count": 0,
                            "is_split": False
                        })

                except Exception as e:
                    print(f"   ❌ Lỗi khi xử lý {file}: {e}")

    # 4️⃣ Xuất thống kê
    summary_path = os.path.join(output_root, "thong_ke_line.csv")
    pd.DataFrame(summary).to_csv(summary_path, index=False, encoding="utf-8-sig")

    # 5️⃣ Tổng kết
    duration = time.time() - start_time
    unique_scanned_lines = len(processed_ids)

    print("\n==============================")
    print("📊 THỐNG KÊ TỔNG HỢP")
    print(f"📁 Tổng số file GeoJSON đã xử lý: {total_files:,}")
    print(f"✅ Số file có line: {files_with_lines:,}")
    print(f"⚠️ Số file không có line: {files_without_lines:,}")
    print(f"📏 Tổng số line trong dữ liệu gốc: {total_lines:,}")
    print(f"📈 Tổng số line sau khi cắt (loại trùng ID): {unique_scanned_lines:,}")
    print(f"📑 File thống kê: {summary_path}")
    print(f"⏱️ Thời gian thực thi: {duration:.2f} giây")
    print("==============================")
    print("🎉 Hoàn tất xử lý toàn bộ tỉnh/thành!")


if __name__ == "__main__":
    print("=== CHƯƠNG TRÌNH CẮT LINE THEO XÃ/PHƯỜNG (GIỮ NGUYÊN THUỘC TÍNH + CHIA NHỎ >20 LINE + GIỮ NGUYÊN TÊN TRƯỜNG) ===")
    lines_path = input("Nhập đường dẫn file GeoJSON chứa line (toàn quốc): ").strip()
    xa_phuong_root = input("Nhập đường dẫn thư mục gốc chứa các tỉnh (XaPhuong): ").strip()
    output_root = input("Nhập đường dẫn thư mục để lưu kết quả: ").strip()

    spatial_split_by_province(lines_path, xa_phuong_root, output_root)
