"""reports_bp: 시장 신고 접수 / 조회."""

import logging
import os
import uuid

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

reports_bp = Blueprint('api_reports', __name__)


@reports_bp.route('/api/reports', methods=['POST'])
def submit_report():
    """신고 접수 (이미지 포함)"""
    from models import MarketReport, Market
    from database import db
    from auth_utils import login_required

    @login_required
    def _submit_report(current_user):
        market_id = request.form.get('market_id')
        report_type = request.form.get('report_type')
        description = request.form.get('description')

        if not market_id or not report_type:
            return jsonify({'error': '필수 정보가 누락되었습니다.'}), 400

        market = Market.query.get(market_id)
        if not market:
            return jsonify({'error': '유효하지 않은 시장입니다.'}), 404

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                    return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400

                filename = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_path = f"/uploads/{filename}"

        report = MarketReport(
            user_id=current_user.id,
            market_id=market_id,
            report_type=report_type,
            description=description,
            image_path=image_path,
        )

        db.session.add(report)
        db.session.commit()

        return jsonify({
            'message': '신고가 접수되었습니다.',
            'report': report.to_dict(),
        }), 201

    return _submit_report()


@reports_bp.route('/api/reports', methods=['GET'])
def get_reports():
    """신고 내역 조회 (관리자용)"""
    from models import MarketReport, Market
    from auth_utils import admin_required

    @admin_required
    def _get_reports(current_user):
        reports = MarketReport.query.order_by(MarketReport.created_at.desc()).all()
        result = []
        for report in reports:
            market = Market.query.get(report.market_id)
            report_data = report.to_dict()
            report_data['market_name'] = market.name if market else '알 수 없음'
            result.append(report_data)
        return jsonify(result)

    return _get_reports()
