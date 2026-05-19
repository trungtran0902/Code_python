import os
import re
import unicodedata
import tkinter as tk
from tkinter import filedialog, messagebox

import geopandas as gpd
import pandas as pd


# =====================================================
# CẤU HÌNH
# =====================================================
# True: chỉ so sánh các line cao tốc highway = motorway nếu có cột highway
# False: so sánh toàn bộ line trong 2 file SHP
ONLY_MOTORWAY = True


# =====================================================
# HỘP THOẠI CHỌN FILE / FOLDER
# =====================================================

def choose_shp(title):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        title=title,
        filetypes=[
            ("Shapefile", "*.shp"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()
    return path


def choose_folder(title):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    folder = filedialog.askdirectory(title=title)

    root.destroy()
    return folder


# =====================================================
# HÀM XỬ LÝ CHUNG
# =====================================================

def text_value(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    s = str(value).strip()

    if s.upper() in ["NULL", "NONE", "NAN"]:
        return ""

    return s


def remove_accents(text):
    text = text_value(text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def norm_text(text):
    return remove_accents(text).casefold().strip()


def find_column(gdf, candidates):
    """Tìm cột không phân biệt hoa/thường, có/không dấu."""
    col_map = {norm_text(c): c for c in gdf.columns}

    for c in candidates:
        key = norm_text(c)
        if key in col_map:
            return col_map[key]

    return None


def remove_old_shapefile(shp_path):
    base = os.path.splitext(shp_path)[0]

    exts = [
        ".shp", ".shx", ".dbf", ".prj", ".cpg",
        ".qpj", ".sbn", ".sbx", ".fix"
    ]

    for ext in exts:
        path = base + ext
        if os.path.exists(path):
            os.remove(path)


def find_match_id_columns(old_gdf, new_gdf):
    """Tìm trường khóa để so sánh 2 bộ SHP. Ưu tiên osm_id."""
    candidates = [
        "osm_id",
        "osmid",
        "osm_id_1",
        "id",
        "fid",
    ]

    for c in candidates:
        old_col = find_column(old_gdf, [c])
        new_col = find_column(new_gdf, [c])

        if old_col and new_col:
            return old_col, new_col

    return None, None


# =====================================================
# ĐỌC BRIDGE TỪ CỘT bridge HOẶC other_tags
# =====================================================

def parse_bridge_series(series):
    """Đọc bridge từ other_tags dạng: \"bridge\"=>\"yes\"."""
    s = series.fillna("").astype(str)
    result = pd.Series("", index=s.index, dtype="object")

    patterns = [
        r'"bridge"\s*=>\s*"([^"]*)"',
        r"'bridge'\s*=>\s*'([^']*)'",
        r'bridge\s*=>\s*"?([^",;]+)"?',
    ]

    for pattern in patterns:
        mask = result.eq("")
        if not mask.any():
            break

        extracted = s.loc[mask].str.extract(pattern, flags=re.IGNORECASE, expand=False)
        extracted = extracted.fillna("").astype(str).str.strip().str.lower()
        result.loc[mask] = extracted

    return result.fillna("").astype(str).str.strip().str.lower()


def add_bridge_value_column(gdf):
    """Thêm cột nội bộ _brg để lưu giá trị bridge."""
    bridge_col = find_column(gdf, ["bridge"])
    other_tags_col = find_column(gdf, ["other_tags", "other_tag", "other_tags_"])

    if not bridge_col and not other_tags_col:
        raise ValueError("Không tìm thấy cột bridge hoặc other_tags trong SHP.")

    brg = pd.Series("", index=gdf.index, dtype="object")

    if bridge_col:
        brg = gdf[bridge_col].fillna("").astype(str).str.strip().str.lower()
        brg = brg.replace({"null": "", "none": "", "nan": ""})

    if other_tags_col:
        parsed = parse_bridge_series(gdf[other_tags_col])
        brg = brg.where(brg.ne(""), parsed)

    gdf["_brg"] = brg.fillna("").astype(str).str.strip().str.lower()
    return gdf


def summarize_bridge_by_id(work_gdf):
    """
    Gom theo ID.
    Nếu cùng osm_id có nhiều đoạn, chỉ cần 1 đoạn có bridge=yes thì xem ID đó là yes.
    Nếu không có yes thì lấy giá trị bridge đầu tiên khác rỗng.
    """
    temp = work_gdf[["_cmp_id", "_brg"]].copy()
    temp["_brg"] = temp["_brg"].fillna("").astype(str).str.strip().str.lower()

    all_ids = temp[["_cmp_id"]].drop_duplicates()

    yes_ids = temp.loc[temp["_brg"].eq("yes"), ["_cmp_id"]].drop_duplicates()
    yes_ids["brg_sum"] = "yes"

    non_empty = temp.loc[temp["_brg"].ne(""), ["_cmp_id", "_brg"]].drop_duplicates("_cmp_id")
    non_empty = non_empty.rename(columns={"_brg": "brg_sum"})

    out = all_ids.merge(yes_ids, on="_cmp_id", how="left")
    out = out.merge(non_empty, on="_cmp_id", how="left", suffixes=("_yes", "_first"))

    out["brg_sum"] = out["brg_sum_yes"].fillna(out["brg_sum_first"]).fillna("")
    return out[["_cmp_id", "brg_sum"]]


def classify_bridge_change(old_brg, new_brg):
    old_brg = text_value(old_brg).lower()
    new_brg = text_value(new_brg).lower()

    if old_brg == new_brg:
        return "NO_CHANGE"

    if old_brg == "yes" and new_brg != "yes":
        return "FIX_REMOVE"

    if old_brg != "yes" and new_brg == "yes":
        return "ADD_BRIDGE"

    return "CHANGED"


# =====================================================
# LỌC HIGHWAY=MOTORWAY NẾU CÓ CỘT HIGHWAY
# =====================================================

def filter_motorway_if_possible(gdf, label):
    if not ONLY_MOTORWAY:
        return gdf

    highway_col = find_column(gdf, ["highway"])
    if not highway_col:
        print(f"⚠️ {label}: Không có cột highway, bỏ qua bước lọc motorway.")
        return gdf

    before = len(gdf)
    gdf = gdf[gdf[highway_col].fillna("").astype(str).str.lower().eq("motorway")].copy()
    after = len(gdf)
    print(f"🛣️ {label}: lọc highway=motorway: {before} → {after} line")
    return gdf


# =====================================================
# TẠO LỚP CHỈ GỒM LINE THAY ĐỔI
# =====================================================

def build_changed_lines(old_work, new_work, changed_report):
    changed_ids = set(changed_report["_cmp_id"].astype(str))

    old_map = dict(zip(changed_report["_cmp_id"], changed_report["old_brg"]))
    new_map = dict(zip(changed_report["_cmp_id"], changed_report["new_brg"]))
    type_map = dict(zip(changed_report["_cmp_id"], changed_report["chg_type"]))

    # Ưu tiên lấy geometry từ bộ SAU FIX để dễ đối chiếu với file mới.
    new_lines = new_work[new_work["_cmp_id"].isin(changed_ids)].copy()
    new_lines["src_geom"] = "SAU_FIX"

    # Nếu ID thay đổi không còn tồn tại trong bộ sau fix, lấy geometry từ bộ TRƯỚC FIX.
    ids_already_from_new = set(new_lines["_cmp_id"].astype(str))
    old_only_ids = changed_ids - ids_already_from_new

    old_lines = old_work[old_work["_cmp_id"].isin(old_only_ids)].copy()
    old_lines["src_geom"] = "TRUOC_FIX"

    if len(new_lines) == 0 and len(old_lines) == 0:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=new_work.crs or old_work.crs)

    changed_lines = pd.concat([new_lines, old_lines], ignore_index=True)
    changed_lines = gpd.GeoDataFrame(changed_lines, geometry="geometry", crs=new_work.crs or old_work.crs)

    changed_lines["cmp_id"] = changed_lines["_cmp_id"].astype(str)
    changed_lines["old_brg"] = changed_lines["_cmp_id"].map(old_map).fillna("")
    changed_lines["new_brg"] = changed_lines["_cmp_id"].map(new_map).fillna("")
    changed_lines["chg_type"] = changed_lines["_cmp_id"].map(type_map).fillna("")

    # Chỉ giữ các cột cần nhìn trong QGIS cho dễ ánh xạ.
    keep_cols = ["cmp_id", "old_brg", "new_brg", "chg_type", "src_geom"]

    name_col = find_column(changed_lines, ["name"])
    highway_col = find_column(changed_lines, ["highway"])

    if name_col and name_col not in keep_cols:
        changed_lines["name"] = changed_lines[name_col]
        keep_cols.append("name")

    if highway_col and highway_col not in keep_cols:
        changed_lines["highway"] = changed_lines[highway_col]
        keep_cols.append("highway")

    keep_cols.append("geometry")
    changed_lines = changed_lines[keep_cols].copy()

    return changed_lines


def save_changed_shp(gdf, output_shp):
    remove_old_shapefile(output_shp)

    if gdf.empty:
        print("⚠️ Không có line thay đổi để xuất SHP.")
        return False

    gdf.to_file(
        output_shp,
        driver="ESRI Shapefile",
        encoding="UTF-8"
    )

    return True


# =====================================================
# CHỨC NĂNG CHÍNH
# =====================================================

def compare_two_shp_bridge_only_changed():
    print("=== SO SÁNH 2 BỘ SHP - CHỈ XUẤT LINE CÓ BRIDGE THAY ĐỔI ===\n")

    old_shp = choose_shp("B1 - Chọn bộ SHP TRƯỚC khi fix")
    if not old_shp:
        print("❌ Chưa chọn SHP trước khi fix.")
        return

    new_shp = choose_shp("B2 - Chọn bộ SHP SAU khi fix")
    if not new_shp:
        print("❌ Chưa chọn SHP sau khi fix.")
        return

    output_folder = choose_folder("B3 - Chọn thư mục xuất SHP line thay đổi")
    if not output_folder:
        print("❌ Chưa chọn thư mục xuất.")
        return

    print(f"✅ SHP trước fix:\n{old_shp}")
    print(f"\n✅ SHP sau fix:\n{new_shp}")
    print(f"\n✅ Thư mục xuất:\n{output_folder}")

    print("\n📖 Đang đọc SHP trước fix...")
    old_gdf = gpd.read_file(old_shp)
    print(f"   → {len(old_gdf)} line")

    print("📖 Đang đọc SHP sau fix...")
    new_gdf = gpd.read_file(new_shp)
    print(f"   → {len(new_gdf)} line")

    # Nếu CRS khác nhau thì đưa old về CRS của new để xuất chung 1 lớp.
    if old_gdf.crs and new_gdf.crs and old_gdf.crs != new_gdf.crs:
        print("🔁 CRS khác nhau, đang chuyển SHP trước fix về CRS của SHP sau fix...")
        old_gdf = old_gdf.to_crs(new_gdf.crs)

    old_gdf = filter_motorway_if_possible(old_gdf, "SHP trước fix")
    new_gdf = filter_motorway_if_possible(new_gdf, "SHP sau fix")

    old_id_col, new_id_col = find_match_id_columns(old_gdf, new_gdf)

    if not old_id_col or not new_id_col:
        print("\n❌ Không tìm thấy trường khóa để so sánh.")
        print("Cần có một trong các trường sau trong cả 2 bộ SHP:")
        print("osm_id, osmid, osm_id_1, id, fid")
        return

    print("\n🔑 Trường dùng để so sánh:")
    print(f"  - SHP trước fix: {old_id_col}")
    print(f"  - SHP sau fix:   {new_id_col}")

    old_work = old_gdf.copy()
    new_work = new_gdf.copy()

    old_work["_cmp_id"] = old_work[old_id_col].apply(text_value)
    new_work["_cmp_id"] = new_work[new_id_col].apply(text_value)

    old_work = old_work[old_work["_cmp_id"] != ""].copy()
    new_work = new_work[new_work["_cmp_id"] != ""].copy()

    print("\n🌉 Đang đọc giá trị bridge từ bridge/other_tags...")
    old_work = add_bridge_value_column(old_work)
    new_work = add_bridge_value_column(new_work)

    print("🔎 Đang gom theo ID và so sánh...")
    old_group = summarize_bridge_by_id(old_work).rename(columns={"brg_sum": "old_brg"})
    new_group = summarize_bridge_by_id(new_work).rename(columns={"brg_sum": "new_brg"})

    report = old_group.merge(new_group, on="_cmp_id", how="outer")
    report["old_brg"] = report["old_brg"].fillna("")
    report["new_brg"] = report["new_brg"].fillna("")

    report["chg_type"] = report.apply(
        lambda row: classify_bridge_change(row["old_brg"], row["new_brg"]),
        axis=1
    )

    changed_report = report[report["chg_type"] != "NO_CHANGE"].copy()

    print("🧩 Đang tạo lớp line thay đổi...")
    changed_lines = build_changed_lines(old_work, new_work, changed_report)

    base_name = os.path.splitext(os.path.basename(new_shp))[0]
    output_shp = os.path.join(output_folder, f"{base_name}_ONLY_bridge_changed_lines.shp")

    ok = save_changed_shp(changed_lines, output_shp)

    print("\n✅ HOÀN TẤT SO SÁNH!")
    print("\n📊 Thống kê:")
    print(f"  - Tổng line trước fix sau lọc: {len(old_work)}")
    print(f"  - Tổng line sau fix sau lọc:   {len(new_work)}")
    print(f"  - Số ID có bridge thay đổi:    {len(changed_report)}")
    print(f"  - Số line xuất ra SHP:         {len(changed_lines)}")

    if ok:
        print(f"\n📄 SHP chỉ gồm các line thay đổi:\n{output_shp}")
    else:
        print("\n⚠️ Không tạo SHP vì không có line thay đổi.")

    print("\n📌 Cột trong SHP đầu ra:")
    print("  - cmp_id   : ID dùng để ánh xạ")
    print("  - old_brg  : bridge trước fix")
    print("  - new_brg  : bridge sau fix")
    print("  - chg_type : loại thay đổi")
    print("  - src_geom : geometry lấy từ SAU_FIX hoặc TRUOC_FIX")

    if ok:
        messagebox.showinfo(
            "Hoàn tất so sánh",
            "Đã so sánh xong!\n\n"
            f"Số line thay đổi xuất ra SHP: {len(changed_lines)}\n\n"
            f"SHP kết quả:\n{output_shp}"
        )
    else:
        messagebox.showinfo(
            "Hoàn tất so sánh",
            "Không phát hiện line có thuộc tính bridge thay đổi."
        )


if __name__ == "__main__":
    try:
        compare_two_shp_bridge_only_changed()
    except Exception as e:
        print("\n❌ Lỗi:")
        print(e)

        try:
            messagebox.showerror("Lỗi", str(e))
        except Exception:
            pass
