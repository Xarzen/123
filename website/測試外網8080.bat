@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在啟動電梯監控系統 (外網模式 - 埠號8080)...
set FLASK_HOST=0.0.0.0
set FLASK_PORT=8080
python elevator_app.py
pause
