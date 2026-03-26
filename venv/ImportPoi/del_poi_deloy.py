import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = "https://api-data.map4d.vn/map/manage/place/delete/"
REQUEST_TIMEOUT = 30
CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
DELETE_CHUNK_SIZE = 25
LOG_COLUMNS = ["source_row", "time", "id", "status", "message"]

st.set_page_config(page_title="Map4D POI Delete Tool", layout="wide")
st.title("Map4D POI Delete Tool")

CHECKPOINT_DIR.mkdir(exist_ok=True)


def build_headers(token):
    return {
        "accept": "text/plain",
        "Authorization": token,
    }


def format_progress_text(processed_count, total_count, status_label):
    percent = (processed_count / total_count * 100) if total_count else 0
    return f"Trang thai: {status_label} | {processed_count}/{total_count} dong | {percent:.2f}%"


def get_file_hash(uploaded_file_bytes):
    return hashlib.md5(uploaded_file_bytes).hexdigest()


def get_file_key(uploaded_file_name, uploaded_file_bytes, token, selected_id_column=""):
    file_hash = get_file_hash(uploaded_file_bytes)
    token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()[:12] if token else "no_token"
    safe_name = Path(uploaded_file_name).stem.replace(" ", "_")
    column_hash = hashlib.md5(selected_id_column.encode("utf-8")).hexdigest()[:8] if selected_id_column else "no_column"
    return f"delete_{safe_name}_{file_hash}_{token_hash}_{column_hash}"


def get_control_state_key(file_key):
    return f"delete_control_state_{file_key}"


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


def build_result_dataframe(results, original_columns):
    result_df = pd.DataFrame(results)
    if result_df.empty:
        return pd.DataFrame(columns=list(original_columns) + LOG_COLUMNS)

    ordered_columns = list(original_columns)
    for column in LOG_COLUMNS:
        if column not in ordered_columns:
            ordered_columns.append(column)

    for column in ordered_columns:
        if column not in result_df.columns:
            result_df[column] = None

    return result_df[ordered_columns]


def get_candidate_delete_rows(df, selected_id_column):
    candidate_rows = []
    for original_index, row in df.iterrows():
        place_id = str(row.get(selected_id_column, "")).strip()
        if place_id and place_id.lower() != "nan":
            candidate_rows.append((original_index, row, place_id))
    return candidate_rows


def check_token(token, show_message=True):
    if not token:
        if show_message:
            st.error("Vui long nhap token.")
        return False, "Thieu token"

    test_id = "test_invalid_id"
    url = f"{API_BASE_URL}{test_id}"

    try:
        response = requests.post(
            url,
            headers=build_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        if show_message:
            st.error(f"Khong the ket noi API: {exc}")
        return False, str(exc)

    if response.status_code == 401:
        if show_message:
            st.error("Token khong hop le hoac da het han.")
        return False, "401 - Unauthorized"

    if show_message:
        st.success("Token hop le.")
    return True, "OK"


def delete_place(place_id, token):
    url = f"{API_BASE_URL}{place_id}"

    try:
        response = requests.post(
            url,
            headers=build_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, str(exc), True

    if response.status_code == 200:
        return True, "Deleted successfully", False

    message = f"{response.status_code} - {response.text}"
    return False, message, False


auth_token = st.text_input(
    "Nhap Authorization Token",
    placeholder="Bearer xxxxxxxxxxxxxxxxx",
)

mode = st.radio(
    "Chon che do",
    ["Nhap ID thu cong", "Upload file CSV / Excel"],
)

if st.button("Kiem tra Token"):
    check_token(auth_token, show_message=True)


if mode == "Nhap ID thu cong":
    place_id = st.text_input("Nhap Place ID")

    if st.button("Xoa POI"):
        token_ok, token_message = check_token(auth_token, show_message=False)
        if not token_ok:
            st.error(token_message)
            st.stop()

        if not place_id:
            st.error("Vui long nhap Place ID.")
            st.stop()

        success, message, should_stop = delete_place(place_id.strip(), auth_token)
        if success:
            st.success(f"Da xoa: {place_id}")
        elif should_stop:
            st.error(f"Loi ket noi/request: {message}")
        else:
            st.error(f"Loi: {message}")


if mode == "Upload file CSV / Excel":
    uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.write("Preview du lieu")
        st.dataframe(df, use_container_width=True)

        id_like_columns = [column for column in df.columns if "id" in str(column).lower()]
        st.text_input(
            "So cot co chua 'id'",
            value=str(len(id_like_columns)),
            disabled=True,
        )

        if not id_like_columns:
            st.error("Khong tim thay cot nao co chua 'id' trong file.")
            st.stop()

        selected_id_column = st.selectbox(
            "Chon cot ID de xoa",
            options=id_like_columns,
            index=0,
        )

        candidate_rows = get_candidate_delete_rows(df, selected_id_column)
        st.text_input(
            "So dong co gia tri ID de xoa",
            value=str(len(candidate_rows)),
            disabled=True,
        )

        if not candidate_rows:
            st.warning(f"Khong co dong nao co gia tri trong cot {selected_id_column}.")
            st.stop()

        file_key = get_file_key(uploaded_file.name, file_bytes, auth_token, selected_id_column)
        control_state_key = get_control_state_key(file_key)
        total = len(candidate_rows)
        st.write(f"Total delete rows: {total}")

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
                completed_df = build_result_dataframe(checkpoint_data.get("results", []), df.columns)
                st.subheader("Saved delete result")
                st.dataframe(completed_df, use_container_width=True)

            restart_delete = st.button("Start New Delete")
            pause_delete = current_control_status == "running" and st.button("Pause Delete")
            resume_delete = (
                checkpoint_status != "completed"
                and current_control_status != "running"
                and st.button("Resume Delete")
            )
        else:
            restart_delete = st.button("Start Delete")
            pause_delete = False
            resume_delete = False

        if pause_delete:
            st.session_state[control_state_key] = "paused"
            checkpoint_data = checkpoint_data or init_checkpoint(file_key, total)
            checkpoint_data["status"] = "paused"
            checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_checkpoint(file_key, checkpoint_data)
            st.rerun()

        if restart_delete:
            delete_checkpoint(file_key)
            checkpoint_data = init_checkpoint(file_key, total)
            st.session_state[control_state_key] = "running"
            current_control_status = "running"

        if resume_delete:
            if checkpoint_data is None:
                checkpoint_data = init_checkpoint(file_key, total)
            st.session_state[control_state_key] = "running"
            current_control_status = "running"

        if current_control_status == "running":
            token_ok, token_message = check_token(auth_token, show_message=False)
            if not token_ok:
                st.error(token_message)
                st.stop()

            if checkpoint_data is None:
                checkpoint_data = init_checkpoint(file_key, total)

            processed_indices = set(checkpoint_data.get("processed_indices", []))
            results = checkpoint_data.get("results", [])
            start_count = len(processed_indices)

            progress = st.progress(start_count / total if total else 0)
            status_placeholder = st.empty()
            status_placeholder.info(format_progress_text(start_count, total, "dang xu ly"))

            interrupted = False
            rows_processed_this_run = 0

            for candidate_index, (original_index, row, place_id) in enumerate(candidate_rows):
                if candidate_index in processed_indices:
                    continue

                success, message, should_stop = delete_place(place_id, auth_token)
                result_row = row.to_dict()
                result_row.update(
                    {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source_row": int(original_index) + 1,
                        "id": place_id,
                        "status": "success" if success else "error",
                        "message": message,
                    }
                )
                results.append(result_row)
                processed_indices.add(candidate_index)
                rows_processed_this_run += 1

                checkpoint_data["results"] = results
                checkpoint_data["processed_indices"] = sorted(processed_indices)
                checkpoint_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                checkpoint_data["last_error"] = message if should_stop else None
                checkpoint_data["status"] = "paused" if should_stop else "in_progress"
                save_checkpoint(file_key, checkpoint_data)

                current_count = len(processed_indices)
                progress.progress(current_count / total if total else 1)
                status_placeholder.info(format_progress_text(current_count, total, "dang xu ly"))

                if should_stop:
                    interrupted = True
                    st.session_state[control_state_key] = "paused"
                    status_placeholder.warning(
                        format_progress_text(current_count, total, "dang tam dung")
                    )
                    st.error(
                        "Delete tam dung do loi ket noi/request. "
                        "Ban co the bam 'Resume Delete' de chay tiep tu dong chua xong."
                    )
                    break

                if rows_processed_this_run >= DELETE_CHUNK_SIZE:
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
            st.subheader("Delete result")
            st.dataframe(result_df, use_container_width=True)

            csv_bytes = result_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Download Result CSV",
                csv_bytes,
                "delete_result.csv",
                "text/csv",
            )

            if (
                st.session_state.get(control_state_key) == "running"
                and len(processed_indices) < total
                and not interrupted
            ):
                st.rerun()

        elif checkpoint_data and checkpoint_data.get("results"):
            result_df = build_result_dataframe(checkpoint_data.get("results", []), df.columns)
            st.subheader("Saved delete result")
            st.dataframe(result_df, use_container_width=True)
            csv_bytes = result_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Download Result CSV",
                csv_bytes,
                "delete_result.csv",
                "text/csv",
            )
