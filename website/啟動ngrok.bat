@echo off
echo =====================================
echo       電梯監控系統 - ngrok 啟動器
echo =====================================
echo.
echo 請確保：
echo 1. 電梯監控系統已在另一個終端啟動
echo 2. 已設置 ngrok authtoken
echo.
echo 正在啟動 ngrok 隧道...
echo.

cd /d "C:\Users\raymo\Documents\123"
.\ngrok.exe http 5000

pause
