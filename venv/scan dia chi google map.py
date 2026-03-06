import pandas as pd
import time
import os
from playwright.sync_api import sync_playwright

# 🔹 Đường dẫn file Excel đầu vào và CSV đầu ra
input_file = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\danh_sach_cong_ty.xlsx"
output_file = r"C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\toado_longan.csv"
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# 🔹 Đọc dữ liệu từ file Excel
df = pd.read_excel(input_file)
records = df[["Tên doanh nghiệp", "Mã số thuế", "Người đại diện", "Địa chỉ"]].dropna()
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)  # slow_mo để theo dõi thao tác
    page = browser.new_page()

    for i, row in records.iterrows():
        ten_cty = row["Tên doanh nghiệp"]
        ma_so_thue = row["Mã số thuế"]
        dai_dien = row["Người đại diện"]
        dia_chi = row["Địa chỉ"]

        try:
            print(f"{i+1:02d}: 🔍 {dia_chi}")
            page.goto("https://www.google.com/maps", timeout=60000)
            time.sleep(3)

            # Gõ địa chỉ vào ô tìm kiếm
            search_box = page.query_selector("input[role='combobox']")
            if search_box is None:
                raise Exception("❌ Không tìm thấy ô tìm kiếm.")

            search_box.fill(dia_chi)
            time.sleep(1)
            search_box.press("Enter")
            time.sleep(5)  # Chờ kết quả hiển thị

            # 🔁 Click vào khung kết quả (nếu có) để URL cập nhật tọa độ chính xác
            # Google Maps thường hiển thị tiêu đề trong thẻ h1 hoặc button trong div[role="main"]
            result_panel = page.query_selector("div[role='main'] h1") or page.query_selector("h1 span")
            if result_panel:
                result_panel.click()
                time.sleep(2)  # chờ URL cập nhật

            # 🌍 Lấy URL hiện tại sau khi click vào kết quả
            url = page.url
            if "/@" in url:
                coords = url.split("/@")[1].split(",")
                lat = coords[0].strip()
                lng = coords[1].strip()
            else:
                print(f"    ⚠️ Không tìm thấy tọa độ trong URL: {url}")
                lat, lng = "N/A", "N/A"

            print(f"    ✅ {lat}, {lng}")
            results.append([ten_cty, ma_so_thue, dai_dien, dia_chi, lat, lng])

        except Exception as e:
            print(f"    ⚠️ Lỗi: {e}")
            results.append([ten_cty, ma_so_thue, dai_dien, dia_chi, "N/A", "N/A"])

        # 💾 Lưu tạm sau mỗi dòng
        df_temp = pd.DataFrame(results, columns=[
            "Tên doanh nghiệp", "Mã số thuế", "Người đại diện", "Địa chỉ", "Latitude", "Longitude"
        ])
        df_temp.to_csv(output_file, index=False, encoding="utf-8")

    browser.close()

print(f"\n✅ Đã lưu kết quả đầy đủ vào: {output_file}")
