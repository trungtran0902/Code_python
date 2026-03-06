import geopandas as gpd
import os
import zipfile

# File đầu vào
input_path = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\Update_15_9_Tong.geojson"
output_dir = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\output_split"
zip_path = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\output_split.zip"

# Tạo thư mục output nếu chưa có
os.makedirs(output_dir, exist_ok=True)

# Đọc file GeoJSON
gdf = gpd.read_file(input_path)

# Tách từng Feature thành file GeoJSON riêng
for idx, row in gdf.iterrows():
    # Lấy tên dự án, thay khoảng trắng = "_"
    tenduan = str(row["Tên Dự Án"]).strip().replace(" ", "_").replace("/", "_")

    # Nếu tên rỗng thì đặt mặc định
    if tenduan == "" or tenduan.lower() == "nan":
        tenduan = f"duan_{idx}"

    # Tạo GeoDataFrame chỉ chứa 1 feature
    single_gdf = gdf.iloc[[idx]]

    # Lưu file GeoJSON
    out_file = os.path.join(output_dir, f"{tenduan}.geojson")
    single_gdf.to_file(out_file, driver="GeoJSON", encoding="utf-8")

print("✅ Đã tách xong tất cả các file GeoJSON riêng lẻ.")

# Nén thành 1 file ZIP
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(output_dir):
        for file in files:
            file_path = os.path.join(root, file)
            zipf.write(file_path, arcname=file)

print(f"✅ Đã nén toàn bộ file GeoJSON vào: {zip_path}")
