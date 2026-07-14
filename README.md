# APE v0.8.0

Adaptive Prediction Engine - ứng dụng desktop phân tích dữ liệu lịch sử.

## Module đã hoàn thành

- M1 - Config & Core Foundation
- M2 - Database Layer
- M3 - Excel Importer & Data Validation
- M4 - Statistics & Data Audit
- Sprint 2.1 - Desktop GUI
- Sprint 2.2 - Report Export & Charts
- Sprint 2.3 - Windows Portable Packaging
- Sprint 2.4 - Interface Refinement

## Cập nhật bản mới

Mở CMD trong thư mục dự án:

```text
git pull
py -m pip install -r requirements.txt
```

## Mở giao diện từ mã nguồn

```text
py main.py
```

Hoặc:

```text
run_ape.bat
```

## Đóng gói thành file chạy Windows

```text
build_windows.bat
```

Sau khi build thành công, file chạy nằm tại:

```text
dist\APE\APE.exe
```

Đây là dạng portable folder. Cần giữ nguyên cả thư mục `dist\APE`, không copy riêng file `APE.exe` ra ngoài.

## Giao diện hiện có

### Tổng quan

- Tổng số kỳ đã lưu.
- Số kỳ đang hiển thị sau khi lọc.
- Khoảng thời gian dữ liệu.
- Trạng thái SQLite.
- Điểm chất lượng dữ liệu.
- Danh sách các kỳ gần nhất theo bộ lọc hiện tại.
- Nút mở thư mục dữ liệu.
- Nút mở thư mục báo cáo.

### Dữ liệu lịch sử

- Lọc từ ngày đến ngày.
- Tìm kiếm theo ngày, thứ, bộ giá trị, tổng hoặc tên file nguồn.
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
- Biểu đồ đường tổng trong 60 kỳ gần nhất.
- Biểu đồ cột phân bố lẻ/chẵn.

## Lưu thiết lập giao diện

APE tự lưu các thiết lập sau vào `data/gui_preferences.json`:

- Kích thước cửa sổ gần nhất.
- Thư mục Excel mở gần nhất.
- Thư mục báo cáo lưu gần nhất.

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

- Python 3.10 đến 3.14 để chạy từ mã nguồn.
- Windows 64-bit.
- Khi build `.exe`, nên build trên chính máy Windows sẽ sử dụng app.

Các thống kê trong APE chỉ mô tả dữ liệu lịch sử, không bảo đảm kết quả tương lai.

## Bước tiếp theo

Sprint 2.5 - Tạo desktop shortcut, icon ứng dụng và tối ưu trải nghiệm bản phát hành portable.
