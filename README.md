# Weather Notification Backend

기상 정보를 바탕으로 사용자에게 알림을 보내는 Flask 백엔드 서버입니다.

## 프로젝트 구조

```
mwn_backend/
├── app.py              # Flask 애플리케이션 메인 파일
├── models.py           # 데이터베이스 모델 정의
├── config.py           # 설정 파일
├── requirements.txt    # Python 패키지 의존성
├── .env.example        # 환경 변수 예시 파일
└── README.md          # 프로젝트 문서
```

## 설치 및 실행

1. 가상환경 생성 및 활성화:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

2. 패키지 설치:
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정:
```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 값들을 설정
```

4. 데이터베이스 초기화:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

5. 서버 실행:
```bash
python app.py
```

## API 엔드포인트

### 건강 상태 확인
- `GET /health` - 서버 상태 확인

### 사용자 관리
- `GET /api/users` - 모든 사용자 조회
- `POST /api/users` - 새 사용자 생성

### 시장 관리
- `GET /api/markets` - 모든 시장 조회
- `POST /api/markets` - 새 시장 생성

### 피해 상태 관리
- `GET /api/damage-status` - 모든 피해 상태 조회
- `POST /api/damage-status` - 새 피해 상태 생성

## 데이터베이스 모델

### User
- 사용자 정보 및 알림 설정 관리

### Market
- 시장 정보 및 위치 데이터 관리

### DamageStatus
- 기상 이벤트로 인한 시장 피해 상태 추적