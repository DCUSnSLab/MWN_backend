# 날씨 알림 백엔드 API 문서

## 🌐 서버 정보
- **베이스 URL**: `http://localhost:5000`
- **포트**: 5000
- **응답 형식**: JSON

---

## 📋 API 엔드포인트 목록

### 🏥 서버 상태

#### 1. 헬스 체크
```http
GET /health
```
**설명**: 서버 상태 확인  
**응답**:
```json
{
    "status": "healthy",
    "timestamp": "2025-10-17T16:00:00.000000"
}
```

---

### 🔐 사용자 인증

#### 2. 회원가입
```http
POST /api/auth/register
```

**요청**:
```json
{
    "name": "김철수",
    "email": "kim@example.com",
    "password": "SecurePass123!",
    "phone": "010-1234-5678",
    "location": "서울특별시 중구"
}
```

**응답**:
```json
{
    "message": "회원가입이 완료되었습니다.",
    "user": {
        "id": 1,
        "name": "김철수",
        "email": "kim@example.com",
        "phone": "010-1234-5678",
        "location": "서울특별시 중구",
        "is_active": true,
        "role": "user",
        "email_verified": false,
        "created_at": "2025-10-19T13:00:00.000000"
    },
    "tokens": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "token_type": "Bearer",
        "expires_in": 86400
    }
}
```

#### 3. 로그인
```http
POST /api/auth/login
```

**요청**:
```json
{
    "email": "kim@example.com",
    "password": "SecurePass123!"
}
```

**응답**:
```json
{
    "message": "로그인에 성공했습니다.",
    "user": {
        "id": 1,
        "name": "김철수",
        "email": "kim@example.com",
        "last_login": "2025-10-19T13:30:00.000000"
    },
    "tokens": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "token_type": "Bearer",
        "expires_in": 86400
    }
}
```

#### 4. 프로필 조회 (인증 필요)
```http
GET /api/auth/me
Authorization: Bearer {access_token}
```

**응답**:
```json
{
    "user": {
        "id": 1,
        "name": "김철수",
        "email": "kim@example.com",
        "phone": "010-1234-5678",
        "location": "서울특별시 중구",
        "is_active": true,
        "email_verified": false,
        "last_login": "2025-10-19T13:30:00.000000"
    }
}
```

#### 5. 토큰 갱신
```http
POST /api/auth/refresh
```

**요청**:
```json
{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**응답**:
```json
{
    "message": "토큰이 갱신되었습니다.",
    "tokens": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "token_type": "Bearer",
        "expires_in": 86400
    }
}
```

#### 6. 로그아웃
```http
POST /api/auth/logout
```

**응답**:
```json
{
    "message": "로그아웃되었습니다."
}
```

---

### 👥 사용자 관리 (관리자용)

#### 7. 사용자 목록 조회 (관리자 권한 필요)
```http
GET /api/users
Authorization: Bearer {admin_access_token}
```

**응답**:
```json
[
    {
        "id": 1,
        "name": "김철수",
        "email": "kim@example.com",
        "phone": "010-1234-5678",
        "location": "서울특별시 중구",
        "is_active": true,
        "email_verified": false,
        "last_login": "2025-10-19T13:30:00.000000",
        "created_at": "2025-10-19T13:00:00.000000"
    }
]
```

#### 8. 관리자용 사용자 생성 (관리자 권한 필요)
```http
POST /api/admin/users
Authorization: Bearer {admin_access_token}
```

**요청**:
```json
{
    "name": "이영희",
    "email": "lee@example.com",
    "password": "TempPass123!",
    "phone": "010-2345-6789",
    "location": "부산광역시 중구",
    "role": "user"
}
```

---

### 🏪 시장 관리

#### 9. 시장 조회/생성
```http
GET /api/markets
POST /api/markets
```

**GET 응답**:
```json
[
    {
        "id": 1,
        "name": "동대문시장",
        "location": "서울특별시 중구 창신동",
        "latitude": 37.5707,
        "longitude": 127.0087,
        "nx": 60,
        "ny": 127,
        "category": "전통시장",
        "is_active": true,
        "created_at": "2025-10-17T07:00:00.000000"
    }
]
```

**POST 요청**:
```json
{
    "name": "새로운시장",
    "location": "대전광역시 중구",
    "latitude": 36.3214,
    "longitude": 127.4214,
    "category": "전통시장"
}
```

#### 9-1. 시장 검색
```http
GET /api/markets/search?q={검색어}&limit={개수}
```

**요청 파라미터**:
- `q`: 검색어 (최소 2글자)
- `limit`: 결과 개수 (기본값: 20)

**응답**:
```json
{
    "query": "동대문",
    "count": 2,
    "markets": [
        {
            "id": 1,
            "name": "동대문시장",
            "location": "서울특별시 중구 창신동",
            "latitude": 37.5707,
            "longitude": 127.0087,
            "nx": 60,
            "ny": 127,
            "category": "전통시장",
            "is_active": true
        }
    ]
}
```

---

### ⭐ 관심목록 관리

#### 10. 사용자 관심목록 조회 (인증 필요)
```http
GET /api/watchlist
Authorization: Bearer {access_token}
```

**응답**:
```json
{
    "count": 2,
    "watchlist": [
        {
            "id": 1,
            "user_id": 1,
            "market_id": 1,
            "market_name": "동대문시장",
            "market_location": "서울특별시 중구 창신동",
            "market_coordinates": {
                "latitude": 37.5707,
                "longitude": 127.0087,
                "nx": 60,
                "ny": 127
            },
            "created_at": "2025-10-22T08:00:00.000000",
            "is_active": true,
            "notification_enabled": true
        }
    ]
}
```

#### 11. 관심목록에 시장 추가 (인증 필요)
```http
POST /api/watchlist
Authorization: Bearer {access_token}
```

**요청**:
```json
{
    "market_id": 1
}
```

**응답**:
```json
{
    "message": "동대문시장이(가) 관심 목록에 추가되었습니다.",
    "interest": {
        "id": 1,
        "user_id": 1,
        "market_id": 1,
        "market_name": "동대문시장",
        "is_active": true,
        "notification_enabled": true,
        "created_at": "2025-10-22T08:00:00.000000"
    }
}
```

#### 12. 관심목록에서 시장 제거 (인증 필요)
```http
DELETE /api/watchlist/{market_id}
Authorization: Bearer {access_token}
```

**응답**:
```json
{
    "message": "관심 목록에서 제거되었습니다.",
    "market_id": 1
}
```

#### 13. 관심 시장 알림 설정 토글 (인증 필요)
```http
PUT /api/watchlist/{interest_id}/notification
Authorization: Bearer {access_token}
```

**응답**:
```json
{
    "message": "알림이 활성화되었습니다.",
    "interest": {
        "id": 1,
        "notification_enabled": true,
        "market_name": "동대문시장"
    }
}
```

---

### ⚠️ 피해 상태 관리

#### 14. 피해 상태 조회/생성
```http
GET /api/damage-status
POST /api/damage-status
```

**POST 요청**:
```json
{
    "market_id": 1,
    "weather_event": "태풍",
    "damage_level": "심각",
    "description": "지붕 일부 손상",
    "estimated_recovery_time": "2025-10-20T10:00:00"
}
```

---

### 🌧️ 비 예보 알림

#### 15. 특정 시장의 비 예보 확인
```http
GET /api/markets/{market_id}/rain-forecast?hours={시간}
```

**요청 파라미터**:
- `market_id`: 시장 ID
- `hours`: 예보 확인 시간 (기본값: 24시간)

**응답**:
```json
{
    "status": "success",
    "market_id": 1,
    "forecast": {
        "has_rain": true,
        "market_name": "동대문시장",
        "alerts": [
            {
                "datetime": "2025-10-22T14:00:00",
                "pop": 60,
                "pty": "1",
                "description": "비"
            }
        ],
        "checked_hours": 24
    }
}
```

#### 16. 관리자용 수동 비 예보 알림 확인 (관리자 권한 필요)
```http
POST /api/admin/rain-alerts/check
Authorization: Bearer {admin_access_token}
```

**요청**:
```json
{
    "hours": 24
}
```

**응답**:
```json
{
    "status": "success",
    "message": "비 예보 알림 확인 완료",
    "result": {
        "success": true,
        "checked_markets": 15,
        "alerts_sent": 3,
        "results": [
            {
                "market": "동대문시장",
                "rain_forecast": true,
                "alert_result": {
                    "success": true,
                    "sent_count": 5
                }
            }
        ]
    }
}
```

---

### 🌤️ 날씨 데이터

#### 17. 현재 날씨 조회
```http
POST /api/weather/current
```

**요청**:
```json
{
    "latitude": 37.5665,
    "longitude": 126.9780,
    "location_name": "서울시청"
}
```

**응답**:
```json
{
    "status": "success",
    "data": {
        "base_date": "20251017",
        "base_time": "1600",
        "nx": 60,
        "ny": 127,
        "temp": 23.1,
        "humidity": 65.0,
        "rain_1h": 0.0,
        "wind_speed": 2.1,
        "wind_direction": 120.0,
        "api_type": "current",
        "location_name": "서울시청"
    }
}
```

#### 18. 날씨 예보 조회
```http
POST /api/weather/forecast
```

**요청**:
```json
{
    "latitude": 37.5665,
    "longitude": 126.9780,
    "location_name": "서울시청"
}
```

**응답**:
```json
{
    "status": "success",
    "data": [
        {
            "base_date": "20251017",
            "base_time": "1630",
            "fcst_date": "20251017",
            "fcst_time": "1700",
            "temp": 22.0,
            "humidity": 70.0,
            "rain_1h": 0.0,
            "pty": "0",
            "sky": "3",
            "api_type": "forecast"
        }
    ]
}
```

#### 19. 저장된 날씨 데이터 조회
```http
GET /api/weather
GET /api/weather?location_name=동대문
GET /api/weather?api_type=current
GET /api/weather?limit=50
```

**응답**:
```json
{
    "status": "success",
    "count": 21,
    "data": [
        {
            "id": 1,
            "location_name": "동대문시장 (서울특별시 중구 창신동)",
            "api_type": "current",
            "temp": 23.1,
            "humidity": 65.0,
            "created_at": "2025-10-17T07:55:12.000000"
        }
    ]
}
```

---

### 🤖 스케줄러 관리

#### 20. 스케줄러 시작
```http
POST /api/scheduler/start
```

**응답**:
```json
{
    "status": "success",
    "message": "날씨 스케줄러가 시작되었습니다."
}
```

#### 21. 스케줄러 정지
```http
POST /api/scheduler/stop
```

#### 22. 스케줄러 상태 조회
```http
GET /api/scheduler/status
```

**응답**:
```json
{
    "scheduler_running": true,
    "job_count": 1,
    "jobs": [
        {
            "id": "weather_collection_job",
            "name": "시장별 날씨 데이터 수집",
            "next_run": "2025-10-17T17:25:00.000000"
        }
    ]
}
```

#### 23. 날씨 데이터 통계
```http
GET /api/scheduler/stats
```

**응답**:
```json
{
    "total_weather_records": 21,
    "current_weather_records": 3,
    "forecast_weather_records": 18,
    "active_markets": 3,
    "markets_with_coordinates": 3,
    "latest_weather_update": "2025-10-17T07:55:12.000000"
}
```

#### 24. 수동 날씨 데이터 수집
```http
POST /api/scheduler/collect
```

**응답**:
```json
{
    "status": "success",
    "message": "날씨 데이터 수집이 완료되었습니다."
}
```

---

### 📱 FCM (푸시 알림) 관리

#### 25. FCM 토큰 등록/업데이트 (인증 필요)
```http
POST /api/fcm/register
Authorization: Bearer {access_token}
```

**요청**:
```json
{
    "token": "FCM_REGISTRATION_TOKEN",
    "device_info": {
        "platform": "web",
        "browser": "Chrome 119.0.0.0",
        "timestamp": "2025-10-19T13:00:00Z"
    },
    "subscribe_topics": ["weather_alerts", "severe_weather"]
}
```

**응답**:
```json
{
    "message": "FCM 토큰이 등록되었습니다.",
    "fcm_enabled": true,
    "subscribed_topics": ["weather_alerts", "severe_weather"]
}
```

#### 26. FCM 설정 조회/업데이트 (인증 필요)
```http
GET /api/fcm/settings
POST /api/fcm/settings
Authorization: Bearer {access_token}
```

**GET 응답**:
```json
{
    "fcm_enabled": true,
    "fcm_topics": ["weather_alerts", "severe_weather"],
    "device_info": {
        "platform": "web",
        "browser": "Chrome 119.0.0.0"
    },
    "has_token": true
}
```

**POST 요청** (설정 업데이트):
```json
{
    "enabled": true,
    "subscribe_topics": ["weather_alerts"],
    "unsubscribe_topics": ["severe_weather"]
}
```

#### 27. FCM 테스트 알림 전송 (인증 필요)
```http
POST /api/fcm/test
Authorization: Bearer {access_token}
```

**응답**:
```json
{
    "message": "테스트 알림이 전송되었습니다."
}
```

#### 28. 관리자용 FCM 알림 전송 (관리자 권한 필요)
```http
POST /api/admin/fcm/send
Authorization: Bearer {admin_access_token}
```

**요청** (주제로 전송):
```json
{
    "title": "기상 특보",
    "body": "서울 지역에 호우 경보가 발령되었습니다.",
    "topic": "severe_weather",
    "data": {
        "type": "severe_weather",
        "location": "서울"
    }
}
```

**요청** (특정 사용자들에게 전송):
```json
{
    "title": "날씨 알림",
    "body": "내일 비가 예상됩니다.",
    "user_ids": [1, 2, 3],
    "data": {
        "type": "weather_forecast"
    }
}
```

**요청** (전체 사용자에게 전송):
```json
{
    "title": "전체 공지",
    "body": "날씨 서비스가 업데이트되었습니다.",
    "data": {
        "type": "announcement"
    }
}
```

**응답**:
```json
{
    "message": "전체 15명의 사용자에게 알림이 전송되었습니다.",
    "result": {
        "success_count": 14,
        "failure_count": 1,
        "failed_tokens": ["invalid_token_example"]
    }
}
```

---

### 🗄️ 데이터베이스 뷰어

#### 29. 웹 데이터베이스 뷰어
```http
GET /db-viewer
```
**설명**: 브라우저에서 데이터베이스 내용을 확인할 수 있는 웹 인터페이스

#### 30. 데이터베이스 API들
```http
GET /db-viewer/api/stats     # 통계
GET /db-viewer/api/users     # 사용자 데이터
GET /db-viewer/api/markets   # 시장 데이터
GET /db-viewer/api/weather   # 날씨 데이터
GET /db-viewer/api/damage    # 피해상태 데이터
```

---

## 🔧 사용 예시

### 1. cURL로 API 호출
```bash
# 헬스 체크
curl http://localhost:5000/health

# 회원가입
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "김철수", "email": "kim@example.com", "password": "SecurePass123!"}'

# 로그인
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "kim@example.com", "password": "SecurePass123!"}'

# 인증된 프로필 조회 (토큰 필요)
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  http://localhost:5000/api/auth/me

# 모든 시장 조회
curl http://localhost:5000/api/markets

# 현재 날씨 조회
curl -X POST http://localhost:5000/api/weather/current \
  -H "Content-Type: application/json" \
  -d '{"latitude": 37.5665, "longitude": 126.9780, "location_name": "서울"}'

# 스케줄러 시작
curl -X POST http://localhost:5000/api/scheduler/start

# 날씨 통계 조회
curl http://localhost:5000/api/scheduler/stats

# FCM 토큰 등록 (인증 필요)
curl -X POST http://localhost:5000/api/fcm/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"token": "FCM_TOKEN", "device_info": {"platform": "web"}}'

# FCM 테스트 알림 전송 (인증 필요)
curl -X POST http://localhost:5000/api/fcm/test \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 관리자용 전체 FCM 알림 전송
curl -X POST http://localhost:5000/api/admin/fcm/send \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"title": "기상 특보", "body": "호우 경보 발령"}'

# 시장 검색
curl "http://localhost:5000/api/markets/search?q=동대문&limit=10"

# 관심목록 조회 (인증 필요)
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  http://localhost:5000/api/watchlist

# 관심목록에 시장 추가 (인증 필요)
curl -X POST http://localhost:5000/api/watchlist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"market_id": 1}'

# 관심목록에서 시장 제거 (인증 필요)
curl -X DELETE http://localhost:5000/api/watchlist/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 시장의 비 예보 확인
curl "http://localhost:5000/api/markets/1/rain-forecast?hours=24"

# 관리자용 수동 비 예보 알림 확인 (관리자 권한 필요)
curl -X POST http://localhost:5000/api/admin/rain-alerts/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"hours": 24}'
```

### 2. JavaScript/Fetch로 호출
```javascript
// 회원가입
const registerResponse = await fetch('http://localhost:5000/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: '김철수',
    email: 'kim@example.com',
    password: 'SecurePass123!'
  })
});
const registerData = await registerResponse.json();
const accessToken = registerData.tokens.access_token;

// 로그인
const loginResponse = await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'kim@example.com',
    password: 'SecurePass123!'
  })
});
const loginData = await loginResponse.json();

// 인증된 프로필 조회
const profileResponse = await fetch('http://localhost:5000/api/auth/me', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const profile = await profileResponse.json();

// 시장 목록 조회
fetch('http://localhost:5000/api/markets')
  .then(response => response.json())
  .then(data => console.log(data));

// 현재 날씨 조회
fetch('http://localhost:5000/api/weather/current', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    latitude: 37.5665,
    longitude: 126.9780,
    location_name: '서울시청'
  })
})
.then(response => response.json())
.then(data => console.log(data));

// FCM 토큰 등록
fetch('http://localhost:5000/api/fcm/register', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${accessToken}`
  },
  body: JSON.stringify({
    token: 'FCM_REGISTRATION_TOKEN',
    device_info: { platform: 'web', browser: 'Chrome' },
    subscribe_topics: ['weather_alerts']
  })
})
.then(response => response.json())
.then(data => console.log(data));

// FCM 테스트 알림
fetch('http://localhost:5000/api/fcm/test', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${accessToken}` }
})
.then(response => response.json())
.then(data => console.log(data));

// 시장 검색
fetch('http://localhost:5000/api/markets/search?q=동대문&limit=10')
  .then(response => response.json())
  .then(data => console.log(data));

// 관심목록 조회
fetch('http://localhost:5000/api/watchlist', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
})
.then(response => response.json())
.then(data => console.log(data));

// 관심목록에 시장 추가
fetch('http://localhost:5000/api/watchlist', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${accessToken}`
  },
  body: JSON.stringify({ market_id: 1 })
})
.then(response => response.json())
.then(data => console.log(data));

// 시장의 비 예보 확인
fetch('http://localhost:5000/api/markets/1/rain-forecast?hours=24')
  .then(response => response.json())
  .then(data => console.log(data));
```

### 3. Python requests로 호출
```python
import requests

# 회원가입
register_data = {
    "name": "김철수",
    "email": "kim@example.com",
    "password": "SecurePass123!"
}
register_response = requests.post('http://localhost:5000/api/auth/register', 
                                 json=register_data)
register_result = register_response.json()
access_token = register_result['tokens']['access_token']

# 로그인
login_data = {
    "email": "kim@example.com",
    "password": "SecurePass123!"
}
login_response = requests.post('http://localhost:5000/api/auth/login', 
                              json=login_data)
login_result = login_response.json()

# 인증된 프로필 조회
headers = {"Authorization": f"Bearer {access_token}"}
profile_response = requests.get('http://localhost:5000/api/auth/me', 
                               headers=headers)
profile = profile_response.json()

# 시장 목록 조회
response = requests.get('http://localhost:5000/api/markets')
markets = response.json()

# 현재 날씨 조회
weather_data = {
    "latitude": 37.5665,
    "longitude": 126.9780,
    "location_name": "서울시청"
}
response = requests.post('http://localhost:5000/api/weather/current', 
                        json=weather_data)
weather = response.json()

# FCM 토큰 등록
fcm_data = {
    "token": "FCM_REGISTRATION_TOKEN",
    "device_info": {"platform": "python", "version": "3.9"},
    "subscribe_topics": ["weather_alerts"]
}
fcm_response = requests.post('http://localhost:5000/api/fcm/register',
                            json=fcm_data, headers=headers)
fcm_result = fcm_response.json()

# FCM 테스트 알림
test_response = requests.post('http://localhost:5000/api/fcm/test',
                             headers=headers)
test_result = test_response.json()
```

---

## 📝 중요 참고사항

1. **인증 시스템**: JWT 토큰 기반 인증을 사용합니다
   - 회원가입/로그인 시 access_token과 refresh_token을 발급받습니다
   - access_token은 24시간, refresh_token은 30일간 유효합니다
   - 인증이 필요한 API는 `Authorization: Bearer {access_token}` 헤더를 사용합니다

2. **사용자 권한 시스템**: 
   - `user`: 일반 사용자 (회원가입으로 생성)
   - `admin`: 관리자 (서버 스크립트로만 생성, ID: snslab / PW: snslab@cu)
   - 관리자 권한이 필요한 API는 별도 표시

3. **관심목록 시스템**:
   - 사용자는 여러 시장을 관심목록에 추가 가능
   - 각 시장별로 개별 알림 설정 가능
   - 관심 시장의 비 예보 시 자동 FCM 알림 전송

4. **비 예보 알림**:
   - 매 시간마다 자동으로 향후 24시간 비 예보 확인
   - 강수확률 30% 이상 또는 강수형태 존재 시 알림
   - 관심 시장 등록 사용자에게만 개별 알림 전송

5. **패스워드 요구사항**: 
   - 최소 8자 이상
   - 대문자, 소문자, 숫자 포함 필수

6. **CORS**: 다른 도메인에서 호출 시 CORS 설정이 필요할 수 있습니다

7. **Rate Limit**: 기상청 API 호출 제한이 있으므로 너무 자주 호출하지 마세요

8. **에러 처리**: 모든 API는 실패 시 `{"error": "메시지"}` 형태로 응답합니다

9. **FCM 설정**: 
   - Firebase 프로젝트 설정 및 서비스 계정 키가 필요합니다
   - 환경변수 `FIREBASE_SERVICE_ACCOUNT_KEY` 또는 `FIREBASE_SERVICE_ACCOUNT_JSON` 설정 필요
   - 클라이언트별 FCM SDK 설정은 `client_fcm_config/` 디렉토리 참조

10. **날씨 알림**: 
    - 자동 스케줄러가 심각한 날씨 조건 감지 시 FCM 알림 자동 전송
    - 폭염(35°C 이상), 한파(-10°C 이하), 호우(10mm/h 이상), 강풍(14m/s 이상) 조건
    - 관심 시장 기반 비 예보 알림 (강수확률 30% 이상)

---

## 🚀 서버 실행
```bash
python app.py
# 서버 주소: http://localhost:5000
```