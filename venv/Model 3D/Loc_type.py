import json  # Import thư viện json
import pandas as pd
import tkinter as tk
from tkinter import filedialog, simpledialog


# Hàm để thống kê số lượng các giá trị trong cột đã chọn
def count_values_in_column(df, column_name):
    # Loại bỏ giá trị NaN và các khoảng trắng thừa trong dữ liệu
    df[column_name] = df[column_name].dropna().str.strip()

    # Đếm số lượng mỗi giá trị trong cột
    return df[column_name].value_counts()


# Hàm để mở hộp thoại chọn file JSON và xử lý
def process_json_and_excel():
    # Mở hộp thoại chọn file JSON
    json_file_path = filedialog.askopenfilename(title="Chọn file JSON", filetypes=[("JSON files", "*.json")])

    if json_file_path:
        # Đọc dữ liệu từ file JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)  # Đảm bảo rằng json được import

        # Hiển thị một số thông tin từ file JSON để người dùng dễ dàng tham khảo
        print(f"Đã chọn file JSON: {json_file_path}")
        print(f"Dữ liệu JSON đầu vào: {json_data[:2]}...")  # In 2 phần tử đầu tiên của dữ liệu

        # Mở hộp thoại chọn file Excel
        excel_file_path = filedialog.askopenfilename(title="Chọn file Excel",
                                                     filetypes=[("Excel files", "*.xlsx;*.xls")])

        if excel_file_path:
            # Đọc dữ liệu từ file Excel vào DataFrame
            df = pd.read_excel(excel_file_path)

            # In danh sách các cột trong file Excel
            print("Danh sách các cột có trong file Excel:")
            for idx, col in enumerate(df.columns.tolist(), start=1):
                print(f"{idx}. {col}")

            # Nhập số thứ tự của cột cần thống kê
            column_index = simpledialog.askinteger("Chọn cột",
                                                   f"Nhập số thứ tự của cột bạn muốn thống kê (từ 1 đến {len(df.columns)}):")

            if column_index and 1 <= column_index <= len(df.columns):
                # Lấy tên cột từ số thứ tự
                column_name = df.columns[column_index - 1]

                # Thống kê số lượng các giá trị trong cột đã chọn
                value_counts = count_values_in_column(df, column_name)

                # In kết quả thống kê ra console
                print(f"Thống kê số lượng giá trị trong cột '{column_name}':")
                print(value_counts)
            else:
                print("Số thứ tự cột không hợp lệ.")
        else:
            print("Bạn chưa chọn file Excel.")
    else:
        print("Bạn chưa chọn file JSON.")


# Tạo giao diện người dùng với tkinter
root = tk.Tk()
root.title("Thống kê giá trị từ file Excel và JSON")

# Ẩn cửa sổ chính của tkinter (chỉ sử dụng hộp thoại)
root.withdraw()

# Gọi hàm xử lý file Excel và JSON
process_json_and_excel()
