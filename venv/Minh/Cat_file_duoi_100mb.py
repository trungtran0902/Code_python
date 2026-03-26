import os
import tempfile
import zipfile
from pathlib import Path
from tkinter import END, StringVar, Tk, filedialog, messagebox
from tkinter import ttk


MAX_PART_SIZE_MB = 100
FEATURES_TOKEN = '"features":['
LOG_FEATURE_INTERVAL = 5000


def sanitize_filename(name):
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid else ch for ch in name)
    return cleaned.strip(" .") or "output"


def split_geojson_parts(input_path, output_dir, max_size_mb=MAX_PART_SIZE_MB, progress_callback=None):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = max_size_mb * 1024 * 1024
    created_files = []

    if progress_callback:
        progress_callback(f"Doc file {input_path.name} ...")

    with input_path.open("r", encoding="utf-8") as source:
        content = source.read()

    feature_token_index = content.find(FEATURES_TOKEN)
    if feature_token_index == -1:
        raise ValueError(f"Khong tim thay mang features trong {input_path.name}")

    prefix = content[: feature_token_index + len(FEATURES_TOKEN)]
    suffix = "]}"
    feature_start = feature_token_index + len(FEATURES_TOKEN)

    part_index = 1
    current_features = []
    current_size = len(prefix.encode("utf-8")) + len(suffix.encode("utf-8"))

    in_string = False
    escape = False
    depth = 0
    feature_buffer = []

    def flush_current_part():
        nonlocal part_index, current_features, current_size
        if not current_features:
            return

        output_name = f"{sanitize_filename(input_path.stem)}_part_{part_index}.geojson"
        output_path = output_dir / output_name
        if progress_callback:
            progress_callback(
                f"Ghi {output_name} - {len(current_features)} feature - "
                f"{current_size / (1024 * 1024):.2f} MB"
            )
        with output_path.open("w", encoding="utf-8") as out:
            out.write(prefix)
            out.write(",".join(current_features))
            out.write(suffix)

        created_files.append(output_path)
        part_index += 1
        current_features = []
        current_size = len(prefix.encode("utf-8")) + len(suffix.encode("utf-8"))

    feature_counter = 0
    for ch in content[feature_start:]:
        if depth == 0 and ch in " \r\n\t,":
            continue
        if depth == 0 and ch == "]":
            break

        feature_buffer.append(ch)

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                feature_text = "".join(feature_buffer).strip()
                feature_buffer = []
                feature_counter += 1
                feature_size = len(feature_text.encode("utf-8"))
                separator_size = 1 if current_features else 0

                if current_features and current_size + separator_size + feature_size > max_bytes:
                    flush_current_part()
                    separator_size = 0

                current_features.append(feature_text)
                current_size += separator_size + feature_size

                if progress_callback and feature_counter % LOG_FEATURE_INTERVAL == 0:
                    progress_callback(
                        f"{input_path.name}: da doc {feature_counter} feature, "
                        f"part hien tai ~ {current_size / (1024 * 1024):.2f} MB"
                    )

                if current_size > max_bytes and len(current_features) == 1:
                    flush_current_part()

    flush_current_part()

    if not created_files:
        raise ValueError(f"Khong tach duoc feature nao tu {input_path.name}")

    if progress_callback:
        progress_callback(
            f"Hoan tat tach {input_path.name}: {feature_counter} feature, {len(created_files)} file"
        )

    return created_files


def build_zip(zip_path, files, progress_callback=None):
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            if progress_callback:
                progress_callback(f"Them vao ZIP: {file_path.name}")
            zf.write(file_path, arcname=file_path.name)
    return zip_path


class GeoJsonSplitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cat file GeoJSON duoi 100MB")
        self.root.geometry("760x420")

        self.selected_files = []
        self.zip_path_var = StringVar()
        self.max_size_var = StringVar(value=str(MAX_PART_SIZE_MB))
        self.progress_var = StringVar(value="San sang.")

        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="B1: Chon file GeoJSON tren 100MB").pack(anchor="w")
        ttk.Button(frame, text="Chon file", command=self.choose_files).pack(anchor="w", pady=(6, 10))

        self.file_list = ttk.Treeview(frame, columns=("name", "size"), show="headings", height=8)
        self.file_list.heading("name", text="Ten file")
        self.file_list.heading("size", text="Dung luong (MB)")
        self.file_list.column("name", width=520)
        self.file_list.column("size", width=120, anchor="center")
        self.file_list.pack(fill="x", pady=(0, 12))

        size_row = ttk.Frame(frame)
        size_row.pack(fill="x", pady=(0, 12))
        ttk.Label(size_row, text="B2: Gioi han kich thuoc moi file (MB)").pack(side="left")
        ttk.Entry(size_row, textvariable=self.max_size_var, width=10).pack(side="left", padx=(8, 0))

        zip_row = ttk.Frame(frame)
        zip_row.pack(fill="x", pady=(0, 12))
        ttk.Label(zip_row, text="B3: Chon file ZIP dau ra").pack(side="left")
        ttk.Entry(zip_row, textvariable=self.zip_path_var, width=60).pack(side="left", padx=(8, 8), fill="x", expand=True)
        ttk.Button(zip_row, text="Chon ZIP", command=self.choose_zip_path).pack(side="left")

        ttk.Button(frame, text="Bat dau xu ly", command=self.run).pack(anchor="w", pady=(0, 12))

        self.progress_bar = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(frame, textvariable=self.progress_var).pack(anchor="w", pady=(0, 12))

        ttk.Label(frame, text="Trang thai").pack(anchor="w")
        self.status_box = ttk.Treeview(frame, columns=("status",), show="headings", height=8)
        self.status_box.heading("status", text="Log")
        self.status_box.column("status", width=700)
        self.status_box.pack(fill="both", expand=True)

    def append_status(self, message):
        self.status_box.insert("", END, values=(message,))
        self.status_box.yview_moveto(1)
        self.progress_var.set(message)
        self.root.update()

    def choose_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Chon file GeoJSON",
            filetypes=[("GeoJSON files", "*.geojson"), ("JSON files", "*.json")],
        )
        if not file_paths:
            return

        self.selected_files = list(file_paths)
        for item in self.file_list.get_children():
            self.file_list.delete(item)

        for file_path in self.selected_files:
            size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            self.file_list.insert("", END, values=(Path(file_path).name, f"{size_mb:.2f}"))

        if not self.zip_path_var.get().strip():
            first_name = sanitize_filename(Path(self.selected_files[0]).stem)
            default_zip = Path(self.selected_files[0]).with_name(f"{first_name}_split.zip")
            self.zip_path_var.set(str(default_zip))

    def choose_zip_path(self):
        zip_path = filedialog.asksaveasfilename(
            title="Luu file ZIP",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
        )
        if zip_path:
            self.zip_path_var.set(zip_path)

    def run(self):
        if not self.selected_files:
            messagebox.showwarning("Thieu file", "Ban chua chon file GeoJSON.")
            return

        zip_path = self.zip_path_var.get().strip()
        if not zip_path:
            messagebox.showwarning("Thieu file ZIP", "Ban chua chon file ZIP dau ra.")
            return

        try:
            max_size_mb = int(self.max_size_var.get().strip())
        except ValueError:
            messagebox.showwarning("Sai gia tri", "Kich thuoc file phai la so nguyen.")
            return

        all_created_files = []
        with tempfile.TemporaryDirectory(prefix="geojson_split_") as temp_dir:
            try:
                self.progress_bar.start(10)
                for file_path in self.selected_files:
                    size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                    self.append_status(f"Dang xu ly {Path(file_path).name} ({size_mb:.2f} MB)")
                    created_files = split_geojson_parts(
                        file_path,
                        temp_dir,
                        max_size_mb=max_size_mb,
                        progress_callback=self.append_status,
                    )
                    all_created_files.extend(created_files)
                    self.append_status(f"  -> Tao {len(created_files)} file")

                self.append_status("Dang dong goi file ZIP ...")
                zip_file = build_zip(zip_path, all_created_files, progress_callback=self.append_status)
                self.append_status(f"Hoan thanh. ZIP: {zip_file}")
            except Exception as exc:
                self.progress_bar.stop()
                messagebox.showerror("Loi", f"Xu ly that bai:\n{exc}")
                self.append_status(f"Loi: {exc}")
                return
            finally:
                self.progress_bar.stop()

        messagebox.showinfo("Hoan thanh", f"Da tao file ZIP:\n{zip_path}")


def main():
    root = Tk()
    app = GeoJsonSplitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
