import time, random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ===== Đọc file Excel =====
file_path = input("Nhập đường dẫn file Excel: ").strip()
df = pd.read_excel(file_path)

print("DANH SÁCH CỘT:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

idx = int(input("Nhập số thứ tự cột làm keyword: "))
keyword_col = df.columns[idx]
keywords = df[keyword_col].dropna().astype(str).tolist()

print(f"Đã chọn cột: {keyword_col}")
print("5 keyword đầu:")
for k in keywords[:5]:
    print("-", k)

# ===== Cấu hình Chrome =====
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 20)

results = []

# ===== Chạy từng keyword =====
for kw in keywords:
    print(f"\nĐang tìm: {kw}")
    driver.get("https://www.google.com")
    time.sleep(random.uniform(2, 4))

    search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
    search_box.clear()
    search_box.send_keys(kw)
    search_box.send_keys(Keys.ENTER)

    try:
        wait.until(EC.presence_of_element_located((By.ID, "rhs")))
    except:
        print("Không có khung bên phải")
        continue

    data = {"keyword": kw}

    try:
        data["ten"] = driver.find_element(By.XPATH, '//div[@data-attrid="title"]').text
    except:
        data["ten"] = None

    try:
        data["dia_chi"] = driver.find_element(
            By.XPATH, '//div[@data-local-attribute="d3adr"]//span[@class="LrzXr"]'
        ).text
    except:
        data["dia_chi"] = None

    try:
        data["so_dien_thoai"] = driver.find_element(
            By.XPATH, '//div[@data-local-attribute="d3ph"]//span[contains(@aria-label,"Gọi")]'
        ).text
    except:
        data["so_dien_thoai"] = None

    try:
        data["website"] = driver.find_element(
            By.XPATH, '//a[contains(@href,"http")]'
        ).get_attribute("href")
    except:
        data["website"] = None

    print(data)
    results.append(data)

# ===== Lưu ra Excel =====
out_df = pd.DataFrame(results)
out_file = "ket_qua_google.xlsx"
out_df.to_excel(out_file, index=False)

print(f"\nĐã lưu kết quả vào: {out_file}")
input("Nhấn Enter để đóng trình duyệt...")
driver.quit()
