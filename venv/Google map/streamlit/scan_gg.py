import os
import re
import json
import math
import time
import tempfile
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl import Workbook
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "outputs")
PROFILE_DIR = os.path.join(APP_DIR, "google_profile")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PROFILE_DIR, exist_ok=True)

FIELDS = [
    "keyword", "name", "address", "located_in", "phone", "website",
    "opening_hours_today", "opening_hours_full", "lat", "lng", "url"
]


def clean_cell(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def normalize_phone_vn(phone):
    if not phone:
        return ""
    d = re.sub(r"\D", "", phone)
    if not d:
        return ""
    if d.startswith("84"):
        return f"+{d}"
    if d.startswith("0"):
        return f"+84{d[1:]}"
    return f"+{d}"


def extract_latlng_from_url(url):
    m = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", url)
    if m:
        return m.group(1), m.group(2)

    m = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if m:
        return m.group(1), m.group(2)

    return "", ""


def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_chrome_path():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return ""


def read_excel_to_dataframe(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        if suffix == ".xls":
            df = pd.read_excel(tmp_path, dtype=str, engine="xlrd")
        else:
            df = pd.read_excel(tmp_path, dtype=str, engine="openpyxl")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return df.fillna("")


def scroll_results(page, max_rounds=30):
    feed = page.locator("div[role='feed']")
    if feed.count() == 0:
        return False

    last = 0
    for _ in range(max_rounds):
        try:
            feed.first.evaluate("(el)=>el.scrollBy(0, el.scrollHeight)")
            time.sleep(0.4)
            h = feed.first.evaluate("(el)=>el.scrollHeight")
            if h == last:
                break
            last = h
        except Exception:
            break
    return True


def scroll_detail_panel(page, max_rounds=10):
    panel = page.locator("div[role='main']")
    if panel.count() == 0:
        return

    last = 0
    for _ in range(max_rounds):
        try:
            panel.first.evaluate("(el)=>el.scrollBy(0, el.scrollHeight)")
            time.sleep(0.12)
            h = panel.first.evaluate("(el)=>el.scrollHeight")
            if h == last:
                break
            last = h
        except Exception:
            break


def get_address(page):
    for s in [
        "button[data-item-id='address']",
        "button[aria-label^='Địa chỉ']",
        "div[aria-label^='Địa chỉ']",
    ]:
        loc = page.locator(s)
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
    return ""


def get_phone(page):
    loc = page.locator("button[data-item-id^='phone']")
    return (loc.first.text_content() or "").strip() if loc.count() > 0 else ""


def get_website(page):
    loc = page.locator("a[data-item-id='authority']")
    return loc.first.get_attribute("href") if loc.count() > 0 else ""


def get_located_in(page):
    try:
        loc = page.locator("text=/Nằm ở:/")
        if loc.count() > 0:
            txt = loc.first.text_content() or ""
            return txt.replace("Nằm ở:", "").strip()
    except Exception:
        pass
    return ""


def expand_opening_hours_block(page):
    scroll_detail_panel(page)
    candidates = [
        "button:has-text('Giờ')",
        "button:has-text('Mở cửa')",
        "button:has-text('Đóng cửa')",
        "div[role='button']:has-text('Giờ')",
        "div[role='button']:has-text('Mở cửa')",
        "div[role='button']:has-text('Đóng cửa')",
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
    ]
    for s in candidates:
        loc = page.locator(s)
        if loc.count() > 0:
            try:
                loc.first.scroll_into_view_if_needed()
                time.sleep(0.2)
                loc.first.click(force=True)
                page.wait_for_selector("text=/Thứ|Chủ/", timeout=6000)
                time.sleep(0.2)
                return True
            except Exception:
                pass
    return False


def scan_opening_hours_by_rows(page):
    hours = {}
    try:
        panel = page.locator("div[role='main']")
        if panel.count() > 0:
            panel_text = panel.first.text_content() or ""
            pattern = r"(Thứ\s+(?:Hai|Ba|Tư|Năm|Sáu|Bảy)|Chủ\s+Nhật)\s*([0-9:–-]+\s*(?:–|-)\s*[0-9:–-]+|Đóng cửa|Mở 24 giờ)"
            matches = re.findall(pattern, panel_text, re.IGNORECASE)
            for d, t in matches:
                if t:
                    hours[d.strip()] = t.strip()
    except Exception:
        pass
    return hours


def get_opening_hours_today(page):
    for s in [
        "button[data-item-id='oh']",
        "div[data-item-id='oh']",
        "button[aria-label*='Mở cửa']",
        "button[aria-label*='Đóng cửa']",
    ]:
        loc = page.locator(s)
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
    return ""


def get_basic_poi_for_filter(page):
    try:
        name = (page.locator("h1").first.text_content() or "").strip()
        lat, lng = extract_latlng_from_url(page.url)
        return name, lat, lng
    except Exception:
        return None, "", ""


def parse_current_poi(page, keyword):
    try:
        name = (page.locator("h1").first.text_content() or "").strip()
        if not name:
            return None
    except Exception:
        return None

    scroll_detail_panel(page)
    address = get_address(page)
    located_in = get_located_in(page)
    phone = normalize_phone_vn(get_phone(page))
    website = get_website(page)
    opening_today = get_opening_hours_today(page)

    opening_full = {}
    if expand_opening_hours_block(page):
        opening_full = scan_opening_hours_by_rows(page)

    lat, lng = extract_latlng_from_url(page.url)

    return {
        "keyword": keyword,
        "name": name,
        "address": address,
        "located_in": located_in,
        "phone": phone,
        "website": website,
        "opening_hours_today": opening_today,
        "opening_hours_full": json.dumps(opening_full, ensure_ascii=False),
        "lat": lat,
        "lng": lng,
        "url": page.url,
    }


def get_place_links_from_list(page):
    try:
        return page.eval_on_selector_all(
            "a[href*='/maps/place/']",
            "els=>[...new Set(els.map(e=>e.href))]",
        )
    except Exception:
        return []


def focus_location_with_radius(page, loc_text, radius_km=0.5):
    try:
        lat, lng = [x.strip() for x in str(loc_text).split(",")]
        if radius_km <= 0.5:
            zoom = 17
        elif radius_km <= 1:
            zoom = 16
        elif radius_km <= 2:
            zoom = 15
        else:
            zoom = 14

        page.goto(f"https://www.google.com/maps/@{lat},{lng},{zoom}z", timeout=60000)
        time.sleep(2)
        return float(lat), float(lng)
    except Exception:
        return None, None


def crawl_google_maps_keyword(
    page,
    keyword,
    center_lat=None,
    center_lng=None,
    radius_km=0.5,
    max_poi_per_keyword=1,
    log_fn=None,
):
    results = []

    try:
        sb = page.wait_for_selector("input[role='combobox']", timeout=15000)
        sb.click()
        sb.fill(keyword)
        sb.press("Enter")
        time.sleep(3)
    except PlaywrightTimeoutError:
        if log_fn:
            log_fn(f"❌ Không tìm thấy ô search Google Maps: {keyword}")
        return results

    has_feed = scroll_results(page)
    links = get_place_links_from_list(page) if has_feed else [page.url]

    if not links and log_fn:
        log_fn(f"⚠️ Không lấy được link kết quả: {keyword}")

    for i, link in enumerate(links, 1):
        try:
            page.goto(link, timeout=60000)
            time.sleep(0.8)

            name, lat, lng = get_basic_poi_for_filter(page)
            if not name:
                continue

            if center_lat and center_lng and lat and lng:
                d = distance_km(center_lat, center_lng, float(lat), float(lng))
                if d > radius_km:
                    if log_fn:
                        log_fn(f"   ⛔ Ngoài {radius_km} km: {name} ({round(d * 1000)} m)")
                    continue

            poi = parse_current_poi(page, keyword)
            if poi:
                results.append(poi)
                if log_fn:
                    log_fn(f"   ✔ {keyword} | {i}: {poi['name']}")

                if len(results) >= max_poi_per_keyword:
                    break

        except Exception as e:
            if log_fn:
                log_fn(f"   ❌ {keyword}: {e}")

    return results


def save_xlsx(path, data):
    wb = Workbook()
    ws = wb.active
    ws.title = "Google Maps"
    ws.append(FIELDS)

    for row in data:
        ws.append([row.get(k, "") for k in FIELDS])

    wb.save(path)


def make_xlsx_bytes(data):
    bio = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Google Maps"
    ws.append(FIELDS)

    for row in data:
        ws.append([row.get(k, "") for k in FIELDS])

    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


st.set_page_config(page_title="Google Maps Crawler Local", layout="wide")
st.title("Google Maps Crawler - Streamlit Local")
st.caption("Upload Excel → chọn cột keyword/location → crawl Google Maps → tải kết quả Excel")

with st.sidebar:
    st.header("Cấu hình chạy")

    chrome_auto = find_chrome_path()
    use_system_chrome = st.checkbox("Dùng Google Chrome đang cài trên máy", value=bool(chrome_auto))

    chrome_path = ""
    if use_system_chrome:
        chrome_path = st.text_input("Đường dẫn Chrome", value=chrome_auto)
    else:
        st.info("Sẽ dùng Chromium của Playwright. Nếu chưa có, chạy: playwright install chromium")

    headless = st.checkbox("Chạy ẩn browser headless", value=False)
    radius_km = st.number_input("Bán kính lọc theo location (km)", min_value=0.1, max_value=20.0, value=0.5, step=0.1)
    max_poi_per_keyword = st.number_input("Số POI tối đa / keyword", min_value=1, max_value=20, value=1, step=1)
    delay_between_keywords = st.number_input("Nghỉ giữa các keyword (giây)", min_value=0.0, max_value=10.0, value=1.0, step=0.5)

uploaded_file = st.file_uploader("Chọn file Excel đầu vào", type=["xlsx", "xls"])

if uploaded_file:
    try:
        df = read_excel_to_dataframe(uploaded_file)
    except Exception as e:
        st.error(f"Không đọc được Excel: {e}")
        st.stop()

    if df.empty:
        st.warning("File Excel không có dữ liệu.")
        st.stop()

    columns = list(df.columns)

    def guess_col_index(possible_names):
        lower_cols = [str(c).strip().lower() for c in columns]
        for name in possible_names:
            name = name.lower()
            for idx, col in enumerate(lower_cols):
                if col == name or name in col:
                    return idx
        return 0

    c1, c2 = st.columns(2)
    with c1:
        keyword_col = st.selectbox("Cột keyword", options=columns)
    with c2:
        limit_rows = st.number_input(
            "Giới hạn số dòng chạy thử",
            min_value=0,
            max_value=len(df),
            value=0,
            step=1,
            help="0 = chạy toàn bộ",
        )

    st.markdown("### Cấu hình tọa độ location")
    location_mode = st.radio(
        "Kiểu dữ liệu tọa độ",
        options=[
            "Không dùng location",
            "Lat,long chung 1 cột",
            "Lat và long tách 2 cột",
        ],
        index=1,
        horizontal=True,
    )

    location_col = None
    lat_col = None
    lng_col = None

    if location_mode == "Lat,long chung 1 cột":
        location_col = st.selectbox(
            "Cột location lat,long",
            options=columns,
            index=guess_col_index(["location", "lat,long", "latlong", "tọa độ", "toa do"]),
        )
    elif location_mode == "Lat và long tách 2 cột":
        c_lat, c_lng = st.columns(2)
        with c_lat:
            lat_col = st.selectbox(
                "Cột LAT",
                options=columns,
                index=guess_col_index(["lat", "latitude", "vĩ độ", "vi do"]),
            )
        with c_lng:
            lng_col = st.selectbox(
                "Cột LNG / LONG",
                options=columns,
                index=guess_col_index(["lng", "long", "longitude", "kinh độ", "kinh do"]),
            )

    st.subheader("Xem trước dữ liệu")
    st.dataframe(df.head(20), use_container_width=True)

    rows_data = []
    for _, row in df.iterrows():
        kw = clean_cell(row.get(keyword_col, ""))
        loc = ""

        if location_mode == "Lat,long chung 1 cột" and location_col:
            loc = clean_cell(row.get(location_col, ""))

        elif location_mode == "Lat và long tách 2 cột" and lat_col and lng_col:
            lat_value = clean_cell(row.get(lat_col, ""))
            lng_value = clean_cell(row.get(lng_col, ""))
            if lat_value and lng_value:
                loc = f"{lat_value},{lng_value}"

        if kw:
            rows_data.append((kw, loc))

    if limit_rows and limit_rows > 0:
        rows_data = rows_data[:limit_rows]

    st.info(f"Sẵn sàng chạy: {len(rows_data)} keyword")

    if st.button("▶️ Bắt đầu crawl", type="primary"):
        if not rows_data:
            st.error("Không có keyword hợp lệ để chạy.")
            st.stop()

        if use_system_chrome and chrome_path and not os.path.exists(chrome_path):
            st.error("Đường dẫn Chrome không tồn tại. Hãy sửa lại hoặc bỏ chọn dùng Chrome hệ thống.")
            st.stop()

        log_lines = []
        log_box = st.empty()
        progress = st.progress(0)
        result_box = st.empty()

        def log_fn(msg):
            log_lines.append(msg)
            log_box.code("\n".join(log_lines[-200:]), language="text")

        all_results = []
        autosave_path = os.path.join(OUTPUT_DIR, "autosave_temp.xlsx")

        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": headless,
                    "locale": "vi-VN",
                    "viewport": {"width": 1280, "height": 800},
                }

                if use_system_chrome and chrome_path:
                    launch_kwargs["executable_path"] = chrome_path

                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    **launch_kwargs,
                )

                page = context.new_page()
                page.goto("https://www.google.com/maps?hl=vi", timeout=60000)
                time.sleep(2)

                for i, (keyword, loc) in enumerate(rows_data, 1):
                    log_fn(f"\n▶️ {i}/{len(rows_data)}: {keyword}")

                    center_lat = center_lng = None

                    if loc:
                        log_fn(f"   📍 Dùng location: {loc}")
                        center_lat, center_lng = focus_location_with_radius(page, loc, radius_km)

                        if center_lat is None or center_lng is None:
                            log_fn("   ⚠️ Location không đúng định dạng lat,long → bỏ lọc bán kính cho keyword này")
                    else:
                        log_fn("   🎯 Không dùng location")

                    results = crawl_google_maps_keyword(
                        page,
                        keyword,
                        center_lat=center_lat,
                        center_lng=center_lng,
                        radius_km=radius_km,
                        max_poi_per_keyword=int(max_poi_per_keyword),
                        log_fn=log_fn,
                    )

                    all_results.extend(results)

                    if all_results:
                        save_xlsx(autosave_path, all_results)
                        result_box.success(f"Đã lấy {len(all_results)} POI. Autosave: {autosave_path}")

                    progress.progress(i / len(rows_data))
                    time.sleep(float(delay_between_keywords))

                context.close()

        except Exception as e:
            st.error(f"Lỗi khi chạy Playwright/Google Maps: {e}")
            if not all_results:
                st.stop()

        if all_results:
            out_name = f"googlemaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            save_xlsx(out_path, all_results)

            st.success(f"Hoàn tất. Tổng POI lấy được: {len(all_results)}")
            st.download_button(
                label="⬇️ Tải file Excel kết quả",
                data=make_xlsx_bytes(all_results),
                file_name=out_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.write("File cũng được lưu tại:")
            st.code(out_path, language="text")
        else:
            st.warning("Chạy xong nhưng chưa lấy được POI nào.")
else:
    st.info("Hãy upload file Excel để bắt đầu.")
