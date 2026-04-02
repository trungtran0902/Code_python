from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

import numpy as np
from openpyxl import Workbook
from PIL import Image, ImageDraw


ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
OUTPUT_DIRNAME = "output_bien_bao_cam"

# Seed metadata from the Vietnam traffic sign catalog on Wikipedia.
PROHIBITION_SIGNS = {
    "P.101": "Duong cam",
    "P.102": "Cam di nguoc chieu",
    "P.103a": "Cam xe o to",
    "P.103b": "Cam xe o to re phai",
    "P.103c": "Cam xe o to re trai",
    "P.104": "Cam xe may",
    "P.105": "Cam xe o to va xe may",
    "P.106a": "Cam xe o to tai",
    "P.106b": "Cam xe o to tai co khoi luong chuyen cho tren muc quy dinh",
    "P.106c": "Cam cac xe cho hang nguy hiem",
    "P.107": "Cam xe o to khach va xe o to tai",
    "P.107a": "Cam xe o to khach",
    "P.107b": "Cam xe o to taxi",
    "P.108": "Cam xe keo ro mooc",
    "P.108a": "Cam xe so mi ro mooc",
    "P.109": "Cam may keo",
    "P.110a": "Cam xe dap",
    "P.110b": "Cam xe dap tho so",
    "P.111a": "Cam xe gan may",
    "P.111b": "Cam xe ba banh loai co dong co",
    "P.111c": "Cam xe ba banh loai co dong co hinh xe xich lo may",
    "P.111d": "Cam xe ba banh loai khong co dong co",
    "P.112": "Cam nguoi di bo",
    "P.113": "Cam xe nguoi keo day",
    "P.114": "Cam xe vat nuoi keo",
    "P.115": "Han che trong tai toan bo xe",
    "P.116": "Han che tai trong tren truc xe",
    "P.117": "Han che chieu cao",
    "P.118": "Han che chieu ngang",
    "P.119": "Han che chieu dai xe",
    "P.120": "Han che chieu dai xe co gioi keo theo ro mooc hoac so mi ro mooc",
    "P.121": "Cu ly toi thieu giua hai xe",
    "P.123a": "Cam re trai",
    "P.123b": "Cam re phai",
    "P.124a1": "Cam quay dau xe duoc re trai",
    "P.124a2": "Cam quay dau xe duoc re phai",
    "P.124b1": "Cam o to quay dau xe duoc re trai",
    "P.124b2": "Cam o to quay dau xe duoc re phai",
    "P.124c": "Cam re trai va quay dau xe",
    "P.124d": "Cam re phai va quay dau xe",
    "P.124e": "Cam o to re trai va quay dau xe",
    "P.124f": "Cam o to re phai va quay dau xe",
    "P.125": "Cam vuot",
    "P.126": "Cam xe o to tai vuot",
    "P.127": "Toc do toi da cho phep",
    "P.127a": "Toc do toi da cho phep ve ban dem",
    "P.127b": "Gioi han toc do theo lan duong",
    "P.127c": "Gioi han toc do theo phuong tien tren tung lan duong",
    "DP.127a": "Het han che toc do toi da cho phep theo phuong tien tren tung lan duong",
    "DP.127b": "Het han che toc do toi da cho phep theo lan duong",
    "DP.127c": "Het han che toc do toi da cho phep theo phuong tien tren tung lan duong",
    "P.128": "Cam su dung coi",
    "P.129": "Kiem tra",
    "P.130": "Cam dung xe va do xe",
    "P.131a": "Cam do xe",
    "P.131b": "Cam do xe ngay le",
    "P.131c": "Cam do xe ngay chan",
    "P.132": "Nhuong duong cho xe co gioi di nguoc chieu qua duong hep",
    "DP.133": "Het cam vuot",
    "DP.134": "Het han che toc do toi da",
    "DP.135": "Het tat ca cac lenh cam",
    "P.136": "Cam di thang",
    "P.137": "Cam re trai va re phai",
    "P.138": "Cam di thang va re trai",
    "P.139": "Cam di thang va re phai",
    "P.140": "Cam xe cong nong va cac loai xe tuong tu",
}


@dataclass
class DetectionResult:
    code: str
    name: str
    confidence: float
    note: str


def ask_for_input_dir() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Chon thu muc chua anh bien bao can nhan dang",
            mustexist=True,
        )
        if not selected:
            return None
        return Path(selected)
    finally:
        root.destroy()


def collect_images(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in ALLOWED_SUFFIXES
        and OUTPUT_DIRNAME.lower() not in {part.lower() for part in path.parts}
    )


def image_to_array(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("RGB"))


def build_red_mask(arr: np.ndarray) -> np.ndarray:
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (r > 140) & (r > g + 40) & (r > b + 40)


def build_dark_mask(arr: np.ndarray) -> np.ndarray:
    gray = arr.mean(axis=2)
    return gray < 100


def extract_sign_roi(arr: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    candidates = extract_sign_candidates(arr)
    if not candidates:
        return None
    best_bbox = candidates[0]
    x0, y0, x1, y1 = best_bbox
    return arr[y0:y1, x0:x1].copy(), best_bbox


def extract_sign_candidates(arr: np.ndarray) -> list[tuple[int, int, int, int]]:
    red_mask = build_red_mask(arr)
    height, width = red_mask.shape
    visited = np.zeros_like(red_mask, dtype=bool)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []

    for y in range(height):
        for x in range(width):
            if not red_mask[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            points: list[tuple[int, int]] = []

            while stack:
                cy, cx = stack.pop()
                points.append((cy, cx))
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if not visited[ny, nx] and red_mask[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))

            if len(points) < 40:
                continue

            ys = [p[0] for p in points]
            xs = [p[1] for p in points]
            y0, y1 = min(ys), max(ys)
            x0, x1 = min(xs), max(xs)
            box_w = x1 - x0 + 1
            box_h = y1 - y0 + 1
            if box_w < 12 or box_h < 12:
                continue

            ratio = min(box_w, box_h) / max(box_w, box_h)
            if ratio < 0.55:
                continue

            area = len(points)
            box_area = box_w * box_h
            fill_ratio = area / max(1, box_area)
            if fill_ratio < 0.12:
                continue

            pad_y = max(6, int(box_h * 0.25))
            pad_x = max(6, int(box_w * 0.25))
            bx0 = max(0, x0 - pad_x)
            by0 = max(0, y0 - pad_y)
            bx1 = min(width, x1 + pad_x + 1)
            by1 = min(height, y1 + pad_y + 1)

            score = ratio * 2.0 + min(1.0, fill_ratio * 2.5) + min(1.0, area / 800.0)
            candidates.append((score, (bx0, by0, bx1, by1)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [bbox for _, bbox in candidates[:12]]


def resize_square(arr: np.ndarray, size: int = 256) -> np.ndarray:
    image = Image.fromarray(arr)
    return np.array(image.resize((size, size), Image.Resampling.LANCZOS))


def mask_circle(size: int = 256, radius_ratio: float = 0.44) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size]
    cx = cy = size / 2.0
    radius = size * radius_ratio
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return dist <= radius


def circular_content_masks(roi: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    square = resize_square(roi)
    red_mask = build_red_mask(square)
    dark_mask = build_dark_mask(square)
    circle_mask = mask_circle(square.shape[0])
    content_mask = dark_mask & circle_mask
    return square, red_mask & circle_mask, content_mask


def build_blue_mask(arr: np.ndarray) -> np.ndarray:
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (b > 100) & (b > r + 20) & (b > g + 10)


def has_prohibition_slash(red_mask: np.ndarray) -> bool:
    size = red_mask.shape[0]
    band = np.zeros_like(red_mask, dtype=bool)
    for offset in range(-18, 19):
        yy = np.arange(size)
        xx = (size - 1 - yy) + offset
        valid = (xx >= 0) & (xx < size)
        band[yy[valid], xx[valid]] = True
    return float((red_mask & band).sum()) / max(1, float(band.sum())) > 0.16


def slash_strength(red_mask: np.ndarray, direction: str) -> float:
    size = red_mask.shape[0]
    band = np.zeros_like(red_mask, dtype=bool)
    for offset in range(-18, 19):
        yy = np.arange(size)
        if direction == "descending":
            xx = (size - 1 - yy) + offset
        else:
            xx = yy + offset
        valid = (xx >= 0) & (xx < size)
        band[yy[valid], xx[valid]] = True
    return float((red_mask & band).sum()) / max(1, float(band.sum()))


def detect_arrow_direction(content_mask: np.ndarray) -> str | None:
    top = content_mask[: int(content_mask.shape[0] * 0.55), :]
    col_sum = top.sum(axis=0)
    row_sum = top.sum(axis=1)
    if col_sum.max() < 8 or row_sum.max() < 8:
        return None

    left_strength = float(col_sum[int(len(col_sum) * 0.58) :].sum())
    right_strength = float(col_sum[: int(len(col_sum) * 0.42)].sum())
    center_strength = float(col_sum[int(len(col_sum) * 0.35) : int(len(col_sum) * 0.65)].sum())

    left_peak = int(np.argmax(col_sum[: int(len(col_sum) * 0.45)]))
    right_peak = int(np.argmax(col_sum[int(len(col_sum) * 0.55) :])) + int(len(col_sum) * 0.55)
    vertical_peak = int(np.argmax(col_sum))

    if right_peak > vertical_peak and left_strength > center_strength * 0.75:
        return "right"
    if left_peak < vertical_peak and right_strength > center_strength * 0.75:
        return "left"
    return None


def detect_turn_only_arrow(content_mask: np.ndarray) -> str | None:
    h, w = content_mask.shape
    top = content_mask[: int(h * 0.68), :]
    if top.sum() < 120:
        return None

    left_half = top[:, : int(w * 0.45)]
    right_half = top[:, int(w * 0.55) :]
    center = top[:, int(w * 0.42) : int(w * 0.58)]

    left_mass = int(left_half.sum())
    right_mass = int(right_half.sum())
    center_mass = int(center.sum())

    if center_mass < 20:
        return None
    # In the normalized mask, the arrow head contributes more mass
    # on the same side it points to.
    if right_mass > left_mass * 1.20:
        return "right"
    if left_mass > right_mass * 1.20:
        return "left"
    return None


def detect_car_icon(content_mask: np.ndarray) -> bool:
    h, w = content_mask.shape
    bottom = content_mask[int(h * 0.50) : int(h * 0.88), int(w * 0.22) : int(w * 0.78)]
    if bottom.size == 0:
        return False
    density = float(bottom.sum()) / float(bottom.size)
    center_band = bottom[:, int(bottom.shape[1] * 0.15) : int(bottom.shape[1] * 0.85)]
    lower_band = bottom[int(bottom.shape[0] * 0.35) :, :]
    side_band = (
        bottom[:, : int(bottom.shape[1] * 0.18)].sum()
        + bottom[:, int(bottom.shape[1] * 0.82) :].sum()
    )
    return (
        density > 0.05
        and center_band.sum() > 90
        and lower_band.sum() > 70
        and side_band > 20
    )


def detect_circle_balance(red_mask: np.ndarray) -> float:
    ys, xs = np.argwhere(red_mask).T
    if len(xs) == 0:
        return 0.0
    width = xs.max() - xs.min() + 1
    height = ys.max() - ys.min() + 1
    ratio = min(width, height) / max(width, height)
    return float(ratio)


def detect_blue_parking_face(square: np.ndarray) -> float:
    blue_mask = build_blue_mask(square)
    circle = mask_circle(square.shape[0], radius_ratio=0.34)
    blue_inner = blue_mask & circle
    return float(blue_inner.sum()) / max(1.0, float(circle.sum()))


def classify_prohibition_sign(roi: np.ndarray) -> DetectionResult:
    square, red_mask, content_mask = circular_content_masks(roi)
    circle_balance = detect_circle_balance(red_mask)
    desc_slash = slash_strength(red_mask, "descending")
    asc_slash = slash_strength(red_mask, "ascending")
    slash = desc_slash > 0.16
    arrow_direction = detect_arrow_direction(content_mask)
    turn_only_arrow = detect_turn_only_arrow(content_mask)
    car_icon = detect_car_icon(content_mask)
    blue_face = detect_blue_parking_face(square)

    confidence = 0.25 + 0.25 * circle_balance + (0.2 if slash else 0.0) + (0.15 if car_icon else 0.0)
    notes = [
        f"circle_balance={circle_balance:.2f}",
        f"slash_desc={desc_slash:.2f}",
        f"slash_asc={asc_slash:.2f}",
        f"arrow={arrow_direction or 'none'}",
        f"turn_arrow={turn_only_arrow or 'none'}",
        f"car={'yes' if car_icon else 'no'}",
        f"blue_face={blue_face:.2f}",
    ]

    if blue_face > 0.04 and desc_slash > 0.12 and asc_slash > 0.12:
        return DetectionResult("P.130", PROHIBITION_SIGNS["P.130"], min(0.97, 0.52 + blue_face + desc_slash + asc_slash), "; ".join(notes))
    if blue_face > 0.04 and desc_slash > 0.14:
        return DetectionResult("P.131a", PROHIBITION_SIGNS["P.131a"], min(0.95, 0.48 + blue_face + desc_slash), "; ".join(notes))

    # Camera perspective and the prohibition slash often invert the simple
    # left/right mass heuristic on real-world photos, so map using observed behavior.
    if slash and not car_icon and turn_only_arrow == "left":
        return DetectionResult("P.123b", PROHIBITION_SIGNS["P.123b"], min(0.93, 0.46 + circle_balance + desc_slash), "; ".join(notes))
    if slash and not car_icon and turn_only_arrow == "right":
        return DetectionResult("P.123a", PROHIBITION_SIGNS["P.123a"], min(0.93, 0.46 + circle_balance + desc_slash), "; ".join(notes))

    if slash and car_icon and blue_face < 0.03 and arrow_direction == "right":
        return DetectionResult("P.103b", PROHIBITION_SIGNS["P.103b"], min(0.96, confidence + 0.18), "; ".join(notes))
    if slash and car_icon and blue_face < 0.03 and arrow_direction == "left":
        return DetectionResult("P.103c", PROHIBITION_SIGNS["P.103c"], min(0.96, confidence + 0.18), "; ".join(notes))
    if slash and car_icon and blue_face < 0.03:
        return DetectionResult("P.103a", PROHIBITION_SIGNS["P.103a"], min(0.84, confidence + 0.08), "; ".join(notes))

    return DetectionResult(
        "UNKNOWN_PROHIBITION",
        "Chua nhan dang duoc chinh xac trong nhom bien cam ho tro",
        max(0.15, min(0.72, confidence)),
        "; ".join(notes),
    )


def annotate_roi(image_path: Path, arr: np.ndarray, bbox: tuple[int, int, int, int], output_dir: Path) -> None:
    debug_dir = output_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(arr)
    draw = ImageDraw.Draw(image)
    draw.rectangle(bbox, outline="red", width=4)
    image.save(debug_dir / image_path.name)


def save_results(results: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "bien_bao_cam_results.json"
    excel_path = output_dir / "bien_bao_cam_results.xlsx"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BienBaoCam"
    headers = [
        "file_name",
        "file_path",
        "ma_bien",
        "ten_bien",
        "do_tin_cay",
        "ghi_chu",
    ]
    sheet.append(headers)
    for row in results:
        sheet.append([row.get(header, "") for header in headers])
    workbook.save(excel_path)
    return json_path, excel_path


def process_image(image_path: Path, output_dir: Path) -> dict[str, str]:
    arr = image_to_array(Image.open(image_path))
    candidate_bboxes = extract_sign_candidates(arr)
    if not candidate_bboxes:
        return {
            "file_name": image_path.name,
            "file_path": str(image_path),
            "ma_bien": "NOT_FOUND",
            "ten_bien": "Khong tim thay bien bao cam ro rang",
            "do_tin_cay": "0.00",
            "ghi_chu": "Khong tim thay cum mau do dang tron du lon",
        }

    best_detection: DetectionResult | None = None
    best_bbox: tuple[int, int, int, int] | None = None
    best_rank = -1.0
    for bbox in candidate_bboxes:
        x0, y0, x1, y1 = bbox
        roi = arr[y0:y1, x0:x1].copy()
        detection = classify_prohibition_sign(roi)
        rank = detection.confidence
        if detection.code != "UNKNOWN_PROHIBITION":
            rank += 0.25
        if rank > best_rank:
            best_rank = rank
            best_detection = detection
            best_bbox = bbox

    assert best_detection is not None and best_bbox is not None
    annotate_roi(image_path, arr, best_bbox, output_dir)
    return {
        "file_name": image_path.name,
        "file_path": str(image_path),
        "ma_bien": best_detection.code,
        "ten_bien": best_detection.name,
        "do_tin_cay": f"{best_detection.confidence:.2f}",
        "ghi_chu": best_detection.note,
    }


def main() -> None:
    input_dir = ask_for_input_dir()
    if input_dir is None:
        print("Da huy thao tac.")
        return

    image_paths = collect_images(input_dir)
    if not image_paths:
        messagebox.showwarning("Khong co anh", "Khong tim thay anh hop le trong thu muc da chon.")
        print("Khong tim thay anh hop le trong thu muc da chon.")
        return

    output_dir = input_dir / OUTPUT_DIRNAME
    results: list[dict[str, str]] = []
    failures: list[str] = []

    print(f"Thu muc input: {input_dir}")
    print(f"So file anh: {len(image_paths)}")
    for image_path in image_paths:
        print(f"\nDang nhan dang: {image_path}")
        try:
            result = process_image(image_path, output_dir)
            results.append(result)
            print(f"  - Ma bien: {result['ma_bien']}")
            print(f"  - Ten bien: {result['ten_bien']}")
            print(f"  - Do tin cay: {result['do_tin_cay']}")
        except Exception as exc:
            failures.append(f"{image_path} | {exc}")
            print(f"  - Loi: {exc}")

    json_path, excel_path = save_results(results, output_dir)
    if failures:
        failed_path = output_dir / "failed_images.txt"
        failed_path.write_text("\n".join(failures), encoding="utf-8")
        print(f"\nDa ghi log loi: {failed_path}")

    print("\n================ HOAN TAT ================")
    print(f"So file anh: {len(image_paths)}")
    print(f"So file xu ly thanh cong: {len(results)}")
    print(f"So file loi: {len(failures)}")
    print(f"Excel: {excel_path}")
    print(f"JSON: {json_path}")
    print("==========================================")


if __name__ == "__main__":
    main()
