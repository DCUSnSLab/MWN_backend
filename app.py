from flask import Flask, request, jsonify
from flask_migrate import Migrate
from datetime import datetime
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

# Database configuration
# PostgreSQL connection string
default_db_url = 'postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', default_db_url)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

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

# Models will be imported later to avoid circular import

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/api/users', methods=['GET'])
def get_users():
    """사용자 목록 조회 (관리자용)"""
    from models import User
    from auth_utils import admin_required
    
    @admin_required
    def _get_users(current_user):
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    
    return _get_users()

@app.route('/api/auth/register', methods=['POST'])
def register():
    """회원가입"""
    from models import User
    from auth_utils import validate_email, validate_password, generate_tokens
    
    data = request.get_json()
    
    # 필수 필드 검증
    required_fields = ['name', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field}는 필수 입력사항입니다.'}), 400
    
    name = data.get('name').strip()
    email = data.get('email').strip().lower()
    password = data.get('password')
    phone = (data.get('phone') or '').strip()
    location = (data.get('location') or '').strip()
    
    # 이메일 형식 검증
    if not validate_email(email):
        return jsonify({'error': '올바른 이메일 형식이 아닙니다.'}), 400
    
    # 패스워드 강도 검증
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # 이메일 중복 확인
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '이미 사용 중인 이메일입니다.'}), 400
    
    try:
        # 새 사용자 생성 (일반 사용자로 설정)
        user = User(
            name=name,
            email=email,
            phone=phone,
            location=location,
            role='user'  # 회원가입은 항상 일반 사용자로
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # JWT 토큰 생성
        tokens = generate_tokens(user.id)
        
        return jsonify({
            'message': '회원가입이 완료되었습니다.',
            'user': user.to_dict(),
            'tokens': tokens
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'회원가입 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """로그인"""
    from models import User
    from auth_utils import generate_tokens
    
    data = request.get_json()
    
    # 필수 필드 검증
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': '이메일과 패스워드를 입력해주세요.'}), 400
    
    email = data.get('email').strip().lower()
    password = data.get('password')
    
    # 사용자 조회
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': '이메일 또는 패스워드가 올바르지 않습니다.'}), 401
    
    if not user.is_active:
        return jsonify({'error': '비활성화된 계정입니다.'}), 401
    
    try:
        # 마지막 로그인 시간 업데이트
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # JWT 토큰 생성
        tokens = generate_tokens(user.id)
        
        return jsonify({
            'message': '로그인에 성공했습니다.',
            'user': user.to_dict(),
            'tokens': tokens
        })
        
    except Exception as e:
        return jsonify({'error': f'로그인 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """토큰 갱신"""
    from models import User
    from auth_utils import verify_token, generate_tokens
    
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': '리프레시 토큰이 필요합니다.'}), 400
    
    # 리프레시 토큰 검증
    payload = verify_token(refresh_token, token_type='refresh')
    if not payload:
        return jsonify({'error': '유효하지 않은 리프레시 토큰입니다.'}), 401
    
    # 사용자 확인
    user = User.query.get(payload['user_id'])
    if not user or not user.is_active:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 401
    
    # 새 토큰 생성
    tokens = generate_tokens(user.id)
    
    return jsonify({
        'message': '토큰이 갱신되었습니다.',
        'tokens': tokens
    })

@app.route('/api/auth/me', methods=['GET'])
def get_profile():
    """현재 사용자 프로필 조회"""
    from auth_utils import login_required
    
    @login_required
    def _get_profile(current_user):
        return jsonify({
            'user': current_user.to_dict()
        })
    
    return _get_profile()

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """로그아웃 (클라이언트에서 토큰 삭제)"""
    return jsonify({'message': '로그아웃되었습니다.'})

@app.route('/api/auth/delete', methods=['POST'])
def delete_account():
    """회원 탈퇴"""
    from auth_utils import login_required
    from models import User

    @login_required
    def _delete_account(current_user):
        data = request.get_json(silent=True) or {}
        deletion_reason = data.get('reason', 'No reason provided.')

        try:
            # 사용자 비활성화 및 탈퇴 처리
            current_user.is_active = False
            current_user.is_deleted = True
            current_user.deleted_at = datetime.utcnow()
            current_user.deletion_reason = deletion_reason

            # 민감 정보 및 기능적 데이터 초기화
            current_user.password_hash = 'deleted'  # nullable=False 이므로 None 대신 비활성 상태 표시
            current_user.fcm_token = None
            current_user.fcm_enabled = False
            
            db.session.commit()
            
            logger.info(f"User {current_user.email} (ID: {current_user.id}) has been deleted.")

            return jsonify({
                'status': 'success',
                'message': '회원 탈퇴 처리가 완료되었습니다. 이용해주셔서 감사합니다.'
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during account deletion for user {current_user.email}: {e}")
            return jsonify({'error': f'회원 탈퇴 중 오류가 발생했습니다: {str(e)}'}), 500

    return _delete_account()

# FCM 관련 API 엔드포인트들
@app.route('/api/fcm/register', methods=['POST'])
def register_fcm_token():
    """FCM 토큰 등록/업데이트"""
    from auth_utils import login_required
    from models import User
    
    @login_required
    def _register_fcm_token(current_user):
        data = request.get_json()
        
        # 필수 필드 검증
        if not data.get('token'):
            return jsonify({'error': 'FCM 토큰이 필요합니다.'}), 400
        
        try:
            fcm_token = data.get('token')
            device_info = data.get('device_info', {})
            
            # 토큰 업데이트
            current_user.update_fcm_token(fcm_token, device_info)
            db.session.commit()
            
            # 기본 주제 구독 (선택사항)
            topics = data.get('subscribe_topics', ['weather_alerts'])
            for topic in topics:
                current_user.subscribe_to_topic(topic)
            
            db.session.commit()
            
            return jsonify({
                'message': 'FCM 토큰이 등록되었습니다.',
                'fcm_enabled': current_user.fcm_enabled,
                'subscribed_topics': current_user.fcm_topics
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'FCM 토큰 등록 실패: {str(e)}'}), 500
    
    return _register_fcm_token()

@app.route('/api/fcm/settings', methods=['GET', 'POST'])
def fcm_settings():
    """FCM 설정 조회/업데이트"""
    from auth_utils import login_required

    @login_required
    def _fcm_settings(current_user):
        if request.method == 'GET':
            # FCM 설정 조회
            return jsonify({
                'fcm_enabled': current_user.fcm_enabled,
                'fcm_topics': current_user.fcm_topics or [],
                'device_info': current_user.device_info,
                'has_token': current_user.fcm_token is not None
            })

        elif request.method == 'POST':
            # FCM 설정 업데이트
            data = request.get_json()

            try:
                # FCM 활성화/비활성화
                if 'enabled' in data:
                    if data['enabled']:
                        current_user.enable_fcm()
                    else:
                        current_user.disable_fcm()

                # 주제 구독 관리
                if 'subscribe_topics' in data:
                    for topic in data['subscribe_topics']:
                        current_user.subscribe_to_topic(topic)

                if 'unsubscribe_topics' in data:
                    for topic in data['unsubscribe_topics']:
                        current_user.unsubscribe_from_topic(topic)

                db.session.commit()

                return jsonify({
                    'message': 'FCM 설정이 업데이트되었습니다.',
                    'fcm_enabled': current_user.fcm_enabled,
                    'fcm_topics': current_user.fcm_topics or []
                })

            except Exception as e:
                db.session.rollback()
                return jsonify({'error': f'FCM 설정 업데이트 실패: {str(e)}'}), 500

    return _fcm_settings()

@app.route('/api/user/do-not-disturb', methods=['GET'])
def get_do_not_disturb():
    """사용자의 방해금지 시간 설정 조회"""
    from auth_utils import login_required

    @login_required
    def _get_do_not_disturb(current_user):
        try:
            dnd_settings = current_user.do_not_disturb or {
                'enabled': False,
                'start_time': '22:00',
                'end_time': '08:00',
                'all_day': False,
                'days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            }

            return jsonify({
                'status': 'success',
                'do_not_disturb': dnd_settings
            })

        except Exception as e:
            logger.error(f"방해금지 설정 조회 실패: {e}")
            return jsonify({'error': f'방해금지 설정 조회 실패: {str(e)}'}), 500

    return _get_do_not_disturb()

@app.route('/api/user/do-not-disturb', methods=['PUT'])
def update_do_not_disturb():
    """사용자의 방해금지 시간 설정 업데이트"""
    from auth_utils import login_required

    @login_required
    def _update_do_not_disturb(current_user):
        data = request.get_json()

        if not data:
            return jsonify({'error': '방해금지 설정 데이터가 필요합니다.'}), 400

        try:
            # 허용된 필드만 업데이트
            allowed_fields = {'enabled', 'start_time', 'end_time', 'all_day', 'days'}
            update_data = {}

            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]

            if not update_data:
                return jsonify({'error': '업데이트할 설정이 없습니다.'}), 400

            # 시간 형식 검증
            if 'start_time' in update_data:
                try:
                    hour, minute = map(int, update_data['start_time'].split(':'))
                    if not (0 <= hour < 24 and 0 <= minute < 60):
                        return jsonify({'error': 'start_time 형식이 올바르지 않습니다. (HH:MM)'}), 400
                except (ValueError, AttributeError):
                    return jsonify({'error': 'start_time 형식이 올바르지 않습니다. (HH:MM)'}), 400

            if 'end_time' in update_data:
                try:
                    hour, minute = map(int, update_data['end_time'].split(':'))
                    if not (0 <= hour < 24 and 0 <= minute < 60):
                        return jsonify({'error': 'end_time 형식이 올바르지 않습니다. (HH:MM)'}), 400
                except (ValueError, AttributeError):
                    return jsonify({'error': 'end_time 형식이 올바르지 않습니다. (HH:MM)'}), 400

            # 요일 검증
            if 'days' in update_data:
                valid_days = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
                if not isinstance(update_data['days'], list):
                    return jsonify({'error': 'days는 배열이어야 합니다.'}), 400
                if not all(day in valid_days for day in update_data['days']):
                    return jsonify({'error': f'유효한 요일: {", ".join(valid_days)}'}), 400

            # 방해금지 설정 업데이트
            current_user.update_do_not_disturb(update_data)
            db.session.commit()

            logger.info(f"사용자 {current_user.email}의 방해금지 설정이 업데이트되었습니다: {update_data}")

            return jsonify({
                'status': 'success',
                'message': '방해금지 설정이 업데이트되었습니다.',
                'do_not_disturb': current_user.do_not_disturb
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"방해금지 설정 업데이트 실패: {e}")
            return jsonify({'error': f'방해금지 설정 업데이트 실패: {str(e)}'}), 500

    return _update_do_not_disturb()

@app.route('/api/fcm/test', methods=['POST'])
def test_fcm_notification():
    """FCM 테스트 알림 전송"""
    from auth_utils import login_required
    from fcm_integration.fcm_utils import fcm_service
    
    @login_required
    def _test_fcm_notification(current_user):
        if not current_user.can_receive_fcm():
            return jsonify({'error': 'FCM 알림을 받을 수 없는 상태입니다.'}), 400
        
        try:
            # 테스트 알림 전송
            success = fcm_service.send_notification(
                token=current_user.fcm_token,
                title="🧪 테스트 알림",
                body="FCM 설정이 정상적으로 작동합니다!",
                data={
                    "type": "test",
                    "user_id": str(current_user.id)
                }
            )
            
            if success:
                return jsonify({'message': '테스트 알림이 전송되었습니다.'})
            else:
                return jsonify({'error': '테스트 알림 전송에 실패했습니다.'}), 500
                
        except Exception as e:
            return jsonify({'error': f'테스트 알림 전송 실패: {str(e)}'}), 500
    
    return _test_fcm_notification()

@app.route('/api/admin/fcm/send', methods=['POST'])
def admin_send_fcm():
    """관리자용 FCM 알림 전송"""
    from fcm_integration.fcm_utils import fcm_service
    from models import User
    from auth_utils import admin_required
    
    @admin_required
    def _admin_send_fcm(current_user):
        data = request.get_json()
        
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
            return jsonify({'error': f'알림 전송 실패: {str(e)}'}), 500
    
    return _admin_send_fcm()

# 기존 사용자 생성 API는 관리자용으로 변경
@app.route('/api/admin/users', methods=['POST'])
def create_user_admin():
    """관리자용 사용자 생성"""
    from models import User
    from auth_utils import admin_required
    
    @admin_required
    def _create_user_admin(current_user):
        data = request.get_json()
        
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
            return jsonify({'error': f'사용자 생성 실패: {str(e)}'}), 500
    
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
        data = request.get_json()
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
        return jsonify({'error': f'검색 중 오류가 발생했습니다: {str(e)}'}), 500

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
        return jsonify({'error': f'시장 조회 실패: {str(e)}'}), 500

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
        return jsonify({'error': f'알림 조건 조회 실패: {str(e)}'}), 500

@app.route('/api/admin/markets/<int:market_id>/alert-conditions', methods=['PUT'])
def update_market_alert_conditions(market_id):
    """관리자용: 특정 시장의 알림 조건 설정/수정"""
    from models import Market
    from auth_utils import admin_required

    @admin_required
    def _update_alert_conditions(current_user):
        data = request.get_json()

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
            return jsonify({'error': f'알림 조건 업데이트 실패: {str(e)}'}), 500

    return _update_alert_conditions()

@app.route('/api/admin/markets/alert-conditions/bulk-update', methods=['POST'])
def bulk_update_alert_conditions():
    """관리자용: 여러 시장의 알림 조건 일괄 업데이트"""
    from models import Market
    from auth_utils import admin_required

    @admin_required
    def _bulk_update_alert_conditions(current_user):
        data = request.get_json()

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
            return jsonify({'error': f'일괄 업데이트 실패: {str(e)}'}), 500

    return _bulk_update_alert_conditions()

@app.route('/api/watchlist', methods=['GET'])
def get_user_watchlist():
    """사용자의 관심 시장 목록 조회"""
    from models import UserMarketInterest
    from auth_utils import login_required
    
    @login_required
    def _get_user_watchlist(current_user):
        try:
            interests = UserMarketInterest.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).all()
            
            return jsonify({
                'count': len(interests),
                'watchlist': [interest.to_dict() for interest in interests]
            })
        except Exception as e:
            return jsonify({'error': f'관심 목록 조회 실패: {str(e)}'}), 500
    
    return _get_user_watchlist()

@app.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    """시장을 관심 목록에 추가"""
    from models import UserMarketInterest, Market
    from auth_utils import login_required
    
    @login_required
    def _add_to_watchlist(current_user):
        data = request.get_json()
        
        if not data.get('market_id'):
            return jsonify({'error': 'market_id가 필요합니다.'}), 400
        
        market_id = data.get('market_id')
        
        try:
            # 시장 존재 확인
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': '존재하지 않는 시장입니다.'}), 404
            
            if not market.is_active:
                return jsonify({'error': '비활성화된 시장입니다.'}), 400
            
            # 관심 목록에 추가
            interest = UserMarketInterest.add_interest(current_user.id, market_id)
            db.session.add(interest)
            db.session.commit()
            
            return jsonify({
                'message': f'{market.name}이(가) 관심 목록에 추가되었습니다.',
                'interest': interest.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'관심 목록 추가 실패: {str(e)}'}), 500
    
    return _add_to_watchlist()

@app.route('/api/watchlist/<int:market_id>', methods=['DELETE'])
def remove_from_watchlist(market_id):
    """시장을 관심 목록에서 제거"""
    from models import UserMarketInterest
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
                'market_id': market_id
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'관심 목록 제거 실패: {str(e)}'}), 500
    
    return _remove_from_watchlist()

@app.route('/api/watchlist/<int:interest_id>/notification', methods=['PUT'])
def toggle_notification_for_interest(interest_id):
    """특정 관심 시장의 알림 설정 토글"""
    from models import UserMarketInterest
    from auth_utils import login_required
    
    @login_required
    def _toggle_notification(current_user):
        try:
            interest = UserMarketInterest.query.filter_by(
                id=interest_id,
                user_id=current_user.id
            ).first()
            
            if not interest:
                return jsonify({'error': '해당 관심 항목을 찾을 수 없습니다.'}), 404
            
            # 알림 설정 토글
            interest.notification_enabled = not interest.notification_enabled
            db.session.commit()
            
            status = "활성화" if interest.notification_enabled else "비활성화"
            return jsonify({
                'message': f'알림이 {status}되었습니다.',
                'interest': interest.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'알림 설정 변경 실패: {str(e)}'}), 500
    
    return _toggle_notification()

@app.route('/api/damage-status', methods=['GET', 'POST'])
def handle_damage_status():
    from models import DamageStatus
    if request.method == 'GET':
        damage_statuses = DamageStatus.query.all()
        return jsonify([status.to_dict() for status in damage_statuses])
    
    elif request.method == 'POST':
        data = request.get_json()
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

@app.route('/api/weather/current', methods=['POST'])
def get_current_weather():
    """현재 날씨 정보 조회 (시장의 최신 데이터 가져오기)"""
    from weather_api import convert_to_grid
    from models import Weather, Market

    data = request.get_json()

    # 필수 파라미터 검증
    if not data or 'latitude' not in data or 'longitude' not in data:
        logger.warning(f"현재 날씨 조회 실패: 필수 파라미터 누락 (data={data})")
        return jsonify({'error': '위도(latitude)와 경도(longitude)가 필요합니다.'}), 400

    try:
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        location_name = data.get('location_name', '')

        # 위경도를 격자좌표로 변환
        nx, ny = convert_to_grid(lat, lon)

        # 해당 격자좌표를 가진 시장 찾기
        # 이런 미친 코드.. 왜 이런 일이 발생했을까요
        # 앱 쪽에서 시장 이름이 아닌 시장의 위도, 경도를 전달받는데(대체 왜?)
        # 전달받은 위경도를 기상청 API에 호출하기 위한 격자 좌표로 변경해서 호출을 진행합니다
        # 이 과정에서 약간의 오차가 발생해서 아래와 같이 변환 결과에 1을 더해줘야 정상적인 값이 나오는걸 확인했습니다
        market = Market.query.filter_by(nx=nx + 1, ny=ny + 1, is_active=True).first()

        if market:
            # 시장이 있으면 해당 시장의 최신 날씨 데이터 조회
            weather = Weather.query.filter_by(
                nx=market.nx,
                ny=market.ny,
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
        return jsonify({'error': '위도와 경도는 숫자여야 합니다.'}), 400
    except Exception as e:
        logger.error(f"현재 날씨 조회 오류: {e}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/weather/forecast', methods=['POST'])
def get_forecast_weather():
    """날씨 예보 정보 조회 (데이터베이스에서 최신 데이터 가져오기)"""
    from weather_api import convert_to_grid
    from models import Weather

    data = request.get_json()

    # 필수 파라미터 검증
    if 'latitude' not in data or 'longitude' not in data:
        return jsonify({'error': '위도(latitude)와 경도(longitude)가 필요합니다.'}), 400

    try:
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        location_name = data.get('location_name', '')

        # 위경도를 격자좌표로 변환
        nx, ny = convert_to_grid(lat, lon)

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
            'location_name': location_name or (forecasts[0].location_name if forecasts else ''),
            'nx': nx,
            'ny': ny,
            'base_date': latest_base_date,
            'base_time': latest_base_time
        }

        return jsonify(result)

    except ValueError:
        return jsonify({'error': '위도와 경도는 숫자여야 합니다.'}), 400
    except Exception as e:
        logger.error(f"예보 날씨 조회 오류: {e}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

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
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """날씨 스케줄러 시작"""
    try:
        from weather_scheduler import start_weather_scheduler
        start_weather_scheduler()
        return jsonify({'status': 'success', 'message': '날씨 스케줄러가 시작되었습니다.'})
    except Exception as e:
        return jsonify({'error': f'스케줄러 시작 실패: {str(e)}'}), 500

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """날씨 스케줄러 정지"""
    try:
        from weather_scheduler import stop_weather_scheduler
        stop_weather_scheduler()
        return jsonify({'status': 'success', 'message': '날씨 스케줄러가 정지되었습니다.'})
    except Exception as e:
        return jsonify({'error': f'스케줄러 정지 실패: {str(e)}'}), 500

@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """스케줄러 상태 조회"""
    try:
        from weather_scheduler import get_scheduler_status
        status = get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': f'상태 조회 실패: {str(e)}'}), 500

@app.route('/api/scheduler/stats', methods=['GET'])
def get_weather_statistics():
    """날씨 데이터 통계 조회"""
    try:
        from weather_scheduler import get_weather_stats
        stats = get_weather_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'통계 조회 실패: {str(e)}'}), 500

@app.route('/api/scheduler/collect', methods=['POST'])
def manual_weather_collection():
    """수동 날씨 데이터 수집"""
    try:
        from weather_scheduler import weather_scheduler
        weather_scheduler.collect_market_weather_data()
        return jsonify({'status': 'success', 'message': '날씨 데이터 수집이 완료되었습니다.'})
    except Exception as e:
        return jsonify({'error': f'수동 수집 실패: {str(e)}'}), 500

@app.route('/api/admin/rain-alerts/check', methods=['POST'])
def manual_rain_alert_check():
    """관리자용 수동 비 예보 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_rain_alerts
    
    @admin_required
    def _manual_rain_alert_check(current_user):
        try:
            data = request.get_json() or {}
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
            return jsonify({'error': f'비 예보 알림 확인 실패: {str(e)}'}), 500
    
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
        return jsonify({'error': f'비 예보 확인 실패: {str(e)}'}), 500

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
        return jsonify({'error': f'날씨 조건 확인 실패: {str(e)}'}), 500

@app.route('/api/admin/weather-alerts/check', methods=['POST'])
def manual_weather_alert_check():
    """관리자용 수동 모든 날씨 알림 확인 및 전송"""
    from auth_utils import admin_required
    from weather_alerts import check_and_send_all_weather_alerts

    @admin_required
    def _manual_weather_alert_check(current_user):
        try:
            data = request.get_json() or {}
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
            return jsonify({'error': f'날씨 알림 확인 실패: {str(e)}'}), 500

    return _manual_weather_alert_check()

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
            return jsonify({'error': f'날씨 요약 알림 테스트 실패: {str(e)}'}), 500

    return _test_weather_summary_alert()

# 알림 이력 관련 API
@app.route('/api/alarm-logs', methods=['GET'])
def get_alarm_logs():
    """알림 이력 목록 조회 (페이지네이션 및 필터링 지원)"""
    from auth_utils import login_required

    @login_required
    def _get_alarm_logs(current_user):
        try:
            # 페이지네이션 파라미터
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)

            # 필터링 파라미터
            market_id = request.args.get('market_id', type=int)
            alert_type = request.args.get('alert_type', type=str)
            start_date = request.args.get('start_date', type=str)
            end_date = request.args.get('end_date', type=str)

            # 기본 쿼리
            query = MarketAlarmLog.query

            # 일반 사용자는 자신의 관심시장 알림만 조회 가능
            if not current_user.is_admin():
                user_market_ids = [interest.market_id for interest in
                                  UserMarketInterest.query.filter_by(
                                      user_id=current_user.id,
                                      is_active=True
                                  ).all()]
                query = query.filter(MarketAlarmLog.market_id.in_(user_market_ids))

            # 필터 적용
            if market_id:
                query = query.filter_by(market_id=market_id)

            if alert_type:
                query = query.filter_by(alert_type=alert_type)

            if start_date:
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(MarketAlarmLog.created_at >= start_dt)

            if end_date:
                from datetime import datetime
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(MarketAlarmLog.created_at <= end_dt)

            # 정렬 및 페이지네이션
            query = query.order_by(MarketAlarmLog.created_at.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            # 결과 직렬화
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
                    'created_at': log.created_at.isoformat() if log.created_at else None
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
                    'has_prev': pagination.has_prev
                }
            })

        except Exception as e:
            logger.error(f"알림 이력 조회 실패: {e}")
            return jsonify({'error': f'알림 이력 조회 실패: {str(e)}'}), 500

    return _get_alarm_logs()

@app.route('/api/alarm-logs/<int:log_id>', methods=['GET'])
def get_alarm_log_detail(log_id):
    """특정 알림 이력 상세 조회"""
    from auth_utils import login_required

    @login_required
    def _get_alarm_log_detail(current_user):
        try:
            log = MarketAlarmLog.query.get(log_id)

            if not log:
                return jsonify({'error': '알림 이력을 찾을 수 없습니다.'}), 404

            # 일반 사용자는 자신의 관심시장 알림만 조회 가능
            if not current_user.is_admin():
                is_interested = UserMarketInterest.query.filter_by(
                    user_id=current_user.id,
                    market_id=log.market_id,
                    is_active=True
                ).first()

                if not is_interested:
                    return jsonify({'error': '접근 권한이 없습니다.'}), 403

            # 상세 정보 반환
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
                'weather_data': log.weather_data,  # JSON 전체 데이터
                'temperature': log.temperature,
                'rain_probability': log.rain_probability,
                'wind_speed': log.wind_speed,
                'precipitation_type': log.precipitation_type,
                'forecast_time': log.forecast_time,
                'checked_hours': log.checked_hours,
                'created_at': log.created_at.isoformat() if log.created_at else None
            }

            return jsonify({
                'status': 'success',
                'data': log_data
            })

        except Exception as e:
            logger.error(f"알림 이력 상세 조회 실패: {e}")
            return jsonify({'error': f'알림 이력 상세 조회 실패: {str(e)}'}), 500

    return _get_alarm_log_detail()

@app.route('/api/markets/<int:market_id>/alarm-logs', methods=['GET'])
def get_market_alarm_logs(market_id):
    """특정 시장의 알림 이력 조회"""
    from auth_utils import login_required

    @login_required
    def _get_market_alarm_logs(current_user):
        try:
            # 시장 존재 확인
            market = Market.query.get(market_id)
            if not market:
                return jsonify({'error': '시장을 찾을 수 없습니다.'}), 404

            # 일반 사용자는 자신의 관심시장 알림만 조회 가능
            if not current_user.is_admin():
                is_interested = UserMarketInterest.query.filter_by(
                    user_id=current_user.id,
                    market_id=market_id,
                    is_active=True
                ).first()

                if not is_interested:
                    return jsonify({'error': '접근 권한이 없습니다.'}), 403

            # 페이지네이션 파라미터
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            alert_type = request.args.get('alert_type', type=str)

            # 쿼리
            query = MarketAlarmLog.query.filter_by(market_id=market_id)

            if alert_type:
                query = query.filter_by(alert_type=alert_type)

            query = query.order_by(MarketAlarmLog.created_at.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            # 결과 직렬화
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
                    'created_at': log.created_at.isoformat() if log.created_at else None
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
                    'has_prev': pagination.has_prev
                }
            })

        except Exception as e:
            logger.error(f"시장 알림 이력 조회 실패: {e}")
            return jsonify({'error': f'시장 알림 이력 조회 실패: {str(e)}'}), 500

    return _get_market_alarm_logs()

# Privacy Policy 페이지
@app.route('/privacy')
def privacy():
    """개인정보처리방침 페이지"""
    from flask import render_template
    return render_template('privacy.html')

# Account Deletion 페이지
@app.route('/account-deletion', methods=['GET', 'POST'])
def account_deletion_page():
    """계정 삭제 페이지"""
    from flask import render_template
    from models import User

    if request.method == 'GET':
        # 계정 삭제 폼 표시
        return render_template('account_deletion.html', message=None, deleted=False)

    elif request.method == 'POST':
        # 폼 데이터 가져오기
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        reason = request.form.get('reason', '웹 페이지를 통한 삭제').strip()

        # 입력 검증
        if not email or not password:
            return render_template(
                'account_deletion.html',
                message='이메일과 비밀번호를 입력해주세요.',
                message_type='error',
                deleted=False
            )

        try:
            # 사용자 조회
            user = User.query.filter_by(email=email).first()

            # 인증 확인
            if not user or not user.check_password(password):
                logger.warning(f"계정 삭제 실패: 잘못된 인증 시도 ({email})")
                return render_template(
                    'account_deletion.html',
                    message='이메일 또는 비밀번호가 올바르지 않습니다.',
                    message_type='error',
                    deleted=False
                )

            # 이미 삭제된 계정인지 확인
            if user.is_deleted:
                return render_template(
                    'account_deletion.html',
                    message='이미 삭제된 계정입니다.',
                    message_type='error',
                    deleted=False
                )

            # 계정 삭제 처리
            user.is_active = False
            user.is_deleted = True
            user.deleted_at = datetime.utcnow()
            user.deletion_reason = reason if reason else '웹 페이지를 통한 삭제'

            # 민감 정보 초기화
            user.password_hash = 'deleted'
            user.fcm_token = None
            user.fcm_enabled = False

            db.session.commit()

            logger.info(f"웹 페이지를 통한 계정 삭제 완료: {email} (ID: {user.id})")

            # 성공 메시지 표시
            return render_template(
                'account_deletion.html',
                message='계정이 성공적으로 삭제되었습니다. 이용해 주셔서 감사합니다.',
                message_type='success',
                deleted=True
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"계정 삭제 중 오류 발생: {e}")
            return render_template(
                'account_deletion.html',
                message=f'계정 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
                message_type='error',
                deleted=False
            )

# 웹 데이터베이스 뷰어 라우트들 추가
@app.route('/db-viewer')
def db_viewer():
    """데이터베이스 뷰어 메인 페이지"""
    from web_db_viewer import render_template_string, HTML_TEMPLATE
    return render_template_string(HTML_TEMPLATE)

@app.route('/db-viewer/api/stats')
def api_stats():
    """데이터베이스 통계 API"""
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
            Market.longitude.isnot(None)
        ).count(),
        'latest_weather_update': None
    }
    
    # 최근 날씨 업데이트 시간
    latest_weather = Weather.query.order_by(Weather.created_at.desc()).first()
    if latest_weather:
        stats['latest_weather_update'] = latest_weather.created_at.isoformat()
    
    return jsonify(stats)

@app.route('/db-viewer/api/users')
def api_users():
    """사용자 데이터 API"""
    from models import User
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@app.route('/db-viewer/api/markets')
def api_markets():
    """시장 데이터 API"""
    from models import Market
    markets = Market.query.all()
    return jsonify([market.to_dict() for market in markets])

@app.route('/db-viewer/api/weather')
def api_weather():
    """날씨 데이터 API"""
    from models import Weather
    limit = request.args.get('limit', 100, type=int)
    weather_data = Weather.query.order_by(Weather.created_at.desc()).limit(limit).all()
    return jsonify([weather.to_dict() for weather in weather_data])

@app.route('/db-viewer/api/damage')
def api_damage():
    """피해상태 데이터 API"""
    from models import DamageStatus
    damages = DamageStatus.query.all()
    return jsonify([damage.to_dict() for damage in damages])

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