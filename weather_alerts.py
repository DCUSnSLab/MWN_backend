#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
날씨 기반 알림 시스템

사용자 관심 시장의 날씨 예보를 확인하고, 비가 올 가능성이 있는 경우
해당 사용자들에게 FCM 알림을 전송합니다.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from weather_api import KMAWeatherAPI
from models import Market, User, UserMarketInterest
from fcm_integration.fcm_utils import fcm_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherAlertSystem:
    """날씨 알림 시스템"""
    
    def __init__(self):
        """초기화"""
        self.service_key = os.environ.get('KMA_SERVICE_KEY')
        if not self.service_key:
            logger.warning("KMA_SERVICE_KEY가 설정되지 않았습니다. 날씨 알림 기능이 제한됩니다.")
        
        self.weather_api = KMAWeatherAPI(self.service_key) if self.service_key else None
        
        # 알림 임계값 설정
        self.rain_probability_threshold = 30  # 강수확률 30% 이상
        self.forecast_hours = 24  # 향후 24시간 예보 확인
        
    def check_rain_forecast_for_market(self, market: Market, hours: int = None) -> Dict[str, Any]:
        """특정 시장의 비 예보 확인"""
        if not self.weather_api:
            return {'has_rain': False, 'error': 'Weather API not available'}
        
        hours = hours or self.forecast_hours
        
        try:
            # 시장의 격자 좌표로 예보 조회
            forecast_data = self.weather_api.get_forecast_weather(
                market.nx, 
                market.ny, 
                market.name
            )
            
            if not forecast_data.get('success'):
                return {'has_rain': False, 'error': 'Failed to get forecast data'}
            
            # 예보 데이터에서 비 가능성 확인
            forecasts = forecast_data.get('data', [])
            rain_alerts = []
            
            current_time = datetime.now()
            target_time = current_time + timedelta(hours=hours)
            
            for forecast in forecasts:
                try:
                    # 예보 시간 파싱
                    fcst_datetime = datetime.strptime(
                        f"{forecast['fcst_date']}{forecast['fcst_time'].zfill(4)}", 
                        "%Y%m%d%H%M"
                    )
                    
                    # 지정된 시간 범위 내 예보만 확인
                    if fcst_datetime <= target_time:
                        pop = forecast.get('pop')  # 강수확률
                        pty = forecast.get('pty', '0')  # 강수형태
                        
                        # 강수확률이 임계값 이상이거나 강수형태가 있는 경우
                        if (pop and pop >= self.rain_probability_threshold) or (pty and pty != '0'):
                            rain_alerts.append({
                                'datetime': fcst_datetime.isoformat(),
                                'pop': pop,
                                'pty': pty,
                                'description': self._get_precipitation_description(pty)
                            })
                            
                except (ValueError, TypeError) as e:
                    logger.warning(f"예보 데이터 파싱 오류: {e}")
                    continue
            
            return {
                'has_rain': len(rain_alerts) > 0,
                'market_name': market.name,
                'alerts': rain_alerts,
                'checked_hours': hours
            }
            
        except Exception as e:
            logger.error(f"시장 {market.name}의 비 예보 확인 중 오류: {e}")
            return {'has_rain': False, 'error': str(e)}
    
    def _get_precipitation_description(self, pty: str) -> str:
        """강수형태 코드를 설명으로 변환"""
        descriptions = {
            '0': '없음',
            '1': '비',
            '2': '비/눈',
            '3': '눈',
            '4': '소나기'
        }
        return descriptions.get(str(pty), '알 수 없음')
    
    def send_rain_alert_to_users(self, market: Market, rain_info: Dict[str, Any]) -> Dict[str, Any]:
        """시장에 관심을 가진 사용자들에게 비 알림 전송"""
        try:
            # 해당 시장에 관심을 가진 사용자들 조회
            interested_users = market.get_interested_users()
            
            if not interested_users:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자가 없습니다.',
                    'sent_count': 0
                }
            
            # FCM 토큰 수집
            fcm_tokens = []
            valid_users = []
            
            for user in interested_users:
                if user.can_receive_fcm():
                    fcm_tokens.append(user.fcm_token)
                    valid_users.append(user)
            
            if not fcm_tokens:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자 중 FCM 알림을 받을 수 있는 사용자가 없습니다.',
                    'sent_count': 0
                }
            
            # 알림 메시지 생성
            alerts = rain_info.get('alerts', [])
            if alerts:
                first_alert = alerts[0]
                pop = first_alert.get('pop')
                description = first_alert.get('description', '비')
                
                if pop:
                    title = f"🌧️ {market.name} 비 예보 알림"
                    body = f"향후 {rain_info['checked_hours']}시간 내에 {description} 가능성이 {pop}%입니다."
                else:
                    title = f"🌧️ {market.name} 강수 예보 알림"
                    body = f"향후 {rain_info['checked_hours']}시간 내에 {description}이(가) 예상됩니다."
            else:
                title = f"🌧️ {market.name} 날씨 알림"
                body = f"향후 {rain_info['checked_hours']}시간 내에 비가 올 가능성이 있습니다."
            
            # FCM 알림 전송
            notification_data = {
                'type': 'rain_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': rain_info.get('alerts', [])
            }
            
            result = fcm_service.send_multicast(
                tokens=fcm_tokens,
                title=title,
                body=body,
                data=notification_data
            )
            
            success_count = result.get('success_count', 0) if result else 0
            
            logger.info(f"{market.name} 비 알림: {len(valid_users)}명 중 {success_count}명에게 전송 성공")
            
            return {
                'success': True,
                'message': f'{market.name} 비 알림이 전송되었습니다.',
                'sent_count': success_count,
                'total_users': len(valid_users),
                'fcm_result': result
            }
            
        except Exception as e:
            logger.error(f"{market.name} 비 알림 전송 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0
            }
    
    def check_all_markets_and_send_alerts(self, hours: int = None) -> Dict[str, Any]:
        """모든 관심 시장의 비 예보를 확인하고 알림 전송"""
        hours = hours or self.forecast_hours
        
        logger.info(f"향후 {hours}시간 비 예보 확인 및 알림 전송 시작")
        
        try:
            # 관심을 가진 사용자가 있는 활성 시장들 조회
            from app import app, db
            
            with app.app_context():
                markets_with_interest = db.session.query(Market).join(
                    UserMarketInterest,
                    Market.id == UserMarketInterest.market_id
                ).filter(
                    Market.is_active == True,
                    UserMarketInterest.is_active == True,
                    UserMarketInterest.notification_enabled == True
                ).distinct().all()
                
                if not markets_with_interest:
                    return {
                        'success': True,
                        'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                        'checked_markets': 0,
                        'alerts_sent': 0
                    }
                
                logger.info(f"{len(markets_with_interest)}개 시장의 비 예보 확인 중...")
                
                checked_count = 0
                alerts_sent = 0
                results = []
                
                for market in markets_with_interest:
                    try:
                        # 시장별 비 예보 확인
                        rain_info = self.check_rain_forecast_for_market(market, hours)
                        checked_count += 1
                        
                        if rain_info.get('has_rain'):
                            # 비 예보가 있는 경우 알림 전송
                            alert_result = self.send_rain_alert_to_users(market, rain_info)
                            
                            if alert_result.get('success'):
                                alerts_sent += alert_result.get('sent_count', 0)
                            
                            results.append({
                                'market': market.name,
                                'rain_forecast': True,
                                'alert_result': alert_result
                            })
                        else:
                            results.append({
                                'market': market.name,
                                'rain_forecast': False,
                                'message': '비 예보 없음'
                            })
                            
                    except Exception as e:
                        logger.error(f"시장 {market.name} 처리 중 오류: {e}")
                        results.append({
                            'market': market.name,
                            'error': str(e)
                        })
                
                logger.info(f"비 예보 확인 완료: {checked_count}개 시장 확인, {alerts_sent}건 알림 전송")
                
                return {
                    'success': True,
                    'message': f'{checked_count}개 시장 확인 완료, {alerts_sent}건 알림 전송',
                    'checked_markets': checked_count,
                    'alerts_sent': alerts_sent,
                    'results': results
                }
                
        except Exception as e:
            logger.error(f"전체 시장 비 예보 확인 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'checked_markets': 0,
                'alerts_sent': 0
            }

# 전역 인스턴스
weather_alert_system = WeatherAlertSystem()

def check_and_send_rain_alerts(hours: int = 24) -> Dict[str, Any]:
    """비 예보 확인 및 알림 전송 (외부 호출용)"""
    return weather_alert_system.check_all_markets_and_send_alerts(hours)

def check_market_rain_forecast(market_id: int, hours: int = 24) -> Dict[str, Any]:
    """특정 시장의 비 예보 확인 (외부 호출용)"""
    from app import app
    
    with app.app_context():
        market = Market.query.get(market_id)
        if not market:
            return {'error': '시장을 찾을 수 없습니다.'}
        
        return weather_alert_system.check_rain_forecast_for_market(market, hours)