HƯỚNG DẪN CHẠY TOOL TRA NGÀNH NGHỀ KINH DOANH TỪ MÃ SỐ THUẾ

1. Cài Python nếu chưa có:
   https://www.python.org/downloads/

2. Mở Terminal hoặc Command Prompt và chạy lệnh sau để cài thư viện cần thiết:
   pip install pandas openpyxl playwright
   playwright install

3. Đảm bảo file "danh_sach_cong_ty.xlsx" nằm cùng thư mục với file main.py

4. Chạy script:
   python main.py

5. Sau khi chạy xong, kết quả sẽ nằm ở file:
   ket_qua_nganh_nghe.xlsx

Lưu ý:
- Nếu bị chặn truy cập do captcha, có thể cần chuyển sang chạy bằng trình duyệt có giao diện (sửa launch(headless=False))
