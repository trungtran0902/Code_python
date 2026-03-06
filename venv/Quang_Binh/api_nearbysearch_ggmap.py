# ====== FULL CODE (FIXED WINDOWS SAFE) ======
import requests
import csv
import os
import re
import time
import unicodedata
from datetime import datetime

API_KEY = "AIzaSyBEXoHOqcjbcK4D7isvej-oqvKVyUlxAuU"

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

location_input = input("📍 Nhập tọa độ tâm (lat,lng): ").strip()
radius = input("📏 Nhập bán kính (mét): ").strip()
keywords_input = input("🔎 Nhập keyword (phân cách bằng dấu ,): ").strip()

def parse_latlng(text):
    m = re.match(r"\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*", text)
    return (m.group(1), m.group(3)) if m else (None, None)

lat, lng = parse_latlng(location_input)
keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

def slugify(text, max_len=30):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"\s+", "_", text)
    return text[:max_len]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
first_kw = slugify(keywords[0])
output_file = os.path.join(
    OUTPUT_DIR,
    f"nearby_{first_kw}_{len(keywords)}kw_{timestamp}.csv"
)

FIELDNAMES = [
    "matched_keyword",
    "center_lat",
    "center_lng",
    "radius",
    "place_id",
    "name",
    "address",
    "lat",
    "lng",
    "rating",
    "user_ratings_total",
    "types"
]

seen_place_ids = set()

def save_to_csv(row):
    file_exists = os.path.isfile(output_file)
    with open(output_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def nearby_search(lat, lng, radius, keyword):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "key": API_KEY,
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": keyword,
        "language": "vi"
    }

    while True:
        resp = requests.get(url, params=params, timeout=30).json()
        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            print("❌ API ERROR:", resp.get("status"))
            break

        for place in resp.get("results", []):
            pid = place.get("place_id")
            if not pid or pid in seen_place_ids:
                continue
            seen_place_ids.add(pid)

            save_to_csv({
                "matched_keyword": keyword,
                "center_lat": lat,
                "center_lng": lng,
                "radius": radius,
                "place_id": pid,
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "lat": place["geometry"]["location"]["lat"],
                "lng": place["geometry"]["location"]["lng"],
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total"),
                "types": ",".join(place.get("types", []))
            })

        token = resp.get("next_page_token")
        if not token:
            break
        time.sleep(2.5)
        params["pagetoken"] = token

print(f"\n🚀 BẮT ĐẦU – {len(keywords)} keyword")
for kw in keywords:
    print(f"🔍 {kw}")
    nearby_search(lat, lng, radius, kw)

print(f"\n✅ HOÀN TẤT\n📁 File: {output_file}")
