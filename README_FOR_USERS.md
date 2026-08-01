# Hướng dẫn sử dụng nhanh APE

APE là ứng dụng desktop dùng để nhập file Excel dữ liệu lịch sử, kiểm tra dữ liệu, xem bảng thống kê, xem biểu đồ, xem tín hiệu lịch sử và xuất báo cáo Excel.

## Cách mở ứng dụng

1. Giải nén file `APE-v...-portable.zip`.
2. Mở thư mục đã giải nén.
3. Bấm đúp vào `APE.exe`.
4. Nếu Windows hiện cảnh báo bảo mật, chọn `More info` rồi chọn `Run anyway`.

Không copy riêng file `APE.exe` ra ngoài. Hãy giữ nguyên cả thư mục ứng dụng.

## Nhập dữ liệu Excel

1. Bấm `Nhập file Excel`.
2. Chọn file `.xlsx` hoặc `.xls`.
3. Xem báo cáo kiểm tra.
4. Bấm xác nhận để nhập dữ liệu.

Sau khi nhập xong, tab Tổng quan, Dữ liệu lịch sử, Thống kê, Pattern Mining và Biểu đồ sẽ tự cập nhật.

## Tìm kiếm và lọc dữ liệu

Vào tab `Dữ liệu lịch sử`:

- Chọn `Từ ngày` và `Đến ngày` để lọc theo thời gian.
- Gõ vào ô tìm kiếm để tìm theo ngày, thứ, bộ số, tổng hoặc tên file nguồn.
- Bấm `Lọc` để áp dụng.
- Bấm `Xóa lọc` để quay lại toàn bộ dữ liệu.

## Pattern Mining

Vào tab `Pattern Mining`:

1. Chọn `Độ trễ N+`.
2. Chọn `Support tối thiểu`.
3. Chọn `Top tín hiệu`.
4. Bấm `Tính tín hiệu lịch sử`.

APE sẽ tính tín hiệu bằng ba lớp:

- Rule số đơn lẻ dạng `số ở kỳ N -> số ở kỳ N+lag`.
- Cấu trúc dãy gồm lẻ/chẵn và phân vùng số `01-09`, `10-20`, `21-30`, `31-40`, `41-45`.
- Độ lặp số giữa kỳ `N` và kỳ `N+lag`, ví dụ kỳ `N+3` thường trùng 0, 1, 2 hay nhiều số so với kỳ N.

Bảng `Top tín hiệu lịch sử từ kỳ dữ liệu cuối` là danh sách tín hiệu được chấm điểm theo rule lịch sử, cấu trúc dãy và độ lặp N→N+lag.

Bảng `Backtest walk-forward` cho biết các tín hiệu đó từng hoạt động thế nào khi kiểm định ngược trên dữ liệu cũ. Bảng này cũng hiển thị thêm các dòng về độ lặp, như số trùng trung bình, tỷ lệ trùng ít nhất 1 số và phân bố số trùng giữa hai kỳ theo độ trễ đã chọn.

## Xuất báo cáo Excel

1. Bấm `Xuất báo cáo Excel`.
2. Chọn nơi lưu file.
3. Mở file Excel đã xuất.

Báo cáo gồm các sheet: Tổng quan, Dữ liệu, Thống kê 01-45, Cặp số, Bộ ba, Kiểm tra và Biểu đồ.

## Sao lưu database

Bấm `Sao lưu DB` để tạo bản sao lưu dữ liệu hiện tại.

File sao lưu thường nằm trong:

```text
data\backups
```

## Khôi phục database

1. Bấm `Khôi phục DB`.
2. Chọn file sao lưu `.db`, `.sqlite` hoặc `.backup`.
3. Xác nhận khôi phục.

Trước khi khôi phục, APE tự tạo một bản sao an toàn của database hiện tại.

## Lưu ý

Các thống kê và tín hiệu trong APE chỉ mô tả dữ liệu lịch sử. Ứng dụng không cam kết và không bảo đảm bất kỳ kết quả tương lai nào.
