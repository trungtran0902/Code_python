import streamlit as st
import pandas as pd
import requests
from io import BytesIO

st.set_page_config(page_title="API Generator", layout="wide")
st.title("🔗 Tạo Danh sách ID Realtion & gọi API từ Excel")

BASE_API = "https://api-private.map4d.vn/osm/administrator-osm/"
API_KEY = "nghiant"

# ---------- B1: Upload ----------
uploaded_file = st.file_uploader("B1: Upload file Excel", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)

    st.subheader("Preview dữ liệu gốc")
    st.dataframe(df_input.head())

    # ---------- B2: Chọn cột ID ----------
    id_column = st.selectbox(
        "B2: Chọn cột chứa ID",
        df_input.columns
    )

    if id_column:
        # 👉 TỰ ĐỘNG gán api_link NGAY KHI CHỌN CỘT
        df_preview = df_input.copy()
        df_preview["api_link"] = df_preview[id_column].apply(
            lambda x: f"{BASE_API}{int(x)}?Key={API_KEY}"
            if pd.notnull(x) else None
        )

        st.subheader("Danh sách Excel sau khi gán API link")
        st.dataframe(df_preview)

        # ---------- B3: Gọi API ----------
        if st.button("🚀 Gọi API & tạo file"):
            rows = []
            progress = st.progress(0)
            total = len(df_preview)

            for i, row in df_preview.iterrows():
                relation_id = row[id_column]
                api_link = row["api_link"]

                try:
                    r = requests.get(api_link, timeout=15)
                    if r.status_code == 200:
                        data = r.json()

                        if isinstance(data, dict):
                            rows.append({
                                "relation_id": relation_id,
                                "api_link": api_link,
                                **data
                            })
                        elif isinstance(data, list):
                            for item in data:
                                rows.append({
                                    "relation_id": relation_id,
                                    "api_link": api_link,
                                    **item
                                })
                    else:
                        rows.append({
                            "relation_id": relation_id,
                            "api_link": api_link,
                            "error": r.status_code
                        })

                except Exception as e:
                    rows.append({
                        "relation_id": relation_id,
                        "api_link": api_link,
                        "error": str(e)
                    })

                progress.progress((i + 1) / total)

            df_result = pd.DataFrame(rows)

            st.subheader("Preview dữ liệu từ API")
            st.dataframe(df_result.head())

            # ---------- B5: Download ----------
            # CSV
            csv_data = df_result.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Download CSV",
                csv_data,
                file_name="api_response.csv",
                mime="text/csv"
            )

            # Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_result.to_excel(writer, index=False, sheet_name="data")
            output.seek(0)

            st.download_button(
                "⬇️ Download Excel",
                output,
                file_name="api_response.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

#== dùng lệnh này để chạy streamlit run truyen_gia_tri.py trên terminal ===