# FCM (Firebase Cloud Messaging) 클라이언트 설정 가이드

이 디렉토리는 날씨 알림 시스템의 클라이언트 측 FCM 설정 파일들을 포함합니다.

## 📁 파일 구조

```
client_fcm_config/
├── README.md                     # 이 파일
├── firebase-config.js            # 웹 클라이언트 FCM 설정
├── firebase-messaging-sw.js      # 서비스 워커 (백그라운드 메시지 처리)
├── AndroidManifest.xml          # Android 앱 매니페스트 설정
├── MyFirebaseMessagingService.java # Android FCM 서비스
└── FCMHelper.swift              # iOS FCM 헬퍼 클래스
```

## 🌐 웹 클라이언트 설정

### 1. Firebase 프로젝트 설정
1. [Firebase Console](https://console.firebase.google.com)에서 프로젝트 생성
2. 웹 앱 추가 및 설정 정보 복사
3. `firebase-config.js`의 `firebaseConfig` 객체를 실제 값으로 변경

### 2. VAPID 키 생성
1. Firebase Console > 프로젝트 설정 > 클라우드 메시징
2. 웹 푸시 인증서의 키 쌍 생성
3. `firebase-config.js`의 `vapidKey` 변수에 설정

### 3. 서비스 워커 등록
```javascript
// index.html 또는 main.js에서
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/firebase-messaging-sw.js')
    .then((registration) => {
      console.log('Service Worker registered:', registration);
    });
}
```

### 4. FCM 초기화 및 사용
```javascript
import { initializeFCM } from './firebase-config.js';

// 사용자 로그인 후 FCM 초기화
const userAuthToken = 'your-jwt-token';
const fcmToken = await initializeFCM(userAuthToken);

if (fcmToken) {
  console.log('FCM 설정 완료');
}
```

## 📱 Android 앱 설정

### 1. Firebase Android 설정
1. Firebase Console에서 Android 앱 추가
2. `google-services.json` 파일을 `app/` 디렉토리에 추가
3. `build.gradle` 파일들에 Firebase SDK 추가

```gradle
// Project level build.gradle
classpath 'com.google.gms:google-services:4.3.15'

// App level build.gradle
implementation 'com.google.firebase:firebase-messaging:23.1.2'
apply plugin: 'com.google.gms.google-services'
```

### 2. 매니페스트 설정
`AndroidManifest.xml` 파일의 내용을 앱의 매니페스트에 추가

### 3. FCM 서비스 구현
`MyFirebaseMessagingService.java`를 앱의 적절한 패키지에 추가

### 4. 앱에서 FCM 토큰 등록
```java
FirebaseMessaging.getInstance().getToken()
    .addOnCompleteListener(new OnCompleteListener<String>() {
        @Override
        public void onComplete(@NonNull Task<String> task) {
            String token = task.getResult();
            // 서버에 토큰 전송
            sendTokenToServer(token);
        }
    });
```

## 🍎 iOS 앱 설정

### 1. Firebase iOS 설정
1. Firebase Console에서 iOS 앱 추가
2. `GoogleService-Info.plist` 파일을 Xcode 프로젝트에 추가
3. CocoaPods 또는 Swift Package Manager로 Firebase SDK 추가

```ruby
# Podfile
pod 'Firebase/Messaging'
```

### 2. AppDelegate 설정
```swift
import Firebase

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication,
                   didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        
        // FCM 설정
        FCMHelper.shared.configure()
        FCMHelper.shared.setupNotificationCategories()
        
        return true
    }
}
```

### 3. FCM 헬퍼 사용
`FCMHelper.swift` 파일을 프로젝트에 추가하고 사용

## 🔧 서버 API 연동

모든 클라이언트는 다음 서버 API를 사용합니다:

### FCM 토큰 등록
```http
POST /api/fcm/register
Authorization: Bearer {JWT_TOKEN}
Content-Type: application/json

{
  "token": "fcm_registration_token",
  "device_info": {
    "platform": "web|android|ios",
    "device_model": "device_info",
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "subscribe_topics": ["weather_alerts", "severe_weather"]
}
```

### FCM 설정 관리
```http
GET /api/fcm/settings
POST /api/fcm/settings
```

### 테스트 알림 전송
```http
POST /api/fcm/test
```

## 🎨 알림 커스터마이징

### 웹
- `firebase-messaging-sw.js`에서 알림 스타일 수정
- CSS로 알림 아이콘 및 이미지 커스터마이징

### Android
- `res/drawable/` 에 알림 아이콘 추가
- `MyFirebaseMessagingService.java`에서 알림 채널 및 스타일 수정

### iOS
- 알림 사운드 파일을 Bundle에 추가
- `FCMHelper.swift`에서 알림 카테고리 및 액션 수정

## 🔍 트러블슈팅

### 일반적인 문제들

1. **토큰이 생성되지 않음**
   - 알림 권한이 허용되었는지 확인
   - Firebase 설정 파일이 올바르게 추가되었는지 확인
   - 네트워크 연결 상태 확인

2. **백그라운드 메시지가 수신되지 않음**
   - 서비스 워커가 올바르게 등록되었는지 확인 (웹)
   - 앱이 백그라운드 처리 권한을 가지고 있는지 확인 (모바일)

3. **알림이 표시되지 않음**
   - 기기의 알림 설정 확인
   - 앱별 알림 권한 확인
   - Do Not Disturb 모드 확인

## 📊 분석 및 모니터링

### Firebase Console에서 확인 가능한 지표
- 메시지 전송 통계
- 토큰 등록 현황
- 알림 열람률
- 오류 로그

### 서버 로그 모니터링
- FCM 토큰 등록/업데이트 로그
- 메시지 전송 성공/실패 로그
- 사용자별 알림 수신 설정

## 🔒 보안 고려사항

1. **토큰 보안**
   - FCM 토큰을 안전하게 저장
   - 토큰 갱신 시 즉시 서버 업데이트

2. **메시지 검증**
   - 서버에서 보낸 메시지인지 검증
   - 악성 페이로드 필터링

3. **권한 관리**
   - 최소 권한 원칙 적용
   - 사용자 동의 없이 알림 전송 금지

## 📞 지원

문제가 발생하거나 추가 설정이 필요한 경우:
- Firebase 공식 문서: https://firebase.google.com/docs/cloud-messaging
- 프로젝트 Issues: [GitHub Issues 링크]

---

**주의사항**: 모든 설정 파일의 `YOUR_*` 플레이스홀더를 실제 값으로 변경해야 합니다.