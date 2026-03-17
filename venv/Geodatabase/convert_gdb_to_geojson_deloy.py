import io
import json
import os
import tempfile
import zipfile

import streamlit as st


st.set_page_config(page_title="Convert GDB to GeoJSON", page_icon=":world_map:", layout="wide")
st.title("Convert GDB to GeoJSON")
st.caption("Upload file .zip chua thu muc .gdb de chuyen doi tung layer sang GeoJSON")


def find_gdb_folder(root_dir):
    for current_root, dirnames, _ in os.walk(root_dir):
        for dirname in dirnames:
            if dirname.lower().endswith(".gdb"):
                return os.path.join(current_root, dirname)
    return None


def list_layers(gdb_path):
    import pyogrio

    layers_info = pyogrio.list_layers(gdb_path)
    return [layer[0] for layer in layers_info]


def convert_layer_to_geojson_text(gdb_path, layer_name):
    import pyogrio

    gdf = pyogrio.read_dataframe(gdb_path, layer=layer_name)
    return gdf.to_json()


def build_download_zip(converted_files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, content in converted_files.items():
            zip_file.writestr(file_name, content)
    buffer.seek(0)
    return buffer


def sanitize_name(name):
    invalid_chars = '<>:"/\\|?*'
    return "".join("_" if ch in invalid_chars else ch for ch in name).replace(" ", "_")


def extract_uploaded_zip(uploaded_zip, temp_dir):
    zip_path = os.path.join(temp_dir, uploaded_zip.name)
    with open(zip_path, "wb") as file_obj:
        file_obj.write(uploaded_zip.getbuffer())

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)


def validate_zip_file(uploaded_zip):
    if not uploaded_zip:
        return False, "Vui long upload file .zip"
    if not uploaded_zip.name.lower().endswith(".zip"):
        return False, "Chi ho tro file .zip"
    return True, ""


uploaded_zip = st.file_uploader("Upload file ZIP chua thu muc .gdb", type=["zip"])

is_valid, message = validate_zip_file(uploaded_zip)
if uploaded_zip and not is_valid:
    st.error(message)

if uploaded_zip and is_valid:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_uploaded_zip(uploaded_zip, temp_dir)
            gdb_path = find_gdb_folder(temp_dir)

            if not gdb_path:
                st.error("Khong tim thay thu muc .gdb trong file zip")
            else:
                st.success(f"Da tim thay geodatabase: {os.path.basename(gdb_path)}")

                layers = list_layers(gdb_path)
                if not layers:
                    st.warning("Khong tim thay layer nao trong geodatabase")
                else:
                    st.info(f"Tim thay {len(layers)} layer")

                    converted_files = {}
                    results = []

                    for layer_name in layers:
                        try:
                            geojson_text = convert_layer_to_geojson_text(gdb_path, layer_name)
                            output_name = f"{sanitize_name(layer_name)}.geojson"
                            converted_files[output_name] = geojson_text

                            feature_count = len(json.loads(geojson_text).get("features", []))
                            results.append((layer_name, "Thanh cong", feature_count))
                        except Exception as exc:
                            results.append((layer_name, f"Loi: {exc}", 0))

                    st.subheader("Ket qua chuyen doi")
                    for layer_name, status, feature_count in results:
                        if status == "Thanh cong":
                            st.success(f"{layer_name}: {status} - {feature_count} features")
                        else:
                            st.error(f"{layer_name}: {status}")

                    if converted_files:
                        output_zip = build_download_zip(converted_files)
                        download_name = f"{os.path.splitext(uploaded_zip.name)[0]}_geojson.zip"
                        st.download_button(
                            label="Tai file ZIP GeoJSON",
                            data=output_zip,
                            file_name=download_name,
                            mime="application/zip",
                        )
                    else:
                        st.warning("Khong co layer nao duoc chuyen doi thanh cong")
    except ModuleNotFoundError as exc:
        st.error(f"Thieu thu vien can thiet: {exc}")
        st.info("Can cai geopandas, pyogrio va cac phu thuoc GDAL trong moi truong deploy")
    except zipfile.BadZipFile:
        st.error("File zip khong hop le")
    except Exception as exc:
        st.error(f"Khong the xu ly file upload: {exc}")
