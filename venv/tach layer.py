import json
import os

def sanitize_filename(name: str) -> str:
    """Làm sạch tên file, tránh lỗi ký tự đặc biệt."""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name).strip()

def split_geojson_by_tenduan(input_file: str, output_dir: str):
    # Đọc file GeoJSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Tạo thư mục output nếu chưa có
    os.makedirs(output_dir, exist_ok=True)

    layers = {}

    # Gom feature theo trường TenDuAn
    for feature in data.get('features', []):
        project_name = feature.get('properties', {}).get('TenDuAn', "unknown")
        safe_name = sanitize_filename(str(project_name))

        if safe_name not in layers:
            layers[safe_name] = {"type": "FeatureCollection", "features": []}
        layers[safe_name]["features"].append(feature)

    # Xuất file cho từng TenDuAn
    for layer_name, layer_data in layers.items():
        output_file = os.path.join(output_dir, f"{layer_name}.geojson")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(layer_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu: {output_file}")

if __name__ == "__main__":
    # Nhập đường dẫn, tên file, và tên thư mục đầu ra
    input_path = input("Nhập đường dẫn chứa file GeoJSON: ").strip()
    file_name = input("Nhập tên file GeoJSON (bao gồm .geojson): ").strip()
    output_folder_name = input("Nhập tên thư mục đầu ra: ").strip()

    # Tạo đường dẫn đầy đủ cho file input
    input_geojson_file = os.path.join(input_path, file_name)

    # Thư mục đầu ra = đường dẫn input + tên thư mục
    output_directory = os.path.join(input_path, output_folder_name)

    # Gọi hàm tách file
    split_geojson_by_tenduan(input_geojson_file, output_directory)
