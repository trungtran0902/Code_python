import os
from docx import Document
import pandas as pd


# Hàm đọc dữ liệu từ tệp Word
def extract_data_from_word(file_path):
    doc = Document(file_path)

    # Danh sách chứa tất cả các dòng thông tin
    data = []
    phuong_data = {}

    # Duyệt qua tất cả các đoạn văn trong tệp Word
    for para in doc.paragraphs:
        text = para.text.strip()
        print(f"Đoạn văn: {text}")  # In ra tất cả các đoạn văn để kiểm tra

        # Kiểm tra và trích xuất thông tin từ các đoạn văn
        if text.startswith("Phường") or text.startswith("Xã"):
            if phuong_data:
                data.append(phuong_data)  # Lưu dữ liệu phường trước đó vào danh sách
            phuong_data = {"Phường": text.split(" ")[1]}  # Lấy tên phường
            phuong_data["Sáp Nhập"] = None
            phuong_data["Diện tích"] = None
            phuong_data["Dân số"] = None

        elif "Sáp nhập từ:" in text:
            phuong_data["Sáp Nhập"] = text.replace("Sáp nhập từ:", "").strip()

        elif "Diện tích" in text:
            phuong_data["Diện tích"] = text.replace("Diện tích (km2)", "").strip() + " km2"

        elif "Dân số" in text:
            phuong_data["Dân số"] = text.replace("Dân số (người)", "").strip() + " người"

    # Đảm bảo thêm thông tin của phường cuối cùng vào danh sách
    if phuong_data:
        data.append(phuong_data)

    return data


# Lấy đường dẫn thư mục hiện tại nơi tệp Python đang chạy
current_directory = os.path.dirname(os.path.abspath(__file__))

# Đọc tệp Word và xử lý dữ liệu
word_file = os.path.join(current_directory, '1.docx')  # Đường dẫn tệp Word nằm cùng thư mục với tệp Python
data = extract_data_from_word(word_file)

# Kiểm tra dữ liệu trước khi lưu vào Excel
print("Dữ liệu trích xuất:", data)

# Lưu kết quả vào tệp Excel
if data:
    output_file = os.path.join(current_directory, 'output.xlsx')  # Đường dẫn tệp Excel xuất ra cùng thư mục
    df = pd.DataFrame(data)
    print(f"Dữ liệu DataFrame:\n{df}")

    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Kết quả đã được lưu vào {output_file}")
else:
    print("Không có dữ liệu để lưu.")
