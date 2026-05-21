import os
import glob
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox


# Đặt True nếu muốn hiện thông báo popup khi hoàn tất/lỗi.
# Đặt False để tool chạy xong là thoát luôn, tránh bị treo vì messagebox.
SHOW_MESSAGEBOX = False


def choose_input_shp():
    """
    B1: Chọn file .shp trong bộ Shapefile.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    shp_path = filedialog.askopenfilename(
        parent=root,
        title="B1 - Chọn file .shp đầu vào",
        filetypes=[
            ("Shapefile", "*.shp"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()
    return shp_path


def choose_output_folder():
    """
    B2: Chọn thư mục xuất Shapefile kết quả.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    folder = filedialog.askdirectory(
        parent=root,
        title="B2 - Chọn thư mục xuất Shapefile đã lọc"
    )

    root.destroy()
    return folder


def show_popup(kind, title, msg):
    """
    Hiện popup có root riêng rồi destroy root sau khi người dùng bấm OK.
    Mặc định không dùng popup để tool tự thoát sau khi chạy xong.
    """
    if not SHOW_MESSAGEBOX:
        return

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    if kind == "error":
        messagebox.showerror(title, msg, parent=root)
    else:
        messagebox.showinfo(title, msg, parent=root)

    root.destroy()


def find_gdal_tool(tool_name):
    """
    Tự tìm ogr2ogr.exe / ogrinfo.exe trong QGIS, GDAL, OSGeo4W.
    """
    tool = shutil.which(tool_name)
    if tool:
        return tool

    patterns = [
        rf"C:\Program Files\QGIS*\bin\{tool_name}.exe",
        rf"C:\Program Files\GDAL\{tool_name}.exe",
        rf"C:\OSGeo4W\bin\{tool_name}.exe",
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
    Thiết lập môi trường GDAL nếu đang dùng QGIS.
    """
    bin_dir = os.path.dirname(ogr2ogr_path)
    qgis_root = os.path.dirname(bin_dir)
    qgis_share = os.path.join(qgis_root, "share")

    os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")

    gdal_data = os.path.join(qgis_share, "gdal")
    proj_lib = os.path.join(qgis_share, "proj")

    if os.path.isdir(gdal_data):
        os.environ["GDAL_DATA"] = gdal_data

    if os.path.isdir(proj_lib):
        os.environ["PROJ_LIB"] = proj_lib
        os.environ["PROJ_DATA"] = proj_lib


def remove_old_shapefile(output_shp):
    """
    Xóa bộ Shapefile cũ nếu đã tồn tại.
    """
    base = os.path.splitext(output_shp)[0]

    exts = [
        ".shp", ".shx", ".dbf", ".prj", ".cpg",
        ".qpj", ".sbn", ".sbx", ".fix"
    ]

    for ext in exts:
        file_path = base + ext
        if os.path.exists(file_path):
            os.remove(file_path)


def get_feature_count(ogrinfo_path, shp_path):
    """
    Đọc số lượng đối tượng trong Shapefile.
    """
    try:
        result = subprocess.run(
            [ogrinfo_path, "-so", "-al", shp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )

        for line in result.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("feature count:"):
                return line.split(":", 1)[1].strip()

    except Exception:
        pass

    return "Không xác định"


def filter_cao_toc_bridge(input_shp, output_shp):
    """
    Lọc các tuyến có:
    - highway = motorway
    - other_tags có '"bridge"=>"yes"'
    """
    ogr2ogr = find_gdal_tool("ogr2ogr")
    ogrinfo = find_gdal_tool("ogrinfo")

    if not ogr2ogr:
        raise FileNotFoundError("Không tìm thấy ogr2ogr.exe. Hãy kiểm tra QGIS/GDAL.")

    if not ogrinfo:
        raise FileNotFoundError("Không tìm thấy ogrinfo.exe. Hãy kiểm tra QGIS/GDAL.")

    setup_gdal_env(ogr2ogr)
    remove_old_shapefile(output_shp)

    where_expr = (
        "highway = 'motorway' "
        "AND "
        "other_tags LIKE '%\"bridge\"=>\"yes\"%'"
    )

    cmd = [
        ogr2ogr,
        "-f", "ESRI Shapefile",
        "-overwrite",
        "-skipfailures",
        output_shp,
        input_shp,
        "-where", where_expr,
        "-lco", "ENCODING=UTF-8",
        "-progress",
    ]

    print("\n🚀 Đang lọc dữ liệu...")
    print("Lệnh chạy:")
    print(" ".join(f'\"{x}\"' if " " in x else x for x in cmd))
    print()

    subprocess.run(cmd, check=True)

    count = get_feature_count(ogrinfo, output_shp)
    return count


def main():
    print("=== TOOL LỌC CAO TỐC CÓ bridge=yes TỪ SHAPEFILE ===\n")

    input_shp = choose_input_shp()
    if not input_shp:
        print("❌ Bạn chưa chọn file .shp.")
        return 1

    if not os.path.isfile(input_shp):
        print("❌ File .shp không tồn tại.")
        print(input_shp)
        return 1

    print(f"✅ Shapefile đầu vào:\n{input_shp}")

    output_folder = choose_output_folder()
    if not output_folder:
        print("❌ Bạn chưa chọn thư mục xuất.")
        return 1

    if not os.path.isdir(output_folder):
        print("❌ Thư mục xuất không tồn tại.")
        print(output_folder)
        return 1

    input_name = os.path.splitext(os.path.basename(input_shp))[0]
    output_name = f"{input_name}_cao_toc_bridge.shp"
    output_shp = os.path.join(output_folder, output_name)

    print(f"\n✅ Shapefile đầu ra:\n{output_shp}")

    try:
        count = filter_cao_toc_bridge(input_shp, output_shp)

        msg = f"Đã lọc xong!\n\nFile kết quả:\n{output_shp}\n\nSố đối tượng: {count}"
        print("\n✅ HOÀN TẤT!")
        print(f"📄 File kết quả:\n{output_shp}")
        print(f"🔢 Số đối tượng lọc được: {count}")

        show_popup("info", "Hoàn tất", msg)
        return 0

    except subprocess.CalledProcessError as e:
        msg = "Lỗi khi chạy ogr2ogr. Xem cửa sổ terminal để biết chi tiết."
        print("\n❌ Lỗi khi chạy ogr2ogr.")
        print(e)
        show_popup("error", "Lỗi", msg)
        return 1

    except Exception as e:
        print("\n❌ Lỗi:")
        print(e)
        show_popup("error", "Lỗi", str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
