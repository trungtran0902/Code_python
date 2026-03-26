import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from tkinter import END, StringVar, Tk, filedialog, messagebox
from tkinter import ttk


MAX_PART_SIZE_MB = 100
LOG_FEATURE_INTERVAL = 5000


def sanitize_filename(name):
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid else ch for ch in name)
    return cleaned.strip(" .") or "output"


def find_features_array_bounds(content):
    match = re.search(r'"features"\s*:\s*\[', content)
    if not match:
        raise ValueError("Khong tim thay mang features.")
    return match.start(), match.end()


def extract_feature_texts_from_content(content, progress_callback=None, log_prefix=""):
    _, feature_start = find_features_array_bounds(content)
    in_string = False
    escape = False
    depth = 0
    feature_buffer = []
    features = []

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
                features.append("".join(feature_buffer).strip())
                feature_buffer = []
                if progress_callback and len(features) % LOG_FEATURE_INTERVAL == 0:
                    progress_callback(f"{log_prefix}da doc {len(features)} feature de doi chieu")

    return features


def split_geojson_parts(
    input_path,
    output_dir,
    max_size_mb=MAX_PART_SIZE_MB,
    progress_callback=None,
    percent_callback=None,
    file_progress_offset=0.0,
    file_progress_span=100.0,
):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = max_size_mb * 1024 * 1024
    created_files = []

    if progress_callback:
        progress_callback(f"Doc file {input_path.name} ...")

    total_size_bytes = input_path.stat().st_size

    with input_path.open("r", encoding="utf-8") as source:
        content = source.read()

    if percent_callback:
        percent_callback(file_progress_offset + file_progress_span * 0.2)

    _, feature_start = find_features_array_bounds(content)
    prefix = content[:feature_start]
    suffix = "]}"

    part_index = 1
    current_features = []
    current_size = len(prefix.encode("utf-8")) + len(suffix.encode("utf-8"))

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

    features = extract_feature_texts_from_content(
        content,
        progress_callback=progress_callback,
        log_prefix=f"{input_path.name}: ",
    )
    total_features = max(len(features), 1)
    for feature_counter, feature_text in enumerate(features, start=1):
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
        if percent_callback:
            ratio = feature_counter / total_features
            percent_callback(
                min(
                    file_progress_offset + file_progress_span * (0.2 + ratio * 0.75),
                    file_progress_offset + file_progress_span * 0.95,
                )
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
    if percent_callback:
        percent_callback(file_progress_offset + file_progress_span)

    return created_files


def build_zip(zip_path, files, progress_callback=None, percent_callback=None, start_percent=0.0, end_percent=100.0):
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        total_files = max(len(files), 1)
        for index, file_path in enumerate(files, start=1):
            if progress_callback:
                progress_callback(f"Them vao ZIP: {file_path.name}")
            zf.write(file_path, arcname=file_path.name)
            if percent_callback:
                ratio = index / total_files
                percent_callback(start_percent + (end_percent - start_percent) * ratio)
    return zip_path


def compare_original_and_split_files(original_path, zip_path, progress_callback=None):
    original_path = Path(original_path)
    zip_path = Path(zip_path)
    base_name = sanitize_filename(original_path.stem)
    expected_prefix = f"{base_name}_part_"

    if progress_callback:
        progress_callback(f"Doi chieu file goc: {original_path.name}")

    with original_path.open("r", encoding="utf-8") as source:
        original_content = source.read()
    original_features = extract_feature_texts_from_content(
        original_content,
        progress_callback=progress_callback,
        log_prefix=f"{original_path.name}: ",
    )

    split_features = []
    part_names = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        matching_names = sorted(
            (
                name for name in zf.namelist()
                if Path(name).name.startswith(expected_prefix) and name.lower().endswith(".geojson")
            ),
            key=lambda name: Path(name).name,
        )
        if not matching_names:
            raise ValueError(f"Khong tim thay part nao trong ZIP cho {original_path.name}")

        for index, member_name in enumerate(matching_names, start=1):
            part_names.append(Path(member_name).name)
            if progress_callback:
                progress_callback(f"  Doc part {index}/{len(matching_names)}: {Path(member_name).name}")
            content = zf.read(member_name).decode("utf-8")
            split_features.extend(
                extract_feature_texts_from_content(
                    content,
                    progress_callback=progress_callback,
                    log_prefix=f"{Path(member_name).name}: ",
                )
            )

    mismatch_index = None
    for index, (original_feature, split_feature) in enumerate(zip(original_features, split_features), start=1):
        if original_feature != split_feature:
            mismatch_index = index
            break

    return {
        "original_file": original_path.name,
        "part_names": part_names,
        "original_count": len(original_features),
        "split_count": len(split_features),
        "matched": (
            mismatch_index is None and len(original_features) == len(split_features)
        ),
        "mismatch_index": mismatch_index,
    }


class GeoJsonSplitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cat file GeoJSON duoi 100MB")
        self.root.geometry("760x420")

        self.selected_files = []
        self.zip_path_var = StringVar()
        self.max_size_var = StringVar(value=str(MAX_PART_SIZE_MB))
        self.progress_var = StringVar(value="San sang.")
        self.progress_percent_var = StringVar(value="0%")
        self.last_zip_path = None
        self.verify_results = []

        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        try:
            style.theme_use(style.theme_use())
        except Exception:
            pass
        style.configure("Visible.Horizontal.TProgressbar", thickness=18)

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
        self.open_folder_btn = ttk.Button(
            frame,
            text="Mo thu muc chua ZIP",
            command=self.open_output_folder,
            state="disabled",
        )
        self.open_folder_btn.pack(anchor="w", pady=(0, 12))
        self.verify_btn = ttk.Button(
            frame,
            text="Doi chieu voi file goc",
            command=self.verify_split_output,
            state="disabled",
        )
        self.verify_btn.pack(anchor="w", pady=(0, 12))

        progress_row = ttk.Frame(frame)
        progress_row.pack(fill="x", pady=(0, 8))
        ttk.Label(progress_row, text="Tien do").pack(side="left")
        ttk.Label(progress_row, textvariable=self.progress_percent_var).pack(side="right")

        self.progress_bar = ttk.Progressbar(
            frame,
            mode="determinate",
            style="Visible.Horizontal.TProgressbar",
            maximum=100,
        )
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

    def set_progress_percent(self, value):
        if isinstance(value, (int, float)):
            numeric = max(0.0, min(float(value), 100.0))
            self.progress_bar["value"] = numeric
            self.progress_percent_var.set(f"{numeric:.1f}%")
        else:
            self.progress_percent_var.set(str(value))
        self.root.update()

    def open_output_folder(self):
        if not self.last_zip_path:
            return
        output_dir = Path(self.last_zip_path).parent
        subprocess.Popen(["explorer", str(output_dir)])

    def verify_split_output(self):
        if not self.last_zip_path or not self.selected_files:
            messagebox.showwarning("Thieu du lieu", "Chua co ket qua cat file de doi chieu.")
            return

        self.append_status("Bat dau doi chieu voi file goc ...")
        self.set_progress_percent(0)
        self.verify_results = []

        try:
            total_files = len(self.selected_files)
            for index, file_path in enumerate(self.selected_files, start=1):
                file_start = ((index - 1) / total_files) * 100.0
                file_end = (index / total_files) * 100.0
                self.set_progress_percent(file_start)
                result = compare_original_and_split_files(
                    file_path,
                    self.last_zip_path,
                    progress_callback=self.append_status,
                )
                self.verify_results.append(result)
                self.set_progress_percent(file_end)

                if result["matched"]:
                    self.append_status(
                        f"OK {result['original_file']}: {result['original_count']} feature, "
                        f"{len(result['part_names'])} part, khop du lieu"
                    )
                else:
                    if result["mismatch_index"] is not None:
                        self.append_status(
                            f"LECH {result['original_file']}: sai tai feature thu {result['mismatch_index']}"
                        )
                    else:
                        self.append_status(
                            f"LECH {result['original_file']}: "
                            f"goc={result['original_count']} feature, part={result['split_count']} feature"
                        )

            mismatches = [result for result in self.verify_results if not result["matched"]]
            if mismatches:
                messagebox.showwarning(
                    "Doi chieu xong",
                    f"Co {len(mismatches)} file bi sai lech. Xem log de biet chi tiet.",
                )
            else:
                messagebox.showinfo(
                    "Doi chieu xong",
                    "Tat ca file da cat khop voi file goc.",
                )
        except Exception as exc:
            self.append_status(f"Loi doi chieu: {exc}")
            messagebox.showerror("Loi doi chieu", str(exc))

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
                self.progress_bar["value"] = 0
                self.set_progress_percent(0)
                self.open_folder_btn.config(state="disabled")
                self.verify_btn.config(state="disabled")
                self.last_zip_path = None
                self.verify_results = []
                total_input_files = len(self.selected_files)
                split_end_percent = 90.0
                for idx, file_path in enumerate(self.selected_files, start=1):
                    size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                    file_start = ((idx - 1) / total_input_files) * split_end_percent
                    file_end = (idx / total_input_files) * split_end_percent
                    self.set_progress_percent(file_start)
                    self.append_status(f"Dang xu ly {Path(file_path).name} ({size_mb:.2f} MB)")
                    created_files = split_geojson_parts(
                        file_path,
                        temp_dir,
                        max_size_mb=max_size_mb,
                        progress_callback=self.append_status,
                        percent_callback=self.set_progress_percent,
                        file_progress_offset=file_start,
                        file_progress_span=file_end - file_start,
                    )
                    all_created_files.extend(created_files)
                    self.append_status(f"  -> Tao {len(created_files)} file")

                self.append_status("Dang dong goi file ZIP ...")
                self.set_progress_percent(split_end_percent)
                zip_file = build_zip(
                    zip_path,
                    all_created_files,
                    progress_callback=self.append_status,
                    percent_callback=self.set_progress_percent,
                    start_percent=split_end_percent,
                    end_percent=100.0,
                )
                self.append_status(f"Hoan thanh. ZIP: {zip_file}")
                self.set_progress_percent(100)
                self.last_zip_path = str(zip_file)
                self.open_folder_btn.config(state="normal")
                self.verify_btn.config(state="normal")
            except Exception as exc:
                self.set_progress_percent("Loi")
                messagebox.showerror("Loi", f"Xu ly that bai:\n{exc}")
                self.append_status(f"Loi: {exc}")
                return

        messagebox.showinfo("Hoan thanh", f"Da tao file ZIP:\n{zip_path}")


def main():
    root = Tk()
    app = GeoJsonSplitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
