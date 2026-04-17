import math
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
    from openpyxl import Workbook, load_workbook
except ImportError:
    print("Thiếu thư viện openpyxl. Cài bằng lệnh: pip install openpyxl")
    sys.exit(1)


def is_row_empty(values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return False
    return True


def collect_non_empty_rows(file_path: str):
    wb = load_workbook(file_path, read_only=True, data_only=False)
    ws = wb[wb.sheetnames[0]]

    rows = []
    for row in ws.iter_rows(values_only=True):
        values = list(row)
        if not is_row_empty(values):
            rows.append(values)

    wb.close()
    return ws.title, rows


def autosize_columns(ws):
    widths = {}
    for row in ws.iter_rows(values_only=True):
        for idx, value in enumerate(row, start=1):
            text = "" if value is None else str(value)
            widths[idx] = max(widths.get(idx, 0), len(text))

    for idx, width in widths.items():
        col_letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[col_letter].width = min(max(width + 2, 10), 40)


def save_split_files(headers, data_rows, rows_per_file, output_dir: Path, base_name: str, sheet_title: str):
    output_files = []
    total_parts = math.ceil(len(data_rows) / rows_per_file) if data_rows else 1

    for part_index in range(total_parts):
        start = part_index * rows_per_file
        end = start + rows_per_file
        chunk = data_rows[start:end]

        wb_out = Workbook()
        ws_out = wb_out.active
        ws_out.title = sheet_title[:31] if sheet_title else "Sheet1"
        ws_out.append(headers)
        for row in chunk:
            ws_out.append(row)

        autosize_columns(ws_out)

        file_name = f"{base_name}_part_{part_index + 1:03d}.xlsx"
        file_path = output_dir / file_name
        wb_out.save(file_path)
        output_files.append(file_path)

    return output_files


def create_zip_file(files, zip_path: Path):
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)


def main():
    root = tk.Tk()
    root.withdraw()
    root.update()

    file_path = filedialog.askopenfilename(
        title="Chọn file Excel cần tách",
        filetypes=[("Excel files", "*.xlsx *.xlsm *.xltx *.xltm"), ("All files", "*.*")],
    )

    if not file_path:
        return

    try:
        sheet_title, rows = collect_non_empty_rows(file_path)
    except Exception as exc:
        messagebox.showerror("Lỗi", f"Không thể đọc file Excel.\n\nChi tiết: {exc}")
        return

    if not rows:
        messagebox.showwarning("Thông báo", "File Excel không có dữ liệu.")
        return

    headers = rows[0]
    data_rows = rows[1:]
    total_rows = len(data_rows)

    messagebox.showinfo(
        "Tổng số rows",
        f"File: {os.path.basename(file_path)}\n"
        f"Sheet đang xử lý: {sheet_title}\n"
        f"Tổng số rows dữ liệu: {total_rows}",
    )

    if total_rows == 0:
        messagebox.showwarning("Thông báo", "File chỉ có header, không có dữ liệu để tách.")
        return

    rows_per_file = simpledialog.askinteger(
        "Nhập số rows",
        "Nhập số rows cho mỗi file xuất ra:",
        minvalue=1,
        initialvalue=min(1000, total_rows),
    )

    if not rows_per_file:
        return

    source = Path(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = source.parent / f"{source.stem}_split_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        output_files = save_split_files(
            headers=headers,
            data_rows=data_rows,
            rows_per_file=rows_per_file,
            output_dir=output_dir,
            base_name=source.stem,
            sheet_title=sheet_title,
        )

        zip_path = source.parent / f"{source.stem}_split_{timestamp}.zip"
        create_zip_file(output_files, zip_path)
    except Exception as exc:
        messagebox.showerror("Lỗi", f"Xử lý thất bại.\n\nChi tiết: {exc}")
        return

    messagebox.showinfo(
        "Hoàn tất",
        f"Đã tách {len(output_files)} file Excel.\n"
        f"Thư mục xuất: {output_dir}\n"
        f"File zip: {zip_path}",
    )


if __name__ == "__main__":
    main()
