import os
import json
import ast
import pandas as pd

def classify_metadata(meta_str):
    """Phân loại metadata: {} hoặc url"""
    if not isinstance(meta_str, str) or not meta_str.strip():
        return "{}"
    try:
        d = json.loads(meta_str) if meta_str.strip().startswith("{") else ast.literal_eval(meta_str)
        if isinstance(d, dict) and "url" in d:
            return "url"
        return "{}"
    except Exception:
        return "{}"

# ======== INPUT ========
folder_path = input("Nhập đường dẫn thư mục chứa file CSV: ").strip()
output_excel = os.path.join(folder_path, "metadata_summary.xlsx")

csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]

rows = []

if not csv_files:
    print("⚠️ Không tìm thấy file CSV nào trong thư mục.")
else:
    for file_name in csv_files:
        file_path = os.path.join(folder_path, file_name)
        province = os.path.splitext(file_name)[0]  # tên tỉnh từ file

        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        df.columns = df.columns.str.strip()

        df["meta_type"] = df["metadata"].apply(classify_metadata)

        count_empty = (df["meta_type"] == "{}").sum()
        count_url = (df["meta_type"] == "url").sum()

        rows.append({"Tỉnh": province, "{}": count_empty, "url": count_url})

    # Xuất ra Excel
    summary_df = pd.DataFrame(rows)
    summary_df.to_excel(output_excel, index=False)

    print(f"✅ Đã tạo file thống kê: {output_excel}")
