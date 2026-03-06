import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def open_google_maps_and_search(driver, lat, long):
    driver.get("https://www.google.com/maps")

    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "searchboxinput"))
    )
    search_box.clear()
    search_box.send_keys(f"{lat}, {long}")
    search_box.send_keys(Keys.RETURN)

    WebDriverWait(driver, 10).until(EC.url_contains("data="))


def inject_logger_script(driver):
    script = """
    window.loggedEvents = [];
    document.addEventListener('click', e => {
        window.loggedEvents.push(`Clicked at (${e.clientX}, ${e.clientY}) on ${e.target.tagName}`);
    });
    document.addEventListener('keydown', e => {
        window.loggedEvents.push(`Key pressed: ${e.key}`);
    });
    """
    driver.execute_script(script)
    print("Đã inject script ghi log sự kiện DOM.")


def get_logged_events(driver):
    return driver.execute_script("return window.loggedEvents;")


def main():
    options = Options()
    options.headless = False
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    lat, long = 10.762622, 106.660172
    open_google_maps_and_search(driver, lat, long)

    inject_logger_script(driver)
    print("Bạn có 20 giây để thao tác trên trang...")
    time.sleep(20)

    logs = get_logged_events(driver)
    print("📋 Các thao tác bạn đã thực hiện:")
    for log in logs:
        print("-", log)

    driver.quit()


if __name__ == "__main__":
    main()
