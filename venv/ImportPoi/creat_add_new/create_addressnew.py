import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import json
from io import BytesIO

st.title("Geo Mapping Address Tool")

st.write("Upload GeoJSON polygons và Excel chứa Latitude / Longitude")

# Upload geojson
geojson_files = st.file_uploader(
    "Upload GeoJSON files",
    type=["geojson"],
    accept_multiple_files=True
)

# Upload excel
excel_file = st.file_uploader(
    "Upload Excel file",
    type=["xlsx", "xls"]
)

if st.button("Process"):

    if not geojson_files:
        st.error("Vui lòng upload GeoJSON")
        st.stop()

    if not excel_file:
        st.error("Vui lòng upload Excel")
        st.stop()

    with st.spinner("Loading GeoJSON..."):

        gdf_list = []

        for file in geojson_files:
            data = json.load(file)

            gdf = gpd.GeoDataFrame.from_features(data["features"])

            if "address" not in gdf.columns:
                st.error(f"{file.name} không có trường address")
                st.stop()

            gdf["ward_address"] = gdf["address"]

            gdf_list.append(gdf[["geometry", "ward_address"]])

        wards_gdf = pd.concat(gdf_list, ignore_index=True)
        wards_gdf = gpd.GeoDataFrame(
            wards_gdf,
            geometry="geometry",
            crs="EPSG:4326"
        )

    with st.spinner("Reading Excel..."):

        df = pd.read_excel(excel_file)

        required_cols = ["Latitude", "Longitude", "Oldaddress"]

        for col in required_cols:
            if col not in df.columns:
                st.error(f"Excel thiếu cột {col}")
                st.stop()

    with st.spinner("Mapping points to polygons..."):

        geometry = [Point(xy) for xy in zip(df["Longitude"], df["Latitude"])]

        points_gdf = gpd.GeoDataFrame(
            df,
            geometry=geometry,
            crs="EPSG:4326"
        )

        result = gpd.sjoin(
            points_gdf,
            wards_gdf,
            how="left",
            predicate="within"
        )

    def build_new_address(row):

        if pd.isna(row["ward_address"]):
            return row["Oldaddress"]

        first_part = row["Oldaddress"].split(",")[0]

        return f"{first_part}, {row['ward_address']}"

    result["NewAddress"] = result.apply(build_new_address, axis=1)

    result = result.drop(columns=["geometry", "index_right"], errors="ignore")

    st.success("Xử lý hoàn thành")

    st.dataframe(result.head())

    output = BytesIO()

    result.to_excel(output, index=False)

    st.download_button(
        label="Download Result Excel",
        data=output.getvalue(),
        file_name="mapped_address.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )