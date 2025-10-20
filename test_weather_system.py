#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
날씨 시스템 통합 테스트

시장별 자동 날씨 조회 시스템의 전체 기능을 테스트합니다.
"""

import time
import requests
import json
from app import app, db
from models import Market, Weather
from weather_scheduler import weather_scheduler

def test_weather_system():
    """날씨 시스템 통합 테스트"""
    print("🧪 날씨 시스템 통합 테스트 시작")
    print("=" * 60)
    
    with app.app_context():
        # 1. 데이터베이스 상태 확인
        print("1️⃣  데이터베이스 상태 확인")
        markets = Market.query.all()
        weather_records = Weather.query.count()
        
        print(f"   📊 시장 개수: {len(markets)}개")
        print(f"   🌤️  날씨 레코드: {weather_records}개")
        
        markets_with_coords = [m for m in markets if m.latitude and m.longitude]
        print(f"   📍 좌표 있는 시장: {len(markets_with_coords)}개")
        
        if len(markets_with_coords) == 0:
            print("   ⚠️  좌표가 있는 시장이 없습니다. 샘플 시장 데이터를 확인해주세요.")
            return
        
        # 2. 스케줄러 상태 확인
        print(f"\n2️⃣  스케줄러 상태 확인")
        stats = weather_scheduler.get_weather_statistics()
        print(f"   📈 통계: {json.dumps(stats, indent=6, ensure_ascii=False)}")
        
        # 3. 수동 날씨 데이터 수집 테스트
        print(f"\n3️⃣  수동 날씨 데이터 수집 테스트")
        print("   🔄 날씨 데이터 수집 시작...")
        
        initial_count = Weather.query.count()
        weather_scheduler.collect_market_weather_data()
        final_count = Weather.query.count()
        
        new_records = final_count - initial_count
        print(f"   ✅ 수집 완료: {new_records}개 새 레코드 추가 (총 {final_count}개)")
        
        # 4. 최신 날씨 데이터 확인
        print(f"\n4️⃣  최신 날씨 데이터 확인")
        latest_current = Weather.query.filter_by(api_type='current').order_by(Weather.created_at.desc()).first()
        latest_forecast = Weather.query.filter_by(api_type='forecast').order_by(Weather.created_at.desc()).first()
        
        if latest_current:
            print(f"   🌡️  최신 현재 날씨: {latest_current.location_name} - {latest_current.temp}°C")
            print(f"      수집 시간: {latest_current.created_at}")
        
        if latest_forecast:
            print(f"   🔮 최신 예보: {latest_forecast.location_name} - {latest_forecast.temp}°C")
            print(f"      예보 시간: {latest_forecast.fcst_date} {latest_forecast.fcst_time}")
        
        # 5. 시장별 데이터 분포 확인
        print(f"\n5️⃣  시장별 데이터 분포")
        location_stats = {}
        for weather in Weather.query.all():
            location = weather.location_name or "미지정"
            if location not in location_stats:
                location_stats[location] = {'current': 0, 'forecast': 0}
            location_stats[location][weather.api_type] += 1
        
        for location, stats in location_stats.items():
            total = stats['current'] + stats['forecast']
            print(f"   📍 {location}: 총 {total}개 (현재 {stats['current']}개, 예보 {stats['forecast']}개)")

def test_api_endpoints():
    """API 엔드포인트 테스트"""
    print(f"\n🌐 API 엔드포인트 테스트")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    
    # 서버가 실행 중인지 확인
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 서버 실행 중")
        else:
            print("❌ 서버 응답 오류")
            return
    except requests.exceptions.RequestException:
        print("❌ 서버에 연결할 수 없습니다. Flask 서버를 먼저 실행해주세요.")
        print("   실행 명령: python app.py")
        return
    
    # API 엔드포인트 테스트
    endpoints = [
        ("GET", "/api/scheduler/status", "스케줄러 상태 조회"),
        ("GET", "/api/scheduler/stats", "날씨 통계 조회"),
        ("POST", "/api/scheduler/collect", "수동 데이터 수집"),
        ("GET", "/api/weather?limit=5", "날씨 데이터 조회")
    ]
    
    for method, endpoint, description in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
            else:
                response = requests.post(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {description}: 성공")
                if endpoint.endswith("stats"):
                    data = response.json()
                    print(f"   📊 통계: {json.dumps(data, indent=6, ensure_ascii=False)}")
            else:
                print(f"❌ {description}: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ {description}: 연결 오류 - {e}")

def main():
    """메인 테스트 실행"""
    print("🚀 날씨 시스템 종합 테스트")
    print("=" * 80)
    
    # 1. 시스템 내부 테스트
    test_weather_system()
    
    # 2. API 엔드포인트 테스트
    test_api_endpoints()
    
    print(f"\n" + "=" * 80)
    print("✅ 테스트 완료!")
    print("\n📋 다음 단계:")
    print("   1. Flask 서버 실행: python app.py")
    print("   2. 스케줄러 시작: POST /api/scheduler/start")
    print("   3. 상태 모니터링: GET /api/scheduler/status")
    print("=" * 80)

if __name__ == "__main__":
    main()