import csv
import json
import hashlib
import os
import tempfile
import zipfile
import time
from datetime import datetime
from io import BytesIO, StringIO

import streamlit as st
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, LineString, mapping, shape
from shapely.ops import transform as geom_transform, unary_union
from shapely.strtree import STRtree
from pyproj import CRS, Transformer
from shapely.validation import explain_validity, make_valid


st.set_page_config(page_title="Check loi Polygon", page_icon=":jigsaw:", layout="wide")
st.title("Check loi Polygon + Topology Gap (GeoJSON / Shapefile ZIP)")


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


# -----------------------------------------------------------------------------
# Topology: detect enclosed uncovered areas in the polygon union.
# IMPORTANT: these are *candidate gaps*, not all ArcGIS Must Not Have Gaps errors.
# Open-to-exterior slivers require an authoritative coverage boundary to detect.
# -----------------------------------------------------------------------------

def local_metric_crs(data):
    """Choose a local UTM CRS from feature bounds; areas use square metres."""
    import geopandas as gpd
    geoms = [shape(f["geometry"]) for f in data.get("features", [])
             if f.get("geometry") and f["geometry"].get("type") in ("Polygon", "MultiPolygon")]
    if not geoms:
        raise ValueError("Khong co Polygon/MultiPolygon de kiem tra topology.")
    bounds = gpd.GeoSeries(geoms, crs="EPSG:4326").total_bounds
    lon = (bounds[0] + bounds[2]) / 2
    lat = (bounds[1] + bounds[3]) / 2
    if not (-180 <= lon <= 180 and -80 <= lat <= 84):
        raise ValueError("Toa do nam ngoai pham vi UTM; kiem tra lai CRS dau vao.")
    zone = max(1, min(60, int((lon + 180) // 6) + 1))
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def collect_projected(data):
    crs = local_metric_crs(data)
    forward = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    indices, geoms = [], []
    for i, f in enumerate(data.get("features", [])):
        gj = f.get("geometry")
        if not gj or gj.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        g = shape(gj)
        if not g.is_valid:
            raise ValueError(f"Feature {i} chua hop le. Hay fix geometry truoc khi scan Gap.")
        if not g.is_empty:
            indices.append(i)
            geoms.append(geom_transform(forward, g))
    if not geoms:
        raise ValueError("Khong co feature de kiem tra.")
    return indices, geoms, inverse, crs.to_string()


def topology_scan(data, max_report=200000, progress_callback=None):
    """Find enclosed holes in the union. Return projected geometries for repair."""
    indices, geometries, inverse, metric_crs = collect_projected(data)
    if progress_callback:
        progress_callback(0, "Đang hợp nhất các Polygon để xác định lỗ khép kín...")
    merged = unary_union(geometries)
    dissolved_parts = ([merged] if isinstance(merged, Polygon) else
                       list(merged.geoms) if isinstance(merged, MultiPolygon) else [])
    holes = [Polygon(ring) for poly in dissolved_parts for ring in poly.interiors]
    if progress_callback:
        progress_callback(0.08, f"Đã xác định {len(holes):,} lỗ khép kín; đang lập chỉ mục cạnh...")
    if len(holes) > max_report:
        raise ValueError(f"Co hon {max_report:,} lo hong; du lieu qua lon de tao report tren Streamlit.")
    # Index short boundary pieces rather than intersecting huge whole-feature
    # boundaries for every tiny gap (much faster on detailed SHP inputs).
    edge_segments = []
    segment_owners = []
    for feature_idx, geom in zip(indices, geometries):
        polys = [geom] if isinstance(geom, Polygon) else list(geom.geoms)
        for poly in polys:
            for ring in [poly.exterior, *poly.interiors]:
                coords = list(ring.coords)
                for pos in range(0, len(coords) - 1, 96):
                    part = coords[pos:min(pos + 97, len(coords))]
                    if len(part) >= 2:
                        edge_segments.append(LineString(part))
                        segment_owners.append(feature_idx)
    tree = STRtree(edge_segments)
    if progress_callback:
        progress_callback(0.17, f"Đã lập chỉ mục {len(edge_segments):,} đoạn cạnh; đang đối chiếu lân cận...")
    rows, records = [], []
    for gap_num, hole in enumerate(holes, 1):
        if progress_callback and (gap_num == 1 or gap_num % 500 == 0 or gap_num == len(holes)):
            progress_callback(0.17 + 0.83 * gap_num / max(1, len(holes)),
                              f"Đã kiểm tra {gap_num:,}/{len(holes):,} lỗ khép kín")
        if hole.is_empty or hole.area <= 0:
            continue
        neighbor_lengths = {}
        # Look up short boundary segments, then aggregate their intersection
        # lengths by feature. Large holes are reported but never auto-filled.
        if hole.area <= 10.0:
            hb = hole.boundary
            for j in tree.query(hole):
                k = int(j)
                length = hb.intersection(edge_segments[k]).length
                if length > 0.00001:
                    owner = segment_owners[k]
                    neighbor_lengths[owner] = neighbor_lengths.get(owner, 0.0) + length
        lengths = list(neighbor_lengths.items())
        lengths.sort(key=lambda pair: (-pair[1], pair[0]))
        seam = len(lengths) >= 2
        best = lengths[0][0] if lengths else None
        total_len = sum(v for _, v in lengths)
        share = lengths[0][1] / total_len if total_len > 0 else 0.0
        category = ("large_hole_not_auto_fix" if hole.area > 10.0 else
                    "between_features" if seam else "single_feature_hole_or_unknown")
        rows.append({
            "gap_id": gap_num, "area_m2": round(hole.area, 6),
            "category": category, "neighbors": len(lengths),
            "target_feature_index": best if best is not None else "",
            "target_share": round(share, 6), "status": "candidate",
        })
        records.append((hole, lengths))
    return {"rows": rows, "records": records, "indices": indices,
            "geometries": geometries, "inverse": inverse,
            "crs": metric_crs, "feature_count": len(indices)}


def fill_topology_gaps(data, scan, threshold_m2, min_share=0.5, progress_callback=None):
    """Batch merge eligible enclosed seam gaps into their best adjacent feature.

    Batch union once per affected feature to avoid extremely slow repeated unions
    against very detailed geometry. Feature count/attributes/order are preserved.
    """
    fixed = json.loads(json.dumps(data))
    inverse = Transformer.from_crs(scan["crs"], "EPSG:4326", always_xy=True).transform
    geometries = dict(zip(scan["indices"], scan["geometries"]))
    groups = {}
    statuses = ["kept"] * len(scan["rows"])
    for n, (row, (hole, lengths)) in enumerate(zip(scan["rows"], scan["records"])):
        if (row["category"] != "between_features" or
                not (0 < hole.area <= threshold_m2) or not lengths):
            continue
        if row["target_share"] < min_share:
            statuses[n] = "skipped_ambiguous_neighbor"
            continue
        target = lengths[0][0]
        groups.setdefault(target, []).append((n, hole))

    filled_area = 0.0
    for k, (target, members) in enumerate(groups.items(), 1):
        if progress_callback and (k == 1 or k % 25 == 0 or k == len(groups)):
            progress_callback(k / max(1, len(groups)),
                              f"Đang gộp Gap vào Feature: {k:,}/{len(groups):,} Feature")
        try:
            old = geometries[target]
            new = unary_union([old] + [g for _, g in members])
            expected = sum(g.area for _, g in members)
            if (new.is_valid and isinstance(new, (Polygon, MultiPolygon)) and
                    abs(new.area - old.area - expected) <= max(0.01, expected * 0.001)):
                geometries[target] = new
                fixed["features"][target]["geometry"] = mapping(geom_transform(inverse, new))
                filled_area += expected
                for n, _ in members:
                    statuses[n] = "filled"
            else:
                for n, _ in members:
                    statuses[n] = "skipped_validation"
        except Exception:
            for n, _ in members:
                statuses[n] = "skipped_error"
    if check_geojson(fixed):
        raise ValueError("Sau khi lap Gap geometry invalid; output bi huy.")
    for row, status in zip(scan["rows"], statuses):
        row["status"] = status
    return fixed, statuses.count("filled"), filled_area


def gaps_geojson(scan, only_unfilled=False):
    inv = scan["inverse"]
    features = []
    for row, (hole, _) in zip(scan["rows"], scan["records"]):
        if only_unfilled and row["status"] == "filled":
            continue
        features.append({"type": "Feature", "geometry": mapping(geom_transform(inv, hole)),
                         "properties": dict(row)})
    return {"type": "FeatureCollection", "features": features}


def gaps_csv(scan):
    buf = StringIO()
    columns = ["gap_id", "area_m2", "category", "neighbors", "target_feature_index", "target_share", "status"]
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(scan["rows"])
    return buf.getvalue().encode("utf-8-sig")


def export_files(data, display_name):
    base = os.path.splitext(os.path.basename(display_name))[0]
    geo_name = f"{base}_fixed.geojson"
    geo = json.dumps(data, ensure_ascii=False).encode("utf-8")
    shp, error = None, None
    try:
        shp = build_shapefile_zip(data, geo_name)
    except Exception as exc:
        error = str(exc)
    return {"geo_name": geo_name, "geo_bytes": geo, "shp_bytes": shp,
            "shp_name": f"{base}_fixed_shapefile.zip", "error": error}


st.caption("Kiểm tra Geometry từng Feature và Topology Gap khép kín. Gap thông ra ranh ngoài cần ranh tham chiếu để phát hiện.")

with st.expander("Cấu hình xử lý", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        process_mode = st.radio(
            "Chế độ chạy",
            ["Chỉ kiểm tra và xuất báo cáo", "Kiểm tra + tự lấp Gap đủ điều kiện"],
            index=0,
            help="Mặc định không thay đổi ranh giới; chế độ lấp Gap cần chọn chủ động.",
        )
    with c2:
        gap_threshold = st.selectbox(
            "Diện tích Gap tối đa được lấp",
            [0.1, 1.0, 5.0, 10.0], index=1,
            format_func=lambda value: f"{value:g} m²",
        )
        min_share = st.slider(
            "Tỷ lệ cạnh chung tối thiểu của Feature nhận Gap",
            0.5, 1.0, 0.5, 0.05,
            help="Chỉ lấp Gap khép kín giữa ít nhất 2 Feature, khi Feature nhận Gap có tỷ lệ cạnh chung đạt ngưỡng.",
        )
    st.info("Tool sẽ tự chạy tuần tự: đọc dữ liệu → kiểm tra → fix geometry nếu cần → scan Gap → lấp Gap nếu đã chọn → kiểm tra lại → xuất kết quả. Diện tích tính bằng m² (UTM địa phương).")

uploaded_files = st.file_uploader("Upload nhiều file GeoJSON", type=["geojson"], accept_multiple_files=True)
uploaded_shapefile_zips = st.file_uploader(
    "Hoặc upload Shapefile ZIP (.shp + .shx + .dbf; nên có .prj)",
    type=["zip"], accept_multiple_files=True,
)

@st.cache_data(show_spinner=False, max_entries=8)
def cached_read_shp_zip(raw, name):
    return read_shapefiles_from_zip(raw, name)

@st.cache_data(show_spinner=False, max_entries=8)
def cached_export(data_as_json, name):
    return export_files(json.loads(data_as_json), name)

input_datasets = []
for upload in uploaded_files:
    try:
        raw = upload.getvalue()
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise ValueError("Yêu cầu GeoJSON FeatureCollection")
        digest = hashlib.sha256(raw).hexdigest()[:16]
        input_datasets.append((upload.name, data, f"geo_{digest}"))
    except Exception as exc:
        st.error(f"Không đọc được GeoJSON {upload.name}: {exc}")
for upload in uploaded_shapefile_zips:
    try:
        raw = upload.getvalue()
        digest = hashlib.sha256(raw).hexdigest()[:16]
        for name, data in cached_read_shp_zip(raw, upload.name):
            input_datasets.append((name, data, f"shp_{digest}_{name}"))
    except Exception as exc:
        st.error(f"Không đọc được ZIP {upload.name}: {exc}")

if "run_results_v3" not in st.session_state:
    st.session_state.run_results_v3 = {}

if input_datasets:
    st.write(f"**Đã nhận {len(input_datasets)} bộ Polygon:** " + ", ".join(n for n, _, _ in input_datasets[:6]) + ("…" if len(input_datasets) > 6 else ""))
else:
    st.info("Hãy upload GeoJSON hoặc Shapefile ZIP để bắt đầu.")

run_clicked = st.button("▶ BẮT ĐẦU XỬ LÝ", type="primary", use_container_width=True, disabled=not input_datasets)

if run_clicked:
    # Every run is intentional and independent of older session results.
    st.session_state.run_results_v3 = {}
    overall_progress = st.progress(0, text="Khởi tạo phiên xử lý...")
    current_status = st.empty()
    live_log = st.empty()
    log_lines = []
    start_total = time.perf_counter()

    def write_log(message, level="INFO"):
        stamp = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"[{stamp}] [{level}] {message}")
        # cap text displayed to prevent excessive Streamlit rerender overhead
        live_log.code("\n".join(log_lines[-45:]), language="text")

    write_log(f"Bắt đầu: {len(input_datasets)} bộ dữ liệu; chế độ: {process_mode}")
    for n, (display_name, source_data, file_key) in enumerate(input_datasets):
        t0 = time.perf_counter()
        base_progress = n / len(input_datasets)
        span = 1 / len(input_datasets)
        def update(frac, detail):
            frac = max(0.0, min(1.0, frac))
            overall_progress.progress(min(1., base_progress + span * frac), text=f"Bộ {n+1}/{len(input_datasets)} • {detail}")
            current_status.info(f"Đang xử lý: {display_name} — {detail}")

        result = {"name": display_name, "logs": [], "status": "error"}
        st.session_state.run_results_v3[file_key] = result
        def step(message, level="INFO"):
            result["logs"].append(message)
            write_log(f"[{n+1}/{len(input_datasets)}] {display_name}: {message}", level)

        step("Đọc dữ liệu thành công")
        try:
            update(0.03, "kiểm tra geometry")
            initial_count = len(source_data.get("features", []))
            initial_issues = check_geojson(source_data)
            result["initial_count"] = initial_count
            result["initial_issues"] = initial_issues
            step(f"Feature ban đầu: {initial_count:,}; geometry invalid: {len(initial_issues):,}")

            working = source_data
            count = removed = 0
            if initial_issues:
                update(0.08, "sửa geometry lỗi")
                working, count, removed = fix_geojson(source_data)
                step(f"Fix geometry: {count:,} Feature sửa; {removed:,} Feature loại theo cơ chế cũ")
            else:
                step("Geometry hợp lệ; không cần fix")
            remaining = check_geojson(working)
            result.update({"fixed_count": count, "removed_count": removed,
                           "remaining_geometry": len(remaining)})
            if remaining:
                step(f"Còn {len(remaining):,} geometry invalid; bỏ qua scan Gap để tránh kết quả sai", "WARN")
                result["error"] = "Còn geometry invalid sau bước fix"
                result["status"] = "partial"
                result["output_data"] = working
                update(0.92, "xuất geometry đã fix một phần")
            else:
                update(0.15, "chuẩn bị scan Topology Gap")
                def scan_progress(p, detail):
                    update(0.15 + 0.60 * p, detail)
                    if p in (0, 0.08, 0.17) or p >= 1.0 or (p > 0.17 and int(p*100) % 10 == 0):
                        # avoid duplicate status lines for many close progress updates
                        if not result["logs"] or result["logs"][-1] != detail:
                            step(detail)
                scan = topology_scan(working, progress_callback=scan_progress)
                result["scan"] = scan
                rows = scan["rows"]
                seams = [r for r in rows if r["category"] == "between_features"]
                eligible = [r for r in seams if r["area_m2"] <= gap_threshold and r["target_share"] >= min_share]
                result["seam_count"] = len(seams)
                result["eligible_count"] = len(eligible)
                step(f"Scan xong: {len(rows):,} lỗ khép kín; {len(seams):,} Gap giữa Feature; {len(eligible):,} đủ điều kiện theo cấu hình")
                if process_mode == "Kiểm tra + tự lấp Gap đủ điều kiện":
                    step(f"Bắt đầu lấp Gap ≤ {gap_threshold:g} m²; tỷ lệ cạnh chung ≥ {min_share:.2f}")
                    def fill_progress(p, detail):
                        update(0.77 + 0.12 * p, detail)
                    working, filled, area = fill_topology_gaps(
                        working, scan, gap_threshold, min_share, progress_callback=fill_progress)
                    result["filled_count"] = filled
                    result["filled_area"] = area
                    step(f"Đã lấp {filled:,} Gap; diện tích cộng thêm {area:,.4f} m²")
                else:
                    result["filled_count"] = 0
                    result["filled_area"] = 0
                    step("Chỉ SCAN: không thay đổi ranh giới vì chưa bật chế độ lấp")
                update(0.91, "kiểm tra lại geometry")
                last_issues = check_geojson(working)
                if last_issues:
                    raise ValueError(f"Output còn {len(last_issues)} geometry invalid")
                step("Kiểm tra lại: 0 geometry invalid")
                result["output_data"] = working
                result["status"] = "success"

            update(0.94, "chuẩn bị file xuất")
            exp = cached_export(json.dumps(result["output_data"], ensure_ascii=False), display_name)
            result["exports"] = exp
            if exp["error"]:
                step(f"Không xuất được SHP: {exp['error']}", "WARN")
            else:
                step("Xuất GeoJSON và Shapefile ZIP thành công")
            step(f"Hoàn thành sau {time.perf_counter() - t0:.1f} giây", "DONE")
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            step(f"Lỗi: {exc}", "ERROR")
        update(1.0, "xong")
    elapsed = time.perf_counter() - start_total
    done = sum(r["status"] == "success" for r in st.session_state.run_results_v3.values())
    write_log(f"KẾT THÚC: {done}/{len(input_datasets)} bộ thành công; tổng thời gian {elapsed:.1f} giây", "DONE")
    st.session_state.last_logs_v3 = "\n".join(log_lines)
    current_status.success(f"Đã xử lý xong {len(input_datasets)} bộ; thành công {done}/{len(input_datasets)}. Xem kết quả bên dưới.")

if st.session_state.get("last_logs_v3"):
    with st.expander("Nhật ký xử lý (log)", expanded=True):
        st.code(st.session_state.last_logs_v3, language="text")
        st.download_button("Tải log .txt", data=st.session_state.last_logs_v3.encode("utf-8-sig"),
                           file_name="check_polygon_processing_log.txt", mime="text/plain")

for display_name, _, file_key in input_datasets:
    result = st.session_state.run_results_v3.get(file_key)
    if not result:
        continue
    st.divider()
    st.subheader(f"Kết quả: {display_name}")
    if result["status"] == "error":
        st.error(result.get("error", "Xử lý thất bại"))
    elif result["status"] == "partial":
        st.warning("Còn lỗi geometry, chưa chạy Scan Gap")
    else:
        st.success("Đã hoàn thành kiểm tra Geometry + Scan Topology Gap")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Feature", f"{result.get('initial_count', 0):,}")
    m2.metric("Geometry lỗi ban đầu", f"{len(result.get('initial_issues', [])):,}")
    m3.metric("Gap giữa Feature", f"{result.get('seam_count', 0):,}")
    m4.metric("Gap đã lấp", f"{result.get('filled_count', 0):,}")
    if "scan" in result:
        scan = result["scan"]
        st.caption(f"Phát hiện {len(scan['rows']):,} lỗ khép kín, {result['eligible_count']:,} Gap đủ điều kiện lấp; "
                   f"diện tích đã lấp {result['filled_area']:,.4f} m². Gap thông ra ngoài chưa được kiểm tra.")
        st.download_button("Tải báo cáo Gap CSV", data=gaps_csv(scan),
                           file_name="topology_gaps_report.csv", mime="text/csv", key=f"report_{file_key}")
        st.download_button("Tải vị trí Gap GeoJSON", data=json.dumps(gaps_geojson(scan), ensure_ascii=False).encode("utf-8"),
                           file_name="topology_gaps.geojson", mime="application/geo+json", key=f"gap_geo_{file_key}")
    if "exports" in result:
        exp = result["exports"]
        st.download_button("Tải GeoJSON kết quả", data=exp["geo_bytes"],
                           file_name=exp["geo_name"], mime="application/geo+json", key=f"geo_{file_key}")
        if exp["shp_bytes"] is not None:
            st.download_button("Tải Shapefile ZIP kết quả (ArcGIS)", data=exp["shp_bytes"],
                               file_name=exp["shp_name"], mime="application/zip", key=f"shp_{file_key}")
        elif exp["error"]:
            st.warning(f"Không xuất được SHP: {exp['error']}")

# Chạy: streamlit run check_polygon_delop.py
