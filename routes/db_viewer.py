"""db_viewer_bp: 관리자 전용 DB 조회 뷰어."""

from flask import Blueprint, jsonify, redirect, request, url_for

db_viewer_bp = Blueprint('db_viewer', __name__)


def _require_admin_session():
    """db-viewer 페이지/엔드포인트용 세션 기반 관리자 권한 체크.

    Flask-Admin과 동일한 세션 키(`admin_user_id`)를 재사용한다.
    """
    from flask import session
    from models import User
    admin_id = session.get('admin_user_id')
    if not admin_id:
        return None
    user = User.query.get(admin_id)
    if not user or not user.is_admin():
        return None
    return user


@db_viewer_bp.route('/db-viewer')
def db_viewer():
    """데이터베이스 뷰어 메인 페이지 (관리자 전용)"""
    if not _require_admin_session():
        return redirect(url_for('admin.login_view'))
    from web_db_viewer import render_template_string, HTML_TEMPLATE
    return render_template_string(HTML_TEMPLATE)


@db_viewer_bp.route('/db-viewer/api/stats')
def api_stats():
    """데이터베이스 통계 API (관리자 전용)"""
    if not _require_admin_session():
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
    from models import User, Market, DamageStatus, Weather
    stats = {
        'users': User.query.count(),
        'markets': Market.query.count(),
        'weather_total': Weather.query.count(),
        'weather_current': Weather.query.filter_by(api_type='current').count(),
        'weather_forecast': Weather.query.filter_by(api_type='forecast').count(),
        'damage_statuses': DamageStatus.query.count(),
        'active_markets': Market.query.filter_by(is_active=True).count(),
        'markets_with_coordinates': Market.query.filter(
            Market.latitude.isnot(None),
            Market.longitude.isnot(None),
        ).count(),
        'latest_weather_update': None,
    }

    latest_weather = Weather.query.order_by(Weather.created_at.desc()).first()
    if latest_weather:
        stats['latest_weather_update'] = latest_weather.created_at.isoformat()

    return jsonify(stats)


@db_viewer_bp.route('/db-viewer/api/users')
def api_users():
    """사용자 데이터 API (관리자 전용)"""
    if not _require_admin_session():
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
    from models import User
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])


@db_viewer_bp.route('/db-viewer/api/markets')
def api_markets():
    """시장 데이터 API (관리자 전용)"""
    if not _require_admin_session():
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
    from models import Market
    markets = Market.query.all()
    return jsonify([market.to_dict() for market in markets])


@db_viewer_bp.route('/db-viewer/api/weather')
def api_weather():
    """날씨 데이터 API (관리자 전용)"""
    if not _require_admin_session():
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
    from models import Weather
    limit = request.args.get('limit', 100, type=int)
    weather_data = Weather.query.order_by(Weather.created_at.desc()).limit(limit).all()
    return jsonify([weather.to_dict() for weather in weather_data])


@db_viewer_bp.route('/db-viewer/api/damage')
def api_damage():
    """피해상태 데이터 API (관리자 전용)"""
    if not _require_admin_session():
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
    from models import DamageStatus
    damages = DamageStatus.query.all()
    return jsonify([damage.to_dict() for damage in damages])
