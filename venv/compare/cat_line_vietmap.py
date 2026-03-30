from __future__ import annotations

import re
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString


NAME_FIELDS = [
    "name",
    "Name",
    "NAME",
    "ten",
    "TEN",
    "ten_tinh",
    "TEN_TINH",
    "tinh",
    "TINH",
    "province",
    "PROVINCE",
    "province_name",
    "PROVINCE_NAME",
    "prov_name",
    "NAME_1",
]


def slugify_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", value).strip()
    value = re.sub(r"\s+", "_", value)
    return value or "province"


def union_all_geometries(series):
    if hasattr(series, "union_all"):
        return series.union_all()
    return series.unary_union


def ask_for_inputs() -> tuple[Path, list[Path], Path] | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        line_file = filedialog.askopenfilename(
            title="Chon file duong dang GeoJSON",
            filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")],
        )
        if not line_file:
            return None

        polygon_files = filedialog.askopenfilenames(
            title="Chon cac file polygon ranh gioi tinh",
            filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")],
        )
        if not polygon_files:
            return None

        default_output = str(Path(line_file).with_name(f"{Path(line_file).stem}_by_province"))
        output_dir = filedialog.askdirectory(
            title="Chon thu muc output",
            mustexist=False,
            initialdir=default_output,
        )
        if not output_dir:
            return None

        return Path(line_file), [Path(path) for path in polygon_files], Path(output_dir)
    finally:
        root.destroy()


def detect_province_name(polygon_gdf: gpd.GeoDataFrame, fallback: str) -> str:
    for field in NAME_FIELDS:
        if field in polygon_gdf.columns:
            values = polygon_gdf[field].dropna().astype(str).str.strip()
            values = values[values != ""]
            if not values.empty:
                return values.iloc[0]
    return fallback


def load_line_data(line_path: Path) -> gpd.GeoDataFrame:
    lines_gdf = gpd.read_file(line_path)
    if lines_gdf.empty:
        raise ValueError("File duong khong co feature nao.")

    lines_gdf = lines_gdf[lines_gdf.geometry.notna()].copy()
    geom_types = lines_gdf.geometry.geom_type
    lines_gdf = lines_gdf[geom_types.isin(["LineString", "MultiLineString"])].copy()

    if lines_gdf.empty:
        raise ValueError("Khong tim thay geometry LineString/MultiLineString trong file duong.")

    if lines_gdf.crs is None:
        lines_gdf = lines_gdf.set_crs("EPSG:4326")

    return lines_gdf


def clip_lines_to_polygon(
    lines_gdf: gpd.GeoDataFrame,
    polygon_geom,
    province_name: str,
) -> gpd.GeoDataFrame:
    sindex = lines_gdf.sindex
    candidate_idx = list(sindex.intersection(polygon_geom.bounds))
    if not candidate_idx:
        return gpd.GeoDataFrame(columns=lines_gdf.columns, geometry=[], crs=lines_gdf.crs)

    candidates = lines_gdf.iloc[candidate_idx].copy()
    candidates = candidates[candidates.intersects(polygon_geom)].copy()
    if candidates.empty:
        return gpd.GeoDataFrame(columns=lines_gdf.columns, geometry=[], crs=lines_gdf.crs)

    candidates["geometry"] = candidates.geometry.intersection(polygon_geom)
    candidates = candidates[candidates.geometry.notna()].copy()
    candidates = candidates[~candidates.geometry.is_empty].copy()

    if candidates.empty:
        return gpd.GeoDataFrame(columns=lines_gdf.columns, geometry=[], crs=lines_gdf.crs)

    candidates = candidates.explode(index_parts=False, ignore_index=True)
    candidates = candidates[candidates.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()

    if candidates.empty:
        return gpd.GeoDataFrame(columns=lines_gdf.columns, geometry=[], crs=lines_gdf.crs)

    multiline_mask = candidates.geometry.geom_type == "MultiLineString"
    if multiline_mask.any():
        expanded_rows = []
        for _, row in candidates.iterrows():
            geom = row.geometry
            if isinstance(geom, MultiLineString):
                for part in geom.geoms:
                    new_row = row.copy()
                    new_row.geometry = LineString(part.coords)
                    expanded_rows.append(new_row)
            else:
                expanded_rows.append(row)
        candidates = gpd.GeoDataFrame(expanded_rows, geometry="geometry", crs=lines_gdf.crs)

    candidates["province_name"] = province_name
    return candidates.reset_index(drop=True)


def process_files(line_path: Path, polygon_paths: list[Path], output_dir: Path) -> tuple[list[Path], int]:
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Doc line file: {line_path}")
    lines_gdf = load_line_data(line_path)
    print(f"So line features hop le: {len(lines_gdf):,}")

    exported_files: list[Path] = []
    skipped_count = 0

    for polygon_path in polygon_paths:
        print(f"\nDang xu ly polygon: {polygon_path}")
        polygon_gdf = gpd.read_file(polygon_path)
        polygon_gdf = polygon_gdf[polygon_gdf.geometry.notna()].copy()
        polygon_gdf = polygon_gdf[
            polygon_gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
        ].copy()

        if polygon_gdf.empty:
            print("Bo qua: file polygon khong co Polygon/MultiPolygon.")
            skipped_count += 1
            continue

        if polygon_gdf.crs is None:
            polygon_gdf = polygon_gdf.set_crs("EPSG:4326")

        if polygon_gdf.crs != lines_gdf.crs:
            polygon_gdf = polygon_gdf.to_crs(lines_gdf.crs)

        province_name = detect_province_name(polygon_gdf, polygon_path.stem)
        province_geom = union_all_geometries(polygon_gdf.geometry)
        clipped_gdf = clip_lines_to_polygon(lines_gdf, province_geom, province_name)

        if clipped_gdf.empty:
            print(f"Khong co line nam trong {province_name}.")
            skipped_count += 1
            continue

        output_path = output_dir / f"{slugify_filename(province_name)}.geojson"
        clipped_gdf.to_file(output_path, driver="GeoJSON")
        exported_files.append(output_path)
        print(f"Da ghi {len(clipped_gdf):,} line vao: {output_path}")

    return exported_files, skipped_count


def main() -> None:
    selection = ask_for_inputs()
    if selection is None:
        print("Da huy thao tac.")
        return

    line_path, polygon_paths, output_dir = selection

    try:
        exported_files, skipped_count = process_files(line_path, polygon_paths, output_dir)
    except Exception as exc:
        messagebox.showerror("Loi", str(exc))
        raise

    print("\n================ HOAN TAT ================")
    print(f"Tong so polygon dau vao: {len(polygon_paths)}")
    print(f"So file GeoJSON da tao: {len(exported_files)}")
    print(f"So polygon khong co output: {skipped_count}")
    print(f"Thu muc output: {output_dir}")
    print("==========================================")


if __name__ == "__main__":
    main()
