# Foody network capture

This script captures network requests to the Foody HomeListPlace API while scrolling/clicking "Xem thêm".

Files added:
- `capture_foody_requests.py` - Playwright script that loads cookies from `foody_state.json` and logs matching requests.
- `requirements.txt` - Python dependency list.

Quick run (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
python -m playwright install
python capture_foody_requests.py
```

Notes:
- Put your existing `foody_state.json` (cookie file) next to this script (it should already be in this folder).
- The script launches a visible Chromium. Open DevTools manually if you want to inspect network details; the script prints captured API URLs to stdout.
- If the page/selector differs for your region, update `start_url` in the script.
