import requests

url = "https://sanpham.starglobal3d.vn/managements/user/assets/Load-Model-3D/php/load_model.php?id=222334&model_id=model-606aeabe626530cb40466d88&lang=vn"
headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    with open("model.glb", "wb") as file:
        file.write(response.content)
    print("Tải thành công: model.glb")
else:
    print(f"Lỗi tải về: {response.status_code}")
