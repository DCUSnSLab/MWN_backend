"""fcm_bp: FCM 토큰 등록·설정·테스트 + 방해금지 시간 설정."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

fcm_bp = Blueprint('fcm', __name__)


@fcm_bp.route('/api/fcm/register', methods=['POST'])
def register_fcm_token():
    """FCM 토큰 등록/업데이트"""
    from auth_utils import login_required
    from models import User
    from database import db

    @login_required
    def _register_fcm_token(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data.get('token'):
            return jsonify({'error': 'FCM 토큰이 필요합니다.'}), 400

        try:
            fcm_token = data.get('token')
            device_info = data.get('device_info', {})

            existing_users = User.query.filter(
                User.fcm_token == fcm_token,
                User.id != current_user.id,
            ).all()
            if existing_users:
                for old_user in existing_users:
                    logger.info(f"Duplicate FCM token found. Clearing token for user {old_user.id} ({old_user.email})")
                    old_user.fcm_token = None
                    old_user.fcm_enabled = False

            current_user.update_fcm_token(fcm_token, device_info)
            db.session.commit()

            topics = data.get('subscribe_topics', ['weather_alerts'])
            for topic in topics:
                current_user.subscribe_to_topic(topic)

            db.session.commit()

            return jsonify({
                'message': 'FCM 토큰이 등록되었습니다.',
                'fcm_enabled': current_user.fcm_enabled,
                'subscribed_topics': current_user.fcm_topics,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"FCM 토큰 등록 실패: {e}")
            return jsonify({'error': 'FCM 토큰 등록에 실패했습니다'}), 500

    return _register_fcm_token()


@fcm_bp.route('/api/fcm/settings', methods=['GET', 'POST'])
def fcm_settings():
    """FCM 설정 조회/업데이트"""
    from auth_utils import login_required
    from database import db

    @login_required
    def _fcm_settings(current_user):
        if request.method == 'GET':
            return jsonify({
                'fcm_enabled': current_user.fcm_enabled,
                'fcm_topics': current_user.fcm_topics or [],
                'device_info': current_user.device_info,
                'has_token': current_user.fcm_token is not None,
            })

        # POST
        data = request.get_json(silent=True, force=True) or {}

        try:
            if 'enabled' in data:
                if data['enabled']:
                    current_user.enable_fcm()
                else:
                    current_user.disable_fcm()

            if 'subscribe_topics' in data:
                for topic in data['subscribe_topics']:
                    current_user.subscribe_to_topic(topic)

            if 'unsubscribe_topics' in data:
                for topic in data['unsubscribe_topics']:
                    current_user.unsubscribe_from_topic(topic)

            db.session.commit()

            return jsonify({
                'message': 'FCM 설정이 업데이트되었습니다.',
                'fcm_enabled': current_user.fcm_enabled,
                'fcm_topics': current_user.fcm_topics or [],
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"FCM 설정 업데이트 실패: {e}")
            return jsonify({'error': 'FCM 설정 업데이트에 실패했습니다'}), 500

    return _fcm_settings()


@fcm_bp.route('/api/user/do-not-disturb', methods=['GET'])
def get_do_not_disturb():
    """사용자의 방해금지 시간 설정 조회"""
    from auth_utils import login_required

    @login_required
    def _get_do_not_disturb(current_user):
        try:
            dnd_settings = current_user.do_not_disturb or {
                'enabled': False,
                'start_time': '22:00',
                'end_time': '08:00',
                'all_day': False,
                'days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
            }
            return jsonify({'status': 'success', 'do_not_disturb': dnd_settings})

        except Exception as e:
            logger.error(f"방해금지 설정 조회 실패: {e}")
            return jsonify({'error': '방해금지 설정 조회에 실패했습니다'}), 500

    return _get_do_not_disturb()


@fcm_bp.route('/api/user/do-not-disturb', methods=['PUT'])
def update_do_not_disturb():
    """사용자의 방해금지 시간 설정 업데이트"""
    from auth_utils import login_required
    from database import db

    @login_required
    def _update_do_not_disturb(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data:
            return jsonify({'error': '방해금지 설정 데이터가 필요합니다.'}), 400

        try:
            allowed_fields = {'enabled', 'start_time', 'end_time', 'all_day', 'days'}
            update_data = {}
            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]

            if not update_data:
                return jsonify({'error': '업데이트할 설정이 없습니다.'}), 400

            if 'start_time' in update_data:
                try:
                    hour, minute = map(int, update_data['start_time'].split(':'))
                    if not (0 <= hour < 24 and 0 <= minute < 60):
                        return jsonify({'error': 'start_time 형식이 올바르지 않습니다. (HH:MM)'}), 400
                except (ValueError, AttributeError):
                    return jsonify({'error': 'start_time 형식이 올바르지 않습니다. (HH:MM)'}), 400

            if 'end_time' in update_data:
                try:
                    hour, minute = map(int, update_data['end_time'].split(':'))
                    if not (0 <= hour < 24 and 0 <= minute < 60):
                        return jsonify({'error': 'end_time 형식이 올바르지 않습니다. (HH:MM)'}), 400
                except (ValueError, AttributeError):
                    return jsonify({'error': 'end_time 형식이 올바르지 않습니다. (HH:MM)'}), 400

            if 'days' in update_data:
                valid_days = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
                if not isinstance(update_data['days'], list):
                    return jsonify({'error': 'days는 배열이어야 합니다.'}), 400
                if not all(day in valid_days for day in update_data['days']):
                    return jsonify({'error': f'유효한 요일: {", ".join(valid_days)}'}), 400

            current_user.update_do_not_disturb(update_data)
            db.session.commit()

            logger.info(f"사용자 {current_user.email}의 방해금지 설정이 업데이트되었습니다: {update_data}")

            return jsonify({
                'status': 'success',
                'message': '방해금지 설정이 업데이트되었습니다.',
                'do_not_disturb': current_user.do_not_disturb,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"방해금지 설정 업데이트 실패: {e}")
            return jsonify({'error': '방해금지 설정 업데이트에 실패했습니다'}), 500

    return _update_do_not_disturb()


@fcm_bp.route('/api/fcm/test', methods=['POST'])
def test_fcm_notification():
    """FCM 테스트 알림 전송"""
    from auth_utils import login_required
    from fcm_integration.fcm_utils import fcm_service

    @login_required
    def _test_fcm_notification(current_user):
        if not current_user.can_receive_fcm():
            return jsonify({'error': 'FCM 알림을 받을 수 없는 상태입니다.'}), 400

        try:
            success = fcm_service.send_notification(
                token=current_user.fcm_token,
                title="🧪 테스트 알림",
                body="FCM 설정이 정상적으로 작동합니다!",
                data={'type': 'test', 'user_id': str(current_user.id)},
            )

            if success:
                return jsonify({'message': '테스트 알림이 전송되었습니다.'})
            return jsonify({'error': '테스트 알림 전송에 실패했습니다.'}), 500

        except Exception as e:
            logger.error(f"테스트 알림 전송 실패: {e}")
            return jsonify({'error': '테스트 알림 전송에 실패했습니다'}), 500

    return _test_fcm_notification()
