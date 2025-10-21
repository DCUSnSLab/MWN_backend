# PostgreSQL 마이그레이션 가이드

## 🎯 개요

이 가이드는 기존 SQLite 기반 날씨 알림 시스템을 PostgreSQL로 마이그레이션하는 방법을 안내합니다.

## ✅ 완료된 작업

1. **PostgreSQL 드라이버 설치**: `psycopg2-binary` 패키지 추가
2. **코드 수정 완료**: Flask 앱이 PostgreSQL을 사용하도록 설정
3. **마이그레이션 스크립트 준비**: 데이터 이전 스크립트 작성
4. **환경설정 업데이트**: PostgreSQL 연결 문자열 설정

## 🔧 PostgreSQL 서버 설정 확인사항

현재 PostgreSQL 서버 연결에 문제가 있습니다. 다음 사항들을 확인하세요:

### 1. PostgreSQL 서버 실행 상태 확인
```bash
# PostgreSQL 서비스 상태 확인
pg_ctl status
# 또는
brew services list | grep postgresql
```

### 2. PostgreSQL 서버 시작
```bash
# Homebrew로 설치한 경우
brew services start postgresql

# 또는 직접 실행
pg_ctl start -D /usr/local/var/postgres
```

### 3. 사용자 및 데이터베이스 확인
```sql
-- postgres 사용자로 접속
psql -U postgres -d postgres

-- myuser 사용자 생성 (존재하지 않는 경우)
CREATE USER myuser WITH PASSWORD 'mypassword';

-- 데이터베이스 생성 권한 부여
ALTER USER myuser CREATEDB;

-- weather_notification 데이터베이스 생성
CREATE DATABASE weather_notification OWNER myuser;
```

### 4. 연결 설정 확인
PostgreSQL이 127.0.0.1:5432에서 접속을 허용하는지 확인:

**pg_hba.conf 설정 확인**:
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
```

**postgresql.conf 설정 확인**:
```
listen_addresses = 'localhost'
port = 5432
```

## 🚀 마이그레이션 실행 단계

### 1. PostgreSQL 연결 테스트
```bash
python test_pg_connection.py
```

### 2. 데이터 마이그레이션 실행
```bash
python migrate_to_postgresql.py
```

### 3. 환경변수 설정 (선택사항)
```bash
export DATABASE_URL="postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification"
```

### 4. Flask 애플리케이션 재시작
```bash
python app.py
```

## 📊 마이그레이션될 데이터

다음 테이블들이 SQLite에서 PostgreSQL로 이전됩니다:

1. **users** (273개 행 예상)
   - 사용자 정보 및 FCM 설정
   
2. **markets** (273개 행)
   - 시장 정보 (위도/경도, nx/ny 격자 좌표 포함)
   
3. **weather** (기존 날씨 데이터)
   - 수집된 날씨 정보
   
4. **damage_statuses** (피해 상태 데이터)
   - 기상 피해 관련 정보

## 🔄 롤백 방법

문제가 발생한 경우 SQLite로 롤백:

1. **app.py에서 데이터베이스 URL 변경**:
```python
default_db_url = 'sqlite:///instance/weather_notification.db'
```

2. **애플리케이션 재시작**

## ✨ PostgreSQL 사용의 장점

1. **성능 향상**: 대용량 데이터 처리 최적화
2. **동시성**: 여러 사용자 동시 접속 지원
3. **확장성**: 수평/수직 확장 가능
4. **고급 기능**: JSON 타입, 전문검색, 파티셔닝 등
5. **운영 안정성**: 엔터프라이즈급 데이터베이스

## 🛠️ 트러블슈팅

### 연결 실패 시
1. PostgreSQL 서버 실행 상태 확인
2. 포트 5432 사용 가능 여부 확인
3. 방화벽 설정 확인
4. 사용자 권한 확인

### 성능 최적화
```sql
-- 인덱스 생성 (마이그레이션 후)
CREATE INDEX idx_markets_coordinates ON markets(latitude, longitude);
CREATE INDEX idx_weather_location ON weather(nx, ny, created_at);
CREATE INDEX idx_users_email ON users(email);
```

## 📝 다음 단계

마이그레이션 완료 후:

1. **기능 테스트**: 모든 API 엔드포인트 동작 확인
2. **성능 모니터링**: 쿼리 성능 최적화
3. **백업 설정**: 정기 백업 스케줄 구성
4. **모니터링 도구**: PostgreSQL 모니터링 설정

---

## 🆘 지원

마이그레이션 중 문제가 발생하면:
1. 로그 확인: PostgreSQL 서버 로그 및 애플리케이션 로그
2. 연결 테스트: `python test_pg_connection.py`
3. 수동 확인: psql 클라이언트로 직접 연결 테스트