import io
import base64
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from tkinter import StringVar, Tk, filedialog, messagebox
from tkinter import ttk

import fitz


TITLE_MAX_Y = 60
FOOTER_MIN_MARGIN = 40
ITEM_MAX_VERTICAL_GAP = 30
ITEM_MAX_CENTER_DELTA = 45
SVG_FALLBACK_SCALE = 2
MIN_CLIP_SIZE = 8


def sanitize_name(value):
    value = re.sub(r'[<>:"/\\|?*]+', "_", str(value).strip())
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .") or "untitled"


def extract_text_blocks(page):
    blocks = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = block
        cleaned = " ".join((text or "").split())
        if not cleaned:
            continue
        blocks.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "cx": (x0 + x1) / 2,
                "text": cleaned,
            }
        )
    return blocks


def detect_title(blocks):
    candidates = [b for b in blocks if b["y0"] <= TITLE_MAX_Y]
    if not candidates:
        return "Untitled"
    candidates.sort(key=lambda b: (b["y0"], b["x0"]))
    return candidates[0]["text"]


def group_item_blocks(blocks, page_height):
    content_blocks = [
        b
        for b in blocks
        if TITLE_MAX_Y < b["y0"] < page_height - FOOTER_MIN_MARGIN
    ]
    content_blocks.sort(key=lambda b: (b["y0"], b["x0"]))

    items = []
    for block in content_blocks:
        matched_item = None
        for item in items:
            if abs(block["cx"] - item["cx"]) > ITEM_MAX_CENTER_DELTA:
                continue
            if 0 <= block["y0"] - item["last_y1"] <= ITEM_MAX_VERTICAL_GAP:
                matched_item = item
                break

        if matched_item is None:
            items.append(
                {
                    "cx": block["cx"],
                    "blocks": [block],
                    "last_y1": block["y1"],
                }
            )
        else:
            matched_item["blocks"].append(block)
            matched_item["last_y1"] = max(matched_item["last_y1"], block["y1"])

    normalized_items = []
    for item in items:
        grouped_blocks = sorted(item["blocks"], key=lambda b: (b["y0"], b["x0"]))
        normalized_items.append(
            {
                "name": grouped_blocks[0]["text"],
                "subtitle": grouped_blocks[1]["text"] if len(grouped_blocks) > 1 else "",
                "cx": item["cx"],
                "name_y0": grouped_blocks[0]["y0"],
                "name_y1": grouped_blocks[0]["y1"],
                "text_bottom": max(block["y1"] for block in grouped_blocks),
            }
        )

    normalized_items.sort(key=lambda item: (item["name_y0"], item["cx"]))
    return normalized_items


def cluster_values(values, threshold):
    clusters = []
    for value in sorted(values):
        if not clusters or abs(value - clusters[-1][-1]) > threshold:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [sum(cluster) / len(cluster) for cluster in clusters]


def build_crop_plan(items, page_rect, title_bottom):
    if not items:
        return []

    row_centers = cluster_values([item["name_y0"] for item in items], threshold=35)
    col_centers = cluster_values([item["cx"] for item in items], threshold=80)

    row_top_bounds = []
    row_bottom_bounds = []
    for row_index, row_center in enumerate(row_centers):
        current_row_items = [item for item in items if abs(item["name_y0"] - row_center) <= 25]
        current_row_top = min(item["name_y0"] for item in current_row_items)
        if row_index == 0:
            top = title_bottom + 20
        else:
            prev_center = row_centers[row_index - 1]
            prev_items = [item for item in items if abs(item["name_y0"] - prev_center) <= 25]
            top = max(item["text_bottom"] for item in prev_items) + 8
        bottom = current_row_top - 8
        row_top_bounds.append(top)
        row_bottom_bounds.append(bottom)

    col_left_bounds = []
    col_right_bounds = []
    for idx, center in enumerate(col_centers):
        if idx == 0:
            left = 18
        else:
            left = (col_centers[idx - 1] + center) / 2
        if idx == len(col_centers) - 1:
            right = page_rect.width - 18
        else:
            right = (center + col_centers[idx + 1]) / 2
        col_left_bounds.append(left)
        col_right_bounds.append(right)

    crop_plan = []
    for item in items:
        row_idx = min(range(len(row_centers)), key=lambda i: abs(row_centers[i] - item["name_y0"]))
        col_idx = min(range(len(col_centers)), key=lambda i: abs(col_centers[i] - item["cx"]))
        left = col_left_bounds[col_idx]
        top = row_top_bounds[row_idx]
        right = col_right_bounds[col_idx]
        bottom = row_bottom_bounds[row_idx]

        if right - left < MIN_CLIP_SIZE or bottom - top < MIN_CLIP_SIZE:
            continue

        crop_plan.append(
            {
                "name": item["name"],
                "subtitle": item["subtitle"],
                "rect": fitz.Rect(left, top, right, bottom),
            }
        )
    return crop_plan


def normalize_clip_rect(clip_rect, page_rect):
    left = max(page_rect.x0, min(clip_rect.x0, page_rect.x1))
    top = max(page_rect.y0, min(clip_rect.y0, page_rect.y1))
    right = max(page_rect.x0, min(clip_rect.x1, page_rect.x1))
    bottom = max(page_rect.y0, min(clip_rect.y1, page_rect.y1))

    if right <= left:
        right = min(page_rect.x1, left + MIN_CLIP_SIZE)
    if bottom <= top:
        bottom = min(page_rect.y1, top + MIN_CLIP_SIZE)

    if right - left < MIN_CLIP_SIZE:
        right = min(page_rect.x1, left + MIN_CLIP_SIZE)
    if bottom - top < MIN_CLIP_SIZE:
        bottom = min(page_rect.y1, top + MIN_CLIP_SIZE)

    if right - left < MIN_CLIP_SIZE or bottom - top < MIN_CLIP_SIZE:
        return None

    return fitz.Rect(left, top, right, bottom)


def render_clip_as_svg(page, clip_rect):
    clip_rect = normalize_clip_rect(clip_rect, page.rect)
    if clip_rect is None:
        raise ValueError("Clip rect khong hop le.")

    pix = page.get_pixmap(
        matrix=fitz.Matrix(SVG_FALLBACK_SCALE, SVG_FALLBACK_SCALE),
        clip=clip_rect,
        alpha=False,
    )
    png_bytes = pix.tobytes("png")
    encoded = base64.b64encode(png_bytes).decode("ascii")
    width = max(int(clip_rect.width * SVG_FALLBACK_SCALE), 1)
    height = max(int(clip_rect.height * SVG_FALLBACK_SCALE), 1)
    svg_text = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<image width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/>'
        "</svg>"
    )
    return svg_text.encode("utf-8"), ".svg"


def export_icons_to_zip(pdf_path, zip_path, progress_callback=None):
    doc = fitz.open(pdf_path)
    name_counters = defaultdict(int)
    skipped_icons = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for page_index, page in enumerate(doc):
            blocks = extract_text_blocks(page)
            title = sanitize_name(detect_title(blocks))

            title_blocks = [b for b in blocks if b["y0"] <= TITLE_MAX_Y]
            title_bottom = max((b["y1"] for b in title_blocks), default=40)

            items = group_item_blocks(blocks, page.rect.height)
            crop_plan = build_crop_plan(items, page.rect, title_bottom)

            for icon in crop_plan:
                try:
                    file_bytes, suffix = render_clip_as_svg(page, icon["rect"])
                except Exception as exc:
                    skipped_icons.append(
                        {
                            "page": page_index + 1,
                            "title": title,
                            "icon": icon["name"],
                            "error": str(exc),
                        }
                    )
                    continue
                base_name = sanitize_name(icon["name"])
                folder_name = title

                name_counters[(folder_name, base_name)] += 1
                order = name_counters[(folder_name, base_name)]
                if order > 1:
                    file_name = f"{base_name}_{order}{suffix}"
                else:
                    file_name = f"{base_name}{suffix}"

                zip_member = f"{folder_name}/{file_name}"
                zf.writestr(zip_member, file_bytes)

            if progress_callback:
                progress_callback(page_index + 1, len(doc), title, len(crop_plan))

        if skipped_icons:
            report_lines = [
                "Cac icon bi bo qua do crop khong hop le:",
                "",
            ]
            for item in skipped_icons:
                report_lines.append(
                    f"Page {item['page']} | {item['title']} | {item['icon']} | {item['error']}"
                )
            zf.writestr("skipped_icons.txt", "\n".join(report_lines).encode("utf-8"))


class IconExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chuyen Icon Tu PDF")
        self.root.geometry("760x280")

        self.pdf_path_var = StringVar()
        self.zip_path_var = StringVar()
        self.status_var = StringVar(value="Chon file PDF de bat dau.")

        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="B1: Chon file PDF").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.pdf_path_var, width=80).grid(
            row=1, column=0, padx=(0, 8), pady=(4, 12), sticky="ew"
        )
        ttk.Button(frame, text="Chon PDF", command=self.choose_pdf).grid(
            row=1, column=1, pady=(4, 12), sticky="ew"
        )

        ttk.Label(frame, text="B2: Chon file ZIP ket qua").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.zip_path_var, width=80).grid(
            row=3, column=0, padx=(0, 8), pady=(4, 12), sticky="ew"
        )
        ttk.Button(frame, text="Chon ZIP", command=self.choose_zip).grid(
            row=3, column=1, pady=(4, 12), sticky="ew"
        )

        ttk.Label(
            frame,
            text=(
                "B3: Xu ly PDF. Icon se duoc nhom theo tieu de trang va xuat vao file ZIP."
            ),
        ).grid(row=4, column=0, columnspan=2, sticky="w")

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 8))

        ttk.Label(frame, textvariable=self.status_var, wraplength=700).grid(
            row=6, column=0, columnspan=2, sticky="w"
        )

        ttk.Button(frame, text="Bat dau xu ly", command=self.run).grid(
            row=7, column=0, columnspan=2, pady=(16, 0)
        )

        frame.columnconfigure(0, weight=1)

    def choose_pdf(self):
        pdf_path = filedialog.askopenfilename(
            title="Chon file PDF",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not pdf_path:
            return

        self.pdf_path_var.set(pdf_path)
        default_zip = str(Path(pdf_path).with_name(f"{Path(pdf_path).stem}_icons.zip"))
        self.zip_path_var.set(default_zip)
        self.status_var.set("Da chon file PDF.")

    def choose_zip(self):
        zip_path = filedialog.asksaveasfilename(
            title="Luu file ZIP",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
        )
        if zip_path:
            self.zip_path_var.set(zip_path)

    def update_progress(self, current_page, total_pages, title, icon_count):
        self.progress["maximum"] = total_pages
        self.progress["value"] = current_page
        self.status_var.set(
            f"Dang xu ly trang {current_page}/{total_pages}: {title} - {icon_count} icon."
        )
        self.root.update_idletasks()

    def run(self):
        pdf_path = self.pdf_path_var.get().strip()
        zip_path = self.zip_path_var.get().strip()

        if not pdf_path:
            messagebox.showwarning("Thieu file", "Ban chua chon file PDF.")
            return

        if not zip_path:
            messagebox.showwarning("Thieu duong dan", "Ban chua chon file ZIP dau ra.")
            return

        try:
            self.progress["value"] = 0
            self.status_var.set("Dang xu ly...")
            export_icons_to_zip(pdf_path, zip_path, self.update_progress)
        except Exception as exc:
            messagebox.showerror("Loi", f"Xu ly that bai:\n{exc}")
            self.status_var.set("Xu ly that bai.")
            return

        self.status_var.set(f"Hoan thanh. File ZIP da duoc tao tai: {zip_path}")
        messagebox.showinfo("Hoan thanh", f"Da xuat icon vao:\n{zip_path}")


def main():
    root = Tk()
    app = IconExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
