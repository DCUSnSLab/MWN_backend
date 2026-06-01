"""예보 데이터 → 알림 대상 조건 판정."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from models import Market

from weather_alerts.messages import precipitation_description
from weather_alerts.thresholds import (
    DEFAULT_FORECAST_HOURS,
    DEFAULT_THRESHOLDS,
    resolve_market_thresholds,
)

logger = logging.getLogger(__name__)


class AlertEvaluator:
    """예보 데이터를 임계값과 비교해 알림 항목을 도출한다."""

    def __init__(self, repository, default_hours: int = DEFAULT_FORECAST_HOURS):
        self.repository = repository
        self.default_hours = default_hours

    def evaluate_rain(self, market: Market, hours: int = None) -> Dict[str, Any]:
        """비 예보만 평가 (레거시 단일-조건 API)."""
        if not self.repository.weather_api:
            return {'has_rain': False, 'error': 'Weather API not available'}

        hours = hours or self.default_hours

        try:
            forecast_data = self.repository.fetch_forecast(market)

            if forecast_data.get('status') != 'success':
                error_msg = forecast_data.get('message', 'Failed to get forecast data')
                return {'has_rain': False, 'error': error_msg}

            forecasts = forecast_data.get('data', [])
            rain_alerts = []

            current_time = datetime.now()
            target_time = current_time + timedelta(hours=hours)

            for forecast in forecasts:
                try:
                    fcst_datetime = datetime.strptime(
                        f"{forecast['fcst_date']}{forecast['fcst_time'].zfill(4)}",
                        "%Y%m%d%H%M",
                    )

                    if fcst_datetime <= target_time:
                        pop = forecast.get('pop')
                        pty = forecast.get('pty', '0')

                        if (pop and pop >= DEFAULT_THRESHOLDS['rain_probability']) or (pty and pty != '0'):
                            rain_alerts.append({
                                'datetime': fcst_datetime.isoformat(),
                                'pop': pop,
                                'pty': pty,
                                'description': precipitation_description(pty),
                            })

                except (ValueError, TypeError) as e:
                    logger.warning(f"예보 데이터 파싱 오류: {e}")
                    continue

            return {
                'has_rain': len(rain_alerts) > 0,
                'market_name': market.name,
                'alerts': rain_alerts,
                'checked_hours': hours,
            }

        except Exception as e:
            logger.error(f"시장 {market.name}의 비 예보 확인 중 오류: {e}")
            return {'has_rain': False, 'error': str(e)}

    def evaluate_all_conditions(
        self,
        market: Market,
        hours: int = None,
        forecast_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """비/폭염/한파/강풍/눈 — 시장별 임계값 반영해서 모두 평가.

        forecast_data 가 주어지면 fetch_forecast 호출을 생략한다(같은 좌표 다중 시장
        평가 시 호출자가 좌표 단위 prefetch 한 결과를 공유하기 위함).
        """
        if not self.repository.weather_api:
            return {'has_alerts': False, 'error': 'Weather API not available'}

        hours = hours or self.default_hours

        thresholds = resolve_market_thresholds(market)

        if not thresholds['enabled']:
            logger.debug(f"시장 {market.name}의 알림이 비활성화되어 있습니다.")
            return {'has_alerts': False, 'message': '알림이 비활성화되어 있습니다.'}

        try:
            if forecast_data is None:
                forecast_data = self.repository.fetch_forecast(market)

            if forecast_data.get('status') != 'success':
                error_msg = forecast_data.get('message', 'Failed to get forecast data')
                return {'has_alerts': False, 'error': error_msg}

            forecasts = forecast_data.get('data', [])
            all_alerts = {
                'rain': [],
                'high_temp': [],
                'low_temp': [],
                'strong_wind': [],
                'snow': [],
            }

            current_time = datetime.now()
            target_time = current_time + timedelta(hours=hours)

            for forecast in forecasts:
                try:
                    fcst_datetime = datetime.strptime(
                        f"{forecast['fcst_date']}{forecast['fcst_time'].zfill(4)}",
                        "%Y%m%d%H%M",
                    )

                    if fcst_datetime <= target_time:
                        pop = forecast.get('pop')
                        pty = forecast.get('pty', '0')
                        tmp = forecast.get('tmp')
                        wsd = forecast.get('wsd')
                        sno = forecast.get('sno', 0)

                        alert_item = {
                            'datetime': fcst_datetime.isoformat(),
                            'time_str': fcst_datetime.strftime('%m월 %d일 %H시'),
                        }

                        if thresholds['rain_enabled']:
                            if (pop and pop >= thresholds['rain_probability']) or (pty and pty != '0'):
                                all_alerts['rain'].append({
                                    **alert_item,
                                    'pop': pop,
                                    'pty': pty,
                                    'description': precipitation_description(pty),
                                })

                                # 단기예보 미수집 환경에서는 sno 가 None — pty 만으로 발화.
                                if thresholds['snow_enabled'] and pty in ['2', '3']:
                                    snow_threshold = DEFAULT_THRESHOLDS['snow_amount']
                                    has_threshold_data = sno is not None and sno >= snow_threshold
                                    if has_threshold_data or sno is None:
                                        all_alerts['snow'].append({
                                            **alert_item,
                                            'snow_amount': sno,
                                            'description': (
                                                f"적설량 {sno}cm 예상"
                                                if has_threshold_data
                                                else ("눈 예보" if pty == '3' else "비/눈 예보")
                                            ),
                                        })

                        if thresholds['temp_enabled'] and tmp and tmp >= thresholds['high_temp']:
                            all_alerts['high_temp'].append({
                                **alert_item,
                                'temperature': tmp,
                                'description': f"폭염 주의 (기온 {tmp}°C)",
                            })

                        if thresholds['temp_enabled'] and tmp and tmp <= thresholds['low_temp']:
                            all_alerts['low_temp'].append({
                                **alert_item,
                                'temperature': tmp,
                                'description': f"한파 주의 (기온 {tmp}°C)",
                            })

                        if thresholds['wind_enabled'] and wsd and wsd >= thresholds['wind_speed']:
                            all_alerts['strong_wind'].append({
                                **alert_item,
                                'wind_speed': wsd,
                                'description': f"강풍 주의 (풍속 {wsd}m/s)",
                            })

                except (ValueError, TypeError) as e:
                    logger.warning(f"예보 데이터 파싱 오류: {e}")
                    continue

            active_alerts = {k: v for k, v in all_alerts.items() if len(v) > 0}

            return {
                'has_alerts': len(active_alerts) > 0,
                'market_name': market.name,
                'alerts': active_alerts,
                'checked_hours': hours,
                'thresholds_used': thresholds,
            }

        except Exception as e:
            logger.error(f"시장 {market.name}의 날씨 조건 확인 중 오류: {e}")
            return {'has_alerts': False, 'error': str(e)}
