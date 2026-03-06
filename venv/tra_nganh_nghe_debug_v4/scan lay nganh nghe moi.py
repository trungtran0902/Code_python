from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd
import re
import unidecode
import random
import time

# Hàm tạo slug từ tên công ty
def generate_slug(company_name):
    name = unidecode.unidecode(company_name).lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

# Hàm tạo URL tra cứu
def generate_masothue_url(mst, company_name):
    slug = generate_slug(company_name)
    return f"https://masothue.com/{mst}-{slug}"

# Đọc danh sách công ty từ file Excel
df = pd.read_excel("danh_sach_cong_ty.xlsx")
df["Mã số thuế"] = df["Mã số thuế"].astype(str).str.strip()
results = []

# Lưu kết quả tạm thời
def save_partial():
    pd.DataFrame(results).to_excel("ket_qua_tinh_trang.xlsx", index=False)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    page = browser.new_page()

    # Thêm User-Agent giả lập
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/116.0.0.0 Safari/537.36"
    })

    for index, row in df.iterrows():
        mst = str(row["Mã số thuế"]).strip()
        ten_cty = str(row["Tên doanh nghiệp"]).replace("\n", " ").strip()
        url = generate_masothue_url(mst, ten_cty)

        print(f"🔍 Đang xử lý: {mst} - {ten_cty}")
        print(f"🌐 Truy cập: {url}")

        try:
            page.goto(url, timeout=20000)
            page.wait_for_selector("table.table-taxinfo", timeout=15000)

            tinh_trang = "Không tìm thấy"
            ngay_hoat_dong = "Không tìm thấy"

            # Duyệt các dòng trong bảng
            rows = page.query_selector_all("table.table-taxinfo tr")
            for r in rows:
                cells = r.query_selector_all("td")
                if len(cells) >= 2:
                    label = cells[0].inner_text().strip()
                    value = cells[1].inner_text().strip()
                    if label.startswith("Tình trạng"):
                        tinh_trang = value
                    elif label.startswith("Ngày hoạt động"):
                        ngay_hoat_dong = value

            results.append({
                "Mã số thuế": mst,
                "Tên công ty": ten_cty,
                "Tình trạng": tinh_trang,
                "Ngày hoạt động": ngay_hoat_dong
            })
            save_partial()
            print(f"✅ Tình trạng: {tinh_trang} | Ngày hoạt động: {ngay_hoat_dong}")

        except TimeoutError:
            results.append({
                "Mã số thuế": mst,
                "Tên công ty": ten_cty,
                "Tình trạng": "Lỗi: Timeout",
                "Ngày hoạt động": "Không lấy được"
            })
            save_partial()
            print(f"❌ Lỗi Timeout khi xử lý {mst}")

        except Exception as e:
            results.append({
                "Mã số thuế": mst,
                "Tên công ty": ten_cty,
                "Tình trạng": f"Lỗi: {str(e)}",
                "Ngày hoạt động": "Không lấy được"
            })
            save_partial()
            print(f"❌ Lỗi khi xử lý {mst}: {e}")

        # Thêm delay ngẫu nhiên tránh bị chặn
        time.sleep(random.uniform(2, 5))

    browser.close()

print("✅ Đã lưu file ket_qua_tinh_trang.xlsx")
