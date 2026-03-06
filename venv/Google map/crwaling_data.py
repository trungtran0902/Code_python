import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ======================
# CONFIG
# ======================
KEYWORD = "Tòa nhà Golden King"
OUTPUT_FILE = "gmaps_poi_details.json"


# ======================
# SETUP
# ======================
def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=vi-VN")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    return driver


# ======================
# HELPER FUNCTIONS
# ======================
def wait_for_element(driver, xpath, timeout=10):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
    except:
        return None


def extract_detail(driver):
    """Trích xuất thông tin từ giao diện chi tiết"""
    data = {}
    try:
        h1 = wait_for_element(driver, "//h1[contains(@class,'DUwDvf')]", 10)
        data["name"] = h1.text if h1 else None
    except:
        data["name"] = None

    def safe_get_text(xpath):
        el = driver.find_elements(By.XPATH, xpath)
        return el[0].text.strip() if el else None

    def safe_get_attr(xpath, attr):
        el = driver.find_elements(By.XPATH, xpath)
        return el[0].get_attribute(attr) if el else None

    data["address"] = safe_get_text("//button[@data-item-id='address']")
    data["phone"] = safe_get_text("//button[contains(@data-item-id,'phone')]")
    data["website"] = safe_get_attr("//a[contains(@aria-label,'Website')]", "href")
    data["rating"] = safe_get_attr("//span[contains(@aria-label,'sao')]", "aria-label")

    # Giờ mở cửa
    try:
        hours = [row.text for row in driver.find_elements(By.XPATH, "//table//tr")]
        data["hours"] = hours if hours else None
    except:
        data["hours"] = None

    # Lấy toạ độ từ URL
    url = driver.current_url
    if "/@" in url:
        coords = url.split("/@")[1].split(",")
        data["latitude"], data["longitude"] = coords[0], coords[1]
    else:
        data["latitude"] = data["longitude"] = None

    print(f"✅ Lấy chi tiết: {data['name']}")
    return data


def scroll_list_panel(driver, delay=1, max_scrolls=10):
    """Cuộn panel bên trái để load thêm kết quả"""
    try:
        panel = driver.find_element(By.XPATH, "//div[@role='feed']")
        for _ in range(max_scrolls):
            driver.execute_script("arguments[0].scrollBy(0, arguments[0].scrollHeight);", panel)
            time.sleep(delay)
        print("🟢 Đã cuộn hết danh sách.")
    except:
        print("⚠️ Không tìm thấy panel danh sách để cuộn.")


# ======================
# MAIN
# ======================
def main():
    driver = setup_driver()
    driver.get("https://www.google.com/maps?hl=vi&gl=VN")
    time.sleep(2)

    # Nhập keyword
    search_box = wait_for_element(driver, "//input[@id='searchboxinput']", 15)
    search_box.clear()
    search_box.send_keys(KEYWORD)
    search_box.send_keys(Keys.ENTER)
    print(f"🔎 Đang tìm kiếm: {KEYWORD}")
    time.sleep(5)

    # Kiểm tra có danh sách kết quả hay không
    list_items = driver.find_elements(By.XPATH, "//div[@role='article']")
    if not list_items:
        print("⚠️ Không có danh sách kết quả, có thể đang ở chế độ chi tiết.")
        data = [extract_detail(driver)]
    else:
        print(f"📋 Có {len(list_items)} kết quả ban đầu.")
        scroll_list_panel(driver, delay=1, max_scrolls=8)
        time.sleep(2)

        results = []
        list_items = driver.find_elements(By.XPATH, "//div[@role='article']")
        print(f"📋 Tổng {len(list_items)} kết quả sau khi cuộn.")

        for i in range(len(list_items)):
            try:
                # Lấy lại danh sách sau mỗi click (DOM thay đổi)
                items = driver.find_elements(By.XPATH, "//div[@role='article']")
                if i >= len(items):
                    break
                item = items[i]
                name = item.text.split("\n")[0]
                print(f"➡️ Click {i+1}/{len(items)}: {name}")
                driver.execute_script("arguments[0].scrollIntoView(true);", item)
                time.sleep(0.5)
                item.click()
                time.sleep(3)

                detail = extract_detail(driver)
                detail["list_name"] = name
                results.append(detail)

                # Quay lại danh sách
                back_btn = driver.find_elements(By.XPATH, "//button[@aria-label='Quay lại']")
                if back_btn:
                    back_btn[0].click()
                    time.sleep(3)
                else:
                    driver.back()
                    time.sleep(3)
            except Exception as e:
                print(f"⚠️ Lỗi khi click item {i+1}: {e}")

        data = results

    # Xuất kết quả ra JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n🎯 Đã lưu {len(data)} địa điểm vào '{OUTPUT_FILE}'")
    input("⏸ Nhấn Enter để thoát...")
    driver.quit()


if __name__ == "__main__":
    main()
