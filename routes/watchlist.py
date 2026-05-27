"""watchlist_bp: 사용자 관심 시장(워치리스트) 관리."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint('api_watchlist', __name__)


@watchlist_bp.route('/api/watchlist', methods=['GET'])
def get_user_watchlist():
    """사용자의 관심 시장 목록 조회"""
    from models import UserMarketInterest
    from auth_utils import login_required

    @login_required
    def _get_user_watchlist(current_user):
        try:
            interests = UserMarketInterest.query.filter_by(
                user_id=current_user.id,
                is_active=True,
            ).all()
            return jsonify({
                'count': len(interests),
                'watchlist': [interest.to_dict() for interest in interests],
            })
        except Exception as e:
            logger.error(f"관심 목록 조회 실패: {e}")
            return jsonify({'error': '관심 목록 조회에 실패했습니다'}), 500

    return _get_user_watchlist()


@watchlist_bp.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    """시장을 관심 목록에 추가"""
    from models import UserMarketInterest, Market
    from database import db
    from auth_utils import login_required

    @login_required
    def _add_to_watchlist(current_user):
        data = request.get_json(silent=True, force=True) or {}

        if not data.get('market_id'):
            return jsonify({'error': 'market_id가 필요합니다.'}), 400

        market_id = data.get('market_id')

        try:
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': '존재하지 않는 시장입니다.'}), 404

            if not market.is_active:
                return jsonify({'error': '비활성화된 시장입니다.'}), 400

            interest = UserMarketInterest.add_interest(current_user.id, market_id)
            db.session.add(interest)
            db.session.commit()

            return jsonify({
                'message': f'{market.name}이(가) 관심 목록에 추가되었습니다.',
                'interest': interest.to_dict(),
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"관심 목록 추가 실패: {e}")
            return jsonify({'error': '관심 목록 추가에 실패했습니다'}), 500

    return _add_to_watchlist()


@watchlist_bp.route('/api/watchlist/<int:market_id>', methods=['DELETE'])
def remove_from_watchlist(market_id):
    """시장을 관심 목록에서 제거"""
    from models import UserMarketInterest
    from database import db
    from auth_utils import login_required

    @login_required
    def _remove_from_watchlist(current_user):
        try:
            interest = UserMarketInterest.remove_interest(current_user.id, market_id)

            if not interest:
                return jsonify({'error': '관심 목록에 해당 시장이 없습니다.'}), 404

            db.session.commit()

            return jsonify({
                'message': '관심 목록에서 제거되었습니다.',
                'market_id': market_id,
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"관심 목록 제거 실패: {e}")
            return jsonify({'error': '관심 목록 제거에 실패했습니다'}), 500

    return _remove_from_watchlist()


@watchlist_bp.route('/api/watchlist/<int:interest_id>/notification', methods=['PUT'])
def toggle_notification_for_interest(interest_id):
    """특정 관심 시장의 알림 설정 토글"""
    from models import UserMarketInterest
    from database import db
    from auth_utils import login_required

    @login_required
    def _toggle_notification(current_user):
        try:
            interest = UserMarketInterest.query.filter_by(
                id=interest_id,
                user_id=current_user.id,
            ).first()

            if not interest:
                return jsonify({'error': '해당 관심 항목을 찾을 수 없습니다.'}), 404

            interest.notification_enabled = not interest.notification_enabled
            db.session.commit()

            status = "활성화" if interest.notification_enabled else "비활성화"
            return jsonify({
                'message': f'알림이 {status}되었습니다.',
                'interest': interest.to_dict(),
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"알림 설정 변경 실패: {e}")
            return jsonify({'error': '알림 설정 변경에 실패했습니다'}), 500

    return _toggle_notification()
