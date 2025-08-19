let isUpdating = false;
let updateTimeout = null;

function startRealtimeMonitoring() {
    // 獲取選中的樓層
    const floorSelect = document.getElementById('floor-select');
    const selectedFloor = floorSelect ? floorSelect.value : '1F';
    
    console.log('開始實時監控，選中樓層：', selectedFloor);
    console.log('發送啟動請求...');
    
    fetch('/start_realtime', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            floor: selectedFloor
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
    const percentageText = document.getElementById('percentageText');
    
    if (progressBar) {
        progressBar.style.width = '0%';
    }
    if (percentageText) {
        percentageText.textContent = '0%';
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
                const percentageText = document.getElementById('percentageText');
                
                if (progressBar) {
                    progressBar.style.width = progress + '%';
                }
                if (percentageText) {
                    percentageText.textContent = Math.round(progress) + '%';
                }
                
                // 更新時間信息
                const timeInfo = document.getElementById('timeInfo');
                if (timeInfo && data.current_time && data.total_time) {
                    timeInfo.textContent = `${data.current_time} / ${data.total_time}`;
                } else if (timeInfo) {
                    // 基於進度計算時間 (假設總時長約12.5秒)
                    const totalSeconds = 12.5;
                    const currentSeconds = (progress / 100) * totalSeconds;
                    const formatTime = (seconds) => {
                        const mins = Math.floor(seconds / 60);
                        const secs = Math.floor(seconds % 60);
                        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                    };
                    timeInfo.textContent = `${formatTime(currentSeconds)} / ${formatTime(totalSeconds)}`;
                }
                
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
