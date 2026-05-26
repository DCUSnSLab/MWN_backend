#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask-Admin 관리자 패널

관리자 전용 웹 기반 관리 인터페이스를 제공합니다.
"""

from flask import redirect, url_for, request, flash, session
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from flask_admin.model.template import EndpointLinkRowAction
from werkzeug.security import check_password_hash
from datetime import datetime, timezone
import logging

from database import db
from models import User, Market, Weather, DamageStatus, UserMarketInterest, MarketAlarmLog

logger = logging.getLogger(__name__)


class SecureAdminIndexView(AdminIndexView):
    """관리자 인증이 필요한 Admin 인덱스 뷰"""

    def is_visible(self):
        """메뉴에 표시 여부"""
        return True

    @expose('/')
    def index(self):
        # 로그인 체크
        if not self.is_accessible():
            return redirect(url_for('.login_view'))

        # 대시보드 통계
        stats = {
            'total_users': User.query.count(),
            'admin_users': User.query.filter_by(role='admin').count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'total_markets': Market.query.count(),
            'active_markets': Market.query.filter_by(is_active=True).count(),
            'total_weather_records': Weather.query.count(),
            'total_watchlist_items': UserMarketInterest.query.count(),
            'active_watchlist_items': UserMarketInterest.query.filter_by(is_active=True).count(),
        }

        # 최근 날씨 데이터
        latest_weather = Weather.query.order_by(Weather.created_at.desc()).limit(10).all()

        # 관심시장 많은 시장 TOP 5
        from sqlalchemy import func
        top_markets = db.session.query(
            Market.name,
            func.count(UserMarketInterest.id).label('interest_count')
        ).join(
            UserMarketInterest, Market.id == UserMarketInterest.market_id
        ).filter(
            UserMarketInterest.is_active == True
        ).group_by(
            Market.id, Market.name
        ).order_by(
            func.count(UserMarketInterest.id).desc()
        ).limit(5).all()

        return self.render('admin/index.html',
                         stats=stats,
                         latest_weather=latest_weather,
                         top_markets=top_markets)

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password) and user.is_admin():
                session['admin_user_id'] = user.id
                session['admin_user_email'] = user.email
                flash('로그인 성공!', 'success')
                return redirect(url_for('.index'))
            else:
                flash('이메일 또는 비밀번호가 잘못되었거나 관리자 권한이 없습니다.', 'error')

        return self.render('admin/login.html')

    @expose('/logout/')
    def logout_view(self):
        session.pop('admin_user_id', None)
        session.pop('admin_user_email', None)
        flash('로그아웃되었습니다.', 'info')
        return redirect(url_for('.login_view'))

    def is_accessible(self):
        """관리자 권한 체크"""
        admin_id = session.get('admin_user_id')
        if admin_id:
            user = User.query.get(admin_id)
            return user and user.is_admin()
        return False

    def inaccessible_callback(self, name, **kwargs):
        """접근 불가 시 로그인 페이지로 리다이렉트"""
        # 이미 로그인 페이지에 있다면 리다이렉트하지 않음 (무한 루프 방지)
        if request.endpoint == 'admin.login_view':
            return None
        return redirect(url_for('.login_view'))


class SecureModelView(ModelView):
    """인증이 필요한 ModelView 베이스 클래스"""

    def is_accessible(self):
        """관리자 권한 체크"""
        admin_id = session.get('admin_user_id')
        if admin_id:
            user = User.query.get(admin_id)
            return user and user.is_admin()
        return False

    def inaccessible_callback(self, name, **kwargs):
        """접근 불가 시 로그인 페이지로 리다이렉트"""
        return redirect(url_for('admin.login_view'))


class UserAdminView(SecureModelView):
    """사용자 관리 뷰"""

    column_list = ['id', 'name', 'email', 'role', 'is_active', 'email_verified', 'fcm_enabled', 'created_at']
    column_searchable_list = ['name', 'email', 'phone']
    column_filters = ['role', 'is_active', 'email_verified', 'fcm_enabled', 'created_at']
    column_sortable_list = ['id', 'name', 'email', 'role', 'is_active', 'created_at']
    column_default_sort = ('created_at', True)

    column_labels = {
        'id': 'ID',
        'name': '이름',
        'email': '이메일',
        'phone': '전화번호',
        'role': '역할',
        'is_active': '활성',
        'email_verified': '이메일 인증',
        'fcm_enabled': 'FCM 활성화',
        'fcm_token': 'FCM 토큰',
        'created_at': '생성일',
        'location': '지역'
    }

    # 폼에서 제외할 필드
    form_excluded_columns = ['password_hash', 'email_verification_token', 'email_verification_sent_at',
                            'password_reset_token', 'password_reset_sent_at', 'fcm_token', 'fcm_topics']

    # 읽기 전용 필드
    form_widget_args = {
        'created_at': {'readonly': True},
    }

    # 리스트에서 표시 형식
    column_formatters = {
        'is_active': lambda v, c, m, n: '✅' if m.is_active else '❌',
        'email_verified': lambda v, c, m, n: '✅' if m.email_verified else '❌',
        'fcm_enabled': lambda v, c, m, n: '✅' if m.fcm_enabled else '❌',
        'role': lambda v, c, m, n: '👑 관리자' if m.role == 'admin' else '👤 사용자',
    }

    @action('activate', '활성화', '선택한 사용자를 활성화하시겠습니까?')
    def action_activate(self, ids):
        try:
            query = User.query.filter(User.id.in_(ids))
            count = query.update({User.is_active: True}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}명의 사용자를 활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')

    @action('deactivate', '비활성화', '선택한 사용자를 비활성화하시겠습니까?')
    def action_deactivate(self, ids):
        try:
            query = User.query.filter(User.id.in_(ids))
            count = query.update({User.is_active: False}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}명의 사용자를 비활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')


class MarketAdminView(SecureModelView):
    """시장 관리 뷰"""

    column_list = ['id', 'name', 'location', 'category', 'is_active', 'latitude', 'longitude', 'nx', 'ny']
    column_searchable_list = ['name', 'location', 'category']
    column_filters = ['category', 'is_active']
    column_sortable_list = ['id', 'name', 'location', 'category', 'is_active']
    column_default_sort = 'name'

    column_labels = {
        'id': 'ID',
        'name': '시장명',
        'location': '위치',
        'category': '카테고리',
        'is_active': '활성',
        'latitude': '위도',
        'longitude': '경도',
        'nx': '격자 X',
        'ny': '격자 Y',
        'description': '설명'
    }

    column_formatters = {
        'is_active': lambda v, c, m, n: '✅' if m.is_active else '❌',
    }

    @action('activate', '활성화', '선택한 시장을 활성화하시겠습니까?')
    def action_activate(self, ids):
        try:
            query = Market.query.filter(Market.id.in_(ids))
            count = query.update({Market.is_active: True}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}개의 시장을 활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')

    @action('deactivate', '비활성화', '선택한 시장을 비활성화하시겠습니까?')
    def action_deactivate(self, ids):
        try:
            query = Market.query.filter(Market.id.in_(ids))
            count = query.update({Market.is_active: False}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}개의 시장을 비활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')


class WeatherAdminView(SecureModelView):
    """날씨 데이터 뷰 (읽기 전용)"""

    can_create = False
    can_edit = False
    can_delete = False

    column_list = ['id', 'location_name', 'api_type', 'temp', 'humidity', 'rain_1h', 'wind_speed', 'created_at']
    column_searchable_list = ['location_name']
    column_filters = ['api_type', 'created_at', 'location_name']
    column_sortable_list = ['id', 'location_name', 'api_type', 'temp', 'created_at']
    column_default_sort = ('created_at', True)

    column_labels = {
        'id': 'ID',
        'location_name': '지역명',
        'api_type': 'API 타입',
        'temp': '기온(°C)',
        'humidity': '습도(%)',
        'rain_1h': '1시간 강수량(mm)',
        'wind_speed': '풍속(m/s)',
        'created_at': '수집시간',
        'base_date': '기준날짜',
        'base_time': '기준시간'
    }

    column_formatters = {
        'api_type': lambda v, c, m, n: '📍 현재' if m.api_type == 'current' else '📊 예보',
    }


class UserMarketInterestAdminView(SecureModelView):
    """관심시장 관리 뷰"""

    column_list = ['id', 'user', 'market', 'is_active', 'notification_enabled', 'created_at']
    column_filters = ['is_active', 'notification_enabled', 'created_at']
    column_sortable_list = ['id', 'created_at']
    column_default_sort = ('created_at', True)

    column_labels = {
        'id': 'ID',
        'user': '사용자',
        'market': '시장',
        'is_active': '활성',
        'notification_enabled': '알림 활성화',
        'created_at': '등록일'
    }

    column_formatters = {
        'user': lambda v, c, m, n: f"{m.user.name} ({m.user.email})" if m.user else 'N/A',
        'market': lambda v, c, m, n: m.market.name if m.market else 'N/A',
        'is_active': lambda v, c, m, n: '✅' if m.is_active else '❌',
        'notification_enabled': lambda v, c, m, n: '✅' if m.notification_enabled else '❌',
    }

    @action('enable_notifications', '알림 활성화', '선택한 항목의 알림을 활성화하시겠습니까?')
    def action_enable_notifications(self, ids):
        try:
            query = UserMarketInterest.query.filter(UserMarketInterest.id.in_(ids))
            count = query.update({UserMarketInterest.notification_enabled: True}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}개 항목의 알림을 활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')

    @action('disable_notifications', '알림 비활성화', '선택한 항목의 알림을 비활성화하시겠습니까?')
    def action_disable_notifications(self, ids):
        try:
            query = UserMarketInterest.query.filter(UserMarketInterest.id.in_(ids))
            count = query.update({UserMarketInterest.notification_enabled: False}, synchronize_session='fetch')
            db.session.commit()
            flash(f'{count}개 항목의 알림을 비활성화했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'오류 발생: {str(e)}', 'error')


class MarketAlarmLogAdminView(SecureModelView):
    """시장 알림 이력 뷰 (읽기 전용)"""

    can_create = False
    can_edit = False
    can_delete = False

    column_list = ['id', 'market', 'alert_type', 'alert_title', 'total_users', 'success_count',
                   'failure_count', 'forecast_time', 'created_at']
    column_searchable_list = ['alert_title', 'alert_body', 'forecast_time']
    column_filters = ['alert_type', 'created_at', 'market_id', 'forecast_time']
    column_sortable_list = ['id', 'created_at', 'alert_type', 'total_users', 'success_count']
    column_default_sort = ('created_at', True)

    column_labels = {
        'id': 'ID',
        'market': '시장',
        'alert_type': '알림 유형',
        'alert_title': '알림 제목',
        'alert_body': '알림 내용',
        'total_users': '전체 사용자',
        'success_count': '성공',
        'failure_count': '실패',
        'temperature': '기온(°C)',
        'rain_probability': '강수확률(%)',
        'wind_speed': '풍속(m/s)',
        'precipitation_type': '강수형태',
        'forecast_time': '예보시간',
        'checked_hours': '예보범위(시간)',
        'weather_data': '날씨 데이터',
        'created_at': '전송시간'
    }

    column_formatters = {
        'market': lambda v, c, m, n: m.market.name if m.market else 'N/A',
        'alert_type': lambda v, c, m, n: {
            'rain': '🌧️ 강수',
            'high_temp': '🌡️ 폭염',
            'low_temp': '❄️ 한파',
            'strong_wind': '💨 강풍',
            'snow': '⛄ 적설'
        }.get(m.alert_type, m.alert_type),
        'alert_title': lambda v, c, m, n: m.alert_title[:50] + '...' if len(m.alert_title) > 50 else m.alert_title,
    }

    column_descriptions = {
        'alert_type': '알림 유형 (rain: 강수, high_temp: 폭염, low_temp: 한파, strong_wind: 강풍, snow: 적설)',
        'total_users': '알림 대상 사용자 수',
        'success_count': 'FCM 전송 성공 수',
        'failure_count': 'FCM 전송 실패 수',
    }

    # 상세 보기에서 표시할 필드
    column_details_list = ['id', 'market', 'alert_type', 'alert_title', 'alert_body',
                          'total_users', 'success_count', 'failure_count',
                          'temperature', 'rain_probability', 'wind_speed', 'precipitation_type',
                          'forecast_time', 'checked_hours', 'weather_data', 'created_at']


class SystemControlView(BaseView):
    """시스템 제어 뷰 (스케줄러, 알림 등)"""

    @expose('/')
    def index(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        # 스케줄러 상태
        from weather_scheduler import weather_scheduler
        scheduler_status = weather_scheduler.get_job_status()

        # 통계
        from weather_scheduler import get_weather_stats
        weather_stats = get_weather_stats()

        # 활성 시장 목록 (테스트 알림용)
        from models import Market
        active_markets = Market.query.filter_by(is_active=True).order_by(Market.name).all()

        return self.render('admin/system_control.html',
                         scheduler_status=scheduler_status,
                         weather_stats=weather_stats,
                         markets=active_markets)

    @expose('/weather-collect/', methods=['POST'])
    def collect_weather(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        try:
            from weather_scheduler import weather_scheduler
            weather_scheduler.collect_market_weather_data()
            flash('날씨 데이터 수집이 시작되었습니다.', 'success')
        except Exception as e:
            flash(f'오류 발생: {str(e)}', 'error')

        return redirect(url_for('.index'))

    @expose('/weather-alert/', methods=['POST'])
    def send_weather_alert(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        try:
            hours = request.form.get('hours', 24, type=int)
            from weather_alerts import check_and_send_all_weather_alerts
            result = check_and_send_all_weather_alerts(hours)

            if result.get('success'):
                flash(f"날씨 알림 전송 완료: {result.get('message')}", 'success')
            else:
                flash(f"날씨 알림 전송 실패: {result.get('error')}", 'error')
        except Exception as e:
            flash(f'오류 발생: {str(e)}', 'error')

        return redirect(url_for('.index'))

    @expose('/scheduler-start/', methods=['POST'])
    def start_scheduler(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        try:
            from weather_scheduler import start_weather_scheduler
            start_weather_scheduler()
            flash('스케줄러를 시작했습니다.', 'success')
        except Exception as e:
            flash(f'오류 발생: {str(e)}', 'error')

        return redirect(url_for('.index'))

    @expose('/scheduler-stop/', methods=['POST'])
    def stop_scheduler(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        try:
            from weather_scheduler import stop_weather_scheduler
            stop_weather_scheduler()
            flash('스케줄러를 중지했습니다.', 'warning')
        except Exception as e:
            flash(f'오류 발생: {str(e)}', 'error')

        return redirect(url_for('.index'))

    @expose('/test-notification/', methods=['POST'])
    def send_test_notification(self):
        """테스트 알림 전송"""
        if not self.is_accessible():
            return redirect(url_for('admin.login_view'))

        try:
            market_id = request.form.get('market_id', type=int)
            title = request.form.get('title', '').strip()
            body = request.form.get('body', '').strip()

            # 입력 검증
            if not market_id:
                flash('시장을 선택해주세요.', 'error')
                return redirect(url_for('.index'))

            if not title or not body:
                flash('제목과 내용을 입력해주세요.', 'error')
                return redirect(url_for('.index'))

            # 시장 조회
            from models import Market, UserMarketInterest
            market = Market.query.get(market_id)
            if not market:
                flash('선택한 시장을 찾을 수 없습니다.', 'error')
                return redirect(url_for('.index'))

            # 해당 시장에 관심을 가진 사용자들 조회
            interested_users = market.get_interested_users()

            if not interested_users:
                flash(f'{market.name}에 관심을 가진 사용자가 없습니다.', 'warning')
                return redirect(url_for('.index'))

            # FCM 토큰 수집
            fcm_tokens = []
            valid_users = []

            for user in interested_users:
                if user.can_receive_fcm():
                    fcm_tokens.append(user.fcm_token)
                    valid_users.append(user)

            if not fcm_tokens:
                flash(f'{market.name}에 관심을 가진 사용자 중 FCM 알림을 받을 수 있는 사용자가 없습니다.', 'warning')
                return redirect(url_for('.index'))

            # FCM 알림 전송
            from fcm_integration.fcm_utils import fcm_service

            notification_data = {
                'type': 'test_notification',
                'market_id': str(market.id),
                'market_name': market.name,
            }

            result = fcm_service.send_multicast(
                tokens=fcm_tokens,
                title=title,
                body=body,
                data=notification_data
            )

            success_count = result.get('success_count', 0) if result else 0
            failure_count = result.get('failure_count', 0) if result else len(valid_users)

            logger.info(f"테스트 알림 전송 - 시장: {market.name}, 대상: {len(valid_users)}명, 성공: {success_count}명, 실패: {failure_count}명")

            # 알림 로그 기록
            from models import MarketAlarmLog
            from database import db
            from datetime import datetime, timezone

            alarm_log = MarketAlarmLog(
                market_id=market.id,
                alert_type='test',
                alert_title=title,
                alert_body=body,
                total_users=len(valid_users),
                success_count=success_count,
                failure_count=failure_count,
                weather_data={'type': 'test_notification'},
                created_at=datetime.now(timezone.utc)
            )

            db.session.add(alarm_log)
            db.session.commit()

            flash(f'테스트 알림을 전송했습니다. (대상: {len(valid_users)}명, 성공: {success_count}명, 실패: {failure_count}명)', 'success')

        except Exception as e:
            logger.error(f"테스트 알림 전송 오류: {e}")
            import traceback
            traceback.print_exc()
            flash(f'오류 발생: {str(e)}', 'error')

        return redirect(url_for('.index'))

    def is_accessible(self):
        """관리자 권한 체크"""
        admin_id = session.get('admin_user_id')
        if admin_id:
            user = User.query.get(admin_id)
            return user and user.is_admin()
        return False

    def inaccessible_callback(self, name, **kwargs):
        """접근 불가 시 로그인 페이지로 리다이렉트"""
        return redirect(url_for('admin.login_view'))


def init_admin(app, db):
    """Flask-Admin 초기화"""

    # Admin 인스턴스 생성
    admin = Admin(
        app,
        name='날씨 알림 시스템',
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView(name='대시보드', url='/admin')
    )

    # 모델 뷰 추가
    admin.add_view(UserAdminView(User, db.session, name='사용자 관리', category='사용자'))
    admin.add_view(MarketAdminView(Market, db.session, name='시장 관리', category='시장'))
    admin.add_view(WeatherAdminView(Weather, db.session, name='날씨 데이터', category='날씨'))
    admin.add_view(UserMarketInterestAdminView(UserMarketInterest, db.session,
                                               name='관심시장 관리', category='사용자'))
    admin.add_view(MarketAlarmLogAdminView(MarketAlarmLog, db.session,
                                          name='알림 이력', category='날씨'))

    # 시스템 제어 뷰 추가
    admin.add_view(SystemControlView(name='시스템 제어', endpoint='system_control', category='시스템'))

    logger.info("Flask-Admin 관리자 패널이 초기화되었습니다.")

    return admin
