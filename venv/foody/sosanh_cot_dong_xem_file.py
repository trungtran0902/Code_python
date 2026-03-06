import streamlit as st
import pandas as pd
from io import BytesIO
from unidecode import unidecode
from rapidfuzz import fuzz
import math

# ======================================================
# INIT SESSION STATE
# ======================================================
if "result_df" not in st.session_state:
    st.session_state.result_df = None

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(page_title="Excel Tool – Compare & View", layout="wide")
st.title("📊 Excel Tool – So sánh & Xem file")

# ======================================================
# HELPERS
# ======================================================
def normalize_text(text):
    if pd.isna(text):
        return ""
    text = unidecode(str(text).lower())
    for ch in [",", ".", "-", "/", "\\"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())

def safe_float(x):
    if pd.isna(x):
        return None
    try:
        v = float(str(x).replace(",", "."))
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except:
        return None

# ======================================================
# B1 – UPLOAD FILE
# ======================================================
uploaded_file = st.file_uploader("📂 B1. Chọn file Excel", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    columns = df.columns.tolist()

    total_rows = len(df)
    total_cols = len(df.columns)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("📄 Tổng số dòng", f"{total_rows:,}")
    with c2:
        st.metric("📊 Tổng số cột", f"{total_cols}")

    # ==================================================
    # B2 – CHỌN CHỨC NĂNG
    # ==================================================
    mode = st.radio(
        "📌 B2. Chọn chức năng",
        ["TH1 – So sánh & xem file", "TH2 – Chỉ xem file Excel", "TH3 – So sánh theo dòng"]
    )

    # ==================================================
    # TH1 – SO SÁNH & XEM FILE
    # ==================================================
    if mode.startswith("TH1"):
        st.subheader("🧠 Chọn cột để so sánh")

        c1, c2 = st.columns(2)
        with c1:
            col_name_1 = st.selectbox("Tên (nguồn 1)", columns, key="c_n1")
            col_addr_1 = st.selectbox("Địa chỉ (nguồn 1)", columns, key="c_a1")
            col_lat_1  = st.selectbox("Lat (nguồn 1)", columns, key="c_lat1")
            col_lng_1  = st.selectbox("Lng (nguồn 1)", columns, key="c_lng1")
        with c2:
            col_name_2 = st.selectbox("Tên (nguồn 2)", columns, key="c_n2")
            col_addr_2 = st.selectbox("Địa chỉ (nguồn 2)", columns, key="c_a2")
            col_lat_2  = st.selectbox("Lat (nguồn 2)", columns, key="c_lat2")
            col_lng_2  = st.selectbox("Lng (nguồn 2)", columns, key="c_lng2")

        name_thr = st.slider("Ngưỡng giống TÊN", 0, 100, 90)
        addr_thr = st.slider("Ngưỡng giống ĐỊA CHỈ", 0, 100, 90)
        dist_thr = st.slider("Ngưỡng khoảng cách (m)", 0, 500, 30)

        if st.button("▶️ Chạy so sánh"):
            st.session_state.result_df = run_compare(
                df,
                col_name_1, col_name_2,
                col_addr_1, col_addr_2,
                col_lat_1, col_lng_1,
                col_lat_2, col_lng_2,
                name_thr, addr_thr, dist_thr
            )

        if st.session_state.result_df is not None:
            result_df = st.session_state.result_df

            # ======================================================
            # LỌC KẾT QUẢ - LỌC CỘT (Đã có từ trước)
            # ======================================================
            if 'filter_conditions' not in st.session_state:
                st.session_state.filter_conditions = []

            # Thêm điều kiện lọc mới khi nhấn nút
            if st.button("➕ Thêm điều kiện lọc"):
                st.session_state.filter_conditions.append({"column": None, "values": []})

            # Hiển thị các bộ lọc hiện tại
            for idx, condition in enumerate(st.session_state.filter_conditions):
                col_name = st.selectbox(
                    f"Chọn cột để lọc - Điều kiện {idx + 1}",
                    columns,
                    key=f"filter_col_{idx}"
                )
                selected_values = st.multiselect(
                    f"Chọn giá trị cho {col_name} - Điều kiện {idx + 1}",
                    df[col_name].dropna().astype(str).unique().tolist(),
                    default=df[col_name].dropna().astype(str).unique().tolist(),
                    key=f"filter_values_{idx}"
                )

                st.session_state.filter_conditions[idx]["column"] = col_name
                st.session_state.filter_conditions[idx]["values"] = selected_values

            # Lọc dữ liệu theo các điều kiện đã chọn (Áp dụng theo kiểu "và" - AND)
            filtered_df = result_df.copy()
            for condition in st.session_state.filter_conditions:
                if condition["column"] and condition["values"]:
                    filtered_df = filtered_df[filtered_df[condition["column"]].isin(condition["values"])]

            # Hiển thị bảng dữ liệu đã lọc
            st.subheader("🔎 Kết quả đã lọc")
            st.dataframe(filtered_df.style.applymap(color_result, subset=["Kết luận"]), use_container_width=True)

    # ==================================================
    # TH2 – CHỈ XEM FILE EXCEL
    # ==================================================
    elif mode.startswith("TH2"):
        st.subheader("👀 Xem & lọc file Excel")

        filter_col = st.selectbox("Chọn cột để lọc", columns, key="f2")
        values = df[filter_col].dropna().astype(str).unique().tolist()
        selected = st.multiselect("Chọn giá trị", values, default=values)

        filtered_df = df[df[filter_col].astype(str).isin(selected)]
        st.dataframe(
            filtered_df.style.applymap(color_result, subset=["Kết luận"]),
            use_container_width=True
        )

    # ==================================================
    # TH3 – SO SÁNH THEO DÒNG
    # ==================================================
    elif mode.startswith("TH3"):
        st.subheader("🧠 So sánh theo dòng (Tìm trùng tên quán)")

        # Lựa chọn cột để so sánh (tên quán)
        col_name = st.selectbox("Chọn cột để so sánh (ví dụ: Tên quán)", columns, key="col_name")

        name_thr = st.slider("Ngưỡng giống TÊN", 0, 100, 90)

        if st.button("▶️ Chạy so sánh theo dòng"):
            # Chuẩn hóa tên trong cột được chọn
            df["name_norm"] = df[col_name].apply(normalize_text)

            # Tạo một cột để lưu kết quả so sánh
            def compare(row, df):
                similar_rows = []
                for idx, compare_row in df.iterrows():
                    if fuzz.token_set_ratio(row["name_norm"], compare_row["name_norm"]) >= name_thr and row.name != compare_row.name:
                        similar_rows.append(compare_row.name)
                return similar_rows

            # Áp dụng so sánh với tất cả các dòng
            df["Trùng với"] = df.apply(compare, axis=1, df=df)

            # Lọc những dòng có tên giống nhau hoặc gần giống
            result_df = df[df["Trùng với"].apply(len) > 0]

            if result_df.empty:
                st.warning("Không tìm thấy dòng nào trùng tên gần đúng.")
            else:
                # Sắp xếp các dòng trùng nhau cạnh nhau
                result_df = result_df.explode("Trùng với")

                # Hiển thị kết quả đã sắp xếp
                st.subheader("🔎 Kết quả trùng tên gần đúng")
                st.dataframe(result_df.style.applymap(lambda val: "background-color: #FFF9C4" if val != "" else "", subset=["Trùng với"]), use_container_width=True)

                # Export (Download button)
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    result_df.to_excel(writer, index=False, sheet_name="Filtered")

                st.download_button(
                    "⬇️ Tải Excel đã lọc",
                    data=buffer.getvalue(),
                    file_name="excel_trung_ten.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

else:
    st.info("👆 Vui lòng chọn file Excel để bắt đầu.")