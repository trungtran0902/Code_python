import json
import math

import streamlit as st
from shapely.geometry import shape
from shapely.validation import explain_validity


st.set_page_config(page_title="Check Loi Point", page_icon=":round_pushpin:", layout="wide")
st.title("Check Loi Point (Upload nhieu file GeoJSON)")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def to_number(value):
    if is_number(value):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if not cleaned:
            return None
        try:
            number = float(cleaned)
            if math.isfinite(number):
                return number
        except ValueError:
            return None

    return None


def normalize_point_coordinates(coords):
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None

    lon = to_number(coords[0])
    lat = to_number(coords[1])
    if lon is None or lat is None:
        return None

    z_value = None
    if len(coords) > 2:
        z_value = to_number(coords[2])

    if -180 <= lon <= 180 and -90 <= lat <= 90:
        if z_value is not None:
            return [lon, lat, z_value]
        return [lon, lat]

    if -180 <= lat <= 180 and -90 <= lon <= 90:
        if z_value is not None:
            return [lat, lon, z_value]
        return [lat, lon]

    return None


def is_geometry_point(geometry):
    return geometry.get("type") == "Point"


def check_non_point_geometry(geometry):
    geom_type = geometry.get("type")
    issues = [f"Geometry khong phai Point, dang la: {geom_type}"]

    try:
        geom = shape(geometry)
        if geom.is_empty:
            issues.append("Geometry rong.")
        if not geom.is_valid:
            issues.append(explain_validity(geom))
    except Exception as exc:
        issues.append(f"Loi shapely: {exc}")

    return issues


def check_point_geometry(geometry):
    issues = []
    coords = geometry.get("coordinates")

    if not isinstance(coords, (list, tuple)):
        issues.append("Coordinates khong phai list/tuple.")
        return issues

    if len(coords) < 2:
        issues.append("Point phai co it nhat 2 gia tri [lon, lat].")
        return issues

    lon = to_number(coords[0])
    lat = to_number(coords[1])

    if lon is None or lat is None:
        issues.append("Longitude/Latitude khong phai so hop le.")
    else:
        if not (-180 <= lon <= 180):
            issues.append(f"Longitude ngoai pham vi hop le: {lon}")
        if not (-90 <= lat <= 90):
            issues.append(f"Latitude ngoai pham vi hop le: {lat}")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            swapped_ok = -180 <= lat <= 180 and -90 <= lon <= 90
            if swapped_ok:
                issues.append("Toa do co the dang bi dao lat/lon.")

    try:
        geom = shape(geometry)
        if geom.is_empty:
            issues.append("Geometry rong.")
        if not geom.is_valid:
            issues.append(explain_validity(geom))
    except Exception as exc:
        issues.append(f"Loi shapely: {exc}")

    return issues


def check_geojson(data):
    issues = []
    for index, feature in enumerate(data.get("features", [])):
        geometry = feature.get("geometry")
        if not geometry:
            issues.append((index, "None", ["Feature khong co geometry."]))
            continue

        if not is_geometry_point(geometry):
            issues.append(
                (
                    index,
                    geometry.get("type"),
                    check_non_point_geometry(geometry),
                )
            )
            continue

        geometry_issues = check_point_geometry(geometry)
        if geometry_issues:
            issues.append((index, geometry.get("type"), geometry_issues))
    return issues


def try_fix_point_geometry(geometry):
    if geometry.get("type") != "Point":
        return geometry, False

    coords = geometry.get("coordinates")
    normalized_coords = normalize_point_coordinates(coords)
    if normalized_coords is None:
        return geometry, False

    original_coords = list(coords) if isinstance(coords, (list, tuple)) else coords
    changed = original_coords != normalized_coords
    return {"type": "Point", "coordinates": normalized_coords}, changed


def fix_geojson(data):
    fixed_data = json.loads(json.dumps(data))
    fixed_count = 0

    for feature in fixed_data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry or not is_geometry_point(geometry):
            continue

        fixed_geometry, changed = try_fix_point_geometry(geometry)
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
                st.success("Khong phat hien loi Point")
                continue

            st.error(f"Co {len(issues)} feature bi loi")
            with st.expander(f"Xem chi tiet {len(issues)} loi", expanded=False):
                for feature_index, geom_type, reasons in issues:
                    st.write(f"- Feature {feature_index} ({geom_type})")
                    for reason in reasons:
                        st.write(f"  + {reason}")

            if st.button(f"Fix point - {uploaded_file.name}", key=f"fix_{uploaded_file.name}"):
                fixed_data, fixed_count = fix_geojson(data)
                remaining_issues = check_geojson(fixed_data)

                if fixed_count == 0:
                    st.warning("Khong fix duoc Point nao")
                else:
                    st.success(f"Da fix {fixed_count} feature")

                if remaining_issues:
                    st.warning(f"Con lai {len(remaining_issues)} feature chua fix duoc")
                else:
                    st.success("Tat ca Point da hop le sau khi fix")

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

# === dung lenh python -m streamlit run check_loi_poi.py chay trong terminal ==
