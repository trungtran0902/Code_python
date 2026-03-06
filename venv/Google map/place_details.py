import requests
import json

def get_place_details(place_id, api_key):
    """
    Gọi Google Place Details API để lấy thông tin đầy đủ.
    """

    url = "https://maps.googleapis.com/maps/api/place/details/json"

    fields = (
        "address_component,"
        "adr_address,"
        "business_status,"
        "formatted_address,"
        "geometry,"
        "icon,"
        "icon_mask_base_uri,"
        "icon_background_color,"
        "name,"
        "photo,"
        "place_id,"
        "plus_code,"
        "type,"
        "url,"
        "utc_offset,"
        "vicinity,"
        "formatted_phone_number,"
        "international_phone_number,"
        "opening_hours,"
        "secondary_opening_hours,"
        "current_opening_hours,"
        "editorial_summary,"
        "reviews,"
        "user_ratings_total,"
        "rating,"
        "website"
    )

    params = {
        "place_id": place_id,
        "key": api_key,
        "language": "vi",
        "fields": fields,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print("❌ Lỗi khi gọi API:", e)
        return None

    data = response.json()

    if data.get("status") != "OK":
        print("❌ API lỗi:", data.get("status"))
        if "error_message" in data:
            print("Chi tiết:", data.get("error_message"))
        return None

    return data.get("result", {})


if __name__ == "__main__":
    print("=== GOOGLE PLACE DETAILS API ===")

    api_key = input("Nhập API Key: ").strip()
    place_id = input("Nhập Place ID: ").strip()

    print("\n⏳ Đang lấy dữ liệu...")

    details = get_place_details(place_id, api_key)

    if details:
        print("\n=== KẾT QUẢ ===\n")
        print(json.dumps(details, indent=4, ensure_ascii=False))
    else:
        print("❌ Không lấy được dữ liệu.")
