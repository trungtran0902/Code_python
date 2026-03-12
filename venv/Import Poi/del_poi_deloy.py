import streamlit as st
import requests
import pandas as pd
import os
import csv
from datetime import datetime

API_BASE_URL = "https://api-data.map4d.vn/map/manage/place/delete/"

st.set_page_config(page_title="Map4D POI Delete Tool", layout="wide")

st.title("🗑️ Map4D POI Delete Tool")

# ===== TOKEN INPUT =====
auth_token = st.text_input(
    "Nhập Authorization Token",
    placeholder="Bearer xxxxxxxxxxxxxxxxx"
)

headers = {
    "accept": "text/plain",
    "Authorization": auth_token
}

# ===== LOG =====
def get_log_file():
    today = datetime.now().strftime("%Y%m%d")
    log_dir = "logs"

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return os.path.join(log_dir, f"del_poi_{today}.csv")


def write_log(place_id, status, message):

    log_file = get_log_file()
    file_exists = os.path.isfile(log_file)

    with open(log_file, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["time", "place_id", "status", "message"])

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([timestamp, place_id, status, message])


# ===== CHECK TOKEN =====
def check_token():

    if not auth_token:
        st.error("❗ Vui lòng nhập token")
        return False

    test_id = "test_invalid_id"
    url = f"{API_BASE_URL}{test_id}"

    try:
        response = requests.post(url, headers=headers)

        if response.status_code == 401:
            st.error("❌ Token không hợp lệ hoặc đã hết hạn")
            return False

        st.success("✅ Token hợp lệ")
        return True

    except Exception as e:
        st.error(f"⚠️ Không thể kết nối API: {e}")
        return False


# ===== DELETE PLACE =====
def delete_place(place_id):

    url = f"{API_BASE_URL}{place_id}"

    try:
        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            write_log(place_id, "success", "Deleted successfully")
            return True, "Deleted successfully"

        else:
            msg = f"{response.status_code} - {response.text}"
            write_log(place_id, "error", msg)
            return False, msg

    except Exception as e:

        write_log(place_id, "error", str(e))
        return False, str(e)


# ===== MODE SELECT =====
mode = st.radio(
    "Chọn chế độ",
    ["Nhập ID thủ công", "Upload file CSV / Excel"]
)

# ===== TOKEN CHECK BUTTON =====
if st.button("🔑 Kiểm tra Token"):
    check_token()


# ===== MANUAL MODE =====
if mode == "Nhập ID thủ công":

    place_id = st.text_input("Nhập Place ID")

    if st.button("🗑️ Xoá POI"):

        if not check_token():
            st.stop()

        if place_id:

            success, message = delete_place(place_id)

            if success:
                st.success(f"✅ Đã xoá: {place_id}")

            else:
                st.error(f"❌ Lỗi: {message}")


# ===== FILE MODE =====
if mode == "Upload file CSV / Excel":

    uploaded_file = st.file_uploader(
        "Upload file",
        type=["csv", "xlsx"]
    )

    if uploaded_file:

        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)

        else:
            df = pd.read_excel(uploaded_file)

        st.write("📄 Preview dữ liệu")
        st.dataframe(df)

        if "id" not in df.columns:
            st.error("❗ File phải có cột 'id'")
            st.stop()

        ids = df["id"].dropna().astype(str).tolist()

        st.write(f"📌 Tổng ID: {len(ids)}")

        if st.button("🚀 Xoá tất cả"):

            if not check_token():
                st.stop()

            progress = st.progress(0)

            results = []

            for i, place_id in enumerate(ids):

                success, message = delete_place(place_id)

                results.append({
                    "id": place_id,
                    "status": "success" if success else "error",
                    "message": message
                })

                progress.progress((i + 1) / len(ids))

            result_df = pd.DataFrame(results)

            st.success("✅ Hoàn thành")

            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "📥 Download Result",
                csv,
                "delete_result.csv",
                "text/csv"
            )