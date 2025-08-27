@echo off
chcp 65001 >nul
echo ====================================
echo     Electric Elevator Monitoring System
echo           with MongoDB Support
echo ====================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found, please ensure Python is installed
    pause
    exit /b 1
)

:: Check MongoDB service status
echo 檢查 MongoDB 服務狀態...
sc query "MongoDB" | find "RUNNING" >nul
if %errorlevel% neq 0 (
    echo.
    echo [警告] MongoDB 服務未運行
    echo 系統將以記憶體模式運行（重啟後資料會遺失）
    echo.
    echo 如需啟動 MongoDB，請：
    echo 1. 以管理員身份運行 "啟動MongoDB.bat"
    echo 2. 或手動執行: net start MongoDB
    echo.
    timeout /t 3 /nobreak >nul
) else (
    echo MongoDB 服務運行中 ✓
)

:: Check if required files exist
if not exist "elevator_app.py" (
    echo [ERROR] Cannot find elevator_app.py file
    pause
    exit /b 1
)

if not exist "../video/emtvideo.mp4" (
    echo [ERROR] Cannot find video file
    pause
    exit /b 1
)

:: Check CUDA availability
echo [CHECK] Checking CUDA environment...
python -c "import torch; print('CUDA Available:', torch.cuda.is_available())" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] PyTorch not installed or CUDA unavailable, will use CPU mode
)

:: Display system info
echo.
echo [SYSTEM INFO]
echo Current Directory: %CD%
echo Python Version:
python --version
echo.

:: Display startup options
echo [STARTUP OPTIONS]
echo 1. Local Mode (127.0.0.1:5000)
echo 2. Network Mode (0.0.0.0:5000) - External access enabled
echo 3. Custom Port Mode
echo.
set /p choice="Please select startup mode (1-3): "

if "%choice%"=="1" (
    set HOST=127.0.0.1
    set PORT=5000
    echo [STARTING] Local Mode
) else if "%choice%"=="2" (
    set HOST=0.0.0.0
    set PORT=5000
    echo [STARTING] Network Mode - External access enabled
) else if "%choice%"=="3" (
    set HOST=0.0.0.0
    set /p PORT="Enter port number (default 5000): "
    if "%PORT%"=="" set PORT=5000
    echo [STARTING] Custom Mode - Port: %PORT%
) else (
    echo [DEFAULT] Using Network Mode
    set HOST=0.0.0.0
    set PORT=5000
)

echo.
echo ====================================
echo Starting Elevator Monitoring System...
echo Host: %HOST%
echo Port: %PORT%
echo ====================================
echo.
echo Tips: 
echo - Local access: http://127.0.0.1:%PORT%
echo - Network access: http://[Your-IP-Address]:%PORT%
echo - Press Ctrl+C to stop system
echo.

:: Set environment variables and start application
set FLASK_HOST=%HOST%
set FLASK_PORT=%PORT%
echo 正在使用 MediaPipe 環境啟動系統...
C:\Users\raymo\anaconda3\envs\mediapipe-env\python.exe elevator_app.py

echo.
echo ====================================
echo Elevator Monitoring System Stopped
echo ====================================
pause
