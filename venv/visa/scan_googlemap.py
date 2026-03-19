import json
import os
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "google_maps_cookies.json")
MAPS_URL = "https://www.google.com/maps"
GOOGLE_HOME_URL = "https://www.google.com"
END_OF_LIST_MARKERS = [
    "Bạn đã xem hết danh sách này.",
    "Ban da xem het danh sach nay.",
    "You've reached the end of the list.",
]


def create_driver():
    options = Options()
    options.headless = False
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    driver.maximize_window()
    return driver


def save_cookies(driver, cookie_file=COOKIE_FILE):
    cookies = driver.get_cookies()
    with open(cookie_file, "w", encoding="utf-8") as file:
        json.dump(cookies, file, ensure_ascii=False, indent=2)
    print(f"Da luu cookie vao: {cookie_file}")


def load_cookies(driver, cookie_file=COOKIE_FILE):
    if not os.path.exists(cookie_file):
        return False

    with open(cookie_file, "r", encoding="utf-8") as file:
        cookies = json.load(file)

    driver.get(GOOGLE_HOME_URL)
    for cookie in cookies:
        cookie = dict(cookie)
        cookie.pop("sameSite", None)
        if "expiry" in cookie:
            try:
                cookie["expiry"] = int(cookie["expiry"])
            except (TypeError, ValueError):
                cookie.pop("expiry", None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            continue

    driver.get(MAPS_URL)
    driver.refresh()
    print(f"Da nap cookie tu: {cookie_file}")
    return True


def ensure_login_and_cookies(driver):
    loaded = load_cookies(driver)
    if loaded:
        return

    driver.get(MAPS_URL)
    print("Chua co cookie Google Maps.")
    print("Hay dang nhap Google tren cua so Chrome vua mo.")
    input("Dang nhap xong va mo duoc Google Maps, nhan Enter de luu cookie...")
    save_cookies(driver)
    driver.get(MAPS_URL)


def open_google_maps_and_search(driver, query):
    driver.get(MAPS_URL)

    search_box = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "searchboxinput"))
    )
    search_box.clear()
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)

    WebDriverWait(driver, 20).until(
        lambda d: "/search/" in d.current_url or d.find_elements(By.CSS_SELECTOR, 'div[role="feed"]')
    )


def get_results_feed(driver):
    candidates = [
        (By.CSS_SELECTOR, 'div[role="feed"]'),
        (By.CSS_SELECTOR, 'div[aria-label][role="feed"]'),
    ]

    for by, selector in candidates:
        try:
            return WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by, selector))
            )
        except TimeoutException:
            continue

    raise TimeoutException("Khong tim thay danh sach ket qua Google Maps.")


def has_end_of_list(driver):
    page_source = driver.page_source
    return any(marker in page_source for marker in END_OF_LIST_MARKERS)


def scroll_until_end_of_results(driver, pause_seconds=2, max_attempts=80):
    feed = get_results_feed(driver)
    stagnant_rounds = 0
    last_height = 0

    for attempt in range(1, max_attempts + 1):
        if has_end_of_list(driver):
            print(f"Da thay thong bao ket thuc danh sach o lan cuon {attempt}.")
            return True

        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight;",
            feed,
        )
        time.sleep(pause_seconds)

        if has_end_of_list(driver):
            print(f"Da thay thong bao ket thuc danh sach o lan cuon {attempt}.")
            return True

        current_height = driver.execute_script("return arguments[0].scrollHeight;", feed)
        if current_height == last_height:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
            last_height = current_height

        print(f"Cuon lan {attempt}: chieu cao danh sach = {current_height}")

        if stagnant_rounds >= 5:
            break

    print("Khong xac nhan duoc dong 'Ban da xem het danh sach nay.' sau khi cuon.")
    return False


def collect_result_links(driver):
    anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"], a[href*="/place/"]')
    results = []
    seen = set()

    for anchor in anchors:
        href = (anchor.get_attribute("href") or "").strip()
        if not href or href in seen:
            continue

        name = (anchor.get_attribute("aria-label") or anchor.text or "").strip()
        if not name:
            continue

        seen.add(href)
        results.append({"name": name, "url": href})

    print(f"Thu duoc {len(results)} lien ket chi tiet sau khi cuon xong.")
    return results


def wait_for_place_title(driver):
    selectors = [
        'h1[class*="fontHeadlineLarge"]',
        "h1.DUwDvf",
        "h1",
    ]

    for selector in selectors:
        try:
            element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            text = element.text.strip()
            if text:
                return text
        except TimeoutException:
            continue

    raise TimeoutException("Khong tai duoc tieu de trang chi tiet.")


def open_detail_pages(driver, results, limit=None):
    detail_rows = []
    total = len(results) if limit is None else min(limit, len(results))

    for index, item in enumerate(results[:total], start=1):
        print(f"Mo chi tiet {index}/{total}: {item['name']}")
        driver.get(item["url"])

        try:
            title = wait_for_place_title(driver)
        except TimeoutException:
            title = item["name"]

        detail_rows.append(
            {
                "name_from_list": item["name"],
                "detail_title": title,
                "url": driver.current_url,
            }
        )
        time.sleep(1)

    return detail_rows


def main():
    driver = create_driver()

    try:
        ensure_login_and_cookies(driver)

        lat, lng = 10.762622, 106.660172
        search_query = f"{lat}, {lng}"
        open_google_maps_and_search(driver, search_query)

        reached_end = scroll_until_end_of_results(driver)
        if not reached_end:
            print("Dung tai day de tranh vao chi tiet khi danh sach chua du tai.")
            return

        results = collect_result_links(driver)
        if not results:
            print("Khong lay duoc lien ket chi tiet nao tu danh sach.")
            return

        details = open_detail_pages(driver, results)
        print("Da mo xong cac trang chi tiet:")
        for row in details:
            print(json.dumps(row, ensure_ascii=False))

        save_cookies(driver)
        input("Nhan Enter de dong trinh duyet...")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
