"""알림 임계값(기본값 및 시장별 설정 해석)."""

from typing import Any, Dict

from models import Market


DEFAULT_THRESHOLDS: Dict[str, Any] = {
    'rain_probability': 30,
    'high_temp': 33,
    'low_temp': -12,
    'wind_speed': 14,
    'snow_amount': 1,
}

DEFAULT_FORECAST_HOURS = 24


def resolve_market_thresholds(market: Market) -> Dict[str, Any]:
    """시장의 알림 조건 해석. 시장별 설정이 없으면 기본값 사용."""
    alert_conditions = market.alert_conditions

    if not alert_conditions:
        return {
            'enabled': True,
            'rain_probability': DEFAULT_THRESHOLDS['rain_probability'],
            'high_temp': DEFAULT_THRESHOLDS['high_temp'],
            'low_temp': DEFAULT_THRESHOLDS['low_temp'],
            'wind_speed': DEFAULT_THRESHOLDS['wind_speed'],
            'snow_enabled': True,
            'rain_enabled': True,
            'temp_enabled': True,
            'wind_enabled': True,
        }

    return {
        'enabled': alert_conditions.get('enabled', True),
        'rain_probability': alert_conditions.get('rain_probability', DEFAULT_THRESHOLDS['rain_probability']),
        'high_temp': alert_conditions.get('high_temp', DEFAULT_THRESHOLDS['high_temp']),
        'low_temp': alert_conditions.get('low_temp', DEFAULT_THRESHOLDS['low_temp']),
        'wind_speed': alert_conditions.get('wind_speed', DEFAULT_THRESHOLDS['wind_speed']),
        'snow_enabled': alert_conditions.get('snow_enabled', True),
        'rain_enabled': alert_conditions.get('rain_enabled', True),
        'temp_enabled': alert_conditions.get('temp_enabled', True),
        'wind_enabled': alert_conditions.get('wind_enabled', True),
    }
