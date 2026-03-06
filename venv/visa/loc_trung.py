import pandas as pd
import os

# ======== NHẬP DỮ LIỆU TỪ NGƯỜI DÙNG ========

folder_path = input("Nhập đường dẫn chứa file Excel: ").strip()
file_name = input("Nhập tên file Excel (vd: du_lieu.xlsx): ").strip()
columns_input = input("Nhập tên các cột cần kiểm tra trùng, cách nhau bởi dấu phẩy (vd: A,B): ").strip()

# Xử lý tên cột
columns_to_check = [col.strip() for col in columns_input.split(",") if col.strip()]

# Tạo đường dẫn đầy đủ
input_file = os.path.join(folder_path, file_name)

# Tên file kết quả
output_file = os.path.join(folder_path, "du_lieu_trung.xlsx")

# ======== XỬ LÝ FILE ========
try:
    # Đọc file Excel
    df = pd.read_excel(input_file)

    # Kiểm tra tồn tại cột
    for col in columns_to_check:
        if col not in df.columns:
            raise ValueError(f"Cột '{col}' không tồn tại trong file Excel. Các cột hiện có: {list(df.columns)}")

    # ✅ Tìm các nhóm giá trị trùng nhau theo tổ hợp cột
    duplicate_groups = df.groupby(columns_to_check).filter(lambda x: len(x) > 1)

    # Xuất ra file Excel mới
    duplicate_groups.to_excel(output_file, index=False)

    print(f"\n✅ Đã lọc xong! File kết quả: {output_file}")
    print(f"🔍 Tổng số dòng trùng (theo tổ hợp {columns_to_check}): {len(duplicate_groups)}")

except FileNotFoundError:
    print("\n❌ Không tìm thấy file. Vui lòng kiểm tra lại đường dẫn hoặc tên file.")
except Exception as e:
    print(f"\n⚠️ Lỗi: {e}")
