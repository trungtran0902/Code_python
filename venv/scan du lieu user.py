import requests
from bs4 import BeautifulSoup


def fetch_data(url):
    # Gửi request đến URL
    response = requests.get(url)

    if response.status_code == 200:
        # Phân tích HTML với BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Giả sử dữ liệu nằm trong các thẻ có id hoặc class tương ứng
        try:
            name = soup.find('div', class_='content').text.strip()  # Ví dụ: class_='name-class'
            email = soup.find('div', class_='rowContent').text.strip()  # Ví dụ: class_='email-class'
            phone = soup.find('div', class_='rowContent').text.strip()  # Ví dụ: class_='phone-class'

            return {
                'name': name,
                'email': email,
                'phone': phone
            }
        except AttributeError:
            print("Không tìm thấy dữ liệu trong trang!")
            return None
    else:
        print(f"Lỗi khi truy cập trang: {response.status_code}")
        return None


# Test với một URL
url = "https://map.map4d.vn/manager/user/user/detail/33ee6838-fc1f-4067-8d8f-cea3e0ccffd0"
data = fetch_data(url)

if data:
    print("Dữ liệu thu thập được:")
    print(f"Tên: {data['name']}")
    print(f"Email: {data['email']}")
    print(f"Số điện thoại: {data['phone']}")
