let isUpdating = false;
let updateTimeout = null;
let emergencyCheckInterval = null;

function startRealtimeMonitoring() {
    // 獲取選中的樓層
    const floorSelect = document.getElementById('floor-select');
    const selectedFloor = floorSelect ? floorSelect.value : '1F';
    
    // 獲取選中的偵測類型
    const detectionTypeSelect = document.getElementById('detection-type-select');
    const selectedDetectionType = detectionTypeSelect ? detectionTypeSelect.value : 'emt';
    
    console.log('開始實時監控，選中樓層：', selectedFloor);
    console.log('選中偵測類型：', selectedDetectionType);
    console.log('發送啟動請求...');
    
    fetch('/start_realtime', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            floor: selectedFloor,
            detection_type: selectedDetectionType
        })
    })
    .then(response => {
        console.log('啟動響應狀態：', response.status);
        if (!response.ok) {
            // 處理 HTTP 錯誤狀態
            return response.json().then(errorData => {
                throw new Error(errorData.message || errorData.error || '伺服器錯誤');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('啟動響應數據：', data);
        if (data.success) {
            const startBtn = document.getElementById('realtime-btn');
            const stopBtn = document.getElementById('stop-btn');
            
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.style.display = 'none';
            }
            if (stopBtn) {
                stopBtn.disabled = false;
                stopBtn.style.display = 'block';
            }
            
            // 顯示實時監控區域
            const realtimeSection = document.getElementById('realtimeSection');
            if (realtimeSection) {
                realtimeSection.style.display = 'block';
            }
            
            // 顯示視頻區域
            const video = document.getElementById('realtime-video');
            if (video) {
                video.style.display = 'block';
            }
            
            // 隱藏載入中文字
            const realtimeLoading = document.getElementById('realtimeLoading');
            if (realtimeLoading) {
                realtimeLoading.style.display = 'none';
            }
            
            // 顯示成功通知
            showToast('success', '實時監控', '實時監控已成功啟動');
            
            isUpdating = true;
            updateRealtimeFrame();
            
            // 啟動緊急狀況檢測（僅限暈倒偵測）
            if (selectedDetectionType === 'fall') {
                startEmergencyMonitoring();
            }
        } else {
            showToast('error', '啟動失敗', data.message || data.error || '未知錯誤');
        }
    })
    .catch(error => {
        console.error('錯誤：', error);
        showToast('error', '啟動失敗', error.message);
    });
}

function stopRealtimeMonitoring() {
    console.log('停止監控');
    isUpdating = false;
    
    // 清除更新超時
    if (updateTimeout) {
        clearTimeout(updateTimeout);
        updateTimeout = null;
    }
    
    // 停止緊急狀況監控
    stopEmergencyMonitoring();
    
    fetch('/stop_realtime', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('停止回應：', data);
        showToast('success', '實時監控', '實時監控已停止');
        resetUI();
    })
    .catch(error => {
        console.error('停止錯誤：', error);
        showToast('error', '停止失敗', '無法停止實時監控');
        resetUI();
    });
}

function resetUI() {
    const startBtn = document.getElementById('realtime-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (startBtn) {
        startBtn.disabled = false;
        startBtn.style.display = 'block';
    }
    if (stopBtn) {
        stopBtn.disabled = true;
        stopBtn.style.display = 'none';
    }
    
    // 清空畫面並隱藏實時監控區域
    const video = document.getElementById('realtime-video');
    if (video) {
        video.src = '';
        video.style.display = 'none';
    }
    
    // 隱藏實時監控區域
    const realtimeSection = document.getElementById('realtimeSection');
    if (realtimeSection) {
        realtimeSection.style.display = 'none';
    }
    
    // 顯示載入中文字
    const realtimeLoading = document.getElementById('realtimeLoading');
    if (realtimeLoading) {
        realtimeLoading.style.display = 'block';
    }
    
    // 顯示載入提示
    const loading = document.getElementById('realtimeLoading');
    if (loading) {
        loading.style.display = 'block';
    }
    
    // 重置進度條
    const progressBar = document.getElementById('progressBar');
    
    if (progressBar) {
        progressBar.style.width = '0%';
    }
}

function updateRealtimeFrame() {
    if (!isUpdating) {
        console.log('停止更新幀，isUpdating = false');
        return;
    }
    
    console.log('請求新幀...');
    fetch('/get_realtime_frame')
        .then(response => {
            console.log('幀響應狀態：', response.status);
            return response.json();
        })
        .then(data => {
            console.log('幀響應數據：', data);
            if (!isUpdating) {
                console.log('在回調中停止更新');
                return;
            }
            
            if (data.success) {
                // 更新視頻圖片
                const video = document.getElementById('realtime-video');
                if (video && data.frame_data) {
                    video.src = 'data:image/jpeg;base64,' + data.frame_data;
                    video.style.display = 'block'; // 確保影片顯示
                    
                    // 隱藏載入提示
                    const loading = document.getElementById('realtimeLoading');
                    if (loading) {
                        loading.style.display = 'none';
                    }
                }
                
                // 更新進度條
                const progress = parseFloat(data.progress) || 0;
                const progressBar = document.getElementById('progressBar');
                
                if (progressBar) {
                    progressBar.style.width = progress + '%';
                }
                
                // 檢查緊急狀況（來自實時幀數據）
                checkFrameEmergency(data);
                
                // 檢查是否完成
                if (progress >= 100) {
                    console.log('監控完成，停止更新');
                    isUpdating = false;
                    setTimeout(() => {
                        stopRealtimeMonitoring();
                        showToast('success', '監控完成', '實時視頻監控已完成');
                    }, 500);
                } else if (isUpdating) {
                    // 繼續更新
                    updateTimeout = setTimeout(updateRealtimeFrame, 100); // 10 FPS，更穩定
                }
            } else {
                console.log('獲取幀失敗：', data.message);
                if (data.message && data.message.includes('實時監控未啟動')) {
                    // 如果後端說監控未啟動，停止前端輪詢
                    console.log('後端監控未啟動，停止前端輪詢');
                    isUpdating = false;
                    stopRealtimeMonitoring();
                } else if (isUpdating) {
                    updateTimeout = setTimeout(updateRealtimeFrame, 1000); // 錯誤時延遲重試
                }
            }
        })
        .catch(error => {
            console.error('更新幀錯誤：', error);
            if (isUpdating) {
                updateTimeout = setTimeout(updateRealtimeFrame, 1000); // 錯誤時延遲重試
            }
        });
}

// 頁面加載完成後初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('頁面加載完成，監控系統就緒');
    
    // 先停止任何正在運行的監控
    fetch('/stop_realtime', {
        method: 'POST'
    }).then(() => {
        console.log('已停止之前的監控會話');
        // 重置 UI 狀態
        resetUI();
    }).catch(() => {
        console.log('沒有需要停止的監控會話');
        // 重置 UI 狀態
        resetUI();
    });
    
    // 添加事件監聽器
    const startBtn = document.getElementById('realtime-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (startBtn) {
        startBtn.addEventListener('click', startRealtimeMonitoring);
        console.log('已綁定開始按鈕事件');
    } else {
        console.error('找不到開始按鈕 (realtime-btn)');
    }
    
    if (stopBtn) {
        stopBtn.addEventListener('click', stopRealtimeMonitoring);
        console.log('已綁定停止按鈕事件');
    } else {
        console.error('找不到停止按鈕 (stop-btn)');
    }
    
    // 偵測類型選擇事件監聽器
    const detectionTypeSelect = document.getElementById('detection-type-select');
    if (detectionTypeSelect) {
        detectionTypeSelect.addEventListener('change', function() {
            const selectedType = this.value;
            console.log('偵測類型已更改為：', selectedType);
            
            // 可以在這裡添加切換偵測類型時的UI更新邏輯
            showToast('info', '偵測類型', 
                selectedType === 'emt' ? '已切換到EMT緊急醫療偵測' : '已切換到暈倒偵測');
        });
        console.log('已綁定偵測類型選擇事件');
    } else {
        console.error('找不到偵測類型選擇器 (detection-type-select)');
    }
});

// Toast 通知功能
function showToast(type, title, message) {
    console.log(`${type.toUpperCase()}: ${title} - ${message}`);
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-header">
            <strong>${title}</strong>
            <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
        <div class="toast-body">${message}</div>
    `;
    
    const container = document.querySelector('.toast-container') || document.body;
    container.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);
}

// 緊急狀況監控功能
function startEmergencyMonitoring() {
    console.log('啟動緊急狀況監控');
    
    // 清除現有的監控間隔
    if (emergencyCheckInterval) {
        clearInterval(emergencyCheckInterval);
    }
    
    // 每2秒檢查一次緊急狀況
    emergencyCheckInterval = setInterval(checkEmergencyStatus, 2000);
}

function stopEmergencyMonitoring() {
    console.log('停止緊急狀況監控');
    
    if (emergencyCheckInterval) {
        clearInterval(emergencyCheckInterval);
        emergencyCheckInterval = null;
    }
    
    // 停止所有警報
    if (window.emergencyAlertSystem) {
        window.emergencyAlertSystem.stopAllAlerts();
    }
}

function checkEmergencyStatus() {
    fetch('/check_emergency')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.emergency_detected) {
                console.log('檢測到緊急狀況:', data.emergency_info);
                
                // 觸發緊急警報
                if (window.emergencyAlertSystem) {
                    window.emergencyAlertSystem.triggerEmergencyAlert(data.emergency_info);
                } else {
                    console.error('緊急警報系統未初始化');
                    // 備用警報方法
                    alert(`🚨 緊急警報 🚨\n${data.emergency_info.floor} 發生緊急狀況\n${data.emergency_info.message}\n請立即處理！`);
                }
            }
        })
        .catch(error => {
            console.error('檢查緊急狀況時發生錯誤:', error);
        });
}

// 在實時幀更新中也檢查緊急狀況
function checkFrameEmergency(data) {
    if (data.emergency_detected && data.emergency_info) {
        console.log('從實時幀中檢測到緊急狀況:', data.emergency_info);
        
        if (window.emergencyAlertSystem) {
            window.emergencyAlertSystem.triggerEmergencyAlert(data.emergency_info);
        }
    }
}
