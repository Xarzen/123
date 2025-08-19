@echo off
chcp 65001 >nul
echo ====================================
echo     電梯監控系統啟動腳本
echo ====================================
echo.

:: 切換到腳本所在目錄
cd /d "%~dp0"

:: 檢查Python是否安裝
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 未找到Python，請確認Python已正確安裝
    pause
    exit /b 1
)

:: 檢查必要檔案是否存在
if not exist "elevator_app.py" (
    echo [錯誤] 找不到 elevator_app.py 檔案
    pause
    exit /b 1
)

if not exist "../video/775119556.823492.mp4" (
    echo [錯誤] 找不到影片檔案
    pause
    exit /b 1
)

:: 檢查CUDA是否可用
echo [檢查] 正在檢查CUDA環境...
python -c "import torch; print('CUDA可用:', torch.cuda.is_available())" 2>nul
if %errorlevel% neq 0 (
    echo [警告] PyTorch未安裝或CUDA不可用，將使用CPU模式
)

:: 顯示系統資訊
echo.
echo [系統資訊]
echo 當前目錄: %CD%
echo Python版本:
python --version
echo.

:: 顯示啟動選項
echo [啟動選項]
echo 1. 本機模式 (127.0.0.1:5000)
echo 2. 區域網路模式 (0.0.0.0:5000) - 可從外網訪問
echo 3. 自訂埠號模式
echo.
set /p choice="請選擇啟動模式 (1-3): "

if "%choice%"=="1" (
    set HOST=127.0.0.1
    set PORT=5000
    echo [啟動] 本機模式
) else if "%choice%"=="2" (
    set HOST=0.0.0.0
    set PORT=5000
    echo [啟動] 區域網路模式 - 可從外網訪問
) else if "%choice%"=="3" (
    set HOST=0.0.0.0
    set /p PORT="請輸入埠號 (預設5000): "
    if "%PORT%"=="" set PORT=5000
    echo [啟動] 自訂模式 - 埠號: %PORT%
) else (
    echo [預設] 使用區域網路模式
    set HOST=0.0.0.0
    set PORT=5000
)

echo.
echo ====================================
echo 正在啟動電梯監控系統...
echo 主機: %HOST%
echo 埠號: %PORT%
echo ====================================
echo.
echo 提示: 
echo - 本機訪問: http://127.0.0.1:%PORT%
echo - 區域網路訪問: http://[您的IP地址]:%PORT%
echo - 按 Ctrl+C 停止系統
echo.

:: 設置環境變數並啟動應用程式
set FLASK_HOST=%HOST%
set FLASK_PORT=%PORT%
python elevator_app.py

echo.
echo ====================================
echo 電梯監控系統已停止
echo ====================================
pause
