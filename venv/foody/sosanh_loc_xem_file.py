import math
from io import BytesIO

import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from rapidfuzz import fuzz
from unidecode import unidecode


if "result_df" not in st.session_state:
    st.session_state.result_df = None
if "filter_conditions" not in st.session_state:
    st.session_state.filter_conditions = []


st.set_page_config(page_title="Excel Tool - Compare & View", layout="wide")
st.title("Excel Tool - So sanh & Xem file")


def normalize_text(text):
    if pd.isna(text):
        return ""
    text = unidecode(str(text).lower())
    for ch in [",", ".", "-", "/", "\\"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def safe_float(value):
    if pd.isna(value):
        return None
    try:
        numeric = float(str(value).replace(",", "."))
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    except Exception:
        return None


def calc_distance(lat1, lng1, lat2, lng2):
    if any(v is None for v in [lat1, lng1, lat2, lng2]):
        return None
    try:
        return round(geodesic((lat1, lng1), (lat2, lng2)).meters, 2)
    except Exception:
        return None


def run_compare(
    df,
    col_name_1,
    col_name_2,
    col_addr_1,
    col_addr_2,
    col_lat_1,
    col_lng_1,
    col_lat_2,
    col_lng_2,
    name_thr,
    addr_thr,
    dist_thr,
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
            return pd.Series(["Trung quan (ten chinh xac)", 100, name_score, None])
        if name_score >= name_thr:
            return pd.Series(["Trung quan (ten gan dung)", name_score, name_score, None])

        addr_score = fuzz.token_set_ratio(row["addr1_norm"], row["addr2_norm"])
        if addr_score >= addr_thr:
            return pd.Series(["Trung dia chi", addr_score, name_score, None])

        distance_m = calc_distance(row["lat1"], row["lng1"], row["lat2"], row["lng2"])

        if distance_m is not None and distance_m <= dist_thr:
            return pd.Series(["Gan nhau nhung khac dia chi", 40, name_score, distance_m])
        if distance_m is not None:
            return pd.Series(["Khac", 0, name_score, distance_m])

        return pd.Series(["Thieu toa do", 0, name_score, None])

    df[["Ket luan", "Do tin cay (%)", "Diem giong ten", "Khoang cach (m)"]] = df.apply(compare, axis=1)

    df.drop(
        columns=[
            "ten_norm",
            "name_norm",
            "addr1_norm",
            "addr2_norm",
            "lat1",
            "lng1",
            "lat2",
            "lng2",
        ],
        inplace=True,
    )

    return df


def color_result(value):
    text = str(value)
    if "Trung quan" in text:
        return "background-color: #C8E6C9"
    if "Trung dia chi" in text:
        return "background-color: #FFF9C4"
    if "Khac" in text:
        return "background-color: #FFCDD2"
    return ""


def show_dataframe(df_to_show, use_result_style=False):
    if use_result_style and "Ket luan" in df_to_show.columns:
        try:
            st.dataframe(
                df_to_show.style.applymap(color_result, subset=["Ket luan"]),
                use_container_width=True,
            )
            return
        except Exception:
            pass

    st.dataframe(df_to_show, use_container_width=True)


def reset_filters_if_needed(current_mode):
    previous_mode = st.session_state.get("tool_mode")
    if previous_mode != current_mode:
        st.session_state.filter_conditions = []
    st.session_state["tool_mode"] = current_mode


filtered_df = None
uploaded_file = st.file_uploader("B1. Chon file Excel", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()
    columns = df.columns.tolist()

    total_rows = len(df)
    total_cols = len(df.columns)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Tong so dong", f"{total_rows:,}")
    with c2:
        st.metric("Tong so cot", f"{total_cols}")

    mode = st.radio(
        "B2. Chon chuc nang",
        ["TH1 - So sanh & xem file", "TH2 - Chi xem file Excel"],
    )
    reset_filters_if_needed(mode)

    if mode.startswith("TH1"):
        st.subheader("Chon cot de so sanh")

        c1, c2 = st.columns(2)
        with c1:
            col_name_1 = st.selectbox("Ten (nguon 1)", columns, key="c_n1")
            col_addr_1 = st.selectbox("Dia chi (nguon 1)", columns, key="c_a1")
            col_lat_1 = st.selectbox("Lat (nguon 1)", columns, key="c_lat1")
            col_lng_1 = st.selectbox("Lng (nguon 1)", columns, key="c_lng1")
        with c2:
            col_name_2 = st.selectbox("Ten (nguon 2)", columns, key="c_n2")
            col_addr_2 = st.selectbox("Dia chi (nguon 2)", columns, key="c_a2")
            col_lat_2 = st.selectbox("Lat (nguon 2)", columns, key="c_lat2")
            col_lng_2 = st.selectbox("Lng (nguon 2)", columns, key="c_lng2")

        name_thr = st.slider("Nguong giong ten", 0, 100, 90)
        addr_thr = st.slider("Nguong giong dia chi", 0, 100, 90)
        dist_thr = st.slider("Nguong khoang cach (m)", 0, 500, 30)

        if st.button("Chay so sanh"):
            st.session_state.result_df = run_compare(
                df,
                col_name_1,
                col_name_2,
                col_addr_1,
                col_addr_2,
                col_lat_1,
                col_lng_1,
                col_lat_2,
                col_lng_2,
                name_thr,
                addr_thr,
                dist_thr,
            )

        if st.session_state.result_df is not None:
            result_df = st.session_state.result_df

            if st.button("Them dieu kien loc"):
                st.session_state.filter_conditions.append({"column": None, "values": []})

            for idx, condition in enumerate(st.session_state.filter_conditions):
                selected_column = st.selectbox(
                    f"Chon cot de loc - Dieu kien {idx + 1}",
                    result_df.columns.tolist(),
                    key=f"filter_col_{idx}",
                )
                selected_values = st.multiselect(
                    f"Chon gia tri cho {selected_column} - Dieu kien {idx + 1}",
                    result_df[selected_column].dropna().astype(str).unique().tolist(),
                    default=result_df[selected_column].dropna().astype(str).unique().tolist(),
                    key=f"filter_values_{idx}",
                )
                st.session_state.filter_conditions[idx]["column"] = selected_column
                st.session_state.filter_conditions[idx]["values"] = selected_values

            filtered_df = result_df.copy()
            for condition in st.session_state.filter_conditions:
                if condition["column"] and condition["values"]:
                    filtered_df = filtered_df[
                        filtered_df[condition["column"]].astype(str).isin(condition["values"])
                    ]

            st.subheader("Loc ket qua")
            show_dataframe(filtered_df, use_result_style=True)

    else:
        st.subheader("Xem & loc file Excel")

        filter_col = st.selectbox("Chon cot de loc", columns, key="f2")
        values = df[filter_col].dropna().astype(str).unique().tolist()
        selected = st.multiselect("Chon gia tri", values, default=values)

        filtered_df = df[df[filter_col].astype(str).isin(selected)]
        show_dataframe(filtered_df, use_result_style=False)

    if filtered_df is not None:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            filtered_df.to_excel(writer, index=False, sheet_name="Filtered")

        st.download_button(
            "Tai Excel da loc",
            data=buffer.getvalue(),
            file_name="excel_da_loc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Vui long chon file Excel de bat dau.")
