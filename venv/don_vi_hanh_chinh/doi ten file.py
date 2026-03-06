import os
import json
import shutil
from unidecode import unidecode

# ==========================
# B1: Nhập đường dẫn chứa các file geojson
# ==========================
input_folder = input("Nhập đường dẫn chứa các file GeoJSON: ").strip()

# ==========================
# B2: Chọn đường dẫn thư mục lưu file sau khi đổi tên
# ==========================
output_base = input("Nhập đường dẫn thư mục muốn lưu kết quả: ").strip()

# ==========================
# B3: Tạo thư mục con mới
# ==========================
new_folder_name = input("Nhập tên thư mục mới để lưu file: ").strip()

output_folder = os.path.join(output_base, new_folder_name)

# Tạo thư mục nếu chưa tồn tại
os.makedirs(output_folder, exist_ok=True)
print(f"Tạo thư mục mới: {output_folder}")

# ==========================
# B4: Xử lý đổi tên + copy file
# ==========================
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".geojson"):
        file_path = os.path.join(input_folder, filename)

        # Đọc file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Lấy trường "tenDVHC"
        ten = None

        # TH1: properties nằm trực tiếp
        if "properties" in data and "tenDVHC" in data["properties"]:
            ten = data["properties"]["tenDVHC"]

        # TH2: FeatureCollection
        elif "features" in data and len(data["features"]) > 0:
            if "properties" in data["features"][0] and "tenDVHC" in data["features"][0]["properties"]:
                ten = data["features"][0]["properties"]["tenDVHC"]

        # Không tìm thấy
        if ten is None:
            print(f"⚠ Không tìm thấy tenDVHC trong file: {filename}")
            continue

        # Chuẩn hóa tên file
        ten_khong_dau = unidecode(ten)
        ten_file = ten_khong_dau.replace(" ", "_").replace("/", "_")

        new_filename = f"{ten_file}.geojson"
        output_path = os.path.join(output_folder, new_filename)

        # Copy nội dung sang file mới và đổi tên
        shutil.copyfile(file_path, output_path)

        print(f"Đã xử lý: {filename} → {new_filename}")

print("🎉 Hoàn thành xử lý tất cả file!")
