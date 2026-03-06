import pandas as pd
import uuid
from bson import Binary  # Sử dụng đúng cách này
import base64

# Đọc file Excel vào DataFrame
file_path = 'tayninh.xlsx'  # Thay đổi với đường dẫn đến file Excel của bạn
df = pd.read_excel(file_path)

# Hàm chuyển UUID string thành BinData Base64
def convert_to_bindata(uuid_str):
    try:
        # Chuyển UUID thành dãy byte
        uuid_value = uuid.UUID(uuid_str)
        uuid_bytes = uuid_value.bytes

        # Chuyển dãy byte thành BinData với subtype 0x04 (UUID)
        binary_uuid = Binary(uuid_bytes, 0x04)

        # Mã hóa Base64 và trả về chuỗi
        base64_encoded = base64.b64encode(binary_uuid).decode("utf-8")
        return f"BinData(3, \"{base64_encoded}\")"
    except ValueError:
        return None  # Trả về None nếu không phải UUID hợp lệ

# Áp dụng hàm chuyển đổi cho cột _id trong DataFrame và tạo thêm cột dãy_id
df['dãy_id'] = df['_id'].apply(convert_to_bindata)

# Lưu kết quả vào file Excel mới
output_file_path = 'output_file.xlsx'  # Đường dẫn file output
df.to_excel(output_file_path, index=False)

# In ra kết quả để kiểm tra
print(df[['dãy_id', '_id']])
