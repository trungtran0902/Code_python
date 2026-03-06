# ===============================================================
# process_postal_code.py
# Tự động thêm postal_old (63 tỉnh cũ) và postal_new (34 tỉnh mới)
# dựa vào old_admin_level_2 và admin_level_2 trong file Excel
# ===============================================================

import os
import pandas as pd


# ===========================================================================
#  POSTAL_OLD — 63 TỈNH / THÀNH CŨ
# ===========================================================================
POSTAL_OLD = {
    "Thành phố Hà Nội": "100000",
    "Tỉnh Hà Giang": "310000",
    "Tỉnh Cao Bằng": "270000",
    "Tỉnh Bắc Kạn": "230000",
    "Tỉnh Tuyên Quang": "300000",
    "Tỉnh Lào Cai": "330000",
    "Tỉnh Điện Biên": "380000",
    "Tỉnh Lai Châu": "390000",
    "Tỉnh Sơn La": "360000",
    "Tỉnh Yên Bái": "320000",
    "Tỉnh Hoà Bình": "350000",
    "Tỉnh Thái Nguyên": "250000",
    "Tỉnh Lạng Sơn": "240000",
    "Tỉnh Quảng Ninh": "200000",
    "Tỉnh Bắc Giang": "260000",
    "Tỉnh Phú Thọ": "290000",
    "Tỉnh Vĩnh Phúc": "280000",
    "Tỉnh Bắc Ninh": "160000",
    "Thành phố Hải Dương": "170000",
    "Thành phố Hải Phòng": "180000",
    "Tỉnh Hưng Yên": "150000",
    "Tỉnh Thái Bình": "060000",
    "Tỉnh Hà Nam": "400000",
    "Tỉnh Nam Định": "070000",
    "Tỉnh Ninh Bình": "420000",
    "Tỉnh Thanh Hóa": "440000",
    "Tỉnh Nghệ An": "430000",
    "Tỉnh Hà Tĩnh": "450000",
    "Tỉnh Quảng Bình": "510000",
    "Tỉnh Quảng Trị": "520000",
    "Tỉnh Thừa Thiên Huế": "530000",
    "Thành phố Đà Nẵng": "550000",
    "Tỉnh Quảng Nam": "560000",
    "Tỉnh Quảng Ngãi": "570000",
    "Tỉnh Bình Định": "550000",
    "Tỉnh Phú Yên": "620000",
    "Tỉnh Khánh Hòa": "650000",
    "Tỉnh Ninh Thuận": "660000",
    "Tỉnh Bình Thuận": "770000",
    "Tỉnh Kon Tum": "580000",
    "Tỉnh Gia Lai": "600000",
    "Tỉnh Đắk Lắk": "630000",
    "Tỉnh Đắk Nông": "640000",
    "Tỉnh Lâm Đồng": "670000",
    "Tỉnh Bình Phước": "830000",
    "Tỉnh Tây Ninh": "800000",
    "Tỉnh Bình Dương": "820000",
    "Tỉnh Đồng Nai": "810000",
    "Thành phố Hồ Chí Minh": "700000",
    "Tỉnh Long An": "850000",
    "Tỉnh Tiền Giang": "860000",
    "Tỉnh Bến Tre": "930000",
    "Tỉnh Trà Vinh": "870000",
    "Tỉnh Vĩnh Long": "890000",
    "Tỉnh Đồng Tháp": "870000",
    "Tỉnh An Giang": "880000",
    "Tỉnh Kiên Giang": "920000",
    "Thành phố Cần Thơ": "900000",
    "Tỉnh Hậu Giang": "910000",
    "Tỉnh Sóc Trăng": "960000",
    "Tỉnh Bạc Liêu": "970000",
    "Tỉnh Cà Mau": "980000"
}


# ===========================================================================
#  POSTAL_NEW — 34 TỈNH MỚI (SAU SÁP NHẬP 2025)
# ===========================================================================
POSTAL_NEW = {
    "Tỉnh Cao Bằng": "02000",
    "Tỉnh Lạng Sơn": "25000",
    "Tỉnh Lào Cai": "27000",
    "Tỉnh Lai Châu": "13000",
    "Tỉnh Điện Biên": "14000",
    "Tỉnh Sơn La": "11000",
    "Tỉnh Tuyên Quang": "25000",
    "Tỉnh Thái Nguyên": "23000",
    "Tỉnh Phú Thọ": "21000",
    "Thành phố Hà Nội": "10000",
    "Tỉnh Bắc Ninh": "22000",
    "Tỉnh Quảng Ninh": "20000",
    "Tỉnh Hưng Yên": "17000",
    "Thành phố Hải Phòng": "15000",
    "Tỉnh Ninh Bình": "19000",
    "Tỉnh Thanh Hóa": "36000",
    "Tỉnh Nghệ An": "37000",
    "Tỉnh Hà Tĩnh": "38000",
    "Tỉnh Quảng Trị": "52000",
    "Thành phố Huế": "53000",
    "Thành Phố Đà Nẵng": "58000",
    "Tỉnh Quảng Ngãi": "57000",
    "Tỉnh Gia Lai": "63000",
    "Tỉnh Khánh Hòa": "65000",
    "Tỉnh Lâm Đồng": "66000",
    "Tỉnh Đắk Lắk": "67000",
    "Thành phố Hồ Chí Minh": "70000",
    "Tỉnh Đồng Nai": "92000",
    "Tỉnh Tây Ninh": "80000",
    "Tỉnh Thành phố Cần Thơ": "95000",
    "Tỉnh Vĩnh Long": "98000",
    "Tỉnh Đồng Tháp": "83000",
    "Tỉnh Cà Mau": "94000",
    "Tỉnh An Giang": "91000"
}


# ===========================================================================
#  HÀM CHUẨN HÓA TÊN TỈNH
# ===========================================================================
def norm(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    return s


# ===========================================================================
#  TRA POSTAL CODE
# ===========================================================================
def get_old_postal(province):
    return POSTAL_OLD.get(norm(province), "")

def get_new_postal(province):
    return POSTAL_NEW.get(norm(province), "")


# ===========================================================================
#  CHƯƠNG TRÌNH CHÍNH
# ===========================================================================
def main():
    print("\n=== TOOL TẠO postal_old & postal_new ===")

    folder = input("B1. Nhập đường dẫn chứa file Excel: ").strip()
    filename = input("B2. Nhập tên file Excel (vd: data.xlsx): ").strip()

    path = os.path.join(folder, filename)

    if not os.path.exists(path):
        print("❌ File không tồn tại:", path)
        return

    print("⏳ Đang đọc file:", path)
    df = pd.read_excel(path)

    required = ["old_admin_level_2", "admin_level_2"]
    for c in required:
        if c not in df.columns:
            print(f"❌ Không tìm thấy cột {c} trong file Excel.")
            return

    print("⏳ Đang xử lý...")

    df["postal_old"] = df["old_admin_level_2"].apply(get_old_postal)
    df["postal_new"] = df["admin_level_2"].apply(get_new_postal)

    out_path = os.path.join(folder, "postal_output.xlsx")
    df.to_excel(out_path, index=False)

    print("\n✅ Hoàn tất!")
    print("📁 File xuất:", out_path)


if __name__ == "__main__":
    main()
