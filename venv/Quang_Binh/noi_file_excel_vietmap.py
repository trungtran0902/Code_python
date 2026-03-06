import os
import pandas as pd

# Bước 1: Nhập đường dẫn chứa các file Excel
input_folder = input("Nhập đường dẫn chứa các file Excel: ")

# Lấy tất cả các file Excel trong thư mục
excel_files = [f for f in os.listdir(input_folder) if f.endswith('.xlsx')]

# Bước 2: Nhập thư mục chứa file output
output_folder = input("Nhập thư mục chứa file output: ")

# Kiểm tra nếu thư mục output không tồn tại, tạo mới
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Bước 3: Xử lý các file
merged_df = pd.DataFrame()

# Đọc từng file Excel và thêm cột 'File' để phân loại
for excel_file in excel_files:
    file_path = os.path.join(input_folder, excel_file)
    df = pd.read_excel(file_path)

    # Thêm cột 'File' chứa tên file để phân loại
    df['File'] = excel_file.split('.')[0]  # Tên file không có đuôi .xlsx

    # Loại bỏ các cột có toàn bộ giá trị NaN
    df = df.dropna(axis=1, how='all')

    # Nối các dataframe lại
    merged_df = pd.concat([merged_df, df], ignore_index=True)

# Lưu kết quả vào file output
output_file = os.path.join(output_folder, 'merged_output.xlsx')
merged_df.to_excel(output_file, index=False)

print(f"Dữ liệu đã được nối và lưu tại: {output_file}")
