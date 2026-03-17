from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://www.foody.vn")

    print("👉 Đăng nhập Foody bằng tay (Google / Facebook / Email)")
    print("👉 Sau khi login xong, CHỜ 5–10s")

    page.wait_for_timeout(60000)  # 60 giây cho bạn login

    # LƯU COOKIE
    output_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foody_state_Hue.json")
    context.storage_state(path=output_json)
    print(f"✅ Đã tạo {output_json}")

    browser.close()
