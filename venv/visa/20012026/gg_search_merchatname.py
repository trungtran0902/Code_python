import time
import tkinter as tk
from tkinter import filedialog
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ===== B1: Mở hộp thoại chọn file =====
root = tk.Tk()
root.withdraw()  # Ẩn cửa sổ chính của Tkinter
file_path = filedialog.askopenfilename(title="Chọn file Excel", filetypes=[("Excel Files", "*.xlsx")])

if not file_path:
    print("Bạn chưa chọn file!")
    exit()

# ===== B2: Hiển thị các cột trong file Excel =====
df = pd.read_excel(file_path)

print("DANH SÁCH CỘT:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

# ===== B3: Chọn số thứ tự cột làm keyword =====
idx = int(input("Nhập số thứ tự cột làm keyword: "))
keyword_col = df.columns[idx]
keywords = df[keyword_col].dropna().astype(str).tolist()

print(f"Đã chọn cột: {keyword_col}")
print("5 keyword đầu:")
for k in keywords[:5]:
    print("-", k)

# ===== B4: Mở Google =====
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ===== B5: Truyền keyword + legal name =====
wait = WebDriverWait(driver, 10)

for kw in keywords:
    print(f"\nĐang tìm: {kw} legal name")
    driver.get("https://www.google.com")
    time.sleep(2)

    search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))

    search_term = f"{kw} legal name"
    search_box.clear()
    search_box.send_keys(search_term)
    search_box.send_keys(Keys.ENTER)

    # ===== B6: Lấy dữ liệu =====
    try:
        # Chờ kết quả và lấy thông tin (kno-rdesc hoặc các phần tử tương tự)
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'kp-header')]")))

        # Cố gắng lấy dữ liệu từ phần thông tin AI (knowledge panel)
        try:
            ai_info_section = driver.find_element(By.XPATH, "//div[contains(@class, 'kno-rdesc')]")
            ai_info = ai_info_section.text.strip() if ai_info_section else "Không có dữ liệu"
            print(f"Thông tin tìm được: {ai_info}")
        except Exception as e:
            print(f"Lỗi khi lấy dữ liệu từ AI info: {e}")
            ai_info = "Không lấy được thông tin từ AI info"

        # Nếu không tìm thấy 'kno-rdesc', thử các XPath khác (ví dụ: lấy tên công ty từ phần tiêu đề)
        if ai_info == "Không lấy được thông tin từ AI info":
            try:
                title_section = driver.find_element(By.XPATH, "//h2[contains(@class, 'kp-header')]")
                ai_info = title_section.text.strip() if title_section else "Không tìm thấy thông tin tiêu đề"
                print(f"Thông tin tìm được từ tiêu đề: {ai_info}")
            except Exception as e:
                print(f"Lỗi khi lấy dữ liệu từ tiêu đề: {e}")
                ai_info = "Không lấy được thông tin tiêu đề"

    except Exception as e:
        print(f"Lỗi khi tìm kiếm: {e}")

    # Lưu kết quả vào file Excel hoặc tiếp tục tìm kiếm
    # (Tùy vào nhu cầu bạn có thể ghi vào file Excel hoặc tiếp tục tìm kiếm)

# ===== Đóng trình duyệt =====
driver.quit()
