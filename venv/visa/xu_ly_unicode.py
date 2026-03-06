import os
import pandas as pd
from unidecode import unidecode

def remove_accents(text):
    try:
        return unidecode(str(text))
    except Exception:
        return text

def input_int(prompt, min_val=None, max_val=None):
    while True:
        try:
            value = int(input(prompt))
            if min_val is not None and value < min_val:
                print("❌ Giá trị quá nhỏ.")
                continue
            if max_val is not None and value > max_val:
                print("❌ Giá trị quá lớn.")
                continue
            return value
        except ValueError:
            print("❌ Vui lòng nhập một số nguyên.")

def main():
    print("=== CHƯƠNG TRÌNH XỬ LÝ EXCEL: CHUYỂN CÓ DẤU → KHÔNG DẤU ===\n")

    # 1. Chọn thư mục
    folder_path = input("Nhập đường dẫn thư mục chứa file Excel: ").strip('"')
    if not os.path.isdir(folder_path):
        print("❌ Thư mục không tồn tại.")
        return

    # 2. Liệt kê file Excel
    excel_files = [f for f in os.listdir(folder_path) if f.endswith((".xlsx", ".xls"))]

    if not excel_files:
        print("❌ Không có file Excel nào.")
        return

    print("\n📄 Các file Excel tìm thấy trong thư mục:")
    for i, f in enumerate(excel_files):
        print(f"{i}. {f}")

    # 3. Chọn file Excel
    file_index = input_int("\nNhập số thứ tự file cần xử lý: ", 0, len(excel_files)-1)

    file_path = os.path.join(folder_path, excel_files[file_index])
    print(f"\n✅ Đang mở file: {excel_files[file_index]} ...")

    # 4. Lấy danh sách sheet
    try:
        xls = pd.ExcelFile(file_path)
        print("\n📑 Danh sách sheet trong file:")
        for s in xls.sheet_names:
            print(" -", s)
    except Exception as e:
        print("❌ Không đọc được danh sách sheet:", e)
        return

    # 5. Nhập tên sheet
    sheet_name = input("\nNhập tên sheet cần xử lý: ").strip()
    if sheet_name not in xls.sheet_names:
        print("❌ Sheet không tồn tại trong file.")
        return

    # 6. Đọc sheet được chọn
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    print(f"\n📄 Sheet '{sheet_name}' có {len(df.columns)} cột và {len(df)} dòng.\n")

    while True:
        print("Danh sách cột:")
        for i, col in enumerate(df.columns):
            print(f"{i}. {col}")

        col_index = input_int("\nNhập số thứ tự cột cần xử lý: ",
                              0, len(df.columns)-1)

        selected_col = df.columns[col_index]
        new_col = f"{selected_col}_khong_dau"

        print(f"🔄 Đang xử lý '{selected_col}' ...")
        df[new_col] = df[selected_col].apply(remove_accents)
        print(f"✅ Đã tạo cột mới: {new_col}\n")

        cont = input("Xử lý thêm cột khác? (y/n): ").strip().lower()
        if cont != "y":
            break

    # 7. Lưu file mới
    base, ext = os.path.splitext(file_path)
    output_file = f"{base}_processed.xlsx"
    df.to_excel(output_file, index=False)

    print(f"\n🎉 Hoàn tất! File đã được lưu tại:\n➡ {output_file}")

if __name__ == "__main__":
    main()
