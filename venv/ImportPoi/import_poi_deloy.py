import ast
import io
import json
from datetime import UTC, date, datetime, time

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
]
OPTIONAL_COLUMNS = [
    "Tags",
    "Phone",
    "Website",
    "website",
    "BusinessHours",
    "businessHours",
    "Time",
    "time",
    "Hours",
    "hours",
]
REQUIRED_ROW_FIELDS = ["Name", "Address", "OldAddress", "Latitude", "Longitude", "Type"]
LOG_COLUMNS = [
    "time",
    "status",
    "id",
    "message",
    "name",
    "address",
    "phone",
    "website",
    "lat",
    "lng",
    "tags",
]

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
    "Excel file bat buoc co 6 cot: Name, Address, OldAddress, Latitude, "
    "Longitude, Type. Cac cot khong bat buoc co the co: Tags, Phone, Website, "
    "BusinessHours/Time."
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
            "BusinessHours": (
                "[{'day': 1, 'start_time': '08:00', 'end_time': '17:30'}]"
            ),
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
    accepted_columns = set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    extra_columns = [col for col in df.columns if col not in accepted_columns]
    return missing_columns, extra_columns


def get_optional_value(row, *column_names):
    for column_name in column_names:
        if column_name in row and not is_blank(row.get(column_name)):
            return str(row.get(column_name)).strip()
    return None


def normalize_time_value(value):
    if is_blank(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%H%M")

    if isinstance(value, datetime):
        return value.strftime("%H%M")

    if isinstance(value, time):
        return value.strftime("%H%M")

    if isinstance(value, date):
        return "0000"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0 <= float(value) < 1:
            total_minutes = round(float(value) * 24 * 60)
            hours, minutes = divmod(total_minutes, 60)
            hours %= 24
            return f"{hours:02d}{minutes:02d}"

        text_value = f"{float(value):g}".strip()
    else:
        text_value = str(value).strip()

    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(text_value, fmt).strftime("%H%M")
        except ValueError:
            continue

    if len(text_value) == 4 and text_value.isdigit():
        return text_value

    if len(text_value) == 5 and text_value[2] == ":":
        return text_value.replace(":", "")

    raise ValueError(f"Khong doc duoc dinh dang gio: {value}")


def normalize_day_value(value):
    if is_blank(value):
        raise ValueError("Thieu gia tri day cho businessHours.")

    if isinstance(value, str):
        normalized = value.strip().lower()
        day_aliases = {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "sun": 0,
            "sunday": 0,
            "cn": 0,
            "mon": 1,
            "monday": 1,
            "thu2": 1,
            "t2": 1,
            "tue": 2,
            "tuesday": 2,
            "thu3": 2,
            "t3": 2,
            "wed": 3,
            "wednesday": 3,
            "thu4": 3,
            "t4": 3,
            "thu": 4,
            "thursday": 4,
            "thu5": 4,
            "t5": 4,
            "fri": 5,
            "friday": 5,
            "thu6": 5,
            "t6": 5,
            "sat": 6,
            "saturday": 6,
            "thu7": 6,
            "t7": 6,
        }
        if normalized in day_aliases:
            return day_aliases[normalized]

    try:
        day_value = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Gia tri day khong hop le: {value}") from exc

    if 1 <= day_value <= 7:
        return 0 if day_value == 7 else day_value

    if not 0 <= day_value <= 6:
        raise ValueError(f"Day phai nam trong khoang 0-6, nhan duoc {value}")

    return day_value


def parse_business_hours_value(raw_value):
    if is_blank(raw_value):
        return []

    parsed_value = raw_value
    if isinstance(raw_value, str):
        text_value = raw_value.strip()
        if not text_value:
            return []

        try:
            parsed_value = json.loads(text_value)
        except json.JSONDecodeError:
            try:
                parsed_value = ast.literal_eval(text_value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(
                    "BusinessHours/Time phai la JSON hoac Python list/dict hop le."
                ) from exc

    if isinstance(parsed_value, dict):
        parsed_items = [parsed_value]
    elif isinstance(parsed_value, list):
        parsed_items = parsed_value
    else:
        raise ValueError("BusinessHours/Time phai la list hoac dict.")

    normalized_items = []
    for item in parsed_items:
        if not isinstance(item, dict):
            raise ValueError("Moi businessHours item phai la object/dict.")

        if "open" in item and "close" in item:
            open_payload = item["open"]
            close_payload = item["close"]
            if not isinstance(open_payload, dict) or not isinstance(close_payload, dict):
                raise ValueError("open/close trong businessHours phai la dict.")

            day_open = normalize_day_value(open_payload.get("day"))
            day_close = normalize_day_value(close_payload.get("day"))
            time_open = normalize_time_value(open_payload.get("time"))
            time_close = normalize_time_value(close_payload.get("time"))
        else:
            day_open = normalize_day_value(
                item.get(
                    "open_day",
                    item.get("start_day", item.get("day", item.get("week_day"))),
                )
            )
            day_close = normalize_day_value(
                item.get(
                    "close_day",
                    item.get("end_day", item.get("day", item.get("week_day"))),
                )
            )
            time_open = normalize_time_value(
                item.get("open_time", item.get("start_time", item.get("from")))
            )
            time_close = normalize_time_value(
                item.get("close_time", item.get("end_time", item.get("to")))
            )

        normalized_items.append(
            {
                "open": {"day": day_open, "time": time_open},
                "close": {"day": day_close, "time": time_close},
            }
        )

    return normalized_items


def get_business_hours(row):
    raw_business_hours = None
    for column_name in ("BusinessHours", "businessHours", "Time", "time", "Hours", "hours"):
        if column_name in row and not is_blank(row.get(column_name)):
            raw_business_hours = row.get(column_name)
            break

    return parse_business_hours_value(raw_business_hours)


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

    try:
        get_business_hours(row)
    except ValueError as exc:
        return False, str(exc)

    return True, ""


def upload_place(row):
    row_valid, row_message = validate_row(row)
    if not row_valid:
        return "INVALID", None, row_message

    name = str(row.get("Name", "")).strip()
    address = str(row.get("Address", "")).strip()
    old_address = str(row.get("OldAddress", "")).strip()
    phone = get_optional_value(row, "Phone")
    website = get_optional_value(row, "Website", "website")

    lat = float(row.get("Latitude"))
    lng = float(row.get("Longitude"))

    types = [str(row["Type"]).strip()] if pd.notna(row.get("Type")) else []
    tags = [str(row["Tags"]).strip()] if pd.notna(row.get("Tags")) else []
    business_hours = get_business_hours(row)

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
        "phoneNumber": phone,
        "website": website,
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat],
        },
        "rank": {"value": 0},
        "layer": "address",
        "source": None,
        "metadata": [],
    }

    if business_hours:
        place["businessHours"] = business_hours

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
                    "website": row.get("Website", row.get("website")),
                    "lat": row.get("Latitude"),
                    "lng": row.get("Longitude"),
                    "tags": row.get("Tags"),
                }
            )

            progress.progress((i + 1) / total)

        result_df = pd.DataFrame(results)
        result_df = result_df.reindex(columns=LOG_COLUMNS)

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

        csv_bytes = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            "Download Log CSV",
            csv_bytes,
            "upload_log.csv",
            "text/csv",
        )
