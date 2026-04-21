import io
import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from business_hours_utils import BUSINESS_HOURS_COLUMNS, get_business_hours

API_URL = "https://api-data.map4d.vn/map/manage/place"
REQUEST_TIMEOUT = 30
CHECKPOINT_DIR = Path(__file__).resolve().parent
IMPORT_CHUNK_SIZE = 25
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
    "error_type",
    "error_column",
    "error_value",
]

st.set_page_config(page_title="Map4D Import POI Tool", layout="wide")

st.title("Map4D Import POI Tool")

CHECKPOINT_DIR.mkdir(exist_ok=True)

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


def summarize_value(value, max_length=200):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def get_business_hours_source(row):
    for column_name in BUSINESS_HOURS_COLUMNS:
        if column_name in row and not is_blank(row.get(column_name)):
            return column_name, row.get(column_name)
    return None, None


def sanitize_token_for_state(auth_token):
    token_value = (auth_token or "").strip()
    if not token_value:
        return ""
    return hashlib.sha256(token_value.encode("utf-8")).hexdigest()[:16]


def build_file_key(file_bytes, auth_token):
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
    token_hash = sanitize_token_for_state(auth_token)
    return f"{file_hash}_{token_hash or 'no_token'}"


def get_control_state_key(file_key):
    return f"import_control_state_{file_key}"


def get_checkpoint_path(file_key):
    return CHECKPOINT_DIR / f"{file_key}.json"


def load_checkpoint(file_key):
    checkpoint_path = get_checkpoint_path(file_key)
    if not checkpoint_path.exists():
        return None

    try:
        return json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_checkpoint(file_key, checkpoint_data):
    checkpoint_path = get_checkpoint_path(file_key)
    checkpoint_path.write_text(
        json.dumps(checkpoint_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_checkpoint(file_key):
    checkpoint_path = get_checkpoint_path(file_key)
    if checkpoint_path.exists():
        checkpoint_path.unlink()


def init_checkpoint(file_key, total_rows):
    checkpoint_data = {
        "status": "in_progress",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_rows": total_rows,
        "results": [],
        "processed_indices": [],
        "last_error": None,
    }
    save_checkpoint(file_key, checkpoint_data)
    return checkpoint_data


def checkpoint_to_dataframe(checkpoint_data):
    result_df = pd.DataFrame(checkpoint_data.get("results", []))
    if result_df.empty:
        return pd.DataFrame(columns=LOG_COLUMNS)
    return result_df


def format_progress_text(processed_count, total_count, status_text):
    if total_count <= 0:
        return f"Trang thai: {status_text} | 0/0 dong | 0.00%"

    percent = (processed_count / total_count) * 100
    return (
        f"Trang thai: {status_text} | "
        f"{processed_count}/{total_count} dong | {percent:.2f}%"
    )


def build_result_row(row, status, place_id, message, diagnostics=None):
    row_data = {}
    if hasattr(row, "to_dict"):
        row_data = row.to_dict()
    elif isinstance(row, dict):
        row_data = dict(row)

    row_data.update(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "id": place_id,
            "message": message,
            "error_type": (diagnostics or {}).get("error_type"),
            "error_column": (diagnostics or {}).get("error_column"),
            "error_value": (diagnostics or {}).get("error_value"),
        }
    )
    return row_data


def build_result_dataframe(results, input_columns):
    result_df = pd.DataFrame(results)
    appended_columns = ["time", "status", "id", "message"]
    ordered_columns = list(input_columns) + [
        col for col in appended_columns if col in result_df.columns
    ]
    remaining_columns = [col for col in result_df.columns if col not in ordered_columns]
    return result_df.reindex(columns=ordered_columns + remaining_columns)


def get_optional_value(row, *column_names):
    for column_name in column_names:
        if column_name in row and not is_blank(row.get(column_name)):
            return str(row.get(column_name)).strip()
    return None


def parse_multi_value_cell(value):
    if is_blank(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def validate_row(row):
    missing_fields = [field for field in REQUIRED_ROW_FIELDS if is_blank(row.get(field))]
    if missing_fields:
        first_missing = missing_fields[0]
        return False, (
            f"Thieu du lieu bat buoc o cot '{first_missing}'."
        ), {
            "error_type": "missing_required_value",
            "error_column": first_missing,
            "error_value": summarize_value(row.get(first_missing)),
        }

    try:
        lat = float(row.get("Latitude"))
        lng = float(row.get("Longitude"))
    except (TypeError, ValueError):
        invalid_column = "Latitude"
        invalid_value = row.get("Latitude")
        try:
            float(row.get("Latitude"))
        except (TypeError, ValueError):
            invalid_column = "Latitude"
            invalid_value = row.get("Latitude")
        else:
            invalid_column = "Longitude"
            invalid_value = row.get("Longitude")
        return False, (
            f"Cot '{invalid_column}' co gia tri khong dung dinh dang so."
        ), {
            "error_type": "invalid_number",
            "error_column": invalid_column,
            "error_value": summarize_value(invalid_value),
        }

    if not (-90 <= lat <= 90):
        return False, "Latitude phai nam trong khoang -90 den 90.", {
            "error_type": "out_of_range",
            "error_column": "Latitude",
            "error_value": summarize_value(row.get("Latitude")),
        }

    if not (-180 <= lng <= 180):
        return False, "Longitude phai nam trong khoang -180 den 180.", {
            "error_type": "out_of_range",
            "error_column": "Longitude",
            "error_value": summarize_value(row.get("Longitude")),
        }

    try:
        get_business_hours(row)
    except ValueError as exc:
        source_column, source_value = get_business_hours_source(row)
        return False, str(exc), {
            "error_type": "invalid_structure",
            "error_column": source_column or "BusinessHours",
            "error_value": summarize_value(source_value),
        }

    return True, "", {}


def upload_place(row):
    row_valid, row_message, diagnostics = validate_row(row)
    if not row_valid:
        return "INVALID", None, row_message, False, diagnostics

    name = str(row.get("Name", "")).strip()
    address = str(row.get("Address", "")).strip()
    old_address = str(row.get("OldAddress", "")).strip()
    phone = get_optional_value(row, "Phone")
    website = get_optional_value(row, "Website", "website")

    lat = float(row.get("Latitude"))
    lng = float(row.get("Longitude"))

    types = parse_multi_value_cell(row.get("Type"))
    tags = parse_multi_value_cell(row.get("Tags"))
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
        return "ERROR", None, str(e), True, {
            "error_type": "request_exception",
            "error_column": None,
            "error_value": summarize_value(e),
        }

    if response.status_code not in (200, 201):
        return "FAIL", None, f"{response.status_code}: {response.text}", False, {
            "error_type": "api_error",
            "error_column": None,
            "error_value": summarize_value(response.text),
        }

    try:
        resp_json = response.json()
    except ValueError as e:
        return "FAIL", None, (
            "API tra ve thanh cong nhung response khong phai JSON, "
            f"khong doc duoc id. Chi tiet: {e}"
        ), False, {
            "error_type": "invalid_api_response",
            "error_column": None,
            "error_value": summarize_value(response.text),
        }

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
        ), False, {
            "error_type": "missing_id_in_response",
            "error_column": "Type/BusinessHours/payload",
            "error_value": summarize_value(resp_json),
        }

    return "OK", place_id, "Uploaded", False, {}


# ===== PROCESS FILE =====
if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    file_key = build_file_key(file_bytes, token)
    control_state_key = get_control_state_key(file_key)

    try:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype={"Phone": str})
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
            f"Thieu: {', '.join(missing_columns)}. "
            f"Cac cot hien co: {', '.join(df.columns.astype(str).tolist())}"
        )
        st.stop()

    if extra_columns:
        st.warning(f"Phat hien cot ngoai mau: {', '.join(extra_columns)}")

    st.subheader("Preview data")
    st.dataframe(df)

    total = len(df)
    st.write(f"Total rows: {total}")

    checkpoint_data = load_checkpoint(file_key)
    checkpoint_status = checkpoint_data.get("status", "in_progress") if checkpoint_data else "idle"
    current_control_status = st.session_state.get(control_state_key)
    if current_control_status is None:
        if checkpoint_status == "completed":
            current_control_status = "completed"
        elif checkpoint_data:
            current_control_status = "paused"
        else:
            current_control_status = "idle"
        st.session_state[control_state_key] = current_control_status

    if checkpoint_data:
        processed_count = len(checkpoint_data.get("processed_indices", []))
        status_label_map = {
            "in_progress": "dang chay",
            "paused": "dang tam dung",
            "completed": "da hoan thanh",
        }
        st.info(
            "Phat hien checkpoint truoc do: "
            f"{processed_count}/{checkpoint_data.get('total_rows', total)} dong da xu ly. "
            f"Trang thai: {checkpoint_status}."
        )
        st.caption(
            format_progress_text(
                processed_count,
                checkpoint_data.get("total_rows", total),
                status_label_map.get(checkpoint_status, checkpoint_status),
            )
        )
        if checkpoint_data.get("last_error"):
            st.warning(f"Loi gan nhat: {checkpoint_data['last_error']}")

        if checkpoint_status == "completed":
            completed_df = checkpoint_to_dataframe(checkpoint_data)
            st.subheader("Saved import result")
            st.dataframe(completed_df, use_container_width=True)

        restart_import = st.button("Start New Import")
        pause_import = current_control_status == "running" and st.button("Pause Import")
        resume_import = (
            checkpoint_status != "completed"
            and current_control_status != "running"
            and st.button("Resume Import")
        )
    else:
        restart_import = st.button("Start Import")
        pause_import = False
        resume_import = False

    if pause_import:
        st.session_state[control_state_key] = "paused"
        checkpoint_data = checkpoint_data or init_checkpoint(file_key, total)
        checkpoint_data["status"] = "paused"
        checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_checkpoint(file_key, checkpoint_data)
        st.rerun()

    if restart_import:
        delete_checkpoint(file_key)
        checkpoint_data = init_checkpoint(file_key, total)
        st.session_state[control_state_key] = "running"
        current_control_status = "running"

    if resume_import:
        if checkpoint_data is None:
            checkpoint_data = init_checkpoint(file_key, total)
        st.session_state[control_state_key] = "running"
        current_control_status = "running"

    if current_control_status == "running":
        token_valid, token_message = validate_token(token)
        if not token_valid:
            st.error(token_message)
            st.stop()

        st.success(token_message)

        if checkpoint_data is None:
            checkpoint_data = init_checkpoint(file_key, total)

        processed_indices = set(checkpoint_data.get("processed_indices", []))
        results = checkpoint_data.get("results", [])
        start_count = len(processed_indices)

        progress = st.progress(start_count / total if total else 0)
        status_placeholder = st.empty()
        status_placeholder.info(
            format_progress_text(start_count, total, "dang xu ly")
        )
        interrupted = False
        rows_processed_this_run = 0

        for i, row in df.iterrows():
            if i in processed_indices:
                continue

            status, place_id, message, should_stop, diagnostics = upload_place(row)

            row_result = build_result_row(row, status, place_id, message, diagnostics)
            results.append(row_result)
            processed_indices.add(i)
            rows_processed_this_run += 1

            checkpoint_data["results"] = results
            checkpoint_data["processed_indices"] = sorted(processed_indices)
            checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            checkpoint_data["last_error"] = message if should_stop else None
            checkpoint_data["status"] = "paused" if should_stop else "in_progress"
            save_checkpoint(file_key, checkpoint_data)

            current_count = len(processed_indices)
            progress.progress(current_count / total if total else 1)
            status_placeholder.info(
                format_progress_text(current_count, total, "dang xu ly")
            )

            if should_stop:
                interrupted = True
                st.session_state[control_state_key] = "paused"
                status_placeholder.warning(
                    format_progress_text(current_count, total, "dang tam dung")
                )
                st.error(
                    "Import tam dung do loi ket noi/request. "
                    "Ban co the bam 'Resume Import' de chay tiep tu dong chua xong."
                )
                break

            if rows_processed_this_run >= IMPORT_CHUNK_SIZE:
                break

        if len(processed_indices) >= total:
            checkpoint_data["status"] = "completed"
            checkpoint_data["last_error"] = None
            checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_checkpoint(file_key, checkpoint_data)
            st.session_state[control_state_key] = "completed"
            status_placeholder.success(
                format_progress_text(len(processed_indices), total, "da hoan thanh")
            )
        elif not interrupted:
            checkpoint_data["status"] = "in_progress"
            checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_checkpoint(file_key, checkpoint_data)
            st.session_state[control_state_key] = "running"

        result_df = build_result_dataframe(results, df.columns)

        if interrupted:
            st.warning(
                f"Da xu ly {len(processed_indices)}/{total} dong. "
                "Tien do da duoc luu de resume."
            )
        elif len(processed_indices) >= total:
            st.success("Import completed")
        else:
            st.info(
                f"He thong dang chay tiep theo tung dot. "
                f"Da xu ly {len(processed_indices)}/{total} dong."
            )
        st.dataframe(result_df, use_container_width=True)

        success_df = result_df[result_df["status"] == "OK"].copy()
        error_df = result_df[result_df["status"] != "OK"].copy()

        if not success_df.empty:
            st.subheader("Imported records")
            st.write(f"Successful imports: {len(success_df)}/{total}")
            st.dataframe(
                success_df,
                use_container_width=True,
            )

            print("Import completed successfully.")
            print("Created records:")
            print(success_df.to_string(index=False))
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

        if (
            st.session_state.get(control_state_key) == "running"
            and len(processed_indices) < total
            and not interrupted
        ):
            st.rerun()
