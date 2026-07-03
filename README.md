# APE v0.4.0

Adaptive Prediction Engine - nền tảng phân tích chuỗi dữ liệu lịch sử.

## Module đã hoàn thành

- M1 - Config & Core Foundation
- M2 - Database Layer
- M3 - Excel Importer & Data Validation
- M4 - Statistics & Data Audit

## Cài đặt

```text
py -m pip install -r requirements.txt
```

## Các lệnh chính

```text
py main.py
py main.py validate FILE.xlsx
py main.py import FILE.xlsx
py main.py analyze
py main.py analyze --limit 15
py main.py analyze --json
py -m pytest -q
```

## M4 cung cấp

- Số lần xuất hiện và tỷ lệ của từng giá trị 01-45.
- Khoảng cách hiện tại, khoảng cách trước đó, trung bình và lớn nhất.
- Thống kê 30 kỳ gần nhất và mức thay đổi so với toàn bộ lịch sử.
- Nhóm đôi và nhóm ba đồng xuất hiện nhiều.
- Phân bố tổng, chẵn-lẻ, thấp-cao và các giá trị liền nhau.
- Mức trùng với kỳ ngay trước đó.
- Thống kê theo thứ, tháng và năm.
- Kiểm tra dữ liệu lỗi, ngày trùng, sai thứ và thiếu thông tin nguồn.

## Kết quả kiểm tra thực tế

- 388 kỳ được phân tích.
- Khoảng ngày: 03/01/2024 đến 24/06/2026.
- 8 bài kiểm thử của M1-M4 đều đạt.
- Điểm chất lượng dữ liệu: 100/100.

Các thống kê trong M4 chỉ mô tả dữ liệu lịch sử, không phải cam kết về kết quả tương lai.

## Module tiếp theo

M5 - Feature Factory v1.
