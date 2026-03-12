# app.py
import io
import re
import zipfile
from pathlib import Path

import streamlit as st
import geopandas as gpd


def safe_filename(s: str, max_len: int = 80) -> str:
    """Tạo tên file an toàn từ giá trị cột."""
    s = str(s)
    s = s.strip()
    # thay ký tự lạ bằng _
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_{2,}", "_", s)
    s = s.strip("_")
    if not s:
        s = "unknown"
    return s[:max_len]


def read_geojson_from_upload(uploaded_file) -> gpd.GeoDataFrame:
    """Đọc GeoJSON từ streamlit uploader."""
    # geopandas có thể đọc file-like, nhưng ổn nhất là đưa bytes vào BytesIO
    data = uploaded_file.read()
    bio = io.BytesIO(data)
    gdf = gpd.read_file(bio)

    # đảm bảo có geometry
    if "geometry" not in gdf.columns:
        raise ValueError("File không có cột geometry.")
    return gdf


def split_and_zip_geojson(gdf: gpd.GeoDataFrame, split_col: str) -> bytes:
    """Tách theo split_col và trả về bytes của file ZIP chứa các GeoJSON."""
    # bỏ feature không có geometry
    gdf = gdf[~gdf.geometry.isna()].copy()

    # nếu cột tách có NaN thì thay bằng 'unknown'
    gdf[split_col] = gdf[split_col].fillna("unknown")

    # tạo zip in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for value, part in gdf.groupby(split_col, dropna=False):
            # giữ CRS
            part = part.copy()

            # tên file
            name = safe_filename(value)
            out_name = f"{split_col}={name}.geojson"

            # ghi ra bytes
            geojson_bytes = part.to_json().encode("utf-8")
            zf.writestr(out_name, geojson_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


st.set_page_config(page_title="Tách GeoJSON theo cột", layout="centered")
st.title("🗺️ Tách 1 file MultiPolygon/Polygon thành nhiều file GeoJSON")

st.write(
    "- B1: Upload GeoJSON\n"
    "- B2: Chọn cột để tách feature\n"
    "- B3: Bấm nút để xử lý và tải ZIP kết quả"
)

uploaded = st.file_uploader("Chọn file GeoJSON", type=["geojson", "json"])

if uploaded is not None:
    try:
        gdf = read_geojson_from_upload(uploaded)
        st.success(f"Đọc thành công: {len(gdf):,} feature")

        # hiển thị vài cột
        non_geom_cols = [c for c in gdf.columns if c != "geometry"]
        if not non_geom_cols:
            st.warning("File chỉ có geometry, không có cột thuộc tính để tách.")
            st.stop()

        split_col = st.selectbox("B2. Chọn cột để tách", non_geom_cols)

        with st.expander("Xem preview dữ liệu"):
            st.dataframe(gdf.head(20))

        st.caption("Gợi ý: Nếu cột có nhiều giá trị trùng nhau, mỗi giá trị sẽ xuất thành 1 file GeoJSON.")

        run = st.button("B3. Thực thi tách file ✅", type="primary")

        if run:
            with st.spinner("Đang xử lý..."):
                zip_bytes = split_and_zip_geojson(gdf, split_col)

            out_zip_name = f"split_by_{safe_filename(split_col)}.zip"
            st.success("Xử lý xong! Tải ZIP bên dưới.")

            st.download_button(
                label="⬇️ Download ZIP kết quả",
                data=zip_bytes,
                file_name=out_zip_name,
                mime="application/zip",
            )

    except Exception as e:
        st.error(f"Lỗi khi đọc/xử lý file: {e}")

else:
    st.info("Hãy upload 1 file GeoJSON để bắt đầu.")