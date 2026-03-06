import os
import re
import geopandas as gpd


# ==============================
#   HÀM LỌC LINE THEO KEYWORD
# ==============================

def filter_lines(
        gdf,
        field_name="name",  # <== ĐÃ SỬA ĐÚNG TÊN CỘT
        prefix_keywords=None,  # ví dụ: ["Hẻm", "Ngõ"]
        contain_keywords=None,  # ví dụ: ["Quốc lộ", "QL"]
        regex_pattern=None,  # ví dụ: r"^Hẻm\s+\d+"
        ignore_case=True
):
    """Trả về GeoDataFrame đã lọc theo nhiều điều kiện"""

    if field_name not in gdf.columns:
        print(f"⚠️ Không tìm thấy cột '{field_name}', giữ nguyên toàn bộ dữ liệu.")
        return gdf.copy()

    series = gdf[field_name].fillna("").astype(str)

    # chuẩn hóa chữ
    if ignore_case:
        series_proc = series.str.lower()
        if prefix_keywords:
            prefix_keywords = [kw.lower() for kw in prefix_keywords]
        if contain_keywords:
            contain_keywords = [kw.lower() for kw in contain_keywords]
        if regex_pattern:
            regex_flags = re.IGNORECASE
        else:
            regex_flags = 0
    else:
        series_proc = series
        regex_flags = 0

    # Điều kiện lọc
    mask = True

    # 1. Prefix
    if prefix_keywords:
        prefix_regex = r"^(" + "|".join(map(re.escape, prefix_keywords)) + ")"
        mask = mask & series_proc.str.match(prefix_regex)

    # 2. Contain
    if contain_keywords:
        contain_regex = "(" + "|".join(map(re.escape, contain_keywords)) + ")"
        mask = mask & series_proc.str.contains(contain_regex)

    # 3. Regex nâng cao
    if regex_pattern:
        mask = mask & series_proc.str.match(regex_pattern, flags=regex_flags)

    return gdf[mask].copy()


# =======================================
#     HÀM CHẠY LỌC TRÊN TOÀN THƯ MỤC
# =======================================

def batch_filter_lines(
        input_folder,
        output_folder,
        field_name="name",  # <== ĐÃ SỬA ĐÚNG
        prefix_keywords=None,
        contain_keywords=None,
        regex_pattern=None,
        ignore_case=True,
        export_unmatched=False
):
    """Lọc toàn bộ file GeoJSON trong thư mục"""

    os.makedirs(output_folder, exist_ok=True)
    files = [f for f in os.listdir(input_folder) if f.lower().endswith(".geojson")]

    print(f"🔍 Phát hiện {len(files)} file GeoJSON để lọc...")

    for file in files:
        input_path = os.path.join(input_folder, file)
        print(f"\n📂 Đang xử lý file: {file}")

        try:
            gdf = gpd.read_file(input_path)

            # Lọc
            filtered = filter_lines(
                gdf,
                field_name=field_name,
                prefix_keywords=prefix_keywords,
                contain_keywords=contain_keywords,
                regex_pattern=regex_pattern,
                ignore_case=ignore_case
            )

            # Ghi file đã lọc
            out_file = os.path.splitext(file)[0] + "_filtered.geojson"
            output_path = os.path.join(output_folder, out_file)
            filtered.to_file(output_path, driver="GeoJSON")
            print(f"   ✔ Tạo file lọc: {out_file} ({len(filtered)} line)")

            # Ghi file không match (nếu cần)
            if export_unmatched:
                unmatched = gdf[~gdf.index.isin(filtered.index)]
                unmatched_name = os.path.splitext(file)[0] + "_unmatched.geojson"
                unmatched_path = os.path.join(output_folder, unmatched_name)
                unmatched.to_file(unmatched_path, driver="GeoJSON")
                print(f"   ✔ Tạo file unmatched: {unmatched_name} ({len(unmatched)} line)")

        except Exception as e:
            print(f"   ❌ Lỗi xử lý file {file}: {e}")


# =======================================
#                 MAIN
# =======================================

if __name__ == "__main__":
    print("=== LỌC LINE NÂNG CAO THEO KEYWORD (CỘT name) ===")

    input_folder = input("Nhập thư mục chứa GeoJSON đã cắt line: ").strip()
    output_folder = input("Nhập thư mục xuất file đã lọc: ").strip()

    # ---- THIẾT LẬP KEYWORD TẠI ĐÂY ----
    prefix_keywords = ["Hẻm", "Ngõ"]  # lọc tên đường BẮT ĐẦU bằng...
    contain_keywords = []  # lọc theo từ chứa
    regex_pattern = None  # regex nâng cao, ví dụ r'^Hẻm\s+\d+'
    field_name = "name"  # <== QUAN TRỌNG

    batch_filter_lines(
        input_folder=input_folder,
        output_folder=output_folder,
        field_name=field_name,
        prefix_keywords=prefix_keywords,
        contain_keywords=contain_keywords,
        regex_pattern=regex_pattern,
        ignore_case=True,
        export_unmatched=False
    )

    print("\n🎉 Hoàn tất lọc line!")
