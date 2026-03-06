import time
import csv
import os
import re
from playwright.sync_api import sync_playwright

# 📁 File CSV xuất
output_file = "googlemaps_petrolimex_autosave.csv"
os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None

def extract_latlng_from_url(url):
    match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    return (match.group(1), match.group(2)) if match else ("", "")

def save_to_csv(data):
    file_exists = os.path.isfile(output_file)
    with open(output_file, "a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "address", "lat", "lng"])
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

def crawl_petrolimex_stations():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            locale="vi-VN",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "vi"}
        )
        page = context.new_page()

        print("🔍 Đang truy cập Google Maps...")
        page.goto("https://www.google.com/maps?hl=vi")
        time.sleep(3)

        print("🔍 Đang tìm kiếm: Cửa hàng Xăng dầu Petrolimex tỉnh Bến Tre")
        search_box = page.query_selector("input[role='combobox']")
        search_box.fill("Cửa hàng Xăng dầu Petrolimex tỉnh Bến Tre")
        time.sleep(1)
        search_box.press("Enter")
        time.sleep(5)

        print("🌀 Đang cuộn danh sách kết quả...")
        scrollable = page.query_selector("div[role='feed']")
        for _ in range(25):
            scrollable.evaluate("el => el.scrollBy(0, 1000)")
            time.sleep(1)

        # 🧭 Lấy danh sách các liên kết entry
        links = page.eval_on_selector_all("div.Nv2PK a.hfpxzc", "els => els.map(el => el.href)")
        print(f"📌 Số địa điểm lấy được: {len(links)}")

        for idx, link in enumerate(links):
            try:
                page.goto(link)
                time.sleep(5)

                # ✅ Tên cây xăng
                try:
                    page.wait_for_selector("h1.DUwDvf", timeout=5000)
                    name = page.locator("h1.DUwDvf").first.text_content() or "N/A"
                except:
                    name = "N/A"

                # ✅ Địa chỉ cây xăng
                try:
                    address = (
                        page.locator("button[data-item-id='address']").first.text_content(timeout=5000) or
                        page.locator("div[aria-label*='Địa chỉ']").first.text_content(timeout=5000) or
                        "N/A"
                    )
                except:
                    address = "N/A"

                # ✅ Tọa độ
                lat, lng = extract_latlng_from_url(page.url)

                print(f"✔ {idx+1:02d}: {name} — {address} — {lat}, {lng}")

                save_to_csv({
                    "name": name,
                    "address": address,
                    "lat": lat,
                    "lng": lng
                })

            except Exception as e:
                print(f"❌ Lỗi entry {idx+1}: {e}")
                continue

        browser.close()
        print(f"\n✅ Đã lưu dữ liệu vào: {output_file}")

# 🔧 Chạy chính
crawl_petrolimex_stations()
