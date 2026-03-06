import time
import math
import re
from playwright.sync_api import sync_playwright


# ======================
# UTILS
# ======================
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ======================
# TILE NAVIGATION
# ======================
def generate_tiles(center_lat, center_lng, radius_km=1):
    # Tạo các tọa độ xung quanh khu vực trung tâm cho các tile nhỏ
    # Ví dụ, chia khu vực thành lưới với 3x3 tiles xung quanh trung tâm
    tiles = []
    offset = radius_km / 111  # 1 degree ~ 111 km

    # Tạo lưới các tọa độ (lat, lng) cho các tile trong bán kính radius_km
    for lat_offset in [-offset, 0, offset]:
        for lng_offset in [-offset, 0, offset]:
            tiles.append((center_lat + lat_offset, center_lng + lng_offset))

    return tiles


def scroll_results(page, max_rounds=30):
    feed = page.locator("div[role='feed']")
    if feed.count() == 0: return False
    last = 0
    for _ in range(max_rounds):
        try:
            feed.first.evaluate("(el)=>el.scrollBy(0, el.scrollHeight)")
            time.sleep(0.6)  # Thêm thời gian chờ để tải POI
            h = feed.first.evaluate("(el)=>el.scrollHeight")
            if h == last: break
            last = h
        except:
            break
    return True


def get_place_links_from_list(page):
    try:
        return page.eval_on_selector_all(
            "a[href*='/maps/place/']",
            "els=>[...new Set(els.map(e=>e.href))]"
        )
    except:
        return []


# ======================
# SCRAPE POI
# ======================
def search_for_keyword(page, keyword):
    # Tìm kiếm từ khóa trên Google Maps
    search_box = page.locator("input[role='combobox']")
    search_box.fill(keyword)
    search_box.press("Enter")
    time.sleep(3)  # Đợi một chút để các kết quả tải xong


def crawl_tile(page, lat, lng, radius_km, keyword):
    print(f"Scanning Tile: {lat}, {lng}")

    # Di chuyển đến tile
    zoom = 14  # Zoom level cho bán kính nhỏ
    url = f"https://www.google.com/maps/@{lat},{lng},{zoom}z"
    page.goto(url, timeout=60000)
    time.sleep(2)

    # Tìm kiếm POI theo từ khóa
    search_for_keyword(page, keyword)

    # Quét POI trong tile này
    scroll_results(page)  # Cuộn để tải thêm POI

    links = get_place_links_from_list(page)

    # Scroll thêm nếu không đủ POI
    scroll_results(page)
    return links


def crawl_tiles_in_area(page, center_lat, center_lng, radius_km=1, keyword=""):
    # Tạo các tile nhỏ quanh khu vực trung tâm
    tiles = generate_tiles(center_lat, center_lng, radius_km)
    all_pois = []

    for tile_lat, tile_lng in tiles:
        # Thu thập POI trong từng tile
        links = crawl_tile(page, tile_lat, tile_lng, radius_km, keyword)
        all_pois.extend(links)

    return all_pois


# ======================
# MAIN FUNCTION
# ======================
def main(center_lat, center_lng, radius_km=1, keyword=""):
    with sync_playwright() as p:
        # Khởi tạo context và trang Playwright
        context = p.chromium.launch_persistent_context(
            user_data_dir="google_profile",  # Lưu thông tin người dùng để không đăng nhập lại
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",  # Đường dẫn tới Chrome
            headless=False,  # Đặt chế độ không đầu (false để xem trình duyệt)
            locale="vi-VN",  # Ngôn ngữ là tiếng Việt
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        # Bắt đầu quét POI từ vị trí trung tâm
        pois = crawl_tiles_in_area(page, center_lat, center_lng, radius_km, keyword)

        # In ra các POI thu thập được
        print(f"Total POIs collected: {len(pois)}")
        for poi in pois:
            print(poi)

        context.close()


if __name__ == "__main__":
    # Đầu vào cho hàm chính
    center_lat = float(input("Enter center latitude: "))  # Tọa độ vĩ độ trung tâm
    center_lng = float(input("Enter center longitude: "))  # Tọa độ kinh độ trung tâm
    radius_km = float(input("Enter radius in km: "))  # Bán kính quét quanh tọa độ trung tâm
    keyword = input("Enter the search keyword: ")  # Từ khóa tìm kiếm

    # Chạy chương trình
    main(center_lat, center_lng, radius_km, keyword)
