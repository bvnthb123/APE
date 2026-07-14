@echo off
setlocal enabledelayedexpansion

cd /d %~dp0

echo ===============================================
echo APE - Windows Portable Build
echo ===============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Khong tim thay Python Launcher ^(py^).
    echo Hay cai Python 3.11, 3.12 hoac 3.13 truoc khi build.
    pause
    exit /b 1
)

if not exist .venv_build (
    echo Tao moi moi truong build .venv_build ...
    py -m venv .venv_build
    if errorlevel 1 goto :error
)

call .venv_build\Scripts\activate.bat
if errorlevel 1 goto :error

echo Nang cap pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo Cai thu vien dong goi ...
python -m pip install -r requirements-packaging.txt
if errorlevel 1 goto :error

echo Xoa ban build cu ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Dang build APE.exe ...
python -m PyInstaller --noconfirm --clean APE.spec
if errorlevel 1 goto :error

if not exist dist\APE\APE.exe (
    echo ERROR: Build xong nhung khong thay dist\APE\APE.exe
    pause
    exit /b 1
)

echo.
echo ===============================================
echo BUILD THANH CONG
echo File chay: dist\APE\APE.exe
echo ===============================================
echo.
pause
exit /b 0

:error
echo.
echo ===============================================
echo BUILD THAT BAI
 echo Kiem tra thong bao loi phia tren.
echo ===============================================
pause
exit /b 1
