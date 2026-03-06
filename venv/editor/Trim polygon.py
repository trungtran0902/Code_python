import os
import math
import geopandas as gpd
from shapely.geometry import box


def auto_grid_shape(n_parts):
    """Tự tính số cột (nx) và hàng (ny) gần vuông nhất từ tổng số phần."""
    nx = math.ceil(math.sqrt(n_parts))
    ny = math.ceil(n_parts / nx)
    return nx, ny


def split_polygon_grid(polygon, nx, ny):
    """Chia polygon thành lưới (nx cột × ny hàng)."""
    minx, miny, maxx, maxy = polygon.bounds
    dx = (maxx - minx) / nx
    dy = (maxy - miny) / ny

    parts = []
    for i in range(nx):
        for j in range(ny):
            grid_cell = box(
                minx + i * dx,
                miny + j * dy,
                minx + (i + 1) * dx,
                miny + (j + 1) * dy
            )
            inter = polygon.intersection(grid_cell)
            if not inter.is_empty:
                parts.append(inter)
    return parts


def get_union_geometry(gdf):
    """Hợp nhất tất cả polygon trong GeoDataFrame (tương thích shapely cũ/mới)."""
    geom = gdf.geometry
    if hasattr(geom, "union_all"):  # Shapely >= 2.0
        return geom.union_all()
    else:  # Shapely < 2.0
        return geom.unary_union


def process_geojson_file(input_path, province_name, output_root, n_parts):
    """Xử lý một file GeoJSON và lưu ra thư mục con/cháu tương ứng."""
    gdf = gpd.read_file(input_path)
    polygon = get_union_geometry(gdf)
    nx, ny = auto_grid_shape(n_parts)
    parts = split_polygon_grid(polygon, nx, ny)

    base_name = os.path.splitext(os.path.basename(input_path))[0]

    # 🔹 Lấy tên xã/phường (bỏ mã số nếu có dạng "_12345")
    subfolder_name = base_name.split("_")[0].strip()

    # 🔹 Tạo đường dẫn đầu ra: Output / [Tỉnh] / [Xã - Phường] /
    output_dir = os.path.join(output_root, province_name, subfolder_name)
    os.makedirs(output_dir, exist_ok=True)

    for idx, part in enumerate(parts, start=1):
        part_gdf = gpd.GeoDataFrame(geometry=[part], crs=gdf.crs)
        output_file = os.path.join(output_dir, f"{base_name}_{idx}.geojson")
        part_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ {province_name}/{subfolder_name}: {len(parts)} phần → {output_dir}")


def main():
    input_root = input("📂 Nhập thư mục gốc chứa các file GeoJSON (vd: XaPhuong): ").strip()
    output_root = input("💾 Nhập thư mục CHA để lưu kết quả (vd: G:\\Relation\\Output): ").strip()
    n_parts = int(input("🔢 Nhập tổng số phần muốn chia (ví dụ 6): ").strip())

    print(f"\n➡️ Bắt đầu duyệt thư mục: {input_root}\n")

    # Duyệt các tỉnh/thành (mỗi thư mục con cấp 1)
    for province in os.listdir(input_root):
        province_path = os.path.join(input_root, province)
        if not os.path.isdir(province_path):
            continue  # bỏ qua file lẻ

        for filename in os.listdir(province_path):
            if filename.lower().endswith(".geojson"):
                input_path = os.path.join(province_path, filename)
                try:
                    process_geojson_file(input_path, province, output_root, n_parts)
                except Exception as e:
                    print(f"❌ Lỗi khi xử lý {province}/{filename}: {e}")

    print("\n🎉 Hoàn tất chia tất cả các file GeoJSON!\n")


if __name__ == "__main__":
    main()
