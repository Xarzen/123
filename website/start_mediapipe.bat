@echo off
chcp 65001 >nul
echo ====================================
echo     電梯監控系統 (MediaPipe版本)
echo ====================================
echo.

cd /d "%~dp0"

echo [INFO] 正在啟動電梯監控系統...
echo [INFO] 使用 MediaPipe 環境: mediapipe-env
echo.

C:\Users\raymo\anaconda3\envs\mediapipe-env\python.exe elevator_app.py

echo.
echo 系統已停止
pause
