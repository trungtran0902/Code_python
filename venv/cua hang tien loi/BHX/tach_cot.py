import re
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import os


# ==============================
# 1. TÁCH NGOẶC CẤP 1
# ==============================
def top_level_parentheses_groups(s: str):
    s = s.strip()
    groups = []
    stack = []
    start_idx = None

    for i, ch in enumerate(s):
        if ch == "(":
            if not stack:
                start_idx = i
            stack.append(i)
        elif ch == ")":
            if stack:
                stack.pop()
                if not stack and start_idx is not None:
                    groups.append(s[start_idx + 1:i].strip())
                    start_idx = None

    base = s
    if groups:
        first_open = s.find("(")
        base = s[:first_open].rstrip()

    return base, groups


# ==============================
# 2. NHẬN DIỆN ĐỊA CHỈ
# ==============================
def looks_like_address(text: str) -> bool:
    t = text.lower()

    keywords = [
        "p.", "phường", "q.", "quận", "tp.", "tỉnh",
        "tx.", "huyện", "đường", "khu vực",
        "việt nam", "tờ bản đồ", "thửa đất"
    ]

    if "," in text:
        return True

    if any(k in t for k in keywords):
        return True

    if re.search(r"\d", text) and "đường" in t:
        return True

    return False


# ==============================
# 3. TÁCH NOTE KHỎI ĐỊA CHỈ
# ==============================
def split_address_and_note(addr_text: str):
    t = addr_text.strip()

    m = re.search(r"\s*\(([^()]*)\)\s*$", t)
    if m:
        note = m.group(1).strip()
        address = re.sub(r"\s*\([^()]*\)\s*$", "", t).strip()
        return address, note

    return t, ""


# ==============================
# 4. HÀM CHÍNH
# ==============================
def parse_bhx_row(raw: str):
    raw = (raw or "").strip()

    if not raw:
        return {"name": "", "address": "", "note": ""}

    base, groups = top_level_parentheses_groups(raw)

    name = base.strip()
    address = ""
    note = ""

    if not groups:
        return {"name": name, "address": "", "note": ""}

    if len(groups) == 1:
        g0 = groups[0]

        if looks_like_address(g0):
            address, note = split_address_and_note(g0)
        else:
            name = f"{name} ({g0})"

        return {"name": name, "address": address, "note": note}

    g0 = groups[0]

    if not looks_like_address(g0):
        name = f"{name} ({g0})"
        addr_candidate = groups[-1]
    else:
        addr_candidate = groups[-1]

    address, note = split_address_and_note(addr_candidate)

    return {"name": name, "address": address, "note": note}


# ==============================
# 5. CHỌN FILE & XỬ LÝ
# ==============================
def main():

    # Ẩn cửa sổ tkinter chính
    root = tk.Tk()
    root.withdraw()

    # Mở hộp thoại chọn file
    file_path = filedialog.askopenfilename(
        title="Chọn file Excel",
        filetypes=[("Excel files", "*.xlsx *.xls")]
    )

    if not file_path:
        messagebox.showwarning("Thông báo", "Bạn chưa chọn file!")
        return

    try:
        df = pd.read_excel(file_path)

        column_name = "Ten cua hang"

        if column_name not in df.columns:
            messagebox.showerror(
                "Lỗi",
                f"Không tìm thấy cột '{column_name}' trong file!"
            )
            return

        results = df[column_name].apply(parse_bhx_row)
        results_df = pd.DataFrame(results.tolist())

        final_df = pd.concat([df, results_df], axis=1)

        # Tạo tên file output
        base_name = os.path.splitext(file_path)[0]
        output_file = base_name + "_output.xlsx"

        final_df.to_excel(output_file, index=False)

        messagebox.showinfo("Hoàn thành", f"Đã tạo file:\n{output_file}")

    except Exception as e:
        messagebox.showerror("Lỗi", str(e))


if __name__ == "__main__":
    main()