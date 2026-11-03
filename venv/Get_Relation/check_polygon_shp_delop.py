import json
import os
import tempfile
import zipfile
from io import BytesIO

import streamlit as st
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import explain_validity, make_valid


st.set_page_config(page_title="Check loi Polygon", page_icon=":jigsaw:", layout="wide")
st.title("Check loi Polygon (GeoJSON / Shapefile ZIP)")


def is_geometry_invalid(geometry):
    try:
        geom = shape(geometry)
        if not geom.is_valid:
            return True, explain_validity(geom)
        return False, ""
    except Exception as e:
        return True, str(e)


def extract_polygon_only(geom):
    if geom.is_empty:
        return None

    if isinstance(geom, Polygon):
        return geom

    if isinstance(geom, MultiPolygon):
        return geom

    if isinstance(geom, GeometryCollection):
        polygon_parts = []
        for sub_geom in geom.geoms:
            polygon_only = extract_polygon_only(sub_geom)
            if polygon_only and not polygon_only.is_empty:
                polygon_parts.append(polygon_only)

        if not polygon_parts:
            return None

        merged = unary_union(polygon_parts)
        if isinstance(merged, (Polygon, MultiPolygon)) and not merged.is_empty:
            return merged
        return None

    if hasattr(geom, "geoms"):
        polygon_parts = [
            sub_geom for sub_geom in geom.geoms
            if isinstance(sub_geom, (Polygon, MultiPolygon)) and not sub_geom.is_empty
        ]
        if not polygon_parts:
            return None

        merged = unary_union(polygon_parts)
        if isinstance(merged, (Polygon, MultiPolygon)) and not merged.is_empty:
            return merged

    return None


def has_minimum_polygon_points(geom):
    if geom is None or geom.is_empty:
        return False

    if isinstance(geom, Polygon):
        return len(list(geom.exterior.coords)) - 1 >= 3

    if isinstance(geom, MultiPolygon):
        valid_polygons = [
            polygon for polygon in geom.geoms
            if len(list(polygon.exterior.coords)) - 1 >= 3
        ]
        return len(valid_polygons) > 0

    return False


def filter_polygon_by_points(geom):
    if geom is None or geom.is_empty:
        return None

    if isinstance(geom, Polygon):
        return geom if has_minimum_polygon_points(geom) else None

    if isinstance(geom, MultiPolygon):
        valid_polygons = [
            polygon for polygon in geom.geoms
            if has_minimum_polygon_points(polygon)
        ]
        if not valid_polygons:
            return None
        if len(valid_polygons) == 1:
            return valid_polygons[0]
        return MultiPolygon(valid_polygons)

    return None


def check_geojson(data):
    issues = []
    for i, feature in enumerate(data.get("features", [])):
        geom = feature.get("geometry")
        if not geom:
            continue

        invalid, reason = is_geometry_invalid(geom)
        if invalid:
            issues.append((i, geom.get("type"), reason))
    return issues


def fix_geojson(data):
    fixed_data = json.loads(json.dumps(data))
    fixed_count = 0
    removed_count = 0

    for feature in fixed_data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        invalid, _ = is_geometry_invalid(geometry)
        if not invalid:
            continue

        try:
            fixed_geometry = make_valid(shape(geometry))
            polygon_only = extract_polygon_only(fixed_geometry)
            polygon_only = filter_polygon_by_points(polygon_only)
            if polygon_only is None:
                feature["geometry"] = None
                removed_count += 1
                continue

            feature["geometry"] = mapping(polygon_only)
            fixed_count += 1
        except Exception:
            continue

    fixed_data["features"] = [
        feature
        for feature in fixed_data.get("features", [])
        if feature.get("geometry")
        and feature["geometry"].get("type") in {"Polygon", "MultiPolygon"}
    ]

    return fixed_data, fixed_count, removed_count


def sanitize_column_name(name, used_names):
    sanitized = "".join(char if char.isalnum() or char == "_" else "_" for char in str(name))
    sanitized = sanitized[:10] or "field"

    candidate = sanitized
    suffix = 1
    while candidate.lower() in used_names:
        suffix_text = str(suffix)
        candidate = f"{sanitized[:10 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    used_names.add(candidate.lower())
    return candidate


def build_shapefile_zip(fixed_data, base_name):
    try:
        import geopandas as gpd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Thieu thu vien geopandas trong moi truong deploy, chua the xuat shapefile zip."
        ) from exc

    features = fixed_data.get("features", [])
    if not features:
        raise ValueError("Khong co feature hop le de xuat shapefile.")

    gdf = gpd.GeoDataFrame.from_features(features)
    if gdf.empty:
        raise ValueError("Khong tao duoc du lieu shapefile tu GeoJSON da fix.")

    gdf = gdf.set_geometry("geometry")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    used_names = set()
    rename_map = {}
    for column in gdf.columns:
        if column == "geometry":
            continue
        rename_map[column] = sanitize_column_name(column, used_names)

    if rename_map:
        gdf = gdf.rename(columns=rename_map)

    for column in gdf.columns:
        if column == "geometry":
            continue
        gdf[column] = gdf[column].apply(
            lambda value: json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else value
        )

    safe_name = os.path.splitext(base_name)[0].replace(" ", "_")
    if not safe_name:
        safe_name = "fixed_geometry"

    with tempfile.TemporaryDirectory() as tmp_dir:
        shp_path = os.path.join(tmp_dir, f"{safe_name}.shp")
        gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="UTF-8")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for extension in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                file_path = os.path.join(tmp_dir, f"{safe_name}{extension}")
                if os.path.exists(file_path):
                    zip_file.write(file_path, arcname=os.path.basename(file_path))

        return zip_buffer.getvalue()


def read_shapefiles_from_zip(zip_bytes, zip_filename):
    """Load each SHP dataset in a ZIP as a GeoJSON FeatureCollection.

    Only files belonging to an SHP dataset are extracted, without honoring
    archive directory paths (prevents path traversal). Coordinates are
    transformed to WGS84 for correct GeoJSON output.
    """
    try:
        import geopandas as gpd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Can cai dat geopandas de doc bo Shapefile ZIP."
        ) from exc

    results = []
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as archive:
        members = [entry for entry in archive.infolist() if not entry.is_dir()]
        shp_members = [entry for entry in members if entry.filename.lower().endswith(".shp")]
        if not shp_members:
            raise ValueError("ZIP khong chua file .shp.")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for index, shp_member in enumerate(shp_members):
                base = os.path.splitext(shp_member.filename)[0]
                sidecars = [entry for entry in members if os.path.splitext(entry.filename)[0].lower() == base.lower()]
                extensions = {os.path.splitext(entry.filename)[1].lower() for entry in sidecars}
                if not {".shp", ".shx", ".dbf"}.issubset(extensions):
                    raise ValueError(f"Bo SHP '{base}' thieu .shp, .shx hoac .dbf.")

                shp_dir = os.path.join(tmp_dir, f"shp_{index}")
                os.makedirs(shp_dir, exist_ok=True)
                safe_base = "input"
                for entry in sidecars:
                    ext = os.path.splitext(entry.filename)[1].lower()
                    if ext not in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                        continue
                    dest = os.path.join(shp_dir, safe_base + ext)
                    with archive.open(entry) as source, open(dest, "wb") as target:
                        import shutil
                        shutil.copyfileobj(source, target)

                gdf = gpd.read_file(os.path.join(shp_dir, safe_base + ".shp"))
                if gdf.crs is not None:
                    gdf = gdf.to_crs("EPSG:4326")
                else:
                    # As before, missing CRS is treated as WGS84 for export.
                    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
                geojson_data = json.loads(gdf.to_json())
                display_name = os.path.splitext(zip_filename)[0] + " / " + base + ".shp"
                results.append((display_name, geojson_data))

    return results


uploaded_files = st.file_uploader(
    "Upload nhieu file GeoJSON",
    type=["geojson"],
    accept_multiple_files=True,
)

uploaded_shapefile_zips = st.file_uploader(
    "Hoac upload bo Shapefile (.shp + .shx + .dbf, khuyen nghi co .prj) duoi dang ZIP",
    type=["zip"],
    accept_multiple_files=True,
)

if "fixed_results" not in st.session_state:
    st.session_state.fixed_results = {}

input_datasets = []
for uploaded_file in uploaded_files:
    try:
        input_datasets.append((uploaded_file.name, json.load(uploaded_file), f"geojson_{uploaded_file.name}_{uploaded_file.size}"))
    except Exception as error:
        st.error(f"Khong doc duoc GeoJSON {uploaded_file.name}: {error}")

for uploaded_zip in uploaded_shapefile_zips:
    try:
        for name, data in read_shapefiles_from_zip(uploaded_zip.getvalue(), uploaded_zip.name):
            input_datasets.append((name, data, f"shp_{uploaded_zip.name}_{uploaded_zip.size}_{name}"))
    except Exception as error:
        st.error(f"Khong doc duoc ZIP {uploaded_zip.name}: {error}")

if input_datasets:
    st.info(f"Tim thay {len(input_datasets)} bo du lieu Polygon")

    for display_name, data, file_key in input_datasets:
        st.markdown("---")
        st.subheader(f"File: {display_name}")
        try:
            issues = check_geojson(data)

            if not issues:
                st.success("Khong phat hien loi")
                continue

            st.error(f"Co {len(issues)} feature bi loi")
            with st.expander(f"Xem chi tiet {len(issues)} loi", expanded=False):
                for idx, gtype, reason in issues:
                    st.write(f"- Feature {idx} ({gtype}): {reason}")

            if st.button(f"Fix geometry - {display_name}", key=f"fix_{file_key}"):
                fixed_data, fixed_count, removed_count = fix_geojson(data)
                remaining_issues = check_geojson(fixed_data)
                fixed_content = json.dumps(fixed_data, ensure_ascii=False, indent=2)
                base_name = os.path.splitext(os.path.basename(display_name))[0]
                fixed_name = f"{base_name}_fixed.geojson"

                shapefile_zip = None
                shapefile_error = None
                try:
                    shapefile_zip = build_shapefile_zip(fixed_data, fixed_name)
                except Exception as export_error:
                    shapefile_error = str(export_error)

                st.session_state.fixed_results[file_key] = {
                    "fixed_data": fixed_data,
                    "fixed_count": fixed_count,
                    "removed_count": removed_count,
                    "remaining_issue_count": len(remaining_issues),
                    "fixed_content": fixed_content,
                    "fixed_name": fixed_name,
                    "shapefile_zip": shapefile_zip,
                    "shapefile_error": shapefile_error,
                }

            result = st.session_state.fixed_results.get(file_key)
            if result:
                if result["fixed_count"] == 0:
                    st.warning("Khong fix duoc geometry nao")
                else:
                    st.success(f"Da fix {result['fixed_count']} feature")

                if result["removed_count"] > 0:
                    st.info(
                        f"Da loai {result['removed_count']} feature khong con geometry polygon sau khi fix."
                    )

                if result["remaining_issue_count"] > 0:
                    st.warning(f"Con lai {result['remaining_issue_count']} feature chua fix duoc")
                else:
                    st.success("File tai xuong chi giu geometry Polygon/MultiPolygon hop le")

                st.download_button(
                    label=f"Tai file da fix - {display_name}",
                    data=result["fixed_content"].encode("utf-8"),
                    file_name=result["fixed_name"],
                    mime="application/geo+json",
                    key=f"download_{file_key}",
                )

                if result["shapefile_zip"] is not None:
                    zip_name = result["fixed_name"].replace(".geojson", "_shapefile.zip")
                    st.download_button(
                        label=f"Tai shapefile zip - {display_name}",
                        data=result["shapefile_zip"],
                        file_name=zip_name,
                        mime="application/zip",
                        key=f"download_shp_{file_key}",
                    )
                elif result["shapefile_error"]:
                    st.warning(f"Khong xuat duoc shapefile zip: {result['shapefile_error']}")
        except Exception as e:
            st.error(f"Khong doc duoc file: {e}")

# Chay: streamlit run check_polygon_delop.py
