import pandas as pd
import os
import re

folder_path = input("Nhập đường dẫn thư mục chứa file CSV: ").strip()
file_name = input("Nhập tên file CSV (vd: data.csv): ").strip()

input_file = os.path.join(folder_path, file_name)
output_folder = os.path.join(folder_path, "output_provinces")
os.makedirs(output_folder, exist_ok=True)

df = pd.read_csv(input_file)
df.columns = df.columns.str.strip()
df = df.dropna(subset=["province"])

for province, group in df.groupby("province"):
    # Loại bỏ tiền tố "Tỉnh " hoặc "Thành phố " nếu có
    clean_name = re.sub(r"^(Tỉnh|Thành phố)\s+", "", province).strip()
    # Thay khoảng trắng bằng "_"
    safe_name = clean_name.replace(" ", "_")

    output_file = os.path.join(output_folder, f"poi_{safe_name}.csv")
    group.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Đã tạo {output_file} với {len(group)} records")
