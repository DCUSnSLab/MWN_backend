#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 스키마 마이그레이션 스크립트 (PostgreSQL/SQLite 호환)

이 스크립트는 다음 기능을 수행합니다:
- Market 테이블에 nx, ny 필드 추가
- User 테이블에 role 필드 추가
- UserMarketInterest 테이블 생성
"""

import os
import sys
import psycopg2
from datetime import datetime
from app import app, db
from models import User, Market, UserMarketInterest, DamageStatus, Weather

def get_database_info():
    """현재 데이터베이스 정보 확인"""
    database_url = os.environ.get('DATABASE_URL', 'postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification')
    
    if database_url.startswith('postgresql'):
        return 'postgresql', database_url
    else:
        return 'sqlite', database_url

def backup_postgresql_database(db_url):
    """PostgreSQL 데이터베이스 백업"""
    try:
        # psql이나 pg_dump를 사용한 백업은 복잡하므로 건너뜀
        print("PostgreSQL 백업은 별도의 pg_dump 명령을 사용하세요.")
        print(f"예: pg_dump {db_url} > backup_$(date +%Y%m%d_%H%M%S).sql")
        return True
    except Exception as e:
        print(f"백업 설정 중 오류: {e}")
        return False

def check_postgresql_column_exists(conn, table_name, column_name):
    """PostgreSQL에서 컬럼 존재 여부 확인"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        print(f"컬럼 확인 중 오류: {e}")
        return False
    finally:
        cursor.close()

def check_postgresql_table_exists(conn, table_name):
    """PostgreSQL에서 테이블 존재 여부 확인"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = %s
        """, (table_name,))
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        print(f"테이블 확인 중 오류: {e}")
        return False
    finally:
        cursor.close()

def migrate_postgresql_database(db_url):
    """PostgreSQL 데이터베이스 마이그레이션"""
    print("PostgreSQL 데이터베이스 마이그레이션 시작...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cursor = conn.cursor()
        
        print("현재 데이터베이스 테이블 확인...")
        
        # 1. Markets 테이블에 nx, ny 필드 추가
        print("\n1. Markets 테이블 nx, ny 필드 확인...")
        for field_name, field_type in [('nx', 'INTEGER'), ('ny', 'INTEGER')]:
            if not check_postgresql_column_exists(conn, 'markets', field_name):
                print(f"  - {field_name} 필드 추가 중...")
                cursor.execute(f"ALTER TABLE markets ADD COLUMN {field_name} {field_type}")
                print(f"  ✅ {field_name} 필드 추가됨")
            else:
                print(f"  ℹ️ {field_name} 필드 이미 존재")
        
        # 2. Users 테이블에 role 필드 추가
        print("\n2. Users 테이블 role 필드 확인...")
        if not check_postgresql_column_exists(conn, 'users', 'role'):
            print("  - role 필드 추가 중...")
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
            print("  ✅ role 필드 추가됨")
        else:
            print("  ℹ️ role 필드 이미 존재")
        
        # 3. UserMarketInterest 테이블 생성
        print("\n3. UserMarketInterest 테이블 확인...")
        if not check_postgresql_table_exists(conn, 'user_market_interests'):
            print("  - UserMarketInterest 테이블 생성 중...")
            cursor.execute("""
                CREATE TABLE user_market_interests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    market_id INTEGER NOT NULL REFERENCES markets(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    notification_enabled BOOLEAN DEFAULT TRUE,
                    UNIQUE(user_id, market_id)
                )
            """)
            print("  ✅ UserMarketInterest 테이블 생성됨")
        else:
            print("  ℹ️ UserMarketInterest 테이블 이미 존재")
        
        # 변경사항 커밋
        conn.commit()
        
        # 마이그레이션 결과 확인
        print("\n마이그레이션 결과 확인:")
        
        # Markets 테이블 구조 확인
        cursor.execute("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'markets' 
            ORDER BY ordinal_position
        """)
        markets_columns = cursor.fetchall()
        print("Markets 테이블 구조:")
        for col in markets_columns:
            print(f"  - {col[0]}: {col[1]} (default: {col[2]})")
        
        # Users 테이블의 role 필드 확인
        cursor.execute("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'role'
        """)
        role_column = cursor.fetchone()
        if role_column:
            print(f"\nUsers 테이블 role 필드: {role_column[0]} ({role_column[1]}, default: {role_column[2]})")
        
        # UserMarketInterest 테이블 확인
        if check_postgresql_table_exists(conn, 'user_market_interests'):
            print("\nUserMarketInterest 테이블: ✅ 존재")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"PostgreSQL 마이그레이션 중 오류: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def migrate_with_sqlalchemy():
    """SQLAlchemy ORM을 사용한 마이그레이션 (더 안전한 방법)"""
    print("\nSQLAlchemy ORM을 사용한 테이블 생성/업데이트...")
    
    with app.app_context():
        try:
            # 모든 모델 import 확인
            print("모델 로드 확인...")
            print(f"  - User: {User}")
            print(f"  - Market: {Market}")
            print(f"  - UserMarketInterest: {UserMarketInterest}")
            print(f"  - DamageStatus: {DamageStatus}")
            print(f"  - Weather: {Weather}")
            
            # 테이블 생성 (이미 있으면 무시됨)
            db.create_all()
            print("✅ SQLAlchemy를 통한 테이블 생성/업데이트 완료")
            
            return True
            
        except Exception as e:
            print(f"SQLAlchemy 마이그레이션 중 오류: {e}")
            return False

def verify_migration():
    """마이그레이션 결과 검증"""
    print("\n마이그레이션 검증 중...")
    
    with app.app_context():
        try:
            # 각 테이블의 레코드 수 확인
            user_count = User.query.count()
            market_count = Market.query.count()
            weather_count = Weather.query.count()
            damage_count = DamageStatus.query.count()
            interest_count = UserMarketInterest.query.count()
            
            print("데이터베이스 현황:")
            print(f"  - Users: {user_count}개")
            print(f"  - Markets: {market_count}개")
            print(f"  - Weather: {weather_count}개")
            print(f"  - DamageStatus: {damage_count}개")
            print(f"  - UserMarketInterest: {interest_count}개")
            
            # 샘플 데이터 확인
            if market_count > 0:
                sample_market = Market.query.first()
                print(f"\n샘플 시장 데이터:")
                print(f"  - 이름: {sample_market.name}")
                print(f"  - 좌표: ({sample_market.latitude}, {sample_market.longitude})")
                print(f"  - 격자: ({sample_market.nx}, {sample_market.ny})")
            
            if user_count > 0:
                sample_user = User.query.first()
                print(f"\n샘플 사용자 데이터:")
                print(f"  - 이름: {sample_user.name}")
                print(f"  - 권한: {sample_user.role}")
            
            return True
            
        except Exception as e:
            print(f"검증 중 오류: {e}")
            return False

def main():
    """메인 함수"""
    print("=" * 60)
    print("데이터베이스 스키마 마이그레이션 스크립트")
    print("=" * 60)
    
    # 데이터베이스 타입 확인
    db_type, db_url = get_database_info()
    print(f"데이터베이스 타입: {db_type}")
    print(f"연결 URL: {db_url}")
    
    success = False
    
    if db_type == 'postgresql':
        # PostgreSQL용 백업 안내
        backup_postgresql_database(db_url)
        
        # PostgreSQL 직접 마이그레이션
        if migrate_postgresql_database(db_url):
            print("✅ PostgreSQL 직접 마이그레이션 완료")
            success = True
        else:
            print("❌ PostgreSQL 직접 마이그레이션 실패")
    
    # SQLAlchemy ORM을 사용한 안전한 마이그레이션 (PostgreSQL, SQLite 모두 지원)
    if migrate_with_sqlalchemy():
        print("✅ SQLAlchemy ORM 마이그레이션 완료")
        success = True
    else:
        print("❌ SQLAlchemy ORM 마이그레이션 실패")
        if not success:
            return 1
    
    # 마이그레이션 검증
    if verify_migration():
        print("\n🎉 모든 마이그레이션이 성공적으로 완료되었습니다!")
        
        print("\n다음 단계:")
        print("1. 엑셀 데이터 임포트: python data/import_market_data.py")
        print("2. 관리자 계정 생성: 서버 시작 시 자동 생성됨")
        print("3. Flask 서버 시작: python app.py")
        
        return 0
    else:
        print("\n❌ 마이그레이션 검증에 실패했습니다.")
        return 1

if __name__ == "__main__":
    # 필요한 패키지 확인
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 패키지가 설치되지 않았습니다.")
        print("다음 명령어로 설치하세요: pip install psycopg2-binary")
        sys.exit(1)
    
    sys.exit(main())