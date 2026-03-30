from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from tkinter import Tk, filedialog


BLOCKED_PHRASES = (
    "cau",
    "thon",
    "tinh lo",
    "quoc lo 1",
    "ngo",
    "kiet",
    "hem",
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def has_blocked_phrase(name: str) -> bool:
    normalized_name = normalize_text(name)
    return any(phrase in normalized_name for phrase in BLOCKED_PHRASES)


def has_duplicate_word(name: str) -> bool:
    words = normalize_text(name).split()
    seen: set[str] = set()

    for word in words:
        if word in seen:
            return True
        seen.add(word)

    return False


def geometry_signature(feature: dict) -> str:
    geometry = feature.get("geometry", {})
    coordinates = geometry.get("coordinates", [])
    return json.dumps(coordinates, ensure_ascii=False, separators=(",", ":"))


def should_keep_feature(feature: dict) -> tuple[bool, str]:
    properties = feature.get("properties", {})
    name = str(properties.get("name", "") or "").strip()

    if not name:
        return False, "name_rong"

    geometry_type = feature.get("geometry", {}).get("type")
    if geometry_type not in {"LineString", "MultiLineString"}:
        return False, "khong_phai_line"

    if has_blocked_phrase(name):
        return False, "trung_tu_khoa_cam"

    if has_duplicate_word(name):
        return False, "name_co_tu_lap"

    return True, "giu_lai"


def build_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_filtered.geojson")


def ask_for_paths() -> tuple[Path, Path] | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    input_file = filedialog.askopenfilename(
        title="Chon file GeoJSON dau vao",
        filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")],
    )
    if not input_file:
        root.destroy()
        return None

    default_output_dir = str(Path(input_file).parent)
    output_dir = filedialog.askdirectory(
        title="Chon thu muc dau ra",
        mustexist=False,
        initialdir=default_output_dir,
    )
    if not output_dir:
        root.destroy()
        return None

    root.destroy()
    input_path = Path(input_file)
    output_path = Path(output_dir) / f"{input_path.stem}_filtered.geojson"
    return input_path, output_path


def filter_geojson_lines(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    features = data.get("features", [])
    kept_features = []
    seen_geometries: set[str] = set()
    stats = {
        "tong_feature": len(features),
        "giu_lai": 0,
        "name_rong": 0,
        "khong_phai_line": 0,
        "trung_tu_khoa_cam": 0,
        "name_co_tu_lap": 0,
        "line_trung_hinh_hoc": 0,
    }

    for feature in features:
        keep, reason = should_keep_feature(feature)
        if not keep:
            stats[reason] += 1
            continue

        signature = geometry_signature(feature)
        if signature in seen_geometries:
            stats["line_trung_hinh_hoc"] += 1
            continue

        seen_geometries.add(signature)
        kept_features.append(feature)
        stats["giu_lai"] += 1

    output_data = {
        "type": data.get("type", "FeatureCollection"),
        "features": kept_features,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output_data, file, ensure_ascii=False, indent=2)

    print("=== KET QUA LOC LINE ===")
    print(f"File input: {input_path}")
    print(f"File output: {output_path}")
    print(f"Tong feature: {stats['tong_feature']:,}")
    print(f"Giu lai: {stats['giu_lai']:,}")
    print(f"Bo vi name rong: {stats['name_rong']:,}")
    print(f"Bo vi khong phai line: {stats['khong_phai_line']:,}")
    print(f"Bo vi trung tu khoa cam: {stats['trung_tu_khoa_cam']:,}")
    print(f"Bo vi name co tu lap: {stats['name_co_tu_lap']:,}")
    print(f"Bo vi trung hinh hoc line: {stats['line_trung_hinh_hoc']:,}")


def main() -> None:
    selection = ask_for_paths()
    if selection is None:
        print("Da huy thao tac chon file hoac thu muc output.")
        return

    input_path, output_path = selection
    if not input_path.is_file():
        print(f"Khong tim thay file: {input_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_geojson_lines(input_path, output_path)


if __name__ == "__main__":
    main()
