import time

OUTPUT_FILE = "foody_api_links.txt"
TOTAL_BATCH = 5

LAT = "21.033333"
LON = "105.85"
COUNT = 12

base = "https://www.foody.vn/__get/Place/HomeListPlace"

urls = []

for _ in range(TOTAL_BATCH):
    t = int(time.time() * 1000)

    url = (
        f"{base}"
        f"?t={t}"
        f"&page=1"
        f"&lat={LAT}"
        f"&lon={LON}"
        f"&count={COUNT}"
        f"&districtId="
        f"&cateId="
        f"&cuisineId="
        f"&isReputation="
        f"&type=1"
    )

    urls.append(url)
    time.sleep(1.2)  # giả lập thời gian user click

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for u in urls:
        f.write(u + "\n")

print("✅ Đã tạo link API đúng pattern Foody:")
for u in urls:
    print(u)
