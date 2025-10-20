#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 데이터 조회 도구

간단한 명령어로 데이터베이스의 내용을 확인할 수 있습니다.
"""

import sys
from app import app, db
from models import User, Market, DamageStatus, Weather

def show_summary():
    """데이터베이스 요약"""
    with app.app_context():
        print("📊 데이터베이스 요약")
        print("=" * 40)
        print(f"👥 사용자: {User.query.count()}명")
        print(f"🏪 시장: {Market.query.count()}개")
        print(f"⚠️  피해상태: {DamageStatus.query.count()}건")
        print(f"🌤️  날씨데이터: {Weather.query.count()}개")
        
        current_count = Weather.query.filter_by(api_type='current').count()
        forecast_count = Weather.query.filter_by(api_type='forecast').count()
        print(f"   📍 현재날씨: {current_count}개")
        print(f"   🔮 예보데이터: {forecast_count}개")

def show_markets():
    """시장 목록"""
    with app.app_context():
        print("\n🏪 시장 목록")
        print("=" * 60)
        markets = Market.query.all()
        
        for i, market in enumerate(markets, 1):
            coords = f"({market.latitude}, {market.longitude})" if market.latitude else "좌표없음"
            status = "🟢" if market.is_active else "🔴"
            print(f"{i}. {status} {market.name}")
            print(f"   📍 위치: {market.location}")
            print(f"   🗺️  좌표: {coords}")
            print(f"   📂 카테고리: {market.category}")
            
            # 해당 시장의 최신 날씨
            latest_weather = Weather.query.filter(
                Weather.location_name.contains(market.name)
            ).order_by(Weather.created_at.desc()).first()
            
            if latest_weather:
                print(f"   🌡️  최신온도: {latest_weather.temp}°C ({latest_weather.created_at.strftime('%m/%d %H:%M')})")
            else:
                print(f"   🌡️  날씨데이터: 없음")
            print()

def show_weather(limit=10):
    """최신 날씨 데이터"""
    with app.app_context():
        print(f"\n🌤️  최신 날씨 데이터 (최근 {limit}개)")
        print("=" * 80)
        
        weather_data = Weather.query.order_by(Weather.created_at.desc()).limit(limit).all()
        
        print("시간     | 지역           | 타입    | 기온   | 습도  | 강수량")
        print("-" * 80)
        
        for weather in weather_data:
            time_str = weather.created_at.strftime("%m/%d %H:%M")
            location = (weather.location_name or "미지정")[:15]
            api_type = weather.api_type[:8]
            temp = f"{weather.temp:.1f}°C" if weather.temp else "---"
            humidity = f"{weather.humidity:.0f}%" if weather.humidity else "---"
            rain = f"{weather.rain_1h:.1f}mm" if weather.rain_1h else "---"
            
            print(f"{time_str} | {location:<15} | {api_type:<7} | {temp:<6} | {humidity:<5} | {rain}")

def show_weather_by_location(location_filter=""):
    """지역별 날씨 데이터"""
    with app.app_context():
        print(f"\n📍 지역별 날씨 데이터 (필터: '{location_filter}')")
        print("=" * 60)
        
        query = Weather.query
        if location_filter:
            query = query.filter(Weather.location_name.contains(location_filter))
        
        weather_data = query.order_by(Weather.created_at.desc()).limit(20).all()
        
        if not weather_data:
            print("해당 조건의 날씨 데이터가 없습니다.")
            return
        
        # 지역별로 그룹화
        location_groups = {}
        for weather in weather_data:
            location = weather.location_name or "미지정"
            if location not in location_groups:
                location_groups[location] = []
            location_groups[location].append(weather)
        
        for location, weathers in location_groups.items():
            print(f"\n🏪 {location}")
            current_weather = [w for w in weathers if w.api_type == 'current']
            forecast_weather = [w for w in weathers if w.api_type == 'forecast']
            
            if current_weather:
                latest = current_weather[0]
                print(f"   🌡️  현재: {latest.temp}°C, 습도 {latest.humidity}%, 풍속 {latest.wind_speed}m/s")
                print(f"   ⏰ 업데이트: {latest.created_at.strftime('%m/%d %H:%M')}")
            
            if forecast_weather:
                print(f"   🔮 예보: {len(forecast_weather)}시간 데이터 있음")

def show_users():
    """사용자 목록"""
    with app.app_context():
        print("\n👥 사용자 목록")
        print("=" * 40)
        
        users = User.query.all()
        for i, user in enumerate(users, 1):
            status = "🟢" if user.is_active else "🔴"
            print(f"{i}. {status} {user.name}")
            print(f"   📧 이메일: {user.email}")
            print(f"   📱 전화: {user.phone or '없음'}")
            print(f"   📍 위치: {user.location or '없음'}")
            print(f"   📅 가입: {user.created_at.strftime('%Y-%m-%d')}")
            print()

def main():
    """메인 함수"""
    commands = {
        'summary': show_summary,
        'markets': show_markets,
        'weather': lambda: show_weather(20),
        'users': show_users,
    }
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in commands:
            commands[command]()
        elif command.startswith('weather:'):
            # weather:동대문 형태로 지역 필터링
            location_filter = command.split(':', 1)[1] if ':' in command else ""
            show_weather_by_location(location_filter)
        else:
            print(f"❌ 알 수 없는 명령어: {command}")
            print("사용 가능한 명령어: summary, markets, weather, users, weather:지역명")
    else:
        # 인자가 없으면 전체 요약 표시
        show_summary()
        show_markets()
        show_weather(10)

if __name__ == "__main__":
    main()