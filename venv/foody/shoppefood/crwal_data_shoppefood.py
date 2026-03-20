import csv
import json
import os
import re
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    from openpyxl import Workbook
except ModuleNotFoundError:
    Workbook = None

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_ENDPOINT = "https://gappapi.deliverynow.vn/api/delivery/get_detail"
DEFAULT_ID_TYPE = 2
DEFAULT_START_ID = 1
DEFAULT_END_ID = 100
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP_SECONDS = 0.15
COOKIE_STATE_FILE = os.path.join(BASE_DIR, "shoppefood_state.json")
LOGIN_URL = "https://shopeefood.vn/"
LOGIN_WAIT_TIMEOUT_MS = 60000


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

    def get(self, url, params=None, timeout=DEFAULT_TIMEOUT):
        query = urlencode(params or {}, doseq=True)
        full_url = url if not query else f"{url}?{query}"
        request_headers = dict(self.headers)
        if self.cookies:
            request_headers["Cookie"] = "; ".join(
                [f"{key}={value}" for key, value in self.cookies.items()]
            )

        request = Request(full_url, headers=request_headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", response.getcode())
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return SimpleResponse(status, body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return SimpleResponse(exc.code, body)
        except URLError as exc:
            raise RuntimeError(f"Network error: {exc}") from exc


def clean_text(value):
    return "" if value is None else str(value).strip()


def choose_output_file():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if Workbook is not None:
        return os.path.join(BASE_DIR, f"shoppefood_api_{stamp}.xlsx")
    return os.path.join(BASE_DIR, f"shoppefood_api_{stamp}.csv")


def build_session():
    if requests is not None:
        session = requests.Session()
    else:
        print("Module 'requests' khong co, dung urllib fallback.")
        session = SimpleSession()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://shopeefood.vn/",
            "Origin": "https://shopeefood.vn",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session


def load_cookie_state_file(cookie_state_file):
    if not cookie_state_file:
        return {}

    if not os.path.isabs(cookie_state_file):
        cookie_state_file = os.path.abspath(cookie_state_file)

    if not os.path.exists(cookie_state_file):
        return {}

    with open(cookie_state_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    cookie_map = {}
    for cookie in data.get("cookies", []):
        name = cookie.get("name")
        value = cookie.get("value")
        domain = str(cookie.get("domain", "")).lower()
        if not name or value is None:
            continue
        if "foody.vn" not in domain and "deliverynow.vn" not in domain:
            continue
        cookie_map[name] = value
    return cookie_map


def attach_cookies(session, cookie_state_file):
    cookie_map = load_cookie_state_file(cookie_state_file)
    if not cookie_map:
        print(f"Khong tim thay cookie state hop le: {cookie_state_file}")
        return False
    session.cookies.update(cookie_map)
    print(f"Da nap {len(cookie_map)} cookie tu state file.")
    return True


def login_and_save_cookie_state(cookie_state_file):
    if sync_playwright is None:
        raise RuntimeError("Chua cai playwright, khong mo duoc trinh duyet de login.")

    cookie_state_file = os.path.abspath(cookie_state_file)
    os.makedirs(os.path.dirname(cookie_state_file), exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, timeout=60000)
        print("Mo ShopeeFood/Foody de dang nhap bang tay.")
        print("Ban co 60 giay de dang nhap. Het 60 giay, browser se tu dong dong va luu cookie.")
        page.wait_for_timeout(LOGIN_WAIT_TIMEOUT_MS)

        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        context.storage_state(path=cookie_state_file)
        print(f"Da luu cookie state: {cookie_state_file}")
        browser.close()


def ensure_cookie_state(session, cookie_state_file, force_refresh=False):
    cookie_state_file = os.path.abspath(cookie_state_file)

    if force_refresh or not os.path.exists(cookie_state_file):
        print("Can dang nhap de tao cookie state cho API.")
        login_and_save_cookie_state(cookie_state_file)

    loaded = attach_cookies(session, cookie_state_file)
    if not loaded:
        print("Cookie state khong hop le, mo login lai.")
        login_and_save_cookie_state(cookie_state_file)
        loaded = attach_cookies(session, cookie_state_file)

    return loaded


def flatten_json(value, prefix="", output=None):
    if output is None:
        output = {}

    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flatten_json(item, next_prefix, output)
        return output

    if isinstance(value, list):
        if not value:
            output[prefix] = ""
            return output
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            flatten_json(item, next_prefix, output)
        return output

    output[prefix] = value
    return output


def normalize_url(value):
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith("/"):
        return f"https://shopeefood.vn{text}"
    return text


def collect_links(obj, path="", links=None):
    if links is None:
        links = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else str(key)
            key_lower = str(key).lower()
            if isinstance(value, str):
                candidate = value.strip()
                if candidate and (
                    candidate.startswith("http://")
                    or candidate.startswith("https://")
                    or candidate.startswith("//")
                    or (candidate.startswith("/") and any(token in key_lower for token in ("url", "link", "share", "web")))
                ):
                    links.append((next_path, normalize_url(candidate)))
            collect_links(value, next_path, links)
        return links

    if isinstance(obj, list):
        for index, item in enumerate(obj):
            next_path = f"{path}[{index}]"
            collect_links(item, next_path, links)
    return links


def extract_primary_fields(payload):
    flattened = flatten_json(payload)
    links = collect_links(payload)

    row = {
        "request_id": "",
        "http_status": "",
        "api_error": clean_text(flattened.get("error")),
        "is_login": clean_text(flattened.get("is_login")),
        "restaurant_id": "",
        "restaurant_name": "",
        "restaurant_address": "",
        "phone": "",
        "latitude": "",
        "longitude": "",
        "primary_link": "",
        "all_links": json.dumps(links, ensure_ascii=False),
        "raw_json": json.dumps(payload, ensure_ascii=False),
    }

    key_priority = {
        "restaurant_id": [
            "reply.delivery_detail.id",
            "reply.delivery_detail.restaurant_id",
            "reply.restaurant.id",
            "result.id",
        ],
        "restaurant_name": [
            "reply.delivery_detail.name",
            "reply.delivery_detail.restaurant_name",
            "reply.restaurant.name",
            "result.name",
        ],
        "restaurant_address": [
            "reply.delivery_detail.address",
            "reply.restaurant.address",
            "result.address",
        ],
        "phone": [
            "reply.delivery_detail.phone",
            "reply.restaurant.phone",
            "result.phone",
        ],
        "latitude": [
            "reply.delivery_detail.latitude",
            "reply.delivery_detail.lat",
            "reply.restaurant.latitude",
            "reply.restaurant.lat",
            "result.latitude",
            "result.lat",
        ],
        "longitude": [
            "reply.delivery_detail.longitude",
            "reply.delivery_detail.lng",
            "reply.restaurant.longitude",
            "reply.restaurant.lng",
            "result.longitude",
            "result.lng",
        ],
    }

    for target_key, candidates in key_priority.items():
        for candidate in candidates:
            if candidate in flattened and clean_text(flattened[candidate]) != "":
                row[target_key] = clean_text(flattened[candidate])
                break

    if links:
        row["primary_link"] = links[0][1]

    return row, flattened


def fetch_detail(session, request_id, id_type=DEFAULT_ID_TYPE, timeout=DEFAULT_TIMEOUT):
    params = {"id_type": id_type, "request_id": request_id}
    response = session.get(API_ENDPOINT, params=params, timeout=timeout)

    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}

    row, flattened = extract_primary_fields(payload)
    row["request_id"] = request_id
    row["http_status"] = response.status_code

    # Gom them mot so field phang de de loc trong Excel.
    important_pairs = []
    for key, value in flattened.items():
        if re.search(r"(name|title|address|phone|lat|lng|url|link|district|city)", key, re.I):
            important_pairs.append(f"{key}={value}")
    row["important_values"] = " | ".join(important_pairs[:50])

    return row


def needs_login(row):
    api_error = clean_text(row.get("api_error"))
    is_login = clean_text(row.get("is_login")).lower()
    return api_error == "90309999" or is_login == "false"


def write_csv(output_file, rows):
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with open(output_file, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(output_file, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ShopeeFood API"

    fieldnames = sorted({key for row in rows for key in row.keys()})
    worksheet.append(fieldnames)

    for row in rows:
        worksheet.append([row.get(name, "") for name in fieldnames])

    workbook.save(output_file)


def save_output(output_file, rows):
    if Workbook is not None and output_file.lower().endswith(".xlsx"):
        write_xlsx(output_file, rows)
        return
    write_csv(output_file, rows)


def main():
    start_id_raw = input(f"Nhap request_id bat dau (mac dinh {DEFAULT_START_ID}): ").strip()
    end_id_raw = input(f"Nhap request_id ket thuc (mac dinh {DEFAULT_END_ID}): ").strip()

    start_id = int(start_id_raw) if start_id_raw else DEFAULT_START_ID
    end_id = int(end_id_raw) if end_id_raw else DEFAULT_END_ID
    if end_id < start_id:
        raise ValueError("request_id ket thuc phai >= request_id bat dau.")

    session = build_session()
    ensure_cookie_state(session, COOKIE_STATE_FILE, force_refresh=False)

    rows = []
    output_file = choose_output_file()

    print(f"Bat dau quet request_id tu {start_id} den {end_id}")
    print(f"Output: {output_file}")

    for request_id in range(start_id, end_id + 1):
        try:
            row = fetch_detail(session, request_id)

            if request_id == start_id and needs_login(row):
                print("API bao chua dang nhap hop le. Tien hanh login lai va thu lai...")
                ensure_cookie_state(session, COOKIE_STATE_FILE, force_refresh=True)
                row = fetch_detail(session, request_id)

            rows.append(row)
            print(
                f"[{request_id}] status={row['http_status']} "
                f"error={row['api_error']} link={row['primary_link']}"
            )
        except Exception as exc:
            rows.append(
                {
                    "request_id": request_id,
                    "http_status": "",
                    "api_error": "",
                    "primary_link": "",
                    "raw_json": "",
                    "important_values": "",
                    "runtime_error": str(exc),
                }
            )
            print(f"[{request_id}] Loi: {exc}")

        if len(rows) % 100 == 0:
            save_output(output_file, rows)
            print(f"Autosave: {output_file}")

        time.sleep(DEFAULT_SLEEP_SECONDS)

    save_output(output_file, rows)
    print("Hoan tat.")
    print("File ket qua:", output_file)


if __name__ == "__main__":
    main()
