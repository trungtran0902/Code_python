from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os

START_URL = "https://shopeefood.vn/ho-chi-minh/danh-sach-dia-diem-giao-tan-noi"
OUTPUT_FILE = "shopeefood_restaurants.csv"


def auto_save(row):
    df = pd.DataFrame([row])
    if not os.path.exists(OUTPUT_FILE):
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(OUTPUT_FILE, mode="a", index=False, header=False, encoding="utf-8-sig")


def kill_all_popups(page):
    try:
        page.evaluate("""
        () => {
            const selectors = [
                '.modal',
                '.modal-backdrop',
                '.ReactModal__Overlay',
                '.ReactModal__Content',
                '[role="dialog"]'
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
            document.body.style.overflow = 'auto';
            document.body.style.pointerEvents = 'auto';
        }
        """)
        time.sleep(0.3)
    except:
        pass


def get_shop_links(page):
    links = set()
    anchors = page.query_selector_all('a[href^="/ho-chi-minh/"]')

    for a in anchors:
        href = a.get_attribute("href")
        if not href:
            continue

        # loại link category
        if href in ["/ho-chi-minh/fmcg", "/ho-chi-minh/flowers", "/ho-chi-minh/liquor", "/ho-chi-minh/medicine", "/ho-chi-minh/fresh", "/ho-chi-minh/pets"]:
            continue

        if "danh-sach" in href:
            continue

        # shop thật thường có slug dài
        if href.count("-") < 2:
            continue

        links.add("https://shopeefood.vn" + href)

    return list(links)


def crawl_single_shop(page, url):
    print("🌐 Mở shop:", url)
    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.5)

        kill_all_popups(page)

        name = None
        name_el = page.query_selector("h1")
        if name_el:
            name = name_el.inner_text().strip()

        address = None
        addr_el = page.query_selector("div.address-restaurant")
        if addr_el:
            address = addr_el.inner_text().strip()

        # giờ mở/đóng: để dạng “best effort” (nếu trang có hiển thị)
        opening_hours = None
        hours_el = page.query_selector("div.time, span.time, div.operating-time")
        if hours_el:
            opening_hours = hours_el.inner_text().strip()

        row = {"Name": name, "Address": address, "OpeningHours": opening_hours, "URL": url}
        auto_save(row)
        print(f"💾 Saved: {name} | {address}")

    except Exception as e:
        print("❌ Lỗi shop:", e)
        auto_save({"Name": None, "Address": None, "OpeningHours": None, "URL": url})

def scroll_to_bottom(page):
    page.evaluate("""
    async () => {
        for (let i = 0; i < 6; i++) {
            window.scrollBy(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 600));
        }
    }
    """)
    time.sleep(1)

def go_to_next_page_spa(page):
    """
    Pagination ShopeeFood kiểu SPA + icon.
    Click bằng JS vào phần tử cha của span.icon-paging-next.
    Sau đó verify đã đổi trang bằng cách so sánh shop links.
    """
    kill_all_popups(page)

    # 1) scroll xuống cuối để pagination render/enable
    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.2)
    except:
        pass

    before = set(get_shop_links(page))

    # 2) thử click next nhiều lần theo các cách khác nhau
    clicked = False

    # Cách A: click bằng JS (ổn định nhất)
    try:
        clicked = page.evaluate("""
        () => {
            const icon = document.querySelector('span.icon.icon-paging-next, span.icon-paging-next, span[class*="icon-paging-next"]');
            if (!icon) return false;
            const btn = icon.closest('a,button');
            if (!btn) return false;

            // nếu có trạng thái disabled thì bỏ qua
            const cls = (btn.getAttribute('class') || '').toLowerCase();
            const ariaDisabled = (btn.getAttribute('aria-disabled') || '').toLowerCase();
            if (cls.includes('disabled') || ariaDisabled === 'true') return false;

            btn.click();
            return true;
        }
        """)
    except:
        clicked = False

    # Cách B: fallback selector nếu JS không tìm thấy
    if not clicked:
        try:
            el = page.query_selector("a:has(span.icon-paging-next), button:has(span.icon-paging-next)")
            if el:
                el.scroll_into_view_if_needed()
                time.sleep(0.5)
                el.click()
                clicked = True
        except:
            clicked = False

    if not clicked:
        print("⛔ Không click được nút Next (icon không thấy/disabled)")
        return False

    # 3) verify đã đổi trang: đợi links khác
    try:
        for _ in range(30):  # ~15s
            time.sleep(0.5)
            kill_all_popups(page)
            after = set(get_shop_links(page))
            if after and after != before:
                print("➡️ Sang trang tiếp theo (SPA OK)")
                return True
        print("⛔ Click rồi nhưng danh sách shop không đổi (có thể Next bị disabled)")
        return False
    except Exception as e:
        print("⛔ Lỗi khi verify trang:", e)
        return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("dialog", lambda d: d.accept())

        crawled = set()
        page_index = 1

        print("🌐 Mở danh sách địa điểm giao tận nơi (Hồ Chí Minh)...")
        page.goto(START_URL, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(4)

        while True:
            print(f"\n📄 TRANG {page_index}")

            kill_all_popups(page)

            # scroll để load đủ shop của trang hiện tại
            for _ in range(4):
                page.mouse.wheel(0, 2500)
                time.sleep(1)

            shop_links = get_shop_links(page)
            print(f"🔗 Tìm thấy {len(shop_links)} shop")

            if not shop_links:
                print("⛔ Không còn shop, dừng")
                break

            # ===== CRAWL SHOP TRONG TRANG HIỆN TẠI =====
            for idx, url in enumerate(shop_links, start=1):
                if url in crawled:
                    continue
                crawled.add(url)

                print(f"🔎 ({idx}/{len(shop_links)}) {url}")
                crawl_single_shop(page, url)
                time.sleep(1.2)

                # 🔑 QUAY LẠI LIST PAGE BẰNG HISTORY
                page.go_back()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(1.5)

            # ===== SANG TRANG TIẾP THEO (SPA) =====
            print("➡️ Chuẩn bị sang trang tiếp theo...")
            scroll_to_bottom(page)

            if not go_to_next_page_spa(page):
                print("⛔ Không còn trang tiếp theo")
                break

            page_index += 1
            time.sleep(3)

        browser.close()

    print("\n🎉 DONE – Crawl hoàn tất")



if __name__ == "__main__":
    main()
