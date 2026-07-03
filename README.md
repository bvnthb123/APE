# APE v0.2.0 - Adaptive Prediction Engine

APE là nền tảng nghiên cứu chuỗi dữ liệu, hiện được cấu hình cho dữ liệu gồm 6 số khác nhau trong khoảng 01-45.

## Trạng thái hiện tại

Đã hoàn thành:

- M1 - Config & Core Foundation.
- M2 - Database Layer.

Phiên bản này chưa thực hiện dự đoán. Nó cung cấp lõi cấu hình, logging, SQLite, SQLAlchemy ORM và Repository Pattern để các module sau sử dụng.

## Database schema

Khi chạy, APE tự tạo file `data/ape.db` với các bảng:

- `draws`: lịch sử ngày và 6 số thực tế.
- `features`: kho đặc trưng theo kỳ và theo từng số.
- `predictions`: lịch sử Top-N do các engine dự đoán.
- `engine_scores`: kết quả chấm điểm từng engine.
- `rules`: các quy luật đã phát hiện và chỉ số chất lượng.
- `experiments`: lịch sử thí nghiệm thuật toán.
- `run_records`: lịch sử các phiên import, backtest và prediction.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```bash
pip install -r requirements.txt
```

## Chạy chương trình

```bash
python main.py
```

Nếu chạy đúng, chương trình sẽ hiển thị:

```text
Status  : Database Layer OK
```

Đồng thời file `data/ape.db` sẽ được tạo tự động.

## Chạy kiểm thử

```bash
python -m pytest -q
```

## Cấu trúc M2

```text
ape/
  core/
    app.py
    constants.py
    exceptions.py
    settings.py
    version.py
  database/
    base.py
    database.py
    models.py
    repositories.py
  utils/
    logger.py
tests/
  test_core.py
  test_database.py
```

## Module tiếp theo

M3 - Excel Importer & Data Validation:

- Đọc file Excel lịch sử.
- Tự nhận diện cột Ngày, Thứ và Bộ số.
- Chuẩn hóa 6 số theo thứ tự tăng dần.
- Phát hiện dữ liệu lỗi, trùng ngày hoặc số ngoài 01-45.
- Import theo cơ chế upsert, không tạo bản ghi trùng.
