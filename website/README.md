# EMT人員辨識系統

這是一個基於 AI 深度學習的緊急醫療技術人員檢測與分析平台，使用 YOLO 模型進行即時影片分析。

## 功能特色

- 🎯 **AI 影片分析**: 使用 YOLO 深度學習模型檢測 EMT 人員
- 📹 **即時處理**: 支援多種影片格式，即時顯示處理進度
- 📊 **詳細統計**: 提供檢測統計資料和信心度分析
- 💾 **資料儲存**: 使用 MongoDB 儲存處理記錄和結果
- 🎨 **美觀介面**: 現代化響應式設計，支援拖拉上傳
- 📱 **移動適配**: 完整支援手機和平板設備

## 技術架構

### 前端
- HTML5 + CSS3 + JavaScript (ES6+)
- 響應式設計，支援各種螢幕尺寸
- 拖拉上傳、進度條、即時更新
- 美觀的動畫效果和過渡

### 後端
- Python Flask 網頁框架
- YOLO (You Only Look Once) 物件檢測
- OpenCV 影片處理
- 多執行緒非同步處理

### 資料庫
- MongoDB 文件資料庫
- 儲存影片資訊、檢測結果、處理狀態

## 安裝說明

### 環境需求
- Python 3.8+
- MongoDB 4.4+
- 至少 4GB RAM
- 支援 CUDA 的 GPU (可選，加速處理)

### 1. 安裝 MongoDB

**Windows:**
1. 從 [MongoDB 官網](https://www.mongodb.com/try/download/community) 下載並安裝
2. 啟動 MongoDB 服務:
   ```powershell
   net start MongoDB
   ```

**macOS (使用 Homebrew):**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb/brew/mongodb-community
```

**Linux (Ubuntu):**
```bash
sudo apt update
sudo apt install -y mongodb
sudo systemctl start mongod
sudo systemctl enable mongod
```

### 2. 安裝 Python 套件

```bash
pip install -r requirements.txt
```

### 3. 準備模型檔案

確保您的 YOLO 模型檔案 `best.pt` 位於 `../model/` 目錄中。

### 4. 啟動應用程式

```bash
python app.py
```

應用程式將在 http://localhost:5000 啟動。

## 使用說明

### 1. 上傳影片
- 拖拉影片檔案到上傳區域，或點擊選擇檔案
- 支援格式：MP4, AVI, MOV, MKV
- 檔案大小限制：100MB

### 2. 監控處理
- 上傳後系統會自動開始處理
- 即時顯示處理進度和當前畫面
- 處理時間取決於影片長度和複雜度

### 3. 查看結果
- 處理完成後自動顯示分析結果
- 包含檢測統計、處理後影片播放
- 詳細的檢測記錄和時間軸資訊

### 4. 管理歷史
- 查看所有處理過的影片記錄
- 下載處理後的影片檔案
- 刪除不需要的記錄

## 專案結構

```
website/
├── app.py                 # Flask 主應用程式
├── video_processor.py     # 影片處理腳本
├── requirements.txt       # Python 套件依賴
├── templates/
│   └── index.html        # 主頁面模板
├── static/
│   ├── style.css         # CSS 樣式檔案
│   └── script.js         # JavaScript 前端邏輯
├── uploads/              # 上傳影片儲存目錄
└── output/               # 處理後影片儲存目錄
```

## API 端點

- `GET /` - 主頁面
- `POST /upload` - 上傳影片檔案
- `GET /progress/<video_id>` - 獲取處理進度
- `GET /results/<video_id>` - 獲取處理結果
- `GET /video/<video_id>` - 下載處理後影片
- `GET /videos` - 獲取影片列表
- `DELETE /delete/<video_id>` - 刪除影片

## 設定選項

### 模型設定
在 `app.py` 中可以調整：
- `confidence_threshold` - 檢測信心度閾值 (預設 0.6)
- `model_path` - YOLO 模型檔案路徑

### 系統限制
- `MAX_CONTENT_LENGTH` - 檔案大小限制 (預設 100MB)
- `UPLOAD_FOLDER` - 上傳目錄
- `OUTPUT_FOLDER` - 輸出目錄

## 疑難排解

### 常見問題

1. **MongoDB 連接失敗**
   - 確認 MongoDB 服務已啟動
   - 檢查連接字串是否正確

2. **YOLO 模型載入失敗**
   - 確認模型檔案路徑正確
   - 檢查檔案是否損壞

3. **影片處理失敗**
   - 檢查影片格式是否支援
   - 確認系統記憶體充足

4. **上傳失敗**
   - 檢查檔案大小是否超出限制
   - 確認網路連接穩定

## 效能優化

### 硬體建議
- **CPU**: Intel i5 或 AMD Ryzen 5 以上
- **記憶體**: 8GB RAM 以上
- **儲存**: SSD 硬碟
- **GPU**: NVIDIA GTX 1660 或以上 (可選)

### 軟體優化
- 使用 GPU 加速 (CUDA)
- 調整處理幀率
- 使用影片壓縮

## 授權條款

本專案採用 MIT 授權條款。請參閱 LICENSE 檔案了解詳情。

## 聯絡資訊

如有問題或建議，請聯絡開發團隊。

---

**注意**: 本系統僅供研究和教育用途，實際部署前請確保符合相關法規要求。
