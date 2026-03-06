import pandas as pd
import re
import os
from tkinter import Tk, filedialog

# ---------------- Chọn file ----------------
root = Tk()
root.withdraw()
file_path = filedialog.askopenfilename(
    title="Chọn file cần fix",
    filetypes=[("Excel files", "*.xlsx *.xls")]
)

if not file_path:
    print("Không chọn file, thoát.")
    exit()

# ---------------- Đọc file ----------------
df = pd.read_excel(file_path)

# Lấy các cột merchant_name*
merchant_cols = [c for c in df.columns if c.lower().startswith("merchant_name")]

EXCLUDE = {
    "PAYOO", "VNPAY", "ZALOPAY",
    "MPOS.VN", "MPOS", "MPOS.VN (MPOS)"
}

# Brand chỉ cắt mã kiểu "HIGHLANDS00266"
BRANCH_BRANDS = ["HIGHLANDS"]

# Brand có dạng "BRAND + địa danh/mô tả"
LOCATION_BRANDS = [
    "MMVN",
    "AEON",
    "AEON MALL",
    "LOTTE MART",
    "CO.OP MART",
    "CO.OPMART",
    "K-MARKET"
]

# ---------------- Clean giá trị ----------------
def clean_value(val):
    if pd.isna(val):
        return None
    val = str(val).strip()

    # Chuẩn hóa riêng cho MPOS.VN (MPOS)
    if re.fullmatch(r"MPOS\.VN\s*\(MPOS\)", val, re.IGNORECASE):
        return "MPOS.VN (MPOS)"

    # Cắt tiền tố trung gian: PAYOO, VNPAY, ZALOPAY, MPOS, MPOS.VN
    m = re.match(r"^(PAYOO|VNPAY|ZALOPAY|MPOS\.VN|MPOS)[-_](.+)$", val, re.IGNORECASE)
    if m:
        val = m.group(2).strip()

    m = re.match(r"^(PAYOO|VNPAY|ZALOPAY|MPOS\.VN|MPOS)\*(.+)$", val, re.IGNORECASE)
    if m:
        val = m.group(2).strip()

    # Chuẩn hóa khoảng trắng
    val = re.sub(r"\s+", " ", val)
    upper = val.upper()

    # Cắt mã chi nhánh dạng số dính brand
    for b in BRANCH_BRANDS:
        if upper.startswith(b.upper()):
            val = re.sub(rf"^{re.escape(b)}\s+[A-Z0-9]+$", b, val, flags=re.IGNORECASE)
            val = re.sub(rf"^{re.escape(b)}[A-Z0-9]+$", b, val, flags=re.IGNORECASE)

    return val

def is_location_variant(value: str, brand: str) -> bool:
    if not value:
        return False
    v = value.strip()
    pattern = rf"^{re.escape(brand)}(\s+|-|\s*-\s*).+"
    return re.match(pattern, v, flags=re.IGNORECASE) is not None

# ---------------- Tìm trùng ----------------
def find_duplicate(row):
    raw_vals = row[merchant_cols].dropna()
    if raw_vals.empty:
        return ""

    cleaned = raw_vals.apply(clean_value).dropna()
    if cleaned.empty:
        return ""

    norm = cleaned.str.strip().str.upper()

    # Loại trung gian
    mask = ~norm.isin(EXCLUDE)
    cleaned = cleaned[mask]
    norm = norm[mask]

    if cleaned.empty:
        return ""

    # Ưu tiên chi nhánh cụ thể
    location_candidates = []
    for brand in LOCATION_BRANDS:
        for v in cleaned.tolist():
            if is_location_variant(v, brand):
                location_candidates.append(v)

    if location_candidates:
        location_candidates.sort(key=lambda s: len(str(s)), reverse=True)
        return location_candidates[0]

    # Fallback: đếm trùng
    counts = norm.value_counts()
    duplicates = counts[counts >= 2]
    if not duplicates.empty:
        top_norm = duplicates.idxmax()
        return cleaned[norm == top_norm].iloc[0]

    return ""

# ---------------- Áp dụng ----------------
df["duplicate_merchant"] = df.apply(find_duplicate, axis=1)

# ---------------- Lưu file ----------------
base, ext = os.path.splitext(file_path)
output_path = base + "_output" + ext
df.to_excel(output_path, index=False)

print("Đã xử lý xong.")
print("File lưu tại:", output_path)
