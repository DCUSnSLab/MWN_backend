# 데이터베이스 마이그레이션 가이드

Flask-Migrate를 사용하여 데이터베이스 스키마를 안전하게 관리하는 방법입니다.

## 🎯 개요

이 프로젝트는 **Flask-Migrate (Alembic 기반)**를 사용하여 데이터베이스 스키마 변경을 추적하고 적용합니다.

### 주요 장점
- ✅ **데이터 보존**: 기존 데이터를 유지하면서 스키마만 변경
- ✅ **버전 관리**: 모든 변경사항이 Git으로 추적됨
- ✅ **자동 적용**: Kubernetes Pod 시작 시 자동으로 마이그레이션 적용
- ✅ **롤백 가능**: 문제 발생 시 이전 버전으로 되돌리기 가능

## 📋 워크플로우

### 1. 모델 변경 (개발자)

`models.py`에서 모델을 수정합니다:

```python
# 예: MarketAlarmLog 모델에 새 필드 추가
class MarketAlarmLog(db.Model):
    # ... 기존 필드들 ...

    # 새 필드 추가
    sent_to_devices = db.Column(db.Integer, default=0)  # 신규 필드
```

### 2. 마이그레이션 생성

로컬 환경에서 마이그레이션 파일을 생성합니다:

```bash
# 방법 1: 헬퍼 스크립트 사용 (권장)
./init_migration.sh "Add sent_to_devices field to MarketAlarmLog"

# 방법 2: Flask CLI 직접 사용
export FLASK_APP=app.py
flask db migrate -m "Add sent_to_devices field to MarketAlarmLog"
```

이 명령어는 `migrations/versions/` 폴더에 새로운 마이그레이션 파일을 생성합니다.

### 3. 마이그레이션 검토

생성된 마이그레이션 파일을 **반드시 검토**하세요:

```bash
ls -la migrations/versions/
cat migrations/versions/xxxx_add_sent_to_devices_field.py
```

자동 생성된 코드가 의도한 변경사항과 일치하는지 확인합니다.

### 4. 로컬 테스트

로컬 데이터베이스에 마이그레이션을 적용하여 테스트합니다:

```bash
# 마이그레이션 적용
flask db upgrade

# 문제가 있으면 롤백
flask db downgrade
```

### 5. Git 커밋

테스트가 완료되면 migrations 폴더를 Git에 커밋합니다:

```bash
git add migrations/
git commit -m "Add migration: Add sent_to_devices field to MarketAlarmLog"
git push
```

### 6. Docker 이미지 빌드 및 배포

Docker 이미지를 빌드하면 `migrations` 폴더가 포함됩니다:

```bash
docker build -t your-registry/weather-backend:latest .
docker push your-registry/weather-backend:latest
```

### 7. 자동 적용 (Kubernetes Pod)

Kubernetes Pod가 시작될 때 `entrypoint.sh`가 자동으로:
1. migrations 디렉토리 확인
2. 새로운 마이그레이션 감지
3. `flask db upgrade` 실행하여 스키마 업데이트

```
🗃️ Initializing database migration...
  🔍 모델 변경사항 확인 중...
  📝 새로운 마이그레이션 파일 생성됨
  🚀 마이그레이션 적용 중...
  ✅ 데이터베이스 마이그레이션 완료!
```

## 🛠️ 주요 명령어

### 마이그레이션 생성
```bash
flask db migrate -m "설명 메시지"
```

### 마이그레이션 적용
```bash
flask db upgrade              # 최신 버전으로 업그레이드
flask db upgrade +1           # 다음 버전으로 한 단계만 업그레이드
flask db upgrade <revision>   # 특정 버전으로 업그레이드
```

### 마이그레이션 롤백
```bash
flask db downgrade            # 이전 버전으로 다운그레이드
flask db downgrade -1         # 한 단계만 다운그레이드
flask db downgrade <revision> # 특정 버전으로 다운그레이드
```

### 정보 확인
```bash
flask db current              # 현재 마이그레이션 버전
flask db history              # 마이그레이션 히스토리
flask db show <revision>      # 특정 마이그레이션 상세 정보
```

### 초기화 (주의!)
```bash
./init_migration.sh --reset   # migrations 폴더 삭제 후 재초기화
```
⚠️ **경고**: 이 명령어는 모든 마이그레이션 히스토리를 삭제합니다!

## 🔧 트러블슈팅

### 문제 1: "Target database is not up to date"

**원인**: 다른 개발자가 만든 마이그레이션이 로컬 DB에 적용되지 않음

**해결**:
```bash
git pull                      # 최신 migrations 가져오기
flask db upgrade              # 마이그레이션 적용
```

### 문제 2: "Can't locate revision identified by 'xxxx'"

**원인**: migrations 폴더와 데이터베이스의 버전 불일치

**해결**:
```bash
# 방법 1: 데이터베이스의 alembic_version 테이블 확인 및 수정
# 방법 2: 개발 환경이면 DB 재생성
flask db stamp head           # 현재 migrations를 최신으로 표시
```

### 문제 3: 자동 감지 실패

**원인**: Alembic이 일부 변경사항을 자동으로 감지하지 못함

**해결**:
```bash
# 마이그레이션 파일을 생성한 후 수동으로 편집
flask db migrate -m "Manual migration"
# migrations/versions/xxxx_manual_migration.py 파일을 열어서 수동으로 수정
```

### 문제 4: Pod 시작 시 마이그레이션 실패

**증상**: Pod가 CrashLoopBackOff 상태

**확인**:
```bash
kubectl logs <pod-name> | grep -A 10 "database migration"
```

**해결**:
1. 마이그레이션 파일 검토
2. 로컬에서 테스트 후 재배포
3. 필요시 수동으로 마이그레이션 적용 후 Pod 재시작

## 📝 모범 사례

### ✅ DO (해야 할 것)
- 모든 모델 변경 후 마이그레이션 생성
- 마이그레이션 파일을 반드시 검토
- 로컬에서 테스트 후 커밋
- 의미있는 마이그레이션 메시지 작성
- migrations 폴더를 Git에 커밋

### ❌ DON'T (하지 말아야 할 것)
- 프로덕션 DB에서 직접 ALTER TABLE 실행
- 마이그레이션 파일 검토 없이 배포
- 이미 배포된 마이그레이션 파일 수정
- migrations 폴더를 .gitignore에 추가
- db.create_all() 또는 db.drop_all() 사용 (개발 초기 제외)

## 🚀 첫 배포 시나리오

### 기존 데이터베이스가 없는 경우 (신규 프로젝트)

1. **로컬에서 초기 마이그레이션 생성**:
```bash
./init_migration.sh "Initial migration"
```

2. **Git 커밋**:
```bash
git add migrations/
git commit -m "Add initial migration"
git push
```

3. **Docker 빌드 및 배포**:
```bash
docker build -t your-registry/weather-backend:latest .
docker push your-registry/weather-backend:latest
kubectl apply -f k8s/deployment.yaml
```

4. **Pod가 자동으로 처리**:
   - migrations 초기화
   - 초기 마이그레이션 생성
   - 테이블 생성

### 기존 데이터베이스가 있는 경우 (마이그레이션 시스템 도입)

1. **현재 스키마를 베이스라인으로 설정**:
```bash
# 로컬에서
./init_migration.sh "Baseline migration from existing schema"
```

2. **프로덕션 DB에 베이스라인 스탬프**:
```bash
# Pod 내부에서 또는 kubectl exec로
flask db stamp head
```

3. **이후 변경사항은 일반 워크플로우 따름**

## 📚 참고 자료

- [Flask-Migrate 공식 문서](https://flask-migrate.readthedocs.io/)
- [Alembic 공식 문서](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 타입 참조](https://docs.sqlalchemy.org/en/20/core/type_basics.html)

## 🆘 긴급 상황 대응

### 마이그레이션 실패로 Pod가 시작 안 될 때

1. **즉시 이전 버전으로 롤백**:
```bash
kubectl rollout undo deployment/weather-backend
```

2. **원인 파악**:
```bash
kubectl logs <failed-pod-name>
```

3. **수정 후 재배포**:
- 마이그레이션 파일 수정
- 로컬 테스트
- 재배포

### 데이터 손실 위험이 있을 때

⚠️ **절대 하지 마세요**: `db.drop_all()`, `DROP TABLE`, `TRUNCATE`

대신:
1. 데이터베이스 백업
2. 마이그레이션 파일 철저히 검토
3. 스테이징 환경에서 먼저 테스트
4. 프로덕션 배포

---

**작성일**: 2025-11-06
**버전**: 1.0
**담당자**: Backend Team
