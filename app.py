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
# 운영에서는 DATABASE_URL env 로 주입(k8s mwn-secret). 미설정 시 명시적으로 실패시켜
# 평문 자격증명 default fallback 으로 인한 사고를 막는다.
_database_url = os.environ.get('DATABASE_URL')
if not _database_url:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('DATABASE_URL environment variable is required in production')
    logger.warning('DATABASE_URL not set; using local SQLite for development')
    _database_url = 'sqlite:///instance/dev.db'
app.config['SQLALCHEMY_DATABASE_URI'] = _database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    # gunicorn --threads 8 환경에서 동시 처리 8 스레드 + 스케줄러 작업 고려.
    # 기본 pool_size 5 는 부족하므로 명시.
    'pool_size': 10,
    'max_overflow': 5,
}
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY environment variable is required in production')
    logger.warning('SECRET_KEY not set; falling back to insecure development value')
    _secret_key = 'dev-secret-key-DO-NOT-USE-IN-PROD'
app.config['SECRET_KEY'] = _secret_key

# 세션 쿠키 보안 옵션 (Flask-Admin 세션 보호)
# - HTTPONLY: JS 접근 차단 (XSS 시 세션 토큰 탈취 방지)
# - SAMESITE=Lax: CSRF 완화 (외부 사이트 POST 요청에 쿠키 미전송)
# - SECURE: HTTPS 전용 — 현재 LB 가 HTTP 라 기본 false. HTTPS 도입 시 env 로 true.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

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

# Rate limiter — /api/auth/login, /api/auth/register 에 데코레이터로 적용된다.
from rate_limit import limiter
limiter.init_app(app)

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
from routes.admin import admin_bp
from routes.markets import markets_bp
from routes.weather import weather_bp
app.register_blueprint(main_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(watchlist_bp)
app.register_blueprint(db_viewer_bp)
app.register_blueprint(alarm_logs_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(fcm_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(markets_bp)
app.register_blueprint(weather_bp)

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