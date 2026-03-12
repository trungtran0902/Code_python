import os
import math
import cv2
import numpy as np
import geopandas as gpd

from tkinter import Tk, filedialog
from shapely.geometry import LineString
try:
    from skimage.morphology import skeletonize as skimage_skeletonize
except ImportError:
    skimage_skeletonize = None


# =========================================================
# CONFIG
# =========================================================

# Nếu có bounding box thật của ảnh thì điền vào đây:
# (min_lon, min_lat, max_lon, max_lat)
# Ví dụ:
# BBOX_WGS84 = (106.6700, 10.7400, 106.6900, 10.7600)
#
# Nếu không có georeference, để None.
BBOX_WGS84 = None

# Thư mục output
OUTPUT_DIR_NAME = "road_output"

# Tham số xử lý
GAUSSIAN_KERNEL = (5, 5)

# Hough parameters
HOUGH_THRESHOLD = 40
MIN_LINE_LENGTH = 60
MAX_LINE_GAP = 20

# Lọc line
KEEP_MASK_RATIO = 0.60       # ít nhất 60% điểm mẫu của line phải nằm trên road mask
MIN_ACCEPTED_LENGTH = 80     # bỏ line quá ngắn
DUP_ANGLE_THRESH = 8         # độ
DUP_DIST_THRESH = 18         # pixel

# Connected component filtering trên mask
MIN_COMPONENT_AREA = 120
MIN_COMPONENT_WIDTH = 3
MIN_COMPONENT_HEIGHT = 3


# =========================================================
# GUI CHỌN ẢNH
# =========================================================

def choose_image():
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Chọn ảnh vệ tinh",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
            ("All files", "*.*")
        ]
    )
    return file_path


# =========================================================
# HÀM PHỤ
# =========================================================

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def line_length(line):
    x1, y1, x2, y2 = line
    return math.hypot(x2 - x1, y2 - y1)


def line_angle_deg(line):
    x1, y1, x2, y2 = line
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    # chuẩn hóa về [0, 180)
    if ang < 0:
        ang += 180
    return ang


def midpoint(line):
    x1, y1, x2, y2 = line
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def point_line_distance(px, py, line):
    x1, y1, x2, y2 = line
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def sample_line_points(line, n=25):
    x1, y1, x2, y2 = line
    xs = np.linspace(x1, x2, n)
    ys = np.linspace(y1, y2, n)
    pts = np.stack([xs, ys], axis=1).astype(int)
    return pts


def compute_mask_ratio(line, mask, n=25):
    h, w = mask.shape[:2]
    pts = sample_line_points(line, n=n)

    valid = 0
    hit = 0
    for x, y in pts:
        if 0 <= x < w and 0 <= y < h:
            valid += 1
            if mask[y, x] > 0:
                hit += 1

    if valid == 0:
        return 0.0
    return hit / valid


def are_lines_duplicate(line_a, line_b,
                        angle_thresh=DUP_ANGLE_THRESH,
                        dist_thresh=DUP_DIST_THRESH):
    ang_a = line_angle_deg(line_a)
    ang_b = line_angle_deg(line_b)

    # chênh lệch góc có tính wrap 180 độ
    diff = abs(ang_a - ang_b)
    diff = min(diff, 180 - diff)
    if diff > angle_thresh:
        return False

    mx, my = midpoint(line_a)
    d = point_line_distance(mx, my, line_b)
    return d <= dist_thresh


def deduplicate_lines(lines):
    if not lines:
        return []

    # sort theo độ dài giảm dần để giữ line dài trước
    lines_sorted = sorted(lines, key=line_length, reverse=True)
    kept = []

    for line in lines_sorted:
        duplicate = False
        for k in kept:
            if are_lines_duplicate(line, k):
                duplicate = True
                break
        if not duplicate:
            kept.append(line)

    return kept


def pixel_to_wgs84(x, y, width, height, bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    lon = min_lon + (x / width) * (max_lon - min_lon)
    lat = max_lat - (y / height) * (max_lat - min_lat)
    return lon, lat


def line_to_geometry(line, width, height, bbox=None):
    x1, y1, x2, y2 = line

    if bbox is None:
        return LineString([(float(x1), float(y1)), (float(x2), float(y2))])

    lon1, lat1 = pixel_to_wgs84(x1, y1, width, height, bbox)
    lon2, lat2 = pixel_to_wgs84(x2, y2, width, height, bbox)
    return LineString([(lon1, lat1), (lon2, lat2)])


def save_overlay(image, lines, out_path):
    vis = image.copy()
    for x1, y1, x2, y2 in lines:
        cv2.line(vis, (x1, y1), (x2, y2), (0, 0, 255), 2)
    cv2.imwrite(out_path, vis)


def normalize_gray(gray):
    return cv2.equalizeHist(gray)


def remove_small_components(binary_mask,
                            min_area=MIN_COMPONENT_AREA,
                            min_w=MIN_COMPONENT_WIDTH,
                            min_h=MIN_COMPONENT_HEIGHT):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask, connectivity=8)

    out = np.zeros_like(binary_mask)
    for i in range(1, num_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]

        if area >= min_area and w >= min_w and h >= min_h:
            out[labels == i] = 255

    return out


# =========================================================
# ROAD MASK
# =========================================================

def build_road_mask(img_bgr):
    """
    Tạo road mask theo hướng classical CV:
    - loại cây xanh
    - loại nước
    - ưu tiên vùng xám / ít bão hòa
    - tăng cường edges
    - morphology để nối vùng
    """

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = normalize_gray(gray)

    h, s, v = cv2.split(hsv)

    # -----------------------------
    # 1) Mask cây xanh
    # -----------------------------
    green_mask = cv2.inRange(
        hsv,
        np.array([35, 35, 25], dtype=np.uint8),
        np.array([95, 255, 255], dtype=np.uint8)
    )

    # -----------------------------
    # 2) Mask nước tối xanh
    # -----------------------------
    water_mask_1 = cv2.inRange(
        hsv,
        np.array([85, 40, 10], dtype=np.uint8),
        np.array([140, 255, 160], dtype=np.uint8)
    )

    # nước rất tối trong gray
    water_mask_2 = cv2.inRange(gray, 0, 55)

    water_mask = cv2.bitwise_or(water_mask_1, water_mask_2)

    # loại bớt false positive bằng open
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel_small, iterations=1)
    water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, kernel_small, iterations=1)

    # -----------------------------
    # 3) Candidate đường:
    #    đường thường ít bão hòa, sáng vừa hoặc hơi tối
    # -----------------------------
    low_sat_mask = cv2.inRange(s, 0, 70)
    mid_val_mask = cv2.inRange(v, 70, 220)

    gray_candidate = cv2.bitwise_and(low_sat_mask, mid_val_mask)

    # -----------------------------
    # 4) Edge để hỗ trợ đường
    # -----------------------------
    blur = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, 0)
    edges = cv2.Canny(blur, 60, 150)

    # làm dày edge nhẹ
    edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges_dilated = cv2.dilate(edges, edge_kernel, iterations=1)

    # -----------------------------
    # 5) Kết hợp
    # -----------------------------
    road_mask = cv2.bitwise_and(gray_candidate, cv2.bitwise_not(green_mask))
    road_mask = cv2.bitwise_and(road_mask, cv2.bitwise_not(water_mask))

    # kết hợp edges để nhấn tuyến
    road_mask = cv2.bitwise_or(road_mask, edges_dilated)

    # -----------------------------
    # 6) Morphology làm sạch
    # -----------------------------
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)

    # loại component rất nhỏ
    road_mask = remove_small_components(road_mask)

    return road_mask, green_mask, water_mask


# =========================================================
# SKELETON MASK
# =========================================================

def skeletonize_fallback(binary):
    # Morphological skeletonization using only OpenCV.
    img = (binary > 0).astype(np.uint8) * 255
    skel = np.zeros_like(img)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))

    while True:
        eroded = cv2.erode(img, kernel)
        temp = cv2.dilate(eroded, kernel)
        temp = cv2.subtract(img, temp)
        skel = cv2.bitwise_or(skel, temp)
        img = eroded
        if cv2.countNonZero(img) == 0:
            break

    return skel


def make_skeleton(binary_mask):
    """
    Skeleton để làm mask mảnh hơn cho line sampling.
    """
    binary = (binary_mask > 0).astype(np.uint8)
    if skimage_skeletonize is not None:
        skel = skimage_skeletonize(binary).astype(np.uint8) * 255
    else:
        skel = skeletonize_fallback(binary)

    # làm dày chút để sample line dễ hit
    skel = cv2.dilate(skel, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
    return skel


# =========================================================
# LINE DETECTION + FILTER
# =========================================================

def detect_lines_from_mask(mask):
    lines = cv2.HoughLinesP(
        mask,
        rho=1,
        theta=np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=MIN_LINE_LENGTH,
        maxLineGap=MAX_LINE_GAP
    )

    out = []
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = l[0]
            out.append((int(x1), int(y1), int(x2), int(y2)))
    return out


def filter_lines(lines, road_mask, water_mask, green_mask):
    kept = []

    for line in lines:
        length = line_length(line)
        if length < MIN_ACCEPTED_LENGTH:
            continue

        road_ratio = compute_mask_ratio(line, road_mask, n=35)
        if road_ratio < KEEP_MASK_RATIO:
            continue

        water_ratio = compute_mask_ratio(line, water_mask, n=35)
        if water_ratio > 0.25:
            continue

        green_ratio = compute_mask_ratio(line, green_mask, n=35)
        if green_ratio > 0.20:
            continue

        kept.append(line)

    kept = deduplicate_lines(kept)
    return kept


# =========================================================
# EXPORT GEOJSON
# =========================================================

def export_geojson(lines, width, height, out_geojson, bbox=None):
    geoms = [line_to_geometry(line, width, height, bbox=bbox) for line in lines]

    if bbox is None:
        gdf = gpd.GeoDataFrame(
            {"id": list(range(1, len(geoms) + 1))},
            geometry=geoms
        )
    else:
        gdf = gpd.GeoDataFrame(
            {"id": list(range(1, len(geoms) + 1))},
            geometry=geoms,
            crs="EPSG:4326"
        )

    gdf.to_file(out_geojson, driver="GeoJSON")


# =========================================================
# MAIN
# =========================================================

def main():
    file_path = choose_image()
    if not file_path:
        print("Không chọn ảnh.")
        return

    print("Ảnh đã chọn:", file_path)

    img = cv2.imread(file_path)
    if img is None:
        print("Không đọc được ảnh.")
        return

    h, w = img.shape[:2]

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(os.path.dirname(file_path), OUTPUT_DIR_NAME)
    ensure_dir(output_dir)

    mask_path = os.path.join(output_dir, f"{base_name}_road_mask.png")
    skel_path = os.path.join(output_dir, f"{base_name}_road_skeleton.png")
    overlay_path = os.path.join(output_dir, f"{base_name}_roads_overlay.png")
    geojson_path = os.path.join(output_dir, f"{base_name}_roads.geojson")

    # 1) build road mask
    road_mask, green_mask, water_mask = build_road_mask(img)
    cv2.imwrite(mask_path, road_mask)

    # 2) skeleton
    road_skeleton = make_skeleton(road_mask)
    cv2.imwrite(skel_path, road_skeleton)

    # 3) detect raw lines
    raw_lines = detect_lines_from_mask(road_skeleton)
    print("Số line thô:", len(raw_lines))

    # 4) filter lines
    filtered_lines = filter_lines(raw_lines, road_mask, water_mask, green_mask)
    print("Số line sau lọc:", len(filtered_lines))

    # 5) save overlay
    save_overlay(img, filtered_lines, overlay_path)

    # 6) export geojson
    export_geojson(filtered_lines, w, h, geojson_path, bbox=BBOX_WGS84)

    print("\nHoàn tất.")
    print("Mask:", mask_path)
    print("Skeleton:", skel_path)
    print("Overlay:", overlay_path)
    print("GeoJSON:", geojson_path)

    if BBOX_WGS84 is None:
        print("\nLưu ý:")
        print("- GeoJSON hiện đang ở tọa độ pixel, không phải WGS84.")
        print("- Mở được trong QGIS như dữ liệu local.")
        print("- geojson.io sẽ báo lỗi nếu chưa gán bbox WGS84 thật.")
    else:
        print("\nGeoJSON đã xuất theo WGS84 (EPSG:4326).")


if __name__ == "__main__":
    main()
