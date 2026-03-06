import pandas as pd

# Đường dẫn tới file Excel gốc của bạn
file_path = "ha noi.xlsx"

# Đọc dữ liệu
df = pd.read_excel(file_path, sheet_name="Sheet1")

# Giữ lại các dòng có cả 'mã' và 'Tên'
df_clean = df.dropna(subset=["mã", "Tên"], how="any")

# Chuyển cột mã về kiểu số nguyên (loại bỏ .0)
df_clean["mã"] = df_clean["mã"].astype(int).astype(str)

# Lấy 2 cột riêng biệt: mã và Tên
result = df_clean[["mã", "Tên"]].reset_index(drop=True)

# Xuất ra file Excel mới
output_path = "du_lieu_gon.xlsx"
result.to_excel(output_path, index=False)

print(f"Đã xuất file thành công: {output_path}")
