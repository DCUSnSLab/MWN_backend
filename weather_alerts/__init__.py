"""weather_alerts: 시장 날씨 기반 FCM 알림 시스템.

내부적으로 책임별 서브모듈로 분리되어 있으나, 외부 호환을 위해
``WeatherAlertSystem``, ``weather_alert_system`` 그리고 모듈-레벨 함수들을
패키지 최상위에서 그대로 노출한다.
"""

from weather_alerts.system import WeatherAlertSystem, weather_alert_system
from weather_alerts.facade import (
    check_and_send_rain_alerts,
    check_and_send_all_weather_alerts,
    check_market_rain_forecast,
    check_market_all_conditions,
    send_test_weather_summary_to_all_users,
)

__all__ = [
    "WeatherAlertSystem",
    "weather_alert_system",
    "check_and_send_rain_alerts",
    "check_and_send_all_weather_alerts",
    "check_market_rain_forecast",
    "check_market_all_conditions",
    "send_test_weather_summary_to_all_users",
]
