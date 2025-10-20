#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 엔드포인트 테스트 스크립트

모든 API 엔드포인트를 테스트하여 외부 앱에서 호출 가능한지 확인합니다.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8002"

def test_endpoint(method, endpoint, data=None, description=""):
    """API 엔드포인트 테스트"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"❌ 지원하지 않는 메서드: {method}")
            return False
        
        status_emoji = "✅" if response.status_code in [200, 201] else "❌"
        print(f"{status_emoji} {method} {endpoint} ({response.status_code}) - {description}")
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                if isinstance(result, dict) and 'error' not in result:
                    return True
                elif isinstance(result, list):
                    return True
                else:
                    print(f"   ⚠️  응답에 오류 있음: {result}")
                    return False
            except json.JSONDecodeError:
                print(f"   ⚠️  JSON 파싱 실패")
                return False
        else:
            print(f"   ❌ 오류: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ {method} {endpoint} - 연결 실패 (서버가 실행되지 않음)")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {method} {endpoint} - 시간 초과")
        return False
    except Exception as e:
        print(f"❌ {method} {endpoint} - 오류: {e}")
        return False

def main():
    """모든 API 엔드포인트 테스트"""
    print("🚀 API 엔드포인트 테스트")
    print("=" * 60)
    print(f"서버 주소: {BASE_URL}")
    print()
    
    # 테스트할 엔드포인트들
    tests = [
        # 기본 상태 체크
        ("GET", "/health", None, "서버 헬스 체크"),
        
        # 사용자 관리
        ("GET", "/api/users", None, "사용자 목록 조회"),
        ("POST", "/api/users", {
            "name": "테스트 사용자",
            "email": f"test_{int(time.time())}@example.com",
            "phone": "010-1111-2222",
            "location": "테스트 지역"
        }, "새 사용자 생성"),
        
        # 시장 관리
        ("GET", "/api/markets", None, "시장 목록 조회"),
        ("POST", "/api/markets", {
            "name": "테스트 시장",
            "location": "테스트시 테스트구",
            "latitude": 37.5,
            "longitude": 127.0,
            "category": "테스트 시장"
        }, "새 시장 생성"),
        
        # 피해 상태
        ("GET", "/api/damage-status", None, "피해 상태 목록 조회"),
        
        # 날씨 데이터
        ("POST", "/api/weather/current", {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "location_name": "API 테스트"
        }, "현재 날씨 조회"),
        
        ("POST", "/api/weather/forecast", {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "location_name": "API 테스트"
        }, "날씨 예보 조회"),
        
        ("GET", "/api/weather?limit=5", None, "저장된 날씨 데이터 조회"),
        ("GET", "/api/weather?api_type=current&limit=3", None, "현재 날씨만 조회"),
        
        # 스케줄러 관리
        ("GET", "/api/scheduler/status", None, "스케줄러 상태 조회"),
        ("GET", "/api/scheduler/stats", None, "날씨 데이터 통계 조회"),
        ("POST", "/api/scheduler/start", None, "스케줄러 시작"),
        ("POST", "/api/scheduler/collect", None, "수동 날씨 수집"),
        
        # 데이터베이스 뷰어 API
        ("GET", "/db-viewer/api/stats", None, "DB 통계 API"),
        ("GET", "/db-viewer/api/users", None, "DB 사용자 API"),
        ("GET", "/db-viewer/api/markets", None, "DB 시장 API"),
        ("GET", "/db-viewer/api/weather", None, "DB 날씨 API"),
        ("GET", "/db-viewer/api/damage", None, "DB 피해상태 API"),
    ]
    
    # 테스트 실행
    success_count = 0
    total_count = len(tests)
    
    for method, endpoint, data, description in tests:
        if test_endpoint(method, endpoint, data, description):
            success_count += 1
        time.sleep(0.5)  # API 호출 간격
    
    # 결과 요약
    print()
    print("=" * 60)
    print(f"📊 테스트 결과: {success_count}/{total_count} 성공")
    
    if success_count == total_count:
        print("🎉 모든 API가 정상 작동합니다!")
        print("\n📋 외부 앱에서 사용 가능한 주요 API:")
        print("   • GET  /health - 서버 상태 확인")
        print("   • GET  /api/markets - 시장 목록")
        print("   • POST /api/weather/current - 현재 날씨")
        print("   • POST /api/weather/forecast - 날씨 예보")
        print("   • GET  /api/weather - 저장된 날씨 데이터")
        print("   • GET  /api/scheduler/stats - 시스템 통계")
    else:
        failed_count = total_count - success_count
        print(f"⚠️  {failed_count}개 API에서 문제가 발생했습니다.")
        print("서버가 실행 중인지 확인해주세요: python app.py")
    
    print("=" * 60)

def test_external_call_examples():
    """외부 호출 예제 테스트"""
    print("\n🌐 외부 앱 호출 시뮬레이션")
    print("=" * 40)
    
    # 1. 모바일 앱에서 시장 목록 요청
    print("📱 [모바일 앱] 시장 목록 요청...")
    success = test_endpoint("GET", "/api/markets", None, "시장 목록")
    
    # 2. 웹 앱에서 특정 지역 날씨 요청
    print("\n💻 [웹 앱] 서울 날씨 요청...")
    weather_request = {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "location_name": "서울시청"
    }
    success = test_endpoint("POST", "/api/weather/current", weather_request, "현재 날씨")
    
    # 3. 대시보드에서 통계 요청
    print("\n📊 [대시보드] 시스템 통계 요청...")
    success = test_endpoint("GET", "/api/scheduler/stats", None, "시스템 통계")
    
    # 4. 관리 시스템에서 데이터 수집 요청
    print("\n🔧 [관리 시스템] 수동 데이터 수집 요청...")
    success = test_endpoint("POST", "/api/scheduler/collect", None, "수동 수집")

if __name__ == "__main__":
    main()
    test_external_call_examples()