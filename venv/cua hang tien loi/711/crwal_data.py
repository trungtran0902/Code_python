import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Mở trình duyệt
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # chạy ẩn
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://7-eleven.vn/thong-tin/danh-sach-cua-hang-7-eleven-gan-day?srsltid=AfmBOooK9PYW54Olibgjj__zVds1QEdgR07CpZsSdoQzrlhPpT7qr2Gx"
driver.get(url)

# Chờ trang load
time.sleep(5)

stores_data = []

store_cards = driver.find_elements(By.CLASS_NAME, "store-card")

for card in store_cards:
    try:
        name = card.find_element(By.CLASS_NAME, "store-name").text
        details = card.find_element(By.CLASS_NAME, "store-details").text

        address = ""
        phone = ""
        email = ""

        lines = details.split("\n")

        for line in lines:
            if "Địa chỉ mới" in line:
                address = line
            elif "📞" in line:
                phone = line.replace("📞", "").strip()
            elif "📧" in line:
                email = line.replace("📧", "").strip()

        stores_data.append({
            "Tên cửa hàng": name,
            "Địa chỉ": address,
            "Điện thoại": phone,
            "Email": email
        })

    except Exception as e:
        print("Lỗi khi đọc store:", e)

driver.quit()

# Lưu ra Excel
df = pd.DataFrame(stores_data)
df.to_excel("danh_sach_7eleven.xlsx", index=False)

print("✅ Đã lưu file danh_sach_7eleven.xlsx")