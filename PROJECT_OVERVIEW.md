# Market Weather Notification (MWN) Backend - Project Overview

이 문서는 MWN(Market Weather Notification) 백엔드 프로젝트를 이어서 작업할 AI 또는 개발자를 위해 작성된 전체 프로젝트 아키텍처 및 구성 요소 명세서입니다.

## 1. 프로젝트 개요
MWN 백엔드는 전통시장 상인 및 사용자들에게 기상청 날씨 데이터를 기반으로 실시간 날씨 정보와 기상 특보(비, 눈, 폭염, 한파, 강풍 등) 알림을 제공하는 **Python Flask 기반의 웹 애플리케이션**입니다.

- **Framework**: Flask (Python 3.11)
- **Database**: PostgreSQL (개발 시 SQLite 지원), SQLAlchemy ORM, Flask-Migrate
- **Authentication**: JWT (JSON Web Tokens) 기반 자체 로그인/인증
- **Background Jobs**: APScheduler (주기적인 날씨 데이터 수집 및 알림 발송)
- **Push Notification**: Firebase Cloud Messaging (FCM)
- **Deployment**: Docker, Kubernetes (k8s), Jenkins (CI/CD)

---

## 2. 디렉터리 및 파일 구조

```text
mwn_backend/
├── app.py                  # Flask 애플리케이션 엔트리포인트 (라우팅, 앱 초기화)
├── models.py               # SQLAlchemy 데이터베이스 모델 정의
├── config.py               # 환경별 설정 정보 (Development/Production 등)
├── database.py             # SQLAlchemy db 인스턴스 초기화
├── auth_utils.py           # JWT 생성, 검증 및 인증 데코레이터 (@login_required 등)
├── admin_panel.py          # Flask-Admin을 활용한 관리자 페이지 설정
├── weather_api.py          # 기상청(KMA) 및 OpenWeatherMap API 통신 모듈
├── weather_scheduler.py    # APScheduler를 활용한 백그라운드 날씨 수집 및 알림 스케줄러
├── weather_alerts.py       # 수집된 날씨 데이터를 분석하여 특보 발생 조건 확인 및 FCM 발송
├── API_DOCUMENTATION.md    # 프론트엔드 연동을 위한 RESTful API 전체 명세서
├── fcm_integration/        # FCM 푸시 알림 연동 및 설정 코드
├── k8s/                    # Kubernetes 배포용 Manifest 파일들 (Deployment, Service)
├── Jenkinsfile             # Jenkins CI/CD 파이프라인 스크립트
├── Dockerfile              # 컨테이너 환경 빌드 설정
├── entrypoint.sh           # 컨테이너 실행 시 DB 마이그레이션(alembic) 및 앱 구동 스크립트
├── docker-compose.yml      # 로컬 개발 및 테스트용 Docker Compose 파일
├── requirements.txt        # 의존성 패키지 목록
└── .env                    # 민감한 환경변수 설정 파일 (DB_URL, API_KEY 등)
```

---

## 3. 핵심 모듈 및 아키텍처 설명

### 3.1. 애플리케이션 엔트리포인트 (`app.py`)
- Flask 애플리케이션 초기화 및 `ProxyFix` 설정 (Nginx 등의 리버스 프록시 뒤에서 구동 시 올바른 클라이언트 IP 확보).
- 사용자 인증(auth), 시장 조회(markets), 알림 설정(watchlist), 피해 신고(reports) 등 모든 API 라우트 포함.
- 데이터베이스 초기화 및 APScheduler 자동 시작 로직 포함.
- **주의:** 모든 POST/PUT 요청 등 바디 데이터 파싱 시 `request.get_json(silent=True, force=True) or {}`를 사용하여 Nginx 프록시 환경에서도 안정적으로 JSON을 파싱하도록 대응되어 있습니다.

### 3.2. 데이터베이스 모델 (`models.py`)
주요 테이블 구조는 다음과 같습니다.
1. **User**: 사용자 정보, 암호화된 비밀번호(werkzeug), 권한(role), FCM 토큰 및 방해금지 시간 설정 보유.
2. **Market**: 지리적 좌표(nx, ny, 위도/경도) 및 날씨 알림 조건 임계값(폭염, 한파 기준 온도 등) 보유.
3. **UserMarketInterest**: 사용자-시장의 N:M 다대다 관계 매핑 (관심 시장 등록).
4. **Weather**: 기상청 등에서 수집해 온 시간별/지역별 날씨 실황 및 예보 데이터 저장.
5. **DamageStatus**: 시장의 기상 피해 상태(침수 등) 보고.
6. **MarketReport**: 상인이 직접 이미지 등과 함께 올리는 사건/사고 접수.
7. **MarketAlarmLog**: FCM으로 대상 시장의 사용자들에게 발송된 기상 특보 이력 및 결과 통계.

### 3.3. 날씨 데이터 및 스케줄러 (`weather_api.py`, `weather_scheduler.py`, `weather_alerts.py`)
- **API**: 공공데이터포털의 기상청 단기예보/초단기실황 API를 주로 사용하여 격자(nx, ny) 데이터 수집.
- **Scheduler**: 백그라운드에서 주기적으로(ex. 매시 정각) 실행되며 등록된(Active) 시장들에 대한 날씨 데이터를 일괄 수집하여 DB의 `weather` 테이블에 캐싱.
- **Alerts**: 수집된 데이터를 바탕으로 각 시장의 `alert_conditions` 기준을 초과하는 경우(ex. 강수 확률 산출, 임계 온도 돌파) FCM 모듈을 호출하여 관심 등록된 사용자들에게 Push 발송.

### 3.4. 배포 환경 (`Dockerfile`, `entrypoint.sh`, `Jenkinsfile`)
- 컨테이너 시작 시 `entrypoint.sh` 스크립트가 실행되어 **동적으로 DB 커넥션을 확인하고 `flask db migrate`, `flask db upgrade`를 수행하여 스키마를 최신 상태로 유지**합니다.
- `mwn_backend_service_loadbalancer.yaml` 또는 Nginx 사이드카 레이어를 통해 Kubernetes 환경에 배포됩니다.
- 본 서버는 외부 웹서버(Nginx 등)의 프록시 뒤에서 5000번 포트로 구동됩니다. (최근 uWSGI 연동 시도가 있었으나 최종 롤백되어 기본적인 `python app.py` 컨테이너 구조를 유지하고 있습니다.)

---

## 4. 향후 작업자를 위한 체크리스트 및 가이드
- **DB 마이그레이션**: 모델 변경 시 로컬에서 `flask db migrate -m "메시지"`를 통해 반드시 픽스 파일을 생성하고 커밋해야 컨테이너 배포 시 `entrypoint.sh`가 자동 업그레이드를 수행합니다.
- **Push Notification 테스트**: `fcm_integration/` 하위의 스크립트 및 `check_scheduler.py`를 활용해 날씨 수집 및 푸시 정상 발송 여부를 터미널에서 스탠드얼론으로 검증할 수 있습니다.
- **API 문서 확인**: 프론트엔드 연동 관련 변동 사항은 반드시 루트의 `API_DOCUMENTATION.md`에 현행화되어야 합니다.
