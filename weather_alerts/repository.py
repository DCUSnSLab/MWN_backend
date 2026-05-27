"""예보 데이터 조회 — DB 우선, 필요 시 KMA API fallback."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import db
from models import Market, Weather, UserMarketInterest

logger = logging.getLogger(__name__)


class ForecastRepository:
    """예보(forecast) 및 현재(current) 날씨 데이터 조회 책임."""

    def __init__(self, weather_api):
        # weather_api 는 KMAWeatherAPI 인스턴스(혹은 None — 서비스키 미설정 시).
        self.weather_api = weather_api

    def get_forecast_from_db(self, nx: int, ny: int) -> Dict[str, Any]:
        """최근 2시간 내 수집된 예보(api_type='forecast')만 사용."""
        from app import app

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)

        try:
            with app.app_context():
                forecasts = Weather.query.filter(
                    Weather.nx == nx,
                    Weather.ny == ny,
                    Weather.api_type == 'forecast',
                    Weather.created_at >= cutoff_time,
                ).order_by(
                    Weather.fcst_date.asc(),
                    Weather.fcst_time.asc(),
                ).all()

                if not forecasts:
                    return {'status': 'empty', 'message': 'No recent forecast data in DB'}

                data = []
                for f in forecasts:
                    # SNO 는 단기예보(getVilageFcst)에서만 제공되어 대부분 None.
                    # 그 경우 pty 기반 알림만 발화한다.
                    data.append({
                        'fcst_date': f.fcst_date,
                        'fcst_time': f.fcst_time,
                        'pop': f.pop,
                        'pty': f.pty,
                        'tmp': f.temp,
                        'wsd': f.wind_speed,
                        'sno': f.sno,
                    })

                return {'status': 'success', 'data': data}

        except Exception as e:
            logger.error(f"DB 예보 조회 중 오류: {e}")
            return {'status': 'error', 'message': str(e)}

    def fetch_forecast(self, market: Market) -> Dict[str, Any]:
        """DB 우선, 실패 시 API fallback."""
        forecast_data = self.get_forecast_from_db(market.nx, market.ny)

        if forecast_data.get('status') != 'success':
            if self.weather_api:
                logger.info(f"DB 데이터 없음, API 호출 시도: {market.name}")
                forecast_data = self.weather_api.get_forecast_weather(
                    market.nx,
                    market.ny,
                    market.name,
                )

        return forecast_data

    def get_current_weather(self, nx: int, ny: int) -> Optional[Weather]:
        """nx/ny 기준 최신 현재 날씨(api_type='current')."""
        return Weather.query.filter_by(
            nx=nx,
            ny=ny,
            api_type='current',
        ).order_by(Weather.created_at.desc()).first()

    def get_short_term_forecast(self, nx: int, ny: int, limit: int = 6) -> List[Weather]:
        """nx/ny 기준 최신 예보(api_type='forecast') 상위 N건."""
        return Weather.query.filter_by(
            nx=nx,
            ny=ny,
            api_type='forecast',
        ).order_by(
            Weather.base_date.desc(),
            Weather.base_time.desc(),
            Weather.fcst_date.asc(),
            Weather.fcst_time.asc(),
        ).limit(limit).all()

    def get_active_markets_with_interest(self, require_grid: bool = False) -> List[Market]:
        """관심 사용자가 있는 활성 시장 목록.

        require_grid=True 면 nx/ny 가 있는 시장만 반환(test_summary 용).
        """
        query = db.session.query(Market).join(
            UserMarketInterest,
            Market.id == UserMarketInterest.market_id,
        ).filter(
            Market.is_active == True,  # noqa: E712
            UserMarketInterest.is_active == True,  # noqa: E712
            UserMarketInterest.notification_enabled == True,  # noqa: E712
        )

        if require_grid:
            query = query.filter(Market.nx.isnot(None), Market.ny.isnot(None))

        return query.distinct(Market.id).all()
