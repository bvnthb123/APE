# APE Release QA Checklist

Checklist này dùng trước khi gửi bản portable ZIP cho người khác.

## 1. Chuẩn bị source

- [ ] Đã chạy `git pull`.
- [ ] `py main.py status` hiển thị đúng version mới nhất.
- [ ] `py -m pytest -q` chạy đạt toàn bộ test.

## 2. Build executable

- [ ] Chạy `build_windows.bat` không báo lỗi.
- [ ] Tồn tại file `dist\APE\APE.exe`.
- [ ] Bấm đúp `dist\APE\APE.exe` mở được giao diện.
- [ ] App có icon hoặc không báo lỗi icon.

## 3. Kiểm thử tính năng chính

- [ ] Mở app thành công.
- [ ] Import file Excel thành công.
- [ ] Tổng số kỳ hiển thị đúng.
- [ ] Tab Dữ liệu lịch sử hiển thị bảng.
- [ ] Lọc theo ngày hoạt động.
- [ ] Tìm kiếm hoạt động.
- [ ] Tab Thống kê & kiểm tra hiển thị dữ liệu.
- [ ] Tab Biểu đồ hiển thị đủ biểu đồ.
- [ ] Xuất báo cáo Excel thành công.
- [ ] Mở file báo cáo Excel được.
- [ ] Sao lưu DB thành công.
- [ ] Khôi phục DB thành công với file sao lưu vừa tạo.

## 4. Tạo release ZIP

- [ ] Chạy `make_release_zip.bat` không báo lỗi.
- [ ] Tồn tại file `releases\APE-v...-portable.zip`.
- [ ] Giải nén ZIP sang thư mục mới.
- [ ] Bấm đúp `APE.exe` trong thư mục giải nén mở được app.
- [ ] File `HUONG_DAN_NHANH.txt` có trong thư mục release.
- [ ] Thư mục `docs` có hướng dẫn sử dụng.

## 5. Kiểm thử thư mục sạch

- [ ] Copy file ZIP sang một thư mục khác.
- [ ] Giải nén.
- [ ] Chạy app.
- [ ] Import Excel.
- [ ] Xuất báo cáo.
- [ ] Sao lưu database.

## 6. Ghi chú phát hành

- [ ] Ghi lại version.
- [ ] Ghi lại ngày build.
- [ ] Ghi lại máy build.
- [ ] Ghi lại tình trạng test.
