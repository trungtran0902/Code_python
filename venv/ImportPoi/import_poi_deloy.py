import io
from datetime import UTC, datetime

import pandas as pd
import requests
import streamlit as st

API_URL = "https://api-data.map4d.vn/map/manage/place"
REQUEST_TIMEOUT = 30
REQUIRED_COLUMNS = [
    "Name",
    "Address",
    "OldAddress",
    "Latitude",
    "Longitude",
    "Type",
    "Tags",
    "Phone",
]
REQUIRED_ROW_FIELDS = ["Name", "Address", "Latitude", "Longitude"]

st.set_page_config(page_title="Map4D Import POI Tool", layout="wide")

st.title("Map4D Import POI Tool")

# ===== TOKEN INPUT =====
token = st.text_input(
    "Authorization Token",
    placeholder="Bearer xxxxxxxxxxxxxxxxx",
)

headers = {
    "accept": "text/plain",
    "Authorization": token.strip(),
    "Content-Type": "application/json",
}

# ===== FILE UPLOAD =====
st.markdown("### Input file format")
st.info(
    "Excel file can phai co cac cot sau: Name, Address, OldAddress, Latitude, "
    "Longitude, Type, Tags, Phone"
)

sample_columns_df = pd.DataFrame(
    [
        {
            "Name": "Sample POI",
            "Address": "123 Example Street",
            "OldAddress": "Old Example Address",
            "Latitude": 21.0285,
            "Longitude": 105.8542,
            "Type": "restaurant",
            "Tags": "sample-tag",
            "Phone": "0123456789",
        }
    ]
)

st.caption("Example input row")
st.dataframe(sample_columns_df, use_container_width=True)

uploaded_file = st.file_uploader(
    "Upload Excel file",
    type=["xlsx", "xls"],
)


def is_blank(value):
    return pd.isna(value) or str(value).strip() == ""


def validate_token(auth_token):
    if not auth_token or not auth_token.strip():
        return False, "Token dang trong."

    try:
        response = requests.post(API_URL, headers=headers, json={}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        return False, f"Khong kiem tra duoc token: {e}"

    if response.status_code in (401, 403):
        return False, f"Token khong hop le hoac khong co quyen. API tra ve {response.status_code}."

    if response.status_code in (200, 201, 400, 405, 409, 422):
        return True, f"Token hop le. API phan hoi {response.status_code} khi kiem tra."

    return False, (
        "Khong xac minh duoc token. "
        f"API tra ve {response.status_code}: {response.text}"
    )


def validate_dataframe_columns(df):
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    extra_columns = [col for col in df.columns if col not in REQUIRED_COLUMNS]
    return missing_columns, extra_columns


def validate_row(row):
    missing_fields = [field for field in REQUIRED_ROW_FIELDS if is_blank(row.get(field))]
    if missing_fields:
        return False, f"Thieu du lieu bat buoc: {', '.join(missing_fields)}"

    try:
        lat = float(row.get("Latitude"))
        lng = float(row.get("Longitude"))
    except (TypeError, ValueError):
        return False, "Latitude hoac Longitude khong dung dinh dang so."

    if not (-90 <= lat <= 90):
        return False, "Latitude phai nam trong khoang -90 den 90."

    if not (-180 <= lng <= 180):
        return False, "Longitude phai nam trong khoang -180 den 180."

    return True, ""


def upload_place(row):
    row_valid, row_message = validate_row(row)
    if not row_valid:
        return "INVALID", None, row_message

    name = str(row.get("Name", "")).strip()
    address = str(row.get("Address", "")).strip()
    old_address = str(row.get("OldAddress", "")).strip()
    phone = str(row.get("Phone", "")).strip()

    lat = float(row.get("Latitude"))
    lng = float(row.get("Longitude"))

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
        "oldAddress": old_address,
        "photos": [],
        "startDate": datetime.now(UTC).isoformat(),
        "endDate": datetime.now(UTC).isoformat(),
        "phoneNumber": phone or None,
        "website": None,
        "businessHours": [],
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat],
        },
        "rank": {"value": 0},
        "layer": "address",
        "source": None,
        "metadata": [],
    }

    try:
        response = requests.post(API_URL, headers=headers, json=place, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        return "ERROR", None, str(e)

    if response.status_code not in (200, 201):
        return "FAIL", None, f"{response.status_code}: {response.text}"

    try:
        resp_json = response.json()
    except ValueError as e:
        return "FAIL", None, (
            "API tra ve thanh cong nhung response khong phai JSON, "
            f"khong doc duoc id. Chi tiet: {e}"
        )

    place_id = None
    if isinstance(resp_json, dict):
        if "result" in resp_json and isinstance(resp_json["result"], dict):
            place_id = resp_json["result"].get("id")
        if not place_id:
            place_id = resp_json.get("id") or resp_json.get("placeId")

    if not place_id:
        return "FAIL", None, (
            "API tra ve thanh cong nhung khong phat sinh id. "
            "Ban ghi chua duoc coi la import thanh cong."
        )

    return "OK", place_id, "Uploaded"


# ===== PROCESS FILE =====
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, dtype={"Phone": str})
    except ImportError:
        st.error(
            "Missing Excel dependency in deployment environment. "
            "Please add 'openpyxl' to requirements.txt."
        )
        st.stop()

    missing_columns, extra_columns = validate_dataframe_columns(df)

    if missing_columns:
        st.error(
            "File Excel sai ten cot hoac thieu cot bat buoc. "
            f"Thieu: {', '.join(missing_columns)}"
        )
        st.stop()

    if extra_columns:
        st.warning(f"Phat hien cot ngoai mau: {', '.join(extra_columns)}")

    st.subheader("Preview data")
    st.dataframe(df)

    total = len(df)
    st.write(f"Total rows: {total}")

    if st.button("Start Import"):
        token_valid, token_message = validate_token(token)
        if not token_valid:
            st.error(token_message)
            st.stop()

        st.success(token_message)

        progress = st.progress(0)
        results = []

        for i, row in df.iterrows():
            status, place_id, message = upload_place(row)

            results.append(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": status,
                    "id": place_id,
                    "message": message,
                    "name": row.get("Name"),
                    "address": row.get("Address"),
                    "phone": row.get("Phone"),
                    "lat": row.get("Latitude"),
                    "lng": row.get("Longitude"),
                    "tags": row.get("Tags"),
                }
            )

            progress.progress((i + 1) / total)

        result_df = pd.DataFrame(results)

        st.success("Import completed")
        st.dataframe(result_df, use_container_width=True)

        success_df = result_df[result_df["status"] == "OK"].copy()
        error_df = result_df[result_df["status"] != "OK"].copy()

        if not success_df.empty:
            st.subheader("Imported records")
            st.write(f"Successful imports: {len(success_df)}/{total}")
            st.dataframe(
                success_df[["id", "name", "address", "phone", "lat", "lng", "tags"]],
                use_container_width=True,
            )

            st.text("Created IDs")
            st.code("\n".join(success_df["id"].fillna("NO_ID").astype(str).tolist()))

            print("Import completed successfully.")
            print("Created records:")
            print(
                success_df[["id", "name", "address", "phone", "lat", "lng", "tags"]]
                .to_string(index=False)
            )
        else:
            st.warning("Import finished but no records were created successfully.")
            print("Import finished but no records were created successfully.")

        if not error_df.empty:
            st.subheader("Import errors")
            st.write(f"Rows with errors: {len(error_df)}/{total}")
            st.dataframe(error_df, use_container_width=True)

        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False)

        st.download_button(
            "Download Log CSV",
            csv_buffer.getvalue(),
            "upload_log.csv",
            "text/csv",
        )
