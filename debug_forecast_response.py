#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기상청 예보 API 실제 응답 구조 확인 도구
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from weather_api import convert_to_grid

# 환경변수 로드
load_dotenv()

def debug_forecast_response():
    service_key = os.getenv('KMA_SERVICE_KEY')
    if not service_key:
        print("KMA_SERVICE_KEY가 설정되지 않았습니다.")
        return
    
    # 인천 좌표
    lat, lon = 37.455301, 126.693331
    nx, ny = convert_to_grid(lat, lon)
    
    print(f"테스트 위치: 인천 (격자: {nx}, {ny})")
    
    # 현재 시간 기준으로 base_date, base_time 설정
    now = datetime.now()
    if now.minute < 30:
        now = now - timedelta(hours=1)
    
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H30")
    
    # API 호출
    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst"
    params = {
        'authKey': service_key,
        'pageNo': '1',
        'numOfRows': '60',  # 예보는 더 많은 데이터가 있을 수 있음
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': str(nx),
        'ny': str(ny)
    }
    
    print(f"\n📡 예보 API 호출:")
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\n📊 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # 응답 구조 분석
            print(f"\n🔍 예보 응답 구조 분석:")
            if 'response' in data:
                response_data = data['response']
                
                if 'header' in response_data:
                    header = response_data['header']
                    print(f"header: resultCode={header.get('resultCode')}, resultMsg={header.get('resultMsg')}")
                
                if 'body' in response_data:
                    body = response_data['body']
                    print(f"body: totalCount={body.get('totalCount')}")
                    
                    if 'items' in body:
                        items = body['items']
                        
                        if isinstance(items, dict) and 'item' in items:
                            item_list = items['item']
                            print(f"item 개수: {len(item_list) if isinstance(item_list, list) else 1}")
                            
                            if isinstance(item_list, list) and len(item_list) > 0:
                                # 첫 번째와 두 번째 아이템 출력
                                print(f"\n📋 첫 번째 예보 아이템:")
                                print(json.dumps(item_list[0], indent=2, ensure_ascii=False))
                                
                                if len(item_list) > 1:
                                    print(f"\n📋 두 번째 예보 아이템:")
                                    print(json.dumps(item_list[1], indent=2, ensure_ascii=False))
                                
                                # 카테고리별 분포 확인
                                categories = {}
                                forecast_times = set()
                                
                                for item in item_list:
                                    category = item.get('category')
                                    fcst_date = item.get('fcstDate')
                                    fcst_time = item.get('fcstTime')
                                    
                                    if category:
                                        categories[category] = categories.get(category, 0) + 1
                                    
                                    if fcst_date and fcst_time:
                                        forecast_times.add(f"{fcst_date} {fcst_time}")
                                
                                print(f"\n📊 카테고리별 개수:")
                                for cat, count in sorted(categories.items()):
                                    print(f"  {cat}: {count}개")
                                
                                print(f"\n⏰ 예보 시간대:")
                                for time in sorted(list(forecast_times))[:10]:  # 첫 10개만
                                    print(f"  {time}")
                                
            print(f"\n📄 전체 응답 (처음 2000자):")
            response_text = json.dumps(data, indent=2, ensure_ascii=False)
            print(response_text[:2000] + "..." if len(response_text) > 2000 else response_text)
                                
        else:
            print(f"HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    debug_forecast_response()