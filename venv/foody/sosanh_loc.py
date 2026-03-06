import pandas as pd
import tkinter as tk
from tkinter import filedialog
from unidecode import unidecode
from rapidfuzz import fuzz
from geopy.distance import geodesic
import math

# =====================
# CONFIG
# =====================
NAME_FUZZY_THRESHOLD = 90       # tên quán giống
ADDRESS_TEXT_THRESHOLD = 90     # địa chỉ text giống
ADDRESS_DISTANCE_M = 30         # mét coi là gần nhau

# =====================
# FILE DIALOG
# =====================
root = tk.Tk()
root.withdraw()

input_file = filedialog.askopenfilename(
    title="Chọn file Excel đầu vào",
    filetypes=[("Excel files", "*.xlsx *.xls")]
)
if not input_file:
    raise SystemExit("❌ Không chọn file input")

output_file = filedialog.asksaveasfilename(
    title="Lưu file kết quả",
    defaultextension=".xlsx",
    filetypes=[("Excel files", "*.xlsx")]
)
if not output_file:
    raise SystemExit("❌ Không chọn file output")

# =====================
# LOAD DATA
# =====================
df = pd.read_excel(input_file)
df.columns = df.columns.str.strip()

# =====================
# HELPERS
# =====================
def normalize_text(text):
    if pd.isna(text):
        return ""
    text = unidecode(str(text).lower())
    for ch in [",", ".", "-", "/", "\\"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())

def safe_float(x):
    if pd.isna(x):
        return None
    try:
        s = str(x).strip().replace(",", ".")
        v = float(s)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except:
        return None

def calc_distance(lat1, lng1, lat2, lng2):
    if any(v is None for v in [lat1, lng1, lat2, lng2]):
        return None
    try:
        return round(geodesic((lat1, lng1), (lat2, lng2)).meters, 2)
    except:
        return None

# =====================
# NORMALIZE DATA
# =====================
# Name
df["ten_norm"] = df["Tên quán"].apply(normalize_text)
df["name_norm"] = df["name"].apply(normalize_text)

# Address
df["addr1_norm"] = df["Địa chỉ"].apply(normalize_text)
df["addr2_norm"] = df["address"].apply(normalize_text)

# GPS
df["lat1"] = df["Latitude"].apply(safe_float)
df["lng1"] = df["Longitude"].apply(safe_float)
df["lat2"] = df["lat"].apply(safe_float)
df["lng2"] = df["lng"].apply(safe_float)

# =====================
# CORE LOGIC
# =====================
def compare(row):
    # ---- 1. SO TÊN QUÁN ----
    name_score = fuzz.token_set_ratio(row["ten_norm"], row["name_norm"])
    name_exact = row["ten_norm"] == row["name_norm"] and row["ten_norm"] != ""

    if name_exact:
        return pd.Series([
            "Trùng quán (tên chính xác)",
            100,
            name_score,
            None
        ])

    if name_score >= NAME_FUZZY_THRESHOLD:
        return pd.Series([
            "Trùng quán (tên gần đúng)",
            name_score,
            name_score,
            None
        ])

    # ---- 2. SO ĐỊA CHỈ TEXT ----
    addr_score = fuzz.token_set_ratio(row["addr1_norm"], row["addr2_norm"])

    if addr_score >= ADDRESS_TEXT_THRESHOLD:
        return pd.Series([
            "Trùng địa chỉ",
            addr_score,
            name_score,
            None
        ])

    # ---- 3. SO GPS ----
    distance_m = calc_distance(
        row["lat1"], row["lng1"],
        row["lat2"], row["lng2"]
    )

    if distance_m is not None and distance_m <= ADDRESS_DISTANCE_M:
        return pd.Series([
            "Gần nhau nhưng khác địa chỉ",
            40,
            name_score,
            distance_m
        ])

    if distance_m is not None:
        return pd.Series([
            "Khác",
            0,
            name_score,
            distance_m
        ])

    return pd.Series([
        "Thiếu tọa độ",
        0,
        name_score,
        None
    ])

# =====================
# APPLY
# =====================
df[[
    "Kết luận",
    "Độ tin cậy (%)",
    "Điểm giống tên",
    "Khoảng cách (m)"
]] = df.apply(compare, axis=1)

# =====================
# CLEANUP
# =====================
df.drop(columns=[
    "ten_norm", "name_norm",
    "addr1_norm", "addr2_norm",
    "lat1", "lng1", "lat2", "lng2"
], inplace=True)

# =====================
# EXPORT
# =====================
try:
    df.to_excel(output_file, index=False)
    print("✅ Hoàn tất")
except PermissionError:
    print("❌ File đang mở hoặc không có quyền ghi")
