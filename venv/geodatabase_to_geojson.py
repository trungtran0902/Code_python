import geopandas as gpd

# Bước 1: Nhập đường dẫn file Geodatabase
gdb_file = input("Nhập đường dẫn file Geodatabase (ví dụ: 'C:/path/to/your/file.gdb'): ")


# Hàm để hiển thị tất cả các lớp trong Geodatabase, bao gồm các lớp con trong dataset
def show_layers(gdb_file):
    try:
        # Đọc tất cả các lớp trong Geodatabase
        layers = gpd.read_file(gdb_file, layer=None)  # layer=None để lấy tất cả lớp

        # Hiển thị tất cả các lớp con trong dataset
        print("\nCác lớp trong Geodatabase này:")
        for layer in layers:
            print(f"- {layer}")

        return list(layers.keys())  # Trả về danh sách các lớp
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
        return []


# Bước 2: Hiển thị tất cả các lớp cần chuyển đổi
layers = show_layers(gdb_file)

if not layers:
    print("Không tìm thấy lớp nào trong Geodatabase.")
else:
    # Bước 3: Nhập tên lớp cần chuyển đổi
    while True:
        layer_name = input("\nNhập tên lớp cần chuyển đổi (hoặc nhập 'exit' để thoát): ")

        if layer_name == 'exit':
            print("Thoát chương trình.")
            break

        if layer_name in layers:
            # Bước 4: Chuyển đổi Geodatabase sang GeoJSON
            try:
                gdf = gpd.read_file(gdb_file, layer=layer_name)  # Chỉ định lớp cần đọc
                geojson_file = f'{layer_name}.geojson'
                gdf.to_file(geojson_file, driver='GeoJSON')
                print(f'Lớp "{layer_name}" đã được chuyển thành {geojson_file}')
            except Exception as e:
                print(f"Đã xảy ra lỗi khi chuyển đổi lớp {layer_name}: {e}")

            # Bước 5: Hỏi có tiếp tục không
            continue_prompt = input("\nBạn có muốn tiếp tục chuyển đổi lớp khác không? (y/n): ").strip().lower()
            if continue_prompt != 'y':
                print("Thoát chương trình.")
                break
        else:
            print("Tên lớp không hợp lệ. Vui lòng nhập lại.")
