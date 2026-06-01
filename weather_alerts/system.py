"""WeatherAlertSystem — 책임별 컴포넌트를 조립하는 facade.

외부에서 호출하는 메서드 시그니처(``check_*``, ``send_*``)는 그대로 유지.
"""

import logging
import os
import traceback
from typing import Any, Dict

from models import Market
from weather_api import KMAWeatherAPI

from weather_alerts.alarm_logger import (
    is_duplicate_alert,
    log_batch_market_alert,
    log_single_market_alert,
)
from weather_alerts.dispatcher import AlertDispatcher
from weather_alerts.evaluator import AlertEvaluator
from weather_alerts.messages import (
    build_weather_alert_message,
    precipitation_description,
)
from weather_alerts.repository import ForecastRepository
from weather_alerts.thresholds import (
    DEFAULT_FORECAST_HOURS,
    DEFAULT_THRESHOLDS,
    resolve_market_thresholds,
)

logger = logging.getLogger(__name__)


class WeatherAlertSystem:
    """날씨 알림 시스템 facade.

    외부에서 호출하는 인터페이스를 보존하면서, 실제 로직은 책임별 모듈에 위임한다.
    """

    def __init__(self):
        self.service_key = os.environ.get('KMA_SERVICE_KEY')
        if not self.service_key:
            logger.warning("KMA_SERVICE_KEY가 설정되지 않았습니다. 날씨 알림 기능이 제한됩니다.")

        self.weather_api = KMAWeatherAPI(self.service_key) if self.service_key else None

        # 시장별 설정이 없을 때 사용되는 기본값.
        self.default_thresholds = dict(DEFAULT_THRESHOLDS)
        self.forecast_hours = DEFAULT_FORECAST_HOURS

        self.repository = ForecastRepository(self.weather_api)
        self.evaluator = AlertEvaluator(self.repository, self.forecast_hours)
        self.dispatcher = AlertDispatcher()

    # ---- 임계값 / 보조 ----------------------------------------------------

    def get_market_thresholds(self, market: Market) -> Dict[str, Any]:
        return resolve_market_thresholds(market)

    def _get_forecast_from_db(self, nx: int, ny: int) -> Dict[str, Any]:
        return self.repository.get_forecast_from_db(nx, ny)

    def _get_precipitation_description(self, pty: str) -> str:
        return precipitation_description(pty)

    def _create_weather_alert_message(self, market_name, alerts, hours):
        return build_weather_alert_message(market_name, alerts, hours)

    def _is_duplicate_alert(self, market_id: int, alert_type: str, forecast_time: str) -> bool:
        return is_duplicate_alert(market_id, alert_type, forecast_time)

    # ---- 평가 -------------------------------------------------------------

    def check_rain_forecast_for_market(self, market: Market, hours: int = None) -> Dict[str, Any]:
        return self.evaluator.evaluate_rain(market, hours)

    def check_all_weather_conditions_for_market(self, market: Market, hours: int = None) -> Dict[str, Any]:
        return self.evaluator.evaluate_all_conditions(market, hours)

    # ---- 발송 -------------------------------------------------------------

    def send_rain_alert_to_users(self, market: Market, rain_info: Dict[str, Any]) -> Dict[str, Any]:
        return self.dispatcher.send_rain_alert(market, rain_info)

    def send_weather_alert_to_users(self, market: Market, weather_info: Dict[str, Any]) -> Dict[str, Any]:
        # 외부에서 직접 부르는 단일-시장 송신 경로. 발송 후 로그까지 기록.
        result = self.dispatcher.send_weather_alert(market, weather_info)

        if result.get('success') and 'valid_users' in result:
            log_single_market_alert(market, weather_info, result)
            # 외부 노출은 기존 슬림 포맷으로 정리.
            return {
                'success': True,
                'message': f'{market.name} 날씨 알림이 전송되었습니다.',
                'sent_count': result.get('sent_count', 0),
                'total_users': result.get('total_users', 0),
                'fcm_result': result.get('fcm_result'),
            }

        return result

    def send_individual_alert_to_user(self, user, market, weather_info) -> bool:
        return self.dispatcher.send_individual_alert(user, market, weather_info)

    def send_summary_alert_to_user(self, user, alerts_list) -> bool:
        return self.dispatcher.send_summary_alert(user, alerts_list)

    # ---- 오케스트레이션 -----------------------------------------------------

    def check_all_markets_and_send_alerts(self, hours: int = None) -> Dict[str, Any]:
        """레거시: 비 예보만 확인하고 시장 멀티캐스트로 발송."""
        hours = hours or self.forecast_hours

        logger.info(f"향후 {hours}시간 비 예보 확인 및 알림 전송 시작")

        try:
            from app import app

            with app.app_context():
                markets_with_interest = self.repository.get_active_markets_with_interest()

                if not markets_with_interest:
                    return {
                        'success': True,
                        'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                        'checked_markets': 0,
                        'alerts_sent': 0,
                    }

                logger.info(f"{len(markets_with_interest)}개 시장의 비 예보 확인 중...")

                checked_count = 0
                alerts_sent = 0
                results = []

                for market in markets_with_interest:
                    try:
                        rain_info = self.evaluator.evaluate_rain(market, hours)
                        checked_count += 1

                        if rain_info.get('has_rain'):
                            alert_result = self.dispatcher.send_rain_alert(market, rain_info)

                            if alert_result.get('success'):
                                alerts_sent += alert_result.get('sent_count', 0)

                            results.append({
                                'market': market.name,
                                'rain_forecast': True,
                                'alert_result': alert_result,
                            })
                        else:
                            results.append({
                                'market': market.name,
                                'rain_forecast': False,
                                'message': '비 예보 없음',
                            })

                    except Exception as e:
                        logger.error(f"시장 {market.name} 처리 중 오류: {e}")
                        results.append({
                            'market': market.name,
                            'error': str(e),
                        })

                logger.info(f"비 예보 확인 완료: {checked_count}개 시장 확인, {alerts_sent}건 알림 전송")

                return {
                    'success': True,
                    'message': f'{checked_count}개 시장 확인 완료, {alerts_sent}건 알림 전송',
                    'checked_markets': checked_count,
                    'alerts_sent': alerts_sent,
                    'results': results,
                }

        except Exception as e:
            logger.error(f"전체 시장 비 예보 확인 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'checked_markets': 0,
                'alerts_sent': 0,
            }

    def check_all_markets_with_all_conditions(self, hours: int = None) -> Dict[str, Any]:
        """모든 조건 + 사용자별 그룹화 (3개 이상이면 요약 알림으로 묶음)."""
        hours = hours or self.forecast_hours

        logger.info(f"향후 {hours}시간 날씨 조건 확인 및 알림 전송 시작 (Grouping 적용)")

        try:
            from app import app
            from database import db as _db

            with app.app_context():
                markets_with_interest = self.repository.get_active_markets_with_interest()

                if not markets_with_interest:
                    return {
                        'success': True,
                        'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                        'checked_markets': 0,
                        'alerts_sent': 0,
                    }

                logger.info(f"{len(markets_with_interest)}개 시장의 날씨 조건 확인 중...")

                # 좌표 단위 prefetch — 278 시장이 98 좌표에 집중되므로 같은 (nx,ny)
                # 의 forecast 를 매 시장마다 다시 조회하는 중복(=N배 DB 호출)을 제거한다.
                # 임계값은 시장별로 달라도 평가 입력(forecast) 은 좌표 단위로 동일.
                coord_forecasts: Dict[Any, Dict[str, Any]] = {}
                for market in markets_with_interest:
                    coord_key = (market.nx, market.ny)
                    if coord_key not in coord_forecasts:
                        coord_forecasts[coord_key] = self.repository.fetch_forecast(market)
                logger.info(
                    f"좌표 prefetch: {len(coord_forecasts)}개 (시장 {len(markets_with_interest)}개)"
                )

                active_market_alerts = []
                user_batches: Dict[Any, Dict[str, Any]] = {}

                checked_count = 0

                for market in markets_with_interest:
                    try:
                        weather_info = self.evaluator.evaluate_all_conditions(
                            market, hours,
                            forecast_data=coord_forecasts.get((market.nx, market.ny)),
                        )
                        checked_count += 1

                        if not weather_info.get('has_alerts'):
                            continue

                        interested_users = market.get_interested_users()
                        valid_users = []

                        # 시장-레벨 dedup: 가장 우선순위 높은 알림 타입 한 개로만 체크.
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

                        if primary_alert_type and is_duplicate_alert(
                            market.id, primary_alert_type, primary_forecast_time
                        ):
                            logger.info(f"시장 {market.name} 중복 알림으로 스킵")
                            continue

                        for user in interested_users:
                            if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
                                valid_users.append(user)

                                if user.id not in user_batches:
                                    user_batches[user.id] = {'user': user, 'alerts': []}

                                user_batches[user.id]['alerts'].append({
                                    'market': market,
                                    'weather_info': weather_info,
                                })

                        active_market_alerts.append({
                            'market': market,
                            'weather_info': weather_info,
                            'users': valid_users,
                            'success_count': 0,
                            'failure_count': 0,
                            'primary_alert_type': primary_alert_type,
                            'primary_forecast_time': primary_forecast_time,
                            'alerts_data': alerts,
                        })

                    except Exception as e:
                        logger.error(f"시장 {market.name} 처리 중 오류: {e}")

                logger.info(f"사용자 {len(user_batches)}명에게 알림 전송 시작")

                total_alerts_sent = 0

                for batch in user_batches.values():
                    user = batch['user']
                    user_alerts = batch['alerts']

                    if not user_alerts:
                        continue

                    is_summary = len(user_alerts) >= 3

                    if is_summary:
                        success = self.dispatcher.send_summary_alert(user, user_alerts)
                        if success:
                            total_alerts_sent += 1

                        # 시장별 카운트 업데이트. 시장 수가 적어 O(N·M) 허용.
                        for item in user_alerts:
                            for m_alert in active_market_alerts:
                                if m_alert['market'].id == item['market'].id:
                                    if success:
                                        m_alert['success_count'] += 1
                                    else:
                                        m_alert['failure_count'] += 1
                                    break
                    else:
                        for item in user_alerts:
                            success = self.dispatcher.send_individual_alert(
                                user, item['market'], item['weather_info']
                            )
                            if success:
                                total_alerts_sent += 1

                            for m_alert in active_market_alerts:
                                if m_alert['market'].id == item['market'].id:
                                    if success:
                                        m_alert['success_count'] += 1
                                    else:
                                        m_alert['failure_count'] += 1
                                    break

                for m_alert in active_market_alerts:
                    log_batch_market_alert(
                        market=m_alert['market'],
                        weather_info=m_alert['weather_info'],
                        success_count=m_alert['success_count'],
                        failure_count=m_alert['failure_count'],
                        total_users=len(m_alert['users']),
                        primary_alert_type=m_alert['primary_alert_type'],
                        primary_forecast_time=m_alert['primary_forecast_time'],
                        alerts_data=m_alert['alerts_data'],
                    )

                _db.session.commit()

                logger.info(
                    f"알림 처리 완료: {checked_count}개 시장 확인, "
                    f"{total_alerts_sent}건 메시지 전송 (요약 포함)"
                )

                return {
                    'success': True,
                    'message': f'{checked_count}개 시장 확인 완료, 총 {total_alerts_sent}건 메시지 전송',
                    'checked_markets': checked_count,
                    'alerts_sent': total_alerts_sent,
                    'results': [],
                }

        except Exception as e:
            logger.error(f"전체 시장 날씨 조건 확인 중 오류: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'checked_markets': 0,
                'alerts_sent': 0,
            }


# 전역 인스턴스 — 외부에서 ``from weather_alerts import weather_alert_system`` 으로 사용.
weather_alert_system = WeatherAlertSystem()
