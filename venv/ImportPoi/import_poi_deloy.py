import streamlit as st
import pandas as pd
import requests
import csv
from datetime import datetime, UTC
import io

API_URL = "https://api-data.map4d.vn/map/manage/place"

st.set_page_config(page_title="Map4D Import POI Tool", layout="wide")

st.title("📥 Map4D Import POI Tool")

# ===== TOKEN INPUT =====
token = st.text_input(
    "Authorization Token",
    placeholder="Bearer xxxxxxxxxxxxxxxxx"
)

headers = {
    "accept": "text/plain",
    "Authorization": token,
    "Content-Type": "application/json"
}

# ===== FILE UPLOAD =====
uploaded_file = st.file_uploader(
    "Upload Excel file",
    type=["xlsx", "xls"]
)

def upload_place(row):

    name = str(row.get("Name", "")).strip()
    address = str(row.get("Address", "")).strip()
    oldAddress = str(row.get("OldAddress", "")).strip()
    phone = str(row.get("Phone", "")).strip()

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
        "phoneNumber": phone or None,
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

                return "OK", place_id, "Uploaded"

            except Exception as e:

                return "OK", None, f"Uploaded (parse error: {e})"

        else:

            return "FAIL", None, f"{response.status_code}: {response.text}"

    except Exception as e:

        return "ERROR", None, str(e)


# ===== PROCESS FILE =====
if uploaded_file:

    df = pd.read_excel(uploaded_file)

    st.subheader("📄 Preview data")
    st.dataframe(df)

    total = len(df)

    st.write(f"📌 Total rows: {total}")

    if st.button("🚀 Start Import"):

        progress = st.progress(0)

        results = []

        for i, row in df.iterrows():

            status, place_id, message = upload_place(row)

            results.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "id": place_id,
                "message": message,
                "name": row.get("Name"),
                "address": row.get("Address"),
                "phone": row.get("Phone"),
                "lat": row.get("Latitude"),
                "lng": row.get("Longitude"),
                "tags": row.get("Tags")
            })

            progress.progress((i + 1) / total)

        result_df = pd.DataFrame(results)

        st.success("✅ Import completed")

        st.dataframe(result_df)

        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False)

        st.download_button(
            "📥 Download Log CSV",
            csv_buffer.getvalue(),
            "upload_log.csv",
            "text/csv"
        )
