import os
import shutil
import zipfile
import subprocess
from pathlib import Path

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# Windows example:
ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"

# Nếu chạy Linux bằng wine hoặc container thì chỉnh lại path này
# ODA_EXE = "/opt/ODAFileConverter/ODAFileConverter"


def clean_folder(folder: Path):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file) -> Path:
    file_path = UPLOAD_DIR / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def convert_dwg_to_dxf(dwg_path: Path, out_dir: Path) -> Path:
    """
    Convert DWG to DXF using ODA File Converter CLI.

    ODA CLI format commonly uses:
    ODAFileConverter input_dir output_dir output_version output_type recursive audit input_filter
    """

    input_dir = dwg_path.parent
    output_dir = out_dir

    cmd = [
        ODA_EXE,
        str(input_dir),
        str(output_dir),
        "ACAD2018",
        "DXF",
        "0",
        "1",
        dwg_path.name,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=False
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ODA convert failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    dxf_files = list(output_dir.glob("*.dxf"))
    if not dxf_files:
        raise FileNotFoundError("Không tìm thấy file DXF sau khi convert từ DWG.")

    return dxf_files[0]


def dxf_to_geojson(dxf_path: Path, geojson_path: Path):
    cmd = [
        "ogr2ogr",
        "-f", "GeoJSON",
        str(geojson_path),
        str(dxf_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=False
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"DXF to GeoJSON failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def dxf_to_shapefile_by_geometry(dxf_path: Path, shp_out_dir: Path):
    """
    Shapefile chỉ nên chứa 1 loại geometry/layer.
    CAD thường có Point, LineString, Polygon, Text...
    Nên export tách theo geometry.
    """

    shp_out_dir.mkdir(parents=True, exist_ok=True)

    geometry_types = {
        "points": "POINT",
        "lines": "LINESTRING",
        "polygons": "POLYGON",
    }

    created_files = []

    for name, geom_type in geometry_types.items():
        out_path = shp_out_dir / f"{name}.shp"

        cmd = [
            "ogr2ogr",
            "-f", "ESRI Shapefile",
            str(out_path),
            str(dxf_path),
            "-where", f"OGR_GEOMETRY='{geom_type}'",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False
        )

        # Có thể không có geometry type đó, không coi là lỗi nghiêm trọng
        if out_path.exists():
            created_files.append(out_path)

    if not created_files:
        # fallback convert toàn bộ
        out_path = shp_out_dir / "cad_entities.shp"
        cmd = [
            "ogr2ogr",
            "-f", "ESRI Shapefile",
            str(out_path),
            str(dxf_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"DXF to Shapefile failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    return shp_out_dir


def zip_folder(folder_path: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob("*"):
            if file.is_file():
                zipf.write(file, file.relative_to(folder_path))
    return zip_path


def preview_geojson(geojson_path: Path):
    gdf = gpd.read_file(geojson_path)

    if gdf.empty:
        st.warning("GeoJSON rỗng, không có đối tượng để hiển thị.")
        return

    # Nếu CAD chưa có CRS, giả định đang là WGS84 để preview.
    # Thực tế nên cho user chọn EPSG.
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326, allow_override=True)

    try:
        gdf_preview = gdf.to_crs(epsg=4326)
    except Exception:
        gdf_preview = gdf

    bounds = gdf_preview.total_bounds

    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=17)

    folium.GeoJson(
        gdf_preview.to_json(),
        name="DWG Preview"
    ).add_to(m)

    folium.LayerControl().add_to(m)

    st_folium(m, width=1000, height=600)

    st.subheader("Thông tin dữ liệu")
    st.write("Số lượng feature:", len(gdf_preview))
    st.write("Geometry types:", list(gdf_preview.geometry.geom_type.unique()))
    st.dataframe(gdf_preview.drop(columns="geometry").head(100))


st.set_page_config(page_title="DWG to Shapefile Tool", layout="wide")

st.title("DWG Viewer & Converter to Shapefile")

uploaded_file = st.file_uploader("Upload file DWG", type=["dwg"])

if uploaded_file:
    clean_folder(TEMP_DIR)
    clean_folder(OUTPUT_DIR)

    dwg_path = save_uploaded_file(uploaded_file)

    st.success(f"Đã upload: {dwg_path.name}")

    if st.button("Xử lý DWG"):
        try:
            with st.spinner("Đang chuyển DWG sang DXF..."):
                dxf_dir = TEMP_DIR / "dxf"
                dxf_dir.mkdir(exist_ok=True)
                dxf_path = convert_dwg_to_dxf(dwg_path, dxf_dir)

            st.success(f"Đã convert sang DXF: {dxf_path.name}")

            with st.spinner("Đang tạo GeoJSON để preview..."):
                geojson_path = OUTPUT_DIR / "preview.geojson"
                dxf_to_geojson(dxf_path, geojson_path)

            st.success("Đã tạo preview GeoJSON")

            st.subheader("Preview bản vẽ")
            preview_geojson(geojson_path)

            with st.spinner("Đang convert sang Shapefile..."):
                shp_dir = OUTPUT_DIR / "shapefile"
                dxf_to_shapefile_by_geometry(dxf_path, shp_dir)

                zip_path = OUTPUT_DIR / "shapefile_result.zip"
                zip_folder(shp_dir, zip_path)

            st.success("Đã convert sang Shapefile")

            with open(zip_path, "rb") as f:
                st.download_button(
                    label="Download Shapefile ZIP",
                    data=f,
                    file_name="shapefile_result.zip",
                    mime="application/zip"
                )

        except Exception as e:
            st.error("Có lỗi khi xử lý file.")
            st.code(str(e))