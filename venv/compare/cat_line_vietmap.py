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


def ask_for_polygon_mode() -> str | None:
    answer = messagebox.askyesnocancel(
        "Chon kieu cat",
        "Yes = Cat theo tinh/thanh\n"
        "No = Cat theo phuong/xa (quet de quy theo thu muc con)\n"
        "Cancel = Huy",
    )
    if answer is None:
        return None
    return "tinh_thanh" if answer else "phuong_xa"


def collect_polygon_jobs(polygon_dir_path: Path, mode: str) -> list[tuple[Path, Path]]:
    if mode == "tinh_thanh":
        polygon_files = sorted(
            path
            for path in polygon_dir_path.iterdir()
            if path.is_file() and path.suffix.lower() in {".geojson", ".json"}
        )
        return [(path, Path(f"{path.stem}.geojson")) for path in polygon_files]

    polygon_files = sorted(
        path
        for path in polygon_dir_path.rglob("*")
        if path.is_file() and path.suffix.lower() in {".geojson", ".json"}
    )
    jobs: list[tuple[Path, Path]] = []
    for path in polygon_files:
        relative_parent = path.relative_to(polygon_dir_path).parent
        jobs.append((path, relative_parent / f"{path.stem}.geojson"))
    return jobs


def ask_for_inputs() -> tuple[Path, list[tuple[Path, Path]], Path] | None:
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

        polygon_mode = ask_for_polygon_mode()
        if polygon_mode is None:
            return None

        polygon_dir = filedialog.askdirectory(
            title=(
                "Chon thu muc chua cac file polygon ranh gioi tinh"
                if polygon_mode == "tinh_thanh"
                else "Chon thu muc cha XaPhuong de quet de quy cac file polygon"
            ),
            mustexist=True,
            initialdir=str(Path(line_file).parent),
        )
        if not polygon_dir:
            return None

        polygon_dir_path = Path(polygon_dir)
        polygon_jobs = collect_polygon_jobs(polygon_dir_path, polygon_mode)
        if not polygon_jobs:
            raise ValueError(f"Khong tim thay file GeoJSON/JSON nao trong thu muc: {polygon_dir_path}")

        default_output = str(Path(line_file).with_name(f"{Path(line_file).stem}_by_province"))
        output_dir = filedialog.askdirectory(
            title="Chon thu muc output",
            mustexist=False,
            initialdir=default_output,
        )
        if not output_dir:
            return None

        return Path(line_file), polygon_jobs, Path(output_dir)
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


def process_files(line_path: Path, polygon_jobs: list[tuple[Path, Path]], output_dir: Path) -> tuple[list[Path], int, list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Doc line file: {line_path}")
    lines_gdf = load_line_data(line_path)
    print(f"So line features hop le: {len(lines_gdf):,}")

    exported_files: list[Path] = []
    skipped_count = 0
    failed_items: list[str] = []

    for polygon_path, relative_output_path in polygon_jobs:
        print(f"\nDang xu ly polygon: {polygon_path}")
        try:
            print("  - Dang doc polygon...")
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
                print("  - Dang doi he toa do polygon...")
                polygon_gdf = polygon_gdf.to_crs(lines_gdf.crs)

            province_name = detect_province_name(polygon_gdf, polygon_path.stem)
            print("  - Dang union polygon...")
            province_geom = union_all_geometries(polygon_gdf.geometry)
            print("  - Dang clip line theo polygon...")
            clipped_gdf = clip_lines_to_polygon(lines_gdf, province_geom, province_name)

            if clipped_gdf.empty:
                print(f"Khong co line nam trong {province_name}.")
                skipped_count += 1
                continue

            output_path = output_dir / relative_output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            print("  - Dang ghi file output...")
            clipped_gdf.to_file(output_path, driver="GeoJSON")
            exported_files.append(output_path)
            print(f"Da ghi {len(clipped_gdf):,} line vao: {output_path}")
        except Exception as exc:
            error_message = f"{polygon_path} | {exc}"
            print(f"  - Loi, bo qua polygon nay: {exc}")
            failed_items.append(error_message)

    return exported_files, skipped_count, failed_items


def main() -> None:
    selection = ask_for_inputs()
    if selection is None:
        print("Da huy thao tac.")
        return

    line_path, polygon_jobs, output_dir = selection

    try:
        exported_files, skipped_count, failed_items = process_files(line_path, polygon_jobs, output_dir)
    except Exception as exc:
        messagebox.showerror("Loi", str(exc))
        raise

    if failed_items:
        failed_log_path = output_dir / "failed_polygons.txt"
        failed_log_path.write_text("\n".join(failed_items), encoding="utf-8")
        print(f"So polygon loi: {len(failed_items)}")
        print(f"Log loi: {failed_log_path}")

    print("\n================ HOAN TAT ================")
    print(f"Tong so polygon dau vao: {len(polygon_jobs)}")
    print(f"So file GeoJSON da tao: {len(exported_files)}")
    print(f"So polygon khong co output: {skipped_count}")
    print(f"Thu muc output: {output_dir}")
    print("==========================================")


if __name__ == "__main__":
    main()
