import geopandas as gpd
import tkinter as tk
from tkinter import filedialog
import os
import pandas as pd
import time

# -------------------------------
# B1: chọn file đường
# -------------------------------
root = tk.Tk()
root.withdraw()

road_file = filedialog.askopenfilename(
    title="Chọn file GeoJSON đường sá",
    filetypes=[("GeoJSON", "*.geojson"), ("All files", "*.*")]
)

# -------------------------------
# B2: chọn folder polygon
# -------------------------------
polygon_folder = filedialog.askdirectory(
    title="Chọn thư mục chứa polygon phường xã"
)

start_total = time.time()

print("Đang đọc dữ liệu đường...")

roads = gpd.read_file(road_file)

if roads.crs.is_geographic:
    roads = roads.to_crs(3857)

# spatial index
roads_sindex = roads.sindex

print("Tạo spatial index xong")

results = []

files = [f for f in os.listdir(polygon_folder)
         if f.endswith(".geojson") or f.endswith(".shp")]

print("Tổng số polygon:", len(files))

# -------------------------------
# xử lý từng polygon
# -------------------------------
for i, file in enumerate(files):

    start = time.time()

    print("--------------------------------------------------")
    print(f"Đang xử lý {i+1}/{len(files)} : {file}")

    path = os.path.join(polygon_folder, file)
    polygon = gpd.read_file(path)

    if polygon.crs != roads.crs:
        polygon = polygon.to_crs(roads.crs)

    poly_geom = polygon.unary_union

    # spatial filter
    possible_index = list(roads_sindex.intersection(poly_geom.bounds))
    candidate_roads = roads.iloc[possible_index]

    print("Số đường candidate:", len(candidate_roads))

    # clip
    roads_clip = candidate_roads.clip(poly_geom)

    print("Số đường sau clip:", len(roads_clip))

    if len(roads_clip) == 0:
        road_area = 0
    else:
        buffer_dist = 10
        road_area = roads_clip.buffer(buffer_dist).unary_union.area

    poly_area = poly_geom.area

    results.append({
        "phuong_xa": os.path.splitext(file)[0],
        "dien_tich_polygon_m2": poly_area,
        "dien_tich_co_duong_m2": road_area,
        "ty_le_duong_%": (road_area/poly_area*100) if poly_area > 0 else 0
    })

    end = time.time()
    print("Thời gian xử lý:", round(end-start,2), "giây")

# -------------------------------
# B3: xuất thống kê
# -------------------------------
df = pd.DataFrame(results)

save_file = filedialog.asksaveasfilename(
    title="Lưu file thống kê",
    defaultextension=".xlsx",
    filetypes=[("Excel", "*.xlsx")]
)

df.to_excel(save_file, index=False)

end_total = time.time()

print("==================================================")
print("HOÀN THÀNH")
print("Tổng thời gian chạy:", round(end_total-start_total,2), "giây")