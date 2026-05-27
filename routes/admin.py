"""admin_bp: 관리자 전용 사용자/푸시 관리."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# 'admin' endpoint name은 Flask-Admin 이 이미 사용 중이므로 다른 이름을 쓴다.
admin_bp = Blueprint('api_admin', __name__)


@admin_bp.route('/api/admin/fcm/send', methods=['POST'])
def admin_send_fcm():
    """관리자용 FCM 알림 전송"""
    from fcm_integration.fcm_utils import fcm_service
    from models import User
    from auth_utils import admin_required

    @admin_required
    def _admin_send_fcm(current_user):
        data = request.get_json(silent=True, force=True) or {}

        required_fields = ['title', 'body']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400

        try:
            title = data.get('title')
            body = data.get('body')
            notification_data = data.get('data', {})

            if data.get('topic'):
                success = fcm_service.send_to_topic(
                    topic=data['topic'],
                    title=title,
                    body=body,
                    data=notification_data,
                )
                return jsonify({
                    'message': f"주제 '{data['topic']}'로 알림이 전송되었습니다.",
                    'success': success,
                })

            if data.get('user_ids'):
                users = User.query.filter(
                    User.id.in_(data['user_ids']),
                    User.fcm_token.isnot(None),
                    User.fcm_enabled == True,
                ).all()

                if not users:
                    return jsonify({'error': '알림을 받을 수 있는 사용자가 없습니다.'}), 400

                tokens = [user.fcm_token for user in users]
                result = fcm_service.send_multicast(tokens, title, body, notification_data)

                return jsonify({
                    'message': f'{len(users)}명의 사용자에게 알림이 전송되었습니다.',
                    'result': result,
                })

            users = User.query.filter(
                User.fcm_token.isnot(None),
                User.fcm_enabled == True,
                User.is_active == True,
            ).all()

            if not users:
                return jsonify({'error': '알림을 받을 수 있는 사용자가 없습니다.'}), 400

            tokens = [user.fcm_token for user in users]
            result = fcm_service.send_multicast(tokens, title, body, notification_data)

            return jsonify({
                'message': f'전체 {len(users)}명의 사용자에게 알림이 전송되었습니다.',
                'result': result,
            })

        except Exception as e:
            logger.error(f"알림 전송 실패: {e}")
            return jsonify({'error': '알림 전송에 실패했습니다'}), 500

    return _admin_send_fcm()


@admin_bp.route('/api/admin/users', methods=['POST'])
def create_user_admin():
    """관리자용 사용자 생성"""
    from models import User
    from database import db
    from auth_utils import admin_required

    @admin_required
    def _create_user_admin(current_user):
        data = request.get_json(silent=True, force=True) or {}

        required_fields = ['name', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400

        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': '이미 사용 중인 이메일입니다.'}), 400

        try:
            user = User(
                name=data.get('name'),
                email=data.get('email'),
                phone=data.get('phone'),
                location=data.get('location'),
                role=data.get('role', 'user'),
            )
            user.set_password(data.get('password'))

            db.session.add(user)
            db.session.commit()

            return jsonify({
                'message': '사용자가 생성되었습니다.',
                'user': user.to_dict(),
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"사용자 생성 실패: {e}")
            return jsonify({'error': '사용자 생성에 실패했습니다'}), 500

    return _create_user_admin()
