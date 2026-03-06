import streamlit as st
import geopandas as gpd
import pandas as pd
import time
import tempfile
import os

st.title("Tính diện tích vùng có đường theo phường/xã")

road_file = st.file_uploader("Upload file GeoJSON đường", type=["geojson","shp"])
polygon_files = st.file_uploader(
    "Upload các file polygon phường/xã",
    type=["geojson","shp"],
    accept_multiple_files=True
)

buffer_dist = st.number_input("Buffer đường (m)", value=10)

if st.button("Bắt đầu xử lý"):

    if road_file is None or len(polygon_files) == 0:
        st.warning("Vui lòng upload dữ liệu")
        st.stop()

    start_total = time.time()

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(road_file.read())
        road_path = tmp.name

    st.write("Đang đọc dữ liệu đường...")
    roads = gpd.read_file(road_path)

    if roads.crs.is_geographic:
        roads = roads.to_crs(3857)

    roads_sindex = roads.sindex

    results = []

    progress = st.progress(0)

    for i, poly_file in enumerate(polygon_files):

        start = time.time()

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(poly_file.read())
            poly_path = tmp.name

        polygon = gpd.read_file(poly_path)

        if polygon.crs != roads.crs:
            polygon = polygon.to_crs(roads.crs)

        poly_geom = polygon.geometry.union_all()

        possible_index = list(roads_sindex.intersection(poly_geom.bounds))
        candidate_roads = roads.iloc[possible_index]

        roads_clip = candidate_roads.clip(poly_geom)

        if len(roads_clip) == 0:
            road_area = 0
        else:
            road_area = roads_clip.buffer(buffer_dist).union_all().area

        poly_area = poly_geom.area

        results.append({
            "phuong_xa": poly_file.name,
            "polygon_area": poly_area,
            "road_area": road_area,
            "road_ratio": road_area/poly_area if poly_area>0 else 0
        })

        st.write(
            f"✔ {poly_file.name} | roads: {len(roads_clip)} | "
            f"time: {round(time.time()-start,2)}s"
        )

        progress.progress((i+1)/len(polygon_files))

    df = pd.DataFrame(results)

    st.success("Hoàn thành!")

    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        csv,
        "thong_ke_duong.csv",
        "text/csv"
    )

    st.write("Tổng thời gian:", round(time.time()-start_total,2), "giây")