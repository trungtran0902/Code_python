import json
import math
import os
import re
import time
from datetime import datetime

from openpyxl import Workbook
from playwright.sync_api import sync_playwright


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = os.path.join(SCRIPT_DIR, "google_profile")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "google_maps_cookies.json")
MAPS_URL = "https://www.google.com/maps?hl=vi"
END_OF_LIST_MARKERS = [
    "Bạn đã xem hết danh sách này.",
    "Ban da xem het danh sach nay.",
    "You've reached the end of the list.",
]


# ======================
# UTILS
# ======================
def clean_cell(value):
    return "" if value is None else str(value).strip()


def normalize_phone_vn(phone):
    if not phone:
        return ""

    digits = re.sub(r"\D", "", phone)
    if not digits:
        return ""
    if digits.startswith("84"):
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+84{digits[1:]}"
    return f"+{digits}"


def extract_latlng_from_url(url):
    match = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", url)
    if match:
        return match.group(1), match.group(2)

    match = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if match:
        return match.group(1), match.group(2)

    return "", ""


def distance_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def has_end_of_list_marker(page):
    try:
        page_text = page.locator("body").text_content() or ""
        return any(marker in page_text for marker in END_OF_LIST_MARKERS)
    except Exception:
        return False


# ======================
# SCROLL
# ======================
def scroll_results(
    page,
    max_idle_rounds=5,
    max_total_rounds=120,
    wait_after_scroll_seconds=2,
    idle_wait_seconds=6,
):
    feed = page.locator("div[role='feed']")
    if feed.count() == 0:
        return False

    last_height = 0
    last_link_count = 0
    idle_rounds = 0

    for round_index in range(1, max_total_rounds + 1):
        try:
            if has_end_of_list_marker(page):
                print(f"Da thay dong ket thuc danh sach o lan cuon {round_index}.")
                return True

            feed.first.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
            print(f"Cuon lan {round_index}: cho {wait_after_scroll_seconds}s de tai them danh sach...")
            page.wait_for_timeout(int(wait_after_scroll_seconds * 1000))
            current_height = feed.first.evaluate("(el) => el.scrollHeight")
            current_link_count = len(get_place_links_from_list(page))

            if has_end_of_list_marker(page):
                print(f"Da thay dong ket thuc danh sach o lan cuon {round_index}.")
                return True

            if current_height == last_height and current_link_count == last_link_count:
                print(f"Cuon lan {round_index}: danh sach chua doi, cho them {idle_wait_seconds}s...")
                page.wait_for_timeout(int(idle_wait_seconds * 1000))
                current_height = feed.first.evaluate("(el) => el.scrollHeight")
                current_link_count = len(get_place_links_from_list(page))

            if has_end_of_list_marker(page):
                print(f"Da thay dong ket thuc danh sach o lan cuon {round_index}.")
                return True

            if current_height == last_height and current_link_count == last_link_count:
                idle_rounds += 1
            else:
                idle_rounds = 0

            print(f"Cuon lan {round_index}: links={current_link_count}, height={current_height}")

            if idle_rounds >= max_idle_rounds:
                break

            last_height = current_height
            last_link_count = current_link_count
        except Exception:
            break

    return feed.count() > 0


def scroll_detail_panel(page, max_rounds=10):
    panel = page.locator("div[role='main']")
    if panel.count() == 0:
        return

    last_height = 0
    for _ in range(max_rounds):
        try:
            panel.first.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
            time.sleep(0.12)
            current_height = panel.first.evaluate("(el) => el.scrollHeight")
            if current_height == last_height:
                break
            last_height = current_height
        except Exception:
            break


# ======================
# BASIC FIELDS
# ======================
def get_address(page):
    selectors = [
        "button[data-item-id='address']",
        "button[aria-label^='Dia chi']",
        "button[aria-label^='Địa chỉ']",
        "div[aria-label^='Dia chi']",
        "div[aria-label^='Địa chỉ']",
    ]
    for selector in selectors:
        loc = page.locator(selector)
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
    return ""


def get_phone(page):
    loc = page.locator("button[data-item-id^='phone']")
    return (loc.first.text_content() or "").strip() if loc.count() > 0 else ""


def get_website(page):
    loc = page.locator("a[data-item-id='authority']")
    return loc.first.get_attribute("href") if loc.count() > 0 else ""


def get_located_in(page):
    try:
        loc = page.locator("text=/Nam o:|Nằm ở:/")
        if loc.count() > 0:
            text = loc.first.text_content() or ""
            return text.replace("Nam o:", "").replace("Nằm ở:", "").strip()
    except Exception:
        pass
    return ""


# ======================
# OPENING HOURS
# ======================
def expand_opening_hours_block(page):
    scroll_detail_panel(page)
    candidates = [
        "button:has-text('Gio')",
        "button:has-text('Giờ')",
        "button:has-text('Mo cua')",
        "button:has-text('Mở cửa')",
        "button:has-text('Dong cua')",
        "button:has-text('Đóng cửa')",
        "div[role='button']:has-text('Gio')",
        "div[role='button']:has-text('Giờ')",
        "div[role='button']:has-text('Mo cua')",
        "div[role='button']:has-text('Mở cửa')",
        "div[role='button']:has-text('Dong cua')",
        "div[role='button']:has-text('Đóng cửa')",
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
    ]
    for selector in candidates:
        loc = page.locator(selector)
        if loc.count() > 0:
            try:
                loc.first.scroll_into_view_if_needed()
                time.sleep(0.2)
                loc.first.click(force=True)
                page.wait_for_selector("text=/Thu|Thứ|Chu|Chủ/", timeout=6000)
                time.sleep(0.2)
                return True
            except Exception:
                pass
    return False


def scan_opening_hours_by_rows(page):
    hours = {}
    try:
        panel = page.locator("div[role='main']")
        if panel.count() > 0:
            panel_text = panel.first.text_content() or ""
            pattern = (
                r"(Thu\s+(?:Hai|Ba|Tu|Tư|Nam|Năm|Sau|Sáu|Bay|Bảy)|"
                r"Chu\s+Nhat|Chủ\s+Nhật)\s*"
                r"([0-9:–-]+\s*(?:–|-)\s*[0-9:–-]+|Dong cua|Đóng cửa|"
                r"Mo 24 gio|Mở 24 giờ)"
            )
            matches = re.findall(pattern, panel_text, re.IGNORECASE)
            for day_name, time_text in matches:
                if time_text:
                    hours[day_name.strip()] = time_text.strip()
            if hours:
                return hours
    except Exception:
        pass
    return hours


def get_opening_hours_full_fallback(page):
    selectors = [
        "div[role='dialog']",
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
        "div[role='main'] [data-item-id='oh']",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue

            text = normalize_hours_text(loc.first.text_content() or "")
            aria_label = normalize_hours_text(loc.first.get_attribute("aria-label") or "")
            title = normalize_hours_text(loc.first.get_attribute("title") or "")
            merged = " | ".join([part for part in [text, aria_label, title] if part])
            if merged and is_probably_hours_text(merged):
                return merged
        except Exception:
            pass
    return ""


def get_opening_hours_today(page):
    selectors = [
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
        "button[aria-label*='Mo cua']",
        "button[aria-label*='Mở cửa']",
        "button[aria-label*='Dong cua']",
        "button[aria-label*='Đóng cửa']",
    ]
    for selector in selectors:
        loc = page.locator(selector)
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
    return ""


def normalize_hours_text(text):
    if not text:
        return ""
    cleaned = str(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def looks_like_day_label(text):
    normalized = normalize_hours_text(text).lower()
    day_tokens = [
        "thứ",
        "thu",
        "chủ nhật",
        "chu nhat",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    return any(token in normalized for token in day_tokens)


def is_probably_hours_text(text):
    normalized = normalize_hours_text(text).lower()
    if not normalized:
        return False

    has_day = looks_like_day_label(normalized)
    has_time = bool(re.search(r"\d{1,2}(?::\d{2})?", normalized))
    has_hours_keyword = any(
        token in normalized
        for token in [
            "mở cửa",
            "mo cua",
            "đóng cửa",
            "dong cua",
            "24 giờ",
            "24 gio",
            "open",
            "closed",
        ]
    )
    return has_day or (has_time and has_hours_keyword)


def expand_opening_hours_block(page):
    scroll_detail_panel(page)
    candidates = [
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
        "button:has-text('Giờ')",
        "button:has-text('Gio')",
        "button:has-text('Mở cửa')",
        "button:has-text('Mo cua')",
        "button:has-text('Đóng cửa')",
        "button:has-text('Dong cua')",
        "div[role='button']:has-text('Giờ')",
        "div[role='button']:has-text('Gio')",
    ]

    for selector in candidates:
        loc = page.locator(selector)
        if loc.count() == 0:
            continue
        try:
            loc.first.scroll_into_view_if_needed()
            time.sleep(0.2)
            loc.first.click(force=True)
            try:
                page.wait_for_selector("div[role='dialog']", timeout=3000)
            except Exception:
                pass
            page.wait_for_timeout(800)
            return True
        except Exception:
            continue
    return False


def scan_opening_hours_by_rows(page):
    hours = {}

    row_selectors = [
        "div[role='dialog'] table tr",
        "div[role='dialog'] div[role='row']",
        "div[role='dialog'] li",
        "div[role='main'] table tr",
        "div[role='main'] div[role='row']",
    ]

    for selector in row_selectors:
        try:
            rows = page.locator(selector)
            for index in range(rows.count()):
                row_text = normalize_hours_text(rows.nth(index).text_content() or "")
                if not row_text or not looks_like_day_label(row_text):
                    continue

                parts = [part.strip() for part in re.split(r"\n|  +", row_text) if part.strip()]
                if len(parts) >= 2:
                    day_name = parts[0]
                    time_text = " ".join(parts[1:])
                else:
                    match = re.match(
                        r"^(.*?(?:Thứ\s*\w+|Thu\s*\w+|Chủ nhật|Chu nhat|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\s+(.*)$",
                        row_text,
                        re.IGNORECASE,
                    )
                    if not match:
                        continue
                    day_name = normalize_hours_text(match.group(1))
                    time_text = normalize_hours_text(match.group(2))

                if day_name and time_text:
                    hours[day_name] = time_text
            if hours:
                return hours
        except Exception:
            pass

    try:
        containers = [
            page.locator("div[role='dialog']"),
            page.locator("div[role='main']"),
        ]
        for container in containers:
            if container.count() == 0:
                continue
            panel_text = normalize_hours_text(container.first.text_content() or "")
            if not is_probably_hours_text(panel_text):
                continue
            pattern = (
                r"(Thứ\s*(?:Hai|Ba|Tư|Tu|Năm|Nam|Sáu|Sau|Bảy|Bay)|"
                r"Thu\s*(?:Hai|Ba|Tu|Nam|Sau|Bay)|"
                r"Chủ nhật|Chu nhat|"
                r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*"
                r"([0-9:hH–—\\-]+\s*(?:–|—|-)\s*[0-9:hH–—\\-]+|"
                r"Đóng cửa|Dong cua|Mở 24 giờ|Mo 24 gio|Open 24 hours|Closed)"
            )
            matches = re.findall(pattern, panel_text, re.IGNORECASE)
            for day_name, time_text in matches:
                if time_text:
                    hours[normalize_hours_text(day_name)] = normalize_hours_text(time_text)
            if hours:
                return hours
    except Exception:
        pass

    return hours


# ======================
# LIGHT FILTER
# ======================
def get_basic_poi_for_filter(page):
    try:
        name = (page.locator("h1").first.text_content() or "").strip()
        lat, lng = extract_latlng_from_url(page.url)
        return name, lat, lng
    except Exception:
        return None, "", ""


# ======================
# PARSE POI FULL
# ======================
def parse_current_poi(page, keyword):
    try:
        name = (page.locator("h1").first.text_content() or "").strip()
        if not name:
            return None
    except Exception:
        return None

    scroll_detail_panel(page)
    address = get_address(page)
    located_in = get_located_in(page)
    phone = normalize_phone_vn(get_phone(page))
    website = get_website(page)
    opening_today = get_opening_hours_today(page)

    opening_full = {}
    if expand_opening_hours_block(page):
        opening_full = scan_opening_hours_by_rows(page)

    if not opening_full:
        fallback_hours = get_opening_hours_full_fallback(page)
        if fallback_hours:
            opening_full = {"raw": fallback_hours}

    lat, lng = extract_latlng_from_url(page.url)

    return {
        "keyword": keyword,
        "name": name,
        "address": address,
        "located_in": located_in,
        "phone": phone,
        "website": website,
        "opening_hours_today": opening_today,
        "opening_hours_full": json.dumps(opening_full, ensure_ascii=False),
        "lat": lat,
        "lng": lng,
        "url": page.url,
    }


# ======================
# GET LINKS
# ======================
def get_place_links_from_list(page):
    try:
        return page.eval_on_selector_all(
            "a[href*='/maps/place/']",
            "els => [...new Set(els.map(e => e.href))]"
        )
    except Exception:
        return []


def collect_all_place_links(page):
    has_feed = scroll_results(page)
    if not has_feed:
        return []

    links = get_place_links_from_list(page)
    print(f"Da thu duoc {len(links)} link chi tiet tu danh sach.")
    return links


def reset_to_maps_home(page):
    page.goto(MAPS_URL, timeout=60000, wait_until="domcontentloaded")
    time.sleep(2)


# ======================
# FOCUS LOCATION
# ======================
def focus_location_with_radius(page, loc_text, radius_km=0.5):
    try:
        lat, lng = [value.strip() for value in loc_text.split(",")]
        if radius_km <= 0.5:
            zoom = 17
        elif radius_km <= 1:
            zoom = 16
        elif radius_km <= 2:
            zoom = 15
        else:
            zoom = 14
        url = f"https://www.google.com/maps/@{lat},{lng},{zoom}z"
        page.goto(url, timeout=60000)
        time.sleep(2)
        return float(lat), float(lng)
    except Exception:
        return None, None


# ======================
# AUTOSAVE XLSX
# ======================
FIELDS = [
    "keyword",
    "name",
    "address",
    "located_in",
    "phone",
    "website",
    "opening_hours_today",
    "opening_hours_full",
    "lat",
    "lng",
    "url",
]


def save_xlsx(path, data):
    wb = Workbook()
    ws = wb.active
    ws.append(FIELDS)
    for row in data:
        ws.append([row.get(key, "") for key in FIELDS])
    wb.save(path)


def save_login_cookies(context):
    storage = context.storage_state()
    with open(COOKIE_FILE, "w", encoding="utf-8") as file:
        json.dump(storage, file, ensure_ascii=False, indent=2)
    print("Da luu cookie/session vao:", COOKIE_FILE)


def is_probably_logged_in(page):
    selectors = [
        "a[aria-label*='Tài khoản Google']",
        "a[aria-label*='Tai khoan Google']",
        "button[aria-label*='Tài khoản Google']",
        "button[aria-label*='Tai khoan Google']",
        "img[alt*='Ảnh hồ sơ']",
        "img[alt*='Anh ho so']",
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


def ensure_google_login(page, context):
    page.goto(MAPS_URL, timeout=60000)
    time.sleep(2)

    if is_probably_logged_in(page):
        print("Da co phien dang nhap san trong profile.")
        save_login_cookies(context)
        return

    print("Buoc 1: dang nhap Google de xem duoc nhieu danh sach hon.")
    print("Sau khi dang nhap xong, script se tu dong phat hien va luu cookie/session.")

    login_timeout_seconds = 300
    poll_interval_seconds = 2
    waited_seconds = 0

    while waited_seconds < login_timeout_seconds:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass

        if is_probably_logged_in(page):
            print("Da phat hien dang nhap thanh cong.")
            break

        current_url = page.url or ""
        if "google.com/maps" in current_url and "accounts.google.com" not in current_url:
            try:
                search_box = page.locator("input[role='combobox']")
                if search_box.count() > 0:
                    print("Da quay lai Google Maps sau khi dang nhap.")
                    break
            except Exception:
                pass

        time.sleep(poll_interval_seconds)
        waited_seconds += poll_interval_seconds

    if waited_seconds >= login_timeout_seconds:
        raise TimeoutError("Qua thoi gian cho dang nhap Google. Hay chay lai script va dang nhap lai.")

    time.sleep(2)

    try:
        if "google.com/maps" not in (page.url or ""):
            page.goto(MAPS_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
    except Exception:
        pass

    save_login_cookies(context)


# ======================
# CRAWL 1 KEYWORD
# ======================
def crawl_google_maps_keyword(page, keyword, center_lat=None, center_lng=None, radius_km=0.5):
    results = []
    reset_to_maps_home(page)
    search_box = page.wait_for_selector("input[role='combobox']", timeout=15000)
    search_box.click()
    search_box.press("Control+A")
    search_box.press("Delete")
    search_box.fill(keyword)
    search_box.press("Enter")
    try:
        page.wait_for_selector("div[role='feed'], h1", timeout=8000)
    except Exception:
        pass
    time.sleep(5)

    links = collect_all_place_links(page)
    if not links:
        print("Khong lay duoc danh sach ket qua o khung ben trai.")
        return results

    for index, link in enumerate(links, 1):
        try:
            page.goto(link, timeout=60000)
            time.sleep(0.8)

            name, lat, lng = get_basic_poi_for_filter(page)
            if not name:
                continue

            if center_lat is not None and center_lng is not None and lat and lng:
                distance = distance_km(center_lat, center_lng, float(lat), float(lng))
                if distance > radius_km:
                    print(f"   Ngoai {radius_km}km: {name} ({round(distance * 1000)} m)")
                    continue

            poi = parse_current_poi(page, keyword)
            if poi:
                results.append(poi)
                print(f"OK {keyword} | {index}/{len(links)}: {poi['name']}")

        except Exception as exc:
            print("Loi", keyword, exc)
    return results


# ======================
# MAIN
# ======================
if __name__ == "__main__":
    keyword = clean_cell(input("Nhap keyword tim kiem Google Maps: "))
    if not keyword:
        print("Khong co keyword de chay.")
        raise SystemExit(1)

    rows_data = [(keyword, "")]
    autosave_path = os.path.join(SCRIPT_DIR, "autosave_temp.xlsx")
    all_results = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=CHROME_PATH,
            headless=False,
            locale="vi-VN",
            viewport={"width": 1280, "height": 800},
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        ensure_google_login(page, context)

        for index, (current_keyword, loc) in enumerate(rows_data, 1):
            print(f"\nDang xu ly {index}/{len(rows_data)}: {current_keyword}")
            print("   Tim truc tiep theo keyword")

            results = crawl_google_maps_keyword(
                page,
                current_keyword,
            )
            all_results.extend(results)
            if all_results:
                save_xlsx(autosave_path, all_results)
                print("Autosave:", autosave_path)
            save_login_cookies(context)
            time.sleep(1)

        context.close()

    output_path = os.path.join(
        SCRIPT_DIR,
        f"googlemaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )
    save_xlsx(output_path, all_results)
    print("File cuoi:", output_path)
    print("File autosave:", autosave_path)
