import streamlit as st
import pandas as pd
from io import BytesIO
from unidecode import unidecode
from rapidfuzz import fuzz
from geopy.distance import geodesic
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

def calc_distance(lat1, lng1, lat2, lng2):
    if any(v is None for v in [lat1, lng1, lat2, lng2]):
        return None
    try:
        return round(geodesic((lat1, lng1), (lat2, lng2)).meters, 2)
    except:
        return None

def run_compare(
    df,
    col_name_1, col_name_2,
    col_addr_1, col_addr_2,
    col_lat_1, col_lng_1,
    col_lat_2, col_lng_2,
    name_thr, addr_thr, dist_thr
):
    df = df.copy()

    df["ten_norm"] = df[col_name_1].apply(normalize_text)
    df["name_norm"] = df[col_name_2].apply(normalize_text)
    df["addr1_norm"] = df[col_addr_1].apply(normalize_text)
    df["addr2_norm"] = df[col_addr_2].apply(normalize_text)

    df["lat1"] = df[col_lat_1].apply(safe_float)
    df["lng1"] = df[col_lng_1].apply(safe_float)
    df["lat2"] = df[col_lat_2].apply(safe_float)
    df["lng2"] = df[col_lng_2].apply(safe_float)

    def compare(row):
        name_score = fuzz.token_set_ratio(row["ten_norm"], row["name_norm"])
        name_exact = row["ten_norm"] == row["name_norm"] and row["ten_norm"] != ""

        if name_exact:
            return pd.Series(["Trùng quán (tên chính xác)", 100, name_score, None])
        if name_score >= name_thr:
            return pd.Series(["Trùng quán (tên gần đúng)", name_score, name_score, None])

        addr_score = fuzz.token_set_ratio(row["addr1_norm"], row["addr2_norm"])
        if addr_score >= addr_thr:
            return pd.Series(["Trùng địa chỉ", addr_score, name_score, None])

        distance_m = calc_distance(
            row["lat1"], row["lng1"], row["lat2"], row["lng2"]
        )

        if distance_m is not None and distance_m <= dist_thr:
            return pd.Series(["Gần nhau nhưng khác địa chỉ", 40, name_score, distance_m])
        if distance_m is not None:
            return pd.Series(["Khác", 0, name_score, distance_m])

        return pd.Series(["Thiếu tọa độ", 0, name_score, None])

    df[["Kết luận", "Độ tin cậy (%)", "Điểm giống tên", "Khoảng cách (m)"]] = df.apply(compare, axis=1)

    df.drop(columns=[
        "ten_norm", "name_norm",
        "addr1_norm", "addr2_norm",
        "lat1", "lng1", "lat2", "lng2"
    ], inplace=True)

    return df

def color_result(val):
    if "Trùng quán" in val:
        return "background-color: #C8E6C9"
    if "Trùng địa chỉ" in val:
        return "background-color: #FFF9C4"
    if "Khác" in val:
        return "background-color: #FFCDD2"
    return ""

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
        ["TH1 – So sánh & xem file", "TH2 – Chỉ xem file Excel"]
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
            # LỌC KẾT QUẢ - THÊM ĐIỀU KIỆN LỌC
            # ======================================================
            if 'filter_conditions' not in st.session_state:
                st.session_state.filter_conditions = []

            # Thêm điều kiện lọc mới khi nhấn nút
            if st.button("➕ Thêm điều kiện lọc"):
                # Mỗi điều kiện sẽ là một tuple gồm (column_name, selected_values)
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

                # Lưu lại giá trị đã chọn
                st.session_state.filter_conditions[idx]["column"] = col_name
                st.session_state.filter_conditions[idx]["values"] = selected_values

            # Lọc dữ liệu theo các điều kiện đã chọn (Áp dụng theo kiểu "và" - AND)
            filtered_df = result_df.copy()

            # Duyệt qua tất cả các điều kiện lọc và áp dụng "và" (AND)
            for condition in st.session_state.filter_conditions:
                if condition["column"] and condition["values"]:
                    # Áp dụng lọc với "và" (AND) - chỉ chọn những bản ghi thỏa mãn tất cả các điều kiện
                    filtered_df = filtered_df[filtered_df[condition["column"]].isin(condition["values"])]

            # Hiển thị bảng dữ liệu đã lọc
            st.subheader("🔎 Lọc kết quả")
            st.dataframe(filtered_df.style.applymap(color_result, subset=["Kết luận"]), use_container_width=True)

    # ==================================================
    # TH2 – CHỈ XEM FILE EXCEL
    # ==================================================
    else:
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
    # EXPORT (CHUNG CHO CẢ 2 TH)
    # ==================================================
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        filtered_df.to_excel(writer, index=False, sheet_name="Filtered")

    st.download_button(
        "⬇️ Tải Excel đã lọc",
        data=buffer.getvalue(),
        file_name="excel_da_loc.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👆 Vui lòng chọn file Excel để bắt đầu.")


#=== dùng lệnh "streamlit run sosanh_loc_xem_file.py" chạy trong ternimal==