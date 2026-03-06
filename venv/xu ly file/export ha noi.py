import pandas as pd

# Danh sách 51 phường
phuong = [
    "Hoàn Kiếm", "Cửa Nam", "Ba Đình", "Ngọc Hà", "Giảng Võ",
    "Hai Bà Trưng", "Vĩnh Tuy", "Bạch Mai", "Đống Đa", "Kim Liên",
    "Văn Miếu – Quốc Tử Giám", "Láng", "Ô Chợ Dừa", "Hồng Hà", "Lĩnh Nam",
    "Hoàng Mai", "Vĩnh Hưng", "Tương Mai", "Định Công", "Hoàng Liệt",
    "Yên Sở", "Thanh Xuân", "Khương Đình", "Phương Liệt", "Cầu Giấy",
    "Nghĩa Đô", "Yên Hòa", "Tây Hồ", "Phú Thượng", "Tây Tựu",
    "Phú Diễn", "Xuân Đỉnh", "Đông Ngạc", "Thượng Cát", "Từ Liêm",
    "Xuân Phương", "Tây Mỗ", "Đại Mỗ", "Long Biên", "Bồ Đề",
    "Việt Hưng", "Phúc Lợi", "Hà Đông", "Dương Nội", "Yên Nghĩa",
    "Phú Lương", "Kiến Hưng", "Thanh Liệt", "Chương Mỹ", "Sơn Tây", "Tùng Thiện"
]

# Danh sách 75 xã
xa = [
    "Thanh Trì", "Nam Phù", "Ngọc Hồi", "Thượng Phúc", "Thường Tín",
    "Chương Dương", "Hồng Vân", "Phú Xuyên", "Phượng Dực", "Chuyên Mỹ",
    "Đại Xuyên", "Thanh Oai", "Bình Minh", "Tam Hưng", "Dân Hòa",
    "Vân Đình", "Ứng Thiên", "Hòa Xá", "Ứng Hòa", "Mỹ Đức",
    "Hồng Sơn", "Phúc Sơn", "Hương Sơn", "Phú Nghĩa", "Xuân Mai",
    "Trần Phú", "Hòa Phú", "Quảng Bị", "Minh Châu", "Quảng Oai",
    "Vật Lại", "Cổ Đô", "Bất Bạt", "Suối Hai", "Ba Vì",
    "Yên Bài", "Đoài Phương", "Phúc Thọ", "Phúc Lộc", "Hát Môn",
    "Thạch Thất", "Hạ Bằng", "Tây Phương", "Hòa Lạc", "Yên Xuân",
    "Quốc Oai", "Hưng Đạo", "Kiều Phú", "Phú Cát", "Hoài Đức",
    "Dương Hòa", "Sơn Đồng", "An Khánh", "Đan Phượng", "Ô Diên",
    "Liên Minh", "Gia Lâm", "Thuận An", "Bát Tràng", "Phù Đổng",
    "Thư Lâm", "Đông Anh", "Phúc Thịnh", "Thiên Lộc", "Mê Linh",
    "Yên Lãng", "Tiến Thắng", "Quang Minh", "Sóc Sơn", "Đa Phúc",
    "Nội Bài", "Trung Giã", "Kim Anh"
]

# Tạo DataFrame
df_phuong = pd.DataFrame({"Loại": "Phường", "Tên": phuong})
df_xa = pd.DataFrame({"Loại": "Xã", "Tên": xa})

# Gộp 2 bảng
df = pd.concat([df_phuong, df_xa], ignore_index=True)

# Xuất ra file Excel
output_path = "ds_phuong_xa_ha_noi.xlsx"
df.to_excel(output_path, index=False)

print(f"Đã tạo file Excel: {output_path}")
