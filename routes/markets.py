"""markets_bp: 시장 정보 / 알림 조건 / 피해 신고."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

markets_bp = Blueprint('markets', __name__)


@markets_bp.route('/api/markets', methods=['GET', 'POST'])
def handle_markets():
    from models import Market
    from database import db

    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        is_active = request.args.get('is_active', type=str)

        query = Market.query

        if is_active is not None:
            query = query.filter_by(is_active=(is_active.lower() == 'true'))

        pagination = query.order_by(Market.name).paginate(
            page=page,
            per_page=per_page,
            error_out=False,
        )

        return jsonify({
            'status': 'success',
            'data': [market.to_dict() for market in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev,
            },
        })

    # POST
    from auth_utils import admin_required

    @admin_required
    def _create_market(current_user):
        data = request.get_json(silent=True, force=True) or {}
        market = Market(
            name=data.get('name'),
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            category=data.get('category'),
        )
        db.session.add(market)
        db.session.commit()
        return jsonify(market.to_dict()), 201

    return _create_market()


@markets_bp.route('/api/markets/search', methods=['GET'])
def search_markets():
    """시장 이름으로 검색"""
    from models import Market

    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)

    if not query:
        return jsonify({'error': '검색어를 입력해주세요.'}), 400

    if len(query) < 2:
        return jsonify({'error': '검색어는 최소 2글자 이상이어야 합니다.'}), 400

    try:
        markets = Market.search_by_name(query, limit)
        return jsonify({
            'query': query,
            'count': len(markets),
            'markets': [market.to_dict() for market in markets],
        })
    except Exception as e:
        logger.error(f"검색 실패: {e}")
        return jsonify({'error': '검색 중 오류가 발생했습니다'}), 500


@markets_bp.route('/api/markets/<int:market_id>', methods=['GET'])
def get_market_detail(market_id):
    """특정 시장 상세 정보 조회"""
    from models import Market

    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

        return jsonify({'status': 'success', 'data': market.to_dict()})
    except Exception as e:
        logger.error(f"시장 조회 실패: {e}")
        return jsonify({'error': '시장 조회에 실패했습니다'}), 500


@markets_bp.route('/api/markets/<int:market_id>/alert-conditions', methods=['GET'])
def get_market_alert_conditions(market_id):
    """특정 시장의 알림 조건 조회"""
    from models import Market

    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

        alert_conditions = market.alert_conditions or market.get_default_alert_conditions()

        return jsonify({
            'status': 'success',
            'market_id': market_id,
            'market_name': market.name,
            'alert_conditions': alert_conditions,
        })
    except Exception as e:
        logger.error(f"알림 조건 조회 실패: {e}")
        return jsonify({'error': '알림 조건 조회에 실패했습니다'}), 500


@markets_bp.route('/api/admin/markets/<int:market_id>/alert-conditions', methods=['PUT'])
def update_market_alert_conditions(market_id):
    """관리자용: 특정 시장의 알림 조건 설정/수정"""
    from models import Market
    from database import db
    from auth_utils import admin_required

    @admin_required
    def _update_alert_conditions(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data:
            return jsonify({'error': '알림 조건 데이터가 필요합니다.'}), 400

        try:
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

            allowed_fields = {
                'enabled', 'rain_probability', 'high_temp', 'low_temp',
                'wind_speed', 'snow_enabled', 'rain_enabled',
                'temp_enabled', 'wind_enabled',
            }
            update_conditions = {}
            for field in allowed_fields:
                if field in data:
                    update_conditions[field] = data[field]

            if not update_conditions:
                return jsonify({'error': '업데이트할 알림 조건이 없습니다.'}), 400

            market.update_alert_conditions(update_conditions)
            db.session.commit()

            logger.info(f"관리자 {current_user.email}가 시장 {market.name}의 알림 조건을 수정했습니다: {update_conditions}")

            return jsonify({
                'status': 'success',
                'message': '알림 조건이 업데이트되었습니다.',
                'market_id': market_id,
                'market_name': market.name,
                'alert_conditions': market.alert_conditions,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"알림 조건 업데이트 실패: {e}")
            return jsonify({'error': '알림 조건 업데이트에 실패했습니다'}), 500

    return _update_alert_conditions()


@markets_bp.route('/api/admin/markets/alert-conditions/bulk-update', methods=['POST'])
def bulk_update_alert_conditions():
    """관리자용: 여러 시장의 알림 조건 일괄 업데이트"""
    from models import Market
    from database import db
    from auth_utils import admin_required

    @admin_required
    def _bulk_update_alert_conditions(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data or 'market_ids' not in data or 'conditions' not in data:
            return jsonify({'error': 'market_ids와 conditions가 필요합니다.'}), 400

        market_ids = data.get('market_ids', [])
        conditions = data.get('conditions', {})

        if not market_ids:
            return jsonify({'error': '시장 ID 목록이 비어있습니다.'}), 400

        if not conditions:
            return jsonify({'error': '업데이트할 조건이 없습니다.'}), 400

        try:
            allowed_fields = {
                'enabled', 'rain_probability', 'high_temp', 'low_temp',
                'wind_speed', 'snow_enabled', 'rain_enabled',
                'temp_enabled', 'wind_enabled',
            }
            update_conditions = {}
            for field in allowed_fields:
                if field in conditions:
                    update_conditions[field] = conditions[field]

            if not update_conditions:
                return jsonify({'error': '업데이트할 유효한 조건이 없습니다.'}), 400

            markets = Market.query.filter(Market.id.in_(market_ids)).all()

            if not markets:
                return jsonify({'error': '유효한 시장을 찾을 수 없습니다.'}), 404

            updated_count = 0
            for market in markets:
                market.update_alert_conditions(update_conditions)
                updated_count += 1

            db.session.commit()

            logger.info(f"관리자 {current_user.email}가 {updated_count}개 시장의 알림 조건을 일괄 수정했습니다: {update_conditions}")

            return jsonify({
                'status': 'success',
                'message': f'{updated_count}개 시장의 알림 조건이 업데이트되었습니다.',
                'updated_count': updated_count,
                'conditions': update_conditions,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"일괄 알림 조건 업데이트 실패: {e}")
            return jsonify({'error': '일괄 업데이트에 실패했습니다'}), 500

    return _bulk_update_alert_conditions()


@markets_bp.route('/api/damage-status', methods=['GET', 'POST'])
def handle_damage_status():
    from models import DamageStatus
    from database import db

    if request.method == 'GET':
        damage_statuses = DamageStatus.query.all()
        return jsonify([status.to_dict() for status in damage_statuses])

    # POST
    from auth_utils import login_required

    @login_required
    def _create_damage_status(current_user):
        data = request.get_json(silent=True, force=True) or {}
        damage_status = DamageStatus(
            market_id=data.get('market_id'),
            weather_event=data.get('weather_event'),
            damage_level=data.get('damage_level'),
            description=data.get('description'),
            estimated_recovery_time=data.get('estimated_recovery_time'),
        )
        db.session.add(damage_status)
        db.session.commit()
        return jsonify(damage_status.to_dict()), 201

    return _create_damage_status()
