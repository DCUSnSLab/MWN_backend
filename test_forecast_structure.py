#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
예보 데이터 구조 확인 스크립트
"""

import os
from dotenv import load_dotenv
from weather_api import KMAWeatherAPI, convert_to_grid
import json

# 환경변수 로드
load_dotenv()

def test_forecast_structure():
    service_key = os.getenv('KMA_SERVICE_KEY')
    if not service_key:
        print("KMA_SERVICE_KEY가 설정되지 않았습니다.")
        return
    
    weather_api = KMAWeatherAPI(service_key)
    
    # 대구가톨릭대학교 좌표
    lat, lon = 35.912828, 128.803543
    location_name = "대구가톨릭대학교"
    
    nx, ny = convert_to_grid(lat, lon)
    print(f"테스트 위치: {location_name} (격자: {nx}, {ny})")
    
    # 예보 데이터 조회
    result = weather_api.get_forecast_weather(nx, ny, location_name)
    
    if result['status'] == 'success':
        data = result['data']
        print(f"\n✅ API 호출 성공!")
        print(f"데이터 타입: {type(data)}")
        print(f"데이터 개수: {len(data) if isinstance(data, list) else 1}")
        
        if isinstance(data, list) and len(data) > 0:
            print(f"\n첫 번째 예보 데이터:")
            first_item = data[0]
            print(json.dumps(first_item, indent=2, ensure_ascii=False))
            
            print(f"\n시간대별 예보 요약:")
            for i, item in enumerate(data[:3]):  # 첫 3개만
                fcst_time = f"{item.get('fcst_date', '')} {item.get('fcst_time', '')}"
                temp = item.get('temp', 'N/A')
                humidity = item.get('humidity', 'N/A')
                print(f"  {i+1}. {fcst_time} | 기온: {temp}°C | 습도: {humidity}%")
        else:
            print(f"\n단일 데이터:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ API 호출 실패: {result['message']}")

if __name__ == "__main__":
    test_forecast_structure()