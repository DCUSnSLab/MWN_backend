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
- 컨테이너 시작 시 `entrypoint.sh` 스크립트가 실행되어 **DB 커넥션을 확인하고 `flask db upgrade`를 수행하여 스키마를 최신 상태로 유지**합니다. (자동 `flask db migrate`는 운영 환경에서 의도치 않은 스키마 변경을 유발할 수 있어 제거되었으며, 마이그레이션 파일 생성은 개발/CI 단계에서 수행합니다.)
- `mwn_backend_service_loadbalancer.yaml` 또는 Nginx 사이드카 레이어를 통해 Kubernetes 환경에 배포됩니다.
- 본 서버는 외부 웹서버(Nginx 등)의 프록시 뒤에서 5000번 포트로 구동됩니다. (최근 uWSGI 연동 시도가 있었으나 최종 롤백되어 기본적인 `python app.py` 컨테이너 구조를 유지하고 있습니다.)

---

## 4. 향후 작업자를 위한 체크리스트 및 가이드
- **DB 마이그레이션**: 모델 변경 시 로컬에서 `flask db migrate -m "메시지"`를 통해 반드시 픽스 파일을 생성하고 커밋해야 컨테이너 배포 시 `entrypoint.sh`가 `flask db upgrade`로 적용합니다. (컨테이너는 더 이상 `migrate`를 자동 실행하지 않습니다.)
- **Push Notification 테스트**: `fcm_integration/` 하위의 스크립트 및 `check_scheduler.py`를 활용해 날씨 수집 및 푸시 정상 발송 여부를 터미널에서 스탠드얼론으로 검증할 수 있습니다.
- **API 문서 확인**: 프론트엔드 연동 관련 변동 사항은 반드시 루트의 `API_DOCUMENTATION.md`에 현행화되어야 합니다.

---

## 5. 필수 환경변수 (운영 배포)

`FLASK_ENV=production`으로 구동 시 아래 변수가 **반드시** 설정되어야 합니다. 누락 시 앱이 시작 단계에서 `RuntimeError`로 중단되거나 컨테이너가 종료됩니다.

| 환경변수 | 용도 | 비고 |
|---|---|---|
| `SECRET_KEY` | Flask 세션 서명 키 | 미설정 시 운영 환경에서 기동 실패 |
| `JWT_SECRET_KEY` | JWT 토큰 서명 키 | 미설정 시 운영 환경에서 기동 실패 |
| `ADMIN_PASSWORD` | 초기 관리자 계정 비밀번호 | `entrypoint.sh`가 강제 요구 (미설정 시 컨테이너 종료) |
| `DATABASE_URL` | PostgreSQL 연결 문자열 | |
| `KMA_SERVICE_KEY` | 기상청 API 인증 키 | 미설정 시 날씨 알림 기능 제한 |
| `FIREBASE_SERVICE_ACCOUNT_KEY` | Firebase 서비스 계정 키 경로 | FCM 발송용 |

선택 변수: `ADMIN_EMAIL`(기본 `snslab@gmail.com`), `ADMIN_NAME`(기본 `시스템 관리자`), `PORT`(기본 5000), `CORS_ORIGINS`(웹 관리자용 CORS 허용 출처, 쉼표 구분, 미설정 시 `*`).

---

## 6. 보안/안정성 개선 이력 (2026-05)

이어서 작업하는 경우 아래 변경 사항을 인지해야 합니다.

### 인증 강화
- `/db-viewer/*`: Flask-Admin 세션(`admin_user_id`) 기반 관리자 인증 적용. 과거 무인증으로 전체 사용자 PII가 노출되던 경로였습니다.
- `/api/scheduler/{start,stop,collect}`: `admin_required`. `/api/scheduler/{status,stats}`: `login_required`.
- `/api/weather/{current,forecast}` (POST): `login_required`.
- `/api/markets` POST: `admin_required`, `/api/damage-status` POST: `login_required`. (각 GET은 공개 유지)
- `web_db_viewer.py`의 라우트 정의는 제거됨 — `app.py`와 endpoint가 충돌하던 dead code였습니다. 이 모듈은 `HTML_TEMPLATE` 상수만 export합니다.

### 외부 의존성 안정화
- `weather_api.py`: KMA API 호출에 `requests.Session` + `Retry`(3회, 지수 백오프) + `timeout=(5,30)` 적용. API 키를 로그에 노출하던 디버그 `print` 제거.
- `fcm_utils.py`: `UnregisteredError`/`SenderIdMismatchError`가 발생한 FCM 토큰을 DB에서 자동 무효화(`User.fcm_token=None`).

### 웹 관리자 CORS 지원
- Flutter Web 웹 관리자(프론트 저장소 `DCUSnSLab/MWN`)가 브라우저에서 `/api/*`를 호출할 수 있도록 `Flask-CORS`를 적용했습니다.
- `app.py`에서 `/api/*` 경로에만 CORS를 적용하며, 허용 출처는 `CORS_ORIGINS` 환경변수(쉼표 구분, 미설정 시 `*`)로 지정합니다. API는 Bearer 토큰 인증이라 와일드카드 출처도 안전합니다.
- `requirements.txt`에 `Flask-CORS==4.0.1`이 추가되어 **이미지 재빌드가 필요**합니다(파드 재시작만으로는 미반영).

### 알려진 버그 수정
- `weather_alerts.py`: `self.thresholds` AttributeError 수정(legacy 비예보 경로).
- `weather_alerts.py`: 적설량 알림이 영구 미발화하던 문제를 강수형태(`pty`) 기반으로 우회. **근본 해결은 미완** — 아래 TODO 참조.

### 남은 개선 항목 (TODO)
> 아래 항목 대부분은 **섹션 7(2026-06 세션)에서 해소**되었습니다. 현행 TODO는 섹션 7 마지막을 참조하세요.

- ~~**`Weather.sno`(적설량) 컬럼 부재**~~ → 컬럼 추가 완료(T15). 단 값 수집은 단기예보 도입 후 가능(섹션 7 참조).
- ~~에러 응답에 `str(e)` 노출~~ → 전역 `handle_unexpected_error` 로 표준 응답 통일.
- ~~`request.get_json` robust 파싱~~ → `silent=True, force=True` 패턴 일괄 적용.
- ~~모델 전반의 timezone-naive `datetime`~~ → `datetime.now(timezone.utc)` 전환(T16).
- ~~`app.py`(2300줄), `weather_alerts.py`(1400줄) 모놀리식~~ → Blueprint 10개 분리(T17) + `weather_alerts/` 패키지 9모듈 분리(T18).

---

## 7. 운영 안정화·최적화 이력 (2026-06 세션)

### 7.1 구조 리팩토링
- **T18 `weather_alerts` 패키지 분리** (`98b5192`): 1,420줄 단일 모듈 → 책임별 9개 모듈
  (`thresholds` / `messages` / `repository` / `evaluator` / `dispatcher` / `alarm_logger` / `system` / `facade` / `__init__`).
  외부 인터페이스(`WeatherAlertSystem`, `weather_alert_system`, 모듈 레벨 함수 5개) 100% 보존 — 동작 변경 없음.

### 7.2 마이그레이션 시스템 정상화 (`c059717`, `8207ca0`)
- `migrations/`를 git·이미지에 포함. **baseline `81fe5d2b22d6`** (8개 테이블·FK·인덱스 전체) 생성.
  모델 ↔ 운영 DB 간 drift 0 확인 후 stamp.
- `entrypoint.sh`가 매 부팅 `flask db init` 하던 동작 제거. SQLAlchemy 2.x 비호환 `db.engine.execute()` 핵 제거.
- **주의**: k8s가 `command: ["/bin/sh", ...]`로 셸을 강제하므로 `entrypoint.sh`에 **bash 전용 구문 사용 금지**
  (`${PIPESTATUS[0]}` 사용 시 dash에서 "Bad substitution" → CrashLoopBackOff 발생 이력).

### 7.3 배포·운영 안정성 (`cece845`, `bbfff02`)
- **Recreate 전략**: postgres가 같은 Pod의 RWO PVC를 쓰므로 RollingUpdate는 볼륨 마운트 충돌로 롤아웃이 막힘.
- **헬스 프로브**: backend startup/readiness/liveness + postgres `pg_isready`.
- **gunicorn 전환**: Werkzeug 개발서버 → `gunicorn --workers 1 --threads 8`.
  **워커 1개 고정 필수** — APScheduler가 워커 프로세스 안에서 돌아 N개면 알림이 N번 중복 발송됨.
- **이미지 버전 핀**: 배포 시 `:latest` → `:${BUILD_NUMBER}` sed 치환. `kubectl rollout undo`로 롤백 가능.

### 7.4 보안·신뢰성 강화 (`8a92021`)
- 세션 쿠키 `HttpOnly` + `SameSite=Lax` (`SESSION_COOKIE_SECURE`는 HTTPS 도입 시 env로 활성).
- **Flask-Limiter** 도입: `/api/auth/login` 10/min·100/h, `/api/auth/register` 5/min·30/h.
- DB 풀 `pool_size=10, max_overflow=5` (threads=8 대응).
- `MarketAlarmLog` 30일 보존 정리잡(매일 03:30) 추가 — 무한 증가 방지.
- `cleanup_old_weather_data`의 TZ 버그 수정(naive KST → naive UTC, cutoff가 9h 어긋나던 문제).
- **`/health`(liveness, DB 미확인) + `/health/ready`(readiness, DB `SELECT 1`) 분리** — transient DB 장애로 Pod가 재시작되는 cascading 회피.

### 7.5 `current.sky` 합성 (`c10b1fb`)
- KMA `getUltraSrtNcst`(초단기실황)는 **SKY 카테고리를 반환하지 않아** `current.sky`가 항상 NULL이었음.
- 같은 시각 `getUltraSrtFcst`(초단기예보)의 SKY를 복사하는 `_backfill_current_sky()` 추가.
- 기존 6,369행은 일회성 SQL backfill (6,271행=98.5% 충전).

### 7.6 성능 최적화 (`df481c1`)
| 항목 | Before | After |
|---|---|---|
| forecast 조회 인덱스 | `idx_weather_lookup`(base_*) — fcst_* 패턴 미적중 | **`idx_weather_forecast_fcst`** partial index 신설 (마이그레이션 `2a9731ed9d40`) |
| 알림 평가 DB 호출 | 278 시장 × 1회 | **98 좌표 × 1회** (좌표 단위 prefetch, **65%↓**) |
| 날씨 수집 시간 | 직렬 ~50초 | **8.78초** (ThreadPoolExecutor 10 워커, **~5.7배**) |

### 7.7 현행 TODO (다음 작업자용)
1. **다중 기상 소스 확장** — 후보 조사·가용성 테스트 완료. KMA apihub 예특보 카테고리 5개 sub-tab 확인:
   - ★★★ **기상특보** `typ01/url/wrn_now_data_new.php` — 공식 발효 특보 직접 인용 (임계 기반보다 신뢰도 우위)
   - ★★★ **영향예보** `typ01/url/ifs_fct_pstt.php` — KMA 공식 위험수준(관심~위험). 현행 33°C/-12°C 자체 임계를 대체 가능
   - ★★★ **단기예보** `typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst` — **POP(강수확률)·SNO(적설량)** 확보. 현재 두 필드가 대부분 NULL인 직접 원인
   - ★★ **중기예보** `MidFcstInfoService/getMidLandFcst`·`getMidTa` — 3~10일 outlook (regId 매핑 필요)
   - ★★ **Open-Meteo** — 무키·무료, 라이브 테스트 200 OK 확인 (10일 hourly + 대기질). 교차검증용
   - ★ **예·특보 구역정보** `FcstZoneInfoService/getFcstZoneCd` — 좌표→regId 매핑 보조
   - **선행 조건**: KMA apihub에서 각 그룹 **활용신청** 필요 (현재 키는 초단기실황·초단기예보만 승인됨 → 나머지는 403).
2. **노출된 KMA 키 회전** — `example_current_weather.py`의 평문 키는 redact 완료(`8a92021`)했으나
   **git history에는 잔존**. 키 회전 + `git filter-repo`로 history 재작성 + force-push 필요(협업자 영향 있어 보류 중).
3. **LoadBalancer `/health` 가로채기** — nginx가 `/health`를 직접 `ok`로 응답해 백엔드까지 도달하지 않음.
   외부에서 본 `/health`는 백엔드 상태와 무관하게 항상 200. k8s 프로브는 Pod 직접 접근이라 영향 없음.
4. **postgres 사이드카 조기 재시작** — 과거 모든 Pod에서 부팅 직후 1회 clean-exit 재시작이 관측되었으나,
   Recreate + 프로브 도입 후 소실됨(restartCount=0). 근본 원인 미규명 — 재발 시 probe 설정 점검.
5. `app.py`의 `db.create_all()`은 gunicorn 환경에서 미실행되는 dead code (마이그레이션이 스키마 권위).
6. `config.py`는 어디서도 import되지 않는 dead code.

### 7.8 운영 환경 현황 (2026-06 기준)
- **최종 배포**: 빌드 #136, 이미지 `harbor.cu.ac.kr/mwn/backend:136`
- **DB 스키마 버전**: alembic `2a9731ed9d40`
- **데이터**: 시장 278개(고유 좌표 98개), 사용자 33명
- **스케줄러 잡 4종**: 날씨수집(매시 45분) / 알림(매시 정각) / 날씨데이터 정리(03:00) / 알림로그 정리(03:30)
