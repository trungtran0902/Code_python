from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir="google_profile",   # thư mục lưu session
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
        ]
    )
    page = context.new_page()
    page.goto("https://accounts.google.com")

    print("👉 Đăng nhập Google bằng tay trong cửa sổ vừa mở.")
    print("👉 Sau khi vào được Google Maps, đóng cửa sổ.")

    page.wait_for_timeout(10 * 60 * 1000)
    context.close()
