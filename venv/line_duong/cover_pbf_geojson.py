import os
import subprocess

def convert_pbf():
    print("=== CHƯƠNG TRÌNH CHUYỂN OSM .PBF → GIS (GDAL / ogr2ogr) ===\n")

    # ===== 1. THƯ MỤC CHỨA FILE PBF =====
    input_folder = input("📁 Nhập thư mục chứa file .pbf: ").strip()
    if not os.path.isdir(input_folder):
        print("❌ Thư mục không tồn tại.")
        return

    pbf_name = input("🗂️ Nhập tên file .pbf (vd: data.pbf): ").strip()
    pbf_path = os.path.join(input_folder, pbf_name)
    if not os.path.isfile(pbf_path):
        print("❌ Không tìm thấy file .pbf.")
        return

    # ===== 2. THƯ MỤC XUẤT FILE =====
    output_folder = input("📂 Nhập thư mục xuất file đầu ra: ").strip()
    if not os.path.isdir(output_folder):
        print("❌ Thư mục xuất không tồn tại.")
        return

    output_name = input("💾 Nhập tên file đầu ra (không cần đuôi): ").strip()

    # ===== 3. CHỌN LAYER =====
    print("\n🔹 Chọn layer OSM:")
    print("  1. points (điểm)")
    print("  2. lines (đường, sông suối, ranh giới tuyến)")
    print("  3. multilinestrings (đa tuyến phức tạp)")
    print("  4. multipolygons (ranh giới hành chính, khu vực)")
    print("  5. other_relations (quan hệ đặc biệt)")

    layer_map = {
        "1": "points",
        "2": "lines",
        "3": "multilinestrings",
        "4": "multipolygons",
        "5": "other_relations"
    }

    layer = layer_map.get(input("👉 Chọn (1–5): ").strip(), "lines")

    # ===== 4. CHỌN ĐỊNH DẠNG =====
    print("\n📦 Chọn định dạng xuất:")
    print("  1. GeoJSON (.geojson)")
    print("  2. Shapefile (.shp)")
    print("  3. GeoPackage (.gpkg) ⭐")

    fmt_choice = input("👉 Chọn (1–3): ").strip()

    if fmt_choice == "1":
        fmt = "GeoJSON"
        ext = ".geojson"
        extra_opts = []
    elif fmt_choice == "2":
        fmt = "ESRI Shapefile"
        ext = ".shp"
        extra_opts = [
            "-lco", "ENCODING=UTF-8",
            "-lco", "SHPT=POLYGON"
        ]
    else:
        fmt = "GPKG"
        ext = ".gpkg"
        extra_opts = ["-nln", output_name]

    output_path = os.path.join(output_folder, output_name + ext)

    # ===== 5. ĐƯỜNG DẪN QGIS =====
    ogr2ogr = r"C:\Program Files\QGIS 3.22.0\bin\ogr2ogr.exe"
    qgis_share = r"C:\Program Files\QGIS 3.22.0\share"

    if not os.path.isfile(ogr2ogr):
        print("❌ Không tìm thấy ogr2ogr.exe.")
        return

    # ===== 6. BIẾN MÔI TRƯỜNG =====
    os.environ["PATH"] = r"C:\Program Files\QGIS 3.22.0\bin" + ";" + os.environ["PATH"]
    os.environ["GDAL_DATA"] = os.path.join(qgis_share, "gdal")
    os.environ["PROJ_LIB"] = os.path.join(qgis_share, "proj")
    os.environ["OSM_CONFIG_FILE"] = os.path.join(qgis_share, "gdal", "osmconf.ini")

    # ===== 7. LỆNH ogr2ogr =====
    cmd = [
        ogr2ogr,
        "-f", fmt,
        output_path,
        pbf_path,
        layer,
        "-t_srs", "EPSG:4326",
        "-skipfailures",
        "-makevalid",
        "-progress"
    ] + extra_opts

    # ===== 8. CHẠY =====
    print("\n🚀 Đang xử lý...\n")
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ HOÀN TẤT!")
        print(f"📄 File tạo tại:\n{output_path}")

    except subprocess.CalledProcessError as e:
        print("\n❌ LỖI KHI CHẠY ogr2ogr")
        print(e)

if __name__ == "__main__":
    convert_pbf()
