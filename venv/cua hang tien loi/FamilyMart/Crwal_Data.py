import os
import json
import pandas as pd
import tkinter as tk
from tkinter import filedialog

# Ẩn cửa sổ chính
root = tk.Tk()
root.withdraw()

# 🔹 BƯỚC 1: Chọn thư mục
folder_path = filedialog.askdirectory(title="Chọn thư mục chứa file TXT")

if not folder_path:
    print("❌ Bạn chưa chọn thư mục.")
    exit()

print("📂 Đã chọn thư mục:", folder_path)

stores = []

# 🔹 BƯỚC 2: Duyệt file txt
for filename in os.listdir(folder_path):
    if filename.endswith(".txt"):
        file_path = os.path.join(folder_path, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)   # <-- đọc JSON trực tiếp

        for store in data:
            stores.append({
                "file": filename,
                "name": store.get("name"),
                "address": store.get("address"),
                "lat": store.get("coordinate", {}).get("lat"),
                "lng": store.get("coordinate", {}).get("lng"),
                "open_time": store.get("open_time"),
                "close_time": store.get("close_time"),
            })

# 🔹 BƯỚC 3: Xuất Excel
if stores:
    df = pd.DataFrame(stores)
    output_file = os.path.join(folder_path, "tong_hop_familymart.xlsx")
    df.to_excel(output_file, index=False)
    print("✅ Đã lưu file:", output_file)
else:
    print("⚠ Không có dữ liệu.")