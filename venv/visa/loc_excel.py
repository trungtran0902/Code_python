import os
import pandas as pd

def read_id_list():
    """
    Hỏi người dùng cách nhập danh sách ID:
    1. Nhập trực tiếp (dán chuỗi cách nhau bởi dấu phẩy hoặc xuống dòng)
    2. Đọc từ file .txt chứa danh sách ID
    """
    print("\n=== Cách nhập danh sách ID ===")
    print("1. Nhập/dán trực tiếp (phân tách bằng dấu phẩy hoặc xuống dòng)")
    print("2. Đọc từ file .txt")
    choice = input("Chọn cách nhập (1 hoặc 2): ").strip()

    if choice == "2":
        file_path = input("Nhập đường dẫn đến file .txt chứa ID: ").strip('"')
        if not os.path.exists(file_path):
            print("❌ File không tồn tại.")
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        ids = [line.strip() for line in lines if line.strip()]
        return ids

    else:
        print("\nDán danh sách ID (Enter 2 lần để kết thúc):")
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        # Ghép tất cả dòng, tách theo dấu phẩy và khoảng trắng
        joined = ",".join(lines)
        ids = [v.strip() for v in joined.split(",") if v.strip()]
        return ids


def main():
    print("=== LỌC DỮ LIỆU EXCEL THEO DANH SÁCH ID ===\n")

    # 1️⃣ Chọn thư mục
    folder_path = input("Nhập đường dẫn thư mục chứa file Excel: ").strip('"')
    if not os.path.isdir(folder_path):
        print("❌ Thư mục không tồn tại.")
        return

    # 2️⃣ Liệt kê file Excel
    excel_files = [f for f in os.listdir(folder_path) if f.endswith((".xlsx", ".xls"))]
    if not excel_files:
        print("❌ Không có file Excel nào trong thư mục.")
        return

    print("\nCác file Excel có trong thư mục:")
    for i, f in enumerate(excel_files):
        print(f"{i}. {f}")

    file_index = int(input("\nNhập số thứ tự file cần mở: "))
    if file_index < 0 or file_index >= len(excel_files):
        print("❌ Số thứ tự không hợp lệ.")
        return

    file_path = os.path.join(folder_path, excel_files[file_index])
    print(f"\n✅ Đang mở file: {excel_files[file_index]} ...")

    df = pd.read_excel(file_path)
    print(f"📄 File có {len(df.columns)} cột và {len(df)} dòng.\n")

    # 3️⃣ Chọn cột để lọc
    print("Danh sách các cột:")
    for i, col in enumerate(df.columns):
        print(f"{i}. {col}")

    col_index = int(input("\nNhập số thứ tự cột chứa ID cần lọc: "))
    if col_index < 0 or col_index >= len(df.columns):
        print("❌ Số thứ tự cột không hợp lệ.")
        return

    selected_col = df.columns[col_index]
    print(f"\n🔹 Cột được chọn: {selected_col}")

    # 4️⃣ Nhập danh sách ID
    ids = read_id_list()
    if not ids:
        print("⚠️ Không có ID nào được nhập. Dừng chương trình.")
        return

    print(f"\n📦 Tổng số ID cần lọc: {len(ids)}")

    # 5️⃣ Lọc dữ liệu
    filtered_df = df[df[selected_col].astype(str).isin(ids)]

    if filtered_df.empty:
        print("\n⚠️ Không tìm thấy bản ghi nào khớp với danh sách ID.")
    else:
        print(f"\n✅ Tìm thấy {len(filtered_df)} bản ghi khớp.")

        # 6️⃣ Xuất ra file Excel mới
        base, ext = os.path.splitext(file_path)
        output_file = f"{base}_filtered.xlsx"
        filtered_df.to_excel(output_file, index=False)
        print(f"💾 File kết quả đã được lưu tại:\n{output_file}")


if __name__ == "__main__":
    main()
