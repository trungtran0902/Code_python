from __future__ import annotations

import re
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

OUTPUT_SUFFIX = "_pages"
IMAGE_EXT = ".png"
RENDER_SCALE = 2.0


def slugify_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", value).strip()
    value = re.sub(r"\s+", "_", value)
    return value or "pdf_file"


def ask_for_input_dir() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected_dir = filedialog.askdirectory(
            title="Chon thu muc chua cac file PDF",
            mustexist=True,
        )
        if not selected_dir:
            return None
        return Path(selected_dir)
    finally:
        root.destroy()


def collect_pdf_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def open_pdf_backend():
    try:
        import fitz  # type: ignore

        return "fitz", fitz
    except Exception:
        pass

    try:
        import pypdfium2  # type: ignore

        return "pypdfium2", pypdfium2
    except Exception:
        pass

    raise ModuleNotFoundError(
        "Khong tim thay thu vien render PDF. Hay cai 1 trong 2 goi: 'PyMuPDF' hoac 'pypdfium2'."
    )


def export_pdf_pages(pdf_path: Path, output_root: Path, backend_name: str, backend_module) -> tuple[int, Path]:
    pdf_output_dir = output_root / f"{slugify_name(pdf_path.stem)}{OUTPUT_SUFFIX}"
    pdf_output_dir.mkdir(parents=True, exist_ok=True)

    if backend_name == "fitz":
        doc = backend_module.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=backend_module.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
            image_path = pdf_output_dir / f"page_{page_index + 1:03d}{IMAGE_EXT}"
            pix.save(image_path)
        return len(doc), pdf_output_dir

    if backend_name == "pypdfium2":
        pdf = backend_module.PdfDocument(str(pdf_path))
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            bitmap = page.render(scale=RENDER_SCALE * 72 / 72)
            image = bitmap.to_pil()
            image_path = pdf_output_dir / f"page_{page_index + 1:03d}{IMAGE_EXT}"
            image.save(image_path)
        return len(pdf), pdf_output_dir

    raise RuntimeError(f"Backend PDF khong duoc ho tro: {backend_name}")


def main() -> None:
    try:
        backend_name, backend_module = open_pdf_backend()
    except ModuleNotFoundError as exc:
        messagebox.showerror("Thieu thu vien PDF", str(exc))
        print(exc)
        return

    input_dir = ask_for_input_dir()
    if input_dir is None:
        print("Da huy thao tac.")
        return

    pdf_files = collect_pdf_files(input_dir)
    if not pdf_files:
        messagebox.showwarning("Khong tim thay PDF", f"Khong co file PDF nao trong thu muc:\n{input_dir}")
        return

    output_root = input_dir / "output_pdf_images"
    output_root.mkdir(parents=True, exist_ok=True)

    total_pages = 0
    success_files = 0
    failed_files: list[str] = []

    print(f"Thu muc input: {input_dir}")
    print(f"So file PDF tim thay: {len(pdf_files)}")
    print(f"Backend render PDF: {backend_name}")

    for pdf_path in pdf_files:
        print(f"\nDang xu ly PDF: {pdf_path}")
        try:
            page_count, pdf_output_dir = export_pdf_pages(pdf_path, output_root, backend_name, backend_module)
            total_pages += page_count
            success_files += 1
            print(f"Da xuat {page_count} page vao: {pdf_output_dir}")
        except Exception as exc:
            failed_files.append(f"{pdf_path} | {exc}")
            print(f"Loi khi xu ly {pdf_path}: {exc}")

    if failed_files:
        failed_log_path = output_root / "failed_pdfs.txt"
        failed_log_path.write_text("\n".join(failed_files), encoding="utf-8")
        print(f"\nDa ghi log loi tai: {failed_log_path}")

    print("\n================ HOAN TAT ================")
    print(f"Tong so file PDF: {len(pdf_files)}")
    print(f"So file xu ly thanh cong: {success_files}")
    print(f"So file loi: {len(failed_files)}")
    print(f"Tong so page da xuat: {total_pages}")
    print(f"Thu muc output: {output_root}")
    print("==========================================")

    messagebox.showinfo(
        "Hoan tat",
        "Da trich xuat anh tu PDF.\n\n"
        f"Tong so file PDF: {len(pdf_files)}\n"
        f"So file xu ly thanh cong: {success_files}\n"
        f"So file loi: {len(failed_files)}\n"
        f"Tong so page da xuat: {total_pages}\n\n"
        f"Thu muc output:\n{output_root}",
    )


if __name__ == "__main__":
    main()
