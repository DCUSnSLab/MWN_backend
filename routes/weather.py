"""weather_bp: 날씨 조회 / 스케줄러 제어 / 관리자 테스트 알림."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

weather_bp = Blueprint('weather', __name__)


@weather_bp.route('/api/weather/current', methods=['POST'])
def get_current_weather():
    """현재 날씨 정보 조회 (시장의 최신 데이터 가져오기)"""
    from auth_utils import login_required
    from models import Weather, Market

    @login_required
    def _get_current_weather(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if 'nx' not in data or 'ny' not in data:
            logger.warning(f"현재 날씨 조회 실패: 필수 파라미터 누락 (data={data})")
            return jsonify({'error': '격자좌표 nx와 ny가 필요합니다.'}), 400

        try:
            nx = int(data['nx'])
            ny = int(data['ny'])

            market = Market.query.filter_by(nx=nx, ny=ny, is_active=True).first()

            if market:
                weather = Weather.query.filter_by(
                    nx=nx,
                    ny=ny,
                    api_type='current',
                ).order_by(Weather.created_at.desc()).first()

                if weather:
                    return jsonify({
                        'status': 'success',
                        'message': f'{market.name}의 최신 날씨 데이터를 가져왔습니다.',
                        'data': weather.to_dict(),
                        'location_name': market.name,
                        'nx': market.nx,
                        'ny': market.ny,
                    })
                logger.warning(f"현재 날씨 조회 실패: {market.name}의 날씨 데이터 없음")
                return jsonify({
                    'status': 'error',
                    'message': f'{market.name}의 날씨 데이터가 없습니다. 스케줄러가 아직 데이터를 수집하지 않았습니다.',
                }), 404

            logger.warning(f"시장 없음: 격자좌표({nx}, {ny})에 해당하는 활성 시장이 없습니다.")
            return jsonify({
                'status': 'error',
                'message': f'해당 위치의 시장 정보가 없습니다. (격자좌표: {nx}, {ny})',
            }), 404

        except ValueError:
            return jsonify({'error': 'nx와 ny는 정수여야 합니다.'}), 400
        except Exception as e:
            logger.error(f"현재 날씨 조회 오류: {e}")
            return jsonify({'error': '서버 오류가 발생했습니다'}), 500

    return _get_current_weather()


@weather_bp.route('/api/weather/forecast', methods=['POST'])
def get_forecast_weather():
    """날씨 예보 정보 조회 (데이터베이스에서 최신 데이터 가져오기)"""
    from auth_utils import login_required
    from models import Weather

    @login_required
    def _get_forecast_weather(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if 'nx' not in data or 'ny' not in data:
            return jsonify({'error': '격자좌표 nx와 ny가 필요합니다.'}), 400

        try:
            nx = int(data['nx'])
            ny = int(data['ny'])

            forecasts = Weather.query.filter_by(
                nx=nx,
                ny=ny,
                api_type='forecast',
            ).order_by(
                Weather.base_date.desc(),
                Weather.base_time.desc(),
                Weather.fcst_date.asc(),
                Weather.fcst_time.asc(),
            ).limit(100).all()

            if not forecasts:
                return jsonify({
                    'status': 'error',
                    'message': f'해당 위치({nx}, {ny})의 예보 데이터가 없습니다. 스케줄러가 아직 데이터를 수집하지 않았거나 해당 지역이 활성 시장 목록에 없습니다.',
                }), 404

            latest_base_date = forecasts[0].base_date
            latest_base_time = forecasts[0].base_time

            latest_forecasts = [
                f for f in forecasts
                if f.base_date == latest_base_date and f.base_time == latest_base_time
            ]

            return jsonify({
                'status': 'success',
                'message': '데이터베이스에서 최신 예보 데이터를 가져왔습니다.',
                'data': [weather.to_dict() for weather in latest_forecasts],
                'location_name': forecasts[0].location_name if forecasts else '',
                'nx': nx,
                'ny': ny,
                'base_date': latest_base_date,
                'base_time': latest_base_time,
            })

        except ValueError:
            return jsonify({'error': 'nx와 ny는 정수여야 합니다.'}), 400
        except Exception as e:
            logger.error(f"예보 날씨 조회 오류: {e}")
            return jsonify({'error': '서버 오류가 발생했습니다'}), 500

    return _get_forecast_weather()


@weather_bp.route('/api/weather', methods=['GET'])
def get_weather_history():
    """저장된 날씨 데이터 조회"""
    from models import Weather

    location_name = request.args.get('location_name')
    api_type = request.args.get('api_type')
    limit = request.args.get('limit', 100, type=int)

    try:
        query = Weather.query

        if location_name:
            query = query.filter(Weather.location_name.contains(location_name))

        if api_type:
            query = query.filter(Weather.api_type == api_type)

        weather_data = query.order_by(Weather.created_at.desc()).limit(limit).all()

        return jsonify({
            'status': 'success',
            'count': len(weather_data),
            'data': [weather.to_dict() for weather in weather_data],
        })

    except Exception as e:
        logger.error(f"날씨 이력 조회 실패: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500


@weather_bp.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """날씨 스케줄러 시작"""
    from auth_utils import admin_required

    @admin_required
    def _start_scheduler(current_user):
        try:
            from weather_scheduler import start_weather_scheduler
            start_weather_scheduler()
            return jsonify({'status': 'success', 'message': '날씨 스케줄러가 시작되었습니다.'})
        except Exception as e:
            logger.error(f"스케줄러 시작 실패: {e}")
            return jsonify({'error': '스케줄러 시작에 실패했습니다'}), 500

    return _start_scheduler()


@weather_bp.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """날씨 스케줄러 정지"""
    from auth_utils import admin_required

    @admin_required
    def _stop_scheduler(current_user):
        try:
            from weather_scheduler import stop_weather_scheduler
            stop_weather_scheduler()
            return jsonify({'status': 'success', 'message': '날씨 스케줄러가 정지되었습니다.'})
        except Exception as e:
            logger.error(f"스케줄러 정지 실패: {e}")
            return jsonify({'error': '스케줄러 정지에 실패했습니다'}), 500

    return _stop_scheduler()


@weather_bp.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """스케줄러 상태 조회"""
    from auth_utils import login_required

    @login_required
    def _get_scheduler_status(current_user):
        try:
            from weather_scheduler import get_scheduler_status as _status
            return jsonify(_status())
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return jsonify({'error': '상태 조회에 실패했습니다'}), 500

    return _get_scheduler_status()


@weather_bp.route('/api/scheduler/stats', methods=['GET'])
def get_weather_statistics():
    """날씨 데이터 통계 조회"""
    from auth_utils import login_required

    @login_required
    def _get_weather_statistics(current_user):
        try:
            from weather_scheduler import get_weather_stats
            return jsonify(get_weather_stats())
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return jsonify({'error': '통계 조회에 실패했습니다'}), 500

    return _get_weather_statistics()


@weather_bp.route('/api/scheduler/collect', methods=['POST'])
def manual_weather_collection():
    """수동 날씨 데이터 수집"""
    from auth_utils import admin_required

    @admin_required
    def _manual_weather_collection(current_user):
        try:
            from weather_scheduler import weather_scheduler
            weather_scheduler.collect_market_weather_data()
            return jsonify({'status': 'success', 'message': '날씨 데이터 수집이 완료되었습니다.'})
        except Exception as e:
            logger.error(f"수동 수집 실패: {e}")
            return jsonify({'error': '수동 수집에 실패했습니다'}), 500

    return _manual_weather_collection()


@weather_bp.route('/api/admin/rain-alerts/check', methods=['POST'])
def manual_rain_alert_check():
    """관리자용 수동 비 예보 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_rain_alerts

    @admin_required
    def _manual_rain_alert_check(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}
            hours = data.get('hours', 24)

            result = check_and_send_rain_alerts(hours)

            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': '비 예보 알림 확인 완료',
                    'result': result,
                })
            return jsonify({
                'status': 'error',
                'message': '비 예보 알림 확인 실패',
                'error': result.get('error'),
            }), 500

        except Exception as e:
            logger.error(f"비 예보 알림 확인 실패: {e}")
            return jsonify({'error': '비 예보 알림 확인에 실패했습니다'}), 500

    return _manual_rain_alert_check()


@weather_bp.route('/api/markets/<int:market_id>/rain-forecast', methods=['GET'])
def get_market_rain_forecast(market_id):
    """특정 시장의 비 예보 확인"""
    from weather_alerts import check_market_rain_forecast

    try:
        hours = request.args.get('hours', 24, type=int)
        result = check_market_rain_forecast(market_id, hours)

        if 'error' in result:
            return jsonify(result), 404

        return jsonify({
            'status': 'success',
            'market_id': market_id,
            'forecast': result,
        })

    except Exception as e:
        logger.error(f"비 예보 확인 실패: {e}")
        return jsonify({'error': '비 예보 확인에 실패했습니다'}), 500


@weather_bp.route('/api/markets/<int:market_id>/weather-conditions', methods=['GET'])
def get_market_weather_conditions(market_id):
    """특정 시장의 모든 날씨 조건 확인 (비, 폭염, 한파, 강풍 등)"""
    from weather_alerts import check_market_all_conditions

    try:
        hours = request.args.get('hours', 24, type=int)
        result = check_market_all_conditions(market_id, hours)

        if 'error' in result:
            return jsonify(result), 404

        return jsonify({
            'status': 'success',
            'market_id': market_id,
            'conditions': result,
        })

    except Exception as e:
        logger.error(f"날씨 조건 확인 실패: {e}")
        return jsonify({'error': '날씨 조건 확인에 실패했습니다'}), 500


@weather_bp.route('/api/admin/weather-alerts/check', methods=['POST'])
def manual_weather_alert_check():
    """관리자용 수동 모든 날씨 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_all_weather_alerts

    @admin_required
    def _manual_weather_alert_check(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}
            hours = data.get('hours', 24)

            result = check_and_send_all_weather_alerts(hours)

            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': '날씨 알림 확인 완료',
                    'result': result,
                })
            return jsonify({
                'status': 'error',
                'message': '날씨 알림 확인 실패',
                'error': result.get('error'),
            }), 500

        except Exception as e:
            logger.error(f"날씨 알림 확인 실패: {e}")
            return jsonify({'error': '날씨 알림 확인에 실패했습니다'}), 500

    return _manual_weather_alert_check()


# 알림 타입별 본문 템플릿 (테스트용)
_ALERT_TEMPLATES = {
    'rain': {
        'title_kw': '강우예보',
        'body': (
            "11월 13일 15시경부터 {name} 인근지역 비 또는 눈 70% 이상 예상됩니다.\n\n"
            "[조치1] 시장 입구 및 주요 통로의 배수구 덮개를 열어 배수로 확보 바랍니다.\n\n"
            "[조치2] 저지대 점포 및 창고 내 전기제품을 고지대로 이동시켜 주세요.\n\n"
            "[조치3] 침수 대비를 위해 배수펌프 및 비닐커버를 사전에 점검 바랍니다.\n\n"
            "* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)\n"
            "** 이것은 테스트 알림입니다"
        ),
    },
    'heat': {
        'title_kw': '폭염예보',
        'body': (
            "11월 13일 14시경 최고기온 35°C 이상 폭염이 예상됩니다.\n\n"
            "[조치1] 냉장·냉동식품의 보관온도를 점검하고, 변질우려 제품은 폐기 바랍니다.\n\n"
            "[조치2] 상인 및 고객을 위한 냉방기 가동과 충분한 환기를 유지 바랍니다.\n\n"
            "[조치3] 노약자 근무자는 충분한 휴식을 취하고, 음료수를 비치해 주세요.\n\n"
            "* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)\n"
            "** 이것은 테스트 알림입니다"
        ),
    },
    'cold': {
        'title_kw': '한파예보',
        'body': (
            "11월 13일 06시경 기온이 -15°C 이하로 떨어질 것으로 예상됩니다.\n\n"
            "[조치1] 수도관과 보일러 배관의 동파 방지를 위해 보온 덮개를 설치 바랍니다.\n\n"
            "[조치2] 난방기 과열 및 전열기 주변 인화물 정리를 철저히 해주세요.\n\n"
            "[조치3] 점포 내 결빙구간(출입구, 배수로 등)을 미리 점검하고 제빙제를 비치 바랍니다.\n\n"
            "* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)\n"
            "** 이것은 테스트 알림입니다"
        ),
    },
    'wind': {
        'title_kw': '강풍예보',
        'body': (
            "11월 13일 14시경부터 {name} 풍속 20m/s 이상 강풍이 예상됩니다.\n\n"
            "[조치1] 가스밸브·전열기 주변 인화성 물질(박스, 천 등)을 제거 바랍니다.\n\n"
            "[조치2] 상인회 주관으로 순찰을 강화하고, 화재대피안내 및 방송 바랍니다.\n\n"
            "[조치3] 비상소화장치(소화기·소화전) 위치를 확인하고 사용법을 숙지하세요.\n\n"
            "[조치4] 출입구 주변 적재물을 정리하여 긴급대피 통로를 확보 바랍니다.\n\n"
            "* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)\n"
            "** 이것은 테스트 알림입니다"
        ),
    },
    'snow': {
        'title_kw': '폭설예보',
        'body': (
            "11월 13일 15시경부터 {name}에 적설량 10cm 이상 폭설이 예상됩니다.\n\n"
            "[조치1] 인근 가설천막 및 차양에 눈이 쌓이지 않도록 수시 점검 바랍니다.\n\n"
            "[조치2] 지붕 위 적설은 붕괴 위험이 있으므로 제설장비를 이용해 즉시 제거 바랍니다.\n\n"
            "[조치3] 통로 및 계단에는 미끄럼방지제(모래, 염화칼슘 등)를 살포해 주시기 바랍니다.\n\n"
            "* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)\n"
            "** 이것은 테스트 알림입니다"
        ),
    },
}


@weather_bp.route('/api/admin/weather-alerts/test-to-user', methods=['POST'])
def test_weather_alert_to_user():
    """관리자용 테스트: 특정 사용자에게 날씨 알림 전송"""
    from auth_utils import admin_required
    from fcm_integration.fcm_utils import fcm_service
    from models import User, Market

    @admin_required
    def _test_weather_alert_to_user(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}
            if not data:
                return jsonify({'error': '요청 데이터가 없습니다.'}), 400

            user_id = data.get('user_id')
            market_id = data.get('market_id')
            alert_type = data.get('alert_type', 'rain')

            if not user_id:
                return jsonify({'error': 'user_id는 필수 입력사항입니다.'}), 400
            if not market_id:
                return jsonify({'error': 'market_id는 필수 입력사항입니다.'}), 400

            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': f'사용자 ID {user_id}를 찾을 수 없습니다.'}), 404

            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': f'시장 ID {market_id}를 찾을 수 없습니다.'}), 404

            if not user.can_receive_fcm():
                return jsonify({
                    'error': f'사용자 {user.name}({user.email})은 FCM 알림을 받을 수 없는 상태입니다.',
                    'reason': {
                        'is_active': user.is_active,
                        'fcm_enabled': user.fcm_enabled,
                        'has_fcm_token': user.fcm_token is not None,
                    },
                }), 400

            is_dnd = user.is_in_do_not_disturb_time()
            ignore_dnd = data.get('ignore_dnd', False)

            if is_dnd and not ignore_dnd:
                return jsonify({
                    'error': f'사용자 {user.name}({user.email})은 현재 방해금지 시간입니다.',
                    'hint': 'ignore_dnd: true를 설정하면 방해금지 시간을 무시하고 전송할 수 있습니다.',
                }), 400

            template = _ALERT_TEMPLATES.get(alert_type)
            if not template:
                return jsonify({
                    'error': f'알 수 없는 알림 타입: {alert_type}',
                    'available_types': list(_ALERT_TEMPLATES.keys()),
                }), 400

            title = f"[{market.name} {template['title_kw']} - 테스트]"
            body = template['body'].format(name=market.name)

            if data.get('custom_title'):
                title = data.get('custom_title')
            if data.get('custom_body'):
                body = data.get('custom_body')

            notification_data = {
                'type': f'{alert_type}_alert_test',
                'market_id': str(market.id),
                'market_name': market.name,
                'is_test': 'true',
                'sent_by': current_user.email,
            }

            success = fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data,
            )

            logger.info(f"관리자 {current_user.email}가 사용자 {user.email}에게 {alert_type} 테스트 알림 전송")

            if success:
                return jsonify({
                    'status': 'success',
                    'message': f'사용자 {user.name}({user.email})에게 {alert_type} 알림이 전송되었습니다.',
                    'data': {
                        'user_id': user.id,
                        'user_name': user.name,
                        'user_email': user.email,
                        'market_id': market.id,
                        'market_name': market.name,
                        'alert_type': alert_type,
                        'title': title,
                        'is_dnd_ignored': is_dnd and ignore_dnd,
                        'fcm_result': {'success': success},
                    },
                })
            return jsonify({
                'status': 'error',
                'message': 'FCM 알림 전송 실패',
                'error': 'FCM notification failed',
            }), 500

        except Exception as e:
            logger.error(f"테스트 알림 전송 실패: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': '테스트 알림 전송에 실패했습니다'}), 500

    return _test_weather_alert_to_user()


@weather_bp.route('/api/admin/weather-alerts/test-summary', methods=['POST'])
def test_weather_summary_alert():
    """관리자용 테스트: 모든 관심 시장의 날씨 요약 알림 전송"""
    from auth_utils import admin_required
    from weather_alerts import send_test_weather_summary_to_all_users

    @admin_required
    def _test_weather_summary_alert(current_user):
        try:
            logger.info(f"관리자 {current_user.email}가 날씨 요약 테스트 알림을 요청했습니다.")

            result = send_test_weather_summary_to_all_users()

            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': '날씨 요약 알림 전송 완료',
                    'result': result,
                })
            return jsonify({
                'status': 'error',
                'message': '날씨 요약 알림 전송 실패',
                'error': result.get('error'),
            }), 500

        except Exception as e:
            logger.error(f"날씨 요약 알림 테스트 실패: {e}")
            return jsonify({'error': '날씨 요약 알림 테스트에 실패했습니다'}), 500

    return _test_weather_summary_alert()
