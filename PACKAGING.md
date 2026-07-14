# Đóng gói APE thành file chạy Windows

Tài liệu này dùng cho Sprint 2.3 - Windows Packaging.

## Kết quả build

Sau khi build thành công, file chạy nằm tại:

```text
dist\APE\APE.exe
```

Đây là dạng portable folder. Cần giữ nguyên cả thư mục `dist\APE`, không chỉ copy riêng file `APE.exe`.

## Cách build nhanh

Mở CMD trong thư mục dự án rồi chạy:

```bat
build_windows.bat
```

Script sẽ tự động:

1. Tạo môi trường `.venv_build`.
2. Cài thư viện từ `requirements-packaging.txt`.
3. Xóa thư mục build cũ.
4. Chạy PyInstaller theo file `APE.spec`.
5. Tạo `dist\APE\APE.exe`.

## Chạy bản source không build

```bat
run_ape.bat
```

hoặc:

```bat
py main.py
```

## Chạy bản đã build

Sau khi build xong:

```bat
dist\APE\APE.exe
```

Lần đầu mở có thể chậm hơn vì Windows cần kiểm tra file mới.

## Ghi chú quan trọng

- Nên build trên chính máy Windows sẽ sử dụng app.
- Nếu antivirus cảnh báo, chọn cho phép đối với thư mục dự án APE do chính bạn build.
- Không đổi tên hoặc di chuyển lẻ `APE.exe` ra khỏi thư mục `dist\APE`.
- Database vẫn được tạo tại thư mục dữ liệu bên cạnh app theo cấu hình hiện tại.

## Dọn build

Có thể xóa các thư mục sau để build lại từ đầu:

```text
build
dist
.venv_build
```

Sau đó chạy lại:

```bat
build_windows.bat
```
