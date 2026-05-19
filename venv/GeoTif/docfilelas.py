# -*- coding: utf-8 -*-
import os
import sys
import json
import math
import platform
import datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

try:
    import numpy as np
    import laspy
    from pyproj import CRS, Geod
except ImportError:
    print("❌ Chưa cài đủ thư viện.")
    print("Cài bằng lệnh:")
    print("conda install --override-channels -c conda-forge laspy lazrs-python numpy pyproj -y")
    sys.exit(1)


# ============================================================
# CẤU HÌNH
# ============================================================

CHUNK_SIZE = 2_000_000
MAX_GRID_CELLS = 5_000_000


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


def format_density(value):
    if value is None:
        return "Không xác định"
    return f"{value:,.6f} điểm/m²"


def json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    return obj


def safe_attr(obj, attr_name, default=None):
    try:
        return getattr(obj, attr_name)
    except Exception:
        return default


def safe_int(value, default=None):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value, default=None):
    try:
        if value is None:
            return default
        return bool(value)
    except Exception:
        return default


def choose_las_file():
    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Chọn file LAS / LAZ",
        filetypes=[
            ("LAS / LAZ point cloud", "*.las *.laz"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path


# ============================================================
# FILE SYSTEM
# ============================================================

def get_file_system_info(file_path):
    stat = os.stat(file_path)

    if platform.system().lower() == "windows":
        created_note = (
            "Thời gian tạo file theo Windows filesystem. "
            "Nếu file từng được copy sang thư mục này thì đây là thời điểm file xuất hiện ở vị trí hiện tại, "
            "không chắc là thời gian export gốc."
        )
    else:
        created_note = (
            "Trên Linux/macOS, ctime thường là thời gian thay đổi metadata, "
            "không chắc là thời gian tạo file."
        )

    return {
        "file_name": Path(file_path).name,
        "file_path": str(Path(file_path).resolve()),
        "file_extension": Path(file_path).suffix.lower(),
        "file_size_bytes": stat.st_size,
        "file_size_mb": bytes_to_mb(stat.st_size),
        "created_time": format_time(stat.st_ctime),
        "created_time_note": created_note,
        "modified_time": format_time(stat.st_mtime),
        "modified_time_note": (
            "Thời gian chỉnh sửa file lần cuối theo hệ điều hành. "
            "Nếu file chưa bị sửa sau khi export thì đây có thể là mốc gần với thời gian export."
        ),
        "accessed_time": format_time(stat.st_atime),
    }


# ============================================================
# CRS
# ============================================================

def get_crs_info(header):
    try:
        crs = header.parse_crs()
    except Exception:
        crs = None

    if crs is None:
        return {
            "has_crs": False,
            "epsg": None,
            "name": None,
            "type": None,
            "unit": None,
            "linear_unit_to_meter": None,
            "is_geographic": False,
            "is_projected": False,
            "wkt": None,
        }

    try:
        pycrs = CRS.from_user_input(crs)
    except Exception:
        pycrs = None

    if pycrs is None:
        return {
            "has_crs": True,
            "epsg": None,
            "name": str(crs),
            "type": "Unknown CRS",
            "unit": None,
            "linear_unit_to_meter": None,
            "is_geographic": False,
            "is_projected": False,
            "wkt": None,
        }

    try:
        epsg_code = pycrs.to_epsg()
        epsg = f"EPSG:{epsg_code}" if epsg_code else None
    except Exception:
        epsg = None

    try:
        is_geographic = bool(pycrs.is_geographic)
    except Exception:
        is_geographic = False

    try:
        is_projected = bool(pycrs.is_projected)
    except Exception:
        is_projected = False

    if is_projected:
        crs_type = "Projected CRS"
    elif is_geographic:
        crs_type = "Geographic CRS"
    else:
        crs_type = "Unknown CRS"

    unit = None
    linear_unit_to_meter = None

    try:
        axis_info = pycrs.axis_info
        if axis_info:
            unit = axis_info[0].unit_name
            linear_unit_to_meter = axis_info[0].unit_conversion_factor
    except Exception:
        pass

    try:
        wkt = pycrs.to_wkt(pretty=True)
    except Exception:
        wkt = None

    return {
        "has_crs": True,
        "epsg": epsg,
        "name": pycrs.name,
        "type": crs_type,
        "unit": unit,
        "linear_unit_to_meter": linear_unit_to_meter,
        "is_geographic": is_geographic,
        "is_projected": is_projected,
        "wkt": wkt,
    }


# ============================================================
# TÍNH DIỆN TÍCH
# ============================================================

def bbox_area_m2(min_x, min_y, max_x, max_y, crs_info):
    width = max_x - min_x
    height = max_y - min_y
    area_crs_units2 = abs(width * height)

    if area_crs_units2 == 0:
        return {
            "area_crs_units2": area_crs_units2,
            "area_m2": 0,
            "method": "BBox không có diện tích."
        }

    if crs_info.get("is_projected") and crs_info.get("linear_unit_to_meter"):
        factor = crs_info.get("linear_unit_to_meter")
        area_m2 = area_crs_units2 * (factor ** 2)
        return {
            "area_crs_units2": area_crs_units2,
            "area_m2": area_m2,
            "method": "Tính trực tiếp từ bbox XY vì CRS là hệ tọa độ phẳng/projected."
        }

    if crs_info.get("is_geographic"):
        try:
            geod = Geod(ellps="WGS84")
            lons = [min_x, max_x, max_x, min_x, min_x]
            lats = [min_y, min_y, max_y, max_y, min_y]
            area, _ = geod.polygon_area_perimeter(lons, lats)
            area_m2 = abs(area)

            return {
                "area_crs_units2": area_crs_units2,
                "area_m2": area_m2,
                "method": "Tính diện tích bbox bằng geodesic area vì CRS là hệ tọa độ địa lý."
            }
        except Exception:
            pass

    return {
        "area_crs_units2": area_crs_units2,
        "area_m2": None,
        "method": "Không quy đổi được sang m² do thiếu CRS hoặc thiếu đơn vị CRS."
    }


def choose_grid_size(width, height, bbox_area_units2, point_count):
    if width <= 0 or height <= 0 or bbox_area_units2 <= 0:
        return None

    approx_spacing = math.sqrt(bbox_area_units2 / point_count) if point_count > 0 else None
    grid_size_by_cell_limit = math.sqrt(bbox_area_units2 / MAX_GRID_CELLS)
    grid_size_by_dimension = max(width / 2500, height / 2500)

    if approx_spacing:
        grid_size = max(approx_spacing, grid_size_by_cell_limit, grid_size_by_dimension)
    else:
        grid_size = max(grid_size_by_cell_limit, grid_size_by_dimension)

    return grid_size


def estimate_occupied_area_grid(las_reader, header, crs_info):
    min_x, min_y, _ = header.mins
    max_x, max_y, _ = header.maxs

    width = max_x - min_x
    height = max_y - min_y
    bbox_area_units2 = abs(width * height)
    point_count = int(header.point_count)

    if width <= 0 or height <= 0 or point_count <= 0:
        return {
            "can_calculate": False,
            "reason": "BBox hoặc số điểm không hợp lệ."
        }

    grid_size = choose_grid_size(width, height, bbox_area_units2, point_count)

    if not grid_size or grid_size <= 0:
        return {
            "can_calculate": False,
            "reason": "Không xác định được grid size."
        }

    cols = int(math.ceil(width / grid_size))
    rows = int(math.ceil(height / grid_size))
    total_grid_cells = cols * rows

    occupied = set()

    for points in las_reader.chunk_iterator(CHUNK_SIZE):
        xs = np.asarray(points.x)
        ys = np.asarray(points.y)

        col_idx = np.floor((xs - min_x) / grid_size).astype(np.int64)
        row_idx = np.floor((ys - min_y) / grid_size).astype(np.int64)

        col_idx = np.clip(col_idx, 0, cols - 1)
        row_idx = np.clip(row_idx, 0, rows - 1)

        cell_ids = row_idx * cols + col_idx
        unique_cells = np.unique(cell_ids)

        for cell_id in unique_cells:
            occupied.add(int(cell_id))

    occupied_cells = len(occupied)
    occupied_ratio = occupied_cells / total_grid_cells if total_grid_cells else 0

    cell_area_units2 = grid_size * grid_size
    occupied_area_units2 = occupied_cells * cell_area_units2

    occupied_area_m2 = None

    if crs_info.get("is_projected") and crs_info.get("linear_unit_to_meter"):
        factor = crs_info.get("linear_unit_to_meter")
        occupied_area_m2 = occupied_area_units2 * (factor ** 2)

    return {
        "can_calculate": True,
        "method": "Ước tính vùng phủ dữ liệu bằng lưới XY có điểm.",
        "grid_size_crs_units": grid_size,
        "cols": cols,
        "rows": rows,
        "total_grid_cells": total_grid_cells,
        "occupied_cells": occupied_cells,
        "occupied_ratio": occupied_ratio,
        "cell_area_crs_units2": cell_area_units2,
        "occupied_area_crs_units2": occupied_area_units2,
        "occupied_area_m2": occupied_area_m2,
        "occupied_area_text": format_area_m2(occupied_area_m2),
        "note": (
            "Đây là diện tích vùng phủ ước tính theo chiếu bằng XY. "
            "Kết quả phụ thuộc kích thước ô lưới. Không phải diện tích bề mặt 3D."
        )
    }


def get_area_info(file_path, header, crs_info):
    min_x, min_y, min_z = header.mins
    max_x, max_y, max_z = header.maxs

    bbox = bbox_area_m2(min_x, min_y, max_x, max_y, crs_info)

    point_count = int(header.point_count)
    density_bbox = None

    if bbox.get("area_m2") and bbox.get("area_m2") > 0:
        density_bbox = point_count / bbox.get("area_m2")

    occupied_area = None
    density_occupied = None

    try:
        with laspy.open(file_path) as las_reader:
            occupied_area = estimate_occupied_area_grid(las_reader, header, crs_info)

        if (
            occupied_area
            and occupied_area.get("occupied_area_m2")
            and occupied_area.get("occupied_area_m2") > 0
        ):
            density_occupied = point_count / occupied_area.get("occupied_area_m2")

    except Exception as e:
        occupied_area = {
            "can_calculate": False,
            "reason": f"Không tính được occupied area: {e}"
        }

    return {
        "bbox_xy": {
            "min_x": float(min_x),
            "min_y": float(min_y),
            "max_x": float(max_x),
            "max_y": float(max_y),
            "width": float(max_x - min_x),
            "height": float(max_y - min_y),
            "area_crs_units2": bbox.get("area_crs_units2"),
            "area_m2": bbox.get("area_m2"),
            "area_text": format_area_m2(bbox.get("area_m2")),
            "method": bbox.get("method"),
        },
        "occupied_xy_estimated": occupied_area,
        "point_density_by_bbox": density_bbox,
        "point_density_by_bbox_text": format_density(density_bbox),
        "point_density_by_occupied_area": density_occupied,
        "point_density_by_occupied_area_text": format_density(density_occupied),
        "note": (
            "Diện tích bbox XY là hình chữ nhật bao ngoài toàn bộ point cloud. "
            "Diện tích occupied XY là vùng phủ ước tính theo các ô lưới có điểm."
        )
    }


# ============================================================
# LAS HEADER
# ============================================================

def get_las_header_info(header):
    creation_date = None

    try:
        if header.creation_date:
            creation_date = header.creation_date.isoformat()
    except Exception:
        creation_date = None

    try:
        point_count_by_return = [int(v) for v in header.number_of_points_by_return]
    except Exception:
        point_count_by_return = []

    try:
        las_version = str(header.version)
    except Exception:
        las_version = None

    try:
        point_format_id = int(header.point_format.id)
    except Exception:
        point_format_id = None

    try:
        point_format = str(header.point_format)
    except Exception:
        point_format = None

    try:
        system_identifier = str(header.system_identifier).strip()
    except Exception:
        system_identifier = None

    try:
        generating_software = str(header.generating_software).strip()
    except Exception:
        generating_software = None

    try:
        global_encoding = str(header.global_encoding)
    except Exception:
        global_encoding = None

    try:
        uuid_value = str(header.uuid)
    except Exception:
        uuid_value = None

    header_size = safe_attr(header, "header_size", None)
    offset_to_point_data = safe_attr(header, "offset_to_point_data", None)
    are_points_compressed = safe_attr(header, "are_points_compressed", None)

    return {
        "las_version": las_version,
        "point_format_id": point_format_id,
        "point_format": point_format,
        "point_count": safe_int(safe_attr(header, "point_count", 0), 0),
        "point_count_by_return": point_count_by_return,
        "creation_date_in_header": creation_date,
        "system_identifier": system_identifier,
        "generating_software": generating_software,
        "file_source_id": safe_int(safe_attr(header, "file_source_id", None)),
        "global_encoding": global_encoding,
        "uuid": uuid_value,

        "scales": {
            "x_scale": safe_float(header.scales[0]),
            "y_scale": safe_float(header.scales[1]),
            "z_scale": safe_float(header.scales[2]),
        },

        "offsets": {
            "x_offset": safe_float(header.offsets[0]),
            "y_offset": safe_float(header.offsets[1]),
            "z_offset": safe_float(header.offsets[2]),
        },

        "bounds": {
            "min_x": safe_float(header.mins[0]),
            "min_y": safe_float(header.mins[1]),
            "min_z": safe_float(header.mins[2]),
            "max_x": safe_float(header.maxs[0]),
            "max_y": safe_float(header.maxs[1]),
            "max_z": safe_float(header.maxs[2]),
            "range_x": safe_float(header.maxs[0] - header.mins[0]),
            "range_y": safe_float(header.maxs[1] - header.mins[1]),
            "range_z": safe_float(header.maxs[2] - header.mins[2]),
        },

        "header_size": safe_int(header_size),
        "offset_to_point_data": safe_int(offset_to_point_data),
        "are_points_compressed": safe_bool(are_points_compressed),
    }


def get_dimensions_info(header):
    dims = []

    try:
        for dim in header.point_format.dimensions:
            try:
                dims.append(dim.name)
            except Exception:
                dims.append(str(dim))
    except Exception:
        pass

    return dims


def get_vlr_info(header):
    vlrs = []

    try:
        for vlr in header.vlrs:
            vlrs.append({
                "user_id": str(safe_attr(vlr, "user_id", "")),
                "record_id": safe_int(safe_attr(vlr, "record_id", None)),
                "description": str(safe_attr(vlr, "description", "")),
                "class": vlr.__class__.__name__,
            })
    except Exception:
        pass

    evlrs = []

    try:
        evlr_list = safe_attr(header, "evlrs", None)

        if evlr_list:
            for evlr in evlr_list:
                evlrs.append({
                    "user_id": str(safe_attr(evlr, "user_id", "")),
                    "record_id": safe_int(safe_attr(evlr, "record_id", None)),
                    "description": str(safe_attr(evlr, "description", "")),
                    "class": evlr.__class__.__name__,
                })
    except Exception:
        pass

    return {
        "vlr_count": len(vlrs),
        "evlr_count": len(evlrs),
        "vlrs": vlrs,
        "evlrs": evlrs,
    }


def get_possible_export_time(file_system_info, header_info):
    candidates = []

    if header_info.get("creation_date_in_header"):
        candidates.append({
            "priority": 1,
            "source": "LAS header creation_date",
            "value": header_info.get("creation_date_in_header"),
            "confidence": "Cao nếu phần mềm export ghi đúng LAS header",
            "note": (
                "Đây là ngày tạo được ghi trong header LAS. "
                "LAS header thường chỉ lưu ngày, không luôn có giờ/phút/giây."
            )
        })

    if file_system_info.get("modified_time"):
        candidates.append({
            "priority": 2,
            "source": "Windows file modified time",
            "value": file_system_info.get("modified_time"),
            "confidence": "Trung bình",
            "note": (
                "Thời gian file được ghi/sửa lần cuối theo hệ điều hành. "
                "Nếu file chưa bị sửa sau khi export thì đây có thể là thời gian export gần đúng."
            )
        })

    if file_system_info.get("created_time"):
        candidates.append({
            "priority": 3,
            "source": "Windows file created time",
            "value": file_system_info.get("created_time"),
            "confidence": "Thấp nếu file từng được copy",
            "note": (
                "Đây là thời gian file xuất hiện tại thư mục hiện tại. "
                "Nếu file được copy từ nơi khác sang thì không phải thời gian export gốc."
            )
        })

    candidates = sorted(candidates, key=lambda x: x["priority"])

    return {
        "best_guess": candidates[0] if candidates else None,
        "all_candidates": candidates
    }


# ============================================================
# THỐNG KÊ POINT ATTRIBUTE
# ============================================================

def init_counter_dict():
    return {
        "classification": {},
        "return_number": {},
        "number_of_returns": {},
        "scan_angle": {
            "min": None,
            "max": None
        },
        "intensity": {
            "exists": False,
            "min": None,
            "max": None,
            "mean": None
        },
        "gps_time": {
            "exists": False,
            "min": None,
            "max": None
        },
        "rgb": {
            "exists": False,
            "red_min": None,
            "red_max": None,
            "green_min": None,
            "green_max": None,
            "blue_min": None,
            "blue_max": None
        }
    }


def update_min_max(current_min, current_max, arr):
    if arr is None or len(arr) == 0:
        return current_min, current_max

    arr_min = float(np.min(arr))
    arr_max = float(np.max(arr))

    if current_min is None or arr_min < current_min:
        current_min = arr_min

    if current_max is None or arr_max > current_max:
        current_max = arr_max

    return current_min, current_max


def add_counts(counter, values):
    if values is None:
        return

    unique, counts = np.unique(values, return_counts=True)

    for k, v in zip(unique, counts):
        try:
            key = str(int(k))
        except Exception:
            key = str(k)

        counter[key] = counter.get(key, 0) + int(v)


def scan_point_attributes(file_path, dimensions):
    result = init_counter_dict()

    intensity_sum = 0
    intensity_count = 0

    has_classification = "classification" in dimensions
    has_return_number = "return_number" in dimensions
    has_number_of_returns = "number_of_returns" in dimensions
    has_scan_angle = "scan_angle" in dimensions
    has_scan_angle_rank = "scan_angle_rank" in dimensions
    has_intensity = "intensity" in dimensions
    has_gps_time = "gps_time" in dimensions
    has_rgb = all(x in dimensions for x in ["red", "green", "blue"])

    with laspy.open(file_path) as las_reader:
        for points in las_reader.chunk_iterator(CHUNK_SIZE):

            if has_classification:
                try:
                    add_counts(result["classification"], np.asarray(points.classification))
                except Exception:
                    pass

            if has_return_number:
                try:
                    add_counts(result["return_number"], np.asarray(points.return_number))
                except Exception:
                    pass

            if has_number_of_returns:
                try:
                    add_counts(result["number_of_returns"], np.asarray(points.number_of_returns))
                except Exception:
                    pass

            if has_scan_angle:
                try:
                    arr = np.asarray(points.scan_angle)
                    result["scan_angle"]["min"], result["scan_angle"]["max"] = update_min_max(
                        result["scan_angle"]["min"],
                        result["scan_angle"]["max"],
                        arr
                    )
                except Exception:
                    pass
            elif has_scan_angle_rank:
                try:
                    arr = np.asarray(points.scan_angle_rank)
                    result["scan_angle"]["min"], result["scan_angle"]["max"] = update_min_max(
                        result["scan_angle"]["min"],
                        result["scan_angle"]["max"],
                        arr
                    )
                except Exception:
                    pass

            if has_intensity:
                try:
                    arr = np.asarray(points.intensity)
                    result["intensity"]["exists"] = True
                    result["intensity"]["min"], result["intensity"]["max"] = update_min_max(
                        result["intensity"]["min"],
                        result["intensity"]["max"],
                        arr
                    )
                    intensity_sum += float(np.sum(arr))
                    intensity_count += int(arr.size)
                except Exception:
                    pass

            if has_gps_time:
                try:
                    arr = np.asarray(points.gps_time)
                    result["gps_time"]["exists"] = True
                    result["gps_time"]["min"], result["gps_time"]["max"] = update_min_max(
                        result["gps_time"]["min"],
                        result["gps_time"]["max"],
                        arr
                    )
                except Exception:
                    pass

            if has_rgb:
                try:
                    result["rgb"]["exists"] = True

                    red = np.asarray(points.red)
                    green = np.asarray(points.green)
                    blue = np.asarray(points.blue)

                    result["rgb"]["red_min"], result["rgb"]["red_max"] = update_min_max(
                        result["rgb"]["red_min"],
                        result["rgb"]["red_max"],
                        red
                    )
                    result["rgb"]["green_min"], result["rgb"]["green_max"] = update_min_max(
                        result["rgb"]["green_min"],
                        result["rgb"]["green_max"],
                        green
                    )
                    result["rgb"]["blue_min"], result["rgb"]["blue_max"] = update_min_max(
                        result["rgb"]["blue_min"],
                        result["rgb"]["blue_max"],
                        blue
                    )
                except Exception:
                    pass

    if intensity_count > 0:
        result["intensity"]["mean"] = intensity_sum / intensity_count

    return result


# ============================================================
# ĐỌC FILE LAS / LAZ
# ============================================================

def read_las_info(file_path):
    file_system_info = get_file_system_info(file_path)

    with laspy.open(file_path) as las_reader:
        header = las_reader.header

        header_info = get_las_header_info(header)
        dimensions = get_dimensions_info(header)
        crs_info = get_crs_info(header)
        vlr_info = get_vlr_info(header)

    point_attribute_summary = scan_point_attributes(file_path, dimensions)

    with laspy.open(file_path) as las_reader:
        header = las_reader.header
        area_info = get_area_info(file_path, header, crs_info)

    info = {
        "file_system": file_system_info,
        "las_header": header_info,
        "coordinate_reference_system": crs_info,
        "dimensions": dimensions,
        "vlr_info": vlr_info,
        "point_attribute_summary": point_attribute_summary,
        "area": area_info,
    }

    info["possible_export_time"] = get_possible_export_time(file_system_info, header_info)

    return json_safe(info)


# ============================================================
# XUẤT TXT
# ============================================================

def write_txt_report(info, output_txt):
    lines = []

    fs = info.get("file_system", {})
    header = info.get("las_header", {})
    crs = info.get("coordinate_reference_system", {})
    area = info.get("area", {})
    attr = info.get("point_attribute_summary", {})
    vlr = info.get("vlr_info", {})

    lines.append("=== BÁO CÁO THÔNG SỐ KỸ THUẬT LAS / LAZ ===")
    lines.append("")

    lines.append("I. THÔNG TIN FILE")
    lines.append(f"Tên file: {fs.get('file_name')}")
    lines.append(f"Đường dẫn: {fs.get('file_path')}")
    lines.append(f"Định dạng: {fs.get('file_extension')}")
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

    lines.append("III. LAS HEADER")
    lines.append(f"LAS version: {header.get('las_version')}")
    lines.append(f"Point format ID: {header.get('point_format_id')}")
    lines.append(f"Point format: {header.get('point_format')}")
    lines.append(f"Số lượng điểm: {header.get('point_count'):,}")
    lines.append(f"Số điểm theo return: {header.get('point_count_by_return')}")
    lines.append(f"Ngày tạo trong LAS header: {header.get('creation_date_in_header')}")
    lines.append(f"System identifier: {header.get('system_identifier')}")
    lines.append(f"Generating software: {header.get('generating_software')}")
    lines.append(f"File source ID: {header.get('file_source_id')}")
    lines.append(f"Global encoding: {header.get('global_encoding')}")
    lines.append(f"UUID: {header.get('uuid')}")
    lines.append(f"Header size: {header.get('header_size')}")
    lines.append(f"Offset to point data: {header.get('offset_to_point_data')}")
    lines.append(f"Point compressed: {header.get('are_points_compressed')}")
    lines.append("")

    scales = header.get("scales", {})
    offsets = header.get("offsets", {})
    bounds = header.get("bounds", {})

    lines.append("IV. SCALE / OFFSET / BOUNDS")
    lines.append(f"X scale: {scales.get('x_scale')}")
    lines.append(f"Y scale: {scales.get('y_scale')}")
    lines.append(f"Z scale: {scales.get('z_scale')}")
    lines.append(f"X offset: {offsets.get('x_offset')}")
    lines.append(f"Y offset: {offsets.get('y_offset')}")
    lines.append(f"Z offset: {offsets.get('z_offset')}")
    lines.append("")
    lines.append(f"Min X: {bounds.get('min_x')}")
    lines.append(f"Min Y: {bounds.get('min_y')}")
    lines.append(f"Min Z: {bounds.get('min_z')}")
    lines.append(f"Max X: {bounds.get('max_x')}")
    lines.append(f"Max Y: {bounds.get('max_y')}")
    lines.append(f"Max Z: {bounds.get('max_z')}")
    lines.append(f"Range X: {bounds.get('range_x')}")
    lines.append(f"Range Y: {bounds.get('range_y')}")
    lines.append(f"Range Z / chênh cao: {bounds.get('range_z')}")
    lines.append("")

    lines.append("V. HỆ TỌA ĐỘ")
    lines.append(f"Có CRS: {crs.get('has_crs')}")
    lines.append(f"EPSG: {crs.get('epsg')}")
    lines.append(f"Tên CRS: {crs.get('name')}")
    lines.append(f"Loại CRS: {crs.get('type')}")
    lines.append(f"Đơn vị: {crs.get('unit')}")
    lines.append(f"Hệ số đổi đơn vị sang mét: {crs.get('linear_unit_to_meter')}")
    lines.append("")

    lines.append("VI. DIỆN TÍCH / MẬT ĐỘ")
    bbox = area.get("bbox_xy", {})
    occupied = area.get("occupied_xy_estimated", {})

    lines.append("1. Diện tích bbox XY")
    lines.append(f"Width X: {bbox.get('width')}")
    lines.append(f"Height Y: {bbox.get('height')}")
    lines.append(f"Diện tích bbox theo CRS²: {bbox.get('area_crs_units2')}")
    lines.append(f"Diện tích bbox quy đổi: {bbox.get('area_text')}")
    lines.append(f"Phương pháp: {bbox.get('method')}")
    lines.append(f"Mật độ điểm theo bbox: {area.get('point_density_by_bbox_text')}")
    lines.append("")

    lines.append("2. Diện tích vùng phủ dữ liệu ước tính")
    if occupied and occupied.get("can_calculate"):
        lines.append(f"Phương pháp: {occupied.get('method')}")
        lines.append(f"Grid size theo CRS: {occupied.get('grid_size_crs_units')}")
        lines.append(f"Số cột grid: {occupied.get('cols')}")
        lines.append(f"Số dòng grid: {occupied.get('rows')}")
        lines.append(f"Tổng số ô grid: {occupied.get('total_grid_cells'):,}")
        lines.append(f"Số ô có điểm: {occupied.get('occupied_cells'):,}")
        lines.append(f"Tỷ lệ ô có điểm: {occupied.get('occupied_ratio'):.6%}")
        lines.append(f"Diện tích vùng phủ theo CRS²: {occupied.get('occupied_area_crs_units2')}")
        lines.append(f"Diện tích vùng phủ quy đổi: {occupied.get('occupied_area_text')}")
        lines.append(f"Mật độ điểm theo vùng phủ: {area.get('point_density_by_occupied_area_text')}")
        lines.append(f"Ghi chú: {occupied.get('note')}")
    else:
        reason = occupied.get("reason") if occupied else "Không có dữ liệu occupied area."
        lines.append(f"Không tính được: {reason}")
    lines.append("")

    lines.append("VII. DIMENSIONS")
    dims = info.get("dimensions", [])
    if dims:
        for d in dims:
            lines.append(f"- {d}")
    else:
        lines.append("Không đọc được dimension.")
    lines.append("")

    lines.append("VIII. THỐNG KÊ POINT ATTRIBUTE")

    lines.append("Classification count:")
    classification = attr.get("classification", {})
    if classification:
        for k, v in sorted(classification.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 9999):
            lines.append(f"  Class {k}: {v:,}")
    else:
        lines.append("  Không có classification hoặc không đọc được.")
    lines.append("")

    lines.append("Return number count:")
    return_number = attr.get("return_number", {})
    if return_number:
        for k, v in sorted(return_number.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 9999):
            lines.append(f"  Return {k}: {v:,}")
    else:
        lines.append("  Không có return_number hoặc không đọc được.")
    lines.append("")

    lines.append("Number of returns count:")
    number_of_returns = attr.get("number_of_returns", {})
    if number_of_returns:
        for k, v in sorted(number_of_returns.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 9999):
            lines.append(f"  Number of returns {k}: {v:,}")
    else:
        lines.append("  Không có number_of_returns hoặc không đọc được.")
    lines.append("")

    intensity = attr.get("intensity", {})
    lines.append("Intensity:")
    lines.append(f"  Có intensity: {intensity.get('exists')}")
    lines.append(f"  Min: {intensity.get('min')}")
    lines.append(f"  Max: {intensity.get('max')}")
    lines.append(f"  Mean: {intensity.get('mean')}")
    lines.append("")

    gps_time = attr.get("gps_time", {})
    lines.append("GPS time:")
    lines.append(f"  Có GPS time: {gps_time.get('exists')}")
    lines.append(f"  Min: {gps_time.get('min')}")
    lines.append(f"  Max: {gps_time.get('max')}")
    lines.append("")

    rgb = attr.get("rgb", {})
    lines.append("RGB:")
    lines.append(f"  Có RGB: {rgb.get('exists')}")
    lines.append(f"  Red min/max: {rgb.get('red_min')} / {rgb.get('red_max')}")
    lines.append(f"  Green min/max: {rgb.get('green_min')} / {rgb.get('green_max')}")
    lines.append(f"  Blue min/max: {rgb.get('blue_min')} / {rgb.get('blue_max')}")
    lines.append("")

    scan_angle = attr.get("scan_angle", {})
    lines.append("Scan angle:")
    lines.append(f"  Min: {scan_angle.get('min')}")
    lines.append(f"  Max: {scan_angle.get('max')}")
    lines.append("")

    lines.append("IX. VLR / EVLR")
    lines.append(f"Số VLR: {vlr.get('vlr_count')}")
    lines.append(f"Số EVLR: {vlr.get('evlr_count')}")
    lines.append("")

    lines.append("Danh sách VLR:")
    for item in vlr.get("vlrs", []):
        lines.append(
            f"- user_id={item.get('user_id')}, "
            f"record_id={item.get('record_id')}, "
            f"class={item.get('class')}, "
            f"description={item.get('description')}"
        )
    lines.append("")

    lines.append("X. WKT HỆ TỌA ĐỘ")
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
    print("=== TOOL ĐỌC THÔNG SỐ KỸ THUẬT LAS / LAZ ===")
    print("")

    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        file_path = choose_las_file()

    if not file_path:
        print("❌ Chưa chọn file.")
        return

    file_path = str(Path(file_path).resolve())

    if not os.path.exists(file_path):
        print("❌ File không tồn tại.")
        print(file_path)
        return

    if not file_path.lower().endswith((".las", ".laz")):
        print("⚠️ File không phải .las hoặc .laz, vẫn thử đọc bằng laspy...")

    try:
        print("Đang đọc file:")
        print(file_path)
        print("")
        print("Lưu ý: File lớn có thể mất vài phút vì tool sẽ scan point để thống kê classification và diện tích vùng phủ.")
        print("")

        info = read_las_info(file_path)

        input_path = Path(file_path)
        output_txt = input_path.with_name(f"{input_path.stem}_thong_so_las.txt")
        output_json = input_path.with_name(f"{input_path.stem}_thong_so_las.json")

        write_txt_report(info, output_txt)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        print("✅ Đã đọc xong thông số kỹ thuật LAS/LAZ")
        print(f"📄 TXT : {output_txt}")
        print(f"📄 JSON: {output_json}")
        print("")

        header = info.get("las_header", {})
        crs = info.get("coordinate_reference_system", {})
        area = info.get("area", {})
        possible = info.get("possible_export_time", {})
        best = possible.get("best_guess")

        print("=== TÓM TẮT NHANH ===")
        print(f"Số lượng điểm: {header.get('point_count'):,}")
        print(f"LAS version: {header.get('las_version')}")
        print(f"Point format: {header.get('point_format_id')}")
        print(f"CRS: {crs.get('epsg')} - {crs.get('name')}")
        print("")

        if best:
            print("=== THỜI GIAN EXPORT / GHI FILE CÓ THỂ ===")
            print(f"Thời gian có khả năng nhất: {best.get('value')}")
            print(f"Nguồn: {best.get('source')}")
            print(f"Độ tin cậy: {best.get('confidence')}")
            print("")

        bbox = area.get("bbox_xy", {})
        occupied = area.get("occupied_xy_estimated", {})

        print("=== DIỆN TÍCH / MẬT ĐỘ ===")
        print(f"Diện tích bbox XY: {bbox.get('area_text')}")
        print(f"Mật độ theo bbox: {area.get('point_density_by_bbox_text')}")

        if occupied and occupied.get("can_calculate"):
            print(f"Diện tích vùng phủ ước tính: {occupied.get('occupied_area_text')}")
            print(f"Mật độ theo vùng phủ: {area.get('point_density_by_occupied_area_text')}")
            print(f"Grid size: {occupied.get('grid_size_crs_units')}")
        else:
            reason = occupied.get("reason") if occupied else "Không có dữ liệu occupied area."
            print(f"Diện tích vùng phủ ước tính: Không tính được - {reason}")

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