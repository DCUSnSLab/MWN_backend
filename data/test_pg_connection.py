#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PostgreSQL 연결 테스트 및 데이터베이스 생성 스크립트
"""

import psycopg2
import sys

def test_connection():
    """PostgreSQL 연결 테스트"""
    try:
        # 먼저 postgres 데이터베이스에 연결
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            user="myuser",
            password="mypassword",
            database="postgres"
        )
        
        print("✅ PostgreSQL 서버 연결 성공!")
        
        # 데이터베이스 생성
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 기존 데이터베이스 확인
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'weather_notification'")
        exists = cursor.fetchone()
        
        if exists:
            print("✅ weather_notification 데이터베이스가 이미 존재합니다.")
        else:
            print("📝 weather_notification 데이터베이스 생성 중...")
            cursor.execute("CREATE DATABASE weather_notification")
            print("✅ weather_notification 데이터베이스가 생성되었습니다.")
        
        cursor.close()
        conn.close()
        
        # weather_notification 데이터베이스에 연결 테스트
        test_conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            user="myuser",
            password="mypassword",
            database="weather_notification"
        )
        
        print("✅ weather_notification 데이터베이스 연결 성공!")
        test_conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        if "password authentication failed" in str(e):
            print("❌ 사용자 인증 실패: 사용자명/비밀번호를 확인하세요.")
        elif "does not exist" in str(e):
            print("❌ 데이터베이스 또는 사용자가 존재하지 않습니다.")
        elif "connection refused" in str(e):
            print("❌ PostgreSQL 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        else:
            print(f"❌ PostgreSQL 연결 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def main():
    print("PostgreSQL 연결 및 데이터베이스 설정 테스트")
    print("=" * 50)
    
    if test_connection():
        print("\n🎉 PostgreSQL 설정이 완료되었습니다!")
        print("이제 마이그레이션을 진행할 수 있습니다.")
        return 0
    else:
        print("\n💡 확인사항:")
        print("1. PostgreSQL 서버가 실행 중인가요?")
        print("2. 사용자 'myuser'가 존재하고 패스워드가 'mypassword'인가요?")
        print("3. 5432 포트가 올바른가요?")
        return 1

if __name__ == "__main__":
    sys.exit(main())