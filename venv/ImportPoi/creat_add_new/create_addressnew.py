import io
import json

import geopandas as gpd
import pandas as pd
import streamlit as st
from shapely.geometry import Point


st.set_page_config(page_title="Create New Address Tool", layout="wide")

st.title("Create New Address Tool")
st.write(
    "Upload GeoJSON ward files and an Excel file with coordinates to build "
    "a new address column."
)


def load_geojson_files(uploaded_geojson_files):
    gdf_list = []

    for uploaded_file in uploaded_geojson_files:
        data = json.loads(uploaded_file.getvalue().decode("utf-8"))
        gdf = gpd.GeoDataFrame.from_features(data["features"])

        if "address" not in gdf.columns:
            raise ValueError(
                f"GeoJSON file {uploaded_file.name} does not contain 'address'."
            )

        gdf["ward_address"] = gdf["address"]
        gdf_list.append(gdf[["geometry", "ward_address"]])

    wards_gdf = pd.concat(gdf_list, ignore_index=True)
    return gpd.GeoDataFrame(wards_gdf, geometry="geometry", crs="EPSG:4326")


def normalize_old_address_column(df):
    if "OldAddress" in df.columns and "Oldaddress" not in df.columns:
        df = df.rename(columns={"OldAddress": "Oldaddress"})
    return df


def validate_input_columns(df):
    required_cols = ["Latitude", "Longitude", "Oldaddress"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(
            "Excel is missing required columns: " + ", ".join(missing_cols)
        )


def build_new_address(row):
    old_address = str(row.get("Oldaddress", "")).strip()

    if pd.isna(row["ward_address"]) or not old_address:
        return old_address

    house_part = old_address.split(",")[0].strip()

    if not house_part:
        return str(row["ward_address"]).strip()

    return f"{house_part}, {str(row['ward_address']).strip()}"


def process_files(excel_file, uploaded_geojson_files):
    wards_gdf = load_geojson_files(uploaded_geojson_files)

    df = pd.read_excel(excel_file)
    df = normalize_old_address_column(df)
    validate_input_columns(df)

    geometry = [Point(xy) for xy in zip(df["Longitude"], df["Latitude"])]
    points_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    result = gpd.sjoin(points_gdf, wards_gdf, how="left", predicate="within")
    result["NewAddress"] = result.apply(build_new_address, axis=1)

    return result.drop(columns=["geometry", "index_right"], errors="ignore")


st.markdown("### Input file format")
st.info(
    "Excel file needs these columns: Latitude, Longitude, Oldaddress. "
    "The app also accepts OldAddress and will map it automatically."
)

sample_input_df = pd.DataFrame(
    [
        {
            "Latitude": 21.0285,
            "Longitude": 105.8542,
            "Oldaddress": "12 Nguyen Trai, Quan 1, TP HCM",
        }
    ]
)

st.caption("Example Excel row")
st.dataframe(sample_input_df, use_container_width=True)

uploaded_geojson_files = st.file_uploader(
    "Upload GeoJSON ward files",
    type=["geojson"],
    accept_multiple_files=True,
)

excel_file = st.file_uploader(
    "Upload Excel file",
    type=["xlsx", "xls"],
)

if uploaded_geojson_files:
    st.write(f"Selected GeoJSON files: {len(uploaded_geojson_files)}")
    geojson_names_df = pd.DataFrame(
        {"GeoJSON file name": [file.name for file in uploaded_geojson_files]}
    )
    st.dataframe(geojson_names_df, use_container_width=True)

if excel_file:
    preview_df = normalize_old_address_column(pd.read_excel(excel_file))
    st.subheader("Excel preview")
    st.dataframe(preview_df, use_container_width=True)
    st.write(f"Total rows: {len(preview_df)}")

if st.button("Start Processing", disabled=not uploaded_geojson_files or not excel_file):
    try:
        with st.spinner("Processing data..."):
            result_df = process_files(excel_file, uploaded_geojson_files)

        st.success("Processing completed successfully.")
        st.dataframe(result_df, use_container_width=True)

        matched_count = result_df["ward_address"].notna().sum()
        st.write(f"Matched rows: {matched_count}/{len(result_df)}")

        output_buffer = io.BytesIO()
        result_df.to_excel(output_buffer, index=False, engine="openpyxl")
        output_buffer.seek(0)

        st.download_button(
            "Download result Excel",
            data=output_buffer.getvalue(),
            file_name="new_address_result.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        print("Processing completed successfully.")
        print(f"Generated {len(result_df)} rows.")
        print(result_df.head(20).to_string(index=False))
    except Exception as exc:
        st.error(f"Processing failed: {exc}")
        print(f"Processing failed: {exc}")
