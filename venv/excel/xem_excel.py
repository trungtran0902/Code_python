import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Excel Viewer", layout="wide")
st.title("📊 Excel Viewer – Lọc & Xuất Excel")

uploaded_file = st.file_uploader("📂 Chọn file Excel", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if "Kết luận" not in df.columns:
        st.error("❌ Không tìm thấy cột 'Kết luận'")
    else:
        # Danh sách giá trị để lọc
        ket_luan_values = sorted(df["Kết luận"].dropna().unique())

        selected = st.multiselect(
            "🔍 Lọc theo cột 'Kết luận'",
            options=ket_luan_values,
            default=ket_luan_values
        )

        keyword = st.text_input("🔎 Tìm trong 'Kết luận'")

        filtered_df = df[df["Kết luận"].isin(selected)]

        if keyword:
            filtered_df = filtered_df[
                filtered_df["Kết luận"].astype(str)
                .str.contains(keyword, case=False, na=False)
            ]

        st.write(f"📌 Số dòng sau lọc: {len(filtered_df)}")
        st.dataframe(filtered_df, use_container_width=True)

        # ===== EXPORT EXCEL =====
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            filtered_df.to_excel(writer, index=False, sheet_name="Filtered")

        st.download_button(
            label="⬇️ Tải file Excel đã lọc",
            data=buffer.getvalue(),
            file_name="du_lieu_da_loc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        #== dùng lệnh này để chạy streamlit run xem_excel.py trên terminal ===
