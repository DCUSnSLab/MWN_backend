"""auth_bp: 회원가입 / 로그인 / 토큰 갱신 / 프로필 / 회원 탈퇴 / 사용자 목록."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/users', methods=['GET'])
def get_users():
    """사용자 목록 조회 (관리자용)"""
    from models import User
    from auth_utils import admin_required

    @admin_required
    def _get_users(current_user):
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])

    return _get_users()


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """회원가입"""
    from models import User
    from database import db
    from auth_utils import validate_email, validate_password, generate_tokens

    data = request.get_json(silent=True, force=True) or {}

    required_fields = ['name', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400

    name = data.get('name').strip()
    email = data.get('email').strip().lower()
    password = data.get('password')
    phone = (data.get('phone') or '').strip()
    location = (data.get('location') or '').strip()

    if not validate_email(email):
        return jsonify({'error': '올바른 이메일 형식이 아닙니다.'}), 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': '이미 사용 중인 이메일입니다.'}), 400

    try:
        user = User(
            name=name,
            email=email,
            phone=phone,
            location=location,
            role='user',
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        tokens = generate_tokens(user.id)

        return jsonify({
            'message': '회원가입이 완료되었습니다.',
            'user': user.to_dict(),
            'tokens': tokens,
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"회원가입 실패: {e}")
        return jsonify({'error': '회원가입 중 오류가 발생했습니다'}), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """로그인"""
    from models import User
    from database import db
    from auth_utils import generate_tokens

    data = request.get_json(silent=True, force=True) or {}

    if not data.get('email') or not data.get('password'):
        return jsonify({'error': '이메일과 패스워드를 입력해주세요.'}), 400

    email = data.get('email').strip().lower()
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'error': '이메일 또는 패스워드가 올바르지 않습니다.'}), 401

    if not user.is_active:
        return jsonify({'error': '비활성화된 계정입니다.'}), 401

    try:
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        tokens = generate_tokens(user.id)

        return jsonify({
            'message': '로그인에 성공했습니다.',
            'user': user.to_dict(),
            'tokens': tokens,
        })

    except Exception as e:
        logger.error(f"로그인 실패: {e}")
        return jsonify({'error': '로그인 중 오류가 발생했습니다'}), 500


@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """토큰 갱신"""
    from models import User
    from auth_utils import verify_token, generate_tokens

    data = request.get_json(silent=True, force=True) or {}
    refresh_token_str = data.get('refresh_token')

    if not refresh_token_str:
        return jsonify({'error': '리프레시 토큰이 필요합니다.'}), 400

    payload = verify_token(refresh_token_str, token_type='refresh')
    if not payload:
        return jsonify({'error': '유효하지 않은 리프레시 토큰입니다.'}), 401

    user = User.query.get(payload['user_id'])
    if not user or not user.is_active:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 401

    tokens = generate_tokens(user.id)

    return jsonify({
        'message': '토큰이 갱신되었습니다.',
        'tokens': tokens,
    })


@auth_bp.route('/api/auth/me', methods=['GET'])
def get_profile():
    """현재 사용자 프로필 조회"""
    from auth_utils import login_required

    @login_required
    def _get_profile(current_user):
        return jsonify({'user': current_user.to_dict()})

    return _get_profile()


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """로그아웃 (클라이언트에서 토큰 삭제)"""
    return jsonify({'message': '로그아웃되었습니다.'})


@auth_bp.route('/api/auth/verify-password', methods=['POST'])
def verify_password():
    """비밀번호 확인 (프로필 수정 전 본인 인증용)"""
    from auth_utils import login_required
    from models import PasswordVerificationAttempt

    @login_required
    def _verify_password(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data.get('password'):
            return jsonify({'error': '비밀번호를 입력해주세요.'}), 400

        is_locked, failure_count = PasswordVerificationAttempt.check_account_lock(
            user_id=current_user.id,
            minutes=15,
            max_failures=10,
        )
        if is_locked:
            logger.warning(f"Account locked for user {current_user.email} due to too many failed password verification attempts")
            return jsonify({
                'error': '너무 많은 시도로 인해 계정이 일시적으로 잠겼습니다. 15분 후 다시 시도해주세요.',
                'locked': True,
                'failure_count': failure_count,
            }), 429

        is_allowed, remaining = PasswordVerificationAttempt.check_rate_limit(
            user_id=current_user.id,
            minutes=1,
            max_attempts=5,
        )
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for user {current_user.email} during password verification")
            return jsonify({
                'error': '너무 많은 요청입니다. 잠시 후 다시 시도해주세요.',
                'remaining_attempts': remaining,
            }), 429

        password = data.get('password')
        is_valid = current_user.check_password(password)

        ip_address = request.remote_addr
        PasswordVerificationAttempt.record_attempt(
            user_id=current_user.id,
            success=is_valid,
            ip_address=ip_address,
        )

        if is_valid:
            logger.info(f"Password verification successful for user {current_user.email}")
            return jsonify({'valid': True, 'message': '비밀번호가 확인되었습니다.'})
        else:
            logger.warning(f"Password verification failed for user {current_user.email}")
            return jsonify({'valid': False, 'message': '비밀번호가 일치하지 않습니다.'}), 401

    return _verify_password()


@auth_bp.route('/api/auth/profile', methods=['PUT'])
def update_profile():
    """사용자 프로필 업데이트"""
    from auth_utils import login_required, validate_email, validate_password
    from models import User
    from database import db

    @login_required
    def _update_profile(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data:
            return jsonify({'error': '업데이트할 정보를 입력해주세요.'}), 400

        updated_fields = []

        try:
            if 'name' in data:
                name = data.get('name', '').strip()
                if not name:
                    return jsonify({'error': '이름은 필수 입력사항입니다.'}), 400
                current_user.name = name
                updated_fields.append('name')

            if 'email' in data:
                email = data.get('email', '').strip().lower()
                if not validate_email(email):
                    return jsonify({'error': '올바른 이메일 형식이 아닙니다.'}), 400

                existing_user = User.query.filter(
                    User.email == email,
                    User.id != current_user.id,
                ).first()
                if existing_user:
                    return jsonify({'error': '이미 사용 중인 이메일입니다.'}), 400

                current_user.email = email
                current_user.email_verified = False
                updated_fields.append('email')
                logger.info(f"Email changed for user {current_user.id}. Email verification reset.")

            if 'password' in data:
                password = data.get('password')
                is_valid, message = validate_password(password)
                if not is_valid:
                    return jsonify({'error': message}), 400
                current_user.set_password(password)
                updated_fields.append('password')
                logger.info(f"Password changed for user {current_user.email}")

            if 'phone' in data:
                phone = data.get('phone', '').strip()
                current_user.phone = phone if phone else None
                updated_fields.append('phone')

            if 'location' in data:
                location = data.get('location', '').strip()
                current_user.location = location if location else None
                updated_fields.append('location')

            if not updated_fields:
                return jsonify({'message': '업데이트할 정보가 없습니다.'}), 400

            current_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            logger.info(f"Profile updated for user {current_user.email}. Updated fields: {', '.join(updated_fields)}")

            user_dict = current_user.to_dict()
            user_dict.pop('password_hash', None)

            return jsonify({
                'status': 'success',
                'message': '프로필이 성공적으로 업데이트되었습니다.',
                'updated_fields': updated_fields,
                'user': user_dict,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile for user {current_user.email}: {e}")
            return jsonify({'error': '프로필 업데이트 중 오류가 발생했습니다'}), 500

    return _update_profile()


@auth_bp.route('/api/auth/delete', methods=['POST'])
def delete_account():
    """회원 탈퇴"""
    from auth_utils import login_required
    from database import db

    @login_required
    def _delete_account(current_user):
        data = request.get_json(silent=True, force=True) or {}
        deletion_reason = data.get('reason', 'No reason provided.')

        try:
            current_user.is_active = False
            current_user.is_deleted = True
            current_user.deleted_at = datetime.now(timezone.utc)
            current_user.deletion_reason = deletion_reason

            current_user.password_hash = 'deleted'
            current_user.fcm_token = None
            current_user.fcm_enabled = False

            db.session.commit()

            logger.info(f"User {current_user.email} (ID: {current_user.id}) has been deleted.")

            return jsonify({
                'status': 'success',
                'message': '회원 탈퇴 처리가 완료되었습니다. 이용해주셔서 감사합니다.',
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during account deletion for user {current_user.email}: {e}")
            return jsonify({'error': '회원 탈퇴 중 오류가 발생했습니다'}), 500

    return _delete_account()
