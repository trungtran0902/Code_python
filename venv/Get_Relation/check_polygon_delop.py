import json

import streamlit as st
from shapely.geometry import mapping, shape
from shapely.validation import explain_validity, make_valid


st.set_page_config(page_title="Check loi Polygon", page_icon=":jigsaw:", layout="wide")
st.title("Check loi Polygon (Upload nhieu file GeoJSON)")


def is_geometry_invalid(geometry):
    try:
        geom = shape(geometry)
        if not geom.is_valid:
            return True, explain_validity(geom)
        return False, ""
    except Exception as e:
        return True, str(e)


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

    for feature in fixed_data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        invalid, _ = is_geometry_invalid(geometry)
        if not invalid:
            continue

        try:
            fixed_geometry = make_valid(shape(geometry))
            feature["geometry"] = mapping(fixed_geometry)
            fixed_count += 1
        except Exception:
            continue

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
                st.success("Khong phat hien loi")
                continue

            st.error(f"Co {len(issues)} feature bi loi")
            for idx, gtype, reason in issues:
                st.write(f"- Feature {idx} ({gtype}): {reason}")

            if st.button(f"Fix geometry - {uploaded_file.name}", key=f"fix_{uploaded_file.name}"):
                fixed_data, fixed_count = fix_geojson(data)
                remaining_issues = check_geojson(fixed_data)

                if fixed_count == 0:
                    st.warning("Khong fix duoc geometry nao")
                else:
                    st.success(f"Da fix {fixed_count} feature")

                if remaining_issues:
                    st.warning(f"Con lai {len(remaining_issues)} feature chua fix duoc")
                else:
                    st.success("Tat ca geometry da hop le sau khi fix")

                fixed_content = json.dumps(fixed_data, ensure_ascii=False, indent=2)
                fixed_name = uploaded_file.name.replace(".geojson", "_fixed.geojson")

                st.download_button(
                    label=f"Tai file da fix - {uploaded_file.name}",
                    data=fixed_content.encode("utf-8"),
                    file_name=fixed_name,
                    mime="application/geo+json",
                    key=f"download_{uploaded_file.name}",
                )
        except Exception as e:
            st.error(f"Khong doc duoc file: {e}")

# === dung lenh "streamlit run check_polygon_delop.py" chay trong terminal ==
