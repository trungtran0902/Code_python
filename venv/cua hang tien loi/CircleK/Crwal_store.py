import os
import json
from tkinter import Tk, filedialog
from openpyxl import Workbook


def extract_stores_from_text(content, province_name):
    """
    Đọc JSON chuẩn dạng:
    [
        {
            "title": "...",
            "lat": "...",
            "lng": "...",
            "html": "..."
        }
    ]
    """

    try:
        data = json.loads(content)
    except Exception as e:
        print("Lỗi đọc JSON:", e)
        return []

    stores = []
    seen = set()

    for item in data:

        lat = item.get("lat")
        lng = item.get("lng")
        title = item.get("title")

        if not lat or not lng or not title:
            continue

        key = (lat.strip(), lng.strip())

        # chống trùng toàn hệ thống
        if key in seen:
            continue

        seen.add(key)

        stores.append({
            "name": "Circle K",
            "province": province_name,
            "address": title.strip(),
            "lat": lat.strip(),
            "lng": lng.strip()
        })

    return stores


def main():

    # ===== MỞ HỘP THOẠI CHỌN FOLDER =====
    root = Tk()
    root.withdraw()

    folder_path = filedialog.askdirectory(title="Chọn thư mục chứa file TXT")

    if not folder_path:
        print("❌ Bạn chưa chọn thư mục.")
        return

    print(f"📂 Đã chọn: {folder_path}")

    all_stores = []
    global_seen = set()

    # ===== ĐỌC TẤT CẢ FILE TXT =====
    for filename in os.listdir(folder_path):

        if filename.endswith(".txt"):

            filepath = os.path.join(folder_path, filename)
            province_name = os.path.splitext(filename)[0]

            print(f"Đang xử lý: {filename}")

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            stores = extract_stores_from_text(content, province_name)

            # chống trùng giữa nhiều tỉnh
            for store in stores:
                key = (store["lat"], store["lng"])
                if key not in global_seen:
                    global_seen.add(key)
                    all_stores.append(store)

    if not all_stores:
        print("⚠ Không tìm thấy dữ liệu.")
        return

    # ===== TẠO FILE EXCEL =====
    wb = Workbook()
    ws = wb.active
    ws.title = "CircleK Stores"

    ws.append(["Tên cửa hàng", "Tỉnh", "Địa chỉ", "Latitude", "Longitude"])

    for store in all_stores:
        ws.append([
            store["name"],
            store["province"],
            store["address"],
            store["lat"],
            store["lng"]
        ])

    output_file = os.path.join(folder_path, "circlek_all_stores.xlsx")
    wb.save(output_file)

    print(f"✔ Đã xuất file: {output_file}")
    print(f"📦 Tổng số cửa hàng: {len(all_stores)}")


if __name__ == "__main__":
    main()