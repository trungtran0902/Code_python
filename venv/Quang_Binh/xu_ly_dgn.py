import arcpy
import os

# Nhập đường dẫn chứa file DGN và tên file DGN từ người dùng
dgn_folder = input("Nhập đường dẫn chứa file DGN: ")
dgn_filename = input("Nhập tên file DGN (ví dụ: yourfile.dgn): ")

# Kết hợp đường dẫn và tên file DGN
dgn_file = os.path.join(dgn_folder, dgn_filename)

# Đảm bảo rằng file DGN tồn tại
if not os.path.exists(dgn_file):
    print(f"File DGN không tồn tại: {dgn_file}")
else:
    print(f"Đang xử lý file: {dgn_file}")

# Nhập tên thư mục đầu ra từ người dùng
output_folder_name = input("Nhập tên thư mục đầu ra (ví dụ: output_folder): ")

# Tạo thư mục đầu ra trong thư mục chứa file DGN
output_folder = os.path.join(dgn_folder, output_folder_name)

# Kiểm tra và tạo thư mục đầu ra nếu chưa tồn tại
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"Thư mục đầu ra đã được tạo: {output_folder}")
else:
    print(f"Thư mục đầu ra đã tồn tại: {output_folder}")

# Đường dẫn đến Geodatabase xuất ra
output_gdb = r"C:\path_to_output.gdb"

# Mở workspace
arcpy.env.workspace = output_gdb

# Tạo các lớp Polyline, Polygon và Annotation
polyline_layer = "Polyline_layer"  # Đặt tên lớp Polyline
polygon_layer = "Polygon_layer"    # Đặt tên lớp Polygon
annotation_layer = "Annotation_layer"  # Đặt tên lớp Annotation

# Tạo kết quả từ Spatial Join cho Polyline và Annotation
polyline_with_annotation = "polyline_with_annotation"
arcpy.analysis.SpatialJoin(polyline_layer, annotation_layer, polyline_with_annotation, join_type="KEEP_COMMON")

# Tạo kết quả từ Spatial Join cho Polygon và Annotation
polygon_with_annotation = "polygon_with_annotation"
arcpy.analysis.SpatialJoin(polygon_layer, annotation_layer, polygon_with_annotation, join_type="KEEP_COMMON")

# Xuất kết quả Spatial Join dưới dạng Shapefile
polyline_shp = os.path.join(output_folder, "polyline_with_annotation.shp")
polygon_shp = os.path.join(output_folder, "polygon_with_annotation.shp")

arcpy.FeatureClassToFeatureClass_conversion(polyline_with_annotation, output_folder, "polyline_with_annotation.shp")
arcpy.FeatureClassToFeatureClass_conversion(polygon_with_annotation, output_folder, "polygon_with_annotation.shp")

print("Shapefile export completed for Polyline and Polygon layers.")

# Xuất kết quả Spatial Join dưới dạng GeoJSON
polyline_geojson = os.path.join(output_folder, "polyline_with_annotation.geojson")
polygon_geojson = os.path.join(output_folder, "polygon_with_annotation.geojson")

# Chuyển đổi từ Feature Class sang GeoJSON
arcpy.FeaturesToJSON_conversion(polyline_with_annotation, polyline_geojson, json_type="FORMATTED")
arcpy.FeaturesToJSON_conversion(polygon_with_annotation, polygon_geojson, json_type="FORMATTED")

print("GeoJSON export completed for Polyline and Polygon layers.")
