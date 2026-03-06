import subprocess
from lxml import etree

def convert_ai_to_svg(ai_path, svg_path):
    # Sử dụng Inkscape để chuyển đổi file .ai sang .svg
    subprocess.run(['inkscape', ai_path, '--export-plain-svg', svg_path], check=True)
    print(f"Đã chuyển đổi {ai_path} sang {svg_path}")

def add_text_to_svg(svg_path, text, output_path, position, font_size=30, color="black"):
    # Load SVG file
    tree = etree.parse(svg_path)
    root = tree.getroot()

    # Create a new text element
    text_element = etree.Element("text", x=str(position[0]), y=str(position[1]), fill=color, style=f"font-size:{font_size}px;")
    text_element.text = text

    # Append the text element to the SVG root
    root.append(text_element)

    # Save the modified SVG
    tree.write(output_path)
    print(f"Đã lưu SVG với text tại {output_path}")

# Đường dẫn tới file .ai và .svg
ai_path = r'C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\input_file.ai'
svg_path = r'C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\converted_file.svg'
output_svg_path = r'C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\output_file.svg'

# Chuyển đổi .ai sang .svg
convert_ai_to_svg(ai_path, svg_path)

# Chèn văn bản vào file .svg
text = 'Hello, World!'
position = (50, 50)  # Vị trí đặt text trên SVG
font_size = 30  # Kích thước chữ
color = "black"  # Màu chữ

add_text_to_svg(svg_path, text, output_svg_path, position, font_size, color)
