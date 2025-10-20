// Firebase Messaging Service Worker
// FCM 백그라운드 메시지 처리용 서비스 워커

// Firebase SDK 임포트 (서비스 워커용)
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

// Firebase 설정 (firebase-config.js와 동일한 설정 사용)
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com", 
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Firebase 초기화
firebase.initializeApp(firebaseConfig);

// FCM 인스턴스 생성
const messaging = firebase.messaging();

// 백그라운드 메시지 수신 처리
messaging.onBackgroundMessage(function(payload) {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);
  
  // 알림 옵션 설정
  const notificationTitle = payload.notification?.title || '날씨 알림';
  const notificationOptions = {
    body: payload.notification?.body || '새로운 날씨 정보가 있습니다.',
    icon: payload.notification?.icon || '/icon-192x192.png',
    badge: '/badge-72x72.png',
    tag: 'weather-notification',
    data: payload.data,
    requireInteraction: payload.data?.type === 'severe_weather',
    actions: [
      {
        action: 'view',
        title: '자세히 보기',
        icon: '/action-view.png'
      },
      {
        action: 'dismiss',
        title: '닫기',
        icon: '/action-close.png'
      }
    ],
    // 커스텀 사운드 (옵션)
    sound: payload.data?.type === 'severe_weather' ? '/sounds/alert.mp3' : '/sounds/notification.mp3'
  };

  // 알림 표시
  self.registration.showNotification(notificationTitle, notificationOptions);
});

// 알림 클릭 이벤트 처리
self.addEventListener('notificationclick', function(event) {
  console.log('[firebase-messaging-sw.js] Notification click received.');
  
  event.notification.close();
  
  // 액션에 따른 처리
  if (event.action === 'view') {
    // 날씨 페이지 열기
    event.waitUntil(
      clients.openWindow('/weather')
    );
  } else if (event.action === 'dismiss') {
    // 알림만 닫기 (기본 동작)
    return;
  } else {
    // 기본 클릭 (액션 버튼이 아닌 알림 자체 클릭)
    event.waitUntil(
      clients.matchAll().then(function(clientList) {
        // 이미 열린 탭이 있으면 포커스
        for (var i = 0; i < clientList.length; i++) {
          var client = clientList[i];
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        // 열린 탭이 없으면 새 탭 열기
        if (clients.openWindow) {
          return clients.openWindow('/');
        }
      })
    );
  }
});

// 알림 닫기 이벤트 처리
self.addEventListener('notificationclose', function(event) {
  console.log('[firebase-messaging-sw.js] Notification closed.');
  
  // 분석 데이터 전송 (옵션)
  const notificationData = event.notification.data;
  if (notificationData) {
    // 서버에 알림 닫힘 통계 전송
    fetch('/api/analytics/notification-closed', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        type: notificationData.type,
        timestamp: new Date().toISOString()
      })
    }).catch(err => console.log('Analytics send failed:', err));
  }
});

// 서비스 워커 설치 이벤트
self.addEventListener('install', function(event) {
  console.log('[firebase-messaging-sw.js] Service worker installed.');
  self.skipWaiting();
});

// 서비스 워커 활성화 이벤트
self.addEventListener('activate', function(event) {
  console.log('[firebase-messaging-sw.js] Service worker activated.');
  event.waitUntil(self.clients.claim());
});