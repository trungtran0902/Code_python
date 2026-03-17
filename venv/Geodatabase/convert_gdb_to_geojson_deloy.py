import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import warnings
import zipfile

import streamlit as st


os.environ.setdefault("CPL_DEBUG", "OFF")
warnings.filterwarnings("ignore")

st.set_page_config(page_title="Convert GDB to GeoJSON", page_icon=":world_map:", layout="wide")
st.title("Convert GDB to GeoJSON")
st.caption("Upload file .zip chua thu muc .gdb de kiem tra he toa do, chuyen sang WGS 84 va convert GeoJSON")


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


def read_layer_dataframe(gdb_path, layer_name):
    import pyogrio

    with contextlib.redirect_stderr(io.StringIO()):
        return pyogrio.read_dataframe(gdb_path, layer=layer_name)


def get_layer_crs(gdb_path, layer_name):
    gdf = read_layer_dataframe(gdb_path, layer_name)
    return gdf.crs


def find_first_available_crs(gdb_path, layers):
    for layer_name in layers:
        try:
            crs = get_layer_crs(gdb_path, layer_name)
            if crs:
                return layer_name, crs
        except Exception:
            continue
    return None, None


def get_central_meridian(crs):
    if not crs or not crs.coordinate_operation:
        return None

    for param in crs.coordinate_operation.params:
        param_name = param.name.lower()
        if "central meridian" in param_name or "longitude of natural origin" in param_name:
            return param.value
    return None


def parse_crs_info(crs):
    from pyproj import CRS

    parsed_crs = CRS.from_user_input(crs)
    epsg_code = parsed_crs.to_epsg()
    crs_name = parsed_crs.name or "Khong ro ten CRS"
    datum_name = parsed_crs.datum.name if parsed_crs.datum else ""
    central_meridian = get_central_meridian(parsed_crs)

    normalized_name = crs_name.upper()
    normalized_datum = datum_name.upper()
    is_wgs84 = "WGS 84" in normalized_name or "WGS 84" in normalized_datum or epsg_code == 4326
    is_vn2000 = "VN-2000" in normalized_name or "VN_2000" in normalized_name or "VN-2000" in normalized_datum

    if is_wgs84:
        system_label = "WGS 84"
    elif is_vn2000:
        system_label = "VN-2000"
    else:
        system_label = crs_name

    return {
        "label": system_label,
        "name": crs_name,
        "epsg": epsg_code,
        "datum": datum_name,
        "central_meridian": central_meridian,
        "is_wgs84": is_wgs84,
        "is_vn2000": is_vn2000,
    }


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


def append_log(log_lines, message, log_placeholder):
    log_lines.append(message)
    log_placeholder.code("\n".join(log_lines), language="text")


def normalize_properties_for_json(gdf):
    for column_name in gdf.columns:
        if column_name == "geometry":
            continue

        series = gdf[column_name]

        if getattr(series.dtype, "kind", "") == "M":
            gdf[column_name] = series.dt.strftime("%Y-%m-%dT%H:%M:%S").where(series.notna(), None)
            continue

        if series.dtype == "object":
            gdf[column_name] = series.apply(
                lambda value: value.isoformat()
                if isinstance(value, (dt.datetime, dt.date))
                else value
            )

    return gdf


def is_geometry_usable(geometry):
    if geometry is None or geometry.is_empty:
        return False

    try:
        geometry.__geo_interface__
        return True
    except Exception:
        return False


def repair_geometry(geometry):
    from shapely import make_valid

    if geometry is None:
        return None

    try:
        repaired = make_valid(geometry)
        if is_geometry_usable(repaired):
            return repaired
    except Exception:
        pass

    try:
        repaired = geometry.buffer(0)
        if is_geometry_usable(repaired):
            return repaired
    except Exception:
        pass

    return None


def fix_invalid_geometries(gdf):
    if gdf.empty or "geometry" not in gdf:
        return gdf, 0, 0

    gdf = gdf.copy()
    fixed_count = 0
    null_geometry_count = 0

    for row_index, geometry in gdf.geometry.items():
        if geometry is None:
            continue

        try:
            is_valid = bool(geometry.is_valid)
        except Exception:
            is_valid = False

        if is_valid and is_geometry_usable(geometry):
            continue

        repaired = repair_geometry(geometry)
        if repaired is not None:
            gdf.at[row_index, "geometry"] = repaired
            fixed_count += 1
        else:
            gdf.at[row_index, "geometry"] = None
            null_geometry_count += 1

    return gdf, fixed_count, null_geometry_count


def dataframe_to_geojson_text(gdf):
    with contextlib.redirect_stderr(io.StringIO()):
        return gdf.to_json()


def build_download_zip(converted_files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, content in converted_files.items():
            zip_file.writestr(file_name, content)
    buffer.seek(0)
    return buffer


def render_crs_info(crs_info, layer_name):
    st.subheader("Thong tin he toa do")
    st.caption(f"Phat hien tu layer: {layer_name}")
    st.write(f"- He toa do: {crs_info['label']}")
    st.write(f"- Ten CRS: {crs_info['name']}")
    if crs_info["epsg"]:
        st.write(f"- EPSG: {crs_info['epsg']}")
    if crs_info["datum"]:
        st.write(f"- Datum: {crs_info['datum']}")
    if crs_info["central_meridian"] is not None:
        st.write(f"- Kinh tuyen truc: {crs_info['central_meridian']}")


def process_layers(gdb_path, layers, mode):
    converted_files = {}
    results = []
    log_lines = []

    mode_label = {
        "reproject_only": "Chuyen he toa do sang WGS 84",
        "convert_geojson": "Convert GeoJSON",
    }[mode]

    st.subheader("Tien trinh xu ly")
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    log_expander = st.expander("Xem log chi tiet", expanded=False)
    log_placeholder = log_expander.empty()

    append_log(log_lines, f"Bat dau: {mode_label}", log_placeholder)
    append_log(log_lines, f"Mo geodatabase: {os.path.basename(gdb_path)}", log_placeholder)
    append_log(log_lines, f"Tim thay {len(layers)} layer", log_placeholder)

    for index, layer_name in enumerate(layers, start=1):
        status_placeholder.info(f"Dang xu ly {index}/{len(layers)}: {layer_name}")
        append_log(log_lines, f"[{index}/{len(layers)}] Dang doc layer: {layer_name}", log_placeholder)

        try:
            gdf = read_layer_dataframe(gdb_path, layer_name)
            source_crs = gdf.crs
            reprojected = False
            original_feature_count = len(gdf)
            gdf, fixed_geometry_count, null_geometry_count = fix_invalid_geometries(gdf)
            gdf = normalize_properties_for_json(gdf)

            if fixed_geometry_count > 0:
                append_log(
                    log_lines,
                    f"[{index}/{len(layers)}] Da sua {fixed_geometry_count} geometry loi trong layer {layer_name}",
                    log_placeholder,
                )

            if null_geometry_count > 0:
                append_log(
                    log_lines,
                    f"[{index}/{len(layers)}] Co {null_geometry_count} feature khong the sua geometry, da giu lai feature va dat geometry = null trong layer {layer_name}",
                    log_placeholder,
                )

            if source_crs:
                crs_info = parse_crs_info(source_crs)
                if mode in {"reproject_only", "convert_geojson"} and not crs_info["is_wgs84"]:
                    with contextlib.redirect_stderr(io.StringIO()):
                        gdf = gdf.to_crs(4326)
                    reprojected = True
                    append_log(
                        log_lines,
                        f"[{index}/{len(layers)}] Da chuyen {layer_name} sang WGS 84",
                        log_placeholder,
                    )

            geojson_text = dataframe_to_geojson_text(gdf)
            feature_count = len(json.loads(geojson_text).get("features", []))
            output_name = f"{sanitize_name(layer_name)}.geojson"
            converted_files[output_name] = geojson_text

            if feature_count != original_feature_count:
                append_log(
                    log_lines,
                    f"[{index}/{len(layers)}] Canh bao: so feature thay doi tu {original_feature_count} thanh {feature_count} o layer {layer_name}",
                    log_placeholder,
                )

            if reprojected:
                status_text = "Thanh cong - da chuyen sang WGS 84"
            else:
                status_text = "Thanh cong"

            results.append((layer_name, status_text, feature_count))
            append_log(
                log_lines,
                f"[{index}/{len(layers)}] Hoan thanh: {layer_name} ({feature_count} features)",
                log_placeholder,
            )
        except Exception as exc:
            results.append((layer_name, f"Loi: {exc}", 0))
            append_log(
                log_lines,
                f"[{index}/{len(layers)}] Loi: {layer_name} -> {exc}",
                log_placeholder,
            )

        progress_bar.progress(index / len(layers))

    status_placeholder.success("Da hoan tat qua trinh xu ly.")
    append_log(log_lines, "Da hoan tat qua trinh xu ly.", log_placeholder)
    return converted_files, results


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

                    crs_layer_name, detected_crs = find_first_available_crs(gdb_path, layers)
                    crs_info = None

                    if detected_crs:
                        crs_info = parse_crs_info(detected_crs)
                        render_crs_info(crs_info, crs_layer_name)
                    else:
                        st.warning("Khong doc duoc thong tin he toa do tu cac layer")

                    st.write("Chon hanh dong ben duoi de xu ly du lieu.")

                    if crs_info and crs_info["is_vn2000"]:
                        st.warning("Du lieu dang o he VN-2000. Ban co the chuyen sang WGS 84 truoc khi convert.")

                    col1, col2 = st.columns(2)
                    with col1:
                        reproject_clicked = st.button("Chuyen he toa do sang WGS 84", type="primary")
                    with col2:
                        convert_clicked = st.button("Convert GeoJSON")

                    if reproject_clicked:
                        converted_files, results = process_layers(gdb_path, layers, mode="reproject_only")

                        st.subheader("Ket qua chuyen he toa do")
                        for layer_name, status, feature_count in results:
                            if status.startswith("Thanh cong"):
                                st.success(f"{layer_name}: {status} - {feature_count} features")
                            else:
                                st.error(f"{layer_name}: {status}")

                        if converted_files:
                            output_zip = build_download_zip(converted_files)
                            download_name = f"{os.path.splitext(uploaded_zip.name)[0]}_wgs84.zip"
                            st.download_button(
                                label="Tai ZIP du lieu WGS 84",
                                data=output_zip,
                                file_name=download_name,
                                mime="application/zip",
                            )
                            st.info("File tai ve la ZIP chua cac layer da duoc dua ve WGS 84 o dang GeoJSON.")
                        else:
                            st.warning("Khong co layer nao duoc chuyen he toa do thanh cong")

                    if convert_clicked:
                        converted_files, results = process_layers(gdb_path, layers, mode="convert_geojson")

                        st.subheader("Ket qua convert GeoJSON")
                        for layer_name, status, feature_count in results:
                            if status.startswith("Thanh cong"):
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
                            st.warning("Khong co layer nao duoc convert thanh cong")
    except ModuleNotFoundError as exc:
        st.error(f"Thieu thu vien can thiet: {exc}")
        st.info("Can cai geopandas, pyogrio va cac phu thuoc GDAL trong moi truong deploy")
    except zipfile.BadZipFile:
        st.error("File zip khong hop le")
    except Exception as exc:
        st.error(f"Khong the xu ly file upload: {exc}")
