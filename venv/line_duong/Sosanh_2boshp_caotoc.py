import os
import re
import time
import unicodedata
import tkinter as tk
from tkinter import filedialog, messagebox

import geopandas as gpd
import pandas as pd


# ============================================================
# TOOL SO SÁNH 2 BỘ SHP CAO TỐC THEO THUỘC TÍNH BRIDGE
# Bản FAST + DEBUG:
# - Có log tiến trình để biết đang chạy tới bước nào
# - Lọc highway = motorway trước khi so sánh nếu có cột highway
# - Đọc bridge bằng xử lý vector hóa, nhanh hơn apply từng dòng
# - Gom theo osm_id nhưng ưu tiên bridge=yes, không lấy .first()
# - Nếu line đã fix bị mất khỏi bộ SAU FIX, vẫn xuất geometry từ bộ TRƯỚC FIX
# ============================================================

ID_CANDIDATES = ["osm_id", "osmid", "osm_id_1", "id", "fid"]
OTHER_TAGS_CANDIDATES = ["other_tags", "other_tag", "other_tags_", "other_ta"]
BRIDGE_CANDIDATES = ["bridge"]
HIGHWAY_CANDIDATES = ["highway"]


# =========================
# LOG
# =========================

def log(msg=""):
    print(msg, flush=True)


class StepTimer:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.last = self.t0

    def mark(self, msg):
        now = time.perf_counter()
        log(f"⏱️ {msg} | bước: {now - self.last:.1f}s | tổng: {now - self.t0:.1f}s")
        self.last = now


# =========================
# HỘP THOẠI CHỌN FILE / FOLDER
# =========================

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


# =========================
# HÀM XỬ LÝ CHUNG
# =========================

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


def find_column_from_list(columns, candidates):
    """
    Tìm cột không phân biệt hoa/thường, có/không dấu.
    """
    col_map = {norm_text(c): c for c in columns}

    for c in candidates:
        key = norm_text(c)
        if key in col_map:
            return col_map[key]

    return None


def find_column(gdf, candidates):
    return find_column_from_list(gdf.columns, candidates)


def list_shp_attribute_columns(shp_path):
    """
    Đọc nhanh danh sách cột thuộc tính, chưa đọc geometry.
    """
    try:
        import fiona
        with fiona.open(shp_path) as src:
            return list(src.schema.get("properties", {}).keys())
    except Exception:
        pass

    # Fallback: đọc 1 dòng để lấy metadata.
    try:
        tmp = gpd.read_file(shp_path, rows=1)
        return [c for c in tmp.columns if c != tmp.geometry.name]
    except Exception:
        return []


def select_needed_columns(shp_path):
    """
    Chỉ đọc các cột cần thiết để tăng tốc.
    Geometry vẫn được đọc để xuất kết quả.
    """
    columns = list_shp_attribute_columns(shp_path)

    if not columns:
        return None

    needed = set()

    for c in ID_CANDIDATES:
        found = find_column_from_list(columns, [c])
        if found:
            needed.add(found)

    for group in [HIGHWAY_CANDIDATES, BRIDGE_CANDIDATES, OTHER_TAGS_CANDIDATES]:
        found = find_column_from_list(columns, group)
        if found:
            needed.add(found)

    # Giữ thêm name để dễ kiểm tra khi mở bảng thuộc tính kết quả.
    name_col = find_column_from_list(columns, ["name"])
    if name_col:
        needed.add(name_col)

    return list(needed) if needed else None


def read_shp_fast(shp_path, label):
    """
    Đọc SHP với log rõ ràng. Nếu có cột highway, cố gắng lọc highway='motorway' ngay lúc đọc.
    Nếu môi trường không hỗ trợ where/columns thì tự fallback.
    """
    log(f"\n📥 Đang đọc {label}...")
    log(f"   {shp_path}")

    cols = select_needed_columns(shp_path)
    highway_col = None

    if cols:
        highway_col = find_column_from_list(cols, HIGHWAY_CANDIDATES)
        log(f"   Cột sẽ đọc: {', '.join(cols)}")
    else:
        log("   Không đọc được metadata cột, sẽ đọc toàn bộ SHP.")

    where_expr = None
    if highway_col:
        where_expr = f'"{highway_col}" = \'motorway\''
        log(f"   Thử lọc ngay khi đọc: {where_expr}")

    # Cách nhanh nhất: đọc theo cột + where.
    if cols and where_expr:
        try:
            gdf = gpd.read_file(shp_path, columns=cols, where=where_expr)
            log(f"   ✅ Đọc xong bằng columns + where. Số dòng: {len(gdf):,}")
            return gdf
        except TypeError:
            log("   ⚠️ Môi trường geopandas không hỗ trợ columns/where, fallback đọc thường.")
        except Exception as e:
            log(f"   ⚠️ Không lọc được bằng where khi đọc: {e}")

    # Fallback: chỉ đọc cột cần thiết.
    if cols:
        try:
            gdf = gpd.read_file(shp_path, columns=cols)
            log(f"   ✅ Đọc xong bằng columns. Số dòng trước lọc: {len(gdf):,}")
        except TypeError:
            log("   ⚠️ Môi trường geopandas không hỗ trợ columns, đọc toàn bộ SHP.")
            gdf = gpd.read_file(shp_path)
            log(f"   ✅ Đọc xong toàn bộ. Số dòng trước lọc: {len(gdf):,}")
        except Exception as e:
            log(f"   ⚠️ Không đọc được bằng columns: {e}")
            gdf = gpd.read_file(shp_path)
            log(f"   ✅ Đọc xong toàn bộ. Số dòng trước lọc: {len(gdf):,}")
    else:
        gdf = gpd.read_file(shp_path)
        log(f"   ✅ Đọc xong toàn bộ. Số dòng trước lọc: {len(gdf):,}")

    # Lọc highway=motorway sau khi đọc nếu có cột highway.
    highway_col = find_column(gdf, HIGHWAY_CANDIDATES)
    if highway_col:
        before = len(gdf)
        hw = gdf[highway_col].fillna("").astype(str).str.strip().str.casefold()
        gdf = gdf[hw.eq("motorway")].copy()
        log(f"   ✅ Đã lọc highway=motorway: {before:,} -> {len(gdf):,} dòng")
    else:
        log("   ⚠️ Không có cột highway, giữ nguyên toàn bộ dòng để so sánh.")

    return gdf


def normalize_str_series(series):
    s = series.fillna("").astype(str).str.strip()
    s = s.mask(s.str.upper().isin(["NULL", "NONE", "NAN"]), "")
    return s


def add_bridge_value_column_fast(gdf):
    """
    Thêm cột nội bộ _brg để lưu giá trị bridge.
    Nhanh hơn bản cũ vì không dùng gdf.apply từng dòng.
    """
    bridge_col = find_column(gdf, BRIDGE_CANDIDATES)
    other_tags_col = find_column(gdf, OTHER_TAGS_CANDIDATES)

    if not bridge_col and not other_tags_col:
        raise ValueError("Không tìm thấy cột bridge hoặc other_tags trong SHP.")

    brg = pd.Series([""] * len(gdf), index=gdf.index, dtype="object")

    if bridge_col:
        brg = normalize_str_series(gdf[bridge_col]).str.lower()

    if other_tags_col:
        tags = normalize_str_series(gdf[other_tags_col])

        # Bắt các kiểu phổ biến:
        # "bridge"=>"yes"
        # 'bridge'=>'yes'
        # bridge=>yes
        extracted = tags.str.extract(
            r'["\']?bridge["\']?\s*=>\s*["\']?([^"\',;]+)',
            flags=re.IGNORECASE,
            expand=False,
        )
        extracted = extracted.fillna("").astype(str).str.strip().str.lower()

        # Nếu cột bridge rỗng thì lấy từ other_tags.
        brg = brg.mask(brg.eq(""), extracted)

    gdf["_brg"] = brg.fillna("")
    return gdf


def find_match_id_columns(old_gdf, new_gdf):
    """
    Tìm trường khóa để so sánh 2 bộ SHP. Ưu tiên osm_id.
    """
    for c in ID_CANDIDATES:
        old_col = find_column(old_gdf, [c])
        new_col = find_column(new_gdf, [c])

        if old_col and new_col:
            return old_col, new_col

    return None, None


def aggregate_bridge(values):
    """
    Một osm_id có thể bị tách thành nhiều đoạn line.
    Ưu tiên yes nếu bất kỳ đoạn nào có bridge=yes.
    """
    vals = [text_value(v).lower() for v in values]
    vals = [v for v in vals if v]

    if not vals:
        return ""

    if "yes" in vals:
        return "yes"

    # Nếu không có yes thì trả giá trị đầu tiên khác rỗng.
    return vals[0]


def classify_bridge_change(old_brg, new_brg):
    old_brg = text_value(old_brg).lower()
    new_brg = text_value(new_brg).lower()

    if old_brg == new_brg:
        return "NO_CHANGE"

    if old_brg == "yes" and new_brg != "yes":
        return "FIX_REMOVE"

    if old_brg != "yes" and new_brg == "yes":
        return "ADD_BRIDGE"

    if old_brg and not new_brg:
        return "REMOVED_OBJECT_OR_TAG"

    if not old_brg and new_brg:
        return "ADDED_OBJECT_OR_TAG"

    return "CHANGED"


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


def save_shp(gdf, output_shp):
    remove_old_shapefile(output_shp)

    if gdf.empty:
        log("⚠️ Không có đối tượng nào để xuất SHP.")
        return False

    # Tránh lỗi kiểu dữ liệu phức tạp khi ghi Shapefile.
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        if pd.api.types.is_object_dtype(gdf[col]):
            gdf[col] = gdf[col].fillna("").astype(str)

    gdf.to_file(
        output_shp,
        driver="ESRI Shapefile",
        encoding="UTF-8"
    )

    return True


def clean_output_columns(gdf):
    """
    Xóa cột nội bộ, giữ lại các cột kết quả cần thiết.
    """
    drop_cols = [c for c in gdf.columns if c.startswith("_")]
    return gdf.drop(columns=drop_cols, errors="ignore")


# =========================
# CHỨC NĂNG CHÍNH
# =========================

def compare_two_shp_bridge():
    timer = StepTimer()

    log("=== SO SÁNH 2 BỘ SHP CAO TỐC THEO THUỘC TÍNH CẦU ===\n")

    old_shp = choose_shp("B1 - Chọn bộ SHP TRƯỚC khi fix")
    if not old_shp:
        log("❌ Chưa chọn SHP trước khi fix.")
        return

    new_shp = choose_shp("B2 - Chọn bộ SHP SAU khi fix")
    if not new_shp:
        log("❌ Chưa chọn SHP sau khi fix.")
        return

    output_folder = choose_folder("B3 - Chọn thư mục xuất kết quả so sánh")
    if not output_folder:
        log("❌ Chưa chọn thư mục xuất.")
        return

    log(f"✅ SHP trước fix:\n{old_shp}")
    log(f"\n✅ SHP sau fix:\n{new_shp}")
    log(f"\n✅ Thư mục xuất:\n{output_folder}")

    timer.mark("Đã chọn xong file/folder")

    old_gdf = read_shp_fast(old_shp, "SHP TRƯỚC FIX")
    timer.mark("Đọc xong SHP trước fix")

    new_gdf = read_shp_fast(new_shp, "SHP SAU FIX")
    timer.mark("Đọc xong SHP sau fix")

    old_id_col, new_id_col = find_match_id_columns(old_gdf, new_gdf)

    if not old_id_col or not new_id_col:
        log("\n❌ Không tìm thấy trường khóa để so sánh.")
        log("Cần có một trong các trường sau trong cả 2 bộ SHP:")
        log(", ".join(ID_CANDIDATES))
        return

    log("\n🔑 Trường dùng để so sánh:")
    log(f"  - SHP trước fix: {old_id_col}")
    log(f"  - SHP sau fix:   {new_id_col}")

    old_work = old_gdf.copy()
    new_work = new_gdf.copy()

    old_work["_cmp_id"] = old_work[old_id_col].apply(text_value)
    new_work["_cmp_id"] = new_work[new_id_col].apply(text_value)

    before_old = len(old_work)
    before_new = len(new_work)
    old_work = old_work[old_work["_cmp_id"] != ""].copy()
    new_work = new_work[new_work["_cmp_id"] != ""].copy()

    log(f"\n🧹 Bỏ dòng không có ID:")
    log(f"  - Trước fix: {before_old:,} -> {len(old_work):,}")
    log(f"  - Sau fix:   {before_new:,} -> {len(new_work):,}")

    old_work = add_bridge_value_column_fast(old_work)
    new_work = add_bridge_value_column_fast(new_work)
    timer.mark("Đọc xong bridge từ bridge/other_tags")

    log("\n🌉 Thống kê bridge sau khi đọc:")
    log("  - Trước fix:")
    log(old_work["_brg"].value_counts(dropna=False).head(10).to_string())
    log("  - Sau fix:")
    log(new_work["_brg"].value_counts(dropna=False).head(10).to_string())

    # Gom theo ID, ưu tiên yes.
    old_group = (
        old_work
        .groupby("_cmp_id", dropna=False)["_brg"]
        .agg(aggregate_bridge)
        .reset_index()
        .rename(columns={"_brg": "old_brg"})
    )

    new_group = (
        new_work
        .groupby("_cmp_id", dropna=False)["_brg"]
        .agg(aggregate_bridge)
        .reset_index()
        .rename(columns={"_brg": "new_brg"})
    )

    timer.mark("Gom nhóm theo ID xong")

    report = old_group.merge(
        new_group,
        on="_cmp_id",
        how="outer"
    )

    report["old_brg"] = report["old_brg"].fillna("")
    report["new_brg"] = report["new_brg"].fillna("")

    report["chg_type"] = report.apply(
        lambda row: classify_bridge_change(row["old_brg"], row["new_brg"]),
        axis=1
    )

    changed_report = report[report["chg_type"] != "NO_CHANGE"].copy()
    changed_ids = set(changed_report["_cmp_id"].astype(str))

    log("\n📊 Thống kê loại thay đổi:")
    if report.empty:
        log("  Không có ID nào để so sánh.")
    else:
        log(report["chg_type"].value_counts(dropna=False).to_string())

    old_map = dict(zip(report["_cmp_id"], report["old_brg"]))
    new_map = dict(zip(report["_cmp_id"], report["new_brg"]))
    type_map = dict(zip(report["_cmp_id"], report["chg_type"]))

    # Ưu tiên xuất geometry từ bộ SAU FIX.
    changed_lines_new = new_work[new_work["_cmp_id"].isin(changed_ids)].copy()
    changed_lines_new["src_geom"] = "SAU_FIX"

    # Nếu ID thay đổi không còn trong bộ SAU FIX, lấy geometry từ bộ TRƯỚC FIX.
    ids_in_new = set(changed_lines_new["_cmp_id"].astype(str))
    missing_in_new_ids = changed_ids - ids_in_new

    changed_lines_old_missing = old_work[old_work["_cmp_id"].isin(missing_in_new_ids)].copy()
    changed_lines_old_missing["src_geom"] = "TRUOC_FIX"

    changed_lines = pd.concat(
        [changed_lines_new, changed_lines_old_missing],
        ignore_index=True
    )

    if not changed_lines.empty:
        changed_lines["cmp_id"] = changed_lines["_cmp_id"]
        changed_lines["old_brg"] = changed_lines["_cmp_id"].map(old_map)
        changed_lines["new_brg"] = changed_lines["_cmp_id"].map(new_map)
        changed_lines["chg_type"] = changed_lines["_cmp_id"].map(type_map)
        changed_lines = clean_output_columns(changed_lines)

    timer.mark("Tạo layer kết quả xong")

    base_name = os.path.splitext(os.path.basename(new_shp))[0]

    output_shp = os.path.join(
        output_folder,
        f"{base_name}_bridge_changed_lines.shp"
    )

    changed_csv_path = os.path.join(
        output_folder,
        f"{base_name}_bridge_changed_report.csv"
    )

    all_csv_path = os.path.join(
        output_folder,
        f"{base_name}_bridge_all_report.csv"
    )

    changed_report.rename(columns={"_cmp_id": "cmp_id"}).to_csv(
        changed_csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    report.rename(columns={"_cmp_id": "cmp_id"}).to_csv(
        all_csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    shp_saved = save_shp(changed_lines, output_shp)
    timer.mark("Ghi file kết quả xong")

    log("\n✅ HOÀN TẤT SO SÁNH!")
    if shp_saved:
        log(f"📄 SHP line có thuộc tính cầu thay đổi:\n{output_shp}")
    else:
        log("📄 Không ghi SHP vì không có line thay đổi.")

    log(f"\n📄 Báo cáo thay đổi CSV:\n{changed_csv_path}")
    log(f"\n📄 Báo cáo toàn bộ CSV:\n{all_csv_path}")

    log("\n📊 Thống kê:")
    log(f"  - Tổng line cao tốc bộ trước fix: {len(old_gdf):,}")
    log(f"  - Tổng line cao tốc bộ sau fix:   {len(new_gdf):,}")
    log(f"  - Số ID có bridge thay đổi:        {len(changed_report):,}")
    log(f"  - Số line xuất ra:                 {len(changed_lines):,}")
    log(f"  - Số ID lấy geometry từ trước fix vì không còn ở sau fix: {len(missing_in_new_ids):,}")

    log("\n📌 Ý nghĩa chg_type:")
    log("  - FIX_REMOVE          : trước là bridge=yes, sau không còn bridge=yes")
    log("  - ADD_BRIDGE          : trước không phải bridge=yes, sau thành bridge=yes")
    log("  - REMOVED_OBJECT_OR_TAG: trước có giá trị bridge, sau không còn object hoặc tag")
    log("  - ADDED_OBJECT_OR_TAG : trước không có, sau mới có object hoặc tag")
    log("  - CHANGED             : giá trị bridge thay đổi khác")

    messagebox.showinfo(
        "Hoàn tất so sánh",
        "Đã so sánh xong!\n\n"
        f"Số ID có bridge thay đổi: {len(changed_report)}\n"
        f"Số line xuất ra: {len(changed_lines)}\n\n"
        f"SHP kết quả:\n{output_shp if shp_saved else 'Không có line thay đổi để xuất SHP'}\n\n"
        f"CSV thay đổi:\n{changed_csv_path}\n\n"
        f"CSV toàn bộ:\n{all_csv_path}"
    )


if __name__ == "__main__":
    try:
        compare_two_shp_bridge()
    except KeyboardInterrupt:
        log("\n⛔ Đã dừng bằng Ctrl+C.")
    except Exception as e:
        log("\n❌ Lỗi:")
        log(str(e))

        try:
            messagebox.showerror("Lỗi", str(e))
        except Exception:
            pass
