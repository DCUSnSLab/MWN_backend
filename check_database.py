#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 확인 도구

현재 저장된 데이터를 확인하고 데이터베이스 상태를 점검하는 스크립트입니다.
"""

import os
import sys
from datetime import datetime

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Market, DamageStatus, Weather

def check_database_tables():
    """데이터베이스 테이블 존재 여부 확인"""
    print("🗄️  데이터베이스 테이블 확인")
    print("=" * 50)
    
    with app.app_context():
        try:
            # 테이블 존재 여부 확인
            tables = {
                'users': User,
                'markets': Market, 
                'damage_statuses': DamageStatus,
                'weather': Weather
            }
            
            for table_name, model in tables.items():
                try:
                    count = model.query.count()
                    print(f"✅ {table_name}: {count}개 레코드")
                except Exception as e:
                    print(f"❌ {table_name}: 오류 - {e}")
                    
        except Exception as e:
            print(f"❌ 데이터베이스 연결 오류: {e}")

def show_weather_data():
    """날씨 데이터 조회"""
    print("\n🌤️  날씨 데이터 조회")
    print("=" * 50)
    
    with app.app_context():
        try:
            # 최근 10개 날씨 데이터 조회
            weather_records = Weather.query.order_by(Weather.created_at.desc()).limit(10).all()
            
            if not weather_records:
                print("📭 저장된 날씨 데이터가 없습니다.")
                print("   웹 API를 통해 날씨 데이터를 조회하면 데이터베이스에 저장됩니다.")
                return
            
            print(f"📊 총 {Weather.query.count()}개의 날씨 데이터 중 최근 10개:")
            print()
            print("날짜시간       | 지역명     | API타입  | 기온    | 습도   | 강수량")
            print("-" * 70)
            
            for record in weather_records:
                created = record.created_at.strftime("%m/%d %H:%M") if record.created_at else "---"
                location = (record.location_name or "미지정")[:10]
                api_type = record.api_type or "---"
                temp = f"{record.temp:.1f}°C" if record.temp is not None else "---"
                humidity = f"{record.humidity:.0f}%" if record.humidity is not None else "---"
                rain = f"{record.rain_1h:.1f}mm" if record.rain_1h is not None else "---"
                
                print(f"{created:<12} | {location:<10} | {api_type:<8} | {temp:<7} | {humidity:<6} | {rain}")
                
        except Exception as e:
            print(f"❌ 날씨 데이터 조회 오류: {e}")

def show_detailed_weather_record():
    """상세 날씨 데이터 1개 조회"""
    print("\n🔍 상세 날씨 데이터")
    print("=" * 50)
    
    with app.app_context():
        try:
            latest_record = Weather.query.order_by(Weather.created_at.desc()).first()
            
            if not latest_record:
                print("📭 저장된 날씨 데이터가 없습니다.")
                return
            
            print("최근 저장된 날씨 데이터:")
            print(f"📅 저장 시간: {latest_record.created_at}")
            print(f"📍 지역명: {latest_record.location_name or '미지정'}")
            print(f"🗓️  기준 날짜: {latest_record.base_date}")
            print(f"⏰ 기준 시간: {latest_record.base_time}")
            print(f"📍 격자 좌표: X={latest_record.nx}, Y={latest_record.ny}")
            print(f"🔗 API 타입: {latest_record.api_type}")
            
            if latest_record.api_type == 'forecast':
                print(f"🔮 예보 날짜: {latest_record.fcst_date}")
                print(f"🔮 예보 시간: {latest_record.fcst_time}")
            
            print("\n🌤️  기상 정보:")
            if latest_record.temp is not None:
                print(f"   🌡️  기온: {latest_record.temp}°C")
            if latest_record.humidity is not None:
                print(f"   💧 습도: {latest_record.humidity}%")
            if latest_record.rain_1h is not None:
                print(f"   🌧️  1시간 강수량: {latest_record.rain_1h}mm")
            if latest_record.wind_speed is not None:
                print(f"   💨 풍속: {latest_record.wind_speed}m/s")
            if latest_record.wind_direction is not None:
                print(f"   🧭 풍향: {latest_record.wind_direction}°")
            
            if latest_record.api_type == 'forecast':
                if latest_record.pop is not None:
                    print(f"   ☔ 강수확률: {latest_record.pop}%")
                if latest_record.pty:
                    pty_map = {'0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}
                    print(f"   🌧️  강수형태: {pty_map.get(latest_record.pty, latest_record.pty)}")
                if latest_record.sky:
                    sky_map = {'1': '맑음', '3': '구름많음', '4': '흐림'}
                    print(f"   ☁️  하늘상태: {sky_map.get(latest_record.sky, latest_record.sky)}")
                    
        except Exception as e:
            print(f"❌ 상세 데이터 조회 오류: {e}")

def show_other_tables():
    """다른 테이블들 조회"""
    print("\n📋 기타 테이블 데이터")
    print("=" * 50)
    
    with app.app_context():
        try:
            # 사용자 데이터
            users = User.query.all()
            print(f"👥 사용자: {len(users)}명")
            for user in users[:3]:  # 최대 3명만 표시
                print(f"   - {user.name} ({user.email})")
            
            # 시장 데이터
            markets = Market.query.all()
            print(f"🏪 시장: {len(markets)}개")
            for market in markets[:3]:  # 최대 3개만 표시
                print(f"   - {market.name} ({market.location})")
            
            # 피해 상태 데이터
            damages = DamageStatus.query.all()
            print(f"⚠️  피해 상태: {len(damages)}건")
            for damage in damages[:3]:  # 최대 3건만 표시
                print(f"   - {damage.weather_event} ({damage.damage_level})")
                
        except Exception as e:
            print(f"❌ 기타 테이블 조회 오류: {e}")

def interactive_query():
    """대화형 데이터 조회"""
    print("\n💻 대화형 데이터 조회")
    print("=" * 50)
    print("원하는 조회를 선택하세요:")
    print("1. 특정 지역 날씨 데이터")
    print("2. 특정 날짜 날씨 데이터")
    print("3. API 타입별 데이터")
    print("4. 종료")
    
    while True:
        try:
            choice = input("\n선택 (1-4): ").strip()
            
            if choice == '1':
                location = input("지역명을 입력하세요 (예: 서울, 부산): ").strip()
                with app.app_context():
                    records = Weather.query.filter(Weather.location_name.contains(location)).order_by(Weather.created_at.desc()).limit(5).all()
                    if records:
                        print(f"\n'{location}' 관련 날씨 데이터 {len(records)}건:")
                        for record in records:
                            print(f"  {record.created_at.strftime('%m/%d %H:%M')} | {record.location_name} | {record.temp}°C")
                    else:
                        print(f"'{location}' 관련 데이터가 없습니다.")
            
            elif choice == '2':
                date = input("날짜를 입력하세요 (YYYYMMDD, 예: 20251017): ").strip()
                with app.app_context():
                    records = Weather.query.filter(Weather.base_date == date).order_by(Weather.created_at.desc()).all()
                    if records:
                        print(f"\n{date} 날씨 데이터 {len(records)}건:")
                        for record in records:
                            print(f"  {record.base_time} | {record.location_name or '미지정'} | {record.temp}°C")
                    else:
                        print(f"'{date}' 날짜의 데이터가 없습니다.")
            
            elif choice == '3':
                api_type = input("API 타입을 입력하세요 (current/forecast): ").strip()
                with app.app_context():
                    records = Weather.query.filter(Weather.api_type == api_type).order_by(Weather.created_at.desc()).limit(10).all()
                    if records:
                        print(f"\n'{api_type}' 타입 데이터 {len(records)}건 (최근 10개):")
                        for record in records:
                            print(f"  {record.created_at.strftime('%m/%d %H:%M')} | {record.location_name or '미지정'} | {record.temp}°C")
                    else:
                        print(f"'{api_type}' 타입 데이터가 없습니다.")
            
            elif choice == '4':
                print("종료합니다.")
                break
            
            else:
                print("잘못된 선택입니다. 1-4 중에서 선택해주세요.")
                
        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"오류 발생: {e}")

def main():
    print("🔍 데이터베이스 확인 도구")
    print("=" * 60)
    
    # 1. 테이블 상태 확인
    check_database_tables()
    
    # 2. 날씨 데이터 요약 조회
    show_weather_data()
    
    # 3. 상세 날씨 데이터 1개 조회
    show_detailed_weather_record()
    
    # 4. 기타 테이블들 조회
    show_other_tables()
    
    # 5. 대화형 조회 (선택사항)
    print("\n" + "=" * 60)
    user_input = input("대화형 조회를 시작하시겠습니까? (y/N): ").strip().lower()
    if user_input in ['y', 'yes']:
        interactive_query()
    
    print("\n✅ 데이터베이스 확인 완료!")

if __name__ == "__main__":
    main()