import time
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains

EXCEL_PATH = "toa do ubnd.xlsx"     # file đầu vào (cùng thư mục .py)
OUTPUT_PATH = "urls_phuong.xlsx"    # file đầu ra (URL sau khi chọn POI đầu tiên)
BASE_URL = "https://maps.viettel.vn/maps"

# ===== Helpers ===============================================================
def wait_url_contains(driver, text, timeout=10):
    WebDriverWait(driver, timeout).until(lambda d: text in d.current_url)

def click_element_hard(driver, el):
    # Cuộn vào giữa màn hình rồi thử 3 cách click
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        el.click()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        pass
    try:
        ActionChains(driver).move_to_element(el).pause(0.1).click().perform()
        return True
    except Exception:
        return False

def find_first_result_element(driver, timeout=10):
    # Tập selector dự phòng cho item kết quả trên trang search_result
    selectors = [
        "a[href*='poiId=']",                               # ưu tiên link có sẵn URL chi tiết
        ".search-result .list-item",
        ".list-result .list-item",
        ".result-list .result-item",
        ".poi-list .poi-item",
        ".search-item",
        ".result-item",
        ".list-item",
        "[poiid]", "[data-poiid]"                          # nhiều trang gắn attr này
    ]
    end = time.time() + timeout
    while time.time() < end:
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                els = [e for e in els if e.is_displayed()]
                if els:
                    return sel, els[0]
            except Exception:
                continue
        time.sleep(0.2)
    return None, None

# ===== Main ==================================================================
df = pd.read_excel(EXCEL_PATH)
keywords = df['Phường/xã mới'].dropna().astype(str).str.strip()
keywords = [kw for kw in keywords if kw]   # bỏ trống

print(f"✅ Đọc {len(keywords)} phường từ file.")

opt = webdriver.ChromeOptions()
opt.add_argument("--start-maximized")
driver = webdriver.Chrome(options=opt)

results = []

try:
    driver.get(BASE_URL)
    # chờ ô tìm kiếm
    def get_search_box():
        return WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Tìm kiếm']"))
        )

    for kw in keywords:
        print(f"\n🔎 Đang xử lý: {kw}")
        try:
            # — Gõ từ khóa & Enter để vào trang search_result
            search_box = get_search_box()
            search_box.clear()
            time.sleep(0.2)
            search_box.send_keys(kw)

            # chờ dropdown xuất hiện để đảm bảo đã có kết quả
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".vtmapgl-ctrl-geocoder--suggestion"))
            )
            # Enter để mở trang search_result
            search_box.send_keys(Keys.ENTER)

            # chờ URL chuyển sang search_result hoặc danh sách hiện ra
            try:
                wait_url_contains(driver, "mode=search_result", timeout=8)
            except Exception:
                # một số trường hợp URL không đổi ngay, chờ danh sách
                pass

            # chờ item đầu tiên của danh sách kết quả
            sel, first_el = find_first_result_element(driver, timeout=10)
            if not first_el:
                raise RuntimeError("Không tìm thấy item kết quả đầu tiên trên trang search_result.")

            # nếu bắt được thẻ <a href*='poiId='> thì lấy trực tiếp URL, khỏi click
            if sel == "a[href*='poiId=']":
                url = first_el.get_attribute("href")
                # Nếu href tương đối, chuyển sang tuyệt đối
                if url and url.startswith("/"):
                    url = "https://maps.viettel.vn" + url
                if url:
                    results.append({"Phường/xã mới": kw, "URL": url})
                    print(f"✅ (href) URL cho {kw}: {url}")
                    continue  # sang từ khóa tiếp theo

            # nếu không có href, bắt buộc click vào item đầu tiên
            if not click_element_hard(driver, first_el):
                raise RuntimeError("Không click được item đầu tiên trong danh sách.")

            # chờ URL có tham số pt=
            WebDriverWait(driver, 10).until(lambda d: "pt=" in d.current_url)
            final_url = driver.current_url
            print(f"✅ URL cho {kw}: {final_url}")
            results.append({"Phường/xã mới": kw, "URL": final_url})

            # nhỏ: đợi nhẹ cho UI ổn định trước khi vòng tiếp theo
            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️ Lỗi với {kw}: {e}")
            results.append({"Phường/xã mới": kw, "URL": None})
            # quay lại trang maps gốc để reset trạng thái cho vòng sau
            driver.get(BASE_URL)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Tìm kiếm']"))
            )
finally:
    driver.quit()

pd.DataFrame(results).to_excel(OUTPUT_PATH, index=False)
print(f"\n📂 Đã lưu danh sách URL vào: {OUTPUT_PATH}")
