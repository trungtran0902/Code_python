import time
import requests
import pandas as pd
from pathlib import Path
import csv
import sys
import re
import unicodedata

# =================== CONFIG ===================
API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"  # <-- Thay bằng API key của bạn
DELAY_NEXT_PAGE = 2.5
DELAY_BETWEEN_DETAILS = 0.2
MAX_PAGES_PER_QUERY = 3
# ==============================================

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


# 🧩 Hàm kiểm tra API key hợp lệ
def check_api_key():
    print("🔑 Kiểm tra API key...")
    try:
        test_params = {
            "location": "0,0",
            "radius": 10,
            "keyword": "test",
            "key": API_KEY,
            "language": "vi"
        }
        resp = requests.get(NEARBY_URL, params=test_params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")

        if status == "REQUEST_DENIED":
            print(f"❌ API key không hợp lệ hoặc chưa bật Google Places API.")
            print(f"➡️  Chi tiết: {data.get('error_message')}")
            sys.exit(1)
        elif status in ("OK", "ZERO_RESULTS"):
            print("✅ API key hợp lệ.\n")
        else:
            print(f"⚠️ Phản hồi bất thường: {status}")
    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra API key: {e}")
        sys.exit(1)


# 🔤 Hàm tạo tên file an toàn từ keyword
def make_safe_filename(keyword):
    # bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize("NFKD", keyword)
    no_diacritics = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # thay khoảng trắng & ký tự đặc biệt
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", no_diacritics.strip())
    # loại bỏ nhiều dấu _ liền nhau
    safe = re.sub(r"_+", "_", safe)
    return safe.lower()


def nearby_search(lat, lng, radius, keyword, page_token=None):
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": keyword,
        "key": API_KEY,
        "language": "vi"
    }
    if page_token:
        params["pagetoken"] = page_token
    resp = requests.get(NEARBY_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_full_address(place_id):
    params = {
        "place_id": place_id,
        "fields": "formatted_address",
        "key": API_KEY,
        "language": "vi"
    }
    try:
        resp = requests.get(DETAILS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("formatted_address")
    except Exception:
        return None


def extract_place_info(place):
    geometry = place.get("geometry", {}).get("location", {})
    return {
        "place_id": place.get("place_id"),
        "name": place.get("name"),
        "lat": geometry.get("lat"),
        "lng": geometry.get("lng"),
    }


def main():
    # ======== KIỂM TRA API KEY ========
    check_api_key()

    # ======== NHẬP THÔNG TIN ========
    try:
        coord_str = input("Nhập tọa độ tâm (lat,long): ").strip()
        lat_str, lng_str = coord_str.split(",")
        lat = float(lat_str)
        lng = float(lng_str)
        radius = int(input("Nhập bán kính (mét): ").strip())
        keyword = input("Nhập từ khóa tìm kiếm: ").strip()
    except ValueError:
        print("❌ Dữ liệu nhập không hợp lệ. Vui lòng nhập đúng dạng: 10.935389,106.383093")
        sys.exit(1)

    # ======== TẠO TÊN FILE TỰ ĐỘNG ========
    safe_kw = make_safe_filename(keyword)
    OUTPUT_CSV = f"poi_{safe_kw}.csv"
    OUTPUT_XLSX = f"poi_{safe_kw}.xlsx"

    # ======== CHUẨN BỊ FILE CSV ========
    fieldnames = ["source_keyword", "name", "address", "lat", "lng", "place_id"]
    file_exists = Path(OUTPUT_CSV).exists()
    csv_file = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    if not file_exists or Path(OUTPUT_CSV).stat().st_size == 0:
        writer.writeheader()

    # ======== BẮT ĐẦU CÀO DỮ LIỆU ========
    print(f"\n🔍 Tìm kiếm quanh ({lat}, {lng}) trong bán kính {radius}m với từ khóa: {keyword}")
    page_token = None
    page = 0

    while True:
        if page_token:
            print("   ⏳ Đợi token hợp lệ (2.5s)...")
            time.sleep(DELAY_NEXT_PAGE)

        data = nearby_search(lat, lng, radius, keyword, page_token)
        results = data.get("results", [])
        print(f"   ✅ Trang {page + 1}: {len(results)} kết quả")

        for p in results:
            info = extract_place_info(p)
            info["source_keyword"] = keyword
            addr = get_full_address(info["place_id"])
            info["address"] = addr or p.get("vicinity")

            writer.writerow(info)
            csv_file.flush()
            time.sleep(DELAY_BETWEEN_DETAILS)

        page += 1
        page_token = data.get("next_page_token")

        if not page_token or page >= MAX_PAGES_PER_QUERY:
            break

    csv_file.close()
    print(f"\n💾 Dữ liệu đã được lưu tại: {OUTPUT_CSV}")

    # ======== XUẤT FILE EXCEL ========
    df_out = pd.read_csv(OUTPUT_CSV)
    df_out.to_excel(OUTPUT_XLSX, index=False)
    print(f"🎉 Xuất hoàn tất → {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
