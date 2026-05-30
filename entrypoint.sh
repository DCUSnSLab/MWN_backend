#!/bin/bash
# Kubernetes Pod Entrypoint Script for Weather Notification Backend
# 날씨 알림 백엔드 서비스를 위한 Kubernetes Pod 진입점 스크립트

set -e  # 오류 발생 시 스크립트 중단

# Firebase 서비스 계정 키 경로 설정
export FIREBASE_SERVICE_ACCOUNT_KEY=/app/instance/serviceAccountKey.json

echo "🚀 Starting Weather Notification Backend initialization..."

# 환경 변수 확인
echo "📋 Environment variables check:"
echo "  - DATABASE_URL: ${DATABASE_URL:-'Not set (will use default PostgreSQL)'}"
echo "  - KMA_SERVICE_KEY: ${KMA_SERVICE_KEY:-'Not set'}"
echo "  - FIREBASE_SERVICE_ACCOUNT_KEY: ${FIREBASE_SERVICE_ACCOUNT_KEY}"
echo "  - FLASK_ENV: ${FLASK_ENV:-'production'}"

# 데이터베이스 연결 대기 (PostgreSQL)
echo "🔌 Waiting for database connection..."
python -c "
import os
import time
import psycopg2
from urllib.parse import urlparse

def wait_for_db():
    db_url = os.environ.get('DATABASE_URL', 'postgresql://myuser:mypassword@localhost:5432/weather_notification')
    parsed = urlparse(db_url)
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:]  # Remove leading '/'
            )
            conn.close()
            print('✅ Database connection successful!')
            return True
        except Exception as e:
            retry_count += 1
            print(f'⏳ Database connection attempt {retry_count}/{max_retries} failed: {e}')
            time.sleep(2)
    
    print('❌ Failed to connect to database after maximum retries')
    return False

if not wait_for_db():
    exit(1)
"

# 데이터베이스 마이그레이션 (Flask-Migrate)
# migrations/ 는 이미지에 포함되어 배포된다. baseline(81fe5d2b22d6) 이후의
# 리비전을 flask db upgrade 가 순서대로 적용한다.
echo "🗃️ Applying database migrations..."
export FLASK_APP=app.py

# init 단계에서 app 을 import 하는 짧은 python -c 블록들이 ephemeral APScheduler 를
# 띄우지 않도록 한다(app.py 의 스케줄러 기동 게이트가 WERKZEUG_RUN_MAIN!='true' && !=None
# 일 때 false 로 평가됨). gunicorn 으로 넘어가기 전에 unset 한다.
export WERKZEUG_RUN_MAIN=false

# 이 스크립트는 /bin/sh(dash)로 실행되므로 bash 전용 구문(PIPESTATUS 등)을 쓰지 않는다.
# set -e 상태에서 upgrade 의 비정상 종료가 스크립트를 즉시 죽이지 않도록 분리 처리.
# 파이프를 쓰면 $? 가 마지막 명령(tee)의 코드가 되므로, 리다이렉트만 써서 flask 의 코드를 본다.
set +e
flask db upgrade > /tmp/upgrade_output.log 2>&1
UPGRADE_RC=$?
set -e
cat /tmp/upgrade_output.log

if [ "$UPGRADE_RC" -ne 0 ]; then
    if grep -q "Can't locate revision" /tmp/upgrade_output.log; then
        # baseline 도입 이전 운영 DB 에 남은 orphan 리비전(전환 1회성).
        # orphan 이 있으면 stamp 조차 현재 위치를 해석하지 못하므로, 스키마가 baseline 과
        # 일치함(검증 완료)을 근거로 alembic_version 을 head 로 직접 교정한 뒤 재적용한다.
        HEAD_REV=$(flask db heads 2>/dev/null | awk 'NR==1{print $1}')
        echo "  ⚠️  orphan 리비전 감지 → alembic_version 을 head($HEAD_REV)로 교정"
        python - "$HEAD_REV" <<'PYEOF'
import sys
from app import app, db
from sqlalchemy import text
head = sys.argv[1]
with app.app_context():
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})
print(f"  ✅ alembic_version → {head} 교정 완료")
PYEOF
        flask db upgrade
        echo "  ✅ 마이그레이션 전환 동기화 완료!"
    else
        echo "  ❌ 마이그레이션 적용 실패"
        cat /tmp/upgrade_output.log
        exit 1
    fi
else
    echo "  ✅ 데이터베이스 마이그레이션 완료!"
fi

# 관리자 계정 생성
echo "👤 Creating admin account..."
if [ -z "${ADMIN_PASSWORD}" ]; then
    echo "  ❌ ADMIN_PASSWORD environment variable is required (set it in the Pod spec / Secret)."
    exit 1
fi
export ADMIN_EMAIL="${ADMIN_EMAIL:-snslab@gmail.com}"
export ADMIN_NAME="${ADMIN_NAME:-시스템 관리자}"
python -c "
import os
from app import app, db
from models import User

with app.app_context():
    try:
        admin_email = os.environ['ADMIN_EMAIL']
        admin_password = os.environ['ADMIN_PASSWORD']
        admin_name = os.environ['ADMIN_NAME']
        
        # 기존 관리자 계정 확인
        existing_admin = User.query.filter_by(email=admin_email).first()
        
        if existing_admin:
            print(f'  ✅ Admin account already exists: {admin_email}')
            if not existing_admin.is_admin():
                existing_admin.make_admin()
                db.session.commit()
                print('  🔄 Upgraded existing user to admin')
        else:
            print(f'  📝 Creating new admin account: {admin_email}')
            admin_user = User.create_admin(
                name=admin_name,
                email=admin_email,
                password=admin_password,
                location='시스템 관리자'
            )
            
            db.session.add(admin_user)
            db.session.commit()
            print(f'  ✅ Admin account created successfully!')
            
    except Exception as e:
        print(f'  ❌ Failed to create admin account: {e}')
        exit(1)
"

# 시장 데이터 존재 여부 확인 및 초기 데이터 로드
echo "📊 Checking market data..."
python -c "
import os
from app import app, db
from models import Market
import pandas as pd

with app.app_context():
    try:
        market_count = Market.query.count()
        print(f'📈 Current market count in database: {market_count}')
        
        if market_count == 0:
            print('📥 No market data found. Loading from Excel file...')
            
            # 엑셀 파일 경로 확인
            excel_path = 'data/market_info.xlsm'
            if not os.path.exists(excel_path):
                print(f'⚠️ Excel file not found: {excel_path}')
                print('   Skipping market data import...')
            else:
                # 엑셀 데이터 로드
                df = pd.read_excel(excel_path)
                print(f'📄 Found {len(df)} markets in Excel file')
                
                # 컬럼명 매핑
                column_mapping = {
                    '시장/상점가명': 'name',
                    '위도': 'latitude', 
                    '경도': 'longitude',
                    'nx': 'nx',
                    'ny': 'ny'
                }
                
                # 데이터베이스에 저장
                success_count = 0
                for index, row in df.iterrows():
                    try:
                        market = Market(
                            name=str(row['시장/상점가명']).strip(),
                            location=str(row['시장/상점가명']).strip(),  # location을 name과 동일하게 설정
                            latitude=float(row['위도']) if pd.notna(row['위도']) else None,
                            longitude=float(row['경도']) if pd.notna(row['경도']) else None,
                            nx=int(row['nx']) if pd.notna(row['nx']) else None,
                            ny=int(row['ny']) if pd.notna(row['ny']) else None,
                            category='전통시장'  # 기본 카테고리 설정
                        )
                        
                        db.session.add(market)
                        success_count += 1
                        
                        # 100개마다 중간 커밋
                        if success_count % 100 == 0:
                            db.session.commit()
                            print(f'  💾 Saved {success_count} markets...')
                            
                    except Exception as e:
                        print(f'  ⚠️ Failed to save market {index + 1}: {e}')
                        continue
                
                # 최종 커밋
                db.session.commit()
                print(f'✅ Successfully imported {success_count} markets to database!')
        else:
            print('✅ Market data already exists in database.')
            
    except Exception as e:
        print(f'❌ Error during market data initialization: {e}')
        exit(1)
"

# 관리자 계정에 모든 시장 관심 등록
echo "⭐ Registering all markets as admin's watchlist..."
python -c "
from app import app, db
from models import User, Market, UserMarketInterest

with app.app_context():
    try:
        admin_email = 'snslab@gmail.com'

        # 관리자 계정 조회
        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            print('  ⚠️ Admin account not found. Skipping watchlist setup.')
        else:
            # 모든 활성 시장 조회
            all_markets = Market.query.filter_by(is_active=True).all()

            if not all_markets:
                print('  ⚠️ No markets found in database. Skipping watchlist setup.')
            else:
                print(f'  📊 Found {len(all_markets)} markets')

                # 기존 관심시장 조회
                existing_interests = UserMarketInterest.query.filter_by(
                    user_id=admin_user.id
                ).all()
                existing_market_ids = {interest.market_id for interest in existing_interests}

                print(f'  📋 Admin already has {len(existing_market_ids)} markets in watchlist')

                # 새로 추가할 시장 필터링
                new_count = 0
                for market in all_markets:
                    if market.id not in existing_market_ids:
                        interest = UserMarketInterest(
                            user_id=admin_user.id,
                            market_id=market.id,
                            is_active=True,
                            notification_enabled=True
                        )
                        db.session.add(interest)
                        new_count += 1

                        # 100개마다 중간 커밋
                        if new_count % 100 == 0:
                            db.session.commit()
                            print(f'  💾 Registered {new_count} new markets...')

                # 최종 커밋
                db.session.commit()

                total_interests = len(existing_market_ids) + new_count
                print(f'  ✅ Admin watchlist setup complete!')
                print(f'     - New markets added: {new_count}')
                print(f'     - Total markets in watchlist: {total_interests}')

    except Exception as e:
        print(f'  ❌ Failed to setup admin watchlist: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
"

# 앱 import 스모크 테스트 — gunicorn 부팅 전 import 오류 조기 감지.
# (k8s startupProbe 가 /health 로 본격 readiness 를 대체하므로 Werkzeug 개발서버를 띄우지 않는다.)
echo "🏥 Running app import smoke test..."
python -c "from app import app; print('✅ App import smoke OK')"

echo "🎉 Initialization completed successfully!"
echo ""
echo "📋 Summary:"
echo "  - Database connection: ✅"
echo "  - Database tables: ✅"
echo "  - Admin account: ✅"
echo "  - Market data: ✅"
echo "  - Admin watchlist: ✅"
echo "  - Health check: ✅"
echo ""

# 스케줄러 상태 확인 메시지
echo "⏰ Weather scheduler will auto-start with Flask application"
echo "   - Weather data collection: Every hour at :15 and :45"
echo "   - Weather alerts (rain/heat/cold/wind): Every hour at :00"
echo ""

echo "🚀 Starting Flask application with weather scheduler..."

# gunicorn 워커가 정상적으로 스케줄러를 띄울 수 있도록 init 가드 해제.
unset WERKZEUG_RUN_MAIN

# Flask 애플리케이션 시작 (gunicorn — 프로덕션 WSGI 서버)
# 워커를 1개로 고정한다: APScheduler 가 워커 프로세스 안에서 돌기 때문에
# 워커가 N개면 날씨 수집/알림/FCM 이 N번 중복 실행된다.
# I/O 바운드(외부 API 호출)이므로 동시성은 스레드로 확보한다.
exec gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT:-80} app:app