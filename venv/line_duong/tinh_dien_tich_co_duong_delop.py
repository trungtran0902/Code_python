import streamlit as st
import geopandas as gpd
import pandas as pd
import tempfile
import time

st.title("Tính diện tích vùng có đường")

buffer_dist = st.number_input("Buffer đường (m)", value=10)

polygon_files = st.file_uploader(
    "Upload polygon phường/xã",
    type=["geojson","shp"],
    accept_multiple_files=True
)

if st.button("Bắt đầu xử lý"):

    start_total = time.time()

    st.write("Đang đọc dữ liệu đường...")

    roads = gpd.read_parquet("data/roads.parquet")

    if roads.crs.is_geographic:
        roads = roads.to_crs(3857)

    roads_sindex = roads.sindex

    progress = st.progress(0)
    console = st.empty()

    logs = []
    results = []

    for i, poly_file in enumerate(polygon_files):

        start = time.time()

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(poly_file.read())
            poly_path = tmp.name

        polygon = gpd.read_file(poly_path)

        if polygon.crs != roads.crs:
            polygon = polygon.to_crs(roads.crs)

        poly_geom = polygon.geometry.union_all()

        idx = list(roads_sindex.intersection(poly_geom.bounds))
        candidate = roads.iloc[idx]

        roads_clip = candidate.clip(poly_geom)

        if len(roads_clip) == 0:
            road_area = 0
        else:
            road_area = roads_clip.buffer(buffer_dist).union_all().area

        poly_area = poly_geom.area

        elapsed = round(time.time()-start,2)

        results.append({
            "phuong_xa": poly_file.name,
            "polygon_area": poly_area,
            "road_area": road_area,
            "ratio": road_area/poly_area if poly_area>0 else 0
        })

        logs.append(f"{i+1}/{len(polygon_files)} {poly_file.name} {elapsed}s")

        console.text("\n".join(logs))

        progress.progress((i+1)/len(polygon_files))

    df = pd.DataFrame(results)

    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        csv,
        "result.csv",
        "text/csv"
    )

    st.write("Tổng thời gian:", round(time.time()-start_total,2), "giây")