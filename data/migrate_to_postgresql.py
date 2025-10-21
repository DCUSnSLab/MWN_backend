#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SQLite에서 PostgreSQL로 데이터 마이그레이션 스크립트

기존 SQLite 데이터베이스의 모든 데이터를 PostgreSQL로 이전합니다.
"""

import sqlite3
import psycopg2
import sys
import os
from datetime import datetime
import json

def connect_sqlite():
    """SQLite 데이터베이스 연결"""
    sqlite_path = 'instance/weather_notification.db'
    if not os.path.exists(sqlite_path):
        print(f"SQLite 데이터베이스를 찾을 수 없습니다: {sqlite_path}")
        return None
    
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        print(f"SQLite 연결 성공: {sqlite_path}")
        return conn
    except Exception as e:
        print(f"SQLite 연결 실패: {e}")
        return None

def connect_postgresql():
    """PostgreSQL 데이터베이스 연결"""
    try:
        # 환경변수에서 DATABASE_URL 가져오기
        db_url = os.environ.get('DATABASE_URL', 'postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification')
        
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        print(f"PostgreSQL 연결 성공: {db_url}")
        return conn
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        print("PostgreSQL 서버가 실행 중인지 확인하고, 데이터베이스가 생성되었는지 확인하세요.")
        return None

def create_postgresql_tables(pg_conn):
    """PostgreSQL에 테이블 생성"""
    cursor = pg_conn.cursor()
    
    try:
        print("PostgreSQL 테이블 생성 중...")
        
        # Users 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                location VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                notification_preferences JSONB,
                email_verified BOOLEAN DEFAULT FALSE,
                last_login TIMESTAMP,
                fcm_token TEXT,
                fcm_enabled BOOLEAN DEFAULT TRUE,
                fcm_topics JSONB,
                device_info JSONB
            )
        """)
        
        # Markets 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                location VARCHAR(300) NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                nx INTEGER,
                ny INTEGER,
                category VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Weather 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                id SERIAL PRIMARY KEY,
                base_date VARCHAR(8) NOT NULL,
                base_time VARCHAR(4) NOT NULL,
                fcst_date VARCHAR(8),
                fcst_time VARCHAR(4),
                nx INTEGER NOT NULL,
                ny INTEGER NOT NULL,
                temp DOUBLE PRECISION,
                humidity DOUBLE PRECISION,
                rain_1h DOUBLE PRECISION,
                east_west_wind DOUBLE PRECISION,
                north_south_wind DOUBLE PRECISION,
                wind_direction DOUBLE PRECISION,
                wind_speed DOUBLE PRECISION,
                pop DOUBLE PRECISION,
                pty VARCHAR(10),
                sky VARCHAR(10),
                lightning VARCHAR(10),
                api_type VARCHAR(20) NOT NULL,
                location_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Damage Statuses 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS damage_statuses (
                id SERIAL PRIMARY KEY,
                market_id INTEGER REFERENCES markets(id),
                weather_event VARCHAR(100) NOT NULL,
                damage_level VARCHAR(50) NOT NULL,
                description TEXT,
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                estimated_recovery_time TIMESTAMP,
                is_resolved BOOLEAN DEFAULT FALSE,
                resolved_at TIMESTAMP
            )
        """)
        
        pg_conn.commit()
        print("PostgreSQL 테이블 생성 완료")
        return True
        
    except Exception as e:
        print(f"PostgreSQL 테이블 생성 실패: {e}")
        pg_conn.rollback()
        return False
    finally:
        cursor.close()

def migrate_table_data(sqlite_conn, pg_conn, table_name, columns):
    """특정 테이블의 데이터 마이그레이션"""
    print(f"\n{table_name} 테이블 마이그레이션 중...")
    
    # SQLite에서 데이터 읽기 - 컬럼 순서 보장을 위해 명시적으로 컬럼명 지정
    sqlite_cursor = sqlite_conn.cursor()
    column_list = ', '.join(columns)
    sqlite_cursor.execute(f"SELECT {column_list} FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"  - {table_name}: 데이터 없음")
        return True
    
    print(f"  - {table_name}: {len(rows)}개 행 발견")
    
    # PostgreSQL에 데이터 삽입
    pg_cursor = pg_conn.cursor()
    
    try:
        # 기존 데이터 확인 및 삭제
        pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing_count = pg_cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"  - {table_name}: 기존 {existing_count}개 행 삭제 중...")
            pg_cursor.execute(f"DELETE FROM {table_name}")
        
        # 새 데이터 삽입
        success_count = 0
        for row in rows:
            try:
                # 데이터 타입 변환 처리
                row_data = []
                for i, col in enumerate(columns):
                    value = row[i] if i < len(row) else None
                    
                    # Boolean 필드 처리 (SQLite의 0,1을 PostgreSQL boolean으로 변환)
                    if col in ['is_active', 'email_verified', 'fcm_enabled', 'is_resolved'] and value is not None:
                        value = bool(value)
                    
                    # JSON 필드 처리 (notification_preferences, fcm_topics, device_info)
                    elif col in ['notification_preferences', 'fcm_topics', 'device_info'] and value:
                        if isinstance(value, str):
                            try:
                                value = json.loads(value)
                            except:
                                value = None
                    
                    # 빈 문자열을 NULL로 변환 (특정 필드들)
                    elif col in ['phone', 'location', 'category', 'description'] and value == '':
                        value = None
                    
                    row_data.append(value)
                
                # ID를 제외한 컬럼들로 INSERT
                insert_columns = [col for col in columns if col != 'id']
                insert_values = [row_data[i] for i, col in enumerate(columns) if col != 'id']
                
                placeholders = ', '.join(['%s'] * len(insert_values))
                insert_query = f"""
                    INSERT INTO {table_name} ({', '.join(insert_columns)}) 
                    VALUES ({placeholders})
                """
                
                pg_cursor.execute(insert_query, insert_values)
                success_count += 1
                
            except Exception as e:
                print(f"  - 행 삽입 실패 (행 {success_count + 1}): {e}")
                # 디버깅을 위해 실패한 데이터 출력
                if success_count < 3:  # 처음 3개 실패만 상세 출력
                    print(f"    실패한 데이터: {row_data[:5]}...")  # 처음 5개 컬럼만 출력
                continue
        
        pg_conn.commit()
        print(f"  - {table_name}: {success_count}개 행 성공적으로 마이그레이션")
        return True
        
    except Exception as e:
        print(f"  - {table_name} 마이그레이션 실패: {e}")
        pg_conn.rollback()
        return False
    finally:
        pg_cursor.close()

def migrate_all_data(sqlite_conn, pg_conn):
    """모든 테이블 데이터 마이그레이션"""
    print("\n데이터 마이그레이션 시작...")
    
    # 테이블별 컬럼 정의
    tables = {
        'users': [
            'id', 'name', 'email', 'password_hash', 'phone', 'location',
            'created_at', 'updated_at', 'is_active', 'notification_preferences',
            'email_verified', 'last_login', 'fcm_token', 'fcm_enabled',
            'fcm_topics', 'device_info'
        ],
        'markets': [
            'id', 'name', 'location', 'latitude', 'longitude', 'nx', 'ny',
            'category', 'created_at', 'updated_at', 'is_active'
        ],
        'weather': [
            'id', 'base_date', 'base_time', 'fcst_date', 'fcst_time', 'nx', 'ny',
            'temp', 'humidity', 'rain_1h', 'east_west_wind', 'north_south_wind',
            'wind_direction', 'wind_speed', 'pop', 'pty', 'sky', 'lightning',
            'api_type', 'location_name', 'created_at'
        ],
        'damage_statuses': [
            'id', 'market_id', 'weather_event', 'damage_level', 'description',
            'reported_at', 'estimated_recovery_time', 'is_resolved', 'resolved_at'
        ]
    }
    
    success_tables = []
    failed_tables = []
    
    for table_name, columns in tables.items():
        try:
            if migrate_table_data(sqlite_conn, pg_conn, table_name, columns):
                success_tables.append(table_name)
            else:
                failed_tables.append(table_name)
        except Exception as e:
            print(f"{table_name} 테이블 마이그레이션 오류: {e}")
            failed_tables.append(table_name)
    
    print(f"\n마이그레이션 완료:")
    print(f"성공: {len(success_tables)}개 테이블 - {success_tables}")
    if failed_tables:
        print(f"실패: {len(failed_tables)}개 테이블 - {failed_tables}")
    
    return len(failed_tables) == 0

def verify_migration(pg_conn):
    """마이그레이션 결과 검증"""
    print("\n마이그레이션 결과 검증 중...")
    
    cursor = pg_conn.cursor()
    
    try:
        # 각 테이블의 행 수 확인
        tables = ['users', 'markets', 'weather', 'damage_statuses']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count}개 행")
        
        # 샘플 데이터 확인
        print("\n샘플 데이터 확인:")
        
        # Markets 테이블 샘플
        cursor.execute("SELECT name, latitude, longitude, nx, ny FROM markets LIMIT 3")
        markets = cursor.fetchall()
        for market in markets:
            print(f"  - 시장: {market[0]}, 위도: {market[1]}, 경도: {market[2]}, nx: {market[3]}, ny: {market[4]}")
        
        return True
        
    except Exception as e:
        print(f"검증 중 오류: {e}")
        return False
    finally:
        cursor.close()

def main():
    """메인 함수"""
    print("=" * 60)
    print("SQLite에서 PostgreSQL로 데이터 마이그레이션")
    print("=" * 60)
    
    # 1. SQLite 연결
    sqlite_conn = connect_sqlite()
    if not sqlite_conn:
        return 1
    
    # 2. PostgreSQL 연결
    pg_conn = connect_postgresql()
    if not pg_conn:
        sqlite_conn.close()
        return 1
    
    try:
        # 3. PostgreSQL 테이블 생성
        if not create_postgresql_tables(pg_conn):
            return 1
        
        # 4. 데이터 마이그레이션
        if not migrate_all_data(sqlite_conn, pg_conn):
            print("\n❌ 일부 테이블 마이그레이션 실패")
            return 1
        
        # 5. 결과 검증
        if not verify_migration(pg_conn):
            return 1
        
        print("\n✅ 모든 데이터가 성공적으로 PostgreSQL로 마이그레이션되었습니다!")
        print("\n다음 단계:")
        print("1. 환경변수 DATABASE_URL을 PostgreSQL로 설정")
        print("2. Flask 애플리케이션 재시작")
        print("3. 기능 테스트 수행")
        
        return 0
        
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    # 필요한 패키지 확인
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 패키지가 설치되지 않았습니다.")
        print("다음 명령어로 설치하세요: pip install psycopg2-binary")
        sys.exit(1)
    
    sys.exit(main())