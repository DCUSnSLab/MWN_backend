#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 마이그레이션 스크립트

FCM 관련 필드들을 기존 데이터베이스에 추가하고 기존 데이터를 보존합니다.
"""

import sqlite3
import os
import sys
from datetime import datetime

def backup_database():
    """데이터베이스 백업"""
    db_path = 'instance/weather_notification.db'
    backup_path = f'instance/weather_notification.db.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    if os.path.exists(db_path):
        print(f"데이터베이스 백업 중: {backup_path}")
        os.system(f'cp "{db_path}" "{backup_path}"')
        print("백업 완료")
        return True
    else:
        print("기존 데이터베이스가 없습니다.")
        return False

def check_table_exists(cursor, table_name):
    """테이블 존재 여부 확인"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def check_column_exists(cursor, table_name, column_name):
    """컬럼 존재 여부 확인"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_users_table(cursor):
    """Users 테이블에 FCM 관련 필드 추가"""
    print("Users 테이블 마이그레이션 중...")
    
    # FCM 관련 필드들 추가
    fcm_fields = [
        ('fcm_token', 'TEXT'),
        ('fcm_enabled', 'BOOLEAN DEFAULT 1'),
        ('fcm_topics', 'JSON'),
        ('device_info', 'JSON'),
        ('email_verified', 'BOOLEAN DEFAULT 0'),
        ('last_login', 'DATETIME')
    ]
    
    for field_name, field_type in fcm_fields:
        if not check_column_exists(cursor, 'users', field_name):
            print(f"  - {field_name} 필드 추가")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {field_name} {field_type}")
        else:
            print(f"  - {field_name} 필드 이미 존재")

def migrate_database():
    """전체 데이터베이스 마이그레이션"""
    db_path = 'instance/weather_notification.db'
    
    print("데이터베이스 마이그레이션 시작...")
    print(f"대상 데이터베이스: {db_path}")
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 기존 테이블들 확인
        print("\n기존 테이블 확인:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # Users 테이블 마이그레이션
        if check_table_exists(cursor, 'users'):
            migrate_users_table(cursor)
        else:
            print("Users 테이블이 존재하지 않습니다. 새로 생성됩니다.")
        
        # 변경사항 커밋
        conn.commit()
        print("\n마이그레이션 완료!")
        
        # 마이그레이션 결과 확인
        print("\n마이그레이션 결과 확인:")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("Users 테이블 구조:")
        for column in columns:
            print(f"  - {column[1]} ({column[2]})")
        
    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

def verify_migration():
    """마이그레이션 결과 검증"""
    print("\n마이그레이션 검증 중...")
    
    db_path = 'instance/weather_notification.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Users 테이블 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"사용자 데이터: {user_count}개")
        
        # Markets 테이블 데이터 확인
        if check_table_exists(cursor, 'markets'):
            cursor.execute("SELECT COUNT(*) FROM markets")
            market_count = cursor.fetchone()[0]
            print(f"시장 데이터: {market_count}개")
        
        # Weather 테이블 데이터 확인
        if check_table_exists(cursor, 'weather'):
            cursor.execute("SELECT COUNT(*) FROM weather")
            weather_count = cursor.fetchone()[0]
            print(f"날씨 데이터: {weather_count}개")
        
        # FCM 필드 확인
        required_fcm_fields = ['fcm_token', 'fcm_enabled', 'fcm_topics', 'device_info']
        missing_fields = []
        
        for field in required_fcm_fields:
            if not check_column_exists(cursor, 'users', field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"누락된 FCM 필드: {missing_fields}")
            return False
        else:
            print("모든 FCM 필드가 정상적으로 추가되었습니다.")
            return True
            
    except Exception as e:
        print(f"검증 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

def main():
    """메인 함수"""
    print("=" * 50)
    print("FCM 데이터베이스 마이그레이션 스크립트")
    print("=" * 50)
    
    # 현재 디렉토리 확인
    current_dir = os.getcwd()
    print(f"현재 디렉토리: {current_dir}")
    
    # instance 디렉토리 확인/생성
    if not os.path.exists('instance'):
        print("instance 디렉토리 생성")
        os.makedirs('instance')
    
    # 기존 데이터베이스 백업
    backup_database()
    
    # 마이그레이션 실행
    if migrate_database():
        # 검증
        if verify_migration():
            print("\n✅ 마이그레이션이 성공적으로 완료되었습니다!")
            print("이제 Flask 앱을 시작할 수 있습니다.")
        else:
            print("\n❌ 마이그레이션 검증에 실패했습니다.")
            return 1
    else:
        print("\n❌ 마이그레이션에 실패했습니다.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())