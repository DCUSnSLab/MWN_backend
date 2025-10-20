#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기상청 API 호출 디버깅 도구

API 호출 실패 원인을 상세히 분석하는 스크립트입니다.
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def check_environment():
    """환경 설정 확인"""
    print("🔍 환경 설정 확인")
    print("=" * 50)
    
    service_key = os.getenv('KMA_SERVICE_KEY')
    if service_key:
        print(f"✅ KMA_SERVICE_KEY: {service_key[:10]}***{service_key[-5:] if len(service_key) > 15 else '***'}")
    else:
        print("❌ KMA_SERVICE_KEY가 설정되지 않았습니다!")
        print("   기상청 공공데이터포털(https://apihub.kma.go.kr/)에서 서비스키를 발급받아")
        print("   .env 파일에 KMA_SERVICE_KEY=your-key 형태로 설정해주세요.")
        return False
    
    print(f"✅ python-dotenv 설치됨")
    print(f"✅ requests 라이브러리 사용 가능")
    return True

def test_simple_api_call():
    """가장 간단한 API 호출 테스트"""
    print("\n🌐 기본 API 호출 테스트")
    print("=" * 50)
    
    service_key = os.getenv('KMA_SERVICE_KEY')
    if not service_key:
        print("❌ 서비스키가 없어 테스트를 건너뜁니다.")
        return
    
    # 서울시청 좌표
    nx, ny = 60, 127  # 서울시청 격자좌표
    
    # 현재 시간 기준 base_date, base_time 계산
    now = datetime.now()
    if now.minute < 40:
        now = now - timedelta(hours=1)
    
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")
    
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
    
    params = {
        'serviceKey': service_key,
        'pageNo': '1',
        'numOfRows': '10',
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': str(nx),
        'ny': str(ny)
    }
    
    print(f"📍 요청 URL: {url}")
    print(f"📅 기준일시: {base_date} {base_time}")
    print(f"📍 격자좌표: X={nx}, Y={ny}")
    print(f"🔑 서비스키: {service_key[:10]}***")
    
    try:
        print("\n⏳ API 호출 중...")
        response = requests.get(url, params=params, timeout=30)
        
        print(f"📊 HTTP 상태코드: {response.status_code}")
        print(f"📄 응답 헤더:")
        for key, value in response.headers.items():
            print(f"   {key}: {value}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"\n✅ JSON 파싱 성공!")
                print(f"📋 응답 구조:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000] + "..." if len(str(data)) > 1000 else json.dumps(data, indent=2, ensure_ascii=False))
                
                # 응답 코드 확인
                header = data.get('response', {}).get('header', {})
                result_code = header.get('resultCode')
                result_msg = header.get('resultMsg')
                
                print(f"\n🔍 API 결과:")
                print(f"   결과코드: {result_code}")
                print(f"   결과메시지: {result_msg}")
                
                if result_code == '00':
                    print("✅ API 호출 성공!")
                    body = data.get('response', {}).get('body', {})
                    items = body.get('items', {})
                    if isinstance(items, dict) and 'item' in items:
                        item_list = items['item']
                        print(f"📦 데이터 개수: {len(item_list) if isinstance(item_list, list) else 1}")
                        if item_list:
                            print(f"📄 첫 번째 데이터 예시:")
                            first_item = item_list[0] if isinstance(item_list, list) else item_list
                            print(json.dumps(first_item, indent=2, ensure_ascii=False))
                    else:
                        print("⚠️  items 구조가 예상과 다릅니다.")
                else:
                    print(f"❌ API 오류: {result_msg}")
                    analyze_error_code(result_code, result_msg)
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"📄 원본 응답 (처음 500자):")
                print(response.text[:500])
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"📄 응답 내용:")
            print(response.text[:500])
            
    except requests.exceptions.Timeout:
        print("❌ 요청 시간 초과 (30초)")
    except requests.exceptions.ConnectionError:
        print("❌ 연결 오류 - 인터넷 연결을 확인해주세요")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

def analyze_error_code(result_code, result_msg):
    """오류 코드 분석"""
    print(f"\n🔍 오류 코드 분석")
    print("-" * 30)
    
    error_codes = {
        '01': '어플리케이션 에러',
        '02': '데이터베이스 에러', 
        '03': '데이터없음 에러',
        '04': 'HTTP 에러',
        '05': '서비스 연결실패 에러',
        '10': '잘못된 요청 파라메터 에러',
        '11': '필수요청 파라메터가 없음',
        '12': '해당 오픈API서비스가 없거나 폐기됨',
        '20': '서비스 접근거부',
        '21': '일시적으로 사용할 수 없는 서비스 키',
        '22': '서비스 요청제한횟수 초과에러',
        '30': '등록되지 않은 서비스키',
        '31': '기한만료된 서비스키',
        '32': '등록되지 않은 IP',
        '33': '서명되지 않은 호출'
    }
    
    description = error_codes.get(result_code, '알 수 없는 오류')
    print(f"코드 {result_code}: {description}")
    print(f"메시지: {result_msg}")
    
    # 해결방법 제안
    if result_code in ['30', '31', '32', '33']:
        print("\n💡 해결방법:")
        print("   1. 기상청 공공데이터포털에서 서비스키가 정상적으로 발급되었는지 확인")
        print("   2. 서비스키가 만료되지 않았는지 확인")
        print("   3. 현재 IP가 허용된 IP 목록에 있는지 확인")
    elif result_code in ['10', '11']:
        print("\n💡 해결방법:")
        print("   1. 요청 파라미터를 다시 확인")
        print("   2. base_date, base_time 형식이 올바른지 확인")
        print("   3. nx, ny 좌표가 유효한지 확인")

def test_coordinate_conversion():
    """좌표 변환 테스트"""
    print("\n🗺️  좌표 변환 테스트")  
    print("=" * 50)
    
    from weather_api import convert_to_grid
    
    test_coords = [
        (37.5665, 126.9780, "서울시청"),
        (35.1595, 129.0756, "부산시청"),
        (33.4996, 126.5312, "제주시청")
    ]
    
    for lat, lon, name in test_coords:
        nx, ny = convert_to_grid(lat, lon)
        print(f"📍 {name}: ({lat}, {lon}) → 격자({nx}, {ny})")

def main():
    print("🚨 기상청 API 디버깅 도구")
    print("=" * 60)
    
    # 1. 환경 설정 확인
    if not check_environment():
        return
    
    # 2. 좌표 변환 테스트  
    test_coordinate_conversion()
    
    # 3. API 호출 테스트
    test_simple_api_call()
    
    print(f"\n📋 추가 확인사항:")
    print("   1. .env 파일에 KMA_SERVICE_KEY가 올바르게 설정되어 있는지")
    print("   2. 기상청 공공데이터포털에서 서비스 신청이 승인되었는지")
    print("   3. 서비스키가 활성화 상태인지") 
    print("   4. 요청 제한 횟수를 초과하지 않았는지")

if __name__ == "__main__":
    main()