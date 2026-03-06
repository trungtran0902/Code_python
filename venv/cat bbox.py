def divide_region(min_long, min_lat, max_long, max_lat, num_regions):
    regions = []
    if num_regions == 4:
        mid_long = (min_long + max_long) / 2
        mid_lat = (min_lat + max_lat) / 2
        regions = [
            (min_long, min_lat, mid_long, mid_lat),
            (min_long, mid_lat, mid_long, max_lat),
            (mid_long, min_lat, max_long, mid_lat),
            (mid_long, mid_lat, max_long, max_lat)
        ]

    elif num_regions == 5:
        mid_long = (min_long + max_long) / 2
        mid_lat = (min_lat + max_lat) / 2
        regions = [
            (min_long, min_lat, mid_long, mid_lat),
            (min_long, mid_lat, mid_long, max_lat),
            (mid_long, min_lat, max_long, mid_lat),
            (mid_long, mid_lat, max_long, max_lat),
            (mid_long - (max_long - min_long) * 0.2, mid_lat - (max_lat - min_lat) * 0.2,
             mid_long + (max_long - min_long) * 0.2, mid_lat + (max_lat - min_lat) * 0.2)
        ]

    elif num_regions == 6:
        mid_long = (min_long + max_long) / 2
        mid_lat = (min_lat + max_lat) / 2
        regions = [
            (min_long, min_lat, mid_long, mid_lat),
            (min_long, mid_lat, mid_long, max_lat),
            (mid_long, min_lat, max_long, mid_lat),
            (mid_long, mid_lat, max_long, max_lat),
            (min_long, mid_lat - (max_lat - min_lat) * 0.2, mid_long, mid_lat),
            (mid_long, mid_lat, max_long, mid_lat + (max_lat - min_lat) * 0.2)
        ]

    elif num_regions == 8:
        # 2 hàng, 4 cột
        long_step = (max_long - min_long) / 4
        lat_step = (max_lat - min_lat) / 2
        for i in range(2):  # rows
            for j in range(4):  # cols
                region_min_long = min_long + j * long_step
                region_max_long = region_min_long + long_step
                region_min_lat = min_lat + i * lat_step
                region_max_lat = region_min_lat + lat_step
                regions.append((region_min_long, region_min_lat, region_max_long, region_max_lat))

    return regions


# ✅ Nhập dữ liệu đầu vào
input_data = input("Nhập min_long,min_lat,max_long,max_lat (VD: 105.0767,23.2393,105.4626,23.4058): ")
try:
    min_long, min_lat, max_long, max_lat = map(float, input_data.strip().split(','))
except ValueError:
    print("❌ Dữ liệu đầu vào không hợp lệ. Vui lòng nhập đúng định dạng.")
    exit()

# ✅ Nhập số lượng vùng
try:
    num_regions = int(input("Nhập số lượng vùng nhỏ (4, 5, 6 hoặc 8): "))
    if num_regions not in [4, 5, 6, 8]:
        raise ValueError
except ValueError:
    print("❌ Số vùng không hợp lệ. Chỉ chấp nhận 4, 5, 6 hoặc 8.")
    exit()

# ✅ Gọi hàm và in kết quả
regions = divide_region(min_long, min_lat, max_long, max_lat, num_regions)
print("\n📍 Các vùng nhỏ:")
for i, region in enumerate(regions, 1):
    print(f"Vùng {i}: ({region[0]:.6f}, {region[1]:.6f}, {region[2]:.6f}, {region[3]:.6f})")
