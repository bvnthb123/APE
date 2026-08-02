# APE v1.5.0

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
- Sprint 2.5 - Release Polish & Backup
- Sprint 2.6 - Release ZIP & QA
- Sprint 3.1 - Pattern Mining & Backtest
- Sprint 3.2 - Structural Pattern Learning
- Sprint 3.3 - Repeat Overlap Learning
- Sprint 3.4 - Strategy Optimizer
- Sprint 3.5 - Target-Hit Strategy Optimizer

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

Bước 1 - Build portable app:

```text
build_windows.bat
```

Sau khi build thành công, file chạy nằm tại:

```text
dist\APE\APE.exe
```

Bước 2 - Tạo file ZIP để gửi người khác:

```text
make_release_zip.bat
```

File ZIP nằm tại:

```text
releases\APE-v1.5.0-portable.zip
```

Đây là dạng portable folder. Người dùng cần giải nén ZIP và chạy `APE.exe`. Không copy riêng `APE.exe` ra ngoài thư mục.

## Tài liệu phát hành

- `README_FOR_USERS.md`: hướng dẫn cho người dùng cuối.
- `RELEASE_QA_CHECKLIST.md`: checklist kiểm thử trước khi gửi bản ZIP.
- `RELEASE_NOTES.md`: ghi chú phát hành.
- `PACKAGING.md`: hướng dẫn build cho Windows.

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
- Nút mở thư mục ứng dụng.
- Nút sao lưu database.
- Nút khôi phục database.
- Nút giới thiệu ứng dụng.

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

### Pattern Mining

- Tính rule lịch sử dạng `số ở kỳ N -> số ở kỳ N+lag`.
- Chọn độ trễ từ `N+1` đến `N+10`.
- Chọn support tối thiểu để lọc rule yếu.
- Học cấu trúc lẻ/chẵn của từng dãy.
- Học phân vùng số: `01-09`, `10-20`, `21-30`, `31-40`, `41-45`.
- Học độ lặp số giữa kỳ `N` và kỳ `N+lag`.
- Đếm tỷ lệ trùng `0 số`, `1 số`, `2 số` hoặc nhiều hơn giữa hai kỳ cách nhau theo độ trễ.
- Ưu tiên có kiểm soát các số từ kỳ gần nhất nếu độ trễ đang chọn thường có số lặp lại.
- Chấm điểm tín hiệu bằng rule số đơn lẻ, cấu trúc dãy và độ lặp N→N+lag.
- Cân bằng Top tín hiệu theo quota cấu trúc lịch sử.
- Hiển thị Top tín hiệu lịch sử từ kỳ dữ liệu cuối.
- Hiển thị Top rule lịch sử theo support, lift và score.
- Chạy backtest walk-forward bằng dữ liệu cũ để xem tín hiệu lịch sử hoạt động ra sao.

Lưu ý: Pattern Mining chỉ mô tả tín hiệu trong dữ liệu quá khứ và kiểm định ngược; không phải cam kết hay bảo đảm cho kết quả tương lai.

## Strategy Optimizer bằng CMD

Lệnh `optimize` dùng cùng database với GUI để thử nhiều phương án tính toán và chọn phương án có kết quả backtest tốt nhất.

Tối ưu mục tiêu trùng ít nhất 1 số:

```text
py main.py optimize --lag 3 --top 10 --support 3 --target 1
```

Tối ưu mục tiêu trùng ít nhất 4 số:

```text
py main.py optimize --lag 3 --top 10 --support 3 --target 4
```

Optimizer sẽ thử nhiều cấu hình:

- Rule thuần.
- Rule + cấu trúc dãy.
- Rule + độ lặp N→N+lag.
- Rule + cấu trúc dãy + độ lặp.
- Nhiều mức support quanh mức bạn chọn.
- Lag đơn và các ensemble nhiều độ trễ quanh lag chính.

Kết quả trả về gồm:

- Phương án tốt nhất trong backtest.
- Tỷ lệ trùng ít nhất `target` số.
- Tỷ lệ không trùng số nào.
- Số khớp trung bình.
- So sánh với baseline random.
- Top tín hiệu theo phương án tốt nhất.

## Biểu đồ

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

## Sao lưu và khôi phục database

- Bấm `Sao lưu DB` để tạo bản sao database hiện tại.
- Bấm `Khôi phục DB` để chọn file `.db`, `.sqlite` hoặc `.backup`.
- Khi khôi phục, APE tự tạo một bản sao an toàn trước khi ghi đè database hiện tại.

## Lệnh CMD vẫn được hỗ trợ

```text
py main.py status
py main.py validate FILE.xlsx
py main.py import FILE.xlsx
py main.py analyze
py main.py analyze --json
py main.py optimize --lag 3 --top 10 --support 3 --target 4
py -m pytest -q
```

## Yêu cầu môi trường

- Python 3.10 đến 3.14 để chạy từ mã nguồn.
- Windows 64-bit.
- Khi build `.exe`, nên build trên chính máy Windows sẽ sử dụng app.

Các thống kê trong APE chỉ mô tả dữ liệu lịch sử, không bảo đảm kết quả tương lai.

## Bước tiếp theo

Sprint 3.6 - Strategy Optimizer GUI: đưa bảng tối ưu mục tiêu trùng ít nhất N số vào giao diện, thêm biểu đồ so sánh strategy và xuất báo cáo Excel.
