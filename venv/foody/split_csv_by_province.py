import csv
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog
from urllib.parse import urlparse
from xml.sax.saxutils import escape


KNOWN_PROVINCES = {
    "an-giang": "An Giang",
    "ba-ria-vung-tau": "Ba Ria - Vung Tau",
    "bac-giang": "Bac Giang",
    "bac-kan": "Bac Kan",
    "bac-lieu": "Bac Lieu",
    "bac-ninh": "Bac Ninh",
    "ben-tre": "Ben Tre",
    "binh-duong": "Binh Duong",
    "binh-dinh": "Binh Dinh",
    "binh-phuoc": "Binh Phuoc",
    "binh-thuan": "Binh Thuan",
    "ca-mau": "Ca Mau",
    "can-tho": "Can Tho",
    "cao-bang": "Cao Bang",
    "da-lat": "Lam Dong",
    "da-nang": "Da Nang",
    "dak-lak": "Dak Lak",
    "dak-nong": "Dak Nong",
    "dien-bien": "Dien Bien",
    "dong-nai": "Dong Nai",
    "dong-thap": "Dong Thap",
    "gia-lai": "Gia Lai",
    "ha-giang": "Ha Giang",
    "ha-nam": "Ha Nam",
    "ha-noi": "Ha Noi",
    "ha-tinh": "Ha Tinh",
    "hai-duong": "Hai Duong",
    "hai-phong": "Hai Phong",
    "hau-giang": "Hau Giang",
    "hoa-binh": "Hoa Binh",
    "hue": "Hue",
    "hung-yen": "Hung Yen",
    "khanh-hoa": "Khanh Hoa",
    "kien-giang": "Kien Giang",
    "kon-tum": "Kon Tum",
    "lai-chau": "Lai Chau",
    "lam-dong": "Lam Dong",
    "lang-son": "Lang Son",
    "lao-cai": "Lao Cai",
    "long-an": "Long An",
    "nam-dinh": "Nam Dinh",
    "nghe-an": "Nghe An",
    "ninh-binh": "Ninh Binh",
    "ninh-thuan": "Ninh Thuan",
    "phu-quoc": "Kien Giang",
    "phu-tho": "Phu Tho",
    "phu-yen": "Phu Yen",
    "quang-binh": "Quang Binh",
    "quang-nam": "Quang Nam",
    "quang-ngai": "Quang Ngai",
    "quang-ninh": "Quang Ninh",
    "quang-tri": "Quang Tri",
    "soc-trang": "Soc Trang",
    "son-la": "Son La",
    "tay-ninh": "Tay Ninh",
    "thai-binh": "Thai Binh",
    "thai-nguyen": "Thai Nguyen",
    "thanh-hoa": "Thanh Hoa",
    "thua-thien-hue": "Hue",
    "tien-giang": "Tien Giang",
    "tp-hcm": "Ho Chi Minh",
    "tphcm": "Ho Chi Minh",
    "tra-vinh": "Tra Vinh",
    "tuyen-quang": "Tuyen Quang",
    "vinh-long": "Vinh Long",
    "vinh-phuc": "Vinh Phuc",
    "yen-bai": "Yen Bai",
}


def sanitize_sheet_name(name):
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", name).strip()
    return cleaned[:31] or "Sheet1"


def sanitize_file_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name).strip().rstrip(".")
    return cleaned or "unknown"


def excel_column_name(index):
    result = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def cell_xml(row_idx, col_idx, value):
    reference = f"{excel_column_name(col_idx)}{row_idx}"
    if value is None:
        return f'<c r="{reference}" t="inlineStr"><is><t></t></is></c>'

    text = str(value)
    if text == "":
        return f'<c r="{reference}" t="inlineStr"><is><t></t></is></c>'

    escaped = escape(text)
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{reference}" t="inlineStr"><is><t{preserve}>{escaped}</t></is></c>'


def build_sheet_xml(headers, rows):
    row_xml = []

    header_cells = "".join(cell_xml(1, idx + 1, name) for idx, name in enumerate(headers))
    row_xml.append(f'<row r="1">{header_cells}</row>')

    for row_number, row in enumerate(rows, start=2):
        cells = "".join(cell_xml(row_number, idx + 1, row.get(header, "")) for idx, header in enumerate(headers))
        row_xml.append(f'<row r="{row_number}">{cells}</row>')

    max_col = excel_column_name(len(headers))
    dimension = f"A1:{max_col}{max(len(rows) + 1, 1)}"

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        '</worksheet>'
    )


def write_simple_xlsx(output_path, sheet_name, headers, rows):
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )

    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '</Relationships>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        '</Relationships>'
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )

    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:creator>Codex</dc:creator>'
        '<cp:lastModifiedBy>Codex</cp:lastModifiedBy>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>'
        '</cp:coreProperties>'
    )

    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Microsoft Excel</Application>'
        '</Properties>'
    )

    sheet_xml = build_sheet_xml(headers, rows)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", root_rels)
        workbook.writestr("docProps/core.xml", core_xml)
        workbook.writestr("docProps/app.xml", app_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook.writestr("xl/styles.xml", styles_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def detect_province(location_url):
    if not location_url:
        return "Unknown"

    parsed = urlparse(location_url)
    path_parts = [part.strip().lower() for part in parsed.path.split("/") if part.strip()]
    if not path_parts:
        return "Unknown"

    province_slug = path_parts[0]
    province_slug = re.sub(r"[^a-z0-9-]", "", province_slug)
    if not province_slug:
        return "Unknown"

    if province_slug in KNOWN_PROVINCES:
        return KNOWN_PROVINCES[province_slug]

    words = [word for word in province_slug.split("-") if word]
    if not words:
        return "Unknown"

    return " ".join(word.capitalize() for word in words)


def choose_csv_file():
    root = Tk()
    root.withdraw()
    csv_path = filedialog.askopenfilename(
        title="Chon file CSV output",
        filetypes=[("CSV files", "*.csv")],
    )
    root.destroy()
    return csv_path


def main():
    csv_path = choose_csv_file()
    if not csv_path:
        print("Khong chon file CSV.")
        sys.exit(0)

    csv_file = Path(csv_path)
    output_dir = csv_file.with_name(f"{csv_file.stem}_split_by_province")
    output_dir.mkdir(parents=True, exist_ok=True)

    with csv_file.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        if not headers:
            print("File CSV khong co header.")
            sys.exit(1)

        if "location_url" not in headers:
            print("Khong tim thay cot 'location_url' trong file CSV.")
            sys.exit(1)

        grouped_rows = defaultdict(list)

        for row in reader:
            province = detect_province(row.get("location_url", ""))
            row["province"] = province
            grouped_rows[province].append(row)

    if "province" not in headers:
        headers = headers + ["province"]

    created_files = []
    for province, rows in sorted(grouped_rows.items()):
        file_name = sanitize_file_name(province) + ".xlsx"
        output_path = output_dir / file_name
        write_simple_xlsx(
            output_path=output_path,
            sheet_name=sanitize_sheet_name(province),
            headers=headers,
            rows=rows,
        )
        created_files.append(output_path)
        print(f"Da xuat: {output_path}")

    print(f"Hoan tat. Tao {len(created_files)} file Excel trong: {output_dir}")


if __name__ == "__main__":
    main()
