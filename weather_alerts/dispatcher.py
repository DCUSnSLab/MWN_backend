"""FCM 발송 — 시장 단위 / 개별 사용자 / 요약 알림."""

import json
import logging
from typing import Any, Dict, List

from fcm_integration.fcm_utils import fcm_service
from models import Market, User

from weather_alerts.messages import build_weather_alert_message

logger = logging.getLogger(__name__)


def _collect_eligible_tokens(users):
    """방해금지 시간 / FCM 수신 가능 여부 체크 후 (tokens, users) 반환."""
    tokens, valid = [], []
    for user in users:
        if user.can_receive_fcm() and not user.is_in_do_not_disturb_time():
            tokens.append(user.fcm_token)
            valid.append(user)
    return tokens, valid


class AlertDispatcher:
    """FCM 발송 책임 — 발송 결과만 반환, 로그 기록은 호출자가 담당."""

    def send_rain_alert(self, market: Market, rain_info: Dict[str, Any]) -> Dict[str, Any]:
        """레거시: 비 예보에 대한 시장 멀티캐스트."""
        try:
            interested_users = market.get_interested_users()

            if not interested_users:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자가 없습니다.',
                    'sent_count': 0,
                }

            fcm_tokens, valid_users = _collect_eligible_tokens(interested_users)

            if not fcm_tokens:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자 중 FCM 알림을 받을 수 있는 사용자가 없습니다.',
                    'sent_count': 0,
                }

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

            notification_data = {
                'type': 'rain_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': json.dumps(rain_info.get('alerts', []), ensure_ascii=False),
            }

            result = fcm_service.send_multicast(
                tokens=fcm_tokens,
                title=title,
                body=body,
                data=notification_data,
            )

            success_count = result.get('success_count', 0) if result else 0

            logger.info(f"{market.name} 비 알림: {len(valid_users)}명 중 {success_count}명에게 전송 성공")

            return {
                'success': True,
                'message': f'{market.name} 비 알림이 전송되었습니다.',
                'sent_count': success_count,
                'total_users': len(valid_users),
                'fcm_result': result,
            }

        except Exception as e:
            logger.error(f"{market.name} 비 알림 전송 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0,
            }

    def send_weather_alert(self, market: Market, weather_info: Dict[str, Any]) -> Dict[str, Any]:
        """모든 조건(폭염/한파/강풍/눈/비) 시장 멀티캐스트. 로그는 호출자가 기록.

        반환값에 ``valid_users``, ``title``, ``body``, ``success_count``,
        ``failure_count`` 를 포함시켜 호출자가 ``MarketAlarmLog`` 를 만들 수 있도록 한다.
        """
        try:
            interested_users = market.get_interested_users()

            if not interested_users:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자가 없습니다.',
                    'sent_count': 0,
                }

            fcm_tokens, valid_users = _collect_eligible_tokens(interested_users)

            if not fcm_tokens:
                return {
                    'success': True,
                    'message': f'{market.name}에 관심을 가진 사용자 중 FCM 알림을 받을 수 있는 사용자가 없습니다.',
                    'sent_count': 0,
                }

            alerts = weather_info.get('alerts', {})
            title, body = build_weather_alert_message(market.name, alerts, weather_info['checked_hours'])

            notification_data = {
                'type': 'weather_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alerts': json.dumps(alerts, ensure_ascii=False),
            }

            result = fcm_service.send_multicast(
                tokens=fcm_tokens,
                title=title,
                body=body,
                data=notification_data,
            )

            success_count = result.get('success_count', 0) if result else 0
            failure_count = result.get('failure_count', 0) if result else len(valid_users)

            logger.info(f"{market.name} 날씨 알림: {len(valid_users)}명 중 {success_count}명에게 전송 성공")

            return {
                'success': True,
                'message': f'{market.name} 날씨 알림이 전송되었습니다.',
                'sent_count': success_count,
                'total_users': len(valid_users),
                'fcm_result': result,
                'title': title,
                'body': body,
                'valid_users': valid_users,
                'success_count': success_count,
                'failure_count': failure_count,
                'alerts': alerts,
            }

        except Exception as e:
            logger.error(f"{market.name} 날씨 알림 전송 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0,
            }

    def send_individual_alert(self, user: User, market: Market, weather_info: Dict[str, Any]) -> bool:
        """개별 사용자에게 단일 시장 날씨 알림."""
        try:
            alerts = weather_info.get('alerts', {})
            title, body = build_weather_alert_message(market.name, alerts, weather_info['checked_hours'])

            # data payload 4KB 한계: 전체 alerts 직렬화 시 "message is too big" 오류.
            # 알림 타입 목록만 보내고 상세는 클라이언트가 앱에서 조회한다.
            notification_data = {
                'type': 'weather_alert',
                'market_id': str(market.id),
                'market_name': market.name,
                'alert_types': json.dumps(list(alerts.keys()), ensure_ascii=False),
            }

            return fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data,
            )
        except Exception as e:
            logger.error(f"사용자 {user.id}에게 개별 알림 전송 실패: {e}")
            return False

    def send_summary_alert(self, user: User, alerts_list: List[Dict[str, Any]]) -> bool:
        """3개 이상 시장에 알림이 동시 발생할 때 사용자 단위 요약 알림."""
        try:
            market_names = [item['market'].name for item in alerts_list]
            count = len(market_names)

            title = f"{count}개 시장 날씨 알림"

            if count <= 2:
                markets_str = ", ".join(market_names)
            else:
                markets_str = f"{market_names[0]}, {market_names[1]} 외 {count-2}곳"

            unique_types = set()
            for item in alerts_list:
                for a_type in item['weather_info'].get('alerts', {}).keys():
                    unique_types.add(a_type)

            type_map = {
                'rain': '비',
                'snow': '눈',
                'high_temp': '폭염',
                'low_temp': '한파',
                'strong_wind': '강풍',
            }

            type_names = [type_map[t] for t in unique_types if t in type_map]

            sort_order = ['비', '눈', '폭염', '한파', '강풍']
            type_names.sort(key=lambda x: sort_order.index(x) if x in sort_order else 99)

            if not type_names:
                weather_str = "기상 특보"
            else:
                weather_str = ", ".join(type_names)

            body = f"{markets_str}에 {weather_str} 등 주의할 날씨가 예상됩니다. 앱에서 상세 내용을 확인하세요."

            summary_data = []
            for item in alerts_list:
                market = item['market']
                alert_types = list(item['weather_info'].get('alerts', {}).keys())
                summary_data.append({
                    'market_id': market.id,
                    'market_name': market.name,
                    'types': alert_types,
                })

            notification_data = {
                'type': 'weather_summary_alert',
                'count': str(count),
                'summary': json.dumps(summary_data, ensure_ascii=False),
            }

            return fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data,
            )
        except Exception as e:
            logger.error(f"사용자 {user.id}에게 요약 알림 전송 실패: {e}")
            return False
