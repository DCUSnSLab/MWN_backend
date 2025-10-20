#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 초기화 스크립트

데이터베이스 테이블을 생성하고 샘플 데이터를 추가합니다.
"""

from app import app, db
from models import User, Market, DamageStatus, Weather

def create_tables():
    """데이터베이스 테이블 생성"""
    print("🗄️  데이터베이스 테이블 생성 중...")
    
    with app.app_context():
        try:
            # 모든 테이블 생성
            db.create_all()
            print("✅ 데이터베이스 테이블 생성 완료!")
            
            # 테이블 확인
            tables = {
                'users': User,
                'markets': Market,
                'damage_statuses': DamageStatus, 
                'weather': Weather
            }
            
            print("\n📋 생성된 테이블:")
            for table_name, model in tables.items():
                try:
                    count = model.query.count()
                    print(f"   ✅ {table_name}: {count}개 레코드")
                except Exception as e:
                    print(f"   ❌ {table_name}: 오류 - {e}")
                    
        except Exception as e:
            print(f"❌ 테이블 생성 오류: {e}")

def add_sample_data():
    """샘플 데이터 추가"""
    print("\n📝 샘플 데이터 추가 중...")
    
    with app.app_context():
        try:
            # 기존 데이터가 있는지 확인
            if User.query.count() > 0:
                print("ℹ️  이미 샘플 데이터가 존재합니다.")
                return
            
            # 샘플 사용자 데이터
            sample_users = [
                User(
                    name="김철수",
                    email="kim@example.com",
                    phone="010-1234-5678",
                    location="서울특별시 중구",
                    notification_preferences={"email": True, "sms": True}
                ),
                User(
                    name="이영희", 
                    email="lee@example.com",
                    phone="010-2345-6789",
                    location="부산광역시 중구",
                    notification_preferences={"email": True, "sms": False}
                )
            ]
            
            # 샘플 시장 데이터
            sample_markets = [
                Market(
                    name="동대문시장",
                    location="서울특별시 중구 창신동",
                    latitude=37.5707,
                    longitude=127.0087,
                    category="전통시장"
                ),
                Market(
                    name="자갈치시장",
                    location="부산광역시 중구 남포동",
                    latitude=35.0969,
                    longitude=129.0305,
                    category="수산시장"
                ),
                Market(
                    name="서문시장",
                    location="대구광역시 중구 대신동",
                    latitude=35.8714,
                    longitude=128.6014,
                    category="전통시장"
                )
            ]
            
            # 데이터베이스에 추가
            for user in sample_users:
                db.session.add(user)
            
            for market in sample_markets:
                db.session.add(market)
            
            db.session.commit()
            
            print("✅ 샘플 데이터 추가 완료!")
            print(f"   👥 사용자: {len(sample_users)}명")
            print(f"   🏪 시장: {len(sample_markets)}개")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 샘플 데이터 추가 오류: {e}")

def main():
    print("🚀 데이터베이스 초기화")
    print("=" * 40)
    
    # 1. 테이블 생성
    create_tables()
    
    # 2. 샘플 데이터 추가
    add_sample_data()
    
    print("\n✅ 데이터베이스 초기화 완료!")
    print("이제 check_database.py를 실행하여 데이터를 확인할 수 있습니다.")

if __name__ == "__main__":
    main()