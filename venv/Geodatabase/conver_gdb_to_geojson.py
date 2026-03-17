import argparse
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog


ARCGIS_PROPY = r"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"


def parse_args():
    parser = argparse.ArgumentParser(description="Convert File Geodatabase to GeoJSON")
    parser.add_argument("--gdb", help="Path to the .gdb folder")
    parser.add_argument("--output", help="Output folder for GeoJSON files")
    parser.add_argument(
        "--backend",
        choices=["auto", "arcpy", "fiona"],
        default="auto",
        help="Backend used for conversion",
    )
    return parser.parse_args()


def select_gdb_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    gdb_path = filedialog.askdirectory(title="Chon File Geodatabase (.gdb)")
    root.destroy()
    return gdb_path


def validate_gdb_path(gdb_path):
    return bool(gdb_path) and gdb_path.lower().endswith(".gdb") and os.path.isdir(gdb_path)


def build_output_folder(gdb_path, output_folder=None):
    if output_folder:
        return output_folder

    gdb = Path(gdb_path)
    return str(gdb.parent / f"{gdb.stem}_geojson_output")


def ensure_output_folder(output_folder):
    os.makedirs(output_folder, exist_ok=True)


def sanitize_name(name):
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if ch in invalid_chars else ch for ch in name)
    return sanitized.replace(" ", "_")


def relaunch_with_arcgis(args, gdb_path, output_folder):
    if not os.path.exists(ARCGIS_PROPY):
        return False

    script_path = os.path.abspath(__file__)
    cmd = [
        ARCGIS_PROPY,
        script_path,
        "--gdb",
        gdb_path,
        "--output",
        output_folder,
        "--backend",
        "arcpy",
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def convert_with_fiona(gdb_path, output_folder):
    import fiona
    import geopandas as gpd

    layers = fiona.listlayers(gdb_path)
    print("Cac Feature Class:")
    for layer in layers:
        print(f" - {layer}")

    if not layers:
        print("Khong tim thay layer nao trong geodatabase.")
        return

    for layer in layers:
        try:
            print(f"Dang xu ly: {layer}")
            gdf = gpd.read_file(gdb_path, layer=layer)
            output_path = os.path.join(output_folder, f"{sanitize_name(layer)}.geojson")
            gdf.to_file(output_path, driver="GeoJSON", encoding="utf-8")
            print(f"Xuat xong: {output_path}")
        except Exception as e:
            print(f"Loi voi {layer}: {e}")


def list_feature_classes_arcpy(arcpy, gdb_path):
    arcpy.env.workspace = gdb_path

    feature_classes = []

    for fc in arcpy.ListFeatureClasses() or []:
        feature_classes.append((fc, fc))

    for dataset in arcpy.ListDatasets(feature_type="feature") or []:
        for fc in arcpy.ListFeatureClasses(feature_dataset=dataset) or []:
            full_name = os.path.join(dataset, fc)
            output_name = f"{dataset}__{fc}"
            feature_classes.append((full_name, output_name))

    return feature_classes


def convert_with_arcpy(gdb_path, output_folder):
    import arcpy

    feature_classes = list_feature_classes_arcpy(arcpy, gdb_path)
    print("Cac Feature Class:")
    for _, display_name in feature_classes:
        print(f" - {display_name}")

    if not feature_classes:
        print("Khong tim thay feature class nao trong geodatabase.")
        return

    for feature_class, output_name in feature_classes:
        try:
            print(f"Dang xu ly: {output_name}")
            input_path = os.path.join(gdb_path, feature_class)
            output_path = os.path.join(output_folder, f"{sanitize_name(output_name)}.geojson")
            arcpy.conversion.FeaturesToJSON(input_path, output_path, geoJSON="GEOJSON")
            print(f"Xuat xong: {output_path}")
        except Exception as e:
            print(f"Loi voi {output_name}: {e}")


def main():
    args = parse_args()
    gdb_path = args.gdb or select_gdb_folder()

    if not validate_gdb_path(gdb_path):
        print("Vui long chon dung thu muc .gdb")
        sys.exit(1)

    output_folder = build_output_folder(gdb_path, args.output)
    ensure_output_folder(output_folder)

    print(f"Da chon: {gdb_path}")
    print(f"Thu muc output: {output_folder}")

    backend = args.backend

    if backend == "auto":
        if os.path.exists(ARCGIS_PROPY) and "arcgispro-py3" not in sys.executable.lower():
            print("Dang chuyen sang Python cua ArcGIS Pro de doc File Geodatabase...")
            success = relaunch_with_arcgis(args, gdb_path, output_folder)
            if success:
                return
            print("Khong the chay bang ArcGIS Pro Python, thu fallback sang fiona/geopandas...")

        backend = "fiona"

    try:
        if backend == "arcpy":
            convert_with_arcpy(gdb_path, output_folder)
        else:
            convert_with_fiona(gdb_path, output_folder)
    except ModuleNotFoundError as e:
        print(f"Thieu thu vien: {e}")
        print("Neu may co ArcGIS Pro, hay chay lai file nay bang propy.bat hoac de script tu relaunch.")
        sys.exit(1)
    except Exception as e:
        print(f"Khong the chuyen doi geodatabase: {e}")
        sys.exit(1)

    print("Hoan thanh!")


if __name__ == "__main__":
    main()
