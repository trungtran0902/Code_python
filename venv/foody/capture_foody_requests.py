from playwright.sync_api import sync_playwright
import json
import time
import os

STATE_FILE = os.path.join(os.path.dirname(__file__), "foody_state_Hue.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "captured_urls_Hue_17032026.txt")

def load_cookies(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Could not read cookie file: {e}")
        return []

    if isinstance(data, dict) and "cookies" in data:
        cookies = data["cookies"]
        # Filter or modify cookies if necessary (for example, removing conflicting geolocation cookies)
        # Example: Removing geolocation cookies or replacing them with Ho Chi Minh values
        for cookie in cookies:
            if 'lat' in cookie or 'lon' in cookie:
                cookie['lat'] = 16.4498
                cookie['lon'] = 107.56235
        return cookies
    if isinstance(data, list):
        return data
    return []

def save_urls(urls, file_path):
    """Auto-save URLs to file"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")
        print(f"  💾 Auto-saved {len(urls)} links to file")
    except Exception as e:
        print(f"  ✗ Failed to auto-save: {e}")

def main():
    cookies = load_cookies(STATE_FILE)
    captured_urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Force geolocation and locale to Hanoi to avoid server using wrong region
        context = browser.new_context(
            geolocation={"latitude": 16.4498, "longitude": 107.56235},
            permissions=["geolocation"],
            locale="vi-VN"
        )

        # Clear any existing cookies (they may contain a different default region)
        try:
            context.clear_cookies()
        except:
            pass

        # Optionally load saved cookies (use with caution if they contain region info)
        if cookies:
            try:
                context.clear_cookies()  # Make sure cookies are cleared
                context.add_cookies(cookies)
                print(f"Loaded {len(cookies)} cookies into context")
            except Exception as e:
                print(f"Failed to add cookies: {e}")

        page = context.new_page()

        # Intercept API requests and normalize lat/lon to Hanoi values so API returns Hanoi data
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        def route_handler(route, request):
            url = request.url
            if "/__get/Place/HomeListPlace" in url:
                purl = urlparse(url)
                qs = parse_qs(purl.query)
                qs['lat'] = [str(16.4498)]
                qs['lon'] = [str(107.56235)]
                qs['CityId'] = ['273']      # QUAN TRỌNG
                qs['districtId'] = ['']     # optional – để all quận

                # flatten values
                new_q = urlencode({k: v[0] for k, v in qs.items()})
                new_url = urlunparse((purl.scheme, purl.netloc, purl.path, purl.params, new_q, purl.fragment))
                try:
                    route.continue_(url=new_url)
                    return
                except Exception:
                    # fallback to continuing original
                    pass
            route.continue_()

        try:
            context.route("**/__get/Place/HomeListPlace**", route_handler)
        except Exception:
            # older playwright versions may require page.route; we handle later if needed
            pass

        def on_request(request):
            url = request.url
            if "/__get/Place/HomeListPlace" in url:
                print(f"[{len(captured_urls)+1}] Captured API: {url}")
                captured_urls.append(url)
                # Auto-save every 5 links
                if len(captured_urls) % 5 == 0:
                    save_urls(captured_urls, OUTPUT_FILE)

        page.on("request", on_request)

        def force_remove_login_popup():
            try:
                page.evaluate("""
                () => {
                    document.querySelectorAll(`
                        .modal,
                        .modal-backdrop,
                        .popup,
                        .popup-login,
                        .ReactModal__Overlay,
                        .ReactModal__Content,
                        [role="dialog"],
                        .login-popup,
                        .overlay,
                        .backdrop
                    `).forEach(el => el.remove());

                    document.querySelectorAll('*').forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' && parseInt(style.zIndex || 0) > 1000) {
                            el.remove();
                        }
                    });

                    document.body.style.overflow = 'auto';
                    document.body.style.pointerEvents = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }
                """)
            except:
                pass

        try:
            # Change this URL to the Foody page you normally use
            start_url = "https://www.foody.vn/hue/"
            
            print("Navigating to", start_url)
            page.goto(start_url, timeout=60000)
            print("✓ Page loaded, waiting for initial requests...")
            time.sleep(2)

            # Scroll and click "Xem thêm" button multiple times (until no more button)
            for i in range(1000):  # Max 1000 rounds, but will break when no more button
                print(f"\n[Round {i+1}] Scrolling down...")
                try:
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                except:
                    print(f"[Round {i+1}] Scroll failed")
                    break
                
                time.sleep(1)
                force_remove_login_popup()
                time.sleep(1)
                
                # Try to find "Xem thêm" button in div.pn-loadmore
                btn_selectors = [
                    "a.fd-btn-more",
                    "div.pn-loadmore a",
                    ".pn-loadmore .fd-btn-more",
                    "//a[@class='fd-btn-more']",
                    "div:has-text('Xem thêm')",
                    "a:has-text('Xem thêm')"
                ]
                
                btn = None
                for selector in btn_selectors:
                    try:
                        btn = page.query_selector(selector)
                        if btn:
                            print(f"[Round {i+1}] Found button with selector: {selector}")
                            break
                    except:
                        continue
                
                if btn:
                    try:
                        btn.scroll_into_view_if_needed()
                        time.sleep(1)
                        btn.click(force=True)
                        print(f"[Round {i+1}] ✓ Clicked 'Xem thêm'")
                        time.sleep(3)
                    except Exception as e:
                        print(f"[Round {i+1}] ✗ Click failed: {e}")
                        break
                else:
                    print(f"[Round {i+1}] ⛔ No 'Xem thêm' button found (reached end)")

            print("\n" + "="*60)
            print(f"Finished scrolling. Captured {len(captured_urls)} API links:")
            for idx, url in enumerate(captured_urls, 1):
                print(f"{idx}. {url}")
            print("="*60)
            
        finally:
            # Save to file (always execute, even if errors occur)
            try:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    for url in captured_urls:
                        f.write(url + "\n")
                print(f"\n✓ Saved {len(captured_urls)} links to: {OUTPUT_FILE}")
            except Exception as e:
                print(f"✗ Failed to save file: {e}")
            
            try:
                print("Closing browser...")
                page.wait_for_timeout(2000)
                browser.close()
            except:
                pass
if __name__ == "__main__":
    main()
