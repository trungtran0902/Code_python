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

        # tránh đè lên property tên "geometry"
        if "geometry" in props:
            props["_orig_geometry_prop"] = props["geometry"]

        props["geometry"] = geom
        features.append(props)

    gdf = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")
    return gdf


def spatial_split_by_province(lines_path, xa_phuong_root, output_root):
    start_time = time.time()

    # 1️⃣ Đọc dữ liệu LINE
    print("🔹 Đang đọc dữ liệu line (giữ nguyên thuộc tính gốc)...")
    gdf_lines = load_geojson_preserve_properties(lines_path)
    gdf_lines["__line_id"] = range(len(gdf_lines))

    total_lines = len(gdf_lines)
    print(f"📏 Tổng số line trong file gốc: {total_lines:,}")
    print(f"📋 Các cột thuộc tính: {list(gdf_lines.columns)}")

    # ---------- Xác định input là FILE hay FOLDER ----------
    xa_phuong_root = xa_phuong_root.replace("\\", "/")

    is_file_input = False

    if os.path.isfile(xa_phuong_root) and xa_phuong_root.lower().endswith(".geojson"):
        is_file_input = True
        print("\n📌 Phát hiện bạn đang nhập **1 FILE polygon duy nhất**.")
        polygon_files = [xa_phuong_root]
        province_list = ["SinglePolygon"]
    elif os.path.isdir(xa_phuong_root):
        print("\n📌 Phát hiện bạn đang nhập **THƯ MỤC chứa các tỉnh**.")
        province_list = [p for p in os.listdir(xa_phuong_root)
                         if os.path.isdir(os.path.join(xa_phuong_root, p))]
        polygon_files = None
    else:
        raise ValueError("❌ Đường dẫn không hợp lệ. Không phải Folder hoặc File GeoJSON.")

    # ---------- BIẾN THỐNG KÊ ----------
    total_files = 0
    files_with_lines = 0
    files_without_lines = 0
    summary = []
    processed_ids = set()

    # ---------- BẮT ĐẦU XỬ LÝ ----------
    print(f"🔹 Phát hiện {len(province_list)} tỉnh/thành để xử lý...\n")

    for province in province_list:

        if is_file_input:
            # xử lý 1 polygon file duy nhất
            province_output = os.path.join(output_root, province)
            os.makedirs(province_output, exist_ok=True)
            files = polygon_files
        else:
            province_path = os.path.join(xa_phuong_root, province)
            province_output = os.path.join(output_root, province)
            os.makedirs(province_output, exist_ok=True)

            files = [
                os.path.join(province_path, f)
                for f in os.listdir(province_path)
                if f.lower().endswith(".geojson")
            ]

        print(f"\n🏙️ Đang xử lý tỉnh: {province}")
        print(f"📁 Số file polygon: {len(files)}")

        for poly_path in files:
            total_files += 1
            file = os.path.basename(poly_path)
            base_name = os.path.splitext(file)[0]

            try:
                gdf_poly = gpd.read_file(poly_path)

                if gdf_poly.geometry is None:
                    raise ValueError(f"{file}: không có cột geometry.")

                if gdf_poly.crs != "EPSG:4326":
                    gdf_poly = gdf_poly.to_crs(epsg=4326)

                # sửa geometry lỗi
                gdf_poly["geometry"] = gdf_poly.buffer(0)

                # tránh xung đột cột
                rename_map = {
                    c: f"poly_{c}"
                    for c in gdf_poly.columns
                    if c in gdf_lines.columns and c != gdf_poly.geometry.name
                }
                gdf_poly = gdf_poly.rename(columns=rename_map)

                # ⚡ LỌC TRƯỚC bằng spatial join (tăng tốc)
                candidate = gpd.sjoin(
                    gdf_lines,
                    gdf_poly,
                    how="inner",
                    predicate="intersects"
                ).drop(columns="index_right", errors="ignore")

                if len(candidate) == 0:
                    files_without_lines += 1
                    print(f"   ⚠️ {file}: không có line nào giao")
                    summary.append({
                        "province": province,
                        "file": file,
                        "line_count": 0,
                        "is_split": False
                    })
                    continue

                # chính xác bằng overlay
                selected = gpd.overlay(candidate, gdf_poly, how="intersection")

                # làm sạch cột _1
                for col in list(selected.columns):
                    if col.endswith("_1"):
                        base = col[:-2]
                        if base in selected.columns:
                            selected = selected.drop(columns=[col])
                        else:
                            selected = selected.rename(columns={col: base})

                selected = selected.fillna("")

                if "__line_id" in selected:
                    processed_ids.update(selected["__line_id"].tolist())

                count_line = len(selected)

                # --- Ghi file ---
                if count_line > 0:
                    if count_line > 20:
                        chunks = [selected.iloc[i:i + 20]
                                  for i in range(0, count_line, 20)]
                        for idx, chunk in enumerate(chunks, start=1):
                            out_path = os.path.join(
                                province_output,
                                f"{base_name}_{idx}.geojson"
                            )
                            chunk.to_file(out_path, driver="GeoJSON")
                            print(f"   🔹 {base_name}_{idx}.geojson: {len(chunk)} line")

                            summary.append({
                                "province": province,
                                "file": f"{base_name}_{idx}.geojson",
                                "line_count": len(chunk),
                                "is_split": True
                            })
                        files_with_lines += 1
                    else:
                        out_path = os.path.join(province_output, file)
                        selected.to_file(out_path, driver="GeoJSON")

                        print(f"   ✅ {file}: {count_line} line")
                        summary.append({
                            "province": province,
                            "file": file,
                            "line_count": count_line,
                            "is_split": False
                        })
                        files_with_lines += 1
                else:
                    files_without_lines += 1

            except Exception as e:
                print(f"   ❌ Lỗi khi xử lý {file}: {e}")

    # ---------- Xuất thống kê ----------
    summary_path = os.path.join(output_root, "thong_ke_line.csv")
    pd.DataFrame(summary).to_csv(summary_path, index=False, encoding="utf-8-sig")

    # ---------- Tổng kết ----------
    duration = time.time() - start_time

    print("\n==============================")
    print("📊 THỐNG KÊ TỔNG HỢP")
    print(f"📁 Tổng số file GeoJSON đã xử lý: {total_files:,}")
    print(f"✅ Số file có line: {files_with_lines:,}")
    print(f"⚠️ Số file không có line: {files_without_lines:,}")
    print(f"📏 Tổng số line trong dữ liệu gốc: {total_lines:,}")
    print(f"📈 Tổng số line sau khi cắt (loại trùng ID): {len(processed_ids):,}")
    print(f"📑 File thống kê: {summary_path}")
    print(f"⏱️ Thời gian thực thi: {duration:.2f} giây")
    print("==============================")
    print("🎉 Hoàn tất xử lý toàn bộ polygon!")


if __name__ == "__main__":
    print("=== CHƯƠNG TRÌNH CẮT LINE THEO XÃ/PHƯỜNG (File hoặc Folder đều chạy được) ===")

    lines_path = input("Nhập đường dẫn file GeoJSON chứa line (toàn quốc): ").replace("\\", "/").strip()
    xa_phuong_root = input("Nhập đường dẫn thư mục hoặc file polygon GeoJSON: ").replace("\\", "/").strip()
    output_root = input("Nhập đường dẫn thư mục để lưu kết quả: ").replace("\\", "/").strip()

    spatial_split_by_province(lines_path, xa_phuong_root, output_root)
