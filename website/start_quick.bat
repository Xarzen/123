@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Elevator Monitoring System (Network Mode)...
set FLASK_HOST=0.0.0.0
set FLASK_PORT=5000
python elevator_app.py
pause
