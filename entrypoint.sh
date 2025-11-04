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

# 데이터베이스 테이블 생성 (Flask-SQLAlchemy 사용)
echo "🗃️ Initializing database tables..."
python -c "
from app import app, db
from models import User, Market, DamageStatus, Weather

with app.app_context():
    try:
        # Import all models to ensure they are registered
        from models import User, Market, DamageStatus, Weather, UserMarketInterest
        db.create_all()
        print('✅ Database tables created successfully!')
    except Exception as e:
        print(f'❌ Failed to create database tables: {e}')
        exit(1)
"

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

# Firebase 서비스 계정 키 파일 확인
echo "🔥 Checking Firebase configuration..."
if [ -n "${FIREBASE_SERVICE_ACCOUNT_KEY}" ]; then
    echo "  📝 Writing Firebase service account key to file..."
    echo "${FIREBASE_SERVICE_ACCOUNT_KEY}" > /app/fcm_integration/serviceAccountKey.json
    echo "  ✅ Firebase service account key configured!"
elif [ -f "fcm_integration/serviceAccountKey.json" ]; then
    echo "  ✅ Firebase service account key file already exists!"
else
    echo "  ⚠️ Firebase service account key not configured. FCM features may not work."
fi

# 헬스체크
echo "🏥 Running health check..."
python -c "
from app import app
import requests
import time
import threading

def run_app():
    app.run(host='0.0.0.0', port=8002, debug=False, use_reloader=False)

# Flask 앱을 백그라운드에서 시작
server_thread = threading.Thread(target=run_app, daemon=True)
server_thread.start()

# 서버가 시작될 때까지 대기
time.sleep(3)

try:
    response = requests.get('http://localhost:8002/health', timeout=5)
    if response.status_code == 200:
        print('✅ Health check passed!')
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
echo "  - Health check: ✅"
echo ""

# 스케줄러 상태 확인 메시지
echo "⏰ Weather scheduler will auto-start with Flask application"
echo "   - Weather data collection: Every hour at :15 and :45"
echo "   - Rain forecast alerts: Every hour at :00"
echo ""

echo "🚀 Starting Flask application with weather scheduler..."

# Flask 애플리케이션 시작 (스케줄러가 자동으로 시작됨)
exec python app.py