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

# 載入 .env 檔案（如果存在）
def load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # 去除值中的註解部分
                    if '#' in value:
                        value = value.split('#')[0]
                    os.environ[key.strip()] = value.strip()

load_env_file()

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

# 簡單的用戶資料庫（實際應用中應使用真正的資料庫）
USERS = {
    'admin': {
        'password': hashlib.sha256('admin123'.encode()).hexdigest(),
        'role': 'administrator',
        'name': '系統管理員'
    },
    'operator': {
        'password': hashlib.sha256('operator123'.encode()).hexdigest(),
        'role': 'operator',
        'name': '操作員'
    },
    'viewer': {
        'password': hashlib.sha256('viewer123'.encode()).hexdigest(),
        'role': 'viewer',
        'name': '觀察員'
    }
}

def verify_password(username, password):
    """驗證用戶密碼"""
    if username in USERS:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return USERS[username]['password'] == password_hash
    return False

def get_user_info(username):
    """獲取用戶資訊"""
    return USERS.get(username, None)

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

# 固定影片路徑配置
VIDEO_PATH = "C:/Users/raymo/Documents/123/video/775119556.823492.mp4"
OUTPUT_FOLDER = 'output'

app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# 載入YOLO模型
try:
    import torch
    model = YOLO("C:/Users/raymo/Documents/123/model/best.pt")
    
    # 檢查並使用GPU（如果可用）
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    
    print(f"YOLO模型載入成功! 使用設備: {device}")
    if device == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU記憶體: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
except Exception as e:
    print(f"YOLO模型載入失敗: {e}")
    model = None
    device = 'cpu'

# 檢查影片檔案是否存在
if not os.path.exists(VIDEO_PATH):
    print(f"錯誤：影片檔案不存在：{VIDEO_PATH}")
    video_exists = False
else:
    print(f"找到影片檔案：{VIDEO_PATH}")
    video_exists = True

class VideoProcessor:
    def __init__(self):
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
            if not video_exists:
                raise Exception("影片檔案不存在")
            
            self.cap = cv2.VideoCapture(VIDEO_PATH)
            if not self.cap.isOpened():
                raise Exception("無法開啟影片檔案")
            
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # 計算視頻總時長
            video_duration = self.frame_count / self.original_fps if self.original_fps > 0 else 0
            
            print(f"影片參數:")
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
            
            # 進行YOLO檢測
            if model and frame is not None:
                results = model(frame, device=device, verbose=False)
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
                                        'floor': getattr(self, 'current_floor', '1F')  # 添加樓層信息
                                    }
                                    self.events.append(event)
                                    print(f"*** [實時監控] 新增事件記錄: {unified_label} (信心度: {conf:.2f}) 樓層: {event['floor']} 在時間 {event['time']} ***")
                                    print(f"*** [實時監控] 目前總事件數: {len(self.events)} ***")
                                else:
                                    print(f"[實時監控] 跳過記錄 {unified_label} (間隔不足: {current_time - self.last_record_time.get(unified_label, 0):.2f}s < {self.record_interval}s)")
                                
                                # 繪製檢測框
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(frame, f"{unified_label} {conf:.2f}", (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 計算進度
            self.progress = int((self.current_frame_num / self.frame_count) * 100)
            
            # 編碼為base64
            _, buffer = cv2.imencode('.jpg', frame)
            self.current_frame = base64.b64encode(buffer).decode('utf-8')
            
            return self.current_frame
        
        return self.current_frame
    
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
            if not video_exists:
                raise Exception("影片檔案不存在")
            
            cap = cv2.VideoCapture(VIDEO_PATH)
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
                    if batch_frames and model:
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
                    if model:
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
            
            # 批量YOLO檢測
            results_batch = model(frames_only, device=device, verbose=False)
            
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
                                        'floor': getattr(self, 'current_floor', '1F')  # 添加樓層信息
                                    }
                                    self.events.append(event)
                                
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

    # 獲取樓層信息
    floor_data = '1F'  # 默認樓層
    try:
        if request.is_json:
            data = request.get_json()
            floor_data = data.get('floor', '1F')
        else:
            floor_data = request.form.get('floor', '1F')
        print(f"收到樓層信息: {floor_data}")
    except Exception as e:
        print(f"解析樓層數據出錯: {e}")
        floor_data = '1F'
    
    # 設置處理器的當前樓層
    video_processor.current_floor = floor_data
    print(f"設置處理器樓層為: {video_processor.current_floor}")

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
        'filename': '775119556.823492.mp4',
        'message': '處理完成'
    })

@app.route('/events_data')
@login_required
def get_events_data():
    return jsonify({
        'events': video_processor.events,
        'total_events': len(video_processor.events)
    })

@app.route('/video')
@login_required
def serve_video():
    if not video_processor.processed or not video_processor.output_path:
        return "影片尚未處理完成", 404
    
    return send_file(video_processor.output_path)

@app.route('/original_video')
@login_required
def serve_original_video():
    if not video_exists:
        return "原始影片不存在", 404
    
    return send_file(VIDEO_PATH)

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
    print(f"影片檔案: {VIDEO_PATH}")
    print(f"影片存在: {'是' if video_exists else '否'}")
    print(f"伺服器配置: {host}:{port}")
    
    app.run(debug=False, host=host, port=port)
