import json
import os
import unicodedata
import pandas as pd


# =========================
#  HÀM CHUẨN HOÁ TEXT
# =========================
def normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")


# =========================
#  ĐỌC ĐẶC TẢ CSDL
# =========================
def load_specification(excel_file: str):
    df = pd.read_excel(excel_file)

    entries = []         # Danh sách giá trị phân loại
    group_fields = {}    # Danh sách field theo từng nhóm

    current_group = None
    current_field = None

    for _, row in df.iterrows():
        group_cell = row.get("Unnamed: 1", None)
        field_cell = row.get("Unnamed: 3", None)
        code = row.get("Unnamed: 6", None)
        label = row.get("Unnamed: 7", None)

        # Nhóm lớp đối tượng
        if isinstance(group_cell, str):
            current_group = group_cell.strip()
            if current_group not in group_fields:
                group_fields[current_group] = []

        # Field trong nhóm
        if isinstance(field_cell, str):
            current_field = field_cell.strip()
            if current_field not in group_fields[current_group]:
                group_fields[current_group].append(current_field)

        # Nếu có mã + nhãn → đây là 1 entry phân loại
        if current_group and current_field and pd.notna(code) and pd.notna(label):
            entries.append({
                "group": current_group,
                "field": current_field,
                "code": str(code).strip(),
                "label": str(label).strip(),
                "norm_label": normalize(str(label)),
                "order": len(entries)
            })

    # Sort theo độ dài từ khoá để match chính xác
    entries_sorted = sorted(entries, key=lambda e: -len(e["norm_label"]))

    return entries_sorted, group_fields


# =========================
#  MATCH KEYWORD
# =========================
def classify_point(name: str, spec_entries):
    norm_name = normalize(name)

    for entry in spec_entries:
        if entry["norm_label"] and entry["norm_label"] in norm_name:
            return entry

    return None


# =========================
#  XOÁ TRÙNG NAME
# =========================
def remove_duplicate_points(features):
    seen = set()
    result = []

    for f in features:
        name = f.get("properties", {}).get("name", "")
        key = normalize(name)

        if key:
            if key in seen:
                continue
            seen.add(key)

        result.append(f)

    return result


# =========================
#  MAIN PROCESS
# =========================
def main():
    print("=== PHÂN LOẠI GEOJSON THEO ĐẶC TẢ + TÁCH FILE + THỐNG KÊ ===\n")

    # INPUT GEOJSON
    geo_dir = input("Nhập đường dẫn chứa file GEOJSON: ").strip()
    geo_name = input("Nhập tên file GEOJSON: ").strip()
    geo_path = os.path.join(geo_dir, geo_name)

    # INPUT ĐẶC TẢ
    spec_dir = input("\nNhập đường dẫn chứa file Đặc tả CSDL: ").strip()
    spec_name = input("Nhập tên file Đặc tả CSDL: ").strip()
    spec_path = os.path.join(spec_dir, spec_name)

    # OUTPUT DIR
    out_dir = input("\nNhập đường dẫn thư mục đầu ra: ").strip()
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # LOAD DATA
    print("\n📥 Đang đọc dữ liệu ...")
    with open(geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    spec_entries, group_fields = load_specification(spec_path)

    print(f"➡ Số dòng phân loại đọc được: {len(spec_entries)}")
    print(f"➡ Số nhóm lớp đối tượng: {len(group_fields)}")

    # REMOVE DUPLICATE
    print("\n🧹 Đang loại point trùng ...")
    features = remove_duplicate_points(geo["features"])

    print(f"➡ Số point sau khi loại trùng: {len(features)}")

    # CLASSIFY
    print("\n🏷 Đang phân loại point ...")
    classified = []

    for f in features:
        props = f.setdefault("properties", {})
        name_goc = props.get("name", "").strip()

        entry = classify_point(name_goc, spec_entries)
        if entry is None:
            continue

        group = entry["group"]
        field = entry["field"]

        # Thêm nhóm lớp
        props["nhomLop"] = group

        # Thêm các field thuộc nhóm (không match → null)
        for fld in group_fields[group]:
            props[fld] = None

        # Field match từ keyword
        props[field] = entry["code"]

        # Thêm loaiDoiTuong
        props["loaiDoiTuong"] = entry["label"]

        # Thêm cột `ten`
        label = entry["label"]
        props["ten"] = f"{label} {name_goc}".strip()

        # Order để sort
        props["_order"] = entry["order"]

        classified.append(f)

    print(f"➡ Tổng số point được phân loại: {len(classified)}")

    # SORT
    classified_sorted = sorted(
        classified,
        key=lambda f: (
            f["properties"].get("_order", 999999),
            f["properties"].get("name", "")
        )
    )

    # TÁCH FILE THEO NHÓM
    print("\n📤 Đang tách file theo từng nhóm lớp ...")

    group_map = {}
    for f in classified_sorted:
        group = f["properties"]["nhomLop"]
        group_map.setdefault(group, []).append(f)

    for group, feats in group_map.items():
        out_geo = {"type": "FeatureCollection", "features": feats}
        out_path = os.path.join(out_dir, f"{group}.geojson")

        with open(out_path, "w", encoding="utf-8") as fo:
            json.dump(out_geo, fo, ensure_ascii=False, indent=4)

        print(f"   ✔ {group}: {len(feats)} point")

    # FILE THỐNG KÊ
    print("\n📊 Đang tạo file thống kê ...")

    stats = []
    for f in classified_sorted:
        p = f["properties"]
        stats.append({
            "nhomLop": p["nhomLop"],
            "maDoiTuong": p.get("maDoiTuong", None),
            "loaiDoiTuong": p.get("loaiDoiTuong", None)
        })

    df_stats = pd.DataFrame(stats)
    df_stats = df_stats.groupby(
        ["nhomLop", "maDoiTuong", "loaiDoiTuong"]
    ).size().reset_index(name="SoLuong")

    stats_file = os.path.join(out_dir, "Thêm thống kê.xlsx")
    df_stats.to_excel(stats_file, index=False)

    print(f"➡ Đã tạo file thống kê: {stats_file}")

    print("\n🎉 HOÀN TẤT!")


if __name__ == "__main__":
    main()
