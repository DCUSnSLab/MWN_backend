from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_cors import CORS
from datetime import datetime, timezone
import os
import logging
from database import db
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# 환경변수 로드 (.env 파일)
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('FLASK_ENV') == 'development' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ProxyFix: LoadBalancer/Reverse Proxy 뒤에서 실행될 때 필요
# X-Forwarded-* 헤더를 올바르게 처리
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # X-Forwarded-For
    x_proto=1,    # X-Forwarded-Proto (http/https 판단)
    x_host=1,     # X-Forwarded-Host
    x_prefix=1    # X-Forwarded-Prefix
)

# CORS: 웹 관리자(브라우저)에서 /api/* 엔드포인트 호출을 허용한다.
# CORS_ORIGINS 환경변수(쉼표 구분)로 허용 출처를 지정하며, 미설정 시 모든 출처를 허용한다.
# API는 쿠키가 아닌 Authorization 헤더(Bearer 토큰)로 인증하므로 와일드카드 출처도 안전하다.
_cors_origins_raw = os.environ.get('CORS_ORIGINS', '*').strip()
_cors_origins = '*' if _cors_origins_raw == '*' else [
    o.strip() for o in _cors_origins_raw.split(',') if o.strip()
]
CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

# Database configuration
# PostgreSQL connection string
default_db_url = 'postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', default_db_url)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY environment variable is required in production')
    logger.warning('SECRET_KEY not set; falling back to insecure development value')
    _secret_key = 'dev-secret-key-DO-NOT-USE-IN-PROD'
app.config['SECRET_KEY'] = _secret_key
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max limit

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# URL 스키마 처리 (LoadBalancer 환경)
app.config['PREFERRED_URL_SCHEME'] = os.environ.get('PREFERRED_URL_SCHEME', 'http')
# 프록시 뒤에서 실행 시 리다이렉트 URL 올바르게 생성
app.config['APPLICATION_ROOT'] = os.environ.get('APPLICATION_ROOT', '/')

# Initialize with app
db.init_app(app)
migrate = Migrate(app, db)

# Flask-Admin 초기화 (모델을 import하기 전에 admin_panel을 import)
from admin_panel import init_admin
admin = init_admin(app, db)

# Blueprint 등록 — 도메인별 라우트 모듈
from routes.main import main_bp
from routes.reports import reports_bp
from routes.watchlist import watchlist_bp
from routes.db_viewer import db_viewer_bp
from routes.alarm_logs import alarm_logs_bp
from routes.auth import auth_bp
from routes.fcm import fcm_bp
app.register_blueprint(main_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(watchlist_bp)
app.register_blueprint(db_viewer_bp)
app.register_blueprint(alarm_logs_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(fcm_bp)

# Models will be imported later to avoid circular import

@app.errorhandler(404)
def handle_not_found(e):
    return jsonify({'error': '요청한 리소스를 찾을 수 없습니다.'}), 404


@app.errorhandler(405)
def handle_method_not_allowed(e):
    return jsonify({'error': '허용되지 않은 요청 메서드입니다.'}), 405


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """미처리 예외를 표준 응답으로 변환. 내부 메시지는 로그로만 남긴다."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    logger.exception(f"처리되지 않은 예외: {e}")
    try:
        db.session.rollback()
    except Exception:
        pass
    return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500


@app.route('/api/admin/fcm/send', methods=['POST'])
def admin_send_fcm():
    """관리자용 FCM 알림 전송"""
    from fcm_integration.fcm_utils import fcm_service
    from models import User
    from auth_utils import admin_required
    
    @admin_required
    def _admin_send_fcm(current_user):
        data = request.get_json(silent=True, force=True) or {}
        
        # 필수 필드 검증
        required_fields = ['title', 'body']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400
        
        try:
            title = data.get('title')
            body = data.get('body')
            notification_data = data.get('data', {})
            
            # 전송 방식 선택
            if data.get('topic'):
                # 주제로 전송
                success = fcm_service.send_to_topic(
                    topic=data['topic'],
                    title=title,
                    body=body,
                    data=notification_data
                )
                return jsonify({
                    'message': f"주제 '{data['topic']}'로 알림이 전송되었습니다.",
                    'success': success
                })
            
            elif data.get('user_ids'):
                # 특정 사용자들에게 전송
                users = User.query.filter(
                    User.id.in_(data['user_ids']),
                    User.fcm_token.isnot(None),
                    User.fcm_enabled == True
                ).all()
                
                if not users:
                    return jsonify({'error': '알림을 받을 수 있는 사용자가 없습니다.'}), 400
                
                tokens = [user.fcm_token for user in users]
                result = fcm_service.send_multicast(tokens, title, body, notification_data)
                
                return jsonify({
                    'message': f'{len(users)}명의 사용자에게 알림이 전송되었습니다.',
                    'result': result
                })
            
            else:
                # 모든 FCM 활성화 사용자에게 전송
                users = User.query.filter(
                    User.fcm_token.isnot(None),
                    User.fcm_enabled == True,
                    User.is_active == True
                ).all()
                
                if not users:
                    return jsonify({'error': '알림을 받을 수 있는 사용자가 없습니다.'}), 400
                
                tokens = [user.fcm_token for user in users]
                result = fcm_service.send_multicast(tokens, title, body, notification_data)
                
                return jsonify({
                    'message': f'전체 {len(users)}명의 사용자에게 알림이 전송되었습니다.',
                    'result': result
                })
                
        except Exception as e:
            return jsonify({'error': '알림 전송에 실패했습니다'}), 500
    
    return _admin_send_fcm()

# 기존 사용자 생성 API는 관리자용으로 변경
@app.route('/api/admin/users', methods=['POST'])
def create_user_admin():
    """관리자용 사용자 생성"""
    from models import User
    from auth_utils import admin_required
    
    @admin_required
    def _create_user_admin(current_user):
        data = request.get_json(silent=True, force=True) or {}
        
        # 필수 필드 검증
        required_fields = ['name', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400
        
        # 이메일 중복 확인
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': '이미 사용 중인 이메일입니다.'}), 400
        
        try:
            user = User(
                name=data.get('name'),
                email=data.get('email'),
                phone=data.get('phone'),
                location=data.get('location'),
                role=data.get('role', 'user')  # 기본값은 일반 사용자
            )
            
            user.set_password(data.get('password'))
            
            db.session.add(user)
            db.session.commit()
            
            return jsonify({
                'message': '사용자가 생성되었습니다.',
                'user': user.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': '사용자 생성에 실패했습니다'}), 500
    
    return _create_user_admin()

@app.route('/api/markets', methods=['GET', 'POST'])
def handle_markets():
    from models import Market
    if request.method == 'GET':
        # 쿼리 파라미터
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        is_active = request.args.get('is_active', type=str)

        # 기본 쿼리
        query = Market.query

        # 필터 적용
        if is_active is not None:
            query = query.filter_by(is_active=(is_active.lower() == 'true'))

        # 페이지네이션
        pagination = query.order_by(Market.name).paginate(
            page=page,
            per_page=per_page,
            error_out=False
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
                'has_prev': pagination.has_prev
            }
        })

    elif request.method == 'POST':
        from auth_utils import admin_required

        @admin_required
        def _create_market(current_user):
            data = request.get_json(silent=True, force=True) or {}
            market = Market(
                name=data.get('name'),
                location=data.get('location'),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                category=data.get('category')
            )
            db.session.add(market)
            db.session.commit()
            return jsonify(market.to_dict()), 201

        return _create_market()

@app.route('/api/markets/search', methods=['GET'])
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
            'markets': [market.to_dict() for market in markets]
        })
    except Exception as e:
        return jsonify({'error': '검색 중 오류가 발생했습니다'}), 500

@app.route('/api/markets/<int:market_id>', methods=['GET'])
def get_market_detail(market_id):
    """특정 시장 상세 정보 조회"""
    from models import Market

    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

        return jsonify({
            'status': 'success',
            'data': market.to_dict()
        })
    except Exception as e:
        return jsonify({'error': '시장 조회에 실패했습니다'}), 500

@app.route('/api/markets/<int:market_id>/alert-conditions', methods=['GET'])
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
            'alert_conditions': alert_conditions
        })
    except Exception as e:
        logger.error(f"알림 조건 조회 실패: {e}")
        return jsonify({'error': '알림 조건 조회에 실패했습니다'}), 500

@app.route('/api/admin/markets/<int:market_id>/alert-conditions', methods=['PUT'])
def update_market_alert_conditions(market_id):
    """관리자용: 특정 시장의 알림 조건 설정/수정"""
    from models import Market
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

            # 허용된 필드만 업데이트
            allowed_fields = {
                'enabled', 'rain_probability', 'high_temp', 'low_temp',
                'wind_speed', 'snow_enabled', 'rain_enabled',
                'temp_enabled', 'wind_enabled'
            }

            # 업데이트할 조건 추출
            update_conditions = {}
            for field in allowed_fields:
                if field in data:
                    update_conditions[field] = data[field]

            if not update_conditions:
                return jsonify({'error': '업데이트할 알림 조건이 없습니다.'}), 400

            # 조건 업데이트
            market.update_alert_conditions(update_conditions)
            db.session.commit()

            logger.info(f"관리자 {current_user.email}가 시장 {market.name}의 알림 조건을 수정했습니다: {update_conditions}")

            return jsonify({
                'status': 'success',
                'message': '알림 조건이 업데이트되었습니다.',
                'market_id': market_id,
                'market_name': market.name,
                'alert_conditions': market.alert_conditions
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"알림 조건 업데이트 실패: {e}")
            return jsonify({'error': '알림 조건 업데이트에 실패했습니다'}), 500

    return _update_alert_conditions()

@app.route('/api/admin/markets/alert-conditions/bulk-update', methods=['POST'])
def bulk_update_alert_conditions():
    """관리자용: 여러 시장의 알림 조건 일괄 업데이트"""
    from models import Market
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
            # 허용된 필드만 업데이트
            allowed_fields = {
                'enabled', 'rain_probability', 'high_temp', 'low_temp',
                'wind_speed', 'snow_enabled', 'rain_enabled',
                'temp_enabled', 'wind_enabled'
            }

            update_conditions = {}
            for field in allowed_fields:
                if field in conditions:
                    update_conditions[field] = conditions[field]

            if not update_conditions:
                return jsonify({'error': '업데이트할 유효한 조건이 없습니다.'}), 400

            # 시장들 조회
            markets = Market.query.filter(Market.id.in_(market_ids)).all()

            if not markets:
                return jsonify({'error': '유효한 시장을 찾을 수 없습니다.'}), 404

            # 각 시장의 알림 조건 업데이트
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
                'conditions': update_conditions
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"일괄 알림 조건 업데이트 실패: {e}")
            return jsonify({'error': '일괄 업데이트에 실패했습니다'}), 500

    return _bulk_update_alert_conditions()

@app.route('/api/damage-status', methods=['GET', 'POST'])
def handle_damage_status():
    from models import DamageStatus
    if request.method == 'GET':
        damage_statuses = DamageStatus.query.all()
        return jsonify([status.to_dict() for status in damage_statuses])
    
    elif request.method == 'POST':
        from auth_utils import login_required

        @login_required
        def _create_damage_status(current_user):
            data = request.get_json(silent=True, force=True) or {}
            damage_status = DamageStatus(
                market_id=data.get('market_id'),
                weather_event=data.get('weather_event'),
                damage_level=data.get('damage_level'),
                description=data.get('description'),
                estimated_recovery_time=data.get('estimated_recovery_time')
            )
            db.session.add(damage_status)
            db.session.commit()
            return jsonify(damage_status.to_dict()), 201

        return _create_damage_status()

@app.route('/api/weather/current', methods=['POST'])
def get_current_weather():
    """현재 날씨 정보 조회 (시장의 최신 데이터 가져오기)"""
    from auth_utils import login_required
    from models import Weather, Market

    @login_required
    def _get_current_weather(current_user):
        data = request.get_json(silent=True, force=True) or {}

        # 필수 파라미터 검증
        if 'nx' not in data or 'ny' not in data:
            logger.warning(f"현재 날씨 조회 실패: 필수 파라미터 누락 (data={data})")
            return jsonify({'error': '격자좌표 nx와 ny가 필요합니다.'}), 400

        try:
            nx = int(data['nx'])
            ny = int(data['ny'])

            # 해당 격자좌표를 가진 시장 찾기
            market = Market.query.filter_by(nx=nx, ny=ny, is_active=True).first()

            if market:
                # 시장이 있으면 해당 시장의 최신 날씨 데이터 조회
                weather = Weather.query.filter_by(
                    nx=nx,
                    ny=ny,
                    api_type='current'
                ).order_by(Weather.created_at.desc()).first()

                if weather:
                    result = {
                        'status': 'success',
                        'message': f'{market.name}의 최신 날씨 데이터를 가져왔습니다.',
                        'data': weather.to_dict(),
                        'location_name': market.name,
                        'nx': market.nx,
                        'ny': market.ny
                    }
                    return jsonify(result)
                else:
                    logger.warning(f"현재 날씨 조회 실패: {market.name}의 날씨 데이터 없음")
                    return jsonify({
                        'status': 'error',
                        'message': f'{market.name}의 날씨 데이터가 없습니다. 스케줄러가 아직 데이터를 수집하지 않았습니다.'
                    }), 404
            else:
                # 시장이 없으면 격자좌표로만 조회
                logger.warning(f"시장 없음: 격자좌표({nx}, {ny})에 해당하는 활성 시장이 없습니다.")
                return jsonify({
                    'status': 'error',
                    'message': f'해당 위치의 시장 정보가 없습니다. (격자좌표: {nx}, {ny})'
                }), 404

        except ValueError:
            return jsonify({'error': 'nx와 ny는 정수여야 합니다.'}), 400
        except Exception as e:
            logger.error(f"현재 날씨 조회 오류: {e}")
            return jsonify({'error': '서버 오류가 발생했습니다'}), 500

    return _get_current_weather()

@app.route('/api/weather/forecast', methods=['POST'])
def get_forecast_weather():
    """날씨 예보 정보 조회 (데이터베이스에서 최신 데이터 가져오기)"""
    from auth_utils import login_required
    from models import Weather

    @login_required
    def _get_forecast_weather(current_user):
        data = request.get_json(silent=True, force=True) or {}

        # 필수 파라미터 검증
        if 'nx' not in data or 'ny' not in data:
            return jsonify({'error': '격자좌표 nx와 ny가 필요합니다.'}), 400

        try:
            nx = int(data['nx'])
            ny = int(data['ny'])

            # 데이터베이스에서 해당 격자 좌표의 최신 예보 데이터 조회
            # 예보는 여러 시간대의 데이터가 있으므로 최신 base_date/base_time 기준으로 모두 가져옴
            forecasts = Weather.query.filter_by(
                nx=nx,
                ny=ny,
                api_type='forecast'
            ).order_by(
                Weather.base_date.desc(),
                Weather.base_time.desc(),
                Weather.fcst_date.asc(),
                Weather.fcst_time.asc()
            ).limit(100).all()

            if not forecasts:
                return jsonify({
                    'status': 'error',
                    'message': f'해당 위치({nx}, {ny})의 예보 데이터가 없습니다. 스케줄러가 아직 데이터를 수집하지 않았거나 해당 지역이 활성 시장 목록에 없습니다.'
                }), 404

            # 가장 최신 base_date/base_time을 가진 예보들만 필터링
            latest_base_date = forecasts[0].base_date
            latest_base_time = forecasts[0].base_time

            latest_forecasts = [
                f for f in forecasts
                if f.base_date == latest_base_date and f.base_time == latest_base_time
            ]

            # 성공 응답 구성
            result = {
                'status': 'success',
                'message': '데이터베이스에서 최신 예보 데이터를 가져왔습니다.',
                'data': [weather.to_dict() for weather in latest_forecasts],
                'location_name': forecasts[0].location_name if forecasts else '',
                'nx': nx,
                'ny': ny,
                'base_date': latest_base_date,
                'base_time': latest_base_time
            }

            return jsonify(result)

        except ValueError:
            return jsonify({'error': 'nx와 ny는 정수여야 합니다.'}), 400
        except Exception as e:
            logger.error(f"예보 날씨 조회 오류: {e}")
            return jsonify({'error': '서버 오류가 발생했습니다'}), 500

    return _get_forecast_weather()

@app.route('/api/weather', methods=['GET'])
def get_weather_history():
    """저장된 날씨 데이터 조회"""
    from models import Weather
    
    # 쿼리 파라미터
    location_name = request.args.get('location_name')
    api_type = request.args.get('api_type')  # 'current' 또는 'forecast'
    limit = request.args.get('limit', 100, type=int)
    
    try:
        query = Weather.query
        
        if location_name:
            query = query.filter(Weather.location_name.contains(location_name))
        
        if api_type:
            query = query.filter(Weather.api_type == api_type)
        
        weather_data = query.order_by(Weather.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'status': 'success',
            'count': len(weather_data),
            'data': [weather.to_dict() for weather in weather_data]
        })
        
    except Exception as e:
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

@app.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """날씨 스케줄러 시작"""
    from auth_utils import admin_required

    @admin_required
    def _start_scheduler(current_user):
        try:
            from weather_scheduler import start_weather_scheduler
            start_weather_scheduler()
            return jsonify({'status': 'success', 'message': '날씨 스케줄러가 시작되었습니다.'})
        except Exception as e:
            return jsonify({'error': '스케줄러 시작에 실패했습니다'}), 500

    return _start_scheduler()

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """날씨 스케줄러 정지"""
    from auth_utils import admin_required

    @admin_required
    def _stop_scheduler(current_user):
        try:
            from weather_scheduler import stop_weather_scheduler
            stop_weather_scheduler()
            return jsonify({'status': 'success', 'message': '날씨 스케줄러가 정지되었습니다.'})
        except Exception as e:
            return jsonify({'error': '스케줄러 정지에 실패했습니다'}), 500

    return _stop_scheduler()

@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """스케줄러 상태 조회"""
    from auth_utils import login_required

    @login_required
    def _get_scheduler_status(current_user):
        try:
            from weather_scheduler import get_scheduler_status
            status = get_scheduler_status()
            return jsonify(status)
        except Exception as e:
            return jsonify({'error': '상태 조회에 실패했습니다'}), 500

    return _get_scheduler_status()

@app.route('/api/scheduler/stats', methods=['GET'])
def get_weather_statistics():
    """날씨 데이터 통계 조회"""
    from auth_utils import login_required

    @login_required
    def _get_weather_statistics(current_user):
        try:
            from weather_scheduler import get_weather_stats
            stats = get_weather_stats()
            return jsonify(stats)
        except Exception as e:
            return jsonify({'error': '통계 조회에 실패했습니다'}), 500

    return _get_weather_statistics()

@app.route('/api/scheduler/collect', methods=['POST'])
def manual_weather_collection():
    """수동 날씨 데이터 수집"""
    from auth_utils import admin_required

    @admin_required
    def _manual_weather_collection(current_user):
        try:
            from weather_scheduler import weather_scheduler
            weather_scheduler.collect_market_weather_data()
            return jsonify({'status': 'success', 'message': '날씨 데이터 수집이 완료되었습니다.'})
        except Exception as e:
            return jsonify({'error': '수동 수집에 실패했습니다'}), 500

    return _manual_weather_collection()

@app.route('/api/admin/rain-alerts/check', methods=['POST'])
def manual_rain_alert_check():
    """관리자용 수동 비 예보 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_rain_alerts
    
    @admin_required
    def _manual_rain_alert_check(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}
            hours = data.get('hours', 24)
            
            result = check_and_send_rain_alerts(hours)
            
            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': f'비 예보 알림 확인 완료',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '비 예보 알림 확인 실패',
                    'error': result.get('error')
                }), 500
                
        except Exception as e:
            return jsonify({'error': '비 예보 알림 확인에 실패했습니다'}), 500
    
    return _manual_rain_alert_check()

@app.route('/api/markets/<int:market_id>/rain-forecast', methods=['GET'])
def get_market_rain_forecast(market_id):
    """특정 시장의 비 예보 확인"""
    from weather_alerts import check_market_rain_forecast
    
    try:
        hours = request.args.get('hours', 24, type=int)
        result = check_market_rain_forecast(market_id, hours)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify({
            'status': 'success',
            'market_id': market_id,
            'forecast': result
        })
        
    except Exception as e:
        return jsonify({'error': '비 예보 확인에 실패했습니다'}), 500

@app.route('/api/markets/<int:market_id>/weather-conditions', methods=['GET'])
def get_market_weather_conditions(market_id):
    """특정 시장의 모든 날씨 조건 확인 (비, 폭염, 한파, 강풍 등)"""
    from weather_alerts import check_market_all_conditions

    try:
        hours = request.args.get('hours', 24, type=int)
        result = check_market_all_conditions(market_id, hours)

        if 'error' in result:
            return jsonify(result), 404

        return jsonify({
            'status': 'success',
            'market_id': market_id,
            'conditions': result
        })

    except Exception as e:
        return jsonify({'error': '날씨 조건 확인에 실패했습니다'}), 500

@app.route('/api/admin/weather-alerts/check', methods=['POST'])
def manual_weather_alert_check():
    """관리자용 수동 모든 날씨 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_all_weather_alerts

    @admin_required
    def _manual_weather_alert_check(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}
            hours = data.get('hours', 24)

            result = check_and_send_all_weather_alerts(hours)

            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': f'날씨 알림 확인 완료',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '날씨 알림 확인 실패',
                    'error': result.get('error')
                }), 500

        except Exception as e:
            return jsonify({'error': '날씨 알림 확인에 실패했습니다'}), 500

    return _manual_weather_alert_check()

@app.route('/api/admin/weather-alerts/test-to-user', methods=['POST'])
def test_weather_alert_to_user():
    """관리자용 테스트: 특정 사용자에게 날씨 알림 전송"""
    from auth_utils import admin_required
    from fcm_integration.fcm_utils import fcm_service
    from models import User, Market
    import json

    @admin_required
    def _test_weather_alert_to_user(current_user):
        try:
            data = request.get_json(silent=True, force=True) or {}

            # 필수 파라미터 확인
            if not data:
                return jsonify({'error': '요청 데이터가 없습니다.'}), 400

            user_id = data.get('user_id')
            market_id = data.get('market_id')
            alert_type = data.get('alert_type', 'rain')  # rain, heat, cold, wind, snow

            if not user_id:
                return jsonify({'error': 'user_id는 필수 입력사항입니다.'}), 400

            if not market_id:
                return jsonify({'error': 'market_id는 필수 입력사항입니다.'}), 400

            # 사용자 조회
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': f'사용자 ID {user_id}를 찾을 수 없습니다.'}), 404

            # 시장 조회
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': f'시장 ID {market_id}를 찾을 수 없습니다.'}), 404

            # FCM 토큰 확인
            if not user.can_receive_fcm():
                return jsonify({
                    'error': f'사용자 {user.name}({user.email})은 FCM 알림을 받을 수 없는 상태입니다.',
                    'reason': {
                        'is_active': user.is_active,
                        'fcm_enabled': user.fcm_enabled,
                        'has_fcm_token': user.fcm_token is not None
                    }
                }), 400

            # 방해금지 시간 체크 (테스트는 무시할 수 있음)
            is_dnd = user.is_in_do_not_disturb_time()
            ignore_dnd = data.get('ignore_dnd', False)

            if is_dnd and not ignore_dnd:
                return jsonify({
                    'error': f'사용자 {user.name}({user.email})은 현재 방해금지 시간입니다.',
                    'hint': 'ignore_dnd: true를 설정하면 방해금지 시간을 무시하고 전송할 수 있습니다.'
                }), 400

            # 알림 타입별 메시지 생성
            if alert_type == 'rain':
                title = f"[{market.name} 강우예보 - 테스트]"
                body = f"""11월 13일 15시경부터 {market.name} 인근지역 비 또는 눈 70% 이상 예상됩니다.

[조치1] 시장 입구 및 주요 통로의 배수구 덮개를 열어 배수로 확보 바랍니다.

[조치2] 저지대 점포 및 창고 내 전기제품을 고지대로 이동시켜 주세요.

[조치3] 침수 대비를 위해 배수펌프 및 비닐커버를 사전에 점검 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)
** 이것은 테스트 알림입니다"""

            elif alert_type == 'heat':
                title = f"[{market.name} 폭염예보 - 테스트]"
                body = f"""11월 13일 14시경 최고기온 35°C 이상 폭염이 예상됩니다.

[조치1] 냉장·냉동식품의 보관온도를 점검하고, 변질우려 제품은 폐기 바랍니다.

[조치2] 상인 및 고객을 위한 냉방기 가동과 충분한 환기를 유지 바랍니다.

[조치3] 노약자 근무자는 충분한 휴식을 취하고, 음료수를 비치해 주세요.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)
** 이것은 테스트 알림입니다"""

            elif alert_type == 'cold':
                title = f"[{market.name} 한파예보 - 테스트]"
                body = f"""11월 13일 06시경 기온이 -15°C 이하로 떨어질 것으로 예상됩니다.

[조치1] 수도관과 보일러 배관의 동파 방지를 위해 보온 덮개를 설치 바랍니다.

[조치2] 난방기 과열 및 전열기 주변 인화물 정리를 철저히 해주세요.

[조치3] 점포 내 결빙구간(출입구, 배수로 등)을 미리 점검하고 제빙제를 비치 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)
** 이것은 테스트 알림입니다"""

            elif alert_type == 'wind':
                title = f"[{market.name} 강풍예보 - 테스트]"
                body = f"""11월 13일 14시경부터 {market.name} 풍속 20m/s 이상 강풍이 예상됩니다.

[조치1] 가스밸브·전열기 주변 인화성 물질(박스, 천 등)을 제거 바랍니다.

[조치2] 상인회 주관으로 순찰을 강화하고, 화재대피안내 및 방송 바랍니다.

[조치3] 비상소화장치(소화기·소화전) 위치를 확인하고 사용법을 숙지하세요.

[조치4] 출입구 주변 적재물을 정리하여 긴급대피 통로를 확보 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)
** 이것은 테스트 알림입니다"""

            elif alert_type == 'snow':
                title = f"[{market.name} 폭설예보 - 테스트]"
                body = f"""11월 13일 15시경부터 {market.name}에 적설량 10cm 이상 폭설이 예상됩니다.

[조치1] 인근 가설천막 및 차양에 눈이 쌓이지 않도록 수시 점검 바랍니다.

[조치2] 지붕 위 적설은 붕괴 위험이 있으므로 제설장비를 이용해 즉시 제거 바랍니다.

[조치3] 통로 및 계단에는 미끄럼방지제(모래, 염화칼슘 등)를 살포해 주시기 바랍니다.

* 긴급연락: ☎119 또는 공단 지역본부 (기상정보 출처: 기상청 특보시스템)
** 이것은 테스트 알림입니다"""

            else:
                return jsonify({
                    'error': f'알 수 없는 알림 타입: {alert_type}',
                    'available_types': ['rain', 'heat', 'cold', 'wind', 'snow']
                }), 400

            # 커스텀 메시지가 제공된 경우 사용
            if data.get('custom_title'):
                title = data.get('custom_title')
            if data.get('custom_body'):
                body = data.get('custom_body')

            # FCM 데이터 생성 (모든 값은 문자열이어야 함)
            notification_data = {
                'type': f'{alert_type}_alert_test',
                'market_id': str(market.id),
                'market_name': market.name,
                'is_test': 'true',
                'sent_by': current_user.email
            }

            # FCM 알림 전송
            success = fcm_service.send_notification(
                token=user.fcm_token,
                title=title,
                body=body,
                data=notification_data
            )

            logger.info(f"관리자 {current_user.email}가 사용자 {user.email}에게 {alert_type} 테스트 알림 전송")

            if success:
                return jsonify({
                    'status': 'success',
                    'message': f'사용자 {user.name}({user.email})에게 {alert_type} 알림이 전송되었습니다.',
                    'data': {
                        'user_id': user.id,
                        'user_name': user.name,
                        'user_email': user.email,
                        'market_id': market.id,
                        'market_name': market.name,
                        'alert_type': alert_type,
                        'title': title,
                        'is_dnd_ignored': is_dnd and ignore_dnd,
                        'fcm_result': {'success': success}
                    }
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'FCM 알림 전송 실패',
                    'error': 'FCM notification failed'
                }), 500

        except Exception as e:
            logger.error(f"테스트 알림 전송 실패: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': '테스트 알림 전송에 실패했습니다'}), 500

    return _test_weather_alert_to_user()


@app.route('/api/admin/weather-alerts/test-summary', methods=['POST'])
def test_weather_summary_alert():
    """관리자용 테스트: 모든 관심 시장의 날씨 요약 알림 전송"""
    from auth_utils import admin_required
    from weather_alerts import send_test_weather_summary_to_all_users

    @admin_required
    def _test_weather_summary_alert(current_user):
        try:
            logger.info(f"관리자 {current_user.email}가 날씨 요약 테스트 알림을 요청했습니다.")

            result = send_test_weather_summary_to_all_users()

            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'message': '날씨 요약 알림 전송 완료',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '날씨 요약 알림 전송 실패',
                    'error': result.get('error')
                }), 500

        except Exception as e:
            logger.error(f"날씨 요약 알림 테스트 실패: {e}")
            return jsonify({'error': '날씨 요약 알림 테스트에 실패했습니다'}), 500

    return _test_weather_summary_alert()

# 알림 이력 관련 API
def init_scheduler():
    """스케줄러 초기화 및 시작"""
    try:
        from weather_scheduler import weather_scheduler

        # 이미 실행 중인지 확인
        if weather_scheduler.scheduler.running:
            logger.info("Weather scheduler is already running")
            return

        logger.info("Starting weather scheduler...")
        from weather_scheduler import start_weather_scheduler
        start_weather_scheduler()
        logger.info("Weather scheduler started successfully!")
    except Exception as e:
        logger.error(f"Failed to start weather scheduler: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

# 스케줄러 자동 시작 플래그
_scheduler_initialized = False

def ensure_scheduler_running():
    """스케줄러가 실행되도록 보장"""
    global _scheduler_initialized
    if not _scheduler_initialized:
        with app.app_context():
            init_scheduler()
        _scheduler_initialized = True

# Flask 앱 시작 시 스케줄러 자동 시작
# 개발 환경에서 reloader를 사용할 때 중복 실행 방지
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.environ.get('WERKZEUG_RUN_MAIN') is None:
    ensure_scheduler_running()

if __name__ == '__main__':
    with app.app_context():
        # Import models here to ensure they are registered with SQLAlchemy
        from models import User, Market, DamageStatus, Weather
        db.create_all()

    # 환경변수에서 포트 설정 (기본값: 80)
    port = int(os.environ.get('PORT', 80))
    # 환경변수에서 호스트 설정 (기본값: 0.0.0.0)
    host = os.environ.get('HOST', '0.0.0.0')
    # 환경변수에서 디버그 모드 설정 (기본값: FLASK_ENV이 development이면 True)
    debug = os.environ.get('FLASK_ENV') == 'development'

    logger.info(f"Starting Flask app on {host}:{port} (debug={debug})")
    app.run(debug=debug, host=host, port=port)