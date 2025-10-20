# FCM (Firebase Cloud Messaging) 통합

이 디렉토리는 날씨 알림 시스템의 FCM 통합 관련 파일들을 포함합니다.

## 📁 디렉토리 구조

```
fcm_integration/
├── README.md                     # 이 파일
├── firebase_config.py            # Firebase 설정 및 초기화
├── fcm_utils.py                  # FCM 서비스 유틸리티
├── migrate_database.py           # FCM 필드 추가 마이그레이션 스크립트
└── client_fcm_config/            # 클라이언트별 FCM 설정 파일들
    ├── README.md                 # 클라이언트 설정 가이드
    ├── firebase-config.js        # 웹 클라이언트 설정
    ├── firebase-messaging-sw.js  # 서비스 워커
    ├── AndroidManifest.xml       # Android 설정
    ├── MyFirebaseMessagingService.java # Android FCM 서비스
    └── FCMHelper.swift           # iOS FCM 헬퍼
```

## 🔧 설정 방법

### 1. Firebase 프로젝트 설정
1. [Firebase Console](https://console.firebase.google.com)에서 새 프로젝트 생성
2. 프로젝트 설정 > 서비스 계정에서 새 비공개 키 생성
3. 생성된 JSON 파일을 안전한 위치에 저장

### 2. 환경변수 설정
```bash
# 방법 1: 파일 경로로 설정
export FIREBASE_SERVICE_ACCOUNT_KEY="/path/to/firebase-service-account.json"

# 방법 2: JSON 문자열로 설정
export FIREBASE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
```

### 3. 데이터베이스 마이그레이션
```bash
# FCM 필드 추가 (기존 데이터 보존)
python fcm_integration/migrate_database.py
```

## 🚀 사용법

### 서버 측 FCM 서비스
```python
from fcm_integration.fcm_utils import fcm_service, weather_notification_service

# 개별 알림 전송
fcm_service.send_notification(
    token="FCM_TOKEN",
    title="날씨 알림",
    body="비가 예상됩니다."
)

# 날씨 알림 전송
weather_notification_service.send_weather_alert(
    users=user_list,
    weather_data=weather_info,
    alert_type="severe_weather"
)
```

### 클라이언트 설정
각 플랫폼별 설정은 `client_fcm_config/README.md` 참조

## 📱 지원 플랫폼

- **웹**: Progressive Web App 지원
- **Android**: Native Android 앱
- **iOS**: Native iOS 앱

## 🔔 알림 유형

1. **일반 날씨 알림**: 정기적인 날씨 정보
2. **심각한 날씨 알림**: 폭염, 한파, 호우, 강풍 등
3. **테스트 알림**: 개발 및 테스트용
4. **관리자 공지**: 시스템 공지사항

## 🛡️ 보안 고려사항

- Firebase 서비스 계정 키는 절대 버전 관리에 포함하지 마세요
- FCM 토큰은 민감한 정보이므로 안전하게 관리하세요
- 프로덕션 환경에서는 HTTPS를 반드시 사용하세요

## 🐛 트러블슈팅

### Firebase 초기화 실패
- 환경변수가 올바르게 설정되었는지 확인
- 서비스 계정 키 파일의 권한 확인
- Firebase 프로젝트 설정 재확인

### FCM 토큰 등록 실패
- 클라이언트 설정이 올바른지 확인
- 네트워크 연결 상태 확인
- 알림 권한이 허용되었는지 확인

### 알림이 도착하지 않음
- FCM 토큰이 유효한지 확인
- 기기의 알림 설정 확인
- 앱이 백그라운드에서 실행 중인지 확인