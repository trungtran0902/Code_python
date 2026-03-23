import io
import json
import re
import unicodedata
from pathlib import Path

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

mode = st.radio(
    "Processing mode",
    options=["Manual upload", "Batch by folder"],
    horizontal=True,
)


def remove_trailing_commas(raw_text):
    return re.sub(r",\s*([}\]])", r"\1", raw_text)


def parse_geojson_text(raw_text, file_name):
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
            f"GeoJSON file '{file_name}' has invalid JSON at "
            f"line {exc.lineno}, column {exc.colno}. "
            f"Please check for a missing comma, an extra comma, or broken quotes. "
            f"Problematic line: {line_text}"
        ) from exc


def parse_geojson_upload(uploaded_file):
    raw_text = uploaded_file.getvalue().decode("utf-8-sig")
    return parse_geojson_text(raw_text, uploaded_file.name)


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


def load_geojson_paths(geojson_paths):
    gdf_list = []

    for geojson_path in geojson_paths:
        with open(geojson_path, "r", encoding="utf-8-sig") as f:
            raw_text = f.read()

        data = parse_geojson_text(raw_text, Path(geojson_path).name)
        gdf = gpd.GeoDataFrame.from_features(data["features"])

        if "address" not in gdf.columns:
            raise ValueError(
                f"GeoJSON file {Path(geojson_path).name} does not contain 'address'."
            )

        gdf["ward_address"] = gdf["address"]
        gdf_list.append(gdf[["geometry", "ward_address"]])

    wards_gdf = pd.concat(gdf_list, ignore_index=True)
    return gpd.GeoDataFrame(wards_gdf, geometry="geometry", crs="EPSG:4326")


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

    return columns[0] if columns else None


def validate_selected_columns(oldaddress_col, latitude_col, longitude_col):
    missing_fields = []

    if not oldaddress_col:
        missing_fields.append("Oldaddress")
    if not latitude_col:
        missing_fields.append("Latitude")
    if not longitude_col:
        missing_fields.append("Longitude")

    if missing_fields:
        raise ValueError("Please select columns for: " + ", ".join(missing_fields))


def build_new_address(row):
    old_address = str(row.get("Oldaddress", "")).strip()

    if pd.isna(row["ward_address"]) or not old_address:
        return old_address

    house_part = old_address.split(",")[0].strip()

    if not house_part:
        return str(row["ward_address"]).strip()

    return f"{house_part}, {str(row['ward_address']).strip()}"


def prepare_points_dataframe(df, oldaddress_col, latitude_col, longitude_col):
    validate_selected_columns(oldaddress_col, latitude_col, longitude_col)

    prepared_df = df.copy()
    prepared_df["Oldaddress"] = prepared_df[oldaddress_col]
    prepared_df["Latitude"] = pd.to_numeric(prepared_df[latitude_col], errors="coerce")
    prepared_df["Longitude"] = pd.to_numeric(
        prepared_df[longitude_col], errors="coerce"
    )

    missing_coordinates = prepared_df["Latitude"].isna() | prepared_df["Longitude"].isna()
    if missing_coordinates.any():
        raise ValueError(
            "Some rows have invalid Latitude/Longitude values in the selected columns."
        )

    geometry = [Point(xy) for xy in zip(prepared_df["Longitude"], prepared_df["Latitude"])]
    return gpd.GeoDataFrame(prepared_df, geometry=geometry, crs="EPSG:4326")


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
    points_gdf = prepare_points_dataframe(
        df, oldaddress_col, latitude_col, longitude_col
    )

    result = gpd.sjoin(points_gdf, wards_gdf, how="left", predicate="within")
    result["NewAddress"] = result.apply(build_new_address, axis=1)

    return result.drop(columns=["geometry", "index_right"], errors="ignore")


def normalize_name(value):
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def find_best_matching_column(columns, candidates):
    normalized_columns = {normalize_name(col): col for col in columns}

    for candidate in candidates:
        key = normalize_name(candidate)
        if key in normalized_columns:
            return normalized_columns[key]

    return None


def auto_detect_excel_columns(df):
    columns = list(df.columns)
    oldaddress_col = find_best_matching_column(
        columns,
        ["Oldaddress", "OldAddress", "Address", "DiaChi", "DiaChiCu"],
    )
    latitude_col = find_best_matching_column(
        columns,
        ["Latitude", "Lat", "ViDo", "Y"],
    )
    longitude_col = find_best_matching_column(
        columns,
        ["Longitude", "Lng", "Lon", "KinhDo", "X"],
    )
    return oldaddress_col, latitude_col, longitude_col


def collect_geojson_groups(geojson_root):
    geojson_root = Path(geojson_root)
    if not geojson_root.exists():
        raise ValueError(f"GeoJSON root folder does not exist: {geojson_root}")

    grouped = {}
    for province_dir in geojson_root.iterdir():
        if not province_dir.is_dir():
            continue

        geojson_files = sorted(str(path) for path in province_dir.rglob("*.geojson"))
        if not geojson_files:
            continue

        province_label = province_dir.name
        normalized_key = normalize_name(province_label)
        if normalized_key.startswith("y") and len(normalized_key) > 1:
            normalized_key = normalized_key[1:]

        grouped[normalized_key] = {
            "province_label": province_label,
            "geojson_files": geojson_files,
        }

    if not grouped:
        raise ValueError("No GeoJSON files were found in the selected folder.")

    return grouped


def collect_excel_files(excel_root):
    excel_root = Path(excel_root)
    if not excel_root.exists():
        raise ValueError(f"Excel folder does not exist: {excel_root}")

    excel_files = []
    for pattern in ("*.xlsx", "*.xls"):
        excel_files.extend(excel_root.glob(pattern))

    if not excel_files:
        raise ValueError("No Excel files were found in the selected folder.")

    return sorted(excel_files)


def match_geojson_group(excel_path, geojson_groups):
    excel_key = normalize_name(excel_path.stem)
    matches = []

    for group_key, group_info in geojson_groups.items():
        if group_key and group_key in excel_key:
            matches.append((len(group_key), group_info))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def process_single_excel_path(excel_path, geojson_paths):
    wards_gdf = load_geojson_paths(geojson_paths)

    df = pd.read_excel(excel_path)
    df = normalize_old_address_column(df)
    points_gdf = prepare_points_dataframe(
        df,
        auto_detect_excel_columns(df)[0],
        auto_detect_excel_columns(df)[1],
        auto_detect_excel_columns(df)[2],
    )

    result = gpd.sjoin(points_gdf, wards_gdf, how="left", predicate="within")
    result["NewAddress"] = result.apply(build_new_address, axis=1)

    return result.drop(columns=["geometry", "index_right"], errors="ignore")


def process_single_excel_path_with_selected_columns(
    excel_path,
    geojson_paths,
    oldaddress_col,
    latitude_col,
    longitude_col,
):
    wards_gdf = load_geojson_paths(geojson_paths)

    df = pd.read_excel(excel_path)
    df = normalize_old_address_column(df)
    points_gdf = prepare_points_dataframe(
        df,
        oldaddress_col,
        latitude_col,
        longitude_col,
    )

    result = gpd.sjoin(points_gdf, wards_gdf, how="left", predicate="within")
    result["NewAddress"] = result.apply(build_new_address, axis=1)

    return result.drop(columns=["geometry", "index_right"], errors="ignore")


def run_batch_processing(
    geojson_root,
    excel_root,
    output_root,
    oldaddress_col,
    latitude_col,
    longitude_col,
):
    geojson_groups = collect_geojson_groups(geojson_root)
    excel_files = collect_excel_files(excel_root)

    output_root_path = Path(output_root)
    output_root_path.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for excel_path in excel_files:
        matched_group = match_geojson_group(excel_path, geojson_groups)

        if matched_group is None:
            summary_rows.append(
                {
                    "excel_file": excel_path.name,
                    "province_folder": "",
                    "status": "Skipped",
                    "message": "No matching GeoJSON province folder found.",
                    "output_file": "",
                }
            )
            continue

        try:
            result_df = process_single_excel_path_with_selected_columns(
                excel_path,
                matched_group["geojson_files"],
                oldaddress_col,
                latitude_col,
                longitude_col,
            )
            output_file = output_root_path / f"{excel_path.stem}_new_address.xlsx"
            result_df.to_excel(output_file, index=False, engine="openpyxl")

            summary_rows.append(
                {
                    "excel_file": excel_path.name,
                    "province_folder": matched_group["province_label"],
                    "status": "Success",
                    "message": f"Processed {len(result_df)} rows.",
                    "output_file": str(output_file),
                }
            )
        except Exception as exc:
            summary_rows.append(
                {
                    "excel_file": excel_path.name,
                    "province_folder": matched_group["province_label"],
                    "status": "Failed",
                    "message": str(exc),
                    "output_file": "",
                }
            )

    return pd.DataFrame(summary_rows)


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

if mode == "Manual upload":
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

    if st.button(
        "Start Processing",
        disabled=not uploaded_geojson_files or not excel_file,
    ):
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
else:
    st.info(
        "Batch mode reads local folders directly. "
        "GeoJSON root example: XaPhuong. Excel folder example: folder containing province Excel files."
    )

    geojson_root = st.text_input(
        "GeoJSON root folder",
        value="",
        placeholder=r"C:\data\XaPhuong",
    )
    excel_root = st.text_input(
        "Excel folder",
        value="",
        placeholder=r"C:\data\ExcelTinh",
    )
    output_root = st.text_input(
        "Output folder",
        value="",
        placeholder=r"C:\data\OutputNewAddress",
    )

    batch_oldaddress_col = None
    batch_latitude_col = None
    batch_longitude_col = None

    if excel_root.strip():
        try:
            batch_excel_files = collect_excel_files(excel_root.strip())
            sample_excel_path = batch_excel_files[0]
            sample_df = normalize_old_address_column(pd.read_excel(sample_excel_path))

            st.subheader("Batch Excel preview")
            st.caption(f"Sample file used for column mapping: {sample_excel_path.name}")
            st.dataframe(sample_df.head(20), use_container_width=True)
            st.write(f"Detected Excel files: {len(batch_excel_files)}")

            sample_columns = list(sample_df.columns)
            default_oldaddress_col, default_latitude_col, default_longitude_col = (
                auto_detect_excel_columns(sample_df)
            )

            batch_oldaddress_col = st.selectbox(
                "Select column for Oldaddress (apply to all Excel files)",
                options=sample_columns,
                index=sample_columns.index(
                    default_oldaddress_col
                    if default_oldaddress_col in sample_columns
                    else sample_columns[0]
                ),
                key="batch_oldaddress_col",
            )
            batch_latitude_col = st.selectbox(
                "Select column for Latitude (apply to all Excel files)",
                options=sample_columns,
                index=sample_columns.index(
                    default_latitude_col
                    if default_latitude_col in sample_columns
                    else sample_columns[0]
                ),
                key="batch_latitude_col",
            )
            batch_longitude_col = st.selectbox(
                "Select column for Longitude (apply to all Excel files)",
                options=sample_columns,
                index=sample_columns.index(
                    default_longitude_col
                    if default_longitude_col in sample_columns
                    else sample_columns[0]
                ),
                key="batch_longitude_col",
            )
        except Exception as exc:
            st.warning(f"Cannot preview Excel folder yet: {exc}")

    if st.button(
        "Start Batch Processing",
        disabled=not geojson_root.strip()
        or not excel_root.strip()
        or not output_root.strip()
        or not batch_oldaddress_col
        or not batch_latitude_col
        or not batch_longitude_col,
    ):
        try:
            with st.spinner("Batch processing data..."):
                summary_df = run_batch_processing(
                    geojson_root.strip(),
                    excel_root.strip(),
                    output_root.strip(),
                    batch_oldaddress_col,
                    batch_latitude_col,
                    batch_longitude_col,
                )

            st.success("Batch processing completed.")
            st.dataframe(summary_df, use_container_width=True)
            st.write(
                f"Success files: {(summary_df['status'] == 'Success').sum()}/"
                f"{len(summary_df)}"
            )
        except Exception as exc:
            st.error(f"Batch processing failed: {exc}")
            print(f"Batch processing failed: {exc}")
