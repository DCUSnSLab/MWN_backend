#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
시장별 날씨 자동 조회 스케줄러

Market 테이블의 모든 시장에 대해 주기적으로 날씨 정보를 조회하고
Weather 테이블에 저장하는 백그라운드 작업을 수행합니다.
"""

import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from app import app, db
from models import Market, Weather, User
from weather_api import KMAWeatherAPI, convert_to_grid
from fcm_integration.fcm_utils import weather_notification_service

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WeatherScheduler:
    """시장별 날씨 자동 조회 스케줄러"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.weather_api = None
        self.check_interval_minutes = int(os.environ.get('WEATHER_CHECK_INTERVAL_MINUTES', 30))
        
        # 기상청 API 초기화
        service_key = os.environ.get('KMA_SERVICE_KEY')
        if service_key:
            self.weather_api = KMAWeatherAPI(service_key)
            logger.info(f"기상청 API 초기화 완료 (서비스키: {service_key[:10]}***)")
        else:
            logger.error("KMA_SERVICE_KEY가 설정되지 않았습니다!")
    
    def collect_market_weather_data(self):
        """모든 시장의 날씨 데이터 수집"""
        if not self.weather_api:
            logger.error("기상청 API가 초기화되지 않았습니다.")
            return
        
        with app.app_context():
            try:
                # 활성화된 시장 조회
                markets = Market.query.filter_by(is_active=True).all()
                logger.info(f"총 {len(markets)}개 시장의 날씨 데이터 수집 시작")
                
                success_count = 0
                error_count = 0
                
                for market in markets:
                    try:
                        # 위경도가 있는 시장만 처리
                        if market.latitude is None or market.longitude is None:
                            logger.warning(f"시장 '{market.name}': 위경도 정보 없음, 건너뜀")
                            continue
                        
                        # 격자 좌표 변환
                        nx, ny = convert_to_grid(market.latitude, market.longitude)
                        
                        # 현재 날씨 조회
                        current_result = self.weather_api.get_current_weather(
                            nx, ny, f"{market.name} ({market.location})"
                        )
                        
                        if current_result['status'] == 'success':
                            logger.info(f"시장 '{market.name}': 현재 날씨 수집 성공")
                            success_count += 1
                            
                            # 날씨 알림 조건 확인 및 전송
                            self._check_and_send_weather_alerts(market, current_result['data'])
                        else:
                            logger.error(f"시장 '{market.name}': 현재 날씨 수집 실패 - {current_result['message']}")
                            error_count += 1
                            continue
                        
                        # 예보 데이터 조회
                        forecast_result = self.weather_api.get_forecast_weather(
                            nx, ny, f"{market.name} ({market.location})"
                        )
                        
                        if forecast_result['status'] == 'success':
                            logger.info(f"시장 '{market.name}': 예보 데이터 수집 성공 ({len(forecast_result['data'])}시간)")
                        else:
                            logger.error(f"시장 '{market.name}': 예보 데이터 수집 실패 - {forecast_result['message']}")
                            error_count += 1
                        
                    except Exception as e:
                        logger.error(f"시장 '{market.name}': 처리 중 오류 - {str(e)}")
                        error_count += 1
                
                # 수집 결과 요약
                total_count = success_count + error_count
                logger.info(f"날씨 데이터 수집 완료: 성공 {success_count}개, 실패 {error_count}개 (총 {total_count}개)")
                
                # 데이터베이스 통계
                weather_count = Weather.query.count()
                current_count = Weather.query.filter_by(api_type='current').count()
                forecast_count = Weather.query.filter_by(api_type='forecast').count()
                logger.info(f"데이터베이스 날씨 데이터: 총 {weather_count}개 (현재 {current_count}개, 예보 {forecast_count}개)")
                
            except Exception as e:
                logger.error(f"날씨 데이터 수집 중 전체 오류: {str(e)}")
    
    def collect_weather_for_market(self, market_id):
        """특정 시장의 날씨 데이터 수집"""
        if not self.weather_api:
            logger.error("기상청 API가 초기화되지 않았습니다.")
            return False
        
        with app.app_context():
            try:
                market = Market.query.get(market_id)
                if not market:
                    logger.error(f"시장 ID {market_id}를 찾을 수 없습니다.")
                    return False
                
                if market.latitude is None or market.longitude is None:
                    logger.error(f"시장 '{market.name}': 위경도 정보가 없습니다.")
                    return False
                
                # 격자 좌표 변환
                nx, ny = convert_to_grid(market.latitude, market.longitude)
                location_name = f"{market.name} ({market.location})"
                
                # 현재 날씨 및 예보 데이터 수집
                current_result = self.weather_api.get_current_weather(nx, ny, location_name)
                forecast_result = self.weather_api.get_forecast_weather(nx, ny, location_name)
                
                success = (current_result['status'] == 'success' and 
                          forecast_result['status'] == 'success')
                
                if success:
                    logger.info(f"시장 '{market.name}': 날씨 데이터 수집 성공")
                else:
                    logger.error(f"시장 '{market.name}': 날씨 데이터 수집 실패")
                
                return success
                
            except Exception as e:
                logger.error(f"시장 ID {market_id} 날씨 수집 중 오류: {str(e)}")
                return False
    
    def get_weather_statistics(self):
        """날씨 데이터 통계 조회"""
        with app.app_context():
            try:
                stats = {
                    'total_weather_records': Weather.query.count(),
                    'current_weather_records': Weather.query.filter_by(api_type='current').count(),
                    'forecast_weather_records': Weather.query.filter_by(api_type='forecast').count(),
                    'active_markets': Market.query.filter_by(is_active=True).count(),
                    'markets_with_coordinates': Market.query.filter(
                        Market.latitude.isnot(None), 
                        Market.longitude.isnot(None)
                    ).count(),
                    'latest_weather_update': None
                }
                
                # 최근 날씨 업데이트 시간
                latest_weather = Weather.query.order_by(Weather.created_at.desc()).first()
                if latest_weather:
                    stats['latest_weather_update'] = latest_weather.created_at.isoformat()
                
                return stats
                
            except Exception as e:
                logger.error(f"통계 조회 중 오류: {str(e)}")
                return {}
    
    def _check_and_send_weather_alerts(self, market, weather_data):
        """날씨 알림 조건 확인 및 전송"""
        try:
            # 심각한 날씨 조건 확인
            severe_conditions = self._check_severe_weather_conditions(weather_data)
            
            if severe_conditions:
                logger.info(f"시장 '{market.name}': 심각한 날씨 조건 감지 - {severe_conditions}")
                
                # 해당 지역 관련 사용자들 조회 (위치 기반)
                location_users = User.query.filter(
                    User.location.contains(market.location.split()[0]),  # 첫 번째 단어로 지역 매칭
                    User.is_active == True,
                    User.fcm_enabled == True,
                    User.fcm_token.isnot(None)
                ).all()
                
                if location_users:
                    # 지역별 날씨 알림 전송
                    result = weather_notification_service.send_weather_alert(
                        users=location_users,
                        weather_data={
                            'location_name': f"{market.name} ({market.location})",
                            'temp': weather_data.get('temp'),
                            'humidity': weather_data.get('humidity'),
                            'rain_1h': weather_data.get('rain_1h', 0),
                            'created_at': datetime.utcnow()
                        },
                        alert_type="severe_weather"
                    )
                    logger.info(f"지역 알림 전송 완료: {result}")
                
                # 전체 심각한 날씨 알림 (주제 기반)
                severe_result = weather_notification_service.send_severe_weather_alert(
                    location=f"{market.name} ({market.location})",
                    weather_condition=severe_conditions
                )
                logger.info(f"전체 심각한 날씨 알림 전송: {severe_result}")
                
        except Exception as e:
            logger.error(f"날씨 알림 전송 중 오류: {str(e)}")
    
    def _check_severe_weather_conditions(self, weather_data):
        """심각한 날씨 조건 확인"""
        conditions = []
        
        temp = weather_data.get('temp')
        rain = weather_data.get('rain_1h', 0)
        wind_speed = weather_data.get('wind_speed', 0)
        
        # 기온 조건
        if temp is not None:
            if temp >= 35:
                conditions.append("폭염")
            elif temp <= -10:
                conditions.append("한파")
        
        # 강수량 조건
        if rain is not None and rain > 10:
            conditions.append("호우")
        
        # 풍속 조건
        if wind_speed is not None and wind_speed > 14:  # 14m/s 이상은 강풍
            conditions.append("강풍")
        
        return ", ".join(conditions) if conditions else None
    
    def start(self):
        """스케줄러 시작"""
        if not self.weather_api:
            logger.error("기상청 API가 설정되지 않아 스케줄러를 시작할 수 없습니다.")
            return
        
        # 주기적 작업 등록
        self.scheduler.add_job(
            func=self.collect_market_weather_data,
            trigger=IntervalTrigger(minutes=self.check_interval_minutes),
            id='weather_collection_job',
            name='시장별 날씨 데이터 수집',
            replace_existing=True
        )
        
        # 스케줄러 시작
        self.scheduler.start()
        logger.info(f"날씨 스케줄러 시작됨 (주기: {self.check_interval_minutes}분)")
        
        # 즉시 한 번 실행
        logger.info("초기 날씨 데이터 수집 시작...")
        self.collect_market_weather_data()
    
    def stop(self):
        """스케줄러 정지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("날씨 스케줄러 정지됨")
    
    def get_job_status(self):
        """작업 상태 조회"""
        jobs = self.scheduler.get_jobs()
        return {
            'scheduler_running': self.scheduler.running,
            'job_count': len(jobs),
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]
        }

# 전역 스케줄러 인스턴스
weather_scheduler = WeatherScheduler()

def start_weather_scheduler():
    """날씨 스케줄러 시작 (외부에서 호출용)"""
    weather_scheduler.start()

def stop_weather_scheduler():
    """날씨 스케줄러 정지 (외부에서 호출용)"""
    weather_scheduler.stop()

def get_scheduler_status():
    """스케줄러 상태 조회 (외부에서 호출용)"""
    return weather_scheduler.get_job_status()

def get_weather_stats():
    """날씨 데이터 통계 조회 (외부에서 호출용)"""
    return weather_scheduler.get_weather_statistics()

if __name__ == "__main__":
    # 스크립트로 직접 실행 시
    import signal
    import sys
    
    def signal_handler(sig, frame):
        logger.info("종료 신호 수신됨")
        weather_scheduler.stop()
        sys.exit(0)
    
    # 신호 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 스케줄러 시작
    weather_scheduler.start()
    
    try:
        # 무한 대기 (스케줄러가 백그라운드에서 실행)
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("키보드 인터럽트로 종료")
        weather_scheduler.stop()