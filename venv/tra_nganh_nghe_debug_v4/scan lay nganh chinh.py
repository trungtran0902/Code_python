from playwright.sync_api import sync_playwright
import pandas as pd
import re
import unidecode
import time
import random

# Tạo slug từ tên công ty
def generate_slug(company_name):
    name = unidecode.unidecode(company_name).lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

# Tạo URL masothue.com từ MST và tên công ty
def generate_masothue_url(mst, company_name):
    slug = generate_slug(company_name)
    return f"https://masothue.com/{mst}-{slug}"

# Đọc file input
df = pd.read_excel("danh_sach_cong_ty.xlsx")
results = []

def save_partial():
    pd.DataFrame(results).to_excel("ket_qua_nganh_nghe.xlsx", index=False)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    page = browser.new_page()

    for index, row in df.iterrows():
        mst = str(row["Mã số thuế"]).strip()
        ten_cty = str(row["Tên doanh nghiệp"]).replace("\n", " ").strip()
        url = generate_masothue_url(mst, ten_cty)

        print(f"🔍 Đang xử lý: {mst} - {ten_cty}")
        print(f"🌐 Truy cập: {url}")

        try:
            page.goto(url, timeout=20000)
            page.wait_for_selector("body", timeout=15000)

            # Kiểm tra nếu MST không tồn tại
            body_text = page.inner_text("body")
            if "Không tìm thấy" in body_text:
                raise Exception("Không tìm thấy doanh nghiệp trên masothue")

            # Tìm bảng ngành nghề
            target_table = page.query_selector("h3.h3:has-text('Ngành nghề kinh doanh') + .table")
            if not target_table:
                tables = page.query_selector_all("table.table")
                if tables:
                    target_table = tables[0]

            if not target_table:
                raise Exception("Không tìm thấy bảng ngành nghề")

            # Crawl từng dòng mã ngành - tên ngành
            rows = target_table.query_selector_all("tbody tr")
            if not rows:
                raise Exception("Không có dữ liệu ngành nghề trong bảng")

            for r in rows:
                cells = r.query_selector_all("td")
                if len(cells) >= 2:
                    code = cells[0].inner_text().strip()
                    name = cells[1].inner_text().strip()
                    results.append({
                        "Mã số thuế": mst,
                        "Tên công ty": ten_cty,
                        "Mã ngành": code,
                        "Tên ngành": name
                    })

            save_partial()
            print(f"✅ Lấy được {len(rows)} ngành nghề")

        except Exception as e:
            print(f"❌ Lỗi khi xử lý {mst}: {e}")
            results.append({
                "Mã số thuế": mst,
                "Tên công ty": ten_cty,
                "Mã ngành": "",
                "Tên ngành": f"Lỗi: {str(e)}"
            })
            save_partial()

        # Nghỉ ngẫu nhiên 1-3 giây để tránh bị chặn
        time.sleep(random.uniform(1, 3))

    browser.close()

print("✅ Hoàn tất. Kết quả lưu tại: ket_qua_nganh_nghe.xlsx")
