import streamlit as st
import json
import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
import tempfile
import os
import zipfile
from io import BytesIO

st.set_page_config(page_title="GeoJSON Region Union", layout="wide")

st.title("🗺️ Merge Polygon GeoJSON Lựa Chọn")

# Bước 1: Upload tất cả các file GeoJSON
uploaded_files = st.file_uploader(
    "📂 Upload GeoJSON files",
    type=["geojson"],
    accept_multiple_files=True
)

# Kiểm tra xem có file được tải lên không
if uploaded_files:
    file_names = [file.name for file in uploaded_files]

    # Lưu trữ thông tin các nhóm merge
    if "merging_sessions" not in st.session_state:
        st.session_state.merging_sessions = []

    # Bước 2: Hiển thị các nhóm merge đã thêm
    for i, session in enumerate(st.session_state.merging_sessions):
        with st.expander(f"Nhóm merge {i+1}"):
            selected_files = st.multiselect(
                f"📌 Chọn các file cần merge (Nhóm {i+1})",
                options=file_names,
                default=session["files"]
            )
            output_filename = st.text_input(
                f"📁 Nhập tên file đầu ra cho nhóm {i+1}",
                value=session["output_filename"]
            )
            session["files"] = selected_files
            session["output_filename"] = output_filename

    # Bước 3: Nút Thêm nhóm merge mới
    if st.button("Thêm nhóm merge"):
        # Thêm nhóm merge vào session_state mà không cần gọi lại giao diện
        st.session_state.merging_sessions.append({
            "files": [],
            "output_filename": ""
        })

    # Bước 4: Thực thi các tác vụ merge
    if st.button("Thực Thi"):
        if not st.session_state.merging_sessions:
            st.warning("❌ Vui lòng thêm ít nhất 1 nhóm merge.")
        else:
            # Khởi tạo một danh sách để lưu các file đã được tạo
            all_merged_geojson = []

            # Duyệt qua tất cả các nhóm merge đã thêm
            for session_id, session in enumerate(st.session_state.merging_sessions):
                selected_files = session["files"]
                output_filename = session["output_filename"]

                # Đảm bảo tên file có đuôi .geojson
                if not output_filename.endswith(".geojson"):
                    output_filename += ".geojson"

                gdfs = []

                with st.spinner(f"Processing {len(selected_files)} files..."):

                    for file in uploaded_files:
                        if file.name in selected_files:
                            # Lưu file tạm
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
                                tmp.write(file.getvalue())
                                tmp_path = tmp.name

                            # Đọc bằng geopandas
                            gdf = gpd.read_file(tmp_path)

                            # Thêm trường "name" vào properties của từng feature
                            base_filename = os.path.splitext(output_filename)[0]  # Loại bỏ phần mở rộng
                            gdf["name"] = base_filename  # Gán tên vào trường "name"

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

                    # Tạo properties cho merged geometry, tăng ID tự động cho mỗi feature
                    merged_gdf["name"] = base_filename
                    # Gán giá trị ID tự động tăng dần cho mỗi feature
                    merged_gdf["id"] = range(len(merged_gdf))

                    # Chuyển GeoDataFrame thành GeoJSON
                    merged_geojson = json.loads(merged_gdf.to_json())

                    st.success(f"✅ Merge thành công: {output_filename}")
                    st.info(f"📊 Số vùng ban đầu: {len(combined_gdf)}")
                    st.info("🗺️ Sau merge: 1 geometry")

                    with st.expander(f"🔍 Preview {output_filename}"):
                        st.json(merged_geojson)

                    # Lưu geojson vào danh sách các file đã tạo
                    all_merged_geojson.append({
                        "data": json.dumps(merged_geojson, indent=2),
                        "file_name": output_filename
                    })
                else:
                    st.error("❌ Không có dữ liệu để gộp.")

            # Bước 5: Nút download cho tất cả các file (tạo file ZIP hợp lệ)
            if all_merged_geojson:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for merged_file in all_merged_geojson:
                        zip_file.writestr(merged_file["file_name"], merged_file["data"])

                zip_buffer.seek(0)

                st.download_button(
                    label="⬇ Download all merged regions",
                    data=zip_buffer,
                    file_name="all_merged_regions.zip",
                    mime="application/zip"
                )