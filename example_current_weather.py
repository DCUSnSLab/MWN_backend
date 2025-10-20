#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기상청 초단기실황조회 API 사용 예제

이 스크립트는 기상청 공공데이터 API를 사용하여 
특정 지역의 현재 날씨 정보를 조회하는 예제입니다.

사용 전 준비사항:
1. 기상청 공공데이터포털에서 서비스키 발급 (https://apihub.kma.go.kr/)
2. .env 파일에 KMA_SERVICE_KEY 설정

https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst?pageNo=1&numOfRows=1000&dataType=XML&base_date=20251017&base_time=0600&nx=55&ny=127&authKey=RS9BlHAdSZevQZRwHQmXLA
https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst?pageNo=1&numOfRows=1000&dataType=XML&base_date=20251017&base_time=0630&nx=55&ny=127&authKey=RS9BlHAdSZevQZRwHQmXLA

https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst?pageNo=1&numOfRows=1000&dataType=XML&base_date=20251017&base_time=0600&nx=92&ny=92&authKey=RS9BlHAdSZevQZRwHQmXLA
https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst?pageNo=1&numOfRows=1000&dataType=XML&base_date=20251017&base_time=0630&nx=92&ny=92&authKey=RS9BlHAdSZevQZRwHQmXLA

대가대 좌표 35.912828, 128.803543
"""

import os
from dotenv import load_dotenv
from weather_api import KMAWeatherAPI, convert_to_grid

# 환경변수 로드
load_dotenv()

def main():
    # 서비스키 설정 (환경변수에서 가져오기)
    service_key = os.getenv('KMA_SERVICE_KEY')
    if not service_key:
        print("ERROR: KMA_SERVICE_KEY가 설정되지 않았습니다.")
        print("기상청 공공데이터포털에서 서비스키를 발급받아 .env 파일에 설정해주세요.")
        return
    
    # Weather API 인스턴스 생성
    weather_api = KMAWeatherAPI(service_key)
    
    # 테스트할 지역들 (위도, 경도, 지역명)
    test_locations = [
        # (37.5665, 126.9780, "서울특별시 중구"),      # 서울시청
        # (35.1595, 129.0756, "부산광역시 중구"),      # 부산시청
        # (35.8714, 128.6014, "대구광역시 중구"),      # 대구시청
        # (37.4563, 126.7052, "인천광역시 중구"),      # 인천시청
        # (36.3504, 127.3845, "대전광역시 서구"),      # 대전시청
        #(35.729331, 128.271345, "고령군"),
        (37.663455, 126.803364, "고양시")
        # (37.455301, 126.693331, "인천")
        # (35.912828, 128.803543, "대구가톨릭대학교") # DCU
    ]
    
    print("=" * 80)
    print("🌤️  기상청 초단기실황조회 API 테스트")
    print("=" * 80)
    
    for lat, lon, location_name in test_locations:
        print(f"\n📍 {location_name} (위도: {lat}, 경도: {lon})")
        print("-" * 50)
        
        # 위경도를 격자좌표로 변환
        nx, ny = convert_to_grid(lat, lon)
        print(f"격자좌표: X={nx}, Y={ny}")
        
        # 현재 날씨 정보 조회
        # result = weather_api.get_current_weather(nx, ny, location_name)

        # 향후 날씨 정보 조회
        result = weather_api.get_forecast_weather(nx, ny, location_name)
        
        if result['status'] == 'success':
            data = result['data']
            print("✅ API 호출 성공!")
            
            # 데이터가 리스트인지 단일 딕셔너리인지 확인
            if isinstance(data, list):
                # 예보 데이터 (리스트)
                print(f"📊 {len(data)}시간 예보 데이터 수신")
                print(f"기준일시: {data[0]['base_date']} {data[0]['base_time']}")
                
                for i, forecast in enumerate(data):
                    print(f"\n⏰ {i+1}시간 후 예보 ({forecast.get('fcst_date', '')} {forecast.get('fcst_time', '')}):")
                    
                    # 주요 기상 정보 출력
                    if forecast.get('temp') is not None:
                        print(f"   🌡️  기온: {forecast['temp']}°C")
                    if forecast.get('humidity') is not None:
                        print(f"   💧 습도: {forecast['humidity']}%")
                    if forecast.get('rain_1h') is not None:
                        print(f"   🌧️  1시간 강수량: {forecast['rain_1h']}mm")
                    if forecast.get('wind_speed') is not None:
                        print(f"   💨 풍속: {forecast['wind_speed']}m/s")
                    if forecast.get('wind_direction') is not None:
                        print(f"   🧭 풍향: {forecast['wind_direction']}°")
                    
                    # 예보 전용 정보
                    if forecast.get('pop') is not None:
                        print(f"   ☔ 강수확률: {forecast['pop']}%")
                    if forecast.get('pty'):
                        pty_map = {'0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}
                        print(f"   🌧️  강수형태: {pty_map.get(forecast['pty'], forecast['pty'])}")
                    if forecast.get('sky'):
                        sky_map = {'1': '맑음', '3': '구름많음', '4': '흐림'}
                        print(f"   ☁️  하늘상태: {sky_map.get(forecast['sky'], forecast['sky'])}")
                        
            else:
                # 현재 날씨 데이터 (단일 딕셔너리)
                print(f"기준일시: {data['base_date']} {data['base_time']}")
                
                # 주요 기상 정보 출력
                if data.get('temp') is not None:
                    print(f"🌡️  기온: {data['temp']}°C")
                if data.get('humidity') is not None:
                    print(f"💧 습도: {data['humidity']}%")
                if data.get('rain_1h') is not None:
                    print(f"🌧️  1시간 강수량: {data['rain_1h']}mm")
                if data.get('wind_speed') is not None:
                    print(f"💨 풍속: {data['wind_speed']}m/s")
                if data.get('wind_direction') is not None:
                    print(f"🧭 풍향: {data['wind_direction']}°")
            
            print(f"\n💾 데이터베이스 저장 완료")
            
        else:
            print("❌ API 호출 실패!")
            print(f"오류: {result['message']}")
    
    print("\n" + "=" * 80)
    print("테스트 완료! 데이터베이스에서 저장된 데이터를 확인해보세요.")
    print("=" * 80)

if __name__ == "__main__":
    main()