import openpyxl
import webbrowser
import time

# Đường dẫn tới file
file_path = "QuangNam.xlsx"  # hoặc đường dẫn đầy đủ nếu cần
wb = openpyxl.load_workbook(file_path)
sheet = wb.active

# Xác định cột API URL
header = [cell.value for cell in sheet[1]]
url_col_index = header.index("API URL") + 1  # openpyxl uses 1-based index

# Mở từng URL trong trình duyệt
for row in sheet.iter_rows(min_row=2, values_only=True):
    url = row[url_col_index - 1]
    if url:
        webbrowser.open_new_tab(url)
        time.sleep(1)  # chờ 1 giây giữa các lần mở tab (điều chỉnh nếu cần)
