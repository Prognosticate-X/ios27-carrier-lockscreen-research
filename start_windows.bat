@echo off
chcp 65001 >nul
title iOS 27 Carrier ^& Lock Screen Suite
color 0A

echo ========================================================
echo   🚀 正在启动 iOS 27 锁屏运营商定制套件 (Windows)
echo ========================================================
echo.

:: 1. 检查 Python 环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo ❌ 错误: 未检测到 Python 环境。
        echo 请先安装 Python 3 (建议 3.10 以上) 并勾选 "Add python.exe to PATH"。
        echo 下载地址: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py -3
    )
) else (
    set PY_CMD=python
)

:: 2. 检查 iTunes / Apple Mobile Device Support (USB驱动)
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Apple Inc.\Apple Mobile Device Support" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] 提示: 未检测到官方 Apple Mobile Device 驱动。
    echo 如果后续无法检测到 iPhone，请安装官方 iTunes 或 Apple Devices 驱动:
    echo 推荐安装: https://www.apple.com/itunes/
    echo.
)

:: 3. 切换至当前脚本所在目录
cd /d "%~dp0"

:: 4. 启动 Web GUI 可视化控制台
echo 🌐 正在启动本地控制台并在浏览器打开...
echo.
%PY_CMD% tools\gui_server.py

pause
