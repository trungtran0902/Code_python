import requests
import time
import random
import openpyxl
from openpyxl import Workbook

# Tạo workbook và worksheet để lưu kết quả vào Excel
wb = Workbook()
ws = wb.active
ws.append(["Số thứ tự", "Tên quán", "Địa chỉ", "Số điện thoại", "Đánh giá trung bình", "Vĩ độ", "Kinh độ", "Khoảng cách", "Giao hàng", "Mở cửa", "Google Maps"])

# Danh sách các URL API
api_urls = [
    "https://www.foody.vn/__get/Place/HomeListPlace?t=1770259102117&page=1&lat=10.823099&lon=106.629664&count=12&districtId=&cateId=&cuisineId=&isReputation=&type=1",
    "https://www.foody.vn/__get/Place/HomeListPlace?t=1770259105077&page=2&lat=10.823099&lon=106.629664&count=12&districtId=&cateId=&cuisineId=&isReputation=&type=1"
    # Thêm các API URL khác nếu cần
]

# Khởi tạo biến đếm tổng số quán
total_place = 0

# Đặt tên file Excel trước khi bắt đầu
excel_file = "restaurants_data.xlsx"

# B2: gọi từng API
for idx, api_url in enumerate(api_urls, start=1):
    print(f"\n🌐 [{idx}/{len(api_urls)}] GET: {api_url}")

    try:
        # Thêm headers để mô phỏng yêu cầu từ trình duyệt
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',  # Chấp nhận JSON
            'Accept-Encoding': 'gzip, deflate, br',  # Thêm encoding
            'Connection': 'keep-alive'  # Giữ kết nối mở
        }

        # Gửi yêu cầu GET tới API với headers
        r = requests.get(api_url, headers=headers, timeout=15)
        print("Status:", r.status_code)

        # Kiểm tra nếu mã trạng thái không phải 200 (thành công)
        if r.status_code != 200:
            print("❌ Lỗi request")
            continue

        # Kiểm tra nếu phản hồi có thể là JSON
        try:
            js = r.json()
            items = js.get("Items", [])
        except ValueError:
            print("❌ Không thể parse dữ liệu JSON")
            print("Phản hồi từ API:")
            print(r.text)  # In ra nội dung phản hồi để xem API trả về gì
            continue

        print(f"Số quán trong batch: {len(items)}")

        # Xử lý từng quán trong danh sách
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

            # Thêm thông tin quán vào worksheet
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

        # 💾 Lưu dữ liệu vào file Excel sau mỗi lần gọi API
        wb.save(excel_file)
        print("💾 Đã lưu Excel")

        # ⏳ Delay ngẫu nhiên 2–3s giữa các lần gọi API
        sleep_time = random.uniform(2, 3)
        print(f"⏳ Nghỉ {sleep_time:.2f}s để tránh call API liên tục...")
        time.sleep(sleep_time)

    except Exception as e:
        print("❌ Lỗi:", e)

print(f"\n🎉 DONE – Tổng số quán lấy được: {total_place}")
print(f"📁 File Excel: {excel_file}")
