from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://www.highlandscoffee.com.vn/vn/he-thong-cua-hang.html")
driver.maximize_window()

time.sleep(3)

stores = []

while True:
    time.sleep(2)

    # Tìm danh sách cửa hàng trên trang hiện tại
    items = driver.find_elements(By.CSS_SELECTOR, ".item-store")

    for item in items:
        name = item.find_element(By.CSS_SELECTOR, ".store-title").text
        address = item.find_element(By.CSS_SELECTOR, ".content-store").text
        stores.append([name, address])

    # Kiểm tra nút "Trang Sau"
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, "a[aria-label='Next']")

        # Nếu nút next bị disabled → hết trang
        if "disabled" in next_btn.get_attribute("class"):
            break

        next_btn.click()
    except:
        break

driver.quit()

# Lưu CSV
with open("highlands_stores.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Tên cửa hàng", "Địa chỉ"])
    writer.writerows(stores)

print("Hoàn thành! Đã lưu vào highlands_stores.csv")
