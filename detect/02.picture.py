from ultralytics import YOLO
import cv2

# 載入已訓練的 YOLO 模型
model = YOLO("C:/Users/raymo/Documents/123/model/best.pt")

# 讀取要辨識的影片
video_path = "C:/Users/raymo/Documents/123/video/775119556.823492.mp4"  # 請替換成您的影片路徑
print(f"正在開啟影片：{video_path}")

# 檢查檔案是否存在
import os
if not os.path.exists(video_path):
    print(f"錯誤：影片檔案不存在：{video_path}")
    exit()

cap = cv2.VideoCapture(video_path)

# 檢查影片是否成功開啟
if not cap.isOpened():
    print("錯誤：無法開啟影片檔案，可能的原因：")
    print("1. 影片格式不支援")
    print("2. 影片檔案損毀")
    print("3. 缺少必要的編解碼器")
    print(f"嘗試使用的影片路徑：{video_path}")
    exit()

print("影片成功開啟！")

# 獲取影片資訊
fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"影片 FPS: {fps}")
print(f"總幀數: {frame_count}")
print("開始處理影片，按 'q' 鍵退出...")

frame_num = 0

# 逐幀處理影片
while True:
    ret, frame = cap.read()
    if not ret:
        print("影片播放完畢")
        break  # 影片結束
    
    frame_num += 1
    if frame_num % 30 == 0:  # 每30幀顯示一次進度
        print(f"處理第 {frame_num} 幀...")
    
    # 執行推論
    results = model(frame)

    # 解析結果並標記到圖片上
    for result in results:
        for box in result.boxes:
            conf = box.conf[0].item()
            if conf < 0.6:
                continue  # 跳過信心度低於 0.6 的預測

            x1, y1, x2, y2 = map(int, box.xyxy[0])  # 邊界框座標
            label = result.names[int(box.cls[0])]  # 類別名稱

            # 在圖片上繪製矩形框和標籤
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 顯示結果
    cv2.imshow("Video Detection", frame)
    
    # 按 'q' 鍵退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 釋放資源
cap.release()
cv2.destroyAllWindows()
