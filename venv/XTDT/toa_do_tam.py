import os
import geopandas as gpd
import pandas as pd


# Hàm để quét tất cả các tệp geojson trong thư mục
def scan_geojson_files(directory):
    # Danh sách để lưu kết quả
    results = []

    # Quét qua tất cả các tệp trong thư mục
    for filename in os.listdir(directory):
        # Kiểm tra nếu tệp có đuôi .geojson
        if filename.endswith(".geojson"):
            # Lấy tên tệp mà không có phần mở rộng .geojson và loại bỏ phần sau dấu "_"
            base_filename = os.path.splitext(filename)[0].split('_')[0]

            file_path = os.path.join(directory, filename)
            try:
                # Đọc tệp geojson bằng geopandas
                gdf = gpd.read_file(file_path)

                # Kiểm tra nếu dataframe có chứa các polygon
                if gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon']).any():
                    # Kiểm tra CRS hiện tại và chuyển đổi nếu cần thiết
                    if gdf.crs.is_geographic:
                        print(f"Chuyển đổi CRS của tệp {filename} từ hệ tọa độ địa lý sang chiếu.")
                        gdf = gdf.to_crs(epsg=3395)  # Chuyển sang EPSG:3395 (WGS 84/Pseudo-Mercator)

                    # Lấy tọa độ tâm của tất cả các polygon
                    centroids = gdf.geometry.centroid

                    # Chuyển đổi centroid về CRS địa lý (EPSG:4326)
                    centroids = centroids.to_crs(epsg=4326)  # Chuyển về EPSG:4326 (WGS 84)

                    # Lưu kết quả: Tên tệp và tọa độ tâm
                    for i, centroid in enumerate(centroids):
                        # Lấy tọa độ lat, long từ centroid
                        lat = centroid.y
                        long = centroid.x

                        # Lưu tọa độ dưới dạng lat, long và không có dấu ngoặc đơn
                        results.append({
                            "file": base_filename,  # Chỉ lưu tên tệp mà không có phần mở rộng và bỏ phần sau dấu "_"
                            "centroid": f"{lat}, {long}"  # Chỉ lưu tọa độ dưới dạng "lat, long"
                        })
            except Exception as e:
                print(f"Không thể đọc tệp {filename}: {e}")

    return results


# Yêu cầu người dùng nhập đường dẫn thư mục chứa các tệp geojson
directory = input("Nhập đường dẫn thư mục chứa các tệp geojson: ")

# Kiểm tra nếu thư mục tồn tại
if not os.path.isdir(directory):
    print("Đường dẫn không hợp lệ. Vui lòng kiểm tra lại.")
else:
    # Quét các tệp geojson và lấy kết quả
    geojson_centroids = scan_geojson_files(directory)

    # Hiển thị tổng số records đã quét
    total_records = len(geojson_centroids)
    print(f"Tổng số records đã quét: {total_records}")

    # Lưu kết quả vào tệp Excel
    if total_records > 0:
        # Chuyển danh sách kết quả thành DataFrame của pandas
        df = pd.DataFrame(geojson_centroids)

        # Lưu vào tệp Excel
        output_file = os.path.join(directory, "centroids_output.xlsx")
        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Kết quả đã được lưu vào: {output_file}")
    else:
        print("Không có centroid nào để lưu.")
