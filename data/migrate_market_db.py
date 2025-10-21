#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Market 테이블에 nx, ny 필드 추가 마이그레이션 스크립트
"""

import sqlite3
import os
import sys
from datetime import datetime

def backup_database():
    """데이터베이스 백업"""
    db_path = 'instance/weather_notification.db'
    backup_path = f'instance/weather_notification.db.backup.market_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    if os.path.exists(db_path):
        print(f"데이터베이스 백업 중: {backup_path}")
        os.system(f'cp "{db_path}" "{backup_path}"')
        print("백업 완료")
        return True
    else:
        print("기존 데이터베이스가 없습니다.")
        return False

def check_column_exists(cursor, table_name, column_name):
    """컬럼 존재 여부 확인"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_markets_table(cursor):
    """Markets 테이블에 nx, ny 필드 추가"""
    print("Markets 테이블 마이그레이션 중...")
    
    # nx, ny 필드 추가
    new_fields = [
        ('nx', 'INTEGER'),
        ('ny', 'INTEGER')
    ]
    
    for field_name, field_type in new_fields:
        if not check_column_exists(cursor, 'markets', field_name):
            print(f"  - {field_name} 필드 추가")
            cursor.execute(f"ALTER TABLE markets ADD COLUMN {field_name} {field_type}")
        else:
            print(f"  - {field_name} 필드 이미 존재")

def migrate_database():
    """전체 데이터베이스 마이그레이션"""
    db_path = 'instance/weather_notification.db'
    
    print("Markets 테이블 마이그레이션 시작...")
    print(f"대상 데이터베이스: {db_path}")
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Markets 테이블 마이그레이션
        migrate_markets_table(cursor)
        
        # 변경사항 커밋
        conn.commit()
        print("\n마이그레이션 완료!")
        
        # 마이그레이션 결과 확인
        print("\n마이그레이션 결과 확인:")
        cursor.execute("PRAGMA table_info(markets)")
        columns = cursor.fetchall()
        print("Markets 테이블 구조:")
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
        # nx, ny 필드 확인
        required_fields = ['nx', 'ny']
        missing_fields = []
        
        for field in required_fields:
            if not check_column_exists(cursor, 'markets', field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"누락된 필드: {missing_fields}")
            return False
        else:
            print("모든 필드가 정상적으로 추가되었습니다.")
            return True
            
    except Exception as e:
        print(f"검증 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

def main():
    """메인 함수"""
    print("=" * 50)
    print("Markets 테이블 nx, ny 필드 추가 마이그레이션")
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
        else:
            print("\n❌ 마이그레이션 검증에 실패했습니다.")
            return 1
    else:
        print("\n❌ 마이그레이션에 실패했습니다.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())