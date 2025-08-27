from flask import Flask, render_template, jsonify, send_file, request, redirect, url_for, session, flash
import os
import cv2
import base64
from ultralytics import YOLO
import datetime
import json
import threading
import time
import hashlib
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import numpy as np
# MediaPipe 導入（添加錯誤處理）
import importlib
MEDIAPIPE_AVAILABLE = False
mp = None

try:
    mp = importlib.import_module('mediapipe')
    MEDIAPIPE_AVAILABLE = True
    print("MediaPipe 已成功導入")
except ImportError as e:
    print(f"MediaPipe 導入失敗: {e}")
    print("將使用基本的暈倒檢測方法（不包含姿態估計）")
    # 創建假的 MediaPipe 類別作為回退
    class MockMediaPipe:
        class solutions:
            class pose:
                Pose = None
                POSE_CONNECTIONS = None
            class drawing_utils:
                draw_landmarks = None
    mp = MockMediaPipe()
import math

# 載入 .env 檔案
load_dotenv()

# MongoDB 配置
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'elevator_monitoring')
MONGODB_COLLECTION_EVENTS = os.getenv('MONGODB_COLLECTION_EVENTS', 'events')
MONGODB_COLLECTION_USERS = os.getenv('MONGODB_COLLECTION_USERS', 'users')

# 連接 MongoDB
try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DATABASE]
    events_collection = db[MONGODB_COLLECTION_EVENTS]
    users_collection = db[MONGODB_COLLECTION_USERS]
    
    # 測試連接
    mongo_client.admin.command('ping')
    print(f"MongoDB 連接成功! 資料庫: {MONGODB_DATABASE}")
    
    # 初始化管理員帳號（如果不存在）
    admin_user = users_collection.find_one({'username': 'admin'})
    if not admin_user:
        admin_data = {
            'username': 'admin',
            'password': hashlib.sha256('admin123'.encode()).hexdigest(),
            'role': 'administrator',
            'name': '系統管理員',
            'created_at': datetime.datetime.now()
        }
        users_collection.insert_one(admin_data)
        print("已創建預設管理員帳號: admin/admin123")
    
    # 初始化操作員帳號（如果不存在）
    operator_user = users_collection.find_one({'username': 'operator'})
    if not operator_user:
        operator_data = {
            'username': 'operator',
            'password': hashlib.sha256('op123'.encode()).hexdigest(),
            'role': 'operator',
            'name': '監控操作員',
            'created_at': datetime.datetime.now()
        }
        users_collection.insert_one(operator_data)
        print("已創建預設操作員帳號: operator/op123")
    
    # 初始化觀察員帳號（如果不存在）
    viewer_user = users_collection.find_one({'username': 'viewer'})
    if not viewer_user:
        viewer_data = {
            'username': 'viewer',
            'password': hashlib.sha256('view123'.encode()).hexdigest(),
            'role': 'viewer',
            'name': '監控觀察員',
            'created_at': datetime.datetime.now()
        }
        users_collection.insert_one(viewer_data)
        print("已創建預設觀察員帳號: viewer/view123")
        
except Exception as e:
    print(f"MongoDB 連接失敗: {e}")
    print("系統將使用記憶體儲存模式運行")
    mongo_client = None
    db = None
    events_collection = None
    users_collection = None

app = Flask(__name__)
app.secret_key = 'elevator_monitoring_system_2025'  # 用於會話加密

# 在請求前添加日誌
@app.before_request
def log_request_info():
    import sys
    print(f"=== 收到請求 ===", flush=True)
    print(f"方法: {request.method}", flush=True)
    print(f"路徑: {request.path}", flush=True)
    print(f"完整URL: {request.url}", flush=True)
    print(f"來源IP: {request.remote_addr}", flush=True)
    print(f"User-Agent: {request.headers.get('User-Agent', 'Unknown')[:50]}...", flush=True)
    print("=" * 50, flush=True)
    sys.stdout.flush()

# 用戶驗證和資料庫操作函數
def verify_password(username, password):
    """驗證用戶密碼"""
    if users_collection is None:
        # 如果 MongoDB 不可用，使用備用驗證
        backup_users = {
            'admin': {
                'password': hashlib.sha256('admin123'.encode()).hexdigest(),
                'role': 'administrator',
                'name': '系統管理員'
            },
            'operator': {
                'password': hashlib.sha256('op123'.encode()).hexdigest(),
                'role': 'operator',
                'name': '監控操作員'
            },
            'viewer': {
                'password': hashlib.sha256('view123'.encode()).hexdigest(),
                'role': 'viewer',
                'name': '監控觀察員'
            }
        }
        if username in backup_users:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            return backup_users[username]['password'] == password_hash
        return False
    
    # 使用 MongoDB 驗證
    try:
        user = users_collection.find_one({'username': username})
        if user:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            return user['password'] == password_hash
        return False
    except Exception as e:
        print(f"資料庫驗證錯誤: {e}")
        return False

def get_user_info(username):
    """獲取用戶資訊"""
    if users_collection is None:
        # 備用用戶資料
        backup_users = {
            'admin': {'role': 'administrator', 'name': '系統管理員'},
            'operator': {'role': 'operator', 'name': '監控操作員'},
            'viewer': {'role': 'viewer', 'name': '監控觀察員'}
        }
        return backup_users.get(username, None)
    
    try:
        user = users_collection.find_one({'username': username})
        if user:
            return {
                'role': user['role'],
                'name': user['name']
            }
        return None
    except Exception as e:
        print(f"獲取用戶資訊錯誤: {e}")
        return None

def save_event_to_db(event_data):
    """儲存事件到資料庫"""
    if events_collection is None:
        return False
    
    try:
        # 加入時間戳記
        event_data['created_at'] = datetime.datetime.now()
        result = events_collection.insert_one(event_data)
        return result.inserted_id is not None
    except Exception as e:
        print(f"儲存事件到資料庫失敗: {e}")
        return False

def get_events_from_db(limit=100):
    """從資料庫獲取事件記錄"""
    if events_collection is None:
        return []
    
    try:
        events = list(events_collection.find().sort('created_at', -1).limit(limit))
        # 轉換 ObjectId 為字串
        for event in events:
            event['_id'] = str(event['_id'])
            if 'created_at' in event:
                event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return events
    except Exception as e:
        print(f"從資料庫獲取事件失敗: {e}")
        return []

def login_required(f):
    """登入裝飾器"""
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    """管理員權限裝飾器"""
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        user_info = get_user_info(session['username'])
        if not user_info or user_info['role'] != 'administrator':
            flash('您沒有權限執行此操作', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 影片和模型路徑配置
# EMT偵測配置
EMT_VIDEO_PATH = "C:/Users/raymo/Documents/123/video/emtvideo.mp4"
EMT_MODEL_PATH = "C:/Users/raymo/Documents/123/model/emt.pt"

# 暈倒偵測配置
FALL_VIDEO_PATH = "C:/Users/raymo/Documents/123/video/fallvideo.mp4"
FALL_MODEL_PATH = "C:/Users/raymo/Documents/123/model/fall.pt"

OUTPUT_FOLDER = 'output'

app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# 初始化MediaPipe姿態檢測
try:
    if MEDIAPIPE_AVAILABLE:
        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils
        pose_model = mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.7, model_complexity=2)
        print("MediaPipe姿態檢測模型載入成功!")
    else:
        raise ImportError("MediaPipe not available")
except Exception as e:
    print(f"MediaPipe載入失敗: {e}")
    print("將使用簡化版暈倒偵測（僅基於YOLO檢測框位置）")
    mp_pose = None
    mp_drawing = None
    pose_model = None
    MEDIAPIPE_AVAILABLE = False

# 載入YOLO模型
try:
    import torch
    # 載入EMT偵測模型
    emt_model = YOLO(EMT_MODEL_PATH)
    
    # 載入暈倒偵測模型
    fall_model = YOLO(FALL_MODEL_PATH)
    
    # 檢查並使用GPU（如果可用）
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    emt_model.to(device)
    fall_model.to(device)
    
    print(f"YOLO模型載入成功! 使用設備: {device}")
    print(f"EMT模型: {EMT_MODEL_PATH}")
    print(f"暈倒偵測模型: {FALL_MODEL_PATH}")
    if device == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU記憶體: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
except Exception as e:
    print(f"YOLO模型載入失敗: {e}")
    emt_model = None
    fall_model = None
    device = 'cpu'

# 檢查影片檔案是否存在
emt_video_exists = os.path.exists(EMT_VIDEO_PATH)
fall_video_exists = os.path.exists(FALL_VIDEO_PATH)

print(f"EMT影片檔案: {EMT_VIDEO_PATH} - {'存在' if emt_video_exists else '不存在'}")
print(f"暈倒偵測影片檔案: {FALL_VIDEO_PATH} - {'存在' if fall_video_exists else '不存在'}")

# 至少要有一個影片檔案存在
video_exists = emt_video_exists or fall_video_exists

# ==================== 暈倒偵測相關函數 ==================== #

def calculate_joint_angle(a, b, c):
    """計算三點之間的夾角"""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    return np.degrees(angle)

def classify_posture(shoulder, hip, knee, height_threshold=40):
    """
    判斷姿勢：優先使用三點夾角，若 <160°再依據高度差判斷是坐著或躺下
    """
    hip_angle = calculate_joint_angle(shoulder, hip, knee)
    height_diff = abs(shoulder[1] - hip[1])  # y 座標差（像素）

    if hip_angle < 150:
        if height_diff < height_threshold or hip_angle < 70:
            return "Lying Down"
        else:
            return "Sitting"
    else:
        return "Standing"

def detect_people_for_fall(frame):
    """使用YOLO檢測人體（用於暈倒偵測）"""
    if fall_model is None:
        return []
    
    results = fall_model(frame)
    persons = []
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if cls == 0:  # person class
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                persons.append((x1, y1, x2, y2))
    return persons

def detect_pose(frame, pose_model):
    """使用MediaPipe檢測人體姿態"""
    if not MEDIAPIPE_AVAILABLE or pose_model is None:
        return None, None
    
    try:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose_model.process(frame_rgb)
        return results.pose_landmarks if results.pose_landmarks else None, results
    except Exception as e:
        print(f"姿態檢測錯誤: {e}")
        return None, None

def check_emergency_status(postures):
    """檢查緊急狀態（暈倒偵測）"""
    for p in postures:
        if p == "Lying Down":
            return 2  # 高風險
        elif p == "Sitting":
            return 1  # 中風險
    return 0  # 無風險

# ==================== 結束暈倒偵測函數 ==================== #

class VideoProcessor:
    def __init__(self, detection_type='emt'):
        self.processing = False
        self.progress = 0
        self.current_frame = None
        self.processed = False
        self.output_path = None
        self.error_message = None
        self.events = []  # 儲存事件記錄
        self.last_record_time = {}  # 記錄每個物件最後一次記錄的時間戳
        self.record_interval = 3.0  # 記錄間隔（秒）
        self.current_floor = '1F'  # 當前樓層，默認為1F
        self.detection_type = detection_type  # 偵測類型：'emt' 或 'fall'
        
        # 實時播放參數
        self.realtime_mode = True  # 實時播放模式
        self.original_fps = 30  # 原始影片FPS
        self.current_frame_num = 0
        self.start_time = None
        self.paused = False
        self.is_processing = False  # 實時處理狀態
        
        # 性能資訊
        self.performance_info = {}
        
        # 影片資料
        self.cap = None
        self.frame_count = 0
    
    def initialize_video(self):
        """初始化影片"""
        try:
            # 根據偵測類型選擇相應的影片檔案
            if self.detection_type == 'fall':
                video_path = FALL_VIDEO_PATH
                if not fall_video_exists:
                    raise Exception("暈倒偵測影片檔案不存在")
            else:  # default to emt
                video_path = EMT_VIDEO_PATH
                if not emt_video_exists:
                    raise Exception("EMT偵測影片檔案不存在")
            
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                raise Exception("無法開啟影片檔案")
            
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # 計算視頻總時長
            video_duration = self.frame_count / self.original_fps if self.original_fps > 0 else 0
            
            print(f"影片參數 ({self.detection_type}):")
            print(f"  - 總幀數: {self.frame_count}")
            print(f"  - FPS: {self.original_fps}")
            print(f"  - 總時長: {video_duration:.2f} 秒")
            print(f"影片初始化成功")
            return True
            
        except Exception as e:
            self.error_message = str(e)
            print(f"初始化影片錯誤: {e}")
            return False
    
    def get_current_frame_with_detection(self):
        """獲取當前幀並進行檢測"""
        try:
            if not self.cap:
                print("錯誤：影片捕獲器未初始化")
                return None
                
            # 計算應該顯示的幀數（基於實際經過的時間）
            if self.start_time is None:
                self.start_time = time.time()
                target_frame = 0
                print("設置開始時間，從第0幀開始")
            else:
                elapsed_time = time.time() - self.start_time
                target_frame = int(elapsed_time * self.original_fps)
            
            print(f"經過時間: {time.time() - self.start_time:.2f}s, 目標幀: {target_frame}, 當前幀: {self.current_frame_num}, 總幀數: {self.frame_count}, FPS: {self.original_fps}")
            
            # 如果目標幀沒有變化且已有當前幀，返回當前幀
            if target_frame == self.current_frame_num and self.current_frame is not None:
                print("目標幀未改變，返回當前幀")
                # 更新進度
                self.progress = (self.current_frame_num / self.frame_count) * 100
                return self.current_frame
            
            # 跳到目標幀
            if target_frame >= self.frame_count:
                # 播放完成
                print("播放完成：目標幀超過總幀數")
                self.progress = 100
                self.is_processing = False
                return None
                
            if target_frame < self.frame_count:
                print(f"設置影片位置到幀 {target_frame}")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                actual_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                print(f"實際影片位置: {actual_frame}")
                self.current_frame_num = target_frame
                
                print(f"嘗試讀取幀...")
                ret, frame = self.cap.read()
                print(f"讀取結果: ret={ret}, frame shape={frame.shape if frame is not None else 'None'}")
                
                if not ret:
                    # 播放完成
                    print("播放完成：無法讀取幀")
                    self.progress = 100
                    self.is_processing = False
                    return None
                
                print(f"成功讀取幀 {self.current_frame_num}")
                
                # 根據偵測類型進行不同的檢測
                if self.detection_type == 'fall':
                    # 暈倒偵測
                    frame = self.process_fall_detection(frame)
                else:
                    # EMT偵測
                    frame = self.process_emt_detection(frame)
                
                # 計算進度
                self.progress = int((self.current_frame_num / self.frame_count) * 100)
                
                # 編碼為base64
                _, buffer = cv2.imencode('.jpg', frame)
                self.current_frame = base64.b64encode(buffer).decode('utf-8')
                
                return self.current_frame
                
        except Exception as e:
            print(f"讀取幀時發生錯誤: {e}")
            self.error_message = str(e)
            self.is_processing = False
            return None
    
    def process_emt_detection(self, frame):
        """處理EMT偵測"""
        if emt_model and frame is not None:
            results = emt_model(frame, device=device, verbose=False)
            current_time = self.current_frame_num / self.original_fps
            
            # 處理檢測結果
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        conf = box.conf[0].item()
                        if conf >= 0.6:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            label = result.names[int(box.cls[0])]
                            
                            # 統一標籤
                            unified_label = "EMT" if label in ["EMT", "EMTLOGO"] else label
                            
                            # 記錄事件
                            should_record = False
                            if unified_label not in self.last_record_time:
                                should_record = True
                            elif current_time - self.last_record_time[unified_label] >= self.record_interval:
                                should_record = True
                            
                            if should_record:
                                self.last_record_time[unified_label] = current_time
                                event = {
                                    'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'object': unified_label,
                                    'confidence': f"{conf:.2f}",
                                    'floor': getattr(self, 'current_floor', '1F'),
                                    'frame_number': self.current_frame_num,
                                    'video_timestamp': current_time
                                }
                                # 儲存到記憶體（用於即時顯示）
                                self.events.append(event)
                                # 儲存到資料庫（用於持久化）
                                save_event_to_db(event.copy())
                                print(f"*** [EMT偵測] 新增事件記錄: {unified_label} (信心度: {conf:.2f}) 樓層: {event['floor']} 在時間 {event['time']} ***")
                            
                            # 繪製檢測框
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{unified_label} {conf:.2f}", (x1, y1 - 10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame
    
    def process_fall_detection(self, frame):
        """處理暈倒偵測"""
        if not MEDIAPIPE_AVAILABLE:
            # MediaPipe 不可用時的回退處理
            cv2.putText(frame, "Fall Detection: MediaPipe not available", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, "Using basic YOLO detection only", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # 基本的 YOLO 人體檢測
            if fall_model and frame is not None:
                current_time = self.current_frame_num / self.original_fps
                results = fall_model(frame, device=device, verbose=False)
                
                # 處理檢測結果
                for result in results:
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        for box in result.boxes:
                            conf = box.conf[0].item()
                            if conf >= 0.6:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                label = result.names[int(box.cls[0])]
                                
                                # 繪製檢測框
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            return frame
        
        # MediaPipe 可用時的完整處理
        if fall_model and pose_model and frame is not None:
            current_time = self.current_frame_num / self.original_fps
            
            # 檢測人體
            persons = detect_people_for_fall(frame)
            frame_postures = []
            
            for idx, (x1, y1, x2, y2) in enumerate(persons):
                person_roi = frame[y1:y2, x1:x2]
                if person_roi.size == 0:
                    continue
                
                landmarks, results = detect_pose(person_roi, pose_model)
                warning_messages = []
                color = (0, 255, 0)  # 預設綠色
                
                if landmarks:
                    # 取得關鍵點
                    shoulder = (landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER].x * person_roi.shape[1],
                               landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER].y * person_roi.shape[0])
                    hip = (landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_HIP].x * person_roi.shape[1],
                          landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_HIP].y * person_roi.shape[0])
                    knee = (landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_KNEE].x * person_roi.shape[1],
                           landmarks.landmark[mp.solutions.pose.PoseLandmark.LEFT_KNEE].y * person_roi.shape[0])
                    
                    angle = calculate_joint_angle(shoulder, hip, knee)
                    posture = classify_posture(shoulder, hip, knee)
                    
                    # 設定顏色和訊息
                    if posture == "Lying Down":
                        warning_messages.append(f"躺下! 角度: {angle:.2f}")
                        color = (0, 0, 255)  # 紅色 - 高風險
                    elif posture == "Sitting":
                        warning_messages.append(f"坐著! 角度: {angle:.2f}")
                        color = (0, 165, 255)  # 橙色 - 中風險
                    elif posture == "Standing":
                        warning_messages.append(f"站立! 角度: {angle:.2f}")
                        color = (0, 255, 0)  # 綠色 - 正常
                    
                    frame_postures.append(posture)
                    
                    # 記錄緊急事件
                    if posture in ["Lying Down", "Sitting"]:
                        should_record = False
                        event_key = f"Person_{idx}_{posture}"
                        
                        if event_key not in self.last_record_time:
                            should_record = True
                        elif current_time - self.last_record_time[event_key] >= self.record_interval:
                            should_record = True
                        
                        if should_record:
                            self.last_record_time[event_key] = current_time
                            event = {
                                'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'object': f"人員{idx+1}_{posture}",
                                'confidence': f"{angle:.2f}°",
                                'floor': getattr(self, 'current_floor', '1F'),
                                'frame_number': self.current_frame_num,
                                'video_timestamp': current_time
                            }
                            # 儲存到記憶體和資料庫
                            self.events.append(event)
                            save_event_to_db(event.copy())
                            print(f"*** [暈倒偵測] 新增事件記錄: {event['object']} (角度: {angle:.2f}°) 樓層: {event['floor']} 在時間 {event['time']} ***")
                    
                    # 繪製姿態連線 (如果可用)
                    if MEDIAPIPE_AVAILABLE and hasattr(mp.solutions, 'drawing_utils'):
                        mp.solutions.drawing_utils.draw_landmarks(frame[y1:y2, x1:x2], results.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
                
                # 繪製檢測框和文字
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                for i, msg in enumerate(warning_messages):
                    cv2.putText(frame, f"Person {idx+1}: {msg}", (x1, y1 - 10 - (i * 20)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # 檢查整體緊急狀態
            emergency_flag = check_emergency_status(frame_postures)
            if emergency_flag > 0:
                status_text = "高風險!" if emergency_flag == 2 else "中風險!"
                cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        return frame
    

    
    def start_realtime_analysis(self):
        """開始實時分析"""
        try:
            print("嘗試初始化影片...")
            if not self.initialize_video():
                print(f"初始化影片失敗: {self.error_message}")
                return False

            print("影片初始化成功，重置所有狀態...")
            # 重置所有狀態
            self.progress = 0
            self.is_processing = False
            self.current_frame_num = 0
            self.start_time = None
            self.current_frame = None
            # self.events = []  # 註解掉重置事件記錄，讓事件可以累積保留
            self.last_record_time = {}  # 重置記錄時間
            
            print(f"狀態重置完成 - progress: {self.progress}, is_processing: {self.is_processing}, current_frame_num: {self.current_frame_num}")
            
            print("設置GPU參數...")
            # 設置GPU相關參數
            self.performance_info.update({
                'gpu_available': torch.cuda.is_available(),
                'device': device,
                'gpu_memory': f"{torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB" if torch.cuda.is_available() else "N/A"
            })
            
            print(f"開始實時分析影片: {self.frame_count} 幀, FPS: {self.original_fps}")
            
            self.is_processing = True
            self.start_time = None  # 將在第一次調用get_current_frame_with_detection時設置
            self.current_frame_num = 0
            
            print(f"監控啟動完成 - is_processing: {self.is_processing}")
            return True
            
        except Exception as e:
            self.error_message = str(e)
            print(f"開始實時分析時發生錯誤: {e}")
            self.is_processing = False
            return False
    
    def stop_analysis(self):
        """停止分析"""
        self.is_processing = False
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # 更新性能資訊
        if self.start_time:
            end_time = time.time()
            total_time = end_time - self.start_time
            self.performance_info.update({
                'processing_time': f"{total_time:.2f}s",
                'avg_fps': f"{self.current_frame_num / total_time:.1f}" if total_time > 0 else "N/A",
                'total_frames': self.current_frame_num,
                'events_detected': len(self.events)
            })
            
            print(f"分析停止! 處理了 {self.current_frame_num} 幀，耗時 {total_time:.2f} 秒")
            print(f"檢測到 {len(self.events)} 個事件")
    
    def process_video(self):
        self.processing = True
        self.progress = 0
        self.processed = False
        self.error_message = None
        # 不再清空事件記錄，讓記錄可以累積
        # self.events = []  # 註解掉清空事件記錄
        self.last_record_time = {}  # 重設記錄時間（每次重新開始間隔控制）
        
        try:
            # 根據偵測類型選擇影片檔案
            if self.detection_type == 'fall':
                video_path = FALL_VIDEO_PATH
                if not fall_video_exists:
                    raise Exception("暈倒偵測影片檔案不存在")
            else:
                video_path = EMT_VIDEO_PATH
                if not emt_video_exists:
                    raise Exception("EMT偵測影片檔案不存在")
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception("無法開啟影片檔案")
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 準備輸出影片（使用更好的編碼器和目標FPS）
            fourcc = cv2.VideoWriter_fourcc(*'H264')  # 使用H264編碼器
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'processed_{timestamp}.mp4'
            self.output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 使用目標FPS而不是原始FPS
            out = cv2.VideoWriter(self.output_path, fourcc, self.target_fps, (width, height))
            
            frame_num = 0
            processed_frames = []
            batch_frames = []
            
            print(f"開始處理影片，總幀數: {frame_count}")
            print(f"使用GPU加速: {device == 'cuda'}")
            print(f"跳幀處理: 每{self.frame_skip + 1}幀處理1幀")
            print(f"批量大小: {self.batch_size}")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    # 處理剩餘的批量數據
                    current_model = fall_model if self.detection_type == 'fall' else emt_model
                    if batch_frames and current_model:
                        self._process_batch(batch_frames, fps, out)
                    break
                
                frame_num += 1
                self.progress = int((frame_num / frame_count) * 100)
                
                # 跳幀處理：只處理特定幀
                if frame_num % (self.frame_skip + 1) != 0:
                    continue
                
                # 添加到批量處理
                batch_frames.append((frame.copy(), frame_num, fps))
                
                # 當批量達到指定大小時進行處理
                if len(batch_frames) >= self.batch_size:
                    current_model = fall_model if self.detection_type == 'fall' else emt_model
                    if current_model:
                        self._process_batch(batch_frames, fps, out)
                    batch_frames = []
                
                # 每30幀打印一次進度
                if frame_num % 30 == 0:
                    print(f"處理進度: {self.progress}% ({frame_num}/{frame_count})")
            
            cap.release()
            out.release()
            
            self.processed = True
            
            print(f"處理完成!")
            print(f"事件記錄: {len(self.events)} 個事件")
            print(f"輸出檔案: {self.output_path}")
            
        except Exception as e:
            self.error_message = str(e)
            print(f"處理影片時發生錯誤: {e}")
        
        finally:
            self.processing = False
            self.progress = 100

    def _process_batch(self, batch_frames, fps, out):
        """批量處理幀數據"""
        try:
            # 準備批量輸入
            frames_only = [frame for frame, _, _ in batch_frames]
            
            # 批量YOLO檢測 - 根據偵測類型使用不同模型
            if self.detection_type == 'fall':
                results_batch = fall_model(frames_only, device=device, verbose=False) if fall_model else []
            else:
                results_batch = emt_model(frames_only, device=device, verbose=False) if emt_model else []
            
            # 處理每一幀的結果
            for i, (frame, frame_num, fps) in enumerate(batch_frames):
                current_time = frame_num / fps
                results = results_batch[i]
                
                # 處理檢測結果
                for result in [results]:  # results_batch[i] 已經是單個結果
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        for box in result.boxes:
                            conf = box.conf[0].item()
                            if conf >= 0.6:  # 信心度閾值
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                label = result.names[int(box.cls[0])]
                                
                                # 將EMTLOGO視為EMT
                                unified_label = "EMT" if label in ["EMT", "EMTLOGO"] else label
                                
                                # 檢查是否需要記錄事件
                                should_record = False
                                if unified_label not in self.last_record_time:
                                    should_record = True
                                elif current_time - self.last_record_time[unified_label] >= self.record_interval:
                                    should_record = True
                                
                                if should_record:
                                    self.last_record_time[unified_label] = current_time
                                    event = {
                                        'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'object': unified_label,
                                        'confidence': f"{conf:.2f}",
                                        'floor': getattr(self, 'current_floor', '1F'),  # 添加樓層信息
                                        'frame_number': frame_num,
                                        'video_timestamp': current_time
                                    }
                                    # 儲存到記憶體（用於即時顯示）
                                    self.events.append(event)
                                    # 儲存到資料庫（用於持久化）
                                    save_event_to_db(event.copy())
                                
                                # 在影片上繪製
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(frame, f"{unified_label} {conf:.2f}", (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # 寫入處理後的幀
                out.write(frame)
                
                # 更新當前幀（用於即時預覽）
                _, buffer = cv2.imencode('.jpg', frame)
                self.current_frame = base64.b64encode(buffer).decode('utf-8')
        
        except Exception as e:
            print(f"批量處理錯誤: {e}")
    
    def set_performance_mode(self, mode='balanced'):
        """設定性能模式"""
        if mode == 'fast':
            self.frame_skip = 4  # 跳過更多幀
            self.batch_size = 8  # 更大批量
            self.target_fps = 10  # 更低FPS
        elif mode == 'quality':
            self.frame_skip = 1  # 跳過較少幀
            self.batch_size = 2  # 較小批量
            self.target_fps = 20  # 更高FPS
        else:  # balanced
            self.frame_skip = 2  # 預設
            self.batch_size = 4  # 預設
            self.target_fps = 15  # 預設

# 全域視頻處理器
video_processor = VideoProcessor()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if verify_password(username, password):
            session['username'] = username
            session['user_info'] = get_user_info(username)
            flash(f'歡迎，{session["user_info"]["name"]}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用戶名或密碼錯誤', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', '訪客')
    session.clear()
    flash('已成功登出', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user_info=session.get('user_info'))

@app.route('/monitoring')
@login_required
def monitoring():
    return render_template('monitoring.html', video_exists=video_exists, user_info=session.get('user_info'))

@app.route('/events')
@login_required
def events():
    return render_template('events.html', user_info=session.get('user_info'))

@app.route('/start_processing', methods=['POST'])
@login_required
def start_processing():
    user_info = session.get('user_info')
    if user_info['role'] == 'viewer':
        return jsonify({'error': '您沒有權限執行監控操作'}), 403
    
    if video_processor.processing:
        return jsonify({'error': '正在處理中，請稍候'}), 400
    
    if not video_exists:
        return jsonify({'error': '影片檔案不存在'}), 400
    
    # 開始處理影片
    thread = threading.Thread(target=video_processor.process_video)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '開始處理影片...'
    })

@app.route('/start_realtime', methods=['POST'])
def start_realtime():
    print("=== 收到實時監控啟動請求 ===")
    print(f"Request method: {request.method}")
    print(f"Request path: {request.path}")
    print(f"Request headers: {dict(request.headers)}")
    
    # 檢查登錄狀態
    if 'username' not in session:
        print("錯誤：用戶未登錄")
        return redirect(url_for('login'))
    
    # 檢查用戶身份
    print(f"Session內容: {dict(session)}")
    
    user_info = session.get('user_info')
    print(f"用戶信息: {user_info}")

    if not user_info:
        print("錯誤：未找到用戶信息")
        return jsonify({'error': '未登錄'}), 401
        
    if user_info['role'] == 'viewer':
        print("權限不足：觀察員角色")
        return jsonify({'error': '您沒有權限執行監控操作'}), 403

    # 獲取樓層信息和偵測類型
    floor_data = '1F'  # 默認樓層
    detection_type = 'emt'  # 默認偵測類型
    try:
        if request.is_json:
            data = request.get_json()
            floor_data = data.get('floor', '1F')
            detection_type = data.get('detection_type', 'emt')
        else:
            floor_data = request.form.get('floor', '1F')
            detection_type = request.form.get('detection_type', 'emt')
        print(f"收到樓層信息: {floor_data}")
        print(f"收到偵測類型: {detection_type}")
    except Exception as e:
        print(f"解析請求數據出錯: {e}")
        floor_data = '1F'
        detection_type = 'emt'
    
    # 設置處理器的當前樓層和偵測類型
    video_processor.current_floor = floor_data
    video_processor.detection_type = detection_type
    print(f"設置處理器樓層為: {video_processor.current_floor}")
    print(f"設置處理器偵測類型為: {video_processor.detection_type}")

    if video_processor.is_processing:
        print("已在實時播放中")
        return jsonify({'error': '正在實時播放中'}), 400

    if not video_exists:
        print("影片檔案不存在")
        return jsonify({'error': '影片檔案不存在'}), 400

    print("開始啟動實時分析...")
    # 開始實時分析
    if video_processor.start_realtime_analysis():
        print("實時分析啟動成功")
        return jsonify({
            'success': True,
            'message': '開始實時分析...',
            'frame_count': video_processor.frame_count,
            'fps': video_processor.original_fps,
            'floor': floor_data
        })
    else:
        print(f"實時分析啟動失敗: {video_processor.error_message}")
        return jsonify({
            'error': video_processor.error_message or '無法開始實時分析'
        }), 400

@app.route('/stop_realtime', methods=['POST'])
@login_required
def stop_realtime():
    user_info = session.get('user_info')
    if user_info['role'] == 'viewer':
        return jsonify({'error': '您沒有權限執行監控操作'}), 403
    
    video_processor.stop_analysis()
    return jsonify({
        'success': True,
        'message': '實時分析已停止'
    })

@app.route('/get_realtime_frame')
@login_required
def get_realtime_frame():
    print(f"收到get_realtime_frame請求，當前狀態：is_processing={video_processor.is_processing}, progress={video_processor.progress}")
    
    if not video_processor.is_processing:
        print("實時監控未啟動，返回錯誤")
        return jsonify({'success': False, 'error': '實時監控未啟動'}), 200
    
    print("嘗試獲取實時幀...")
    frame_data = video_processor.get_current_frame_with_detection()
    
    print(f"獲取幀數據後狀態：is_processing={video_processor.is_processing}, progress={video_processor.progress}, frame_data是否為None={frame_data is None}")
    
    # 檢查是否播放完成
    if not video_processor.is_processing or video_processor.progress >= 100 or frame_data is None:
        print("播放完成，停止實時監控")
        video_processor.stop_analysis()
        return jsonify({
            'success': True,
            'completed': True,
            'performance_info': video_processor.performance_info,
            'progress': 100
        })
    
    print(f"成功獲取幀數據，進度: {video_processor.progress}%")
    return jsonify({
        'success': True,
        'frame_data': frame_data,
        'progress': video_processor.progress,
        'current_frame': video_processor.current_frame_num,
        'total_frames': video_processor.frame_count,
        'fps': video_processor.original_fps,
        'processing': video_processor.is_processing,
        'completed': False
    })

@app.route('/progress')
@login_required
def get_progress():
    response = {
        'progress': video_processor.progress,
        'processing': video_processor.processing,
        'processed': video_processor.processed,
        'error': video_processor.error_message,
        'device': device,
        'gpu_enabled': device == 'cuda',
        'frame_skip': video_processor.frame_skip,
        'batch_size': video_processor.batch_size,
        'target_fps': video_processor.target_fps
    }
    
    if video_processor.current_frame:
        response['current_frame'] = video_processor.current_frame
    
    return jsonify(response)

@app.route('/results')
@login_required
def get_results():
    if not video_processor.processed:
        return jsonify({'error': '影片尚未處理完成'}), 400
    
    # 只返回事件統計資訊
    return jsonify({
        'total_events': len(video_processor.events),
        'filename': 'emtvideo.mp4',
        'message': '處理完成'
    })

@app.route('/events_data')
@login_required
def get_events_data():
    # 取得查詢參數
    source = request.args.get('source', 'memory')  # 'memory' 或 'database'
    limit = int(request.args.get('limit', 100))
    
    if source == 'database':
        # 從資料庫獲取事件
        db_events = get_events_from_db(limit)
        return jsonify({
            'events': db_events,
            'total_events': len(db_events),
            'source': 'database'
        })
    else:
        # 從記憶體獲取事件（當前會話）
        return jsonify({
            'events': video_processor.events,
            'total_events': len(video_processor.events),
            'source': 'memory'
        })

@app.route('/video')
@login_required
def serve_video():
    if not video_processor.processed or not video_processor.output_path:
        return "影片尚未處理完成", 404
    
    return send_file(video_processor.output_path)

@app.route('/reset')
@admin_required
def reset_processing():
    if not video_processor.processing:
        video_processor.processed = False
        video_processor.progress = 0
        video_processor.current_frame = None
        video_processor.error_message = None
        # 不清除事件記錄，讓管理員可以選擇是否保留歷史記錄
        return jsonify({'success': True, 'message': '已重設處理狀態'})
    else:
        return jsonify({'error': '正在處理中，無法重設'}), 400

@app.route('/clear_events')
@admin_required
def clear_events():
    """專門用於清除事件記錄的路由"""
    video_processor.events = []
    return jsonify({
        'success': True,
        'message': '事件記錄已清除'
    })

if __name__ == '__main__':
    # 確保必要的目錄存在
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # 從環境變數讀取配置，如果沒有則使用預設值
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    
    print(f"電梯監控系統已啟動")
    print(f"EMT影片檔案: {EMT_VIDEO_PATH} - {'存在' if emt_video_exists else '不存在'}")
    print(f"暈倒偵測影片檔案: {FALL_VIDEO_PATH} - {'存在' if fall_video_exists else '不存在'}")
    print(f"伺服器配置: {host}:{port}")
    
    app.run(debug=False, host=host, port=port)
