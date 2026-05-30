"""main_bp: 헬스체크 / 정적 파일 / 개인정보·계정삭제 페이지."""

import logging
from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

logger = logging.getLogger(__name__)

main_bp = Blueprint('api_main', __name__)


@main_bp.route('/health')
def health_check():
    """Liveness probe — 프로세스 살아있음만 보고 DB 는 체크하지 않는다.
    (DB 일시 장애로 Pod 가 재시작되는 cascading 회피)"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})


@main_bp.route('/health/ready')
def readiness_check():
    """Readiness probe — DB 접근까지 확인. 실패 시 503 으로 트래픽 차단.
    livenessProbe 와 분리해 transient DB 장애가 pod 재시작을 유발하지 않도록 한다."""
    from database import db
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return jsonify({'status': 'ready', 'timestamp': datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.warning(f"readiness check 실패: {e}")
        return jsonify({'status': 'not_ready', 'error': 'database unavailable'}), 503


@main_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    """업로드된 파일 서빙"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@main_bp.route('/privacy')
def privacy():
    """개인정보처리방침 페이지"""
    return render_template('privacy.html')


@main_bp.route('/account-deletion', methods=['GET', 'POST'])
def account_deletion_page():
    """계정 삭제 페이지"""
    from models import User
    from database import db

    if request.method == 'GET':
        return render_template('account_deletion.html', message=None, deleted=False)

    # POST
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    reason = request.form.get('reason', '웹 페이지를 통한 삭제').strip()

    if not email or not password:
        return render_template(
            'account_deletion.html',
            message='이메일과 비밀번호를 입력해주세요.',
            message_type='error',
            deleted=False,
        )

    try:
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            logger.warning(f"계정 삭제 실패: 잘못된 인증 시도 ({email})")
            return render_template(
                'account_deletion.html',
                message='이메일 또는 비밀번호가 올바르지 않습니다.',
                message_type='error',
                deleted=False,
            )

        if user.is_deleted:
            return render_template(
                'account_deletion.html',
                message='이미 삭제된 계정입니다.',
                message_type='error',
                deleted=False,
            )

        user.is_active = False
        user.is_deleted = True
        user.deleted_at = datetime.now(timezone.utc)
        user.deletion_reason = reason if reason else '웹 페이지를 통한 삭제'
        user.password_hash = 'deleted'
        user.fcm_token = None
        user.fcm_enabled = False

        db.session.commit()
        logger.info(f"웹 페이지를 통한 계정 삭제 완료: {email} (ID: {user.id})")

        return render_template(
            'account_deletion.html',
            message='계정이 성공적으로 삭제되었습니다. 이용해 주셔서 감사합니다.',
            message_type='success',
            deleted=True,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"계정 삭제 중 오류 발생: {e}")
        return render_template(
            'account_deletion.html',
            message='계정 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
            message_type='error',
            deleted=False,
        )
