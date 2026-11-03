import csv
import json
import hashlib
import os
import tempfile
import zipfile
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


def topology_scan(data, max_report=200000):
    """Find enclosed holes in the union. Return projected geometries for repair."""
    indices, geometries, inverse, metric_crs = collect_projected(data)
    merged = unary_union(geometries)
    dissolved_parts = ([merged] if isinstance(merged, Polygon) else
                       list(merged.geoms) if isinstance(merged, MultiPolygon) else [])
    holes = [Polygon(ring) for poly in dissolved_parts for ring in poly.interiors]
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
    rows, records = [], []
    for gap_num, hole in enumerate(holes, 1):
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


def fill_topology_gaps(data, scan, threshold_m2, min_share=0.5):
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
    for target, members in groups.items():
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


st.caption("Kiem tra geometry tung Feature va Gap topology nam kin ben trong vung phu. Gap mo ra bien ngoai can ranh tham chieu de phat hien.")
with st.expander("Cau hinh Topology Gap", expanded=True):
    st.info("Che do mac dinh chi SCAN, khong tu y sua ranh. Don vi dien tich: m² (UTM dia phuong).")
    gap_threshold = st.selectbox("Chi lap Gap co dien tich khong vuot qua", [0.1, 1.0, 5.0, 10.0], index=1, format_func=lambda v: f"{v:g} m²")
    min_share = st.slider("Ty le canh chung toi thieu cua Feature duoc nhan Gap", 0.5, 1.0, 0.5, 0.05,
                          help="Chi lap vao Feature tiep giap co do dai canh chung lon nhat, va dat ty le nay.")

uploaded_files = st.file_uploader("Upload nhieu file GeoJSON", type=["geojson"], accept_multiple_files=True)
uploaded_shapefile_zips = st.file_uploader(
    "Hoac upload Shapefile ZIP (.shp + .shx + .dbf, khuyen nghi co .prj)",
    type=["zip"], accept_multiple_files=True)

if "results_v2" not in st.session_state:
    st.session_state.results_v2 = {}

input_datasets = []
for uploaded_file in uploaded_files:
    try:
        raw = uploaded_file.getvalue()
        data = json.loads(raw)
        checksum = hashlib.sha256(raw).hexdigest()[:16]
        input_datasets.append((uploaded_file.name, data, f"geo_{checksum}"))
    except Exception as error:
        st.error(f"Khong doc duoc GeoJSON {uploaded_file.name}: {error}")

for uploaded_zip in uploaded_shapefile_zips:
    try:
        raw = uploaded_zip.getvalue()
        checksum = hashlib.sha256(raw).hexdigest()[:16]
        for name, data in read_shapefiles_from_zip(raw, uploaded_zip.name):
            input_datasets.append((name, data, f"shp_{checksum}_{name}"))
    except Exception as error:
        st.error(f"Khong doc duoc ZIP {uploaded_zip.name}: {error}")

if input_datasets:
    st.info(f"Tim thay {len(input_datasets)} bo du lieu Polygon")

for display_name, source_data, file_key in input_datasets:
    st.divider()
    st.subheader(f"File: {display_name}")
    if file_key not in st.session_state.results_v2:
        st.session_state.results_v2[file_key] = {}
    result = st.session_state.results_v2[file_key]
    initial_issues = check_geojson(source_data)
    st.write(f"So Feature ban dau: **{len(source_data.get('features', []))}**; Geometry invalid: **{len(initial_issues)}**")
    if initial_issues:
        with st.expander(f"Xem chi tiet {len(initial_issues)} loi geometry"):
            for idx, typ, msg in initial_issues[:300]:
                st.write(f"- Feature {idx} ({typ}): {msg}")
            if len(initial_issues) > 300:
                st.caption("Chi hien thi 300 loi dau.")
    else:
        st.success("Geometry: khong phat hien feature invalid. Chua co nghia topology khong Gap.")

    if st.button(f"1. Fix geometry (co che cu) - {display_name}", key=f"fix_{file_key}"):
        fixed, count, removed = fix_geojson(source_data)
        remaining = check_geojson(fixed)
        result.clear()
        result.update({"data": fixed, "fixed_count": count, "removed_count": removed,
                       "remaining": len(remaining)})
    if "data" in result:
        st.write(f"Da fix **{result['fixed_count']}** feature; da loai **{result['removed_count']}** (theo logic cu); con **{result['remaining']}** loi geometry.")

    working = result.get("data", source_data)
    working_issues = check_geojson(working)
    if st.button(f"2. Scan Topology Gap - {display_name}", key=f"scan_{file_key}",
                 disabled=bool(working_issues)):
        try:
            with st.spinner("Dang tinh union va quet cac vung trong khep kin..."):
                scan = topology_scan(working)
            result["scan"] = scan
            result.pop("topology_data", None)
            result.pop("topology_summary", None)
        except Exception as exc:
            st.error(f"Scan Gap that bai: {exc}")

    if "scan" in result:
        scan = result["scan"]
        rows = scan["rows"]
        seam = [r for r in rows if r["category"] == "between_features"]
        eligible = [r for r in seam if 0 < r["area_m2"] <= gap_threshold and r["target_share"] >= min_share]
        a, b, c, d = st.columns(4)
        a.metric("Lo kin phat hien", f"{len(rows):,}")
        b.metric("Gap giua Feature", f"{len(seam):,}")
        c.metric("Gap du dieu kien lap", f"{len(eligible):,}")
        d.metric("Tong dien tich ho", f"{sum(r['area_m2'] for r in rows):,.2f} m²")
        st.caption("Gap phat hien = lo kin trong polygon union; khong bao gom cac khe thong ra ben ngoai hoac Gap ngoai ranh quy hoach. 'Gap giua Feature' can it nhat hai Feature co chung bien.")
        st.download_button("Tai bao cao Gap CSV", data=gaps_csv(scan),
                           file_name="topology_gaps_report.csv", mime="text/csv", key=f"csv_{file_key}")
        st.download_button("Tai cac Gap de kiem tra tren ArcGIS (GeoJSON)",
                           data=json.dumps(gaps_geojson(scan), ensure_ascii=False).encode("utf-8"),
                           file_name="topology_gaps.geojson", mime="application/geo+json", key=f"gaps_{file_key}")
        st.warning("Can xac nhan Gap la loi thuc su truoc khi lap. Cong cu KHONG tu lap cac lo nam trong 1 Feature, Gap lon hon nguong, hoac Gap khong du ty le canh chung.")
        if st.button(f"3. Lap Gap <= {gap_threshold:g} m² va xuat ket qua - {display_name}",
                     key=f"gapfix_{file_key}_{gap_threshold}_{min_share}"):
            try:
                with st.spinner("Dang lap cac Gap du dieu kien..."):
                    out, count, area = fill_topology_gaps(working, scan, gap_threshold, min_share)
                result["topology_data"] = out
                result["topology_summary"] = (count, area)
            except Exception as exc:
                st.error(f"Lap Gap that bai: {exc}")

    final_data = result.get("topology_data", result.get("data"))
    if final_data is not None:
        if "topology_summary" in result:
            count, area = result["topology_summary"]
            st.success(f"Da lap {count:,} Gap; tong dien tich bo sung {area:,.4f} m². Feature/thuoc tinh duoc giu nguyen.")
        st.caption("Ket qua output: da xu ly geometry" + (" + topology Gap" if "topology_data" in result else ""))
        # Build exports only when a result exists; cache per content identity in session.
        output_sig = (id(final_data), len(final_data.get("features", [])))
        if result.get("export_sig") != output_sig:
            result["exports"] = export_files(final_data, display_name)
            result["export_sig"] = output_sig
        exp = result["exports"]
        st.download_button("Tai GeoJSON da fix", data=exp["geo_bytes"],
                           file_name=exp["geo_name"], mime="application/geo+json", key=f"outgeo_{file_key}")
        if exp["shp_bytes"] is not None:
            st.download_button("Tai Shapefile ZIP da fix (dung cho ArcGIS)", data=exp["shp_bytes"],
                               file_name=exp["shp_name"], mime="application/zip", key=f"outshp_{file_key}")
        else:
            st.warning(f"Khong xuat duoc SHP: {exp['error']}")

# Chay: streamlit run check_polygon_delop.py
