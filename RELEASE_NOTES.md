# APE Release Notes

## v1.0.0 - Portable Release & QA

Đây là bản phát hành portable đầu tiên được chuẩn hóa quy trình đóng gói và kiểm thử.

### Có gì trong bản này

- Ứng dụng desktop APE chạy bằng `APE.exe`.
- Nhập và kiểm tra file Excel.
- Lưu dữ liệu vào SQLite.
- Xem dữ liệu lịch sử.
- Lọc theo ngày và tìm kiếm nhanh.
- Thống kê lịch sử.
- Biểu đồ trực quan.
- Xuất báo cáo Excel.
- Sao lưu và khôi phục database.
- Tạo shortcut desktop.
- Tạo file ZIP portable để gửi cho người dùng khác.

### File quan trọng

- `APE.exe`: file chạy ứng dụng.
- `HUONG_DAN_NHANH.txt`: hướng dẫn mở nhanh.
- `docs/README_FOR_USERS.md`: hướng dẫn sử dụng cho người dùng cuối.
- `docs/RELEASE_QA_CHECKLIST.md`: checklist kiểm thử bản phát hành.

### Lưu ý kỹ thuật

- Đây là bản portable folder, không phải installer.
- Không copy riêng `APE.exe` ra khỏi thư mục release.
- Database được tạo trong thư mục `data` khi ứng dụng chạy.
- Báo cáo xuất ra nằm trong thư mục `reports` hoặc vị trí người dùng chọn.

### Giới hạn phạm vi

APE chỉ mô tả và kiểm tra dữ liệu lịch sử. Ứng dụng không dự đoán, không cam kết và không bảo đảm bất kỳ kết quả tương lai nào.
