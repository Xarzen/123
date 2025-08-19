#!/bin/bash
# Render 啟動腳本

echo "正在啟動電梯監控系統..."

# 設定環境變數
export FLASK_ENV=production
export FLASK_HOST=0.0.0.0
export FLASK_PORT=10000

# 使用 Gunicorn 啟動應用程式
exec gunicorn --config gunicorn.conf.py elevator_app:app
