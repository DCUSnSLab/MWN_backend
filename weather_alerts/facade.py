"""모듈-레벨 함수 facade — 외부 호출처(routes/weather, admin_panel 등)의 import 호환성 유지."""

import logging
import traceback
from typing import Any, Dict

from fcm_integration.fcm_utils import fcm_service
from models import Market

from weather_alerts.system import weather_alert_system

logger = logging.getLogger(__name__)


def check_and_send_rain_alerts(hours: int = 24) -> Dict[str, Any]:
    """비 예보 확인 및 알림 전송 — 레거시 단일-조건 경로."""
    return weather_alert_system.check_all_markets_and_send_alerts(hours)


def check_and_send_all_weather_alerts(hours: int = 24) -> Dict[str, Any]:
    """모든 날씨 조건 확인 및 알림 전송 — 현재 운영 경로."""
    return weather_alert_system.check_all_markets_with_all_conditions(hours)


def check_market_rain_forecast(market_id: int, hours: int = 24) -> Dict[str, Any]:
    """특정 시장의 비 예보 확인."""
    from app import app

    with app.app_context():
        market = Market.query.get(market_id)
        if not market:
            return {'error': '시장을 찾을 수 없습니다.'}

        return weather_alert_system.check_rain_forecast_for_market(market, hours)


def check_market_all_conditions(market_id: int, hours: int = 24) -> Dict[str, Any]:
    """특정 시장의 모든 날씨 조건 확인."""
    from app import app

    with app.app_context():
        market = Market.query.get(market_id)
        if not market:
            return {'error': '시장을 찾을 수 없습니다.'}

        return weather_alert_system.check_all_weather_conditions_for_market(market, hours)


def send_test_weather_summary_to_all_users() -> Dict[str, Any]:
    """[테스트용] 조건 체크 없이 최신 날씨 정보를 요약해서 모든 관심 사용자에게 발송."""
    from app import app

    logger.info("테스트 날씨 요약 알림 전송 시작")

    try:
        with app.app_context():
            markets_with_interest = weather_alert_system.repository.get_active_markets_with_interest(
                require_grid=True,
            )

            if not markets_with_interest:
                return {
                    'success': True,
                    'message': '관심을 가진 사용자가 있는 활성 시장이 없습니다.',
                    'sent_count': 0,
                }

            logger.info(f"{len(markets_with_interest)}개 시장의 날씨 요약 알림 전송 중...")

            total_sent = 0
            results = []

            for market in markets_with_interest:
                try:
                    current_weather = weather_alert_system.repository.get_current_weather(
                        market.nx, market.ny,
                    )

                    forecast_weather = weather_alert_system.repository.get_short_term_forecast(
                        market.nx, market.ny, limit=6,
                    )

                    if not current_weather:
                        logger.warning(f"{market.name}: 날씨 데이터 없음")
                        results.append({
                            'market': market.name,
                            'success': False,
                            'message': '날씨 데이터 없음',
                        })
                        continue

                    interested_users = market.get_interested_users()

                    if not interested_users:
                        results.append({
                            'market': market.name,
                            'success': True,
                            'message': '관심 사용자 없음',
                            'sent_count': 0,
                        })
                        continue

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
                            'sent_count': 0,
                        })
                        continue

                    title = f"☀️ {market.name} 날씨 정보"

                    temp = current_weather.temp if current_weather.temp is not None else '?'
                    humidity = current_weather.humidity if current_weather.humidity is not None else '?'
                    wind_speed = current_weather.wind_speed if current_weather.wind_speed is not None else '?'

                    weather_condition = "맑음"
                    if current_weather.pty:
                        pty_map = {'0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}
                        weather_condition = pty_map.get(current_weather.pty, '맑음')

                    body = f"현재: {temp}°C, 습도 {humidity}%, 풍속 {wind_speed}m/s"
                    if weather_condition != "없음" and weather_condition != "맑음":
                        body += f"\n날씨: {weather_condition}"

                    if forecast_weather:
                        rain_forecasts = [f for f in forecast_weather if f.pop and f.pop >= 30]
                        if rain_forecasts:
                            max_pop = max([f.pop for f in rain_forecasts])
                            body += f"\n향후 강수확률: 최대 {int(max_pop)}%"

                    updated_time = current_weather.created_at.strftime('%H:%M') if current_weather.created_at else '?'
                    body += f"\n(업데이트: {updated_time})"

                    notification_data = {
                        'type': 'weather_summary_test',
                        'market_id': str(market.id),
                        'market_name': market.name,
                        'temperature': str(temp),
                        'humidity': str(humidity),
                        'wind_speed': str(wind_speed),
                        'weather_condition': weather_condition,
                        'updated_at': updated_time,
                    }

                    result = fcm_service.send_multicast(
                        tokens=fcm_tokens,
                        title=title,
                        body=body,
                        data=notification_data,
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
                            'condition': weather_condition,
                        },
                    })

                except Exception as e:
                    logger.error(f"시장 {market.name} 처리 중 오류: {e}")
                    results.append({
                        'market': market.name,
                        'success': False,
                        'error': str(e),
                    })

            logger.info(f"테스트 날씨 요약 알림 전송 완료: 총 {total_sent}건 전송")

            return {
                'success': True,
                'message': f'{len(markets_with_interest)}개 시장에 대해 총 {total_sent}건 알림 전송 완료',
                'total_markets': len(markets_with_interest),
                'total_sent': total_sent,
                'results': results,
            }

    except Exception as e:
        logger.error(f"테스트 날씨 요약 알림 전송 중 오류: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'total_sent': 0,
        }
