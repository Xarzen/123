"""
雲端版本的電梯監控系統 - 不包含大型檔案
適用於 Render 等雲端平台部署
"""
from flask import Flask, render_template, jsonify, send_file, request, redirect, url_for, session, flash
import os
import cv2
import base64
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
                    if '#' in value:
                        value = value.split('#')[0]
                    os.environ[key.strip()] = value.strip()

load_env_file()

app = Flask(__name__)
app.secret_key = 'elevator_monitoring_system_2025'

# 雲端環境檢測
IS_CLOUD = os.environ.get('RENDER') or os.environ.get('HEROKU') or os.environ.get('VERCEL')

# 簡單的用戶資料庫
USERS = {
    'admin': {
        'password': hashlib.sha256('admin123'.encode()).hexdigest(),
        'role': 'administrator',
        'name': '系統管理員'
    },
    'operator': {
        'password': hashlib.sha256('op123'.encode()).hexdigest(),
        'role': 'operator',
        'name': '操作員'
    }
}

def verify_password(username, password):
    if username in USERS:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return USERS[username]['password'] == password_hash
    return False

def get_user_info(username):
    return USERS.get(username, None)

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('monitoring.html', 
                         user_info=get_user_info(session['username']),
                         cloud_mode=IS_CLOUD)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if verify_password(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('用戶名或密碼錯誤', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/api/status')
@login_required
def api_status():
    return jsonify({
        'status': 'running',
        'mode': 'cloud' if IS_CLOUD else 'local',
        'user': get_user_info(session['username'])
    })

@app.route('/api/demo')
@login_required
def api_demo():
    """演示模式 - 返回模擬數據"""
    demo_data = {
        'frame_data': '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCADIAMgDASIAAhEBAxEB/8QAFwABAQEBAAAAAAAAAAAAAAAAAAECA//EACQQAQEBAAIBBAMBAQEBAAAAAAABESExQVFhcYGRobHB0fDh8f/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwD+fwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        'detections': [
            {
                'class': 'person',
                'confidence': 0.95,
                'bbox': [100, 50, 200, 300],
                'timestamp': datetime.datetime.now().isoformat()
            }
        ],
        'floor': '1F',
        'timestamp': datetime.datetime.now().isoformat(),
        'demo_mode': True
    }
    return jsonify(demo_data)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

if __name__ == '__main__':
    # 從環境變數獲取配置
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 10000))
    
    print(f"電梯監控系統 (雲端版) 已啟動")
    print(f"運行模式: {'雲端' if IS_CLOUD else '本地'}")
    print(f"伺服器配置: {host}:{port}")
    
    app.run(debug=False, host=host, port=port)
