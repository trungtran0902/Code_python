import streamlit as st
import json
import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
import tempfile
import os

st.set_page_config(page_title="GeoJSON Region Union", layout="wide")

st.title("🗺️ Merge Polygon GeoJSON Lựa Chọn")

uploaded_files = st.file_uploader(
    "📂 Upload GeoJSON files",
    type=["geojson"],
    accept_multiple_files=True
)

if uploaded_files:

    file_names = [file.name for file in uploaded_files]

    selected_files = st.multiselect(
        "📌 Select files to merge",
        options=file_names
    )

    # Nhập tên file đầu ra
    output_filename = st.text_input(
        "📁 Nhập tên file đầu ra (ví dụ: merged_region.geojson)",
        "merged_region.geojson"
    )

    # Loại bỏ phần mở rộng ".geojson"
    base_filename = os.path.splitext(output_filename)[0]  # Lấy phần tên file mà không có ".geojson"

    # Button "Thực Thi" để merge
    if st.button("Thực Thi"):

        if selected_files:

            gdfs = []

            with st.spinner("Processing geometries..."):

                for file in uploaded_files:
                    if file.name in selected_files:

                        # Lưu file tạm
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
                            tmp.write(file.getvalue())
                            tmp_path = tmp.name

                        # Đọc bằng geopandas
                        gdf = gpd.read_file(tmp_path)

                        # Thêm trường "name" vào properties của từng feature
                        gdf["name"] = base_filename

                        gdfs.append(gdf)

                        os.remove(tmp_path)

            if gdfs:

                # Gộp tất cả lại
                combined_gdf = gpd.GeoDataFrame(
                    pd.concat(gdfs, ignore_index=True),
                    crs=gdfs[0].crs
                )

                # Sửa geometry lỗi nếu có
                combined_gdf["geometry"] = combined_gdf["geometry"].buffer(0)

                # Union toàn bộ geometry
                merged_geometry = unary_union(combined_gdf.geometry)

                # Tạo GeoDataFrame mới với geometry và properties
                merged_gdf = gpd.GeoDataFrame(
                    geometry=[merged_geometry],
                    crs=combined_gdf.crs
                )

                # Tạo properties cho merged geometry
                merged_gdf["name"] = base_filename

                # Chuyển GeoDataFrame thành GeoJSON
                merged_geojson = json.loads(merged_gdf.to_json())

                st.success("✅ Merge thành công thành 1 vùng duy nhất!")
                st.info(f"📊 Số vùng ban đầu: {len(combined_gdf)}")
                st.info("🗺️ Sau merge: 1 geometry")

                with st.expander("🔍 Preview merged GeoJSON"):
                    st.json(merged_geojson)

                # Thêm button "Thực thu"
                st.download_button(
                    label="⬇ Download merged region",
                    data=json.dumps(merged_geojson, indent=2),
                    file_name=base_filename + ".geojson",  # Tên file đầu ra
                    mime="application/json"
                )

            else:
                st.error("❌ Không có dữ liệu để gộp.")
        else:
            st.warning("❌ Vui lòng chọn ít nhất 1 file để merge.")

else:
    st.info("Upload ít nhất 1 file GeoJSON.")