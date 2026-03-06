from playwright.sync_api import sync_playwright
import pandas as pd
import re
import unidecode
import time

# Hàm tạo slug từ tên công ty
def generate_slug(company_name):
    name = unidecode.unidecode(company_name).lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

# Hàm tạo URL từ MST và tên công ty
def generate_masothue_url(mst, company_name):
    slug = generate_slug(company_name)
    return f"https://masothue.com/{mst}-{slug}"

# Đọc file Excel
df = pd.read_excel("danh_sach_cong_ty_ver2.xlsx")
results = []

# Lưu tạm sau mỗi công ty
def save_partial():
    pd.DataFrame(results).to_excel("ket_qua_nganh_nghe_Ver2.xlsx", index=False)

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

            # Cuộn trang để load lazy-loading content
            for _ in range(10):
                page.mouse.wheel(0, 1000)
                time.sleep(0.8)

            page.wait_for_selector("h3.h3", timeout=10000)

            # Tìm bảng sau tiêu đề "Ngành nghề kinh doanh"
            titles = page.query_selector_all("h3.h3")
            target_table = None
            for title in titles:
                if "ngành nghề kinh doanh" in title.inner_text().lower():
                    next_sibling = title.evaluate_handle("el => el.nextElementSibling")
                    if next_sibling and next_sibling.as_element().get_attribute("class") == "table":
                        target_table = next_sibling.as_element()
                        break

            if target_table:
                rows = target_table.query_selector_all("tbody tr")
                nganh_list = []
                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        ma = cells[0].inner_text().strip()
                        ten = cells[1].inner_text().strip()
                        nganh_list.append(f"{ma} - {ten}")
                nganh_text = "; ".join(nganh_list)
                results.append({
                    "Mã số thuế": mst,
                    "Tên công ty": ten_cty,
                    "Ngành nghề kinh doanh": nganh_text
                })
                save_partial()
                print(f"✅ Ngành nghề: {nganh_text}")
            else:
                print("⚠️ Không tìm thấy bảng ngành nghề")
                results.append({
                    "Mã số thuế": mst,
                    "Tên công ty": ten_cty,
                    "Ngành nghề kinh doanh": "Không tìm thấy bảng ngành nghề"
                })
                save_partial()

        except Exception as e:
            results.append({
                "Mã số thuế": mst,
                "Tên công ty": ten_cty,
                "Ngành nghề kinh doanh": f"Lỗi: {str(e)}"
            })
            save_partial()
            print(f"❌ Lỗi khi xử lý {mst}: {e}")

    browser.close()

# Tách mã ngành và tên ngành thành từng dòng
expanded_rows = []
for row in results:
    raw_text = row["Ngành nghề kinh doanh"]
    ten_cong_ty = str(row["Tên công ty"]).replace("\n", " ").strip()
    mst = row["Mã số thuế"]

    if isinstance(raw_text, str) and ";" in raw_text:
        for item in raw_text.split(";"):
            if " - " in item:
                code, name = item.strip().split(" - ", 1)
                expanded_rows.append({
                    "Mã số thuế": mst,
                    "Tên công ty": ten_cong_ty,
                    "Mã ngành": code.strip(),
                    "Tên ngành": name.strip()
                })
    elif " - " in raw_text:
        code, name = raw_text.split(" - ", 1)
        expanded_rows.append({
            "Mã số thuế": mst,
            "Tên công ty": ten_cong_ty,
            "Mã ngành": code.strip(),
            "Tên ngành": name.strip()
        })
    else:
        expanded_rows.append({
            "Mã số thuế": mst,
            "Tên công ty": ten_cong_ty,
            "Mã ngành": "",
            "Tên ngành": raw_text.strip() if isinstance(raw_text, str) else ""
        })

# Xuất ra file cuối cùng
df_clean = pd.DataFrame(expanded_rows)
df_clean.to_excel("ket_qua_nganh_nghe.xlsx", index=False)
print("✅ Đã lưu file ket_qua_nganh_nghe.xlsx với cột Mã ngành và Tên ngành tách riêng")
