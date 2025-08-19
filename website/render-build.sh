#!/usr/bin/env bash
# Render 建置腳本

set -o errexit  # 發生錯誤時停止

# 安裝 Python 依賴套件
pip install -r requirements.txt

# 建立必要目錄
mkdir -p output
mkdir -p static/css
mkdir -p static/js
mkdir -p templates

echo "建置完成！"
