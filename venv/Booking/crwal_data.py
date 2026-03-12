import json
import os
import re
import sys
import tempfile
from datetime import datetime
from time import sleep
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup
from openpyxl.utils.exceptions import IllegalCharacterError
import undetected_chromedriver as uc
from selenium.common.exceptions import InvalidSessionIdException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Doi tinh/thanh tai day, vi du: "Ha Noi", "Da Nang", "Can Tho"
SEARCH_CITY = "Hue, Viet Nam"
CHECKIN_DATE = "2026-03-19"
CHECKOUT_DATE = "2026-03-20"
ADULTS = 2
ROOMS = 1
CHILDREN = 0

MAX_PAGES = 200
PAGE_SIZE = 25
EARLY_STOP_EMPTY_PAGES = 10
DETAILS_LIMIT = 0
DETAILS_AUTOSAVE_EVERY = 5

INTERACTIVE_LOGIN = False
USE_LOAD_MORE_MODE = True
AUTO_FALLBACK_TO_OFFSET = False
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies_booking.json")
OUTPUT_BASENAME = "booking_hotels_Hue"
OUTPUT_XLSX = os.path.join(BASE_DIR, "booking_hotels_Hue.xlsx")
OUTPUT_CSV = os.path.join(BASE_DIR, "booking_hotels_Hue.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "booking_hotels_Hue.json")
OUTPUT_COLUMNS = [
    "hotel_name",
    "address",
    "score_text",
    "hotel_url",
    "hotel_name_detail",
    "address_detail",
    "lat",
    "lng",
    "star_rating",
    "rating_value",
    "rating_count",
    "description",
    "metadata_json",
]
ILLEGAL_EXCEL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")


def build_search_url():
    return (
        "https://www.booking.com/searchresults.vi.html?"
        f"ss={quote_plus(SEARCH_CITY)}"
        f"&checkin={CHECKIN_DATE}"
        f"&checkout={CHECKOUT_DATE}"
        f"&group_adults={ADULTS}"
        f"&no_rooms={ROOMS}"
        f"&group_children={CHILDREN}"
    )


def _build_options(headless):
    options = uc.ChromeOptions()
    options.headless = headless
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument(f"--user-data-dir={os.path.join(tempfile.gettempdir(), 'uc_booking_profile')}")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path
    return options


def start_driver(version_main=145, headless=False):
    try:
        return uc.Chrome(options=_build_options(headless), version_main=version_main)
    except Exception:
        try:
            return uc.Chrome(options=_build_options(headless), version_main=145)
        except Exception:
            return uc.Chrome(options=_build_options(True), version_main=145)


def save_cookies(driver, cookie_file=COOKIE_FILE):
    cookies = driver.get_cookies()
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def sanitize_excel_value(value):
    if isinstance(value, str):
        value = ILLEGAL_EXCEL_CHARS_RE.sub("", value)
        value = "".join(ch for ch in value if ch in "\t\n\r" or 32 <= ord(ch) <= 0xFFFD)
        return value[:32767]
    return value


def save_hotel_outputs(hotels):
    output_df = pd.DataFrame(hotels)
    for col in OUTPUT_COLUMNS:
        if col not in output_df.columns:
            output_df[col] = None
    ordered_columns = OUTPUT_COLUMNS + [col for col in output_df.columns if col not in OUTPUT_COLUMNS]
    output_df = output_df.reindex(columns=ordered_columns)

    excel_df = output_df.copy()
    for col in excel_df.columns:
        if excel_df[col].dtype == "object":
            excel_df[col] = excel_df[col].map(sanitize_excel_value)

    excel_path = OUTPUT_XLSX
    try:
        excel_df.to_excel(excel_path, index=False)
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = os.path.join(BASE_DIR, f"{OUTPUT_BASENAME}_{ts}.xlsx")
        try:
            excel_df.to_excel(excel_path, index=False)
            print(f"Khong ghi de duoc file dang mo. Da luu file moi: {excel_path}", flush=True)
        except Exception as exc:
            excel_path = None
            print(f"Khong the ghi file Excel du phong: {exc}", flush=True)
    except (IllegalCharacterError, ValueError) as exc:
        try:
            excel_df = excel_df.applymap(sanitize_excel_value)
            excel_df.to_excel(excel_path, index=False)
            print(f"Da lam sach du lieu va ghi lai file Excel sau loi: {exc}", flush=True)
        except Exception as retry_exc:
            excel_path = None
            print(f"Bo qua ghi Excel do loi du lieu: {retry_exc}", flush=True)
    except Exception as exc:
        excel_path = None
        print(f"Bo qua ghi Excel do loi khong xac dinh: {exc}", flush=True)

    csv_path = OUTPUT_CSV
    try:
        output_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(BASE_DIR, f"{OUTPUT_BASENAME}_{ts}.csv")
        output_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"Khong ghi de duoc file CSV dang mo. Da luu file moi: {csv_path}", flush=True)

    json_path = OUTPUT_JSON
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(hotels, f, ensure_ascii=False, indent=2)
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(BASE_DIR, f"{OUTPUT_BASENAME}_{ts}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(hotels, f, ensure_ascii=False, indent=2)
        print(f"Khong ghi de duoc file JSON dang mo. Da luu file moi: {json_path}", flush=True)

    return excel_path, csv_path, json_path


def load_cookies(driver, cookie_file=COOKIE_FILE):
    if not os.path.exists(cookie_file):
        return False
    driver.get("https://www.booking.com/")
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    for cookie in cookies:
        cookie.pop("sameSite", None)
        if "expiry" in cookie:
            try:
                cookie["expiry"] = int(cookie["expiry"])
            except Exception:
                cookie.pop("expiry", None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass
    driver.get(build_search_url())
    return True


def ensure_login_and_cookies(driver):
    loaded = load_cookies(driver)
    if loaded:
        print(f"Da nap cookie tu: {COOKIE_FILE}", flush=True)
        return

    print("Chua co file cookie. Mo Booking va crawl khong dang nhap.", flush=True)
    driver.get("https://www.booking.com/")
    if INTERACTIVE_LOGIN and sys.stdin and sys.stdin.isatty():
        input("Dang nhap xong, nhan Enter de luu cookie va tiep tuc crawl...")
        save_cookies(driver)
    driver.get(build_search_url())
    if os.path.exists(COOKIE_FILE):
        print(f"Da luu cookie: {COOKIE_FILE}", flush=True)


def normalize_address(address):
    if not address:
        return ""
    clean = re.sub(r"\s+", " ", str(address)).strip(" ,;-")
    parts = [p.strip() for p in re.split(r",|\||;", clean) if p.strip()]
    dedup_parts = []
    seen = set()
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            dedup_parts.append(part)
    if dedup_parts:
        return ", ".join(dedup_parts)
    return clean


def click_load_more_if_present(driver, wait_seconds=5):
    xpath_candidates = [
        "//button[contains(normalize-space(.), 'Tải thêm')]",
        "//button[contains(normalize-space(.), 'Hiển thị thêm')]",
        "//button[contains(normalize-space(.), 'Tải thêm kết quả')]",
        "//button[contains(normalize-space(.), 'Show more')]",
        "//button[contains(normalize-space(.), 'Load more')]",
        "//*[@role='button' and contains(normalize-space(.), 'Tải thêm')]",
        "//*[@role='button' and contains(normalize-space(.), 'Hiển thị thêm')]",
        "//*[@role='button' and contains(normalize-space(.), 'Show more')]",
        "//*[@data-testid and contains(@data-testid, 'load-more')]",
        "//*[@data-testid and contains(@data-testid, 'show-more')]",
    ]

    for xpath in xpath_candidates:
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
        except Exception:
            buttons = []
        for btn in buttons:
            if not btn.is_displayed():
                continue
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                sleep(0.4)
                btn.click()
                sleep(wait_seconds)
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    sleep(wait_seconds)
                    return True
                except Exception:
                    continue
    return False


def click_load_more_with_js(driver, wait_seconds=5):
    try:
        button = driver.execute_script(
            """
            const phrases = ['tải thêm', 'hiển thị thêm', 'tải thêm kết quả', 'show more', 'load more'];
            const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
            return nodes.find((node) => {
                const text = ((node.innerText || node.textContent || '') + ' ' + (node.getAttribute('aria-label') || '')).toLowerCase();
                const visible = !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
                return visible && phrases.some((phrase) => text.includes(phrase));
            }) || null;
            """
        )
    except Exception:
        button = None

    if button is None:
        return False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
        sleep(0.4)
        driver.execute_script("arguments[0].click();", button)
        sleep(wait_seconds)
        return True
    except Exception:
        return False


def scroll_results_page(driver, rounds=8, pause=1.2, allow_load_more=True):
    last_count = 0
    stable_rounds = 0
    for _ in range(rounds):
        driver.execute_script("window.scrollBy(0, Math.max(1200, window.innerHeight));")
        sleep(pause)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(0.8)
        clicked = False
        if allow_load_more:
            clicked = click_load_more_if_present(driver, wait_seconds=2)
            if not clicked:
                clicked = click_load_more_with_js(driver, wait_seconds=2)
        if clicked:
            sleep(1)
            driver.execute_script("window.scrollBy(0, 800);")
            sleep(0.6)
        current_count = len(driver.find_elements(By.CSS_SELECTOR, "div[data-testid='property-card']"))
        if current_count <= last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
        last_count = current_count
        if stable_rounds >= 2:
            break


def merge_hotels(base_hotels, extra_hotels):
    merged = list(base_hotels)
    seen = {
        item.get("hotel_url", "").split("?")[0]
        for item in base_hotels
        if item.get("hotel_url", "")
    }
    added = 0
    for item in extra_hotels:
        url_key = item.get("hotel_url", "").split("?")[0]
        if not url_key or url_key in seen:
            continue
        seen.add(url_key)
        merged.append(item)
        added += 1
    return merged, added


def crawl_with_load_more(driver, max_rounds=30):
    all_hotels = []
    seen = set()
    no_growth_rounds = 0

    driver.get(build_search_url())
    WebDriverWait(driver, 40).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "a[data-testid='title-link'], div[data-testid='property-card']")
        )
    )

    for round_idx in range(max_rounds):
        scroll_results_page(driver, rounds=3, pause=1.0)
        clicked = click_load_more_if_present(driver, wait_seconds=2)

        page_cards = extract_cards_from_results(driver)
        cards_on_page = len(page_cards)
        new_count = 0
        for item in page_cards:
            url_key = item.get("hotel_url", "").split("?")[0]
            if not url_key or url_key in seen:
                continue
            seen.add(url_key)
            all_hotels.append(item)
            new_count += 1

        print(
            f"LoadMore {round_idx + 1}/{max_rounds} - clicked={clicked} - cards={cards_on_page} - Hotel moi: {new_count} - Tong: {len(all_hotels)}",
            flush=True,
        )

        if new_count == 0 and not clicked:
            no_growth_rounds += 1
        else:
            no_growth_rounds = 0

        if all_hotels and no_growth_rounds >= 3:
            print(
                f"LoadMore dung sau {no_growth_rounds} vong khong co hotel moi. Bat dau crawl chi tiet.",
                flush=True,
            )
            break

    return all_hotels


def extract_cards_from_results(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = []
    for card in soup.select("div[data-testid='property-card']"):
        name_node = card.select_one("div[data-testid='title']")
        address_node = (
            card.select_one("[data-testid='address']")
            or card.select_one("span[data-testid='address']")
            or card.select_one("[data-testid='location']")
        )
        link_node = card.select_one("a[data-testid='title-link'][href]") or card.select_one("a[href*='/hotel/']")
        score_node = card.select_one("[data-testid='review-score'] [aria-hidden='true']")

        hotel_url = ""
        if link_node and link_node.get("href"):
            hotel_url = urljoin("https://www.booking.com", link_node.get("href"))

        cards.append(
            {
                "hotel_name": name_node.get_text(strip=True) if name_node else "",
                "address": normalize_address(address_node.get_text(" ", strip=True) if address_node else ""),
                "score_text": score_node.get_text(strip=True) if score_node else "",
                "hotel_url": hotel_url,
            }
        )
    return cards


def crawl_result_pages(driver, max_pages=MAX_PAGES):
    all_hotels = []
    seen = set()
    empty_pages = 0
    for page_idx in range(max_pages):
        offset = page_idx * PAGE_SIZE
        page_url = f"{build_search_url()}&offset={offset}"
        try:
            driver.get(page_url)
            WebDriverWait(driver, 40).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[data-testid='title-link'], div[data-testid='property-card']")
                )
            )
        except (TimeoutException, WebDriverException, InvalidSessionIdException):
            empty_pages += 1
            print(f"Trang {page_idx + 1}/{max_pages} - timeout/loi tai trang", flush=True)
            if empty_pages >= EARLY_STOP_EMPTY_PAGES:
                break
            continue

        # Mode offset: chi cuon de lazy-load card, khong click "Load more".
        scroll_results_page(driver, rounds=6, pause=1.0, allow_load_more=False)
        page_cards = extract_cards_from_results(driver)
        new_count = 0
        for item in page_cards:
            url_key = item.get("hotel_url", "").split("?")[0]
            if not url_key or url_key in seen:
                continue
            seen.add(url_key)
            all_hotels.append(item)
            new_count += 1
        print(f"Trang {page_idx + 1}/{max_pages} - Hotel moi: {new_count} - Tong: {len(all_hotels)}", flush=True)
        if new_count == 0:
            empty_pages += 1
        else:
            empty_pages = 0
        if empty_pages >= EARLY_STOP_EMPTY_PAGES:
            break
    return all_hotels


def _pick_hotel_ld_json(soup):
    scripts = soup.select("script[type='application/ld+json']")
    for script in scripts:
        raw = script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Hotel":
                    return item
        elif isinstance(data, dict):
            if data.get("@type") == "Hotel":
                return data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "Hotel":
                        return item
    return {}


def _extract_lat_lng_from_text(text):
    lat_patterns = [
        r'"latitude"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r'"lat"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r'"latitud"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r"b_map_center_latitude['\"]?\s*:\s*'?(-?\d+(?:\.\d+)?)'?",
        r"latitude\s*[=:]\s*'?(-?\d+(?:\.\d+)?)'?",
        r"lat\s*[=:]\s*'?(-?\d+(?:\.\d+)?)'?",
    ]
    lng_patterns = [
        r'"longitude"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r'"lng"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r'"longitud"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        r"b_map_center_longitude['\"]?\s*:\s*'?(-?\d+(?:\.\d+)?)'?",
        r"longitude\s*[=:]\s*'?(-?\d+(?:\.\d+)?)'?",
        r"lng\s*[=:]\s*'?(-?\d+(?:\.\d+)?)'?",
    ]

    lat = None
    lng = None
    for pattern in lat_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            lat = m.group(1)
            break
    for pattern in lng_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            lng = m.group(1)
            break
    if lat and lng:
        return lat, lng

    pair_patterns = [
        r"data-atlas-latlng\s*=\s*['\"]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*['\"]",
        r"center(?:=|%3D)(-?\d+(?:\.\d+)?)(?:,|%2C)(-?\d+(?:\.\d+)?)",
        r"markers(?:=|%3D)(-?\d+(?:\.\d+)?)(?:,|%2C)(-?\d+(?:\.\d+)?)",
        r"bbox=(?:-?\d+(?:\.\d+)?,){2}(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        r"[-_/](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:[/?&#]|$)",
    ]
    for pattern in pair_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1), m.group(2)
    return lat, lng


def _extract_lat_lng_from_url(url):
    if not url:
        return None, None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        lat = (qs.get("latitude") or qs.get("lat") or [None])[0]
        lng = (qs.get("longitude") or qs.get("lng") or [None])[0]
        if lat and lng:
            return lat, lng
    except Exception:
        pass

    m = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _extract_lat_lng_from_soup(soup):
    selectors = [
        "[data-atlas-latlng]",
        "[data-bbox]",
        "[data-testid*='map']",
        "[id*='map']",
        "[class*='map']",
        "a[href*='latitude=']",
        "a[href*='lat=']",
        "img[src*='center=']",
        "img[src*='markers=']",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            atlas = node.get("data-atlas-latlng", "")
            if atlas and "," in atlas:
                lat_raw, lng_raw = atlas.split(",", 1)
                return lat_raw.strip(), lng_raw.strip()

            for _, attr_value in node.attrs.items():
                if isinstance(attr_value, list):
                    attr_value = " ".join(str(v) for v in attr_value)
                attr_value = str(attr_value)
                lat_raw, lng_raw = _extract_lat_lng_from_text(attr_value)
                if lat_raw and lng_raw:
                    return lat_raw, lng_raw
                lat_raw, lng_raw = _extract_lat_lng_from_url(attr_value)
                if lat_raw and lng_raw:
                    return lat_raw, lng_raw
    return None, None


def extract_hotel_details(driver, hotel_url, fallback_name="", fallback_address=""):
    details = {
        "hotel_name_detail": fallback_name or "",
        "address_detail": normalize_address(fallback_address or ""),
        "lat": None,
        "lng": None,
        "star_rating": None,
        "rating_value": None,
        "rating_count": None,
        "description": "",
        "metadata_json": "",
    }

    if not hotel_url:
        return details

    try:
        driver.get(hotel_url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = driver.page_source
        ld_hotel = _pick_hotel_ld_json(soup)
        if ld_hotel:
            geo = ld_hotel.get("geo", {}) if isinstance(ld_hotel.get("geo"), dict) else {}
            aggregate = (
                ld_hotel.get("aggregateRating", {})
                if isinstance(ld_hotel.get("aggregateRating"), dict)
                else {}
            )
            star = ld_hotel.get("starRating")
            address_obj = ld_hotel.get("address", {})
            details["hotel_name_detail"] = ld_hotel.get("name", "")
            if isinstance(address_obj, dict):
                details["address_detail"] = ", ".join(
                    str(address_obj.get(k, "")).strip()
                    for k in ["streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"]
                    if str(address_obj.get(k, "")).strip()
                )
            elif isinstance(address_obj, str):
                details["address_detail"] = address_obj
            details["lat"] = geo.get("latitude")
            details["lng"] = geo.get("longitude")
            details["star_rating"] = (
                star.get("ratingValue") if isinstance(star, dict) else star
            )
            details["rating_value"] = aggregate.get("ratingValue")
            details["rating_count"] = aggregate.get("ratingCount")
            details["description"] = ld_hotel.get("description", "")
            details["metadata_json"] = json.dumps(ld_hotel, ensure_ascii=False)

        if not details["hotel_name_detail"]:
            title_node = soup.select_one("h2[data-testid='title'], h1")
            if title_node:
                details["hotel_name_detail"] = title_node.get_text(" ", strip=True)

        if not details["address_detail"]:
            addr_node = soup.select_one(
                "[data-node_tt_id='location_score_tooltip'] [data-testid='address'], "
                "[data-testid='address'], "
                "[data-testid='location-address'], "
                "span.hp_address_subtitle, "
                "a[data-testid='address-link'], "
                "div#showMap2 a"
            )
            if addr_node:
                details["address_detail"] = addr_node.get_text(" ", strip=True)

        if not details["lat"] or not details["lng"]:
            latlng_node = soup.select_one(
                "[data-atlas-latlng], [data-bbox], #hotel_sidebar_static_map, [id*='map']"
            )
            if latlng_node and latlng_node.get("data-atlas-latlng"):
                atlas = latlng_node.get("data-atlas-latlng", "")
                if "," in atlas:
                    lat_raw, lng_raw = atlas.split(",", 1)
                    details["lat"] = details["lat"] or lat_raw.strip()
                    details["lng"] = details["lng"] or lng_raw.strip()

        if not details["lat"] or not details["lng"]:
            lat_raw, lng_raw = _extract_lat_lng_from_soup(soup)
            details["lat"] = details["lat"] or lat_raw
            details["lng"] = details["lng"] or lng_raw

        if not details["lat"] or not details["lng"]:
            lat_raw, lng_raw = _extract_lat_lng_from_text(page_text)
            details["lat"] = details["lat"] or lat_raw
            details["lng"] = details["lng"] or lng_raw

        if not details["lat"] or not details["lng"]:
            lat_raw, lng_raw = _extract_lat_lng_from_url(driver.current_url)
            details["lat"] = details["lat"] or lat_raw
            details["lng"] = details["lng"] or lng_raw

        if not details["lat"] or not details["lng"]:
            lat_raw, lng_raw = _extract_lat_lng_from_url(hotel_url)
            details["lat"] = details["lat"] or lat_raw
            details["lng"] = details["lng"] or lng_raw
    except (TimeoutException, WebDriverException, InvalidSessionIdException):
        pass

    details["address_detail"] = normalize_address(details.get("address_detail", ""))
    return details


def main():
    driver = None
    try:
        print("Dang khoi tao trinh duyet...", flush=True)
        driver = start_driver(headless=False)
        driver.set_page_load_timeout(60)
        print("Da khoi tao trinh duyet.", flush=True)
        ensure_login_and_cookies(driver)

        if USE_LOAD_MORE_MODE:
            hotels = crawl_with_load_more(driver, max_rounds=MAX_PAGES)
            if AUTO_FALLBACK_TO_OFFSET and len(hotels) <= PAGE_SIZE:
                print(
                    "Load more khong mo rong duoc ket qua. Chuyen sang crawl theo offset de lay them.",
                    flush=True,
                )
                paged_hotels = crawl_result_pages(driver, max_pages=MAX_PAGES)
                hotels, added = merge_hotels(hotels, paged_hotels)
                print(f"Offset mode bo sung them: {added} hotel", flush=True)
        else:
            hotels = crawl_result_pages(driver, max_pages=MAX_PAGES)
        print("Tong hotel tu ket qua tim kiem:", len(hotels), flush=True)

        if DETAILS_LIMIT and DETAILS_LIMIT > 0:
            hotels = hotels[:DETAILS_LIMIT]
            print(f"Gioi han crawl chi tiet: {len(hotels)} hotel", flush=True)

        for idx, item in enumerate(hotels, start=1):
            detail = extract_hotel_details(
                driver,
                item.get("hotel_url", ""),
                fallback_name=item.get("hotel_name", ""),
                fallback_address=item.get("address", ""),
            )
            item.update(detail)
            if detail.get("hotel_name_detail"):
                item["hotel_name"] = detail["hotel_name_detail"]
            if detail.get("address_detail"):
                item["address"] = detail["address_detail"]
            item["address"] = normalize_address(item.get("address", ""))
            print(f"Chi tiet {idx}/{len(hotels)}: {item.get('hotel_name', '')}", flush=True)
            if DETAILS_AUTOSAVE_EVERY > 0 and idx % DETAILS_AUTOSAVE_EVERY == 0:
                excel_path, csv_path, json_path = save_hotel_outputs(hotels)
                print(
                    f"Auto save sau {idx} ket qua chi tiet: {excel_path}, {csv_path}, {json_path}",
                    flush=True,
                )

        excel_path, csv_path, json_path = save_hotel_outputs(hotels)

        save_cookies(driver)
        if excel_path:
            print(f"Da luu: {excel_path}", flush=True)
        else:
            print("Bo qua file Excel do loi ghi file.", flush=True)
        print(f"Da luu: {csv_path}", flush=True)
        print(f"Da luu: {json_path}", flush=True)
        print(f"Cookie file: {COOKIE_FILE}", flush=True)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()

# & "C:\Users\Admin Data\PycharmProjects\pythonProject1\github\Code_python\venv\.venv\Scripts\python.exe" -u "C:\Users\Admin Data\PycharmProjects\pythonProject1\github\Code_python\venv\Booking\crwal_data.py"
# Điều kiện dừng LoadMore giờ là khi đã có dữ liệu và 3 vòng liên tiếp không có hotel mới,
#  thì script sẽ dừng ngay sau đó và bắt đầu vào từng khách sạn để lấy chi tiết.
