import json

import streamlit as st
from shapely.geometry import shape
from shapely.validation import explain_validity


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
            else:
                st.error(f"Co {len(issues)} feature bi loi")
                for idx, gtype, reason in issues:
                    st.write(f"- Feature {idx} ({gtype}): {reason}")
        except Exception as e:
            st.error(f"Khong doc duoc file: {e}")

# === dung lenh "streamlit run check_polygon_delop.py" chay trong terminal ==
