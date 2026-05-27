"""alarm_logs_bp: FCM 알림 발송 이력 조회 (관리자/사용자/시장별)."""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

alarm_logs_bp = Blueprint('api_alarm_logs', __name__)


@alarm_logs_bp.route('/api/admin/logs/alerts', methods=['GET'])
def get_admin_alert_logs():
    """관리자용 알림 전송 이력 조회"""
    from models import MarketAlarmLog
    from auth_utils import admin_required

    @admin_required
    def _get_logs(current_user):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        market_id = request.args.get('market_id', type=int)

        query = MarketAlarmLog.query

        if market_id:
            query = query.filter_by(market_id=market_id)

        query = query.order_by(MarketAlarmLog.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'logs': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'has_next': pagination.has_next,
        })

    return _get_logs()


@alarm_logs_bp.route('/api/user/logs/alerts', methods=['GET'])
def get_user_alert_logs():
    """사용자용 알림 전송 이력 조회 (관심 시장만)"""
    from models import MarketAlarmLog, UserMarketInterest
    from database import db
    from auth_utils import login_required

    @login_required
    def _get_user_logs(current_user):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        interested_market_ids = db.session.query(UserMarketInterest.market_id).filter_by(
            user_id=current_user.id,
            is_active=True,
        ).all()
        market_ids = [m[0] for m in interested_market_ids]

        if not market_ids:
            return jsonify({
                'logs': [],
                'total': 0,
                'pages': 0,
                'current_page': page,
                'has_next': False,
                'message': '등록된 관심 시장이 없습니다.',
            })

        query = MarketAlarmLog.query.filter(
            MarketAlarmLog.market_id.in_(market_ids)
        ).order_by(MarketAlarmLog.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'logs': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'has_next': pagination.has_next,
        })

    return _get_user_logs()


@alarm_logs_bp.route('/api/alarm-logs', methods=['GET'])
def get_alarm_logs():
    """알림 이력 목록 조회 (페이지네이션 및 필터링 지원)"""
    from models import MarketAlarmLog, UserMarketInterest
    from auth_utils import login_required

    @login_required
    def _get_alarm_logs(current_user):
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            market_id = request.args.get('market_id', type=int)
            alert_type = request.args.get('alert_type', type=str)
            start_date = request.args.get('start_date', type=str)
            end_date = request.args.get('end_date', type=str)

            query = MarketAlarmLog.query

            if not current_user.is_admin():
                user_market_ids = [interest.market_id for interest in
                                  UserMarketInterest.query.filter_by(
                                      user_id=current_user.id,
                                      is_active=True,
                                  ).all()]
                query = query.filter(MarketAlarmLog.market_id.in_(user_market_ids))

            if market_id:
                query = query.filter_by(market_id=market_id)

            if alert_type:
                query = query.filter_by(alert_type=alert_type)

            if start_date:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(MarketAlarmLog.created_at >= start_dt)

            if end_date:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(MarketAlarmLog.created_at <= end_dt)

            query = query.order_by(MarketAlarmLog.created_at.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            logs = []
            for log in pagination.items:
                log_data = {
                    'id': log.id,
                    'market_id': log.market_id,
                    'market_name': log.market.name if log.market else None,
                    'alert_type': log.alert_type,
                    'alert_title': log.alert_title,
                    'alert_body': log.alert_body,
                    'total_users': log.total_users,
                    'success_count': log.success_count,
                    'failure_count': log.failure_count,
                    'temperature': log.temperature,
                    'rain_probability': log.rain_probability,
                    'wind_speed': log.wind_speed,
                    'precipitation_type': log.precipitation_type,
                    'forecast_time': log.forecast_time,
                    'checked_hours': log.checked_hours,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                logs.append(log_data)

            return jsonify({
                'status': 'success',
                'data': logs,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev,
                },
            })

        except Exception as e:
            logger.error(f"알림 이력 조회 실패: {e}")
            return jsonify({'error': '알림 이력 조회에 실패했습니다'}), 500

    return _get_alarm_logs()


@alarm_logs_bp.route('/api/alarm-logs/<int:log_id>', methods=['GET'])
def get_alarm_log_detail(log_id):
    """특정 알림 이력 상세 조회"""
    from models import MarketAlarmLog, UserMarketInterest
    from auth_utils import login_required

    @login_required
    def _get_alarm_log_detail(current_user):
        try:
            log = MarketAlarmLog.query.get(log_id)

            if not log:
                return jsonify({'error': '알림 이력을 찾을 수 없습니다.'}), 404

            if not current_user.is_admin():
                is_interested = UserMarketInterest.query.filter_by(
                    user_id=current_user.id,
                    market_id=log.market_id,
                    is_active=True,
                ).first()

                if not is_interested:
                    return jsonify({'error': '접근 권한이 없습니다.'}), 403

            log_data = {
                'id': log.id,
                'market_id': log.market_id,
                'market_name': log.market.name if log.market else None,
                'alert_type': log.alert_type,
                'alert_title': log.alert_title,
                'alert_body': log.alert_body,
                'total_users': log.total_users,
                'success_count': log.success_count,
                'failure_count': log.failure_count,
                'weather_data': log.weather_data,
                'temperature': log.temperature,
                'rain_probability': log.rain_probability,
                'wind_speed': log.wind_speed,
                'precipitation_type': log.precipitation_type,
                'forecast_time': log.forecast_time,
                'checked_hours': log.checked_hours,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            }

            return jsonify({'status': 'success', 'data': log_data})

        except Exception as e:
            logger.error(f"알림 이력 상세 조회 실패: {e}")
            return jsonify({'error': '알림 이력 상세 조회에 실패했습니다'}), 500

    return _get_alarm_log_detail()


@alarm_logs_bp.route('/api/markets/<int:market_id>/alarm-logs', methods=['GET'])
def get_market_alarm_logs(market_id):
    """특정 시장의 알림 이력 조회"""
    from models import MarketAlarmLog, UserMarketInterest, Market
    from auth_utils import login_required

    @login_required
    def _get_market_alarm_logs(current_user):
        try:
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

            if not current_user.is_admin():
                is_interested = UserMarketInterest.query.filter_by(
                    user_id=current_user.id,
                    market_id=market_id,
                    is_active=True,
                ).first()

                if not is_interested:
                    return jsonify({'error': '접근 권한이 없습니다.'}), 403

            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            alert_type = request.args.get('alert_type', type=str)

            query = MarketAlarmLog.query.filter_by(market_id=market_id)

            if alert_type:
                query = query.filter_by(alert_type=alert_type)

            query = query.order_by(MarketAlarmLog.created_at.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            logs = []
            for log in pagination.items:
                log_data = {
                    'id': log.id,
                    'alert_type': log.alert_type,
                    'alert_title': log.alert_title,
                    'alert_body': log.alert_body,
                    'total_users': log.total_users,
                    'success_count': log.success_count,
                    'failure_count': log.failure_count,
                    'temperature': log.temperature,
                    'rain_probability': log.rain_probability,
                    'wind_speed': log.wind_speed,
                    'precipitation_type': log.precipitation_type,
                    'forecast_time': log.forecast_time,
                    'checked_hours': log.checked_hours,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                logs.append(log_data)

            return jsonify({
                'status': 'success',
                'market_id': market_id,
                'market_name': market.name,
                'data': logs,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev,
                },
            })

        except Exception as e:
            logger.error(f"시장 알림 이력 조회 실패: {e}")
            return jsonify({'error': '시장 알림 이력 조회에 실패했습니다'}), 500

    return _get_market_alarm_logs()
