# -*- coding: utf-8 -*-
"""
Crawl dữ liệu bưu cục VNPost theo ProvinceId + CommuneID và xuất Excel.

Yêu cầu:
    pip install requests pandas openpyxl

Luồng chạy:
    B1: Mở hộp thoại chọn file provinces.txt
    B2: Mở hộp thoại chọn tất cả file danh sách phường/xã/đặc khu theo từng tỉnh/thành
    B3: Crawl API VNPost theo từng ProvinceId + CommuneID
    B4: Xuất file Excel

Output Excel gồm 3 sheet:
    1. post_offices   : dữ liệu bưu cục lấy được
    2. empty_communes : xã/phường/đặc khu không có dữ liệu
    3. crawl_errors   : lỗi mapping file hoặc lỗi request
"""

from __future__ import annotations

import json
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pandas as pd
import requests
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import tkinter as tk
from tkinter import filedialog


# =========================
# CONFIG
# =========================

DEFAULT_TEMPLATE_URL = (
    "https://vietnampost.vn/vnpost/post-office"
    "?district_code=&district_id=94118&province_code=&province_id=94"
)

MAX_WORKERS = 5
REQUEST_TIMEOUT = 25
RETRY_TIMES = 3
RETRY_SLEEP_SECONDS = 1.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://vietnampost.vn/",
}

MAIN_COLUMNS = [
    "ProvinceFullName",
    "ProvinceId",
    "CommunesFullName",
    "CommuneID",
    "PostCode",
    "PostOfficeName",
    "DetailsAddress",
    "lat",
    "lng",
    "VNPost_id",
    "PostOfficeId",
    "api_commune_id",
    "api_district_id",
    "crawl_url",
]


# =========================
# GUI
# =========================

def select_files_gui() -> tuple[str | None, list[str], str | None]:
    """
    Chọn file bằng GUI.

    Lưu ý:
    - Không dùng messagebox.showinfo() vì dễ bị ẩn sau PyCharm/Terminal.
    - Dùng topmost để dialog hiện phía trước.
    """
    root = tk.Tk()
    root.withdraw()
    root.update()
    root.attributes("-topmost", True)

    province_file = filedialog.askopenfilename(
        parent=root,
        title="B1 - Chọn file provinces.txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )

    if not province_file:
        root.destroy()
        return None, [], None

    commune_files = filedialog.askopenfilenames(
        parent=root,
        title="B2 - Chọn tất cả file phường/xã/đặc khu theo từng tỉnh/thành",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )

    if not commune_files:
        root.destroy()
        return province_file, [], None

    default_output = f"vnpost_post_offices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_file = filedialog.asksaveasfilename(
        parent=root,
        title="B4 - Chọn nơi lưu file Excel",
        defaultextension=".xlsx",
        initialfile=default_output,
        filetypes=[("Excel files", "*.xlsx")],
    )

    root.destroy()
    return province_file, list(commune_files), output_file or None


# =========================
# READ / NORMALIZE DATA
# =========================

def normalize_text(value: Any) -> str:
    """Chuẩn hóa text để so khớp tên tỉnh với tên file."""
    text = unicodedata.normalize("NFC", str(value or ""))
    text = text.strip().lower()
    text = " ".join(text.split())
    return text


def load_json_txt(file_path: str | Path) -> list[dict[str, Any]]:
    """Đọc file .txt có nội dung JSON array."""
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8-sig").strip()

    if not raw:
        return []

    data = json.loads(raw)

    if isinstance(data, list):
        return data

    raise ValueError(f"File không phải JSON array: {path}")


def read_template_url(province_file: str | Path) -> str:
    """
    Đọc URL mẫu từ text_lay_store.txt cùng thư mục với provinces.txt.
    Nếu không có thì dùng DEFAULT_TEMPLATE_URL.
    """
    province_dir = Path(province_file).parent
    url_file = province_dir / "text_lay_store.txt"

    if url_file.exists():
        url = url_file.read_text(encoding="utf-8-sig").strip()
        if url:
            return url

    return DEFAULT_TEMPLATE_URL


def build_vnpost_url(template_url: str, province_id: str, commune_id: str) -> str:
    """
    Thay province_id và district_id theo yêu cầu:
    - province_id  = ProvinceId
    - district_id  = CommuneID
    - district_code/province_code để rỗng
    """
    parsed = urlparse(template_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    query["district_code"] = [""]
    query["district_id"] = [str(commune_id)]
    query["province_code"] = [""]
    query["province_id"] = [str(province_id)]

    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def build_commune_file_map(commune_files: list[str]) -> dict[str, str]:
    """Map tên file tỉnh/thành sang path file."""
    result: dict[str, str] = {}

    for file_path in commune_files:
        path = Path(file_path)
        key = normalize_text(path.stem)

        # Người dùng có thể lỡ chọn cả provinces.txt hoặc text_lay_store.txt, bỏ qua.
        if key in {"provinces", "text_lay_store"}:
            continue

        result[key] = str(path)

    return result


def build_tasks(
    province_file: str,
    commune_files: list[str],
    template_url: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Ghép đúng file tỉnh/thành và tạo danh sách URL cần crawl."""
    provinces = load_json_txt(province_file)
    commune_file_map = build_commune_file_map(commune_files)

    tasks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for province in provinces:
        province_name = province.get("ProvinceFullName")
        province_id = province.get("ProvinceId")

        if not province_name or not province_id:
            errors.append({
                "ProvinceFullName": province_name,
                "ProvinceId": province_id,
                "error": "Thiếu ProvinceFullName hoặc ProvinceId trong provinces.txt",
            })
            continue

        province_key = normalize_text(province_name)
        commune_file = commune_file_map.get(province_key)

        if not commune_file:
            errors.append({
                "ProvinceFullName": province_name,
                "ProvinceId": province_id,
                "error": (
                    "Không tìm thấy file phường/xã tương ứng. "
                    "Tên file nên trùng ProvinceFullName, ví dụ: TP. Hồ Chí Minh.txt"
                ),
            })
            continue

        try:
            communes = load_json_txt(commune_file)
        except Exception as exc:
            errors.append({
                "ProvinceFullName": province_name,
                "ProvinceId": province_id,
                "file": commune_file,
                "error": f"Không đọc được file phường/xã: {exc}",
            })
            continue

        for commune in communes:
            commune_name = commune.get("CommunesFullName")
            commune_id = commune.get("CommuneID")

            if not commune_id:
                errors.append({
                    "ProvinceFullName": province_name,
                    "ProvinceId": province_id,
                    "CommunesFullName": commune_name,
                    "CommuneID": commune_id,
                    "error": "Thiếu CommuneID",
                })
                continue

            url = build_vnpost_url(template_url, str(province_id), str(commune_id))

            tasks.append({
                "ProvinceFullName": province_name,
                "ProvinceId": str(province_id),
                "CommunesFullName": commune_name,
                "CommuneID": str(commune_id),
                "url": url,
            })

    return tasks, errors


# =========================
# CRAWL
# =========================

def fetch_one_commune(task: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    """
    Crawl 1 CommuneID.

    Return:
        rows, error, empty_commune
    """
    last_error = None
    url = task["url"]

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"HTTP {response.status_code}"
                time.sleep(RETRY_SLEEP_SECONDS * attempt)
                continue

            response.raise_for_status()
            data = response.json()

            # Hiện tại endpoint trả list trực tiếp.
            # Nếu sau này đổi dạng {"data": [...]}, vẫn xử lý được.
            if isinstance(data, dict):
                if isinstance(data.get("data"), list):
                    data = data["data"]
                elif isinstance(data.get("result"), list):
                    data = data["result"]
                else:
                    data = [data]

            if not isinstance(data, list):
                return [], {
                    **task,
                    "error": f"Response không phải JSON list/dict. Type={type(data)}",
                }, None

            if len(data) == 0:
                return [], None, {
                    "ProvinceFullName": task["ProvinceFullName"],
                    "ProvinceId": task["ProvinceId"],
                    "CommunesFullName": task["CommunesFullName"],
                    "CommuneID": task["CommuneID"],
                    "crawl_url": url,
                }

            rows: list[dict[str, Any]] = []
            for item in data:
                if not isinstance(item, dict):
                    continue

                rows.append({
                    "ProvinceFullName": task["ProvinceFullName"],
                    "ProvinceId": task["ProvinceId"],
                    "CommunesFullName": task["CommunesFullName"],
                    "CommuneID": task["CommuneID"],
                    "PostCode": item.get("PostCode"),
                    "PostOfficeName": item.get("PostOfficeName"),
                    "DetailsAddress": item.get("DetailsAddress"),
                    "lat": item.get("lat"),
                    "lng": item.get("lng"),
                    "VNPost_id": item.get("id"),
                    "PostOfficeId": item.get("PostOfficeId"),
                    "api_commune_id": item.get("commune_id"),
                    "api_district_id": item.get("district_id"),
                    "crawl_url": url,
                })

            return rows, None, None

        except Exception as exc:
            last_error = str(exc)
            time.sleep(RETRY_SLEEP_SECONDS * attempt)

    return [], {
        **task,
        "error": last_error,
    }, None


def crawl_all(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Crawl toàn bộ tasks."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    empty_communes: list[dict[str, Any]] = []

    total = len(tasks)
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(fetch_one_commune, task): task for task in tasks}

        for index, future in enumerate(as_completed(future_map), start=1):
            task = future_map[future]

            try:
                task_rows, task_error, task_empty = future.result()
                rows.extend(task_rows)

                if task_error:
                    errors.append(task_error)

                if task_empty:
                    empty_communes.append(task_empty)

            except Exception as exc:
                errors.append({
                    **task,
                    "error": str(exc),
                })

            if index % 50 == 0 or index == total:
                elapsed = time.time() - start
                print(
                    f"Đã xử lý {index}/{total} | "
                    f"bưu cục: {len(rows)} | "
                    f"không có dữ liệu: {len(empty_communes)} | "
                    f"lỗi: {len(errors)} | "
                    f"elapsed: {elapsed:.1f}s"
                )

    return rows, empty_communes, errors


# =========================
# EXPORT EXCEL
# =========================

def autosize_and_style_excel(output_file: str | Path) -> None:
    wb = load_workbook(output_file)

    text_columns = {
        "ProvinceId",
        "CommuneID",
        "PostCode",
        "VNPost_id",
        "PostOfficeId",
        "api_commune_id",
        "api_district_id",
    }

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"

        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9EAF7")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        if ws.max_row >= 1 and ws.max_column >= 1:
            ws.auto_filter.ref = ws.dimensions

        headers: dict[int, str] = {}
        for col_idx, cell in enumerate(ws[1], start=1):
            headers[col_idx] = str(cell.value or "")

        for col_idx in range(1, ws.max_column + 1):
            col_letter = get_column_letter(col_idx)
            header = headers.get(col_idx, "")
            max_len = len(header)

            for cell in ws[col_letter]:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
                if header in text_columns:
                    cell.number_format = "@"

            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 70)

    wb.save(output_file)


def export_excel(
    rows: list[dict[str, Any]],
    empty_communes: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    output_file: str,
) -> None:
    df_main = pd.DataFrame(rows)

    if df_main.empty:
        df_main = pd.DataFrame(columns=MAIN_COLUMNS)
    else:
        df_main = df_main.reindex(columns=MAIN_COLUMNS)
        df_main = df_main.drop_duplicates(
            subset=["ProvinceId", "CommuneID", "PostCode", "PostOfficeName", "DetailsAddress"],
            keep="first",
        )

    df_empty = pd.DataFrame(empty_communes)
    df_errors = pd.DataFrame(errors)

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="post_offices", index=False)
        df_empty.to_excel(writer, sheet_name="empty_communes", index=False)
        df_errors.to_excel(writer, sheet_name="crawl_errors", index=False)

    autosize_and_style_excel(output_file)


# =========================
# MAIN
# =========================

def main() -> None:
    province_file, commune_files, output_file = select_files_gui()

    if not province_file:
        print("Bạn chưa chọn file provinces.txt. Dừng xử lý.")
        return

    if not commune_files:
        print("Bạn chưa chọn file phường/xã/đặc khu. Dừng xử lý.")
        return

    if not output_file:
        print("Bạn chưa chọn nơi lưu file Excel. Dừng xử lý.")
        return

    template_url = read_template_url(province_file)
    print(f"URL mẫu: {template_url}")

    tasks, mapping_errors = build_tasks(province_file, commune_files, template_url)

    print(f"Số file phường/xã đã chọn: {len(commune_files)}")
    print(f"Số request cần crawl: {len(tasks)}")
    print(f"Số lỗi mapping ban đầu: {len(mapping_errors)}")

    rows, empty_communes, crawl_errors = crawl_all(tasks)
    all_errors = mapping_errors + crawl_errors

    export_excel(rows, empty_communes, all_errors, output_file)

    print("\nHOÀN TẤT")
    print(f"File Excel: {output_file}")
    print(f"Số dòng bưu cục: {len(rows)}")
    print(f"Số phường/xã không có dữ liệu: {len(empty_communes)}")
    print(f"Số lỗi: {len(all_errors)}")


if __name__ == "__main__":
    main()
