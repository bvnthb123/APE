# APE v0.6.0

Adaptive Prediction Engine - ứng dụng desktop phân tích dữ liệu lịch sử.

## Module đã hoàn thành

- M1 - Config & Core Foundation
- M2 - Database Layer
- M3 - Excel Importer & Data Validation
- M4 - Statistics & Data Audit
- Sprint 2.1 - Desktop GUI
- Sprint 2.2 - Report Export & Charts

## Cập nhật bản mới

Mở CMD trong thư mục dự án:

```text
git pull
py -m pip install -r requirements.txt
```

## Mở giao diện

```text
py main.py
```

Hoặc chạy rõ lệnh GUI:

```text
py main.py gui
```

## Giao diện hiện có

### Tổng quan

- Tổng số kỳ đã lưu.
- Khoảng thời gian dữ liệu.
- Trạng thái SQLite.
- Điểm chất lượng dữ liệu.
- Danh sách các kỳ gần nhất.
- Nút mở thư mục dữ liệu.
- Nút mở thư mục báo cáo.

### Dữ liệu lịch sử

- Ngày và thứ.
- Bộ giá trị.
- Tổng.
- Cấu trúc lẻ/chẵn và thấp/cao.
- Tên file nguồn.

### Thống kê & kiểm tra

- Số lần xuất hiện và tỷ lệ lịch sử.
- Khoảng cách xuất hiện hiện tại, trung bình và lớn nhất.
- Thống kê 30 kỳ gần nhất.
- Cặp và bộ ba đồng xuất hiện.
- Dòng lỗi, ngày trùng, sai thứ và khoảng thời gian dữ liệu dài.

### Biểu đồ

- Biểu đồ cột tần suất 01-45.
- Biểu đồ đường khoảng vắng hiện tại.

## Nhập Excel trên giao diện

1. Nhấn `Nhập file Excel`.
2. Chọn file `.xlsx` hoặc `.xls`.
3. Xem báo cáo kiểm tra.
4. Xác nhận nhập dữ liệu.
5. Dashboard tự động làm mới.

## Xuất báo cáo Excel

1. Nhấn `Xuất báo cáo Excel`.
2. Chọn nơi lưu file.
3. Mở file `.xlsx` đã xuất.

File báo cáo gồm các sheet:

- `Tong_quan`
- `Du_lieu`
- `Thong_ke_01_45`
- `Cap_so`
- `Bo_ba`
- `Kiem_tra`
- `Bieu_do`

## Lệnh CMD vẫn được hỗ trợ

```text
py main.py status
py main.py validate FILE.xlsx
py main.py import FILE.xlsx
py main.py analyze
py main.py analyze --json
py -m pytest -q
```

## Yêu cầu môi trường

- Python 3.10 đến 3.14.
- PySide6 6.11 trở lên.
- Windows 64-bit được hỗ trợ.

Các thống kê trong APE chỉ mô tả dữ liệu lịch sử, không bảo đảm kết quả tương lai.

## Bước tiếp theo

Sprint 2.3 - Windows Packaging: đóng gói thành file `.exe` chạy độc lập.
