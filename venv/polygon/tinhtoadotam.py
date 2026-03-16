import streamlit as st
import geopandas as gpd
import pandas as pd
import tempfile
import json

st.set_page_config(page_title="GeoJSON Centroid Tool", layout="wide")

st.title("📍 GeoJSON Polygon Centroid Calculator")

st.write("Upload các file GeoJSON polygon để tính tọa độ tâm và xuất bảng thống kê.")

uploaded_files = st.file_uploader(
    "Chọn file GeoJSON",
    type=["geojson", "json"],
    accept_multiple_files=True
)

results = []

if uploaded_files:

    for uploaded_file in uploaded_files:

        data = json.load(uploaded_file)

        gdf = gpd.GeoDataFrame.from_features(data["features"])

        if gdf.empty:
            continue

        gdf["centroid"] = gdf.geometry.centroid
        gdf["centroid_x"] = gdf.centroid.x
        gdf["centroid_y"] = gdf.centroid.y

        for idx, row in gdf.iterrows():
            results.append({
                "file": uploaded_file.name,
                "feature_id": idx,
                "centroid_x": row["centroid_x"],
                "centroid_y": row["centroid_y"]
            })

    df = pd.DataFrame(results)

    st.subheader("📊 Bảng thống kê centroid")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name="centroid_results.csv",
        mime="text/csv"
    )

else:
    st.info("Vui lòng upload ít nhất một file GeoJSON.")