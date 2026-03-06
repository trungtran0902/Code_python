import pandas as pd
import requests
import csv
from datetime import datetime, UTC
import os

# ====== CONFIG ======
API_URL = "https://api-data.map4d.vn/map/manage/place"
BEARER_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJNMUtocHl1OGg1cjlxVkNfN29hbDJaUERseU9CRjJMazkwdlVBS2hTNko0In0.eyJqdGkiOiIxNDVlNTMzMi0yNGJlLTQ2OWQtYjE5Yy1kZGNhNWY0MDViMjQiLCJleHAiOjE3NjY2MzIyMjEsIm5iZiI6MCwiaWF0IjoxNzY1NzY4MjIyLCJpc3MiOiJodHRwczovL2FjY291bnRzLm1hcDRkLnZuL2F1dGgvcmVhbG1zL3ZpbWFwIiwiYXVkIjoiYWNjb3VudCIsInN1YiI6IjM2MzZkMjhlLTRiYzctNGUxNy04YzUxLWEzZGFmOGQzY2EwNSIsInR5cCI6IkJlYXJlciIsImF6cCI6Im1hcDRkIiwiYXV0aF90aW1lIjoxNzY1NzY4MjIxLCJzZXNzaW9uX3N0YXRlIjoiNjNkMWRmYjEtMjU4Ny00M2QzLWE4MjEtMzFhNjcyNDE5MTNmIiwiYWNyIjoiMSIsInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJwcm9maWxlIGVtYWlsIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJUcuG6p24gQW5oIFRydW5nIiwicHJlZmVycmVkX3VzZXJuYW1lIjoidHJ1bmciLCJsb2NhbGUiOiJ2aSIsImdpdmVuX25hbWUiOiJUcuG6p24gQW5oIiwiZmFtaWx5X25hbWUiOiJUcnVuZyIsImVtYWlsIjoidHJ1bmd0YUBpb3RsaW5rLmNvbS52biJ9.QNYhyzhxQhEQf4_Jy9CaL4MqsZii15aq5AqKPFbRqkS_pNpdgsNPMxxJGhGZ_sNXU3EdTRJsLCM1D7J0SAJkY6oWrS42QR-LLruYP0AZAwFhBCu3sSUppHmYHxbGXmrC8knFRBKbirBVW7DuPqM84_xtl_TFJpGg7LtlirI1d0Yoie1MWytNkgb9-2P2VLeHVZiMe_dSWvsGoI2ux0J17pDViiVeQHYeOdmcRinAbnfbuLGiO74OQAImXpd-ddW1M0HSNd1VOyxa4Xhi4BkCDSEuU0JXe8X1YDZZ2Y4UERVkI4MOiAZRXbmYEcFpZMXEZF0NC91nxEZLjh8j9IqaTQ"   # 👉 thay token thật vào
# ====================

def upload_places_from_excel(excel_path):
    df = pd.read_excel(excel_path)

    headers = {
        "accept": "text/plain",
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Tạo tên file CSV mới theo timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"upload_log_{timestamp_str}.csv"

    with open(csv_filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time", "status", "id", "message",
            "name", "address", "lat", "lng", "tags"
        ])

        for _, row in df.iterrows():
            name = str(row.get("Name", "")).strip()
            address = str(row.get("Address", "")).strip()
            oldAddress = str(row.get("OldAddress", "")).strip()
            lat = float(row.get("Latitude", 0.0))
            lng = float(row.get("Longitude", 0.0))
            types = [str(row["Type"]).strip()] if pd.notna(row.get("Type")) else []
            tags = [str(row["Tags"]).strip()] if pd.notna(row.get("Tags")) else []

            place = {
                "location": {"lng": lng, "lat": lat},
                "name": name,
                "objectId": None,
                "description": None,
                "types": types,
                "tags": tags,
                "address": address,
                "oldAddress": oldAddress,
                "photos": [],
                "startDate": datetime.now(UTC).isoformat(),
                "endDate": datetime.now(UTC).isoformat(),
                "phoneNumber": None,
                "website": None,
                "businessHours": [],
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "rank": {"value": 0},
                "layer": "address",
                "source": None,
                "metadata": []
            }

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status, place_id, message = "ERROR", None, ""

            try:
                response = requests.post(API_URL, headers=headers, json=place)
                if response.status_code in (200, 201):
                    try:
                        resp_json = response.json()
                        place_id = None
                        if isinstance(resp_json, dict):
                            if "result" in resp_json and isinstance(resp_json["result"], dict):
                                place_id = resp_json["result"].get("id")
                            if not place_id:
                                place_id = resp_json.get("id") or resp_json.get("placeId")
                        status = "OK"
                        message = "Uploaded"
                        if not place_id:
                            message += f" (resp={resp_json})"
                    except Exception as e:
                        status = "OK"
                        message = f"Uploaded (parse error: {e})"
                else:
                    status = "FAIL"
                    message = f"{response.status_code}: {response.text}"
            except Exception as e:
                status = "ERROR"
                message = str(e)

            print(f"{timestamp} [{status}] {name} → id={place_id} {message}")

            writer.writerow([
                timestamp, status, place_id, message,
                name, address, lat, lng, ",".join(tags)
            ])

    print(f"\n✅ Hoàn thành upload. Kết quả được lưu trong {csv_filename}")


if __name__ == "__main__":
    folder_path = input("📂 Nhập đường dẫn chứa file Excel: ").strip()
    file_name = input("📄 Nhập tên file Excel (ví dụ: Aegona_Danh_sach_khach_san.xlsx): ").strip()

    excel_file_path = os.path.join(folder_path, file_name)

    if not os.path.exists(excel_file_path):
        print(f"❌ Không tìm thấy file: {excel_file_path}")
    else:
        upload_places_from_excel(excel_file_path)
