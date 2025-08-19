#!/bin/bash
# Render 雲端版啟動腳本

echo "正在啟動電梯監控系統 (雲端版)..."

# 設定環境變數
export FLASK_ENV=production
export FLASK_HOST=0.0.0.0
export FLASK_PORT=10000
export RENDER=true

# 使用 Gunicorn 啟動雲端版應用程式
exec gunicorn --config gunicorn.conf.py elevator_app_cloud:app
