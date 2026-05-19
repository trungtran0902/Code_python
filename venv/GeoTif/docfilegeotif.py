# -*- coding: utf-8 -*-
import os
import sys
import json
import platform
import datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

try:
    from osgeo import gdal, osr
    import numpy as np
except ImportError:
    print("❌ Chưa cài GDAL hoặc NumPy.")
    print("Cài bằng lệnh:")
    print("conda create -n geo_env --override-channels -c conda-forge python=3.11 gdal numpy -y")
    sys.exit(1)


gdal.UseExceptions()


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def format_time(timestamp):
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def bytes_to_mb(size_bytes):
    return round(size_bytes / (1024 * 1024), 3)


def format_area_m2(area_m2):
    if area_m2 is None:
        return "Không xác định"

    return (
        f"{area_m2:,.3f} m² | "
        f"{area_m2 / 10_000:,.6f} ha | "
        f"{area_m2 / 1_000_000:,.6f} km²"
    )


def choose_tif_file():
    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Chọn file GeoTIFF / TIF",
        filetypes=[
            ("GeoTIFF / TIF", "*.tif *.tiff"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path


def convert_tuple_to_list(obj):
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, list):
        return [convert_tuple_to_list(x) for x in obj]
    if isinstance(obj, dict):
        return {k: convert_tuple_to_list(v) for k, v in obj.items()}
    return obj


# ============================================================
# THÔNG TIN FILE SYSTEM
# ============================================================

def get_file_system_info(file_path):
    stat = os.stat(file_path)

    if platform.system().lower() == "windows":
        created_note = (
            "Thời gian tạo file theo Windows filesystem. "
            "Nếu file từng được copy sang thư mục này thì đây là thời điểm copy/tạo file tại vị trí hiện tại, "
            "không chắc là thời điểm export gốc."
        )
    else:
        created_note = (
            "Trên Linux/macOS, ctime thường là thời gian thay đổi metadata, "
            "không chắc là thời gian tạo file."
        )

    return {
        "file_name": Path(file_path).name,
        "file_path": str(Path(file_path).resolve()),
        "file_extension": Path(file_path).suffix,
        "file_size_bytes": stat.st_size,
        "file_size_mb": bytes_to_mb(stat.st_size),
        "created_time": format_time(stat.st_ctime),
        "created_time_note": created_note,
        "modified_time": format_time(stat.st_mtime),
        "modified_time_note": (
            "Thời gian chỉnh sửa nội dung file lần cuối theo hệ điều hành. "
            "Nếu file chưa bị sửa sau khi export thì đây thường là mốc gần nhất với thời gian export."
        ),
        "accessed_time": format_time(stat.st_atime),
    }


# ============================================================
# GEO TRANSFORM / BOUNDS
# ============================================================

def get_geotransform(ds):
    try:
        return ds.GetGeoTransform(can_return_null=True)
    except Exception:
        return None


def pixel_to_coord(gt, px, py):
    x = gt[0] + px * gt[1] + py * gt[2]
    y = gt[3] + px * gt[4] + py * gt[5]
    return x, y


def get_bounds(ds, gt):
    if gt is None:
        return None

    width = ds.RasterXSize
    height = ds.RasterYSize

    corners = {
        "top_left": pixel_to_coord(gt, 0, 0),
        "top_right": pixel_to_coord(gt, width, 0),
        "bottom_left": pixel_to_coord(gt, 0, height),
        "bottom_right": pixel_to_coord(gt, width, height),
    }

    xs = [v[0] for v in corners.values()]
    ys = [v[1] for v in corners.values()]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "corners": corners
    }


# ============================================================
# CRS
# ============================================================

def get_crs_info(ds):
    projection = ds.GetProjection()

    if not projection:
        return {
            "has_crs": False,
            "epsg": None,
            "name": None,
            "type": None,
            "unit": None,
            "linear_unit_to_meter": None,
            "wkt": None
        }

    srs = osr.SpatialReference()
    srs.ImportFromWkt(projection)

    authority_name = srs.GetAuthorityName(None)
    authority_code = srs.GetAuthorityCode(None)

    epsg = None
    if authority_name and authority_code:
        epsg = f"{authority_name}:{authority_code}"

    linear_unit_to_meter = None

    if srs.IsProjected():
        crs_type = "Projected CRS"
        unit = srs.GetLinearUnitsName()
        linear_unit_to_meter = srs.GetLinearUnits()
    elif srs.IsGeographic():
        crs_type = "Geographic CRS"
        unit = srs.GetAngularUnitsName()
    else:
        crs_type = "Unknown CRS"
        unit = None

    return {
        "has_crs": True,
        "epsg": epsg,
        "name": srs.GetName(),
        "type": crs_type,
        "unit": unit,
        "linear_unit_to_meter": linear_unit_to_meter,
        "wkt": srs.ExportToPrettyWkt()
    }


# ============================================================
# TÍNH DIỆN TÍCH
# ============================================================

def polygon_area_shoelace(coords):
    if not coords or len(coords) < 3:
        return None

    area = 0.0
    n = len(coords)

    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        area += x1 * y2 - x2 * y1

    return abs(area) / 2.0


def get_footprint_points(gt, width, height, steps=64):
    if gt is None:
        return []

    points_px = []

    def add_edge(x1, y1, x2, y2):
        for i in range(steps):
            t = i / steps
            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t
            points_px.append((px, py))

    add_edge(0, 0, width, 0)
    add_edge(width, 0, width, height)
    add_edge(width, height, 0, height)
    add_edge(0, height, 0, 0)

    return [pixel_to_coord(gt, px, py) for px, py in points_px]


def calculate_equal_area_m2(ds, gt):
    """
    Dùng cho file có CRS dạng địa lý, ví dụ EPSG:4326.
    Chuyển footprint sang EPSG:6933 để tính diện tích gần đúng theo m².
    """
    try:
        wkt = ds.GetProjection()
        if not wkt:
            return None

        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(wkt)

        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(6933)

        try:
            src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        except Exception:
            pass

        transform = osr.CoordinateTransformation(src_srs, dst_srs)

        width = ds.RasterXSize
        height = ds.RasterYSize

        points = get_footprint_points(gt, width, height, steps=64)

        transformed = []
        for x, y in points:
            x2, y2, _ = transform.TransformPoint(float(x), float(y))
            transformed.append((x2, y2))

        return polygon_area_shoelace(transformed)

    except Exception:
        return None


def find_alpha_band_index(ds):
    for i in range(1, ds.RasterCount + 1):
        band = ds.GetRasterBand(i)
        if band.GetColorInterpretation() == gdal.GCI_AlphaBand:
            return i
    return None


def count_valid_pixels(ds):
    """
    Đếm pixel hợp lệ:
    - Nếu có alpha band: alpha > 0 là pixel có dữ liệu.
    - Nếu không có alpha: dùng mask/nodata của band 1.
    - Nếu không có mask/nodata: xem toàn bộ raster là hợp lệ.
    """
    width = ds.RasterXSize
    height = ds.RasterYSize
    total_pixels = width * height

    alpha_index = find_alpha_band_index(ds)

    if alpha_index:
        src_band = ds.GetRasterBand(alpha_index)
        source = f"Alpha band {alpha_index}, pixel alpha > 0"
    else:
        band1 = ds.GetRasterBand(1)
        mask_flags = band1.GetMaskFlags()

        if mask_flags & gdal.GMF_ALL_VALID:
            return {
                "valid_pixels": total_pixels,
                "total_pixels": total_pixels,
                "invalid_pixels": 0,
                "valid_ratio": 1.0,
                "source": "Không có alpha/nodata/mask. Tạm xem toàn bộ raster là vùng dữ liệu.",
                "is_exact": False
            }

        src_band = band1.GetMaskBand()
        source = "Mask/Nodata của band 1, mask > 0"

    valid_pixels = 0

    try:
        block_x, block_y = src_band.GetBlockSize()
    except Exception:
        block_x, block_y = 512, 512

    step_x = max(block_x, 512)
    step_y = max(block_y, 512)

    for y in range(0, height, step_y):
        rows = min(step_y, height - y)

        for x in range(0, width, step_x):
            cols = min(step_x, width - x)

            arr = src_band.ReadAsArray(x, y, cols, rows)

            if arr is None:
                continue

            valid_pixels += int(np.count_nonzero(arr > 0))

    invalid_pixels = total_pixels - valid_pixels
    valid_ratio = valid_pixels / total_pixels if total_pixels else 0

    return {
        "valid_pixels": int(valid_pixels),
        "total_pixels": int(total_pixels),
        "invalid_pixels": int(invalid_pixels),
        "valid_ratio": float(valid_ratio),
        "source": source,
        "is_exact": True
    }


def get_area_info(ds, gt, crs_info):
    """
    Tính:
    1. Diện tích toàn khung ảnh / extent
    2. Diện tích vùng dữ liệu thật nếu có alpha/nodata/mask
    """
    if gt is None:
        return {
            "can_calculate": False,
            "reason": "File không có GeoTransform nên không tính được diện tích."
        }

    width = ds.RasterXSize
    height = ds.RasterYSize
    total_pixels = width * height

    pixel_area_crs_units2 = abs(gt[1] * gt[5] - gt[2] * gt[4])
    full_area_crs_units2 = pixel_area_crs_units2 * total_pixels

    crs_type = crs_info.get("type")
    unit_name = crs_info.get("unit")
    linear_unit_to_meter = crs_info.get("linear_unit_to_meter")

    full_area_m2_projected = None

    if crs_type == "Projected CRS" and linear_unit_to_meter:
        full_area_m2_projected = full_area_crs_units2 * (linear_unit_to_meter ** 2)

    full_area_m2_equal_area = calculate_equal_area_m2(ds, gt)

    if full_area_m2_projected is not None:
        best_full_area_m2 = full_area_m2_projected
        area_method = "Tính trực tiếp từ pixel size vì CRS là hệ tọa độ phẳng/projected."
    elif full_area_m2_equal_area is not None:
        best_full_area_m2 = full_area_m2_equal_area
        area_method = "Tính bằng cách chuyển footprint sang hệ equal-area EPSG:6933."
    else:
        best_full_area_m2 = None
        area_method = "Không chuyển được sang m². Chỉ có diện tích theo đơn vị CRS gốc."

    valid_pixel_info = count_valid_pixels(ds)

    valid_area_m2 = None

    if valid_pixel_info and best_full_area_m2 is not None:
        valid_pixels = valid_pixel_info.get("valid_pixels", 0)
        valid_ratio = valid_pixel_info.get("valid_ratio", 0)

        if full_area_m2_projected is not None:
            valid_area_m2 = valid_pixels * pixel_area_crs_units2 * (linear_unit_to_meter ** 2)
        else:
            valid_area_m2 = best_full_area_m2 * valid_ratio

    return {
        "can_calculate": True,

        "width_pixels": int(width),
        "height_pixels": int(height),
        "total_pixels": int(total_pixels),

        "pixel_area_crs_units2": float(pixel_area_crs_units2),
        "full_area_crs_units2": float(full_area_crs_units2),
        "crs_unit": unit_name,

        "full_area_m2_projected": full_area_m2_projected,
        "full_area_m2_equal_area": full_area_m2_equal_area,
        "best_full_area_m2": best_full_area_m2,
        "best_full_area_text": format_area_m2(best_full_area_m2),

        "area_method": area_method,

        "valid_pixel_info": valid_pixel_info,
        "valid_area_m2": valid_area_m2,
        "valid_area_text": format_area_m2(valid_area_m2),

        "note": (
            "Diện tích extent là toàn bộ khung ảnh. "
            "Diện tích vùng dữ liệu thật sẽ loại pixel alpha=0 hoặc nodata/mask nếu file có thông tin này."
        )
    }


# ============================================================
# METADATA
# ============================================================

def get_metadata_all_domains(ds):
    result = {}

    try:
        domains = ds.GetMetadataDomainList()
    except Exception:
        domains = None

    if not domains:
        domains = [""]

    for domain in domains:
        try:
            metadata = ds.GetMetadata(domain)
            if metadata:
                key = domain if domain else "DEFAULT"
                result[key] = metadata
        except Exception:
            pass

    return result


def find_datetime_tags(metadata_domains):
    result = {}

    keywords = [
        "DATETIME",
        "DATE_TIME",
        "DATE",
        "TIME",
        "CREATED",
        "CREATION",
        "EXPORT",
        "MODIFIED",
        "ACQUISITION"
    ]

    for domain, metadata in metadata_domains.items():
        for key, value in metadata.items():
            upper_key = key.upper()
            if any(word in upper_key for word in keywords):
                result[f"{domain}.{key}"] = value

    return result


def get_important_tiff_tags(metadata_domains):
    important = {}

    important_keywords = [
        "TIFFTAG_DATETIME",
        "TIFFTAG_SOFTWARE",
        "TIFFTAG_ARTIST",
        "TIFFTAG_COPYRIGHT",
        "TIFFTAG_DOCUMENTNAME",
        "TIFFTAG_IMAGEDESCRIPTION",
        "AREA_OR_POINT"
    ]

    for domain, metadata in metadata_domains.items():
        for key, value in metadata.items():
            upper_key = key.upper()
            if any(k in upper_key for k in important_keywords):
                important[f"{domain}.{key}"] = value

    return important


# ============================================================
# XÁC ĐỊNH THỜI GIAN EXPORT CÓ THỂ
# ============================================================

def get_possible_export_time(info):
    candidates = []

    metadata_domains = info.get("metadata_domains", {})

    for domain, metadata in metadata_domains.items():
        for key, value in metadata.items():
            upper_key = key.upper()

            if upper_key == "TIFFTAG_DATETIME" or "TIFFTAG_DATETIME" in upper_key:
                candidates.append({
                    "priority": 1,
                    "source": f"Metadata nội bộ: {domain}.{key}",
                    "value": value,
                    "confidence": "Cao",
                    "note": (
                        "Đây là tag thời gian bên trong TIFF/GeoTIFF. "
                        "Nếu phần mềm export có ghi tag này thì đây thường là thời gian ghi/export file."
                    )
                })

    for domain, metadata in metadata_domains.items():
        for key, value in metadata.items():
            upper_key = key.upper()

            if upper_key == "TIFFTAG_DATETIME" or "TIFFTAG_DATETIME" in upper_key:
                continue

            if any(x in upper_key for x in [
                "DATETIME",
                "DATE_TIME",
                "CREATION",
                "CREATED",
                "EXPORT",
                "MODIFIED",
                "ACQUISITION"
            ]):
                candidates.append({
                    "priority": 2,
                    "source": f"Metadata nội bộ: {domain}.{key}",
                    "value": value,
                    "confidence": "Trung bình đến cao",
                    "note": (
                        "Đây là metadata thời gian bên trong file. "
                        "Cần xem tên tag để xác định là thời gian export, thời gian chụp, hay thời gian xử lý."
                    )
                })

    fs = info.get("file_system", {})

    if fs.get("modified_time"):
        candidates.append({
            "priority": 3,
            "source": "Windows file modified time",
            "value": fs.get("modified_time"),
            "confidence": "Trung bình",
            "note": (
                "Đây là thời gian file được ghi/sửa lần cuối theo hệ điều hành. "
                "Nếu file chưa bị sửa sau khi export thì thường có thể xem là thời gian export gần đúng."
            )
        })

    if fs.get("created_time"):
        candidates.append({
            "priority": 4,
            "source": "Windows file created time",
            "value": fs.get("created_time"),
            "confidence": "Thấp nếu file từng được copy",
            "note": (
                "Đây là thời gian file xuất hiện tại thư mục hiện tại. "
                "Nếu file được copy từ nơi khác sang thì thời gian này không phải thời gian export gốc."
            )
        })

    candidates = sorted(candidates, key=lambda x: x["priority"])

    best = candidates[0] if candidates else None

    return {
        "best_guess": best,
        "all_candidates": candidates
    }


# ============================================================
# BAND INFO
# ============================================================

def get_band_info(ds):
    bands = []

    for i in range(1, ds.RasterCount + 1):
        band = ds.GetRasterBand(i)

        try:
            stats = band.GetStatistics(False, False)
        except Exception:
            stats = None

        try:
            block_size = band.GetBlockSize()
        except Exception:
            block_size = None

        try:
            metadata = band.GetMetadata()
        except Exception:
            metadata = {}

        band_data = {
            "band_index": i,
            "data_type": gdal.GetDataTypeName(band.DataType),
            "color_interpretation": gdal.GetColorInterpretationName(
                band.GetColorInterpretation()
            ),
            "no_data_value": band.GetNoDataValue(),
            "scale": band.GetScale(),
            "offset": band.GetOffset(),
            "unit_type": band.GetUnitType(),
            "block_size": block_size,
            "overview_count": band.GetOverviewCount(),
            "minimum": band.GetMinimum(),
            "maximum": band.GetMaximum(),
            "statistics_cached": {
                "min": stats[0],
                "max": stats[1],
                "mean": stats[2],
                "std_dev": stats[3],
            } if stats else None,
            "metadata": metadata
        }

        bands.append(band_data)

    return bands


# ============================================================
# ĐỌC TOÀN BỘ THÔNG TIN GEOTIFF
# ============================================================

def read_geotiff_info(file_path):
    ds = gdal.Open(file_path, gdal.GA_ReadOnly)

    if ds is None:
        raise RuntimeError("Không mở được file TIF/GeoTIFF.")

    driver = ds.GetDriver()
    gt = get_geotransform(ds)
    metadata_domains = get_metadata_all_domains(ds)
    crs_info = get_crs_info(ds)
    area_info = get_area_info(ds, gt, crs_info)

    try:
        file_list = ds.GetFileList()
    except Exception:
        file_list = []

    info = {
        "file_system": get_file_system_info(file_path),

        "raster": {
            "driver_short_name": driver.ShortName if driver else None,
            "driver_long_name": driver.LongName if driver else None,
            "width_pixels": ds.RasterXSize,
            "height_pixels": ds.RasterYSize,
            "band_count": ds.RasterCount,
        },

        "geo_reference": {
            "geo_transform": gt,
            "pixel_width": gt[1] if gt else None,
            "pixel_height": gt[5] if gt else None,
            "pixel_size_abs": {
                "x": abs(gt[1]) if gt else None,
                "y": abs(gt[5]) if gt else None,
            },
            "bounds": get_bounds(ds, gt),
        },

        "coordinate_reference_system": crs_info,

        "area": area_info,

        "metadata_domains": metadata_domains,

        "datetime_tags_inside_file": find_datetime_tags(metadata_domains),

        "important_tiff_tags": get_important_tiff_tags(metadata_domains),

        "image_structure": ds.GetMetadata("IMAGE_STRUCTURE"),

        "file_list": file_list,

        "bands": get_band_info(ds),
    }

    info["possible_export_time"] = get_possible_export_time(info)

    ds = None

    return convert_tuple_to_list(info)


# ============================================================
# XUẤT FILE TXT
# ============================================================

def write_txt_report(info, output_txt):
    lines = []

    fs = info["file_system"]
    raster = info["raster"]
    geo = info["geo_reference"]
    crs = info["coordinate_reference_system"]
    area = info.get("area", {})

    lines.append("=== BÁO CÁO THÔNG SỐ KỸ THUẬT GEOTIFF / TIF ===")
    lines.append("")

    lines.append("I. THÔNG TIN FILE")
    lines.append(f"Tên file: {fs.get('file_name')}")
    lines.append(f"Đường dẫn: {fs.get('file_path')}")
    lines.append(f"Dung lượng: {fs.get('file_size_mb')} MB")
    lines.append(f"Thời gian tạo file: {fs.get('created_time')}")
    lines.append(f"Ghi chú thời gian tạo: {fs.get('created_time_note')}")
    lines.append(f"Thời gian chỉnh sửa: {fs.get('modified_time')}")
    lines.append(f"Ghi chú thời gian chỉnh sửa: {fs.get('modified_time_note')}")
    lines.append(f"Thời gian truy cập: {fs.get('accessed_time')}")
    lines.append("")

    lines.append("II. THỜI GIAN EXPORT / GHI FILE CÓ THỂ")
    possible = info.get("possible_export_time", {})
    best = possible.get("best_guess")

    if best:
        lines.append("Kết luận gần đúng:")
        lines.append(f"Thời gian export/ghi file có khả năng nhất: {best.get('value')}")
        lines.append(f"Nguồn: {best.get('source')}")
        lines.append(f"Độ tin cậy: {best.get('confidence')}")
        lines.append(f"Ghi chú: {best.get('note')}")
        lines.append("")
    else:
        lines.append("Không xác định được thời gian export/ghi file.")
        lines.append("")

    lines.append("Tất cả mốc thời gian tìm được:")
    candidates = possible.get("all_candidates", [])
    if candidates:
        for item in candidates:
            lines.append(f"- Nguồn: {item.get('source')}")
            lines.append(f"  Giá trị: {item.get('value')}")
            lines.append(f"  Độ tin cậy: {item.get('confidence')}")
            lines.append(f"  Ghi chú: {item.get('note')}")
            lines.append("")
    else:
        lines.append("Không có mốc thời gian nào.")
        lines.append("")

    lines.append("III. THÔNG TIN RASTER")
    lines.append(f"Driver: {raster.get('driver_short_name')} - {raster.get('driver_long_name')}")
    lines.append(f"Kích thước ảnh: {raster.get('width_pixels')} x {raster.get('height_pixels')} pixels")
    lines.append(f"Số band: {raster.get('band_count')}")
    lines.append("")

    lines.append("IV. THÔNG TIN KHÔNG GIAN")
    lines.append(f"GeoTransform: {geo.get('geo_transform')}")
    lines.append(f"Pixel size X: {geo.get('pixel_size_abs', {}).get('x')}")
    lines.append(f"Pixel size Y: {geo.get('pixel_size_abs', {}).get('y')}")

    if geo.get("bounds"):
        b = geo["bounds"]
        lines.append(f"Min X: {b.get('min_x')}")
        lines.append(f"Max X: {b.get('max_x')}")
        lines.append(f"Min Y: {b.get('min_y')}")
        lines.append(f"Max Y: {b.get('max_y')}")
        lines.append(f"Góc trên trái: {b.get('corners', {}).get('top_left')}")
        lines.append(f"Góc trên phải: {b.get('corners', {}).get('top_right')}")
        lines.append(f"Góc dưới trái: {b.get('corners', {}).get('bottom_left')}")
        lines.append(f"Góc dưới phải: {b.get('corners', {}).get('bottom_right')}")
    else:
        lines.append("Không có thông tin bounds/geotransform.")

    lines.append("")

    lines.append("V. THÔNG TIN DIỆN TÍCH")
    if area.get("can_calculate"):
        lines.append(f"Kích thước raster: {area.get('width_pixels')} x {area.get('height_pixels')} pixels")
        lines.append(f"Tổng số pixel: {area.get('total_pixels'):,}")
        lines.append("")

        lines.append("1. Diện tích toàn khung ảnh / extent")
        lines.append(f"Diện tích 1 pixel theo đơn vị CRS: {area.get('pixel_area_crs_units2')}")
        lines.append(f"Đơn vị CRS: {area.get('crs_unit')}")
        lines.append(f"Diện tích extent theo đơn vị CRS²: {area.get('full_area_crs_units2')}")
        lines.append(f"Diện tích extent quy đổi: {area.get('best_full_area_text')}")
        lines.append(f"Phương pháp tính: {area.get('area_method')}")
        lines.append("")

        valid = area.get("valid_pixel_info", {})

        lines.append("2. Diện tích vùng dữ liệu thật")
        lines.append(f"Nguồn xác định pixel hợp lệ: {valid.get('source')}")
        lines.append(f"Pixel hợp lệ: {valid.get('valid_pixels'):,}")
        lines.append(f"Pixel không hợp lệ/trong suốt/nodata: {valid.get('invalid_pixels'):,}")
        lines.append(f"Tỷ lệ pixel hợp lệ: {valid.get('valid_ratio'):.6%}")
        lines.append(f"Diện tích vùng dữ liệu thật: {area.get('valid_area_text')}")
        lines.append(f"Ghi chú: {area.get('note')}")
        lines.append("")
    else:
        lines.append(f"Không tính được diện tích: {area.get('reason')}")
        lines.append("")

    lines.append("VI. HỆ TỌA ĐỘ")
    lines.append(f"Có CRS: {crs.get('has_crs')}")
    lines.append(f"EPSG: {crs.get('epsg')}")
    lines.append(f"Tên CRS: {crs.get('name')}")
    lines.append(f"Loại CRS: {crs.get('type')}")
    lines.append(f"Đơn vị: {crs.get('unit')}")
    lines.append(f"Hệ số đổi đơn vị sang mét: {crs.get('linear_unit_to_meter')}")
    lines.append("")

    lines.append("VII. TIFF TAG QUAN TRỌNG")
    important_tags = info.get("important_tiff_tags", {})
    if important_tags:
        for k, v in important_tags.items():
            lines.append(f"{k}: {v}")
    else:
        lines.append("Không tìm thấy TIFF tag quan trọng.")
    lines.append("")

    lines.append("VIII. DATE/TIME TAG BÊN TRONG FILE")
    datetime_tags = info.get("datetime_tags_inside_file", {})
    if datetime_tags:
        for k, v in datetime_tags.items():
            lines.append(f"{k}: {v}")
    else:
        lines.append("Không tìm thấy tag thời gian bên trong metadata của file.")
    lines.append("")

    lines.append("IX. IMAGE STRUCTURE")
    image_structure = info.get("image_structure", {})
    if image_structure:
        for k, v in image_structure.items():
            lines.append(f"{k}: {v}")
    else:
        lines.append("Không có IMAGE_STRUCTURE metadata.")
    lines.append("")

    lines.append("X. THÔNG TIN BAND")
    for band in info.get("bands", []):
        lines.append(f"--- Band {band.get('band_index')} ---")
        lines.append(f"Data type: {band.get('data_type')}")
        lines.append(f"Color interpretation: {band.get('color_interpretation')}")
        lines.append(f"NoData: {band.get('no_data_value')}")
        lines.append(f"Scale: {band.get('scale')}")
        lines.append(f"Offset: {band.get('offset')}")
        lines.append(f"Unit: {band.get('unit_type')}")
        lines.append(f"Block size: {band.get('block_size')}")
        lines.append(f"Overview count: {band.get('overview_count')}")
        lines.append(f"Minimum: {band.get('minimum')}")
        lines.append(f"Maximum: {band.get('maximum')}")
        lines.append(f"Statistics cached: {band.get('statistics_cached')}")
        lines.append("")

    lines.append("XI. FILE LIÊN QUAN")
    file_list = info.get("file_list", [])
    if file_list:
        for f in file_list:
            lines.append(str(f))
    else:
        lines.append("Không có file liên quan hoặc GDAL không trả về file list.")
    lines.append("")

    lines.append("XII. METADATA GỐC")
    metadata_domains = info.get("metadata_domains", {})
    if metadata_domains:
        for domain, metadata in metadata_domains.items():
            lines.append(f"[{domain}]")
            for k, v in metadata.items():
                lines.append(f"{k}: {v}")
            lines.append("")
    else:
        lines.append("Không có metadata.")
        lines.append("")

    lines.append("XIII. WKT HỆ TỌA ĐỘ")
    if crs.get("wkt"):
        lines.append(crs.get("wkt"))
    else:
        lines.append("Không có WKT CRS.")

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ============================================================
# MAIN
# ============================================================

def main():
    print("=== TOOL ĐỌC THÔNG SỐ KỸ THUẬT GEOTIFF / TIF ===")
    print("")

    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        file_path = choose_tif_file()

    if not file_path:
        print("❌ Chưa chọn file.")
        return

    file_path = str(Path(file_path).resolve())

    if not os.path.exists(file_path):
        print("❌ File không tồn tại.")
        print(file_path)
        return

    if not file_path.lower().endswith((".tif", ".tiff")):
        print("⚠️ File không phải .tif hoặc .tiff, vẫn thử đọc bằng GDAL...")

    try:
        print("Đang đọc file:")
        print(file_path)
        print("")

        info = read_geotiff_info(file_path)

        input_path = Path(file_path)
        output_txt = input_path.with_name(f"{input_path.stem}_thong_so_geotiff.txt")
        output_json = input_path.with_name(f"{input_path.stem}_thong_so_geotiff.json")

        write_txt_report(info, output_txt)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2, default=str)

        print("✅ Đã đọc xong thông số kỹ thuật GeoTIFF/TIF")
        print(f"📄 TXT : {output_txt}")
        print(f"📄 JSON: {output_json}")
        print("")

        possible = info.get("possible_export_time", {})
        best = possible.get("best_guess")

        print("=== THỜI GIAN EXPORT / GHI FILE CÓ THỂ ===")
        if best:
            print(f"Thời gian có khả năng nhất: {best.get('value')}")
            print(f"Nguồn: {best.get('source')}")
            print(f"Độ tin cậy: {best.get('confidence')}")
            print(f"Ghi chú: {best.get('note')}")
        else:
            print("Không xác định được thời gian export/ghi file.")

        print("")
        print("=== THÔNG TIN DIỆN TÍCH ===")
        area = info.get("area", {})

        if area.get("can_calculate"):
            print(f"Diện tích toàn khung ảnh: {area.get('best_full_area_text')}")
            print(f"Diện tích vùng dữ liệu thật: {area.get('valid_area_text')}")

            valid = area.get("valid_pixel_info", {})
            print(f"Pixel hợp lệ: {valid.get('valid_pixels'):,}")
            print(f"Pixel không hợp lệ/trong suốt/nodata: {valid.get('invalid_pixels'):,}")
            print(f"Tỷ lệ pixel hợp lệ: {valid.get('valid_ratio'):.6%}")
            print(f"Nguồn xác định pixel hợp lệ: {valid.get('source')}")
        else:
            print(f"Không tính được diện tích: {area.get('reason')}")

        try:
            messagebox.showinfo(
                "Hoàn tất",
                f"Đã xuất báo cáo:\n\n{output_txt}\n\n{output_json}"
            )
        except Exception:
            pass

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        try:
            messagebox.showerror("Lỗi", str(e))
        except Exception:
            pass


if __name__ == "__main__":
    main()