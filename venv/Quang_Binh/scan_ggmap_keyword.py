import time
import csv
import os
import re
from playwright.sync_api import sync_playwright
from datetime import datetime

# ======================
# 🔎 NHẬP TỪ CONSOLE
# ======================
location_input = input("📍 Nhập location (lat,lng): ").strip()
keyword = input("🔎 Nhập keyword tìm kiếm: ").strip()

if not location_input or not keyword:
    print("❌ Location và Keyword không được để trống")
    exit()

# ======================
# 🧭 PARSE lat,lng
# ======================
def parse_latlng(text):
    match = re.match(r"\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*", text)
    if not match:
        return None, None
    return match.group(1), match.group(3)

center_lat, center_lng = parse_latlng(location_input)
if not center_lat:
    print("❌ Location phải đúng dạng lat,lng (vd: 10.2435,106.3752)")
    exit()

# ======================
# 📁 FILE CSV THEO KEYWORD
# ======================
def sanitize_filename(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text

safe_keyword = sanitize_filename(keyword)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# Lấy thư mục chứa file .py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

output_file = os.path.join(
    BASE_DIR,
    f"googlemaps_{safe_keyword}_{timestamp}.csv"
)

# ======================
# 🧭 TÁCH lat,lng TỪ URL
# ======================
def extract_latlng_from_url(url):
    m1 = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m1:
        return m1.group(1), m1.group(2)
    m2 = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
    if m2:
        return m2.group(1), m2.group(2)
    return "", ""

# ======================
# 💾 AUTOSAVE CSV
# ======================
def save_to_csv(data):
    file_exists = os.path.isfile(output_file)
    with open(output_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "center_lat","center_lng","keyword",
                "name","address","phone","website","open_hours",
                "lat","lng","url"
            ]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)
        f.flush()

# ======================
# 🌀 SCROLL DANH SÁCH
# ======================
def scroll_results(page, max_round=40):
    feed = page.query_selector("div[role='feed']")
    if not feed:
        return False
    last_height = 0
    for _ in range(max_round):
        page.evaluate("(el) => el.scrollBy(0, el.scrollHeight)", feed)
        time.sleep(1.2)
        new_height = page.evaluate("(el) => el.scrollHeight", feed)
        if new_height == last_height:
            break
        last_height = new_height
    return True

# ======================
# 📍 LẤY ĐỊA CHỈ
# ======================
def get_address(page):
    sels = [
        "button[data-item-id='address']",
        "button[aria-label^='Địa chỉ']",
        "div[aria-label^='Địa chỉ']"
    ]
    for s in sels:
        loc = page.locator(s)
        if loc.count() > 0:
            return loc.first.text_content().strip()
    return "N/A"

def get_phone(page):
    sels = [
        "button[data-item-id^='phone']",
        "button[aria-label^='Số điện thoại']",
        "div[aria-label^='Số điện thoại']"
    ]
    for s in sels:
        loc = page.locator(s)
        if loc.count() > 0:
            return loc.first.text_content().strip()
    return "N/A"

def get_website(page):
    sels = [
        "a[data-item-id='authority']",
        "a[aria-label^='Trang web']",
        "a[aria-label^='Website']"
    ]
    for s in sels:
        loc = page.locator(s)
        if loc.count() > 0:
            return loc.first.get_attribute("href")
    return "N/A"

def get_open_hours(page):
    sels = [
        "div[aria-label^='Giờ mở cửa']",
        "button[aria-label^='Giờ mở cửa']",
        "div[aria-label^='Open']"
    ]
    for s in sels:
        loc = page.locator(s)
        if loc.count() > 0:
            return loc.first.text_content().strip()
    return "N/A"

# ======================
# 🚀 CRAWL GOOGLE MAPS
# ======================
def crawl_google_maps(center_lat, center_lng, keyword):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(locale="vi-VN", viewport={"width":1280,"height":800})
        page = context.new_page()

        print(f"📍 Di chuyển tới tọa độ: {center_lat},{center_lng}")
        page.goto(f"https://www.google.com/maps/@{center_lat},{center_lng},14z?hl=vi", timeout=60000)
        time.sleep(5)

        print(f"🔎 Tìm kiếm keyword: {keyword}")
        search_box = page.wait_for_selector("input[role='combobox']", timeout=10000)
        search_box.fill(keyword)
        time.sleep(1)
        search_box.press("Enter")
        time.sleep(6)

        print("🌀 Đang kiểm tra danh sách kết quả...")
        feed = page.query_selector("div[role='feed']")
        if feed:
            print("➡ Có danh sách, bắt đầu cuộn...")
            scroll_results(page)
            links = page.eval_on_selector_all(
                "a[href*='/maps/place/']",
                "els => [...new Set(els.map(el => el.href))]"
            )
        else:
            print("➡ Không có danh sách – chỉ có 1 địa điểm")
            links = [page.url]

        print(f"📌 Số địa điểm lấy được: {len(links)}")

        seen = set()
        for idx, link in enumerate(links):
            if link in seen:
                continue
            seen.add(link)
            try:
                page.goto(link, timeout=60000)
                time.sleep(4)

                try:
                    page.wait_for_selector("h1", timeout=5000)
                    name = page.locator("h1").first.text_content()
                except:
                    name = "N/A"

                address = get_address(page)
                phone = get_phone(page)
                website = get_website(page)
                open_hours = get_open_hours(page)
                lat, lng = extract_latlng_from_url(page.url)

                print(f"✔ {idx+1:03d}: {name}")
                print(f"   📍 {address}")
                print(f"   📞 {phone}")
                print(f"   🌐 {website}")
                print(f"   ⏰ {open_hours}")
                print(f"   🧭 {lat},{lng}")

                save_to_csv({
                    "center_lat": center_lat,
                    "center_lng": center_lng,
                    "keyword": keyword,
                    "name": name,
                    "address": address,
                    "phone": phone,
                    "website": website,
                    "open_hours": open_hours,
                    "lat": lat,
                    "lng": lng,
                    "url": page.url
                })

            except Exception as e:
                print(f"❌ Lỗi entry {idx+1}: {e}")

        browser.close()
        print(f"\n✅ Hoàn tất – dữ liệu đã lưu vào:\n{output_file}")

# ======================
# ▶️ RUN
# ======================
crawl_google_maps(center_lat, center_lng, keyword)
