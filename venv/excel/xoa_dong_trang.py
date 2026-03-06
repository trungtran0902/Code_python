import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Xóa dòng trống Excel",
    page_icon="📊",
    layout="centered"
)

st.title("📊 Xóa dòng trống trong Excel")
st.write("Upload file Excel → hệ thống sẽ tự động xóa các dòng trống.")

# Upload file
uploaded_file = st.file_uploader(
    "📂 Chọn file Excel",
    type=["xlsx", "xls"]
)

if uploaded_file is not None:
    try:
        # Đọc file Excel
        df = pd.read_excel(uploaded_file)

        st.subheader("🔍 Xem trước dữ liệu (10 dòng đầu)")
        st.dataframe(df.head(10))

        # Nút xử lý
        if st.button("🚀 Xóa dòng trống"):
            # Xóa các dòng trống hoàn toàn
            df_clean = df.dropna(how="all")

            st.success(
                f"✅ Đã xóa {len(df) - len(df_clean)} dòng trống"
            )

            # Ghi file ra bộ nhớ
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_clean.to_excel(writer, index=False, sheet_name="Data")

            output.seek(0)

            # Download
            st.download_button(
                label="⬇️ Tải file Excel đã xử lý",
                data=output,
                file_name="excel_da_xoa_dong_trong.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error("❌ Có lỗi khi xử lý file Excel")
        st.exception(e)
#== dùng lệnh này để chạy "streamlit run xem_excel.py" trên terminal ===