import csv
import os

# Nhập thư mục chứa file CSV
folder_path = input("Nhập đường dẫn thư mục chứa file CSV: ").strip()

# Nhập tên file CSV gốc
file_name = input("Nhập tên file CSV (vd: data.csv): ").strip()

input_file = os.path.join(folder_path, file_name)
rows_per_file = 100_000
file_count = 1

with open(input_file, newline='', encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)  # đọc header

    rows = []
    for i, row in enumerate(reader, start=1):
        rows.append(row)

        if i % rows_per_file == 0:
            output_file = os.path.join(folder_path, f"{file_name}_part_{file_count}.csv")
            with open(output_file, "w", newline='', encoding="utf-8") as out:
                writer = csv.writer(out)
                writer.writerow(header)
                writer.writerows(rows)
            print(f"Đã tạo {output_file} với {len(rows)} records")

            rows = []
            file_count += 1

    # Ghi nốt phần dư
    if rows:
        output_file = os.path.join(folder_path, f"{file_name}_part_{file_count}.csv")
        with open(output_file, "w", newline='', encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerow(header)
            writer.writerows(rows)
        print(f"Đã tạo {output_file} với {len(rows)} records")
