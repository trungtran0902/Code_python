import osmnx as ox
import geopandas as gpd


def roads_from_bbox(min_lat, min_lon, max_lat, max_lon, output_shp):
    """
    Lấy dữ liệu đường từ OpenStreetMap trong bbox và lưu ra shapefile.
    """
    # tạo bbox theo thứ tự (north, south, east, west)
    bbox = (max_lat, min_lat, max_lon, min_lon)

    # Gọi đúng hàm với bbox
    G = ox.graph_from_bbox(bbox, network_type="drive", simplify=True)

    # chuyển graph sang GeoDataFrame edges
    _, gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    # (nếu signature graph_to_gdfs khác, điều chỉnh)

    # lưu shapefile
    gdf_edges.to_file(output_shp, driver="ESRI Shapefile")
    print(f"✅ Đã lưu shapefile đường vào: {output_shp}")
    print(f"👉 Số lượng đoạn đường: {len(gdf_edges)}")
    return gdf_edges


if __name__ == "__main__":
    bbox_str = input("Nhập bounding box (min_lat,min_lon,max_lat,max_lon):\n")
    try:
        min_lat, min_lon, max_lat, max_lon = map(float, bbox_str.split(","))
    except ValueError:
        print("⚠️ Sai định dạng! Ví dụ: 10.753547,106.632957,10.798572,106.715527")
        exit()

    output_file = "roads_bbox.shp"
    gdf = roads_from_bbox(min_lat, min_lon, max_lat, max_lon, output_file)
    print(gdf.head())
