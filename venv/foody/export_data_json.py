import json
import csv
import sys
import zipfile
from pathlib import Path

from tkinter import Tk, filedialog

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None


def to_text(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


root = Tk()
root.withdraw()

zip_path = filedialog.askopenfilename(
    title="Chon file ZIP chua JSON",
    filetypes=[("ZIP files", "*.zip")],
)

root.destroy()

if not zip_path:
    print("Khong chon file.")
    sys.exit(0)

print(f"Dang doc: {zip_path}")

results = []
fieldnames = [
    "name",
    "address",
    "categories",
    "phones",
    "latitude",
    "longitude",
    "location_url",
    "time",
]

with zipfile.ZipFile(zip_path, "r") as z:
    json_files = [name for name in z.namelist() if name.lower().endswith(".json")]

    print(f"Tong so file JSON: {len(json_files)}")

    for i, file_name in enumerate(json_files, start=1):
        try:
            with z.open(file_name) as f:
                data = json.load(f)

            result = {
                "name": data.get("name"),
                "address": data.get("address"),
                "categories": to_text(data.get("categories", [])),
                "phones": to_text(data.get("phones", [])),
                "latitude": data.get("position", {}).get("latitude"),
                "longitude": data.get("position", {}).get("longitude"),
                "location_url": data.get("location_url"),
                "time": str(data.get("delivery", {}).get("time", {}).get("week_days", [])),
            }
            results.append(result)
        except Exception as e:
            print(f"Loi file {file_name}: {e}")

        if i % 1000 == 0 or i == len(json_files):
            print(f"Da xu ly: {i}/{len(json_files)}")

base_output = Path(zip_path).with_name("output")

if pd is not None:
    output_file = base_output.with_suffix(".xlsx")
    df = pd.DataFrame(results)
    df.to_excel(output_file, index=False)
    print(f"Done! Xuat file Excel: {output_file}")
else:
    output_file = base_output.with_suffix(".csv")
    with output_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print("Khong tim thay pandas/openpyxl, da xuat file CSV thay the.")
    print(f"Done! Xuat file CSV: {output_file}")
