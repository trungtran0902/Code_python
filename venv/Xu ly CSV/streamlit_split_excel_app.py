import copy
import math
import os
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import streamlit as st
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter


st.set_page_config(page_title="Tách file Excel và nén ZIP", page_icon="📦", layout="centered")


def copy_cell_style(src_cell, dst_cell):
    """Copy cell value and basic style."""
    dst_cell.value = src_cell.value
    if src_cell.has_style:
        dst_cell.font = copy.copy(src_cell.font)
        dst_cell.fill = copy.copy(src_cell.fill)
        dst_cell.border = copy.copy(src_cell.border)
        dst_cell.alignment = copy.copy(src_cell.alignment)
        dst_cell.number_format = src_cell.number_format
        dst_cell.protection = copy.copy(src_cell.protection)
    if src_cell.hyperlink:
        dst_cell._hyperlink = copy.copy(src_cell.hyperlink)
    if src_cell.comment:
        dst_cell.comment = copy.copy(src_cell.comment)



def copy_sheet_chunk(src_ws, start_row, end_row, header_rows=1):
    """Create a new worksheet with header + selected row chunk."""
    wb = Workbook()
    dst_ws = wb.active
    dst_ws.title = src_ws.title

    # Copy frozen panes if any
    dst_ws.freeze_panes = src_ws.freeze_panes

    # Copy header rows
    dst_row_idx = 1
    for r in range(1, header_rows + 1):
        for c in range(1, src_ws.max_column + 1):
            copy_cell_style(src_ws.cell(r, c), dst_ws.cell(dst_row_idx, c))
        dst_ws.row_dimensions[dst_row_idx].height = src_ws.row_dimensions[r].height
        dst_row_idx += 1

    # Copy chunk rows
    for r in range(start_row, end_row + 1):
        for c in range(1, src_ws.max_column + 1):
            copy_cell_style(src_ws.cell(r, c), dst_ws.cell(dst_row_idx, c))
        dst_ws.row_dimensions[dst_row_idx].height = src_ws.row_dimensions[r].height
        dst_row_idx += 1

    # Copy column widths
    for col_letter, dim in src_ws.column_dimensions.items():
        dst_ws.column_dimensions[col_letter].width = dim.width
        dst_ws.column_dimensions[col_letter].hidden = dim.hidden

    # Copy merged cells that lie fully inside header or selected chunk
    selected_rows = set(range(1, header_rows + 1)) | set(range(start_row, end_row + 1))
    for merged_range in src_ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        rows_in_range = set(range(min_row, max_row + 1))
        if rows_in_range.issubset(selected_rows):
            # Calculate new row positions in destination sheet
            def map_row(r):
                if r <= header_rows:
                    return r
                return header_rows + (r - start_row) + 1

            new_min_row = map_row(min_row)
            new_max_row = map_row(max_row)
            new_range = f"{get_column_letter(min_col)}{new_min_row}:{get_column_letter(max_col)}{new_max_row}"
            dst_ws.merge_cells(new_range)

    return wb



def workbook_to_bytes(workbook):
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()



def split_excel_to_zip(file_bytes, original_name, sheet_name, rows_per_file, header_rows=1):
    wb = load_workbook(filename=BytesIO(file_bytes))
    ws = wb[sheet_name]

    total_rows = ws.max_row
    if total_rows <= header_rows:
        raise ValueError("File không có dữ liệu để tách.")

    data_start_row = header_rows + 1
    data_rows = total_rows - header_rows
    total_parts = math.ceil(data_rows / rows_per_file)

    base_name = os.path.splitext(original_name)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for part_idx in range(total_parts):
            start_row = data_start_row + (part_idx * rows_per_file)
            end_row = min(start_row + rows_per_file - 1, total_rows)

            part_wb = copy_sheet_chunk(
                src_ws=ws,
                start_row=start_row,
                end_row=end_row,
                header_rows=header_rows,
            )

            part_filename = f"{base_name}_{sheet_name}_part_{part_idx + 1}.xlsx"
            zip_file.writestr(part_filename, workbook_to_bytes(part_wb))

    zip_buffer.seek(0)
    zip_name = f"{base_name}_{sheet_name}_split_{timestamp}.zip"
    return zip_buffer.getvalue(), zip_name, data_rows, total_parts


st.title("📦 Tách file Excel và nén ZIP")
st.write("Upload file Excel, chọn sheet cần tách, nhập số dòng cho mỗi file, sau đó tải file ZIP kết quả.")

uploaded_file = st.file_uploader("Chọn file Excel", type=["xlsx", "xlsm", "xltx", "xltm"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    try:
        preview_wb = load_workbook(filename=BytesIO(file_bytes), read_only=True)
        sheet_names = preview_wb.sheetnames
    except Exception as e:
        st.error(f"Không đọc được file Excel: {e}")
        st.stop()

    selected_sheet = st.selectbox("Chọn sheet cần tách", sheet_names)

    try:
        preview_ws = preview_wb[selected_sheet]
        total_rows = preview_ws.max_row
        total_columns = preview_ws.max_column
        data_rows = max(total_rows - 1, 0)
    except Exception as e:
        st.error(f"Không đọc được sheet đã chọn: {e}")
        st.stop()

    col1, col2 = st.columns(2)
    col1.metric("Tổng số rows", total_rows)
    col2.metric("Số rows dữ liệu", data_rows)

    st.caption("Mặc định xem dòng đầu tiên là header và sẽ được giữ lại trong tất cả file tách.")

    rows_per_file = st.number_input(
        "Nhập số rows dữ liệu cho mỗi file",
        min_value=1,
        max_value=max(data_rows, 1),
        value=min(1000, max(data_rows, 1)),
        step=1,
    )

    if data_rows > 0:
        expected_parts = math.ceil(data_rows / int(rows_per_file))
        st.info(f"Dự kiến tạo ra **{expected_parts}** file Excel trong 1 file ZIP.")

    if st.button("Tách file và tạo ZIP", type="primary"):
        try:
            zip_bytes, zip_name, final_data_rows, total_parts = split_excel_to_zip(
                file_bytes=file_bytes,
                original_name=uploaded_file.name,
                sheet_name=selected_sheet,
                rows_per_file=int(rows_per_file),
                header_rows=1,
            )

            st.success(
                f"Hoàn tất: đã tách {final_data_rows} dòng dữ liệu thành {total_parts} file Excel và nén thành ZIP."
            )
            st.download_button(
                label="⬇️ Tải file ZIP",
                data=zip_bytes,
                file_name=zip_name,
                mime="application/zip",
            )
        except Exception as e:
            st.error(f"Có lỗi khi xử lý file: {e}")
else:
    st.info("Hãy upload file Excel để bắt đầu.")
