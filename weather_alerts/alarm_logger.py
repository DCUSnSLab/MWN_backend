"""MarketAlarmLog 기록 및 중복 알림 체크."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import db
from models import Market, MarketAlarmLog

from weather_alerts.messages import build_weather_alert_message

logger = logging.getLogger(__name__)

# Cool-down: 마지막 알림 이후 이 시간 안에 동일 시장+타입은 재발화 안 함.
COOL_DOWN_HOURS = 6


def is_duplicate_alert(market_id: int, alert_type: str, forecast_time: str) -> bool:
    """최근 cool-down 안에 같은 시장+타입이 이미 나갔거나, 같은 예보 시점이면 True."""
    try:
        last_log = MarketAlarmLog.query.filter_by(
            market_id=market_id,
            alert_type=alert_type,
        ).order_by(MarketAlarmLog.created_at.desc()).first()

        if not last_log:
            return False

        # DB created_at 은 timezone-naive UTC 로 저장되므로 비교 시 동일 형태로 맞춘다.
        now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        elapsed = now_naive_utc - last_log.created_at
        if elapsed < timedelta(hours=COOL_DOWN_HOURS):
            return True

        if last_log.forecast_time == forecast_time:
            return True

        return False

    except Exception as e:
        logger.error(f"중복 알림 체크 중 오류: {e}")
        return False


def _resolve_primary_alert(alerts: Dict[str, Any]) -> Dict[str, Any]:
    """우선순위(high_temp > low_temp > strong_wind > snow > rain)로 대표 알림 추출."""
    result = {
        'alert_type': None,
        'temperature': None,
        'rain_probability': None,
        'wind_speed': None,
        'precipitation_type': None,
        'forecast_time': None,
    }

    if alerts.get('high_temp'):
        data = alerts['high_temp'][0]
        result['alert_type'] = 'high_temp'
        result['temperature'] = data.get('temperature')
        result['forecast_time'] = data.get('time_str')
    elif alerts.get('low_temp'):
        data = alerts['low_temp'][0]
        result['alert_type'] = 'low_temp'
        result['temperature'] = data.get('temperature')
        result['forecast_time'] = data.get('time_str')
    elif alerts.get('strong_wind'):
        data = alerts['strong_wind'][0]
        result['alert_type'] = 'strong_wind'
        result['wind_speed'] = data.get('wind_speed')
        result['forecast_time'] = data.get('time_str')
    elif alerts.get('snow'):
        data = alerts['snow'][0]
        result['alert_type'] = 'snow'
        result['precipitation_type'] = 'snow'
        result['forecast_time'] = data.get('time_str')
    elif alerts.get('rain'):
        data = alerts['rain'][0]
        result['alert_type'] = 'rain'
        result['rain_probability'] = data.get('pop')
        result['precipitation_type'] = data.get('description')
        result['forecast_time'] = data.get('time_str')

    return result


def log_single_market_alert(
    market: Market,
    weather_info: Dict[str, Any],
    dispatch_result: Dict[str, Any],
) -> Optional[MarketAlarmLog]:
    """단일 시장 멀티캐스트 결과를 ``MarketAlarmLog`` 로 기록(commit 포함)."""
    try:
        alerts = dispatch_result.get('alerts') or weather_info.get('alerts', {})
        primary = _resolve_primary_alert(alerts)

        if not primary['alert_type']:
            logger.warning(f"{market.name} 알림 타입을 결정할 수 없어 로그를 기록하지 못했습니다.")
            return None

        title = dispatch_result.get('title')
        body = dispatch_result.get('body')
        valid_users = dispatch_result.get('valid_users') or []
        success_count = dispatch_result.get('success_count', 0)
        failure_count = dispatch_result.get('failure_count', 0)

        alarm_log = MarketAlarmLog(
            market_id=market.id,
            alert_type=primary['alert_type'],
            alert_title=title,
            alert_body=body,
            total_users=len(valid_users),
            success_count=success_count,
            failure_count=failure_count,
            weather_data=alerts,
            temperature=primary['temperature'],
            rain_probability=primary['rain_probability'],
            wind_speed=primary['wind_speed'],
            precipitation_type=primary['precipitation_type'],
            forecast_time=primary['forecast_time'],
            checked_hours=weather_info.get('checked_hours'),
        )

        db.session.add(alarm_log)
        db.session.commit()

        logger.info(f"{market.name} 알림 로그 데이터베이스 기록 완료 (ID: {alarm_log.id})")
        return alarm_log

    except Exception as log_error:
        logger.error(f"{market.name} 알림 로그 데이터베이스 기록 실패: {log_error}")
        db.session.rollback()
        return None


def log_batch_market_alert(
    market: Market,
    weather_info: Dict[str, Any],
    success_count: int,
    failure_count: int,
    total_users: int,
    primary_alert_type: Optional[str],
    primary_forecast_time: Optional[str],
    alerts_data: Dict[str, Any],
) -> None:
    """배치(그룹화) 발송 결과를 ``MarketAlarmLog`` 로 기록 (commit 은 호출자)."""
    try:
        if success_count == 0 and failure_count == 0:
            return

        alerts = alerts_data

        temperature = None
        rain_probability = None
        wind_speed = None
        precipitation_type = None

        if alerts.get('high_temp'):
            temperature = alerts['high_temp'][0].get('temperature')
        elif alerts.get('low_temp'):
            temperature = alerts['low_temp'][0].get('temperature')

        if alerts.get('rain'):
            rain_probability = alerts['rain'][0].get('pop')
            precipitation_type = alerts['rain'][0].get('description')

        if alerts.get('strong_wind'):
            wind_speed = alerts['strong_wind'][0].get('wind_speed')
        if alerts.get('snow'):
            precipitation_type = 'snow'

        # 요약으로 나갔더라도 로그에는 원본 이벤트 기록.
        title, body = build_weather_alert_message(market.name, alerts, weather_info['checked_hours'])

        alarm_log = MarketAlarmLog(
            market_id=market.id,
            alert_type=primary_alert_type or 'unknown',
            alert_title=title,
            alert_body=body,
            total_users=total_users,
            success_count=success_count,
            failure_count=failure_count,
            weather_data=alerts,
            temperature=temperature,
            rain_probability=rain_probability,
            wind_speed=wind_speed,
            precipitation_type=precipitation_type,
            forecast_time=primary_forecast_time,
            checked_hours=weather_info.get('checked_hours'),
        )
        db.session.add(alarm_log)
    except Exception as e:
        logger.error(f"로그 기록 중 오류 (시장: {market.name}): {e}")
