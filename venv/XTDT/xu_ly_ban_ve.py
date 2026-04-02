from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageColor, ImageDraw
from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import polygonize


DEFAULT_PDF = Path(r"G:\Lâm Đồng\Tài liệu KCN Phú Bình\BV-QH04.pdf")
DEFAULT_SCALE = 0.5
DEFAULT_SIMPLIFY = 4.0
DEFAULT_DILATION = 4
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output_ranh_quy_hoach"
DEFAULT_ANCHOR_LAT = 11.678926
DEFAULT_ANCHOR_LNG = 108.283167
DEFAULT_METERS_PER_POINT = 1.0


def render_pdf_page(pdf_path: Path, page_index: int, scale: float) -> tuple[np.ndarray, fitz.Page]:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
    return image, page


def safe_console(value: object) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def build_red_mask(image: np.ndarray) -> np.ndarray:
    red = image[:, :, 0].astype(np.int16)
    green = image[:, :, 1].astype(np.int16)
    blue = image[:, :, 2].astype(np.int16)
    dominant_other = np.maximum(green, blue)
    return (red > 145) & (green < 180) & (blue < 180) & ((red - dominant_other) > 25)


def dilate_mask(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(iterations):
        padded = np.pad(result, 1)
        result = (
            padded[:-2, :-2]
            | padded[:-2, 1:-1]
            | padded[:-2, 2:]
            | padded[1:-1, :-2]
            | padded[1:-1, 1:-1]
            | padded[1:-1, 2:]
            | padded[2:, :-2]
            | padded[2:, 1:-1]
            | padded[2:, 2:]
        )
    return result


def largest_component(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    visited = np.zeros((height, width), dtype=np.uint8)
    best_points: list[tuple[int, int]] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue

            queue = deque([(y, x)])
            visited[y, x] = 1
            current_points: list[tuple[int, int]] = []

            while queue:
                cy, cx = queue.popleft()
                current_points.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = 1
                        queue.append((ny, nx))

            if len(current_points) > len(best_points):
                best_points = current_points

    component = np.zeros_like(mask, dtype=bool)
    for y, x in best_points:
        component[y, x] = True
    return component


def fill_enclosed_region(boundary_mask: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    ys, xs = np.where(boundary_mask)
    if len(xs) == 0:
        raise ValueError("Khong tim thay component ranh do lon nhat.")

    min_y, max_y = int(ys.min()), int(ys.max())
    min_x, max_x = int(xs.min()), int(xs.max())

    sub_mask = boundary_mask[min_y : max_y + 1, min_x : max_x + 1]
    height, width = sub_mask.shape
    outside = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            if not sub_mask[y, x] and not outside[y, x]:
                outside[y, x] = True
                queue.append((y, x))

    for y in range(height):
        for x in (0, width - 1):
            if not sub_mask[y, x] and not outside[y, x]:
                outside[y, x] = True
                queue.append((y, x))

    while queue:
        cy, cx = queue.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < height and 0 <= nx < width and not sub_mask[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                queue.append((ny, nx))

    inside = ~outside & ~sub_mask
    return inside, (min_x, min_y, max_x, max_y)


def polygon_from_mask(inside_mask: np.ndarray, offset: tuple[int, int], scale: float, simplify: float) -> Polygon:
    min_x, min_y = offset
    table = {
        1: [((0, 0.5), (0.5, 1))],
        2: [((0.5, 1), (1, 0.5))],
        3: [((0, 0.5), (1, 0.5))],
        4: [((0.5, 0), (1, 0.5))],
        5: [((0.5, 0), (0, 0.5)), ((0.5, 1), (1, 0.5))],
        6: [((0.5, 0), (0.5, 1))],
        7: [((0.5, 0), (0, 0.5))],
        8: [((0.5, 0), (0, 0.5))],
        9: [((0.5, 0), (0.5, 1))],
        10: [((0.5, 0), (1, 0.5)), ((0, 0.5), (0.5, 1))],
        11: [((0.5, 0), (1, 0.5))],
        12: [((0, 0.5), (1, 0.5))],
        13: [((0.5, 1), (1, 0.5))],
        14: [((0, 0.5), (0.5, 1))],
    }

    height, width = inside_mask.shape
    segments: list[LineString] = []
    for y in range(height - 1):
        row_0 = inside_mask[y]
        row_1 = inside_mask[y + 1]
        for x in range(width - 1):
            idx = (int(row_0[x]) << 3) | (int(row_0[x + 1]) << 2) | (int(row_1[x + 1]) << 1) | int(row_1[x])
            if idx in (0, 15):
                continue

            for start, end in table[idx]:
                segments.append(
                    LineString(
                        [
                            ((x + start[0] + min_x) / scale, (y + start[1] + min_y) / scale),
                            ((x + end[0] + min_x) / scale, (y + end[1] + min_y) / scale),
                        ]
                    )
                )

    polygons = list(polygonize(segments))
    if not polygons:
        raise ValueError("Khong polygonize duoc ranh quy hoach.")

    polygon = max(polygons, key=lambda geom: geom.area)
    polygon = polygon.simplify(simplify, preserve_topology=True)
    if polygon.geom_type != "Polygon" or polygon.is_empty:
        raise ValueError("Polygon ket qua khong hop le sau simplify.")
    return polygon


def save_geojson(
    polygon: Polygon,
    output_path: Path,
    pdf_path: Path,
    page_width: float,
    page_height: float,
    coordinate_space: str,
    anchor_lat: float | None = None,
    anchor_lng: float | None = None,
    meters_per_point: float | None = None,
) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "source_pdf": str(pdf_path),
                    "coordinate_space": coordinate_space,
                    "page_width": page_width,
                    "page_height": page_height,
                    "anchor_lat": anchor_lat,
                    "anchor_lng": anchor_lng,
                    "meters_per_point": meters_per_point,
                },
                "geometry": mapping(polygon),
            }
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_preview(image: np.ndarray, polygon: Polygon, scale: float, output_path: Path) -> None:
    preview = Image.fromarray(image)
    draw = ImageDraw.Draw(preview, "RGBA")
    coords = [(x * scale, y * scale) for x, y in polygon.exterior.coords]
    draw.polygon(coords, fill=ImageColor.getrgb("#4da3ff") + (70,), outline="#005bd1", width=4)
    preview.save(output_path)


def approximate_georeference_polygon(
    polygon: Polygon,
    anchor_lat: float,
    anchor_lng: float,
    meters_per_point: float,
) -> Polygon:
    centroid = polygon.centroid
    cos_lat = math.cos(math.radians(anchor_lat))
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lng = max(1e-9, meters_per_degree_lat * cos_lat)

    transformed_coords = []
    for x, y in polygon.exterior.coords:
        dx_m = (x - centroid.x) * meters_per_point
        dy_m = (centroid.y - y) * meters_per_point
        lng = anchor_lng + (dx_m / meters_per_degree_lng)
        lat = anchor_lat + (dy_m / meters_per_degree_lat)
        transformed_coords.append((lng, lat))

    return Polygon(transformed_coords)


def extract_boundary(
    pdf_path: Path,
    page_index: int,
    scale: float,
    simplify: float,
    dilation: int,
    output_dir: Path,
    anchor_lat: float | None = None,
    anchor_lng: float | None = None,
    meters_per_point: float = DEFAULT_METERS_PER_POINT,
) -> dict:
    image, page = render_pdf_page(pdf_path, page_index=page_index, scale=scale)
    red_mask = build_red_mask(image)
    red_mask = dilate_mask(red_mask, iterations=dilation)
    boundary = largest_component(red_mask)
    filled_region, bbox = fill_enclosed_region(boundary)
    polygon = polygon_from_mask(filled_region, offset=(bbox[0], bbox[1]), scale=scale, simplify=simplify)

    output_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = output_dir / f"{pdf_path.stem}_ranh_quy_hoach.geojson"
    preview_path = output_dir / f"{pdf_path.stem}_ranh_quy_hoach_preview.png"
    approx_geojson_path = output_dir / f"{pdf_path.stem}_ranh_quy_hoach_anchor_approx.geojson"

    save_geojson(
        polygon,
        geojson_path,
        pdf_path=pdf_path,
        page_width=float(page.mediabox.width),
        page_height=float(page.mediabox.height),
        coordinate_space="pdf_page_points",
    )
    save_preview(image, polygon, scale=scale, output_path=preview_path)

    approx_polygon = None
    if anchor_lat is not None and anchor_lng is not None:
        approx_polygon = approximate_georeference_polygon(
            polygon,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
            meters_per_point=meters_per_point,
        )
        save_geojson(
            approx_polygon,
            approx_geojson_path,
            pdf_path=pdf_path,
            page_width=float(page.mediabox.width),
            page_height=float(page.mediabox.height),
            coordinate_space="EPSG:4326_approx_anchor",
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
            meters_per_point=meters_per_point,
        )

    return {
        "geojson_path": geojson_path,
        "approx_geojson_path": approx_geojson_path if approx_polygon is not None else None,
        "preview_path": preview_path,
        "vertex_count": len(polygon.exterior.coords),
        "page_width": float(page.mediabox.width),
        "page_height": float(page.mediabox.height),
        "polygon_area": float(polygon.area),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trich xuat ranh quy hoach tu ban ve PDF (uu tien ranh mau do)."
    )
    parser.add_argument("pdf_path", nargs="?", default=str(DEFAULT_PDF), help="Duong dan file PDF ban ve.")
    parser.add_argument("--page", type=int, default=0, help="Chi so trang PDF, mac dinh 0.")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE, help="Ti le render PDF.")
    parser.add_argument("--simplify", type=float, default=DEFAULT_SIMPLIFY, help="Do don gian hoa polygon.")
    parser.add_argument("--dilation", type=int, default=DEFAULT_DILATION, help="So lan noi mask ranh.")
    parser.add_argument("--anchor-lat", type=float, default=DEFAULT_ANCHOR_LAT, help="Vi do moc gan dung.")
    parser.add_argument("--anchor-lng", type=float, default=DEFAULT_ANCHOR_LNG, help="Kinh do moc gan dung.")
    parser.add_argument(
        "--meters-per-point",
        type=float,
        default=DEFAULT_METERS_PER_POINT,
        help="He so quy doi gan dung tu don vi PDF sang met.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Thu muc output. Mac dinh la thu muc output_ranh_quy_hoach canh script.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Khong tim thay file PDF: {pdf_path}")

    output_dir = Path(args.output_dir)
    result = extract_boundary(
        pdf_path=pdf_path,
        page_index=args.page,
        scale=args.scale,
        simplify=args.simplify,
        dilation=args.dilation,
        output_dir=output_dir,
        anchor_lat=args.anchor_lat,
        anchor_lng=args.anchor_lng,
        meters_per_point=args.meters_per_point,
    )

    print("================ HOAN TAT ================")
    print(f"PDF: {safe_console(pdf_path)}")
    print(f"GeoJSON: {safe_console(result['geojson_path'])}")
    if result["approx_geojson_path"] is not None:
        print(f"GeoJSON approx WGS84: {safe_console(result['approx_geojson_path'])}")
    print(f"Preview: {safe_console(result['preview_path'])}")
    print(f"So dinh polygon: {result['vertex_count']}")
    print(f"Dien tich polygon (pdf points^2): {result['polygon_area']:.2f}")
    print("Luu y: file approx WGS84 la gan dung theo 1 moc neo, chua phai georeference chuan.")
    print("==========================================")


if __name__ == "__main__":
    main()
