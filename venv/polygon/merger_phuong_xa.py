import streamlit as st
import json

st.set_page_config(page_title="GeoJSON Merger", layout="wide")

st.title("🗺️ Merge Multiple GeoJSON Polygon ALL ")
st.write("Upload multiple .geojson files to merge them into one FeatureCollection.")

uploaded_files = st.file_uploader(
    "📂 Upload GeoJSON files",
    type=["geojson"],
    accept_multiple_files=True
)

if uploaded_files:

    all_features = []
    error_files = []

    with st.spinner("Processing files..."):
        for file in uploaded_files:
            try:
                data = json.load(file)

                if data["type"] == "FeatureCollection":
                    all_features.extend(data["features"])

                elif data["type"] == "Feature":
                    all_features.append(data)

                else:
                    error_files.append(file.name)

            except Exception:
                error_files.append(file.name)

    if error_files:
        st.warning("⚠ Some files could not be processed:")
        for f in error_files:
            st.write(f"- {f}")

    if all_features:
        merged_geojson = {
            "type": "FeatureCollection",
            "features": all_features
        }

        st.success(f"✅ Merge completed!")
        st.info(f"📊 Total features: {len(all_features)}")

        # Preview JSON (optional)
        with st.expander("🔍 Preview merged JSON"):
            st.json(merged_geojson)

        # Download button
        st.download_button(
            label="⬇ Download merged GeoJSON",
            data=json.dumps(merged_geojson, ensure_ascii=False, indent=2),
            file_name="merged.geojson",
            mime="application/json"
        )

    else:
        st.error("❌ No valid GeoJSON features found.")
else:
    st.info("Please upload at least one GeoJSON file.")