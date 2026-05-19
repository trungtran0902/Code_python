import os
import glob
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog


def clean_path(path: str) -> str:
    return path.strip().strip('"').strip("'")


def choose_pbf_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Chọn file OSM .PBF",
        filetypes=[
            ("OSM PBF files", "*.pbf"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()
    return file_path


def choose_output_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    folder_path = filedialog.askdirectory(
        title="Chọn thư mục xuất file"
    )

    root.destroy()
    return folder_path


def find_ogr2ogr():
    """
    Tự tìm ogr2ogr.exe trong PATH hoặc thư mục cài QGIS/GDAL.
    """
    ogr = shutil.which("ogr2ogr")
    if ogr:
        return ogr

    patterns = [
        r"C:\Program Files\QGIS*\bin\ogr2ogr.exe",
        r"C:\Program Files\GDAL\ogr2ogr.exe",
        r"C:\OSGeo4W\bin\ogr2ogr.exe",
    ]

    matches = []
    for pattern in patterns:
        matches.extend(glob.glob(pattern))

    if matches:
        matches.sort()
        return matches[-1]

    return None


def setup_gdal_env(ogr2ogr_path):
    """
    Thiết lập biến môi trường GDAL / PROJ / OSM nếu dùng QGIS.
    """
    bin_dir = os.path.dirname(ogr2ogr_path)
    qgis_root = os.path.dirname(bin_dir)
    qgis_share = os.path.join(qgis_root, "share")

    os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")

    gdal_data = os.path.join(qgis_share, "gdal")
    proj_lib = os.path.join(qgis_share, "proj")
    osm_config = os.path.join(gdal_data, "osmconf.ini")

    if os.path.isdir(gdal_data):
        os.environ["GDAL_DATA"] = gdal_data

    if os.path.isdir(proj_lib):
        os.environ["PROJ_LIB"] = proj_lib
        os.environ["PROJ_DATA"] = proj_lib

    if os.path.isfile(osm_config):
        os.environ["OSM_CONFIG_FILE"] = osm_config


def convert_pbf():
    print("=== CHƯƠNG TRÌNH CHUYỂN OSM .PBF → GIS (GDAL / ogr2ogr) ===\n")

    # ===== 1. CHỌN FILE PBF BẰNG HỘP THOẠI =====
    print("📁 Đang mở hộp thoại chọn file .pbf...")
    pbf_path = choose_pbf_file()

    if not pbf_path:
        print("❌ Bạn chưa chọn file .pbf.")
        return

    pbf_path = clean_path(pbf_path)

    if not os.path.isfile(pbf_path):
        print("❌ Không tìm thấy file .pbf.")
        print(f"Đường dẫn đang kiểm tra: {pbf_path}")
        return

    if not pbf_path.lower().endswith(".pbf"):
        print("⚠️ File được chọn không có đuôi .pbf.")
        print("⚠️ Chương trình vẫn tiếp tục nếu GDAL đọc được file này.")

    print(f"✅ File đầu vào:\n{pbf_path}")

    # ===== 2. CHỌN THƯ MỤC XUẤT BẰNG HỘP THOẠI =====
    print("\n📂 Đang mở hộp thoại chọn thư mục xuất...")
    output_folder = choose_output_folder()

    if not output_folder:
        print("❌ Bạn chưa chọn thư mục xuất.")
        return

    output_folder = clean_path(output_folder)

    if not os.path.isdir(output_folder):
        print("❌ Thư mục xuất không tồn tại.")
        print(f"Đường dẫn đang kiểm tra: {output_folder}")
        return

    print(f"✅ Thư mục xuất:\n{output_folder}")

    # ===== 3. CHỌN LAYER =====
    print("\n🔹 Chọn layer OSM:")
    print("  1. points - điểm")
    print("  2. lines - đường, sông suối, ranh giới tuyến")
    print("  3. multilinestrings - đa tuyến phức tạp")
    print("  4. multipolygons - ranh giới hành chính, khu vực")
    print("  5. other_relations - quan hệ đặc biệt")

    layer_map = {
        "1": "points",
        "2": "lines",
        "3": "multilinestrings",
        "4": "multipolygons",
        "5": "other_relations",
    }

    layer_choice = input("👉 Chọn layer (1–5), mặc định 2 - lines: ").strip()
    layer = layer_map.get(layer_choice, "lines")

    # ===== 4. CHỌN ĐỊNH DẠNG XUẤT =====
    print("\n📦 Chọn định dạng xuất:")
    print("  1. GeoJSON (.geojson)")
    print("  2. Shapefile (.shp)")
    print("  3. GeoPackage (.gpkg) ⭐ khuyên dùng")

    fmt_choice = input("👉 Chọn định dạng (1–3), mặc định 3 - GPKG: ").strip()

    # ===== 5. TÊN FILE ĐẦU RA =====
    default_name = os.path.splitext(os.path.basename(pbf_path))[0] + "_" + layer

    output_name = clean_path(
        input(f"💾 Nhập tên file đầu ra, không cần đuôi, mặc định {default_name}: ")
    )

    if not output_name:
        output_name = default_name

    # ===== 6. CẤU HÌNH ĐỊNH DẠNG =====
    extra_opts = []

    if fmt_choice == "1":
        fmt = "GeoJSON"
        ext = ".geojson"

    elif fmt_choice == "2":
        fmt = "ESRI Shapefile"
        ext = ".shp"

        extra_opts = [
            "-lco", "ENCODING=UTF-8",
        ]

        # Sửa lỗi:
        # Không ép tất cả Shapefile thành POLYGON nữa.
        # Chọn đúng kiểu hình học theo layer.
        if layer == "points":
            extra_opts += ["-lco", "SHPT=POINT"]

        elif layer in ["lines", "multilinestrings"]:
            extra_opts += ["-lco", "SHPT=ARC"]

        elif layer == "multipolygons":
            extra_opts += ["-lco", "SHPT=POLYGON"]

        else:
            print("⚠️ other_relations có thể chứa nhiều kiểu hình học.")
            print("⚠️ Nếu lỗi Shapefile, hãy xuất sang GeoPackage (.gpkg).")

    else:
        fmt = "GPKG"
        ext = ".gpkg"
        extra_opts = ["-nln", output_name]

    output_path = os.path.join(output_folder, output_name + ext)

    # ===== 7. TÌM OGR2OGR =====
    ogr2ogr = find_ogr2ogr()

    if not ogr2ogr or not os.path.isfile(ogr2ogr):
        print("❌ Không tìm thấy ogr2ogr.exe.")
        print("Bạn cần cài QGIS hoặc GDAL, hoặc thêm ogr2ogr vào PATH.")
        return

    setup_gdal_env(ogr2ogr)

    print(f"\n✅ Tìm thấy ogr2ogr:\n{ogr2ogr}")

    # ===== 8. LỆNH OGR2OGR =====
    cmd = [
        ogr2ogr,
        "-f", fmt,
        "-overwrite",
        "-t_srs", "EPSG:4326",
        "-skipfailures",
        "-makevalid",
        "-progress",
    ] + extra_opts + [
        output_path,
        pbf_path,
        layer,
    ]

    # ===== 9. CHẠY =====
    print("\n🚀 Đang xử lý...\n")
    print("Lệnh chạy:")
    print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
    print()

    try:
        subprocess.run(cmd, check=True)

        print("\n✅ HOÀN TẤT!")
        print(f"📄 File tạo tại:\n{output_path}")

    except subprocess.CalledProcessError as e:
        print("\n❌ LỖI KHI CHẠY ogr2ogr")
        print(e)

        if fmt == "ESRI Shapefile":
            print("\n💡 Gợi ý:")
            print("- Nếu xuất đường giao thông/sông suối, chọn layer 2 - lines.")
            print("- Nếu xuất ranh giới hành chính/khu vực, chọn layer 4 - multipolygons.")
            print("- Nếu dữ liệu OSM phức tạp, nên chọn GeoPackage (.gpkg).")


if __name__ == "__main__":
    convert_pbf()