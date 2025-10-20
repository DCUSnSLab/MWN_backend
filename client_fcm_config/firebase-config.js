// Firebase Configuration for Web Client
// FCM (Firebase Cloud Messaging) 웹 클라이언트 설정

// Firebase SDK 임포트
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

// Firebase 프로젝트 설정
// 실제 사용 시 아래 값들을 Firebase 콘솔에서 가져온 값으로 변경하세요
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Firebase 앱 초기화
const app = initializeApp(firebaseConfig);

// FCM 인스턴스 생성
const messaging = getMessaging(app);

// VAPID 키 (Firebase 콘솔 > 프로젝트 설정 > 클라우드 메시징에서 생성)
const vapidKey = "YOUR_VAPID_KEY";

// FCM 토큰 요청
export const requestFCMToken = async () => {
  try {
    const token = await getToken(messaging, { vapidKey });
    if (token) {
      console.log('FCM Token:', token);
      return token;
    } else {
      console.log('No registration token available.');
      return null;
    }
  } catch (error) {
    console.error('An error occurred while retrieving token. ', error);
    return null;
  }
};

// 포그라운드 메시지 수신 처리
export const onMessageListener = () =>
  new Promise((resolve) => {
    onMessage(messaging, (payload) => {
      console.log('Message received. ', payload);
      resolve(payload);
    });
  });

// 서버에 FCM 토큰 등록
export const registerTokenWithServer = async (token, userAuthToken) => {
  try {
    const response = await fetch('/api/fcm/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userAuthToken}` // JWT 토큰
      },
      body: JSON.stringify({
        token: token,
        device_info: {
          platform: 'web',
          browser: navigator.userAgent,
          timestamp: new Date().toISOString()
        },
        subscribe_topics: ['weather_alerts', 'severe_weather']
      })
    });

    if (response.ok) {
      const result = await response.json();
      console.log('Token registered successfully:', result);
      return true;
    } else {
      console.error('Failed to register token:', response.statusText);
      return false;
    }
  } catch (error) {
    console.error('Error registering token:', error);
    return false;
  }
};

// FCM 초기화 및 설정
export const initializeFCM = async (userAuthToken) => {
  try {
    // 알림 권한 요청
    const permission = await Notification.requestPermission();
    
    if (permission === 'granted') {
      console.log('Notification permission granted.');
      
      // FCM 토큰 요청
      const token = await requestFCMToken();
      
      if (token) {
        // 서버에 토큰 등록
        await registerTokenWithServer(token, userAuthToken);
        
        // 포그라운드 메시지 리스너 설정
        onMessageListener().then((payload) => {
          // 커스텀 알림 표시
          showNotification(payload);
        });
        
        return token;
      }
    } else {
      console.log('Unable to get permission to notify.');
      return null;
    }
  } catch (error) {
    console.error('Error initializing FCM:', error);
    return null;
  }
};

// 커스텀 알림 표시
const showNotification = (payload) => {
  const { title, body, icon } = payload.notification || {};
  const { type, weather_data } = payload.data || {};
  
  // 브라우저 알림 생성
  if ('Notification' in window && Notification.permission === 'granted') {
    const notification = new Notification(title || '날씨 알림', {
      body: body || '새로운 날씨 정보가 있습니다.',
      icon: icon || '/icon-192x192.png',
      badge: '/badge-72x72.png',
      tag: 'weather-notification',
      requireInteraction: type === 'severe_weather', // 심각한 날씨는 사용자 상호작용 필요
      actions: [
        {
          action: 'view',
          title: '자세히 보기'
        },
        {
          action: 'close',
          title: '닫기'
        }
      ]
    });
    
    notification.onclick = function(event) {
      event.preventDefault();
      // 알림 클릭 시 처리 (예: 날씨 페이지로 이동)
      window.open('/weather', '_blank');
      notification.close();
    };
    
    // 알림 자동 닫기 (심각한 날씨가 아닌 경우)
    if (type !== 'severe_weather') {
      setTimeout(() => {
        notification.close();
      }, 5000);
    }
  }
};

export default {
  initializeFCM,
  requestFCMToken,
  registerTokenWithServer,
  onMessageListener
};