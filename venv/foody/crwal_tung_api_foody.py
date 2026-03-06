import requests
import time

COOKIE = "..."  # giữ nguyên cookie bạn đã có

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.foody.vn/",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": COOKIE
})

url = "https://www.foody.vn/__get/Place/HomeListPlace"
params = {
    "t": int(time.time() * 1000),
    "page": 1,
    "lat": 21.033333,
    "lon": 105.85,
    "count": 12,
    "type": 1
}

r = s.get(url, params=params, timeout=10)
js = r.json()

items = js.get("Items", [])

print("Status:", r.status_code)
print("Số quán:", len(items))

print(f"Số quán: {len(items)}\n")

for i, place in enumerate(items, start=1):
    print(f"#{i}")
    print("Tên     :", place.get("Name"))
    print("Địa chỉ :", place.get("Address"))
    print("Điện thoại:", place.get("Phone", "Không có"))
    print("Rating  :", place.get("AvgRating"))
    print("-" * 40)
