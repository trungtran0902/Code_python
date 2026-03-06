from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

# Khởi tạo WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Chạy ở chế độ không giao diện
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Truy cập trang web
url = "https://www.highlandscoffee.com.vn/vn/he-thong-cua-hang.html"
driver.get(url)

# Đợi trang tải xong
time.sleep(5)

# Tìm tất cả các phần tử chứa thông tin cửa hàng
store_elements = driver.find_elements(By.CLASS_NAME, "store-item")

# Mở file CSV để lưu dữ liệu
with open('highlands_coffee_stores.csv', 'w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['Tên Cửa Hàng', 'Địa Chỉ', 'Số Điện Thoại', 'Khu Vực'])  # Tiêu đề cột

    # Lặp qua từng cửa hàng và lấy thông tin
    for store in store_elements:
        name = store.find_element(By.TAG_NAME, 'h3').text if store.find_element(By.TAG_NAME, 'h3') else 'N/A'
        address = store.find_element(By.CLASS_NAME, 'store-address').text if store.find_element(By.CLASS_NAME,
                                                                                                'store-address') else 'N/A'
        phone = store.find_element(By.CLASS_NAME, 'store-phone').text if store.find_element(By.CLASS_NAME,
                                                                                            'store-phone') else 'N/A'
        region = store.find_element(By.CLASS_NAME, 'store-region').text if store.find_element(By.CLASS_NAME,
                                                                                              'store-region') else 'N/A'

        # Lưu dữ liệu vào file CSV
        writer.writerow([name, address, phone, region])

# Đóng trình duyệt
driver.quit()

print("Dữ liệu đã được lưu vào highlands_coffee_stores.csv.")
