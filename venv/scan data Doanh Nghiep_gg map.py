from playwright.sync_api import sync_playwright
import time
import csv

def crawl_google_maps(keyword, max_records=100, output_file=r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\google_maps_companies.csv"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page = browser.new_page()
        page.goto(f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}", timeout=60000)
        page.wait_for_timeout(5000)

        scroll_container = page.query_selector('div[role="feed"]')
        for _ in range(10):
            scroll_container.evaluate("e => e.scrollBy(0, 1000)")
            time.sleep(1.5)

        cards = page.query_selector_all("div.Nv2PK")
        print(f"🔍 Tìm thấy {len(cards)} kết quả thô")

        results = []
        for i, card in enumerate(cards[:max_records]):
            try:
                card.click()
                time.sleep(2)

                # Lấy tên công ty
                name_el = page.query_selector("h1.DUwDvf")
                name = name_el.inner_text().strip() if name_el else "N/A"

                # Lấy địa chỉ
                addr_el = page.query_selector('button[data-item-id="address"]')
                address = addr_el.inner_text().strip() if addr_el else "N/A"

                # Tọa độ từ URL
                url = page.url
                if "/@" in url:
                    lat, lng = url.split("/@")[1].split(",")[:2]
                else:
                    lat, lng = "N/A", "N/A"

                results.append([name, address, lat, lng])
                print(f"{i+1:03d}: ✅ {name}")
                time.sleep(1.2)
            except Exception as e:
                print(f"{i+1:03d}: ⚠️ Lỗi: {e}")
                continue

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Address", "Latitude", "Longitude"])
            writer.writerows(results)

        print(f"\n✅ Đã lưu {len(results)} công ty vào {output_file}")
        browser.close()

# Gọi chạy
if __name__ == "__main__":
    crawl_google_maps("công ty Hồ Chí Minh", max_records=100)
