from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager  # Đảm bảo bạn đã cài webdriver_manager
import time

# Cấu hình ChromeOptions
chrome_options = Options()
chrome_options.add_argument("--headless")  # Chạy trình duyệt ẩn
chrome_options.add_argument("--lang=vi")  # Đặt ngôn ngữ là tiếng Việt

# Cập nhật cách sử dụng Service với WebDriverManager
service = Service(ChromeDriverManager().install())

# Khởi tạo driver với WebDriverManager và options
driver = webdriver.Chrome(service=service, options=chrome_options)

# Bước 1: Mở Google Maps và tìm kiếm
driver.get("https://www.google.com/maps")

# Chờ cho trang tải xong
time.sleep(3)

# Tìm ô tìm kiếm và nhập từ khóa
search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
search_box.send_keys("nhà hàng quận 7")
search_box.send_keys(Keys.RETURN)

# Chờ kết quả tải
time.sleep(5)

# Bước 2: Cuộn xuống để tải hết danh sách
for _ in range(5):  # Cuộn 5 lần
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

# Bước 3: Click vào một kết quả chi tiết
# Giả sử bạn lấy kết quả đầu tiên trong danh sách
first_result = driver.find_element(By.XPATH, "(//div[@class='Nv2PK THOPZb'])[1]")
first_result.click()

# Bước 4: Chờ trang chi tiết mở và lấy dữ liệu
time.sleep(3)

# Lấy tên quán, địa chỉ, và lượt đánh giá (nếu có)
try:
    name = driver.find_element(By.XPATH, "//h1[@class='x3AX1-LfntMc-header-title-title']").text
    address = driver.find_element(By.XPATH, "//button[@data-tooltip='Sao chép địa chỉ']").text
    rating = driver.find_element(By.XPATH, "//div[@class='section-star-display']/span").text
    print(f"Tên quán: {name}")
    print(f"Địa chỉ: {address}")
    print(f"Lượt đánh giá: {rating}")
except Exception as e:
    print(f"Lỗi khi lấy dữ liệu: {e}")

# Đóng trình duyệt
driver.quit()
