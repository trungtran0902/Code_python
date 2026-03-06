import os
import geopandas as gpd
import tkinter as tk
from tkinter import filedialog

# Bảng ánh xạ mã loại đất từ dữ liệu bạn cung cấp
loai_dat_dict = {
    # (Dữ liệu ánh xạ đã cung cấp ở trên)
}


# Hàm chọn thư mục chứa shapefile
def select_shapefile_folder():
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính của tkinter
    folder_selected = filedialog.askdirectory(title="Chọn thư mục chứa shapefile")
    return folder_selected


# Hàm chọn thư mục đầu ra
def select_output_folder():
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính của tkinter
    folder_selected = filedialog.askdirectory(title="Chọn thư mục đầu ra")
    return folder_selected


# Hàm xử lý shapefile
def process_shapefile(input_folder, output_folder):
    # In ra đường dẫn đầy đủ đến tệp shapefile để kiểm tra
    shp_file = os.path.join(input_folder, "xabotrach.shp")  # Đổi tên 'tenfile.shp' theo shapefile của bạn
    print(f"Đường dẫn shapefile: {shp_file}")

    # Kiểm tra xem tệp shapefile có tồn tại không
    if not os.path.exists(shp_file):
        print(f"Lỗi: Không tìm thấy tệp shapefile tại {shp_file}")
        return

    output_file = os.path.join(output_folder, "xabotrach_capnhat.shp")

    # Đọc shapefile
    gdf = gpd.read_file(shp_file)

    # Áp dụng bảng ánh xạ cho cột 'Text'
    gdf['LoaiDat'] = gdf['Text'].map(loai_dat_dict)

    # Lưu lại shapefile mới
    gdf.to_file(output_file)
    print(f"Cột 'LoaiDat' đã được thêm vào shapefile và lưu tại {output_file}.")


# Thực thi chương trình
input_folder = select_shapefile_folder()
output_folder = select_output_folder()
process_shapefile(input_folder, output_folder)
