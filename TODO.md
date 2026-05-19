# TODO - DWG -> DXF -> GeoJSON -> GIS Mapping

## Step 1
- [ ] Xác định cấu hình template zip và mapping gdb 4 template

## Step 2
- [ ] Sửa `venv/DWG/convert_dwg_shp.py` để:
  - [ ] Cấu hình UPLOAD/TEMP/OUTPUT/CONFIG theo thư mục `venv/DWG` (base hiện tại)
  - [ ] Giải nén template zip vào `temp/templates/` lần đầu và tái sử dụng cho các lần chạy
  - [ ] Thay `mapping_rules.json` để chỉ chứa rule/aliases (không hardcode path gdb)
  - [ ] Load schema layer từ `.gdb` đã giải nén
  - [ ] CRS: nếu input CRS thiếu → gán `EPSG:4326`
  - [ ] Mapping: user chọn 1 template → ghi ra **duy nhất 1 gdb** tương ứng
  - [ ] Output: zip gdb + tên file ổn định

## Step 3
- [ ] Sửa `venv/DWG/mapping_rules.json` nếu cần cho đúng format mới

## Step 4
- [ ] Cập nhật UI text để phản ánh “ghi vào 1 gdb duy nhất”

## Step 5
- [ ] Lint/kiểm tra import và chạy thử (nếu môi trường có đủ deps)

