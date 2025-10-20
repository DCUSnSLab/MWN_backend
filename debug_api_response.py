#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기상청 API 실제 응답 구조 확인 도구
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from weather_api import convert_to_grid

# 환경변수 로드
load_dotenv()

def debug_api_response():
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
    if now.minute < 40:
        now = now - timedelta(hours=1)
    
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")
    
    # API 호출
    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    params = {
        'authKey': service_key,
        'pageNo': '1',
        'numOfRows': '10',
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': str(nx),
        'ny': str(ny)
    }
    
    print(f"\n📡 API 호출:")
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\n📊 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📄 전체 응답 구조:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 응답 구조 분석
            print(f"\n🔍 응답 구조 분석:")
            if 'response' in data:
                response_data = data['response']
                print(f"response 키 존재: ✅")
                
                if 'header' in response_data:
                    header = response_data['header']
                    print(f"header 키 존재: ✅")
                    print(f"  resultCode: {header.get('resultCode')}")
                    print(f"  resultMsg: {header.get('resultMsg')}")
                
                if 'body' in response_data:
                    body = response_data['body']
                    print(f"body 키 존재: ✅")
                    print(f"  dataType: {body.get('dataType')}")
                    print(f"  numOfRows: {body.get('numOfRows')}")
                    print(f"  pageNo: {body.get('pageNo')}")
                    print(f"  totalCount: {body.get('totalCount')}")
                    
                    if 'items' in body:
                        items = body['items']
                        print(f"  items 키 존재: ✅")
                        print(f"  items 타입: {type(items)}")
                        
                        if isinstance(items, dict) and 'item' in items:
                            item_list = items['item']
                            print(f"  item 리스트 존재: ✅")
                            print(f"  item 개수: {len(item_list) if isinstance(item_list, list) else 1}")
                            
                            if isinstance(item_list, list) and len(item_list) > 0:
                                first_item = item_list[0]
                            elif not isinstance(item_list, list):
                                first_item = item_list
                            else:
                                first_item = None
                                
                            if first_item:
                                print(f"\n📋 첫 번째 아이템 구조:")
                                print(json.dumps(first_item, indent=2, ensure_ascii=False))
                                
                                print(f"\n🔍 아이템 필드:")
                                for key, value in first_item.items():
                                    print(f"  {key}: {value} ({type(value).__name__})")
            else:
                print(f"response 키 없음: ❌")
                
        else:
            print(f"HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    debug_api_response()