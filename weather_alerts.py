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
from models import Market, User, UserMarketInterest, MarketAlarmLog
from fcm_integration.fcm_utils import fcm_service
from database import db

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

        # 기본 알림 임계값 설정 (시장별 설정이 없을 때 사용)
        self.default_thresholds = {
            'rain_probability': 30,  # 강수확률 30% 이상
            'high_temp': 33,  # 폭염: 33도 이상
            'low_temp': -12,  # 한파: -12도 이하
            'wind_speed': 14,  # 강풍: 14m/s 이상
            'snow_amount': 1,  # 적설량: 1cm 이상
        }
        self.forecast_hours = 24  # 향후 24시간 예보 확인

    def get_market_thresholds(self, market: Market) -> Dict[str, Any]:
        """
        시장의 알림 조건 가져오기
        시장에 설정된 조건이 있으면 사용하고, 없으면 기본값 사용
        """
        alert_conditions = market.alert_conditions

        if not alert_conditions:
            # 기본값 사용
            return {
                'enabled': True,
                'rain_probability': self.default_thresholds['rain_probability'],
                'high_temp': self.default_thresholds['high_temp'],
                'low_temp': self.default_thresholds['low_temp'],
                'wind_speed': self.default_thresholds['wind_speed'],
                'snow_enabled': True,
                'rain_enabled': True,
                'temp_enabled': True,
                'wind_enabled': True
            }

        # 시장에 설정된 조건 사용
        return {
            'enabled': alert_conditions.get('enabled', True),
            'rain_probability': alert_conditions.get('rain_probability', self.default_thresholds['rain_probability']),
            'high_temp': alert_conditions.get('high_temp', self.default_thresholds['high_temp']),
            'low_temp': alert_conditions.get('low_temp', self.default_thresholds['low_temp']),
            'wind_speed': alert_conditions.get('wind_speed', self.default_thresholds['wind_speed']),
            'snow_enabled': alert_conditions.get('snow_enabled', True),
            'rain_enabled': alert_conditions.get('rain_enabled', True),
            'temp_enabled': alert_conditions.get('temp_enabled', True),
            'wind_enabled': alert_conditions.get('wind_enabled', True)
        }
        
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
            
            if forecast_data.get('status') != 'success':
                error_msg = forecast_data.get('message', 'Failed to get forecast data')
                return {'has_rain': False, 'error': error_msg}
            
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
                        if (pop and pop >= self.thresholds['rain_probability']) or (pty and pty != '0'):
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
            
            # FCM 토큰 수집 (방해금지 시간 체크 포함)
            fcm_tokens = []
            valid_users = []

            for user in interested_users:
                if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
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
            import json
            notification_data = {
                'type': 'rain_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': json.dumps(rain_info.get('alerts', []), ensure_ascii=False)  # JSON 문자열로 변환
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
                ).distinct(Market.id).all()
                
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

    def check_all_weather_conditions_for_market(self, market: Market, hours: int = None) -> Dict[str, Any]:
        """특정 시장의 모든 날씨 조건 확인 (비, 폭염, 한파, 강풍 등) - 시장별 설정 적용"""
        if not self.weather_api:
            return {'has_alerts': False, 'error': 'Weather API not available'}

        hours = hours or self.forecast_hours

        # 시장별 알림 조건 가져오기
        thresholds = self.get_market_thresholds(market)

        # 알림이 비활성화된 시장은 체크하지 않음
        if not thresholds['enabled']:
            logger.debug(f"시장 {market.name}의 알림이 비활성화되어 있습니다.")
            return {'has_alerts': False, 'message': '알림이 비활성화되어 있습니다.'}

        try:
            # 시장의 격자 좌표로 예보 조회
            forecast_data = self.weather_api.get_forecast_weather(
                market.nx,
                market.ny,
                market.name
            )

            if forecast_data.get('status') != 'success':
                error_msg = forecast_data.get('message', 'Failed to get forecast data')
                return {'has_alerts': False, 'error': error_msg}

            # 예보 데이터에서 다양한 날씨 조건 확인
            forecasts = forecast_data.get('data', [])
            all_alerts = {
                'rain': [],
                'high_temp': [],
                'low_temp': [],
                'strong_wind': [],
                'snow': []
            }

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
                        tmp = forecast.get('tmp')  # 기온
                        wsd = forecast.get('wsd')  # 풍속
                        sno = forecast.get('sno', 0)  # 적설량

                        alert_item = {
                            'datetime': fcst_datetime.isoformat(),
                            'time_str': fcst_datetime.strftime('%m월 %d일 %H시')
                        }

                        # 1. 비/눈 확인 (rain_enabled가 True일 때만)
                        if thresholds['rain_enabled']:
                            if (pop and pop >= thresholds['rain_probability']) or (pty and pty != '0'):
                                all_alerts['rain'].append({
                                    **alert_item,
                                    'pop': pop,
                                    'pty': pty,
                                    'description': self._get_precipitation_description(pty)
                                })

                                # 눈인 경우 별도 확인 (snow_enabled가 True일 때만)
                                if thresholds['snow_enabled'] and pty in ['2', '3'] and sno and sno >= self.default_thresholds['snow_amount']:
                                    all_alerts['snow'].append({
                                        **alert_item,
                                        'snow_amount': sno,
                                        'description': f"적설량 {sno}cm 예상"
                                    })

                        # 2. 폭염 확인 (temp_enabled가 True일 때만)
                        if thresholds['temp_enabled'] and tmp and tmp >= thresholds['high_temp']:
                            all_alerts['high_temp'].append({
                                **alert_item,
                                'temperature': tmp,
                                'description': f"폭염 주의 (기온 {tmp}°C)"
                            })

                        # 3. 한파 확인 (temp_enabled가 True일 때만)
                        if thresholds['temp_enabled'] and tmp and tmp <= thresholds['low_temp']:
                            all_alerts['low_temp'].append({
                                **alert_item,
                                'temperature': tmp,
                                'description': f"한파 주의 (기온 {tmp}°C)"
                            })

                        # 4. 강풍 확인 (wind_enabled가 True일 때만)
                        if thresholds['wind_enabled'] and wsd and wsd >= thresholds['wind_speed']:
                            all_alerts['strong_wind'].append({
                                **alert_item,
                                'wind_speed': wsd,
                                'description': f"강풍 주의 (풍속 {wsd}m/s)"
                            })

                except (ValueError, TypeError) as e:
                    logger.warning(f"예보 데이터 파싱 오류: {e}")
                    continue

            # 알림이 있는 조건만 필터링
            active_alerts = {k: v for k, v in all_alerts.items() if len(v) > 0}

            return {
                'has_alerts': len(active_alerts) > 0,
                'market_name': market.name,
                'alerts': active_alerts,
                'checked_hours': hours,
                'thresholds_used': thresholds  # 사용된 임계값 정보 포함
            }

        except Exception as e:
            logger.error(f"시장 {market.name}의 날씨 조건 확인 중 오류: {e}")
            return {'has_alerts': False, 'error': str(e)}

    def send_weather_alert_to_users(self, market: Market, weather_info: Dict[str, Any]) -> Dict[str, Any]:
        """시장에 관심을 가진 사용자들에게 날씨 알림 전송 (모든 조건)"""
        try:
            # 해당 시장에 관심을 가진 사용자들 조회
            interested_users = market.get_interested_users()

            if not interested_users:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자가 없습니다.',
                    'sent_count': 0
                }

            # FCM 토큰 수집 (방해금지 시간 체크 포함)
            fcm_tokens = []
            valid_users = []

            for user in interested_users:
                if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
                    fcm_tokens.append(user.fcm_token)
                    valid_users.append(user)

            if not fcm_tokens:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자 중 FCM 알림을 받을 수 있는 사용자가 없습니다.',
                    'sent_count': 0
                }

            # 알림 메시지 생성 (우선순위: 폭염 > 한파 > 강풍 > 비/눈)
            alerts = weather_info.get('alerts', {})
            title, body = self._create_weather_alert_message(market.name, alerts, weather_info['checked_hours'])

            # FCM 알림 전송
            import json
            notification_data = {
                'type': 'weather_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': json.dumps(alerts, ensure_ascii=False)  # JSON 문자열로 변환
            }

            result = fcm_service.send_multicast(
                tokens=fcm_tokens,
                title=title,
                body=body,
                data=notification_data
            )

            success_count = result.get('success_count', 0) if result else 0
            failure_count = result.get('failure_count', 0) if result else len(valid_users)

            logger.info(f"{market.name} 날씨 알림: {len(valid_users)}명 중 {success_count}명에게 전송 성공")

            # 데이터베이스에 알림 로그 기록
            try:
                # 알림 타입 결정 (우선순위: high_temp > low_temp > strong_wind > snow > rain)
                alert_type = None
                alert_data = None
                temperature = None
                rain_probability = None
                wind_speed = None
                precipitation_type = None
                forecast_time = None

                if alerts.get('high_temp'):
                    alert_type = 'high_temp'
                    alert_data = alerts['high_temp'][0]
                    temperature = alert_data.get('temperature')
                    forecast_time = alert_data.get('time_str')
                elif alerts.get('low_temp'):
                    alert_type = 'low_temp'
                    alert_data = alerts['low_temp'][0]
                    temperature = alert_data.get('temperature')
                    forecast_time = alert_data.get('time_str')
                elif alerts.get('strong_wind'):
                    alert_type = 'strong_wind'
                    alert_data = alerts['strong_wind'][0]
                    wind_speed = alert_data.get('wind_speed')
                    forecast_time = alert_data.get('time_str')
                elif alerts.get('snow'):
                    alert_type = 'snow'
                    alert_data = alerts['snow'][0]
                    precipitation_type = 'snow'
                    forecast_time = alert_data.get('time_str')
                elif alerts.get('rain'):
                    alert_type = 'rain'
                    alert_data = alerts['rain'][0]
                    rain_probability = alert_data.get('pop')
                    precipitation_type = alert_data.get('description')
                    forecast_time = alert_data.get('time_str')

                # MarketAlarmLog 레코드 생성
                if alert_type and alert_data:
                    alarm_log = MarketAlarmLog(
                        market_id=market.id,
                        alert_type=alert_type,
                        alert_title=title,
                        alert_body=body,
                        total_users=len(valid_users),
                        success_count=success_count,
                        failure_count=failure_count,
                        weather_data=alerts,  # JSON 필드로 전체 알림 데이터 저장
                        temperature=temperature,
                        rain_probability=rain_probability,
                        wind_speed=wind_speed,
                        precipitation_type=precipitation_type,
                        forecast_time=forecast_time,
                        checked_hours=weather_info.get('checked_hours')
                    )

                    db.session.add(alarm_log)
                    db.session.commit()

                    logger.info(f"{market.name} 알림 로그 데이터베이스 기록 완료 (ID: {alarm_log.id})")
                else:
                    logger.warning(f"{market.name} 알림 타입을 결정할 수 없어 로그를 기록하지 못했습니다.")

            except Exception as log_error:
                logger.error(f"{market.name} 알림 로그 데이터베이스 기록 실패: {log_error}")
                db.session.rollback()
                # 로그 기록 실패는 전체 프로세스를 중단하지 않음

            return {
                'success': True,
                'message': f'{market.name} 날씨 알림이 전송되었습니다.',
                'sent_count': success_count,
                'total_users': len(valid_users),
                'fcm_result': result
            }

        except Exception as e:
            logger.error(f"{market.name} 날씨 알림 전송 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0
            }

    def _create_weather_alert_message(self, market_name: str, alerts: Dict, hours: int) -> tuple:
        """날씨 알림 메시지 생성 (우선순위에 따라)"""
        # 우선순위: 폭염 > 한파 > 강풍 > 눈 > 비
        if alerts.get('high_temp'):
            alert = alerts['high_temp'][0]
            temp = alert.get('temperature')

            # 폭염 단계 결정 (기온 기준)
            if temp >= 35:
                alert_level = "위험단계"
                temp_desc = "폭염"
            elif temp >= 33:
                alert_level = "경계단계"
                temp_desc = "폭염"
            else:
                alert_level = "주의단계"
                temp_desc = "고온"

            title = f"[{market_name} 폭염예보 - {alert_level}]"

            # 본문 생성
            time_str = alert['time_str']

            body = f"""{time_str}경 최고기온 {temp}°C 이상 {temp_desc}이 예상됩니다.

[조치1] 냉장·냉동식품의 보관온도를 점검하고, 변질우려 제품은 폐기 바랍니다.

[조치2] 상인 및 고객을 위한 냉방기 가동과 충분한 환기를 유지 바랍니다.

[조치3] 노약자 근무자는 충분한 휴식을 취하고, 음료수를 비치해 주세요.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""

            return (title, body)

        if alerts.get('low_temp'):
            alert = alerts['low_temp'][0]
            temp = alert.get('temperature')

            # 한파 단계 결정 (기온 기준)
            if temp <= -15:
                alert_level = "위험단계"
                temp_desc = "강한 한파"
            elif temp <= -12:
                alert_level = "경계단계"
                temp_desc = "한파"
            else:
                alert_level = "주의단계"
                temp_desc = "한파"

            title = f"[{market_name} 한파예보 - {alert_level}]"

            # 본문 생성
            time_str = alert['time_str']

            body = f"""{time_str}경 기온이 {temp}°C 이하로 떨어질 것으로 예상됩니다.

[조치1] 수도관과 보일러 배관의 동파 방지를 위해 보온 덮개를 설치 바랍니다.

[조치2] 난방기 과열 및 전열기 주변 인화물 정리를 철저히 해주세요.

[조치3] 점포 내 결빙구간(출입구, 배수로 등)을 미리 점검하고 제빙제를 비치 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""

            return (title, body)

        if alerts.get('strong_wind'):
            alert = alerts['strong_wind'][0]
            wind = alert.get('wind_speed')

            # 강풍 단계 결정 (풍속 기준)
            if wind >= 20:
                alert_level = "위험단계"
                wind_desc = "매우 강한 바람"
            elif wind >= 17:
                alert_level = "경계단계"
                wind_desc = "강풍"
            else:
                alert_level = "주의단계"
                wind_desc = "강풍"

            title = f"[{market_name} 강풍예보 - {alert_level}]"

            # 본문 생성
            time_str = alert['time_str']

            body = f"""{time_str}경부터 {market_name} 풍속 {wind}m/s 이상 {wind_desc}이 예상됩니다.

[조치1] 가스밸브·전열기 주변 인화성 물질(박스, 천 등)을 제거 바랍니다.

[조치2] 상인회 주관으로 순찰을 강화하고, 화재대피안내 및 방송 바랍니다.

[조치3] 비상소화장치(소화기·소화전) 위치를 확인하고 사용법을 숙지하세요.

[조치4] 출입구 주변 적재물을 정리하여 긴급대피 통로를 확보 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""

            return (title, body)

        if alerts.get('snow'):
            alert = alerts['snow'][0]
            snow = alert.get('snow_amount')

            # 폭설 단계 결정 (적설량 기준)
            if snow >= 10:
                alert_level = "경고단계"
                snow_desc = "폭설"
            elif snow >= 5:
                alert_level = "주의단계"
                snow_desc = "대설"
            else:
                alert_level = "관심단계"
                snow_desc = "적설"

            title = f"[{market_name} 폭설예보 - {alert_level}]"

            # 본문 생성
            time_str = alert['time_str']

            body = f"""{time_str}경부터 {market_name}에 적설량 {snow}cm 이상 {snow_desc}이 예상됩니다.

[조치1] 인근 가설천막 및 차양에 눈이 쌓이지 않도록 수시 점검 바랍니다.

[조치2] 지붕 위 적설은 붕괴 위험이 있으므로 제설장비를 이용해 즉시 제거 바랍니다.

[조치3] 통로 및 계단에는 미끄럼방지제(모래, 염화칼슘 등)를 살포해 주시기 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""

            return (title, body)

        if alerts.get('rain'):
            alert = alerts['rain'][0]
            pop = alert.get('pop')
            description = alert.get('description', '비')

            # 강수 단계 결정 (강수확률 기준)
            if pop and pop >= 70:
                alert_level = "주의단계"
                rain_desc = "폭우" if pop >= 80 else "강우"
            elif pop and pop >= 50:
                alert_level = "관심단계"
                rain_desc = "강우"
            else:
                alert_level = "관심단계"
                rain_desc = description

            title = f"[{market_name} {rain_desc}예보 - {alert_level}]"

            # 본문 생성
            time_str = alert['time_str']
            prob_str = f"강수확률 {pop}%" if pop else rain_desc

            body = f"""{time_str}경부터 {market_name} 인근지역 {prob_str} 예상됩니다.

[조치1] 시장 입구 및 주요 통로의 배수구 덮개를 열어 배수로 확보 바랍니다.

[조치2] 저지대 점포 및 창고 내 전기제품을 고지대로 이동시켜 주세요.

[조치3] 침수 대비를 위해 배수펌프 및 비닐커버를 사전에 점검 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""

            return (title, body)

    def send_individual_alert_to_user(self, user: User, market: Market, weather_info: Dict[str, Any]) -> bool:
        """개별 사용자에게 단일 시장 날씨 알림 전송"""
        try:
            alerts = weather_info.get('alerts', {})
            title, body = self._create_weather_alert_message(market.name, alerts, weather_info['checked_hours'])

            # FCM 알림 전송
            import json
            notification_data = {
                'type': 'weather_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': json.dumps(alerts, ensure_ascii=False)
            }

            return fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data
            )
        except Exception as e:
            logger.error(f"사용자 {user.id}에게 개별 알림 전송 실패: {e}")
            return False

    def send_summary_alert_to_user(self, user: User, alerts_list: List[Dict[str, Any]]) -> bool:
        """개별 사용자에게 요약된 날씨 알림 전송 (3개 이상 시장)"""
        try:
            market_names = [item['market'].name for item in alerts_list]
            count = len(market_names)
            
            # 제목 생성
            title = f"{count}개 시장 날씨 알림"
            
            # 본문 생성 (시장A, 시장B 외 N곳...)
            if count <= 2:
                markets_str = ", ".join(market_names)
            else:
                markets_str = f"{market_names[0]}, {market_names[1]} 외 {count-2}곳"
                
            body = f"{markets_str}에 비, 폭염 등 주의할 날씨가 예상됩니다. 앱에서 상세 내용을 확인하세요."

            # 데이터 페이로드 생성 (간소화)
            import json
            summary_data = []
            for item in alerts_list:
                market = item['market']
                alert_types = list(item['weather_info'].get('alerts', {}).keys())
                summary_data.append({
                    'market_id': market.id,
                    'market_name': market.name,
                    'types': alert_types
                })

            notification_data = {
                'type': 'weather_summary_alert',
                'count': str(count),
                'summary': json.dumps(summary_data, ensure_ascii=False)
            }

            return fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data
            )
        except Exception as e:
            logger.error(f"사용자 {user.id}에게 요약 알림 전송 실패: {e}")
            return False


    def check_all_markets_with_all_conditions(self, hours: int = None) -> Dict[str, Any]:
        """모든 관심 시장의 다양한 날씨 조건 확인 및 알림 전송 (사용자별 그룹화 적용)"""
        hours = hours or self.forecast_hours

        logger.info(f"향후 {hours}시간 날씨 조건 확인 및 알림 전송 시작 (Grouping 적용)")

        try:
            # 1. 정보를 수집할 활성 시장 및 사용자 조회
            from app import app, db

            with app.app_context():
                markets_with_interest = db.session.query(Market).join(
                    UserMarketInterest,
                    Market.id == UserMarketInterest.market_id
                ).filter(
                    Market.is_active == True,
                    UserMarketInterest.is_active == True,
                    UserMarketInterest.notification_enabled == True
                ).distinct(Market.id).all()

                if not markets_with_interest:
                    return {
                        'success': True,
                        'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                        'checked_markets': 0,
                        'alerts_sent': 0
                    }

                logger.info(f"{len(markets_with_interest)}개 시장의 날씨 조건 확인 중...")

                # 2. 시장별 날씨 확인 및 알림 대상 수집
                # 구조: active_market_alerts = [ { 'market': m, 'info': info, 'users': [u1, u2...] } ]
                active_market_alerts = []
                # 구조: user_batches = { user_id: { 'user': u, 'alerts': [ {'market': m, 'weather_info': info} ] } }
                user_batches = {}

                checked_count = 0
                
                for market in markets_with_interest:
                    try:
                        # 날씨 확인
                        weather_info = self.check_all_weather_conditions_for_market(market, hours)
                        checked_count += 1

                        if weather_info.get('has_alerts'):
                            # 알림이 필요한 경우만 처리
                            interested_users = market.get_interested_users()
                            valid_users = []

                            # 중복 체크 (Deduplication) - 시장 레벨에서 체크
                            # 주의: 사용자별로 그룹화해서 보내더라도, '이 시장에 대한 알림'이 최근에 나갔는지 체크는 필요함.
                            # 하지만 여기서는 '이벤트' 자체의 중복을 막는 것이므로, 
                            # 대표 알림 타입 하나로 체크하거나, 내부적으로직 체크해야 함.
                            # 간단히 하기 위해, 가장 우선순위 높은 알림 타입으로 중복 체크 수행
                            alerts = weather_info.get('alerts', {})
                            primary_alert_type = None
                            primary_forecast_time = None
                            
                            if alerts.get('high_temp'):
                                primary_alert_type = 'high_temp'
                                primary_forecast_time = alerts['high_temp'][0].get('time_str')
                            elif alerts.get('low_temp'):
                                primary_alert_type = 'low_temp'
                                primary_forecast_time = alerts['low_temp'][0].get('time_str')
                            elif alerts.get('strong_wind'):
                                primary_alert_type = 'strong_wind'
                                primary_forecast_time = alerts['strong_wind'][0].get('time_str')
                            elif alerts.get('snow'):
                                primary_alert_type = 'snow'
                                primary_forecast_time = alerts['snow'][0].get('time_str')
                            elif alerts.get('rain'):
                                primary_alert_type = 'rain'
                                primary_forecast_time = alerts['rain'][0].get('time_str')

                            if primary_alert_type and self._is_duplicate_alert(market.id, primary_alert_type, primary_forecast_time):
                                logger.info(f"시장 {market.name} 중복 알림으로 스킵")
                                continue

                            # 유효한 사용자 수집 및 배치 구성
                            for user in interested_users:
                                if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
                                    valid_users.append(user)
                                    
                                    if user.id not in user_batches:
                                        user_batches[user.id] = {'user': user, 'alerts': []}
                                    
                                    user_batches[user.id]['alerts'].append({
                                        'market': market,
                                        'weather_info': weather_info
                                    })
                            
                            # 시장별 알림 정보 저장 (나중에 로그 기록용)
                            active_market_alerts.append({
                                'market': market,
                                'weather_info': weather_info,
                                'users': valid_users,
                                'success_count': 0, # 전송 후 업데이트
                                'failure_count': 0,
                                'primary_alert_type': primary_alert_type, # 로그용
                                'primary_forecast_time': primary_forecast_time,
                                'alerts_data': alerts
                            })

                    except Exception as e:
                        logger.error(f"시장 {market.name} 처리 중 오류: {e}")

                # 3. 사용자별 알림 전송 (Grouping)
                logger.info(f"사용자 {len(user_batches)}명에게 알림 전송 시작")
                
                total_alerts_sent = 0
                
                for user_id, batch in user_batches.items():
                    user = batch['user']
                    user_alerts = batch['alerts']
                    
                    if not user_alerts:
                        continue
                        
                    is_summary = len(user_alerts) >= 3
                    
                    if is_summary:
                        # 요약 알림 전송
                        success = self.send_summary_alert_to_user(user, user_alerts)
                        if success:
                            total_alerts_sent += 1
                        
                        # 각 시장별 성공 카운트 업데이트
                        for item in user_alerts:
                            # 해당 시장의 active_market_alerts 항목 찾기
                            # 성능을 위해 매번 찾는건 비효율적일 수 있으나, 시장 수가 적으므로 허용
                            for m_alert in active_market_alerts:
                                if m_alert['market'].id == item['market'].id:
                                    if success:
                                        m_alert['success_count'] += 1
                                    else:
                                        m_alert['failure_count'] += 1
                                    break
                    else:
                        # 개별 알림 전송
                        for item in user_alerts:
                            success = self.send_individual_alert_to_user(user, item['market'], item['weather_info'])
                            if success:
                                total_alerts_sent += 1
                                
                            # 시장별 성공 카운트 업데이트
                            for m_alert in active_market_alerts:
                                if m_alert['market'].id == item['market'].id:
                                    if success:
                                        m_alert['success_count'] += 1
                                    else:
                                        m_alert['failure_count'] += 1
                                    break

                # 4. 로그 기록 (시장별로)
                for m_alert in active_market_alerts:
                    try:
                        market = m_alert['market']
                        # 성공한 건수가 있거나 실패한 건수가 있을 때만 기록 (대상 사용자가 없으면 스킵될 수 있음)
                        if m_alert['success_count'] > 0 or m_alert['failure_count'] > 0:
                            # 상세 데이터 추출
                            alerts = m_alert['alerts_data']
                            
                            # 로그 데이터 준비
                            temperature = None
                            rain_probability = None
                            wind_speed = None
                            precipitation_type = None
                            
                            if alerts.get('high_temp'): temperature = alerts['high_temp'][0].get('temperature')
                            elif alerts.get('low_temp'): temperature = alerts['low_temp'][0].get('temperature')
                            
                            if alerts.get('rain'): 
                                rain_probability = alerts['rain'][0].get('pop')
                                precipitation_type = alerts['rain'][0].get('description')
                                
                            if alerts.get('strong_wind'): wind_speed = alerts['strong_wind'][0].get('wind_speed')
                            if alerts.get('snow'): precipitation_type = 'snow'

                            # 알림 제목/본문은 대표값으로 (요약 알림으로 나갔을 수도 있지만, 로그에는 원본 이벤트 기록)
                            title, body = self._create_weather_alert_message(market.name, alerts, m_alert['weather_info']['checked_hours'])

                            alarm_log = MarketAlarmLog(
                                market_id=market.id,
                                alert_type=m_alert['primary_alert_type'] or 'unknown',
                                alert_title=title,
                                alert_body=body,
                                total_users=len(m_alert['users']),
                                success_count=m_alert['success_count'],
                                failure_count=m_alert['failure_count'],
                                weather_data=alerts,
                                temperature=temperature,
                                rain_probability=rain_probability,
                                wind_speed=wind_speed,
                                precipitation_type=precipitation_type,
                                forecast_time=m_alert['primary_forecast_time'],
                                checked_hours=m_alert['weather_info'].get('checked_hours')
                            )
                            db.session.add(alarm_log)
                    except Exception as e:
                        logger.error(f"로그 기록 중 오류 (시장: {m_alert['market'].name}): {e}")

                db.session.commit()
                
                logger.info(f"알림 처리 완료: {checked_count}개 시장 확인, {total_alerts_sent}건 메시지 전송 (요약 포함)")

                return {
                    'success': True,
                    'message': f'{checked_count}개 시장 확인 완료, 총 {total_alerts_sent}건 메시지 전송',
                    'checked_markets': checked_count,
                    'alerts_sent': total_alerts_sent,
                    'results': [] # 상세 결과는 생략 (구조가 복잡해짐)
                }

        except Exception as e:
            logger.error(f"전체 시장 날씨 조건 확인 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'checked_markets': 0,
                'alerts_sent': 0
            }

# 전역 인스턴스
weather_alert_system = WeatherAlertSystem()

def check_and_send_rain_alerts(hours: int = 24) -> Dict[str, Any]:
    """비 예보 확인 및 알림 전송 (외부 호출용) - 레거시 지원"""
    return weather_alert_system.check_all_markets_and_send_alerts(hours)

def check_and_send_all_weather_alerts(hours: int = 24) -> Dict[str, Any]:
    """모든 날씨 조건 확인 및 알림 전송 (외부 호출용)"""
    return weather_alert_system.check_all_markets_with_all_conditions(hours)

def check_market_rain_forecast(market_id: int, hours: int = 24) -> Dict[str, Any]:
    """특정 시장의 비 예보 확인 (외부 호출용)"""
    from app import app

    with app.app_context():
        market = Market.query.get(market_id)
        if not market:
            return {'error': '시장을 찾을 수 없습니다.'}

        return weather_alert_system.check_rain_forecast_for_market(market, hours)

def check_market_all_conditions(market_id: int, hours: int = 24) -> Dict[str, Any]:
    """특정 시장의 모든 날씨 조건 확인 (외부 호출용)"""
    from app import app

    with app.app_context():
        market = Market.query.get(market_id)
        if not market:
            return {'error': '시장을 찾을 수 없습니다.'}

        return weather_alert_system.check_all_weather_conditions_for_market(market, hours)

def send_test_weather_summary_to_all_users() -> Dict[str, Any]:
    """
    [테스트용] 모든 관심 시장의 날씨 요약을 조건 없이 사용자에게 알림 전송

    실제 날씨 조건(비, 폭염, 한파 등) 체크 없이 데이터베이스에 저장된
    최신 날씨 정보를 요약해서 관심 시장을 등록한 사용자들에게 전송합니다.

    Returns:
        Dict: 전송 결과
    """
    from app import app, db
    from models import Weather
    from datetime import datetime
    import json

    logger.info("테스트 날씨 요약 알림 전송 시작")

    try:
        with app.app_context():
            # 관심을 가진 사용자가 있는 활성 시장들 조회
            markets_with_interest = db.session.query(Market).join(
                UserMarketInterest,
                Market.id == UserMarketInterest.market_id
            ).filter(
                Market.is_active == True,
                Market.nx.isnot(None),
                Market.ny.isnot(None),
                UserMarketInterest.is_active == True,
                UserMarketInterest.notification_enabled == True
            ).distinct(Market.id).all()

            if not markets_with_interest:
                return {
                    'success': True,
                    'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                    'sent_count': 0
                }

            logger.info(f"{len(markets_with_interest)}개 시장의 날씨 요약 알림 전송 중...")

            total_sent = 0
            results = []

            for market in markets_with_interest:
                try:
                    # 데이터베이스에서 최신 날씨 데이터 조회
                    current_weather = Weather.query.filter_by(
                        nx=market.nx,
                        ny=market.ny,
                        api_type='current'
                    ).order_by(Weather.created_at.desc()).first()

                    # 최신 예보 데이터도 조회 (향후 날씨)
                    forecast_weather = Weather.query.filter_by(
                        nx=market.nx,
                        ny=market.ny,
                        api_type='forecast'
                    ).order_by(
                        Weather.base_date.desc(),
                        Weather.base_time.desc(),
                        Weather.fcst_date.asc(),
                        Weather.fcst_time.asc()
                    ).limit(6).all()  # 향후 6시간 정도

                    if not current_weather:
                        logger.warning(f"{market.name}: 날씨 데이터 없음")
                        results.append({
                            'market': market.name,
                            'success': False,
                            'message': '날씨 데이터 없음'
                        })
                        continue

                    # 해당 시장에 관심을 가진 사용자들 조회
                    interested_users = market.get_interested_users()

                    if not interested_users:
                        results.append({
                            'market': market.name,
                            'success': True,
                            'message': '관심 사용자 없음',
                            'sent_count': 0
                        })
                        continue

                    # FCM 토큰 수집 (방해금지 시간 체크 포함)
                    fcm_tokens = []
                    valid_users = []

                    for user in interested_users:
                        if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
                            fcm_tokens.append(user.fcm_token)
                            valid_users.append(user)

                    if not fcm_tokens:
                        results.append({
                            'market': market.name,
                            'success': True,
                            'message': 'FCM 알림을 받을 수 있는 사용자 없음',
                            'sent_count': 0
                        })
                        continue

                    # 날씨 요약 메시지 생성
                    title = f"☀️ {market.name} 날씨 정보"

                    # 현재 날씨 정보
                    temp = current_weather.temp if current_weather.temp is not None else '?'
                    humidity = current_weather.humidity if current_weather.humidity is not None else '?'
                    wind_speed = current_weather.wind_speed if current_weather.wind_speed is not None else '?'

                    # 강수 형태 확인
                    weather_condition = "맑음"
                    if current_weather.pty:
                        pty_map = {'0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}
                        weather_condition = pty_map.get(current_weather.pty, '맑음')

                    body = f"현재: {temp}°C, 습도 {humidity}%, 풍속 {wind_speed}m/s"
                    if weather_condition != "없음" and weather_condition != "맑음":
                        body += f"\n날씨: {weather_condition}"

                    # 향후 예보 정보 추가
                    if forecast_weather:
                        # 강수확률이 있는 예보 찾기
                        rain_forecasts = [f for f in forecast_weather if f.pop and f.pop >= 30]
                        if rain_forecasts:
                            max_pop = max([f.pop for f in rain_forecasts])
                            body += f"\n향후 강수확률: 최대 {int(max_pop)}%"

                    # 데이터 업데이트 시간
                    updated_time = current_weather.created_at.strftime('%H:%M') if current_weather.created_at else '?'
                    body += f"\n(업데이트: {updated_time})"

                    # FCM 알림 전송
                    notification_data = {
                        'type': 'weather_summary_test',
                        'market_id': str(market.id),
                        'market_name': market.name,
                        'temperature': str(temp),
                        'humidity': str(humidity),
                        'wind_speed': str(wind_speed),
                        'weather_condition': weather_condition,
                        'updated_at': updated_time
                    }

                    result = fcm_service.send_multicast(
                        tokens=fcm_tokens,
                        title=title,
                        body=body,
                        data=notification_data
                    )

                    success_count = result.get('success_count', 0) if result else 0
                    failure_count = result.get('failure_count', 0) if result else len(valid_users)

                    logger.info(f"{market.name} 날씨 요약: {len(valid_users)}명 중 {success_count}명에게 전송 성공")

                    total_sent += success_count

                    results.append({
                        'market': market.name,
                        'success': True,
                        'sent_count': success_count,
                        'failed_count': failure_count,
                        'weather_summary': {
                            'temp': temp,
                            'humidity': humidity,
                            'wind_speed': wind_speed,
                            'condition': weather_condition
                        }
                    })

                except Exception as e:
                    logger.error(f"시장 {market.name} 처리 중 오류: {e}")
                    results.append({
                        'market': market.name,
                        'success': False,
                        'error': str(e)
                    })

            logger.info(f"테스트 날씨 요약 알림 전송 완료: 총 {total_sent}건 전송")

            return {
                'success': True,
                'message': f'{len(markets_with_interest)}개 시장에 대해 총 {total_sent}건 알림 전송 완료',
                'total_markets': len(markets_with_interest),
                'total_sent': total_sent,
                'results': results
            }

    except Exception as e:
        logger.error(f"테스트 날씨 요약 알림 전송 중 오류: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'total_sent': 0
        }