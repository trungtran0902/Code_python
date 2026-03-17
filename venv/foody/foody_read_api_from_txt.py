import time
import random
import tkinter as tk
from tkinter import filedialog
import os
import json
import csv
from urllib.parse import urlsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    from openpyxl import Workbook, load_workbook
except ModuleNotFoundError:
    Workbook = None
    load_workbook = None


COLUMNS = [
    "STT",
    "Ten quan",
    "Dia chi",
    "Dien thoai",
    "Rating",
    "Latitude",
    "Longitude",
    "Distance",
    "IsDelivery",
    "IsOpening",
    "Google Maps"
]


class SimpleResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def json(self):
        return json.loads(self.text)


class SimpleSession:
    def __init__(self):
        self.headers = {}
        self.cookies = {}

    def get(self, endpoint, params=None, timeout=15):
        query = urlencode(params or {}, doseq=True)
        url = endpoint if not query else f"{endpoint}?{query}"
        req_headers = dict(self.headers)
        if self.cookies:
            req_headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

        request = Request(url, headers=req_headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as resp:
                status = getattr(resp, "status", resp.getcode())
                content_type = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(content_type, errors="replace")
                return SimpleResponse(status, body)
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return SimpleResponse(e.code, body)
        except URLError as e:
            raise RuntimeError(f"Network error: {e}") from e


class CsvWorksheet:
    def __init__(self, file_name):
        self.file_name = file_name
        self.rows = []

        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8-sig", newline="") as f:
                self.rows = list(csv.reader(f))

        if not self.rows:
            self.rows.append(COLUMNS)

    @property
    def max_row(self):
        return len(self.rows)

    def append(self, row):
        self.rows.append(row)


class CsvWorkbook:
    def __init__(self, ws):
        self.ws = ws

    def save(self, file_name=None):
        target = file_name or self.ws.file_name
        with open(target, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(self.ws.rows)


# ======================
# COOKIE ĐĂNG NHẬP
# ======================
COOKIE = "..."   # ðŸ”´ GIá»® NGUYÃŠN COOKIE Báº N ÄÃƒ CÃ“
USE_COOKIE = True
COOKIE_STATE_FILE = "foody_state_HaiPhong.json"


# ======================
# CHỌN FILE TXT
# ======================
def choose_txt_file():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Chon file TXT chua link API Foody",
        filetypes=[("Text files", "*.txt")]
    )
    return file_path


def make_excel_file_name(txt_file):
    base_name = os.path.splitext(os.path.basename(txt_file))[0]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ext = ".xlsx" if Workbook is not None else ".csv"
    return os.path.join(script_dir, f"{base_name}{ext}")


def parse_cookie_string(cookie_str):
    cookies = {}
    if not cookie_str or cookie_str.strip() == "...":
        return cookies

    for chunk in cookie_str.split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies


def load_cookie_state_file(cookie_state_file):
    if not cookie_state_file:
        return {}

    if not os.path.isabs(cookie_state_file):
        cookie_state_file = os.path.join(os.path.dirname(__file__), cookie_state_file)

    if not os.path.exists(cookie_state_file):
        return {}

    with open(cookie_state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cookie_map = {}
    for c in data.get("cookies", []):
        name = c.get("name")
        value = c.get("value")
        domain = str(c.get("domain", "")).lower()
        if not name or value is None:
            continue
        if "foody.vn" not in domain:
            continue
        cookie_map[name] = value
    return cookie_map


def remove_location_cookies(cookies):
    # TrÃ¡nh cookie location ghi Ä‘Ã¨ lat/lon cá»§a URL (gÃ¢y lá»‡ch HCM -> HN)
    block_keywords = ("city", "district", "location", "lat", "lon", "province", "ward", "region")
    filtered = {}
    removed = {}

    for key, value in cookies.items():
        key_lower = key.lower()
        if any(word in key_lower for word in block_keywords):
            removed[key] = value
            continue
        filtered[key] = value
    return filtered, removed


def split_api_url(api_url):
    parsed = urlsplit(api_url)
    endpoint = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return endpoint, params


# ======================
# KHá»žI Táº O / Má»ž FILE EXCEL
# ======================
def init_excel(file_name):
    if Workbook is None:
        ws = CsvWorksheet(file_name)
        wb = CsvWorkbook(ws)
        wb.save(file_name)
        return wb, ws

    if os.path.exists(file_name):
        wb = load_workbook(file_name)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Foody Map Data"
        ws.append(COLUMNS)
        wb.save(file_name)

    return wb, ws


# ======================
# MAIN
# ======================
def main():
    txt_file = choose_txt_file()
    if not txt_file:
        print("No TXT file selected")
        return

    print("Selected file:", txt_file)

    with open(txt_file, "r", encoding="utf-8") as f:
        api_urls = [line.strip() for line in f if line.strip()]

    print(f"Total API links: {len(api_urls)}\n")

    if requests is not None:
        s = requests.Session()
    else:
        print("Module 'requests' not found, using urllib fallback.")
        s = SimpleSession()

    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.foody.vn/",
        "X-Requested-With": "XMLHttpRequest"
    })

    if USE_COOKIE:
        cookie_map = load_cookie_state_file(COOKIE_STATE_FILE)
        if cookie_map:
            s.cookies.update(cookie_map)
            print(f"Loaded {len(cookie_map)} cookies from state file: {COOKIE_STATE_FILE}")
        else:
            cookie_map = parse_cookie_string(COOKIE)
            cookie_map, removed = remove_location_cookies(cookie_map)
            if cookie_map:
                s.cookies.update(cookie_map)
                print(f"Loaded {len(cookie_map)} cookies from COOKIE (removed {len(removed)} location cookies)")
            else:
                print("No cookies loaded (state file/COOKIE empty or invalid).")
    else:
        print("Calling API without cookies.")

    excel_file = make_excel_file_name(txt_file)
    if Workbook is None:
        print("Module 'openpyxl' not found, saving as CSV.")
    wb, ws = init_excel(excel_file)

    total_place = ws.max_row - 1

    for idx, api_url in enumerate(api_urls, start=1):
        print(f"\n[{idx}/{len(api_urls)}] GET: {api_url}")

        try:
            endpoint, params = split_api_url(api_url)
            r = s.get(endpoint, params=params, timeout=15)
            print("Status:", r.status_code)

            if r.status_code != 200:
                print("Request error")
                continue

            js = r.json()
            items = js.get("Items", [])
            print(f"Items in batch: {len(items)}")

            for place in items:
                total_place += 1

                lat = place.get("Latitude")
                lng = place.get("Longitude")
                distance = place.get("Distance")
                is_delivery = place.get("IsDelivery")
                is_opening = place.get("IsOpening")

                maps_url = ""
                if lat and lng:
                    maps_url = f"https://www.google.com/maps?q={lat},{lng}"

                ws.append([
                    total_place,
                    place.get("Name"),
                    place.get("Address"),
                    place.get("Phone", ""),
                    place.get("AvgRating"),
                    lat,
                    lng,
                    distance,
                    is_delivery,
                    is_opening,
                    maps_url
                ])

            wb.save(excel_file)
            print("Saved output file")

            sleep_time = random.uniform(2, 3)
            print(f"Sleep {sleep_time:.2f}s before next API call...")
            time.sleep(sleep_time)

        except Exception as e:
            print("Error:", e)

    print(f"\nDONE - Total places collected: {total_place}")
    print(f"Output file: {excel_file}")
if __name__ == "__main__":
    main()


