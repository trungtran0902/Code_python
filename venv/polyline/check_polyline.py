import json
import math

import streamlit as st
from shapely.geometry import LineString, MultiLineString, mapping, shape
from shapely.validation import explain_validity


st.set_page_config(page_title="Check Loi Polyline", page_icon=":straight_ruler:", layout="wide")
st.title("Check Loi Polyline (Upload nhieu file GeoJSON)")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_valid_lon_lat(coord):
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        return False
    lon, lat = coord[0], coord[1]
    if not is_number(lon) or not is_number(lat):
        return False
    return -180 <= lon <= 180 and -90 <= lat <= 90


def find_consecutive_duplicate_points(coords):
    duplicates = []
    for index in range(1, len(coords)):
        if coords[index] == coords[index - 1]:
            duplicates.append(index)
    return duplicates


def validate_linestring_coords(coords):
    issues = []

    if not isinstance(coords, list):
        return ["Coordinates khong phai list."]

    if len(coords) < 2:
        return ["LineString phai co it nhat 2 diem."]

    invalid_points = []
    for index, coord in enumerate(coords):
        if not is_valid_lon_lat(coord):
            invalid_points.append(index)

    if invalid_points:
        issues.append(f"Toa do khong hop le tai cac diem: {invalid_points}")

    duplicate_points = find_consecutive_duplicate_points(coords)
    if duplicate_points:
        issues.append(f"Co diem trung lien tiep tai index: {duplicate_points}")

    return issues


def check_polyline_geometry(geometry):
    issues = []
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "LineString":
        issues.extend(validate_linestring_coords(coords))
    elif geom_type == "MultiLineString":
        if not isinstance(coords, list) or not coords:
            issues.append("MultiLineString khong co coordinates hop le.")
        else:
            for line_index, line_coords in enumerate(coords):
                line_issues = validate_linestring_coords(line_coords)
                for issue in line_issues:
                    issues.append(f"Line {line_index}: {issue}")
    else:
        issues.append(f"Geometry type khong phai polyline: {geom_type}")
        return issues

    try:
        geom = shape(geometry)
        if geom.is_empty:
            issues.append("Geometry rong.")
        if geom.length == 0:
            issues.append("Geometry co do dai bang 0.")
        if not geom.is_valid:
            issues.append(explain_validity(geom))
    except Exception as exc:
        issues.append(f"Loi shapely: {exc}")

    return issues


def is_geometry_polyline(geometry):
    return geometry.get("type") in {"LineString", "MultiLineString"}


def check_geojson(data):
    issues = []
    for index, feature in enumerate(data.get("features", [])):
        geometry = feature.get("geometry")
        if not geometry:
            issues.append((index, "None", ["Feature khong co geometry."]))
            continue

        if not is_geometry_polyline(geometry):
            issues.append((index, geometry.get("type"), [f"Khong phai polyline: {geometry.get('type')}"]))
            continue

        geometry_issues = check_polyline_geometry(geometry)
        if geometry_issues:
            issues.append((index, geometry.get("type"), geometry_issues))
    return issues


def remove_consecutive_duplicate_points(coords):
    if not coords:
        return coords

    cleaned = [coords[0]]
    for coord in coords[1:]:
        if coord != cleaned[-1]:
            cleaned.append(coord)
    return cleaned


def try_fix_polyline_geometry(geometry):
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "LineString":
        cleaned = [coord for coord in coords if is_valid_lon_lat(coord)]
        cleaned = remove_consecutive_duplicate_points(cleaned)
        if len(cleaned) >= 2:
            return {"type": "LineString", "coordinates": cleaned}, True
        return geometry, False

    if geom_type == "MultiLineString":
        fixed_lines = []
        for line_coords in coords or []:
            cleaned = [coord for coord in line_coords if is_valid_lon_lat(coord)]
            cleaned = remove_consecutive_duplicate_points(cleaned)
            if len(cleaned) >= 2:
                fixed_lines.append(cleaned)
        if fixed_lines:
            return {"type": "MultiLineString", "coordinates": fixed_lines}, True
        return geometry, False

    return geometry, False


def fix_geojson(data):
    fixed_data = json.loads(json.dumps(data))
    fixed_count = 0

    for feature in fixed_data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry or not is_geometry_polyline(geometry):
            continue

        fixed_geometry, changed = try_fix_polyline_geometry(geometry)
        if changed:
            feature["geometry"] = fixed_geometry
            fixed_count += 1

    return fixed_data, fixed_count


uploaded_files = st.file_uploader(
    "Upload nhieu file GeoJSON",
    type=["geojson"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.info(f"Tim thay {len(uploaded_files)} file GeoJSON")

    for uploaded_file in uploaded_files:
        st.markdown("---")
        st.subheader(f"File: {uploaded_file.name}")

        try:
            data = json.load(uploaded_file)
            issues = check_geojson(data)

            if not issues:
                st.success("Khong phat hien loi polyline")
                continue

            st.error(f"Co {len(issues)} feature bi loi")
            with st.expander(f"Xem chi tiet {len(issues)} loi", expanded=False):
                for feature_index, geom_type, reasons in issues:
                    st.write(f"- Feature {feature_index} ({geom_type})")
                    for reason in reasons:
                        st.write(f"  + {reason}")

            if st.button(f"Fix polyline - {uploaded_file.name}", key=f"fix_{uploaded_file.name}"):
                fixed_data, fixed_count = fix_geojson(data)
                remaining_issues = check_geojson(fixed_data)

                if fixed_count == 0:
                    st.warning("Khong fix duoc polyline nao")
                else:
                    st.success(f"Da fix {fixed_count} feature")

                if remaining_issues:
                    st.warning(f"Con lai {len(remaining_issues)} feature chua fix duoc")
                else:
                    st.success("Tat ca polyline da hop le sau khi fix")

                fixed_content = json.dumps(fixed_data, ensure_ascii=False, indent=2)
                fixed_name = uploaded_file.name.replace(".geojson", "_fixed.geojson")

                st.download_button(
                    label=f"Tai file da fix - {uploaded_file.name}",
                    data=fixed_content.encode("utf-8"),
                    file_name=fixed_name,
                    mime="application/geo+json",
                    key=f"download_{uploaded_file.name}",
                )
        except Exception as exc:
            st.error(f"Khong doc duoc file: {exc}")

# === dung lenh "streamlit run check_polyline.py" chay trong terminal ==
