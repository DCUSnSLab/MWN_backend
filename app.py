from flask import Flask, request, jsonify
from flask_migrate import Migrate
from datetime import datetime
import os
from database import db

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///weather_notification.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Initialize with app
db.init_app(app)
migrate = Migrate(app, db)

# Models will be imported later to avoid circular import

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/api/users', methods=['GET'])
def get_users():
    """사용자 목록 조회 (관리자용)"""
    from models import User
    from auth_utils import login_required
    
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

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
    phone = data.get('phone', '').strip()
    location = data.get('location', '').strip()
    
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
        # 새 사용자 생성
        user = User(
            name=name,
            email=email,
            phone=phone,
            location=location
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

# 기존 사용자 생성 API는 관리자용으로 변경
@app.route('/api/admin/users', methods=['POST'])
def create_user_admin():
    """관리자용 사용자 생성"""
    from models import User
    
    data = request.get_json()
    user = User(
        name=data.get('name'),
        email=data.get('email'),
        phone=data.get('phone'),
        location=data.get('location')
    )
    
    # 임시 패스워드 설정 (실제로는 이메일로 전송하거나 다른 방식 사용)
    user.set_password(data.get('password', 'temp123'))
    
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@app.route('/api/markets', methods=['GET', 'POST'])
def handle_markets():
    from models import Market
    if request.method == 'GET':
        markets = Market.query.all()
        return jsonify([market.to_dict() for market in markets])
    
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
    """현재 날씨 정보 조회"""
    from weather_api import KMAWeatherAPI, convert_to_grid
    
    data = request.get_json()
    
    # 필수 파라미터 검증
    if 'latitude' not in data or 'longitude' not in data:
        return jsonify({'error': '위도(latitude)와 경도(longitude)가 필요합니다.'}), 400
    
    try:
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        location_name = data.get('location_name', '')
        
        # 서비스키 확인
        service_key = os.environ.get('KMA_SERVICE_KEY')
        if not service_key:
            return jsonify({'error': 'KMA_SERVICE_KEY가 설정되지 않았습니다.'}), 500
        
        # 위경도를 격자좌표로 변환
        nx, ny = convert_to_grid(lat, lon)
        
        # Weather API 호출
        weather_api = KMAWeatherAPI(service_key)
        result = weather_api.get_current_weather(nx, ny, location_name)
        
        return jsonify(result)
        
    except ValueError:
        return jsonify({'error': '위도와 경도는 숫자여야 합니다.'}), 400
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/weather/forecast', methods=['POST'])
def get_forecast_weather():
    """날씨 예보 정보 조회"""
    from weather_api import KMAWeatherAPI, convert_to_grid
    
    data = request.get_json()
    
    # 필수 파라미터 검증
    if 'latitude' not in data or 'longitude' not in data:
        return jsonify({'error': '위도(latitude)와 경도(longitude)가 필요합니다.'}), 400
    
    try:
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        location_name = data.get('location_name', '')
        
        # 서비스키 확인
        service_key = os.environ.get('KMA_SERVICE_KEY')
        if not service_key:
            return jsonify({'error': 'KMA_SERVICE_KEY가 설정되지 않았습니다.'}), 500
        
        # 위경도를 격자좌표로 변환
        nx, ny = convert_to_grid(lat, lon)
        
        # Weather API 호출
        weather_api = KMAWeatherAPI(service_key)
        result = weather_api.get_forecast_weather(nx, ny, location_name)
        
        return jsonify(result)
        
    except ValueError:
        return jsonify({'error': '위도와 경도는 숫자여야 합니다.'}), 400
    except Exception as e:
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

if __name__ == '__main__':
    with app.app_context():
        # Import models here to ensure they are registered with SQLAlchemy
        from models import User, Market, DamageStatus, Weather
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8002)