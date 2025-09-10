/**
 * 緊急警報系統
 * 包含警報聲、瀏覽器通知和語音播報功能
 */

class EmergencyAlertSystem {
    constructor() {
        this.isAlertActive = false;
        this.alertAudio = null;
        this.voiceSynthesis = window.speechSynthesis;
        this.lastAlertTime = 0;
        this.alertCooldown = 5000; // 5秒冷卻時間，避免重複警報
        
        this.initializeAudio();
        this.requestNotificationPermission();
    }

    /**
     * 初始化警報音效
     */
    initializeAudio() {
        try {
            // 創建警報音效 - 使用音頻上下文生成警報聲
            this.alertAudio = this.createAlertSound();
        } catch (error) {
            console.error('初始化警報音效失敗:', error);
        }
    }

    /**
     * 創建警報聲音
     */
    createAlertSound() {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        const createBeep = (frequency, duration, volume = 0.3) => {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0, audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(volume, audioContext.currentTime + 0.1);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration - 0.1);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + duration);
            
            return new Promise(resolve => {
                oscillator.onended = resolve;
            });
        };

        return {
            play: async () => {
                try {
                    // 警報音效模式：高低交替的緊急警報聲
                    for (let i = 0; i < 6; i++) {
                        await createBeep(800, 0.3, 0.5); // 高音
                        await new Promise(resolve => setTimeout(resolve, 100));
                        await createBeep(600, 0.3, 0.5); // 低音
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                } catch (error) {
                    console.error('播放警報聲失敗:', error);
                }
            }
        };
    }

    /**
     * 請求瀏覽器通知權限
     */
    requestNotificationPermission() {
        if ('Notification' in window) {
            if (Notification.permission === 'default') {
                Notification.requestPermission().then(permission => {
                    console.log('通知權限狀態:', permission);
                });
            }
        }
    }

    /**
     * 顯示瀏覽器通知
     */
    showNotification(title, message, options = {}) {
        if ('Notification' in window && Notification.permission === 'granted') {
            const defaultOptions = {
                icon: '/static/emergency-icon.png', // 您可以添加緊急圖標
                badge: '/static/emergency-badge.png',
                requireInteraction: true, // 需要用戶交互才能關閉
                tag: 'emergency-alert', // 防止重複通知
                renotify: true,
                vibrate: [200, 100, 200, 100, 200], // 震動模式（如果支援）
                ...options
            };

            const notification = new Notification(title, {
                body: message,
                ...defaultOptions
            });

            // 自動關閉通知
            setTimeout(() => {
                notification.close();
            }, 10000); // 10秒後自動關閉

            return notification;
        } else {
            console.warn('瀏覽器不支援通知或沒有權限');
            return null;
        }
    }

    /**
     * 語音播報
     */
    speakAlert(message) {
        if (this.voiceSynthesis) {
            // 停止當前語音
            this.voiceSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(message);
            
            // 設置語音參數
            utterance.lang = 'zh-TW'; // 繁體中文
            utterance.rate = 1.0;     // 語速
            utterance.pitch = 1.2;    // 音調
            utterance.volume = 1.0;   // 音量

            // 選擇中文語音（如果可用）
            const voices = this.voiceSynthesis.getVoices();
            const chineseVoice = voices.find(voice => 
                voice.lang.includes('zh') || voice.lang.includes('zh-TW') || voice.lang.includes('zh-CN')
            );
            
            if (chineseVoice) {
                utterance.voice = chineseVoice;
            }

            utterance.onstart = () => {
                console.log('開始語音播報:', message);
            };

            utterance.onend = () => {
                console.log('語音播報完成');
            };

            utterance.onerror = (error) => {
                console.error('語音播報錯誤:', error);
            };

            this.voiceSynthesis.speak(utterance);
        } else {
            console.warn('瀏覽器不支援語音合成');
        }
    }

    /**
     * 觸發完整的緊急警報
     */
    triggerEmergencyAlert(emergencyInfo) {
        const now = Date.now();
        
        // 檢查冷卻時間，避免重複警報
        if (now - this.lastAlertTime < this.alertCooldown) {
            console.log('警報冷卻中，跳過此次警報');
            return;
        }

        this.lastAlertTime = now;
        this.isAlertActive = true;

        console.log('觸發緊急警報:', emergencyInfo);

        // 1. 播放警報聲
        if (this.alertAudio) {
            this.alertAudio.play().catch(error => {
                console.error('播放警報聲失敗:', error);
            });
        }

        // 2. 顯示瀏覽器通知
        const notificationTitle = '🚨 緊急警報 🚨';
        const notificationMessage = `${emergencyInfo.floor} 發生緊急狀況，請立即處理！`;
        
        this.showNotification(notificationTitle, notificationMessage, {
            urgency: 'critical'
        });

        // 3. 語音播報
        const voiceMessage = '發生緊急狀況 請及時處理';
        setTimeout(() => {
            this.speakAlert(voiceMessage);
        }, 500); // 延遲500ms確保警報聲先播放

        // 4. 顯示頁面警報
        this.showPageAlert(emergencyInfo);

        // 5. 設置警報結束
        setTimeout(() => {
            this.isAlertActive = false;
        }, 5000);
    }

    /**
     * 在頁面上顯示警報
     */
    showPageAlert(emergencyInfo) {
        // 移除現有警報
        const existingAlert = document.getElementById('emergency-alert-overlay');
        if (existingAlert) {
            existingAlert.remove();
        }

        // 創建警報覆蓋層
        const alertOverlay = document.createElement('div');
        alertOverlay.id = 'emergency-alert-overlay';
        alertOverlay.innerHTML = `
            <div class="emergency-alert-container">
                <div class="emergency-alert-icon">🚨</div>
                <div class="emergency-alert-title">緊急警報</div>
                <div class="emergency-alert-message">
                    ${emergencyInfo.floor} 發生緊急狀況<br>
                    請及時處理
                </div>
                <div class="emergency-alert-time">
                    時間: ${new Date().toLocaleString('zh-TW')}
                </div>
                <button class="emergency-alert-close" onclick="this.parentElement.parentElement.remove()">
                    確認
                </button>
            </div>
        `;

        // 添加樣式
        alertOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 0, 0, 0.9);
            z-index: 10000;
            display: flex;
            justify-content: center;
            align-items: center;
            animation: alertPulse 1s infinite;
        `;

        // 添加內部樣式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes alertPulse {
                0%, 100% { background: rgba(255, 0, 0, 0.9); }
                50% { background: rgba(255, 100, 100, 0.9); }
            }
            
            .emergency-alert-container {
                background: white;
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                max-width: 400px;
                animation: alertShake 0.5s infinite;
            }
            
            @keyframes alertShake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-5px); }
                75% { transform: translateX(5px); }
            }
            
            .emergency-alert-icon {
                font-size: 4em;
                margin-bottom: 15px;
                animation: iconSpin 2s linear infinite;
            }
            
            @keyframes iconSpin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .emergency-alert-title {
                font-size: 2em;
                font-weight: bold;
                color: #d32f2f;
                margin-bottom: 15px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            
            .emergency-alert-message {
                font-size: 1.2em;
                margin-bottom: 15px;
                color: #333;
                line-height: 1.4;
            }
            
            .emergency-alert-time {
                font-size: 0.9em;
                color: #666;
                margin-bottom: 20px;
            }
            
            .emergency-alert-close {
                background: #d32f2f;
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 1.1em;
                border-radius: 5px;
                cursor: pointer;
                transition: background 0.3s;
            }
            
            .emergency-alert-close:hover {
                background: #b71c1c;
            }
        `;

        document.head.appendChild(style);
        document.body.appendChild(alertOverlay);

        // 自動關閉警報
        setTimeout(() => {
            if (alertOverlay.parentNode) {
                alertOverlay.remove();
            }
        }, 15000); // 15秒後自動關閉
    }

    /**
     * 停止所有警報
     */
    stopAllAlerts() {
        this.isAlertActive = false;
        
        // 停止語音
        if (this.voiceSynthesis) {
            this.voiceSynthesis.cancel();
        }
        
        // 移除頁面警報
        const alertOverlay = document.getElementById('emergency-alert-overlay');
        if (alertOverlay) {
            alertOverlay.remove();
        }
    }
}

// 全局警報系統實例
window.emergencyAlertSystem = new EmergencyAlertSystem();
