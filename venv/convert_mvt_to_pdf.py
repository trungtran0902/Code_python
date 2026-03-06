import mapbox_vector_tile
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# === CẤU HÌNH ===
input_file = "61504.mvt"  # Đổi tên file MVT của bạn ở đây
output_file = "output_vector_data.pdf"

# === ĐỌC FILE MVT ===
with open(input_file, "rb") as f:
    tile_data = f.read()

# Giải mã MVT thành dict Python
tile = mapbox_vector_tile.decode(tile_data)

# === TẠO FILE PDF ===
c = canvas.Canvas(output_file, pagesize=A4)
width, height = A4
y = height - 40
line_height = 14

for layer_name, layer in tile.items():
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, f"Layer: {layer_name}")
    y -= line_height * 2

    for idx, feature in enumerate(layer["features"]):
        geom_type = feature["geometry"]["type"]
        props = feature.get("properties", {})
        prop_str = ", ".join(f"{k}: {v}" for k, v in props.items())

        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Feature {idx + 1} ({geom_type}): {prop_str[:120]}...")
        y -= line_height

        # Tạo trang mới nếu gần cuối
        if y < 50:
            c.showPage()
            y = height - 40

c.save()
print(f"✅ Đã tạo file PDF: {output_file}")
