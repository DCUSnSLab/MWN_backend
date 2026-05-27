"""알림 메시지 빌더 — 강수형태 라벨, 본문 텍스트 생성."""

from typing import Any, Dict, Tuple


PRECIPITATION_DESCRIPTIONS = {
    '0': '없음',
    '1': '비',
    '2': '비/눈',
    '3': '눈',
    '4': '소나기',
    '5': '빗방울',
    '6': '빗방울/눈날림',
    '7': '눈날림',
}


def precipitation_description(pty: Any) -> str:
    """강수형태 코드를 한글 설명으로 변환."""
    return PRECIPITATION_DESCRIPTIONS.get(str(pty), '알 수 없음')


def build_weather_alert_message(
    market_name: str,
    alerts: Dict[str, Any],
    hours: int,
) -> Tuple[str, str]:
    """우선순위(폭염 > 한파 > 강풍 > 눈 > 비)에 따라 (title, body) 반환."""
    if alerts.get('high_temp'):
        alert = alerts['high_temp'][0]
        temp = alert.get('temperature')

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
        snow = alert.get('snow_amount') or 0

        # 적설량이 없으면(snow == 0) pty 기반 발화 — 기본 단계로 처리한다.
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
        time_str = alert['time_str']

        if snow > 0:
            forecast_line = f"{time_str}경부터 {market_name}에 적설량 {snow}cm 이상 {snow_desc}이 예상됩니다."
        else:
            forecast_line = f"{time_str}경부터 {market_name}에 {snow_desc}이 예상됩니다."

        body = f"""{forecast_line}

[조치1] 인근 가설천막 및 차양에 눈이 쌓이지 않도록 수시 점검 바랍니다.

[조치2] 지붕 위 적설은 붕괴 위험이 있으므로 제설장비를 이용해 즉시 제거 바랍니다.

[조치3] 통로 및 계단에는 미끄럼방지제(모래, 염화칼슘 등)를 살포해 주시기 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""
        return (title, body)

    if alerts.get('rain'):
        alert = alerts['rain'][0]
        pop = alert.get('pop')
        description = alert.get('description', '비')

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
        time_str = alert['time_str']
        prob_str = f"강수확률 {pop}%" if pop else rain_desc

        body = f"""{time_str}경부터 {market_name} 인근지역 {prob_str} 예상됩니다.

[조치1] 시장 입구 및 주요 통로의 배수구 덮개를 열어 배수로 확보 바랍니다.

[조치2] 저지대 점포 및 창고 내 전기제품을 고지대로 이동시켜 주세요.

[조치3] 침수 대비를 위해 배수펌프 및 비닐커버를 사전에 점검 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)"""
        return (title, body)

    # 기존 코드는 위 5개 분기 중 어디에도 안 걸리면 None 을 반환했다 (암묵적).
    return (None, None)
