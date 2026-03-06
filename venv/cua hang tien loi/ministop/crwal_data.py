import tkinter as tk
from tkinter import filedialog, messagebox
from bs4 import BeautifulSoup
import pandas as pd
import re
import os

def scan_ministop_stores():
    # Ẩn cửa sổ tkinter chính
    root = tk.Tk()
    root.withdraw()

    # Mở hộp thoại chọn file
    file_path = filedialog.askopenfilename(
        title="Chọn file HTML",
        filetypes=[("HTML files", "*.html *.htm *.txt")]
    )

    if not file_path:
        messagebox.showwarning("Thông báo", "Bạn chưa chọn file!")
        return

    # Đọc file
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    stores = []
    ul_tags = soup.find_all("ul")

    i = 0
    while i < len(ul_tags) - 1:
        first_li = ul_tags[i].find("li")
        second_li = ul_tags[i+1].find("li")

        if first_li and second_li:
            a_tag = first_li.find("a")

            if a_tag and "MINISTOP" in a_tag.text:
                store_name = a_tag.text.strip()
                address = second_li.text.strip()

                stores.append({
                    "Tên cửa hàng": store_name,
                    "Địa chỉ": address
                })

                i += 2
                continue

        i += 1

    if not stores:
        messagebox.showerror("Lỗi", "Không tìm thấy cửa hàng nào!")
        return

    # Xuất Excel
    df = pd.DataFrame(stores)

    output_path = os.path.splitext(file_path)[0] + "_MINISTOP.xlsx"
    df.to_excel(output_path, index=False)

    messagebox.showinfo("Hoàn tất", f"Đã lưu {len(stores)} cửa hàng vào:\n{output_path}")

if __name__ == "__main__":
    scan_ministop_stores()