import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from tkinter import Tk, filedialog


CURRENT_FILE = Path(__file__).resolve()
VENDOR_DIR = CURRENT_FILE.parents[2] / "_vendor_geo"
GeometryCollection = None
MultiPolygon = None
Polygon = None
mapping = None
shape = None
unary_union = None
explain_validity = None
make_valid = None


def add_candidate_site_packages():
    candidate_paths = [
        CURRENT_FILE.parent / "_vendor",
        VENDOR_DIR,
        CURRENT_FILE.parents[1] / "Lib" / "site-packages",
        CURRENT_FILE.parents[3] / "venv" / "Lib" / "site-packages",
        CURRENT_FILE.parents[4] / "venv" / "Lib" / "site-packages",
        CURRENT_FILE.parents[3] / "Code_python" / "venv" / "Lib" / "site-packages",
    ]

    for path in candidate_paths:
        try:
            if path.exists():
                path_str = str(path)
                if path_str not in sys.path:
                    sys.path.append(path_str)
        except OSError:
            continue


def try_import_shapely():
    add_candidate_site_packages()
    importlib.invalidate_caches()
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
    from shapely.ops import unary_union
    from shapely.validation import explain_validity, make_valid

    return (
        GeometryCollection,
        MultiPolygon,
        Polygon,
        mapping,
        shape,
        unary_union,
        explain_validity,
        make_valid,
    )


def ensure_shapely_available():
    global GeometryCollection, MultiPolygon, Polygon, mapping
    global shape, unary_union, explain_validity, make_valid

    if all(
        value is not None
        for value in (
            GeometryCollection,
            MultiPolygon,
            Polygon,
            mapping,
            shape,
            unary_union,
            explain_validity,
            make_valid,
        )
    ):
        return

    try:
        (
            GeometryCollection,
            MultiPolygon,
            Polygon,
            mapping,
            shape,
            unary_union,
            explain_validity,
            make_valid,
        ) = try_import_shapely()
        return
    except ModuleNotFoundError:
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "shapely",
                    "--target",
                    str(VENDOR_DIR),
                    "--upgrade",
                ],
                check=True,
            )
        except Exception as exc:
            pip_exe = Path(sys.executable).with_name("pip.exe")
            if pip_exe.exists():
                try:
                    subprocess.run(
                        [
                            str(pip_exe),
                            "install",
                            "shapely",
                            "--target",
                            str(VENDOR_DIR),
                            "--upgrade",
                        ],
                        check=True,
                    )
                except Exception as pip_exc:
                    raise SystemExit(
                        "Khong tim thay thu vien 'shapely' va khong the tu dong cai dat.\n"
                        "Hay chay lenh sau roi thu lai:\n"
                        f'"{pip_exe}" install shapely'
                    ) from pip_exc
            else:
                raise SystemExit(
                    "Khong tim thay thu vien 'shapely' va khong the tu dong cai dat."
                ) from exc

        try:
            (
                GeometryCollection,
                MultiPolygon,
                Polygon,
                mapping,
                shape,
                unary_union,
                explain_validity,
                make_valid,
            ) = try_import_shapely()
            return
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "Da thu cai 'shapely' nhung van khong import duoc.\n"
                f"Hay kiem tra thu muc vendor: {VENDOR_DIR}"
            ) from exc


def is_geometry_invalid(geometry):
    ensure_shapely_available()
    try:
        geom = shape(geometry)
        if not geom.is_valid:
            return True, explain_validity(geom)
        return False, ""
    except Exception as exc:
        return True, str(exc)


def extract_polygon_only(geom):
    ensure_shapely_available()
    if geom.is_empty:
        return None

    if isinstance(geom, (Polygon, MultiPolygon)):
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
            sub_geom
            for sub_geom in geom.geoms
            if isinstance(sub_geom, (Polygon, MultiPolygon)) and not sub_geom.is_empty
        ]
        if not polygon_parts:
            return None

        merged = unary_union(polygon_parts)
        if isinstance(merged, (Polygon, MultiPolygon)) and not merged.is_empty:
            return merged

    return None


def has_minimum_polygon_points(geom):
    ensure_shapely_available()
    if geom is None or geom.is_empty:
        return False

    if isinstance(geom, Polygon):
        return len(list(geom.exterior.coords)) - 1 >= 3

    if isinstance(geom, MultiPolygon):
        valid_polygons = [
            polygon for polygon in geom.geoms if len(list(polygon.exterior.coords)) - 1 >= 3
        ]
        return len(valid_polygons) > 0

    return False


def filter_polygon_by_points(geom):
    ensure_shapely_available()
    if geom is None or geom.is_empty:
        return None

    if isinstance(geom, Polygon):
        return geom if has_minimum_polygon_points(geom) else None

    if isinstance(geom, MultiPolygon):
        valid_polygons = [polygon for polygon in geom.geoms if has_minimum_polygon_points(polygon)]
        if not valid_polygons:
            return None
        if len(valid_polygons) == 1:
            return valid_polygons[0]
        return MultiPolygon(valid_polygons)

    return None


def check_geojson(data):
    issues = []
    for index, feature in enumerate(data.get("features", [])):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        invalid, reason = is_geometry_invalid(geometry)
        if invalid:
            issues.append((index, geometry.get("type"), reason))
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
            "Thieu thu vien geopandas, chua the xuat shapefile zip."
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

    safe_name = Path(base_name).stem.replace(" ", "_") or "fixed_geometry"

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


def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_geojson(data, output_path):
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def extract_geojson_from_zip(zip_path, temp_root):
    extracted_files = []
    target_dir = temp_root / zip_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        for member in zip_file.infolist():
            member_path = Path(member.filename)
            if member.is_dir() or member_path.suffix.lower() != ".geojson":
                continue

            safe_name = member_path.name
            output_path = target_dir / safe_name

            suffix = 1
            while output_path.exists():
                output_path = target_dir / f"{member_path.stem}_{suffix}{member_path.suffix}"
                suffix += 1

            with zip_file.open(member) as source, open(output_path, "wb") as target:
                target.write(source.read())

            extracted_files.append(output_path)

    return extracted_files


def resolve_input_files(inputs, temp_root):
    files = []
    for input_value in inputs:
        path = Path(input_value)
        if not path.exists():
            print(f"[SKIP] Khong tim thay: {path}")
            continue

        if path.is_dir():
            files.extend(sorted(path.glob("*.geojson")))
        elif path.suffix.lower() == ".geojson":
            files.append(path)
        elif path.suffix.lower() == ".zip":
            try:
                zip_files = extract_geojson_from_zip(path, temp_root)
                if zip_files:
                    files.extend(zip_files)
                else:
                    print(f"[SKIP] File zip khong chua .geojson: {path}")
            except Exception as exc:
                print(f"[SKIP] Khong doc duoc file zip {path}: {exc}")
        else:
            print(f"[SKIP] Chi ho tro .geojson, folder, hoac .zip: {path}")

    unique_files = []
    seen = set()
    for file in files:
        resolved = str(file.resolve())
        if resolved not in seen:
            unique_files.append(file)
            seen.add(resolved)
    return unique_files


def process_file(file_path, output_dir, export_shapefile):
    data = load_geojson(file_path)
    issues = check_geojson(data)

    print(f"\n=== {file_path.name} ===")
    if not issues:
        print("Khong phat hien loi geometry.")
        return

    print(f"Phat hien {len(issues)} feature loi:")
    for index, geometry_type, reason in issues:
        print(f"  - Feature {index} ({geometry_type}): {reason}")

    fixed_data, fixed_count, removed_count = fix_geojson(data)
    remaining_issues = check_geojson(fixed_data)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_geojson = output_dir / f"{file_path.stem}_fixed.geojson"
    save_geojson(fixed_data, output_geojson)

    print(f"Da fix: {fixed_count} feature")
    print(f"Da loai: {removed_count} feature khong con polygon hop le")
    print(f"Con loi: {len(remaining_issues)} feature")
    print(f"Da ghi file: {output_geojson}")

    if export_shapefile:
        try:
            shapefile_bytes = build_shapefile_zip(fixed_data, output_geojson.name)
            zip_path = output_dir / f"{file_path.stem}_fixed_shapefile.zip"
            with open(zip_path, "wb") as file:
                file.write(shapefile_bytes)
            print(f"Da ghi shapefile zip: {zip_path}")
        except Exception as exc:
            print(f"Khong xuat duoc shapefile zip: {exc}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Kiem tra va fix Polygon/MultiPolygon loi trong file GeoJSON."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Duong dan toi file .geojson hoac thu muc chua cac file .geojson.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="fixed_output",
        help="Thu muc luu file ket qua. Mac dinh: fixed_output",
    )
    parser.add_argument(
        "--export-shapefile",
        action="store_true",
        help="Xuat them shapefile zip neu da cai geopandas.",
    )
    return parser


def choose_inputs_by_dialog():
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        selected_files = filedialog.askopenfilenames(
            title="Chon file GeoJSON",
            filetypes=[("GeoJSON files", "*.geojson")],
        )
        if selected_files:
            return list(selected_files)

        selected_directory = filedialog.askdirectory(
            title="Neu khong chon file, hay chon thu muc chua GeoJSON",
        )
        if selected_directory:
            return [selected_directory]

        return []
    finally:
        root.destroy()


def main():
    parser = build_parser()
    args = parser.parse_args()

    input_sources = args.inputs
    if not input_sources:
        input_sources = choose_inputs_by_dialog()
        if not input_sources:
            print("Ban chua chon file hoac thu muc nao.")
            return 1

    output_dir = Path(args.output_dir)

    with tempfile.TemporaryDirectory(prefix="geojson_input_") as temp_dir:
        input_files = resolve_input_files(input_sources, Path(temp_dir))
        if not input_files:
            print("Khong co file .geojson hop le de xu ly.")
            return 1

        print(f"Tim thay {len(input_files)} file GeoJSON can xu ly.")

        for file_path in input_files:
            try:
                process_file(file_path, output_dir, args.export_shapefile)
            except Exception as exc:
                print(f"\n=== {file_path.name} ===")
                print(f"Khong xu ly duoc file: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
