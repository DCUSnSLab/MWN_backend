import requests
import json
from datetime import datetime, timedelta

class KMAWeatherAPI:
    """기상청 날씨 API 클래스"""
    
    def __init__(self, service_key):
        self.service_key = service_key
        # self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
        self.base_url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0"
        
    def get_current_weather(self, nx, ny, location_name=None):
        """
        초단기실황조회 API 호출
        
        Args:
            nx (int): 격자 X 좌표
            ny (int): 격자 Y 좌표  
            location_name (str): 지역명 (선택사항)
            
        Returns:
            dict: API 응답 데이터
        """
        # 현재 시간 기준으로 base_date, base_time 설정
        now = datetime.now()
        # 실황 자료는 매시 40분에 생성되므로, 40분 이전이면 이전 시간으로 설정
        if now.minute < 40:
            now = now - timedelta(hours=1)
            
        base_date = now.strftime("%Y%m%d")
        base_time = now.strftime("%H00")
        
        params = {
            'authKey': self.service_key,
            'pageNo': '1',
            'numOfRows': '1000',
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': str(nx),
            'ny': str(ny)
        }
        
        url = f"{self.base_url}/getUltraSrtNcst"
        
        try:
            response = requests.get(url, params=params)
            print(response.request.url)
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 검증
            if data['response']['header']['resultCode'] != '00':
                raise Exception(f"API Error: {data['response']['header']['resultMsg']}")
                
            items = data['response']['body']['items']['item']
            
            # 데이터베이스에 저장
            weather_data = self._parse_current_weather_data(items, base_date, base_time, nx, ny, location_name)
            weather_id = self._save_weather_data(weather_data)
            weather_data['saved_id'] = weather_id
            
            return {
                'status': 'success',
                'data': weather_data,
                'raw_response': data
            }
            
        except requests.exceptions.RequestException as e:
            print("except requests.exceptions.RequestException as e:")
            return {
                'status': 'error',
                'message': f"HTTP Error: {str(e)}"
            }
        except Exception as e:
            print("except Exception as e:")
            return {
                'status': 'error', 
                'message': f"Error: {str(e)}"
            }
    
    def get_forecast_weather(self, nx, ny, location_name=None):
        """
        초단기예보조회 API 호출
        
        Args:
            nx (int): 격자 X 좌표
            ny (int): 격자 Y 좌표
            location_name (str): 지역명 (선택사항)
            
        Returns:
            dict: API 응답 데이터
        """
        # 현재 시간 기준으로 base_date, base_time 설정
        now = datetime.now()
        # 예보 자료는 매시 30분에 생성되므로, 30분 이전이면 이전 시간으로 설정
        if now.minute < 30:
            now = now - timedelta(hours=1)
            
        base_date = now.strftime("%Y%m%d")
        base_time = now.strftime("%H30")
        
        params = {
            'authKey': self.service_key,
            'pageNo': '1',
            'numOfRows': '1000',
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': str(nx),
            'ny': str(ny)
        }
        
        url = f"{self.base_url}/getUltraSrtFcst"
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 검증
            if data['response']['header']['resultCode'] != '00':
                raise Exception(f"API Error: {data['response']['header']['resultMsg']}")
                
            items = data['response']['body']['items']['item']
            
            # 데이터베이스에 저장
            weather_forecasts = self._parse_forecast_weather_data(items, base_date, base_time, nx, ny, location_name)
            for weather_data in weather_forecasts:
                weather_id = self._save_weather_data(weather_data)
                weather_data['saved_id'] = weather_id
            
            return {
                'status': 'success',
                'data': weather_forecasts,
                'raw_response': data
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"HTTP Error: {str(e)}"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }
    
    def _parse_current_weather_data(self, items, base_date, base_time, nx, ny, location_name):
        """초단기실황 데이터 파싱"""
        # API 응답에서 실제 baseDate, baseTime 사용 (첫 번째 아이템에서 추출)
        if items and len(items) > 0:
            actual_base_date = items[0].get('baseDate', base_date)
            actual_base_time = items[0].get('baseTime', base_time)
        else:
            actual_base_date = base_date
            actual_base_time = base_time
            
        weather_data = {
            'base_date': actual_base_date,
            'base_time': actual_base_time,
            'nx': nx,
            'ny': ny,
            'api_type': 'current',
            'location_name': location_name
        }
        
        # 카테고리별 데이터 매핑
        category_mapping = {
            'T1H': 'temp',          # 기온
            'REH': 'humidity',      # 습도
            'RN1': 'rain_1h',       # 1시간 강수량
            'UUU': 'east_west_wind',    # 동서바람성분
            'VVV': 'north_south_wind',  # 남북바람성분
            'VEC': 'wind_direction',    # 풍향
            'WSD': 'wind_speed',    # 풍속
            'PTY': 'pty'            # 강수형태 (실황에서도 제공)
        }
        
        for item in items:
            category = item['category']
            if category in category_mapping:
                field_name = category_mapping[category]
                try:
                    if category == 'RN1' and item['obsrValue'] in ['', '강수없음', '없음', '0']:
                        weather_data[field_name] = 0.0
                    elif category == 'PTY':
                        # 강수형태는 문자열로 저장
                        weather_data[field_name] = item['obsrValue']
                    elif item['obsrValue'] != '':
                        weather_data[field_name] = float(item['obsrValue'])
                    else:
                        weather_data[field_name] = None
                except ValueError:
                    if category == 'RN1':
                        weather_data[field_name] = 0.0
                    elif category == 'PTY':
                        weather_data[field_name] = item['obsrValue']
                    else:
                        weather_data[field_name] = None
                
        return weather_data
    
    def _parse_forecast_weather_data(self, items, base_date, base_time, nx, ny, location_name):
        """초단기예보 데이터 파싱"""
        # 시간별로 그룹화
        forecast_groups = {}
        
        # API 응답에서 실제 baseDate, baseTime 사용 (첫 번째 아이템에서 추출)
        if items and len(items) > 0:
            actual_base_date = items[0].get('baseDate', base_date)
            actual_base_time = items[0].get('baseTime', base_time)
        else:
            actual_base_date = base_date
            actual_base_time = base_time
        
        for item in items:
            fcst_date = item['fcstDate']
            fcst_time = item['fcstTime']
            key = f"{fcst_date}_{fcst_time}"
            
            if key not in forecast_groups:
                forecast_groups[key] = {
                    'base_date': actual_base_date,
                    'base_time': actual_base_time,
                    'fcst_date': fcst_date,
                    'fcst_time': fcst_time,
                    'nx': nx,
                    'ny': ny,
                    'api_type': 'forecast',
                    'location_name': location_name
                }
            
            # 카테고리별 데이터 매핑
            category = item['category']
            fcst_value = item['fcstValue']
            
            try:
                if category == 'T1H':
                    forecast_groups[key]['temp'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'REH':
                    forecast_groups[key]['humidity'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'RN1':
                    if fcst_value in ['', '강수없음', '없음', '0']:
                        forecast_groups[key]['rain_1h'] = 0.0
                    else:
                        forecast_groups[key]['rain_1h'] = float(fcst_value)
                elif category == 'UUU':
                    forecast_groups[key]['east_west_wind'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'VVV':
                    forecast_groups[key]['north_south_wind'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'VEC':
                    forecast_groups[key]['wind_direction'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'WSD':
                    forecast_groups[key]['wind_speed'] = float(fcst_value) if fcst_value != '' else None
                elif category == 'PTY':
                    forecast_groups[key]['pty'] = fcst_value
                elif category == 'SKY':
                    forecast_groups[key]['sky'] = fcst_value
                elif category == 'LGT':
                    forecast_groups[key]['lightning'] = fcst_value  # 낙뢰
                    
            except ValueError:
                # 숫자로 변환할 수 없는 경우 기본값 처리
                if category == 'RN1':
                    forecast_groups[key]['rain_1h'] = 0.0
                elif category in ['PTY', 'SKY', 'LGT']:
                    forecast_groups[key][{
                        'PTY': 'pty', 
                        'SKY': 'sky', 
                        'LGT': 'lightning'
                    }[category]] = fcst_value
                else:
                    # 다른 숫자 필드는 None 처리
                    pass
        
        return list(forecast_groups.values())
    
    def _save_weather_data(self, weather_data):
        """날씨 데이터를 데이터베이스에 저장 (Flask 앱 컨텍스트가 있을 때만)"""
        try:
            # Flask 앱과 데이터베이스 모듈을 동적으로 import
            from app import db
            from models import Weather
            
            weather = Weather(**weather_data)
            db.session.add(weather)
            db.session.commit()
            return weather.id
        except ImportError:
            # Flask 앱 컨텍스트가 없는 경우 (예제 실행 시)
            print("ℹ️  데이터베이스 저장 건너뜀 (Flask 앱 컨텍스트 없음)")
            return None
        except Exception as e:
            try:
                from app import db
                db.session.rollback()
            except:
                pass
            print(f"⚠️  데이터베이스 저장 실패: {str(e)}")
            return None

# 좌표 변환 유틸리티 함수들
def convert_to_grid(lat, lon):
    """
    위경도를 기상청 격자좌표로 변환
    
    Args:
        lat (float): 위도
        lon (float): 경도
        
    Returns:
        tuple: (nx, ny) 격자 좌표
    """
    # 기상청 격자 변환 상수
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0     # 투영 위도1(degree)
    SLAT2 = 60.0     # 투영 위도2(degree)
    OLON = 126.0     # 기준점 경도(degree)
    OLAT = 38.0      # 기준점 위도(degree)
    XO = 43          # 기준점 X좌표(GRID)
    YO = 136         # 기준점 Y좌표(GRID)
    
    import math
    
    DEGRAD = math.pi / 180.0
    RADDEG = 180.0 / math.pi
    
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD
    
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    
    x = math.floor(ra * math.sin(theta) + XO + 0.5)
    y = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    
    return int(x), int(y)