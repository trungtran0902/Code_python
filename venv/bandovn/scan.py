import json
import csv
import glob
import os

# -----------------------------------
# Thư mục đầu ra cố định
OUTPUT_DIR = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\bandovn\ket_qua_sapnhap"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cột chuẩn hóa
FIELDS = [
    "tentinh",
    "tenxa",
    "loai",
    "matinh",
    "maxa",
    "danso",
    "dientich_km2",
    "trungtam_hc",
    "truoc_sapnhap",
    "kinhdo",
    "vido",
]

def normalize_record(x):
    """Chuẩn hóa dữ liệu JSON sang dict đúng cột"""
    return {
        "tentinh": x.get("tentinh"),
        "tenxa": x.get("tenhc"),
        "loai": x.get("loai"),
        "matinh": x.get("matinh"),
        "maxa": x.get("maxa") or x.get("id"),
        "danso": x.get("dansonguoi"),
        "dientich_km2": x.get("dientichkm2"),
        "trungtam_hc": x.get("trungtamhc"),
        "truoc_sapnhap": x.get("truocsapnhap"),
        "kinhdo": x.get("kinhdo"),
        "vido": x.get("vido"),
    }

def process_files(input_dir):
    """Đọc từng file JSON/TXT và tạo file CSV trùng tên trong OUTPUT_DIR"""
    if not os.path.exists(input_dir):
        print(f"❌ Thư mục '{input_dir}' không tồn tại.")
        return

    files = sorted(
        glob.glob(os.path.join(input_dir, "*.txt")) +
        glob.glob(os.path.join(input_dir, "*.json"))
    )

    if not files:
        print(f"⚠️ Không tìm thấy file .txt hoặc .json nào trong {input_dir}")
        return

    for file in files:
        name = os.path.splitext(os.path.basename(file))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{name}.csv")

        print(f"📄 Đang xử lý: {name}")

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"⚠️ Bỏ qua {file}: lỗi đọc hoặc JSON không hợp lệ ({e})")
            continue

        rows = [normalize_record(x) for x in data if isinstance(x, dict)]
        if not rows:
            print(f"⚠️ Không có dữ liệu hợp lệ trong {file}")
            continue

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ Đã lưu {len(rows)} dòng → {out_path}\n")

    print(f"🎉 Hoàn tất! Tất cả file CSV được lưu tại:\n📁 {OUTPUT_DIR}")

# -----------------------------------
if __name__ == "__main__":
    print("📂 Nhập đường dẫn thư mục chứa các file JSON/TXT (ví dụ: D:/dulieu_tinh):")
    folder = input("➡️ Thư mục: ").strip().strip('"')

    process_files(folder)
