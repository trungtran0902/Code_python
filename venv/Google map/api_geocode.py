import requests

API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"  # TODO: thay bằng API Key thật của bạn


# ---------- 1. REVERSE GEOCODE (TỌA ĐỘ -> ĐỊA CHỈ) ----------

def reverse_geocode(lat, lng, api_key):
    """Từ tọa độ (lat, lng) -> địa chỉ (Geocoding API)."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key,
        "language": "vi",  # cho dễ đọc
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Lỗi khi gọi Geocoding API: {e}")
        return None

    data = response.json()
    status = data.get("status")

    if status == "OK":
        return data.get("results", [])
    else:
        print(f"Geocoding API không trả về kết quả. Status: {status}")
        print("Chi tiết:", data.get("error_message"))
        return None


def print_geocode_results(results):
    """In kết quả từ Geocoding API."""
    if not results:
        print("Không có kết quả nào.")
        return

    print("Kết quả reverse geocode (Geocoding API):")
    for idx, result in enumerate(results, start=1):
        print(f"\nKết quả {idx}:")
        print(f"Địa chỉ: {result.get('formatted_address')}")

        geometry = result.get("geometry", {})
        location = geometry.get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is not None and lng is not None:
            print(f"Tọa độ: lat={lat}, lng={lng}")

        print("Các thành phần địa chỉ:")
        for component in result.get("address_components", []):
            types = ",".join(component.get("types", []))
            print(f"  - {types}: {component.get('long_name')}")


# ---------- 2. PLACE SEARCH (KEYWORD -> ĐỊA ĐIỂM) ----------

def place_search_text(query, api_key):
    """Tìm địa điểm theo keyword (Places Text Search API)."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key,
        "language": "vi",
        "region": "vn",  # ưu tiên kết quả ở Việt Nam
        # Có thể thêm location + radius nếu muốn ưu tiên quanh 1 khu vực nào đó
        # "location": "10.77,106.70",
        # "radius": 5000,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Lỗi khi gọi Places API: {e}")
        return None

    data = response.json()
    status = data.get("status")

    if status == "OK":
        return data.get("results", [])
    else:
        print(f"Places API không trả về kết quả. Status: {status}")
        print("Chi tiết:", data.get("error_message"))
        return None


def print_place_results(results):
    """In kết quả từ Places Text Search."""
    if not results:
        print("Không có kết quả nào.")
        return

    print("Kết quả place search (Places Text Search API):")
    for idx, place in enumerate(results, start=1):
        print(f"\nKết quả {idx}:")
        print(f"Tên: {place.get('name')}")
        print(f"Địa chỉ: {place.get('formatted_address')}")

        geometry = place.get("geometry", {})
        location = geometry.get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is not None and lng is not None:
            print(f"Tọa độ: lat={lat}, lng={lng}")

        rating = place.get("rating")
        user_ratings_total = place.get("user_ratings_total")
        if rating is not None:
            print(f"Rating: {rating} ({user_ratings_total} đánh giá)")

        place_types = place.get("types", [])
        if place_types:
            print("Loại địa điểm:", ", ".join(place_types))

        place_id = place.get("place_id")
        if place_id:
            print(f"Place ID: {place_id}")


# ---------- 3. HÀM HỖ TRỢ & CHƯƠNG TRÌNH CHÍNH ----------

def try_parse_lat_lng(text):
    """
    Cố gắng parse chuỗi theo dạng:
      '10.7719523, 106.7041746'
    Trả về (True, lat, lng) nếu parse được,
    ngược lại (False, None, None).
    """
    parts = text.split(",")
    if len(parts) != 2:
        return False, None, None

    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        return True, lat, lng
    except ValueError:
        return False, None, None


if __name__ == "__main__":
    user_input = input(
        "Nhập location hoặc keyword:\n"
        "  - Dạng tọa độ: '10.7719523, 106.7041746'\n"
        "  - Dạng keyword: 'adidas Bitexco', 'Highlands Bitexco', ...\n"
        ">> "
    ).strip()

    is_coord, lat, lng = try_parse_lat_lng(user_input)

    if is_coord:
        # Người dùng nhập tọa độ -> dùng Geocoding reverse geocode
        results = reverse_geocode(lat, lng, API_KEY)
        print_geocode_results(results)
    else:
        # Người dùng nhập keyword -> dùng Places Text Search
        results = place_search_text(user_input, API_KEY)
        print_place_results(results)
