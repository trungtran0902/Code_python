import os
import json
import zipfile
import tempfile
import streamlit as st
from shapely.geometry import shape
from shapely.validation import explain_validity


st.set_page_config(page_title="Check lỗi Polygon", page_icon="🧩", layout="wide")
st.title("🧩 Check lỗi Polygon (Upload file)")


# -----------------------
# Logic xử lý polygon
# -----------------------
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


# -----------------------
# UI upload ZIP
# -----------------------
uploaded_zip = st.file_uploader(
    "📦 Upload folder GeoJSON (zip)",
    type=["zip"]
)

if uploaded_zip:
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "data.zip")

        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        st.success("✅ Đã giải nén folder")

        geojson_files = []
        for root, _, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".geojson"):
                    geojson_files.append(os.path.join(root, file))

        if not geojson_files:
            st.warning("⚠️ Không tìm thấy file .geojson trong folder")
        else:
            st.info(f"🔍 Tìm thấy {len(geojson_files)} file GeoJSON")

            for file_path in geojson_files:
                st.markdown("---")
                st.subheader(f"📄 {os.path.basename(file_path)}")

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                issues = check_geojson(data)

                if not issues:
                    st.success("✅ Không phát hiện lỗi")
                else:
                    st.error(f"❌ {len(issues)} feature lỗi")
                    for idx, gtype, reason in issues:
                        st.write(f"- Feature {idx} ({gtype}): {reason}")
#=== dùng lệnh "streamlit run check_polygon_delop.py" chạy trong ternimal==