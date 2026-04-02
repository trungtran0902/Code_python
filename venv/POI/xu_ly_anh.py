from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

import numpy as np
from openpyxl import Workbook
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


OUTPUT_DIRNAME = "output_ocr_anh"
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
TESSERACT_CMD = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OCR_LANG = "vie+eng"
VIETNAM_LAT_RANGE = (8.0, 24.5)
VIETNAM_LNG_RANGE = (102.0, 110.5)
SAVE_DEBUG_CROPS = True


def ask_for_input_dir() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Chon thu muc chua cac file anh can OCR",
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
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES
    )


def get_tesseract() -> object:
    try:
        import pytesseract  # type: ignore

        if not TESSERACT_CMD.is_file():
            raise FileNotFoundError(f"Khong tim thay tesseract.exe tai: {TESSERACT_CMD}")
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)
        return pytesseract
    except Exception as exc:
        raise ModuleNotFoundError(
            "OCR chua san sang. Hay kiem tra pytesseract va Tesseract OCR.\n"
            f"Path mong doi: {TESSERACT_CMD}"
        ) from exc


def clean_text(value: str) -> str:
    value = value.replace("\x0c", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{2,}", "\n", value)
    return value.strip()


def clean_line(value: str) -> str:
    value = clean_text(value)
    value = value.strip(" -_,.;:")
    value = re.sub(r"\s+", " ", value)
    return value


def basic_normalize_text(value: str) -> str:
    for old, new in {
        "ï¼Œ": ",",
        "ã€‚": ".",
    }.items():
        value = value.replace(old, new)
    return value


def normalize_numeric_text(value: str) -> str:
    value = basic_normalize_text(value)
    for old, new in {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "|": "1",
    }.items():
        value = value.replace(old, new)
    return value


def extract_lines(text: str) -> list[str]:
    return [clean_line(line) for line in text.splitlines() if clean_line(line)]


def normalize_store_name(value: str) -> str:
    value = clean_line(value)
    value = re.sub(r"\s*&\s*", " & ", value)
    return value


def normalize_address_text(value: str) -> str:
    value = clean_line(basic_normalize_text(value))
    replacements = [
        (r"\bP\s*\.?\s*(\d+)\b", r"Phuong \1"),
        (r"\bQ\s*\.?\s*TB\b", "Quan Tan Binh"),
        (r"\bQ\s*\.?\s*(\d+)\b", r"Quan \1"),
        (r"\bTP\s*\.?\s*HCM\b", "TP. Ho Chi Minh"),
        (r"\bHCM\b", "Ho Chi Minh"),
        (r"\bWAN\b", "VAN"),
        (r"\bDT\b", "Dien thoai"),
    ]
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    value = re.sub(r"\s*,\s*", ", ", value)
    return clean_line(value)


def looks_like_phone_line(line: str) -> bool:
    lower = normalize_numeric_text(line).lower()
    digit_count = sum(char.isdigit() for char in lower)
    return "dien thoai" in lower or "dt" in lower or digit_count >= 9


def looks_like_address_line(line: str) -> bool:
    lower = normalize_address_text(line).lower()
    has_number = bool(re.search(r"\b\d{1,4}\b", lower))
    has_hint = any(
        keyword in lower
        for keyword in ("duong", "pham", "phuong", "quan", "tp", "hcm", "tan binh", "viet nam")
    )
    return has_number and has_hint


def extract_address_from_sign_text(sign_text: str) -> str:
    candidates: list[tuple[int, int, str]] = []
    for line in extract_lines(sign_text):
        normalized = normalize_address_text(line)
        upper = normalized.upper()
        score = 0
        if re.search(r"\b\d{1,4}\b", upper):
            score += 3
        if "PHUONG" in upper or re.search(r"\bP\s*\.?\s*\d+\b", upper):
            score += 3
        if "QUAN" in upper or re.search(r"\bQ\s*\.?\s*[A-Z0-9]+\b", upper):
            score += 2
        if "PHAM" in upper or "DUONG" in upper:
            score += 2
        if looks_like_phone_line(normalized):
            score -= 3
        if score > 0:
            candidates.append((score, len(normalized), normalized))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def guess_store_name(sign_text: str) -> str:
    lines = extract_lines(sign_text)
    if not lines:
        return ""
    name_lines: list[str] = []
    for line in lines:
        if looks_like_address_line(line) or looks_like_phone_line(line):
            break
        if len(re.sub(r"[^A-Za-zÀ-ỹ& ]", "", line)) < 2:
            continue
        name_lines.append(line)
        if len(name_lines) >= 3:
            break
    if not name_lines:
        filtered = [line for line in lines if not looks_like_phone_line(line)]
        if not filtered:
            return ""
        return normalize_store_name(max(filtered, key=len))
    return normalize_store_name(" ".join(name_lines))


def guess_address(text: str) -> str:
    scored: list[tuple[int, int, str]] = []
    for line in extract_lines(text):
        normalized = normalize_address_text(line)
        lower = normalized.lower()
        score = 0
        if looks_like_address_line(normalized):
            score += 4
        score += sum(
            keyword in lower
            for keyword in ("duong", "pham", "phuong", "quan", "tp", "tan binh", "viet nam")
        )
        if score:
            scored.append((score, len(normalized), normalized))
    if not scored:
        return ""
    scored.sort(reverse=True)
    return scored[0][2]


def upscale_image(image: Image.Image, scale: int = 2) -> Image.Image:
    width, height = image.size
    return image.resize((width * scale, height * scale), Image.Resampling.LANCZOS)


def preprocess_for_ocr(
    image: Image.Image,
    threshold: int | None = None,
    scale: int = 1,
) -> Image.Image:
    if scale > 1:
        image = upscale_image(image, scale=scale)
    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(2.3)
    gray = gray.filter(ImageFilter.SHARPEN)
    if threshold is not None:
        arr = np.array(gray)
        arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
        return Image.fromarray(arr)
    return gray


def preprocess_red_text(image: Image.Image, scale: int = 3) -> Image.Image:
    if scale > 1:
        image = upscale_image(image, scale=scale)
    arr = np.array(image.convert("RGB"))
    red_mask = (
        (arr[:, :, 0] > 110)
        & (arr[:, :, 0] > arr[:, :, 1] + 25)
        & (arr[:, :, 0] > arr[:, :, 2] + 25)
    )
    output = np.where(red_mask, 0, 255).astype(np.uint8)
    return Image.fromarray(output)


def preprocess_light_text(image: Image.Image, scale: int = 5, threshold: int = 165) -> Image.Image:
    if scale > 1:
        image = upscale_image(image, scale=scale)
    gray = np.array(ImageOps.grayscale(image))
    mask = np.where(gray >= threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(mask)


def crop_regions(image: Image.Image) -> dict[str, Image.Image]:
    width, height = image.size
    sign_full_box = (
        int(width * 0.10),
        int(height * 0.05),
        int(width * 0.83),
        int(height * 0.45),
    )
    sign_name_box = (
        int(width * 0.16),
        int(height * 0.06),
        int(width * 0.76),
        int(height * 0.33),
    )
    sign_addr_box = (
        int(width * 0.18),
        int(height * 0.33),
        int(width * 0.78),
        int(height * 0.43),
    )
    gps_overlay_box = (
        int(width * 0.18),
        int(height * 0.67),
        int(width * 0.95),
        int(height * 0.86),
    )
    latlng_box = (
        int(width * 0.18),
        int(height * 0.74),
        int(width * 0.94),
        int(height * 0.84),
    )
    return {
        "sign_full": image.crop(sign_full_box),
        "sign_name": image.crop(sign_name_box),
        "sign_addr": image.crop(sign_addr_box),
        "gps_overlay": image.crop(gps_overlay_box),
        "latlng": image.crop(latlng_box),
    }


def save_debug_crops(image_path: Path, regions: dict[str, Image.Image], output_dir: Path) -> None:
    if not SAVE_DEBUG_CROPS:
        return
    debug_dir = output_dir / "debug_crops" / image_path.stem
    debug_dir.mkdir(parents=True, exist_ok=True)
    for name, region in regions.items():
        region.save(debug_dir / f"{name}.png")


def run_ocr(pytesseract_module: object, image: Image.Image, psm: int, lang: str = OCR_LANG) -> str:
    config = f"--oem 3 --psm {psm}"
    text = pytesseract_module.image_to_string(image, lang=lang, config=config)
    return clean_text(text)


def run_latlng_ocr(pytesseract_module: object, image: Image.Image, psm: int) -> str:
    config = (
        f"--oem 3 --psm {psm} "
        "-c tessedit_char_whitelist=LatLongLongitudeLatitude0123456789.,:"
    )
    text = pytesseract_module.image_to_string(image, lang="eng", config=config)
    return clean_text(text)


def extract_lat_lng(text: str) -> tuple[str, str]:
    normalized = normalize_numeric_text(text)
    lat_match = re.search(
        r"(?:Lat|Latitude)\s*[:= ]\s*([+-]?\d{1,2}(?:[.,]\d+)?)",
        normalized,
        flags=re.IGNORECASE,
    )
    lng_match = re.search(
        r"(?:Long|Lng|Lon|Longitude)\s*[:= ]\s*([+-]?\d{1,3}(?:[.,]\d+)?)",
        normalized,
        flags=re.IGNORECASE,
    )
    lat = lat_match.group(1).replace(",", ".") if lat_match else ""
    lng = lng_match.group(1).replace(",", ".") if lng_match else ""
    if lat and lng:
        lat_value = float(lat)
        lng_value = float(lng)
        if VIETNAM_LAT_RANGE[0] <= lat_value <= VIETNAM_LAT_RANGE[1] and VIETNAM_LNG_RANGE[0] <= lng_value <= VIETNAM_LNG_RANGE[1]:
            return lat, lng
    decimal_pairs = re.findall(r"([+-]?\d{1,3}(?:[.,]\d{5,}))", normalized, flags=re.IGNORECASE)
    decimal_pairs = [value.replace(",", ".") for value in decimal_pairs]
    if len(decimal_pairs) >= 2:
        for idx in range(len(decimal_pairs) - 1):
            first = float(decimal_pairs[idx])
            second = float(decimal_pairs[idx + 1])
            if VIETNAM_LAT_RANGE[0] <= first <= VIETNAM_LAT_RANGE[1] and VIETNAM_LNG_RANGE[0] <= second <= VIETNAM_LNG_RANGE[1]:
                return decimal_pairs[idx], decimal_pairs[idx + 1]
    return "", ""


def process_image(
    image_path: Path,
    pytesseract_module: object,
    output_dir: Path,
) -> dict[str, str]:
    image = Image.open(image_path).convert("RGB")
    regions = crop_regions(image)
    save_debug_crops(image_path, regions, output_dir)

    sign_full_variants = [
        preprocess_for_ocr(regions["sign_full"], scale=2),
        preprocess_for_ocr(regions["sign_full"], threshold=170, scale=3),
        preprocess_for_ocr(regions["sign_full"], threshold=195, scale=4),
    ]
    sign_name_variants = [
        preprocess_red_text(regions["sign_name"], scale=3),
        preprocess_for_ocr(regions["sign_name"], threshold=170, scale=3),
        preprocess_for_ocr(regions["sign_name"], threshold=200, scale=4),
    ]
    sign_addr_variants = [
        preprocess_red_text(regions["sign_addr"], scale=4),
        preprocess_for_ocr(regions["sign_addr"], threshold=165, scale=4),
        preprocess_for_ocr(regions["sign_addr"], threshold=190, scale=5),
    ]
    latlng_variants = [
        preprocess_light_text(regions["latlng"], scale=6, threshold=145),
        preprocess_light_text(regions["latlng"], scale=6, threshold=165),
        preprocess_for_ocr(regions["latlng"], threshold=160, scale=6),
        preprocess_light_text(regions["gps_overlay"], scale=4, threshold=150),
        preprocess_for_ocr(regions["gps_overlay"], threshold=170, scale=4),
    ]

    sign_full_text_parts: list[str] = []
    for variant in sign_full_variants:
        sign_full_text_parts.append(run_ocr(pytesseract_module, variant, psm=4))
        sign_full_text_parts.append(run_ocr(pytesseract_module, variant, psm=6))
        sign_full_text_parts.append(run_ocr(pytesseract_module, variant, psm=11))
    sign_full_text = clean_text("\n".join(part for part in sign_full_text_parts if part))

    sign_name_text_parts: list[str] = []
    for variant in sign_name_variants:
        sign_name_text_parts.append(run_ocr(pytesseract_module, variant, psm=6))
        sign_name_text_parts.append(run_ocr(pytesseract_module, variant, psm=11))
    sign_name_text = clean_text("\n".join(part for part in sign_name_text_parts if part))

    sign_addr_text_parts: list[str] = []
    for variant in sign_addr_variants:
        sign_addr_text_parts.append(run_ocr(pytesseract_module, variant, psm=6))
        sign_addr_text_parts.append(run_ocr(pytesseract_module, variant, psm=11))
    sign_addr_text = clean_text("\n".join(part for part in sign_addr_text_parts if part))

    latlng_text_parts: list[str] = []
    for variant in latlng_variants:
        latlng_text_parts.append(run_latlng_ocr(pytesseract_module, variant, psm=7))
        latlng_text_parts.append(run_latlng_ocr(pytesseract_module, variant, psm=6))
        latlng_text_parts.append(run_latlng_ocr(pytesseract_module, variant, psm=13))
    gps_text = clean_text("\n".join(part for part in latlng_text_parts if part))

    lat, lng = extract_lat_lng(gps_text)
    sign_text = clean_text("\n".join(part for part in [sign_name_text, sign_addr_text, sign_full_text] if part))
    address_guess = (
        extract_address_from_sign_text(sign_addr_text)
        or extract_address_from_sign_text(sign_full_text)
        or guess_address(sign_addr_text)
        or guess_address(sign_full_text)
    )
    combined_text = clean_text("\n".join(part for part in [sign_text, gps_text] if part))
    store_name = guess_store_name(clean_text("\n".join(part for part in [sign_name_text, sign_full_text] if part)))

    return {
        "file_name": image_path.name,
        "file_path": str(image_path),
        "store_name": store_name,
        "address_guess": address_guess,
        "lat": lat,
        "lng": lng,
        "sign_text": sign_text,
        "gps_text": gps_text,
        "combined_text": combined_text,
    }


def save_results(results: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ocr_results.json"
    csv_path = output_dir / "ocr_results.csv"
    excel_path = output_dir / "ocr_results.xlsx"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "file_name",
        "file_path",
        "store_name",
        "address_guess",
        "lat",
        "lng",
        "sign_text",
        "gps_text",
        "combined_text",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "OCR_Results"
    sheet.append(fieldnames)
    for row in results:
        sheet.append([row.get(field, "") for field in fieldnames])
    workbook.save(excel_path)

    return json_path, csv_path, excel_path


def main() -> None:
    try:
        pytesseract_module = get_tesseract()
    except ModuleNotFoundError as exc:
        print(exc)
        messagebox.showerror("Thieu OCR", str(exc))
        return

    input_dir = ask_for_input_dir()
    if input_dir is None:
        print("Da huy thao tac.")
        return

    image_paths = collect_images(input_dir)
    if not image_paths:
        print("Khong tim thay file anh hop le trong thu muc da chon.")
        return

    output_dir = input_dir / OUTPUT_DIRNAME
    results: list[dict[str, str]] = []
    failed_items: list[str] = []

    print(f"Thu muc input: {input_dir}")
    print(f"So file anh: {len(image_paths)}")
    for image_path in image_paths:
        print(f"\nDang OCR: {image_path}")
        try:
            result = process_image(image_path, pytesseract_module, output_dir)
            results.append(result)
            print(f"  - Ten bien hieu: {result['store_name'] or '[khong ro]'}")
            print(f"  - Dia chi doan duoc: {result['address_guess'] or '[khong ro]'}")
            print(f"  - Lat/Lng: {result['lat'] or '?'} / {result['lng'] or '?'}")
        except Exception as exc:
            failed_items.append(f"{image_path} | {exc}")
            print(f"  - Loi OCR: {exc}")

    json_path, csv_path, excel_path = save_results(results, output_dir)

    if failed_items:
        failed_log = output_dir / "failed_images.txt"
        failed_log.write_text("\n".join(failed_items), encoding="utf-8")
        print(f"\nDa ghi log loi: {failed_log}")

    print("\n================ HOAN TAT ================")
    print(f"So file anh: {len(image_paths)}")
    print(f"So file OCR thanh cong: {len(results)}")
    print(f"So file loi: {len(failed_items)}")
    print(f"Excel: {excel_path}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print("==========================================")


if __name__ == "__main__":
    main()
