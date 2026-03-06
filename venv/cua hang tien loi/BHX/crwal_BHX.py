from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import pandas as pd
import time
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_URL_PART = "GetStoresByLocation"
BASE_API = "https://api.bachhoaxanh.com/gw/Location/V2/GetStoresByLocation"
OUTPUT_DIR = Path(__file__).resolve().parent / "Data"
OUTPUT_FILE = OUTPUT_DIR / "BHX_full.xlsx"
PROVINCE_IDS = [
    1032, 1020, 1027, 1019, 1031, 1033, 1024,
    1026, 1029, 1022, 1017, 1013, 1023, 1025,
    1016, 1014, 1021, 1018, 1028, 1015, 1030
]


def get_live_headers():
    print("Dang mo trinh duyet lay header song...")

    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)

    driver.get("https://www.bachhoaxanh.com/he-thong-cua-hang")
    time.sleep(8)

    live_headers = None
    live_cookies = None

    for request in driver.requests:
        if request.response and API_URL_PART in request.url:
            live_headers = request.headers
            live_cookies = driver.get_cookies()
            break

    driver.quit()

    if not live_headers:
        raise Exception("Khong bat duoc request API!")

    print("Da lay duoc header hop le.")
    return live_headers, live_cookies


def create_session(headers, cookies):
    session = requests.Session()

    allowed_headers = [
        "Authorization",
        "Accesstoken",
        "Customer-Id",
        "Deviceid",
        "Devicetoken",
        "Xapikey",
        "Username",
        "Platform",
        "Origin",
        "Referer",
        "User-Agent"
    ]

    clean_headers = {}
    for h in allowed_headers:
        if h in headers:
            clean_headers[h] = headers[h]

    clean_headers["Accept"] = "application/json, text/plain, */*"

    session.headers.update(clean_headers)

    for c in cookies:
        session.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=".bachhoaxanh.com"
        )

    return session


def crawl_all_pages(session, province_id):
    page_index = 0
    page_size = 10
    all_stores = []

    while True:
        params = {
            "provinceId": province_id,
            "wardId": 0,
            "pageSize": page_size,
            "pageIndex": page_index
        }

        response = session.get(BASE_API, params=params)

        if response.status_code != 200:
            print(f"Loi provinceId={province_id}: {response.status_code}")
            break

        if "Unauthorized" in response.text:
            print("Token het han.")
            break

        data = response.json()
        stores = data.get("data", {}).get("stores", [])

        if not stores:
            break

        print(f"provinceId={province_id} | Trang {page_index} - {len(stores)} cua hang")

        for store in stores:
            all_stores.append({
                "Province ID": province_id,
                "Store ID": store.get("storeId"),
                "Ten cua hang": store.get("storeLocation"),
                "Latitude": store.get("lat"),
                "Longitude": store.get("lng"),
                "Gio mo cua": store.get("openHour")
            })

        page_index += 1
        time.sleep(0.2)

    return all_stores


if __name__ == "__main__":
    headers, cookies = get_live_headers()
    session = create_session(headers, cookies)

    stores = []
    for province_id in PROVINCE_IDS:
        print(f"\n=== Bat dau quet provinceId={province_id} ===")
        province_stores = crawl_all_pages(session, province_id)
        stores.extend(province_stores)
        print(f"Da quet xong provinceId={province_id}: {len(province_stores)} cua hang")

    df = pd.DataFrame(stores)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_excel(OUTPUT_FILE, index=False)

    print(f"Hoan tat. Da xuat Excel: {OUTPUT_FILE}")
