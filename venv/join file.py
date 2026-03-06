import geopandas as gpd
import pandas as pd

# Đường dẫn tới file
geojson_path = "XTDT_LAMDONG.geojson"     # thay bằng file geojson của bạn
excel_path = "DSKCN.xlsx"        # thay bằng file excel của bạn
output_path = "output_joined_1.geojson"

# Đọc dữ liệu
gdf = gpd.read_file(geojson_path)
df = pd.read_excel(excel_path)

# Làm sạch cột TenDuAn: bỏ khoảng trắng, xuống dòng, viết thường
gdf["TenDuAn_clean"] = gdf["TenDuAn"].astype(str).str.strip().str.lower()
df["TenDuAn_clean"] = df["TenDuAn"].astype(str).str.strip().str.lower()

# Nếu bên GeoJSON có số thứ tự ở đầu (vd: "2.Khu đô thị...") thì bỏ số + dấu chấm
gdf["TenDuAn_clean"] = gdf["TenDuAn_clean"].str.replace(r"^\d+\.*\s*", "", regex=True)
df["TenDuAn_clean"] = df["TenDuAn_clean"].str.replace(r"^\d+\.*\s*", "", regex=True)

# Merge dựa trên cột đã làm sạch
merged = gdf.merge(df, on="TenDuAn_clean", how="left")

# Xuất ra GeoJSON mới
merged.to_file(output_path, driver="GeoJSON")

print("✅ Đã tạo file:", output_path)
