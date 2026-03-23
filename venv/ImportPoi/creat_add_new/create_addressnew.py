import io
import json
import re

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
        data = parse_geojson_upload(uploaded_file)
        gdf = gpd.GeoDataFrame.from_features(data["features"])

        if "address" not in gdf.columns:
            raise ValueError(
                f"GeoJSON file {uploaded_file.name} does not contain 'address'."
            )

        gdf["ward_address"] = gdf["address"]
        gdf_list.append(gdf[["geometry", "ward_address"]])

    wards_gdf = pd.concat(gdf_list, ignore_index=True)
    return gpd.GeoDataFrame(wards_gdf, geometry="geometry", crs="EPSG:4326")


def remove_trailing_commas(raw_text):
    return re.sub(r",\s*([}\]])", r"\1", raw_text)


def parse_geojson_upload(uploaded_file):
    raw_text = uploaded_file.getvalue().decode("utf-8-sig")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        sanitized_text = remove_trailing_commas(raw_text)

        if sanitized_text != raw_text:
            try:
                return json.loads(sanitized_text)
            except json.JSONDecodeError:
                pass

        line_text = ""
        text_lines = raw_text.splitlines()
        if 1 <= exc.lineno <= len(text_lines):
            line_text = text_lines[exc.lineno - 1].strip()

        raise ValueError(
            f"GeoJSON file '{uploaded_file.name}' has invalid JSON at "
            f"line {exc.lineno}, column {exc.colno}. "
            f"Please check for a missing comma, an extra comma, or broken quotes. "
            f"Problematic line: {line_text}"
        ) from exc


def normalize_old_address_column(df):
    if "OldAddress" in df.columns and "Oldaddress" not in df.columns:
        df = df.rename(columns={"OldAddress": "Oldaddress"})
    return df


def get_default_column(columns, candidates):
    normalized_map = {str(col).strip().lower(): col for col in columns}

    for candidate in candidates:
        match = normalized_map.get(candidate.lower())
        if match is not None:
            return match

    return columns[0] if len(columns) > 0 else None


def validate_selected_columns(oldaddress_col, latitude_col, longitude_col):
    missing_fields = []

    if not oldaddress_col:
        missing_fields.append("Oldaddress")
    if not latitude_col:
        missing_fields.append("Latitude")
    if not longitude_col:
        missing_fields.append("Longitude")

    if missing_fields:
        raise ValueError(
            "Please select columns for: " + ", ".join(missing_fields)
        )


def build_new_address(row):
    old_address = str(row.get("Oldaddress", "")).strip()

    if pd.isna(row["ward_address"]) or not old_address:
        return old_address

    house_part = old_address.split(",")[0].strip()

    if not house_part:
        return str(row["ward_address"]).strip()

    return f"{house_part}, {str(row['ward_address']).strip()}"


def process_files(
    excel_file,
    uploaded_geojson_files,
    oldaddress_col,
    latitude_col,
    longitude_col,
):
    wards_gdf = load_geojson_files(uploaded_geojson_files)

    df = pd.read_excel(excel_file)
    df = normalize_old_address_column(df)
    validate_selected_columns(oldaddress_col, latitude_col, longitude_col)

    df = df.copy()
    df["Oldaddress"] = df[oldaddress_col]
    df["Latitude"] = pd.to_numeric(df[latitude_col], errors="coerce")
    df["Longitude"] = pd.to_numeric(df[longitude_col], errors="coerce")

    missing_coordinates = df["Latitude"].isna() | df["Longitude"].isna()
    if missing_coordinates.any():
        raise ValueError(
            "Some rows have invalid Latitude/Longitude values in the selected columns."
        )

    geometry = [Point(xy) for xy in zip(df["Longitude"], df["Latitude"])]
    points_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    result = gpd.sjoin(points_gdf, wards_gdf, how="left", predicate="within")
    result["NewAddress"] = result.apply(build_new_address, axis=1)

    return result.drop(columns=["geometry", "index_right"], errors="ignore")


st.markdown("### Input file format")
st.info(
    "Upload an Excel file, then choose which columns should be used for "
    "Oldaddress, Latitude, and Longitude."
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

    excel_columns = list(preview_df.columns)
    oldaddress_col = st.selectbox(
        "Select column for Oldaddress",
        options=excel_columns,
        index=excel_columns.index(
            get_default_column(excel_columns, ["Oldaddress", "OldAddress"])
        ),
    )
    latitude_col = st.selectbox(
        "Select column for Latitude",
        options=excel_columns,
        index=excel_columns.index(
            get_default_column(excel_columns, ["Latitude", "lat", "y"])
        ),
    )
    longitude_col = st.selectbox(
        "Select column for Longitude",
        options=excel_columns,
        index=excel_columns.index(
            get_default_column(excel_columns, ["Longitude", "lng", "lon", "x"])
        ),
    )
else:
    oldaddress_col = None
    latitude_col = None
    longitude_col = None

if st.button("Start Processing", disabled=not uploaded_geojson_files or not excel_file):
    try:
        with st.spinner("Processing data..."):
            result_df = process_files(
                excel_file,
                uploaded_geojson_files,
                oldaddress_col,
                latitude_col,
                longitude_col,
            )

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
