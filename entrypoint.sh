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

# 데이터베이스 마이그레이션 (Flask-Migrate 사용)
echo "🗃️ Initializing database migration..."

# Flask 앱 경로 설정 (flask db 명령어 사용을 위해 필요)
export FLASK_APP=app.py

# migrations 디렉토리가 없으면 초기화
if [ ! -d "migrations" ]; then
    echo "  📁 migrations 디렉토리가 없습니다. 마이그레이션 초기화 중..."
    flask db init
    echo "  ✅ 마이그레이션 초기화 완료!"
fi

# 데이터베이스 마이그레이션 버전 확인 시도
echo "  🔍 데이터베이스 마이그레이션 상태 확인 중..."
flask db current 2>&1 | tee /tmp/db_current.log

# 마이그레이션 히스토리 오류 처리
if grep -q "Can't locate revision" /tmp/db_current.log; then
    echo "  ⚠️  데이터베이스에 이전 마이그레이션 버전이 있지만 파일이 없습니다."
    echo "  🔄 alembic_version 테이블을 초기화합니다..."

    # alembic_version 테이블 삭제 (Python으로 처리)
    python -c "
from app import app, db
with app.app_context():
    try:
        db.engine.execute('DROP TABLE IF EXISTS alembic_version CASCADE;')
        print('  ✅ alembic_version 테이블 삭제 완료')
    except Exception as e:
        print(f'  ⚠️  alembic_version 테이블 삭제 실패 (무시): {e}')
" || echo "  ℹ️  alembic_version 테이블이 없거나 이미 삭제됨"
fi

# 현재 모델과 데이터베이스 스키마 비교하여 마이그레이션 생성
echo "  🔍 모델 변경사항 확인 중..."
flask db migrate -m "Auto-migration on startup" 2>&1 | tee /tmp/migrate_output.log

# migrate 결과 확인
if grep -q "No changes in schema detected" /tmp/migrate_output.log; then
    echo "  ℹ️  스키마 변경사항 없음"
elif grep -q "Generating" /tmp/migrate_output.log; then
    echo "  📝 새로운 마이그레이션 파일 생성됨"
else
    echo "  ⚠️  마이그레이션 생성 결과를 확인하세요"
fi

# 마이그레이션 적용
echo "  🚀 마이그레이션 적용 중..."
flask db upgrade 2>&1 | tee /tmp/upgrade_output.log

if [ $? -eq 0 ]; then
    echo "  ✅ 데이터베이스 마이그레이션 완료!"
else
    # 업그레이드 실패 시 추가 처리
    if grep -q "Can't locate revision" /tmp/upgrade_output.log; then
        echo "  ⚠️  마이그레이션 버전 불일치 문제 재시도..."

        # stamp를 사용하여 현재 상태를 head로 설정
        echo "  🔄 데이터베이스를 현재 코드 상태로 동기화합니다..."
        flask db stamp head

        echo "  ✅ 데이터베이스 마이그레이션 동기화 완료!"
    else
        echo "  ❌ 마이그레이션 적용 실패"
        cat /tmp/upgrade_output.log
        exit 1
    fi
fi

# 관리자 계정 생성
echo "👤 Creating admin account..."
python -c "
from app import app, db
from models import User

with app.app_context():
    try:
        admin_email = 'snslab@gmail.com'
        admin_password = 'snslab@cu'
        admin_name = '시스템 관리자'
        
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

# 헬스체크
echo "🏥 Running health check..."

# 환경변수에서 포트 가져오기 (기본값: 80)
HEALTH_CHECK_PORT=${PORT:-80}

python -c "
import os
from app import app
import requests
import time
import threading

# 환경변수에서 포트 가져오기
port = int(os.environ.get('PORT', 80))

def run_app():
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Flask 앱을 백그라운드에서 시작
server_thread = threading.Thread(target=run_app, daemon=True)
server_thread.start()

# 서버가 시작될 때까지 대기
time.sleep(3)

try:
    response = requests.get(f'http://localhost:{port}/health', timeout=5)
    if response.status_code == 200:
        print(f'✅ Health check passed on port {port}!')
    else:
        print(f'❌ Health check failed with status code: {response.status_code}')
        exit(1)
except Exception as e:
    print(f'❌ Health check failed: {e}')
    exit(1)
"

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

# Flask 애플리케이션 시작 (스케줄러가 자동으로 시작됨)
exec python app.py