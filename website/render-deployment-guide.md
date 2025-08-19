# Render 部署指南

## 準備步驟

### 1. 準備 Git Repository
```bash
cd C:\Users\raymo\Documents\123\website
git init
git add .
git commit -m "Initial commit for Render deployment"
```

### 2. 推送到 GitHub
1. 在 GitHub 創建新的 repository
2. 按照 GitHub 指示推送代碼：
```bash
git remote add origin https://github.com/your-username/elevator-monitoring.git
git branch -M main
git push -u origin main
```

### 3. 上傳必要檔案
由於模型檔案 (.pt) 和影片檔案過大，需要另外處理：

#### 選項 1: 使用 Git LFS (推薦)
```bash
git lfs install
git lfs track "*.pt"
git lfs track "*.mp4"
git add .gitattributes
git add model/best.pt
git add video/775119556.823492.mp4
git commit -m "Add large files with LFS"
git push
```

#### 選項 2: 使用雲端儲存
- 上傳檔案到 Google Drive, Dropbox 等
- 修改程式碼使用 URL 下載檔案

## Render 設定步驟

### 1. 連接 Repository
1. 登入 [Render](https://render.com/)
2. 點擊 "New +" → "Web Service"
3. 連接您的 GitHub repository

### 2. 設定部署參數
- **Name**: elevator-monitoring
- **Environment**: Python 3
- **Build Command**: `./render-build.sh`
- **Start Command**: `./start.sh`
- **Instance Type**: Free (或根據需要選擇)

### 3. 環境變數設定
在 Render 控制台設定以下環境變數：
```
RENDER=true
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=10000
```

### 4. 進階設定
- **Health Check Path**: `/`
- **Auto-Deploy**: Yes

## 注意事項

### 檔案大小限制
- Render 免費版有檔案大小限制
- 大型模型檔案建議使用外部儲存

### GPU 支援
- Render 免費版不支援 GPU
- 模型會自動切換到 CPU 模式

### 效能考量
- 免費版有計算時間限制
- 建議優化模型或升級到付費版

## 測試部署
部署完成後，您可以透過 Render 提供的 URL 存取您的電梯監控系統。

## 故障排除

### 常見問題
1. **模型載入失敗**: 檢查模型檔案是否正確上傳
2. **影片播放問題**: 確認影片檔案路徑正確
3. **記憶體不足**: 考慮升級 Render 計畫

### 查看日誌
在 Render 控制台的 "Logs" 頁面查看詳細錯誤訊息。
