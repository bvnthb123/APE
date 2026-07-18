@echo off
setlocal enabledelayedexpansion

cd /d %~dp0

echo ===============================================
echo APE - Make Portable Release ZIP
echo ===============================================
echo.

if not exist dist\APE\APE.exe (
    echo ERROR: Chua thay dist\APE\APE.exe
    echo Hay chay build_windows.bat truoc.
    pause
    exit /b 1
)

py make_release_zip.py
if errorlevel 1 (
    echo.
    echo ERROR: Tao release ZIP that bai.
    pause
    exit /b 1
)

echo.
echo Hoan tat. File ZIP nam trong thu muc releases.
pause
