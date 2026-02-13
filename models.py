from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    notification_preferences = db.Column(db.JSON)
    email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    
    # 사용자 탈퇴 관련 필드
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deletion_reason = db.Column(db.Text)
    
    # FCM 관련 필드들
    fcm_token = db.Column(db.Text)  # FCM 등록 토큰
    fcm_enabled = db.Column(db.Boolean, default=True)  # FCM 알림 활성화 여부
    fcm_topics = db.Column(db.JSON)  # 구독한 FCM 주제들
    device_info = db.Column(db.JSON)  # 기기 정보 (플랫폼, 버전 등)

    # 방해금지 시간 설정 (JSON 형식)
    do_not_disturb = db.Column(db.JSON, default=lambda: {
        'enabled': False,  # 방해금지 모드 활성화 여부
        'start_time': '22:00',  # 시작 시간 (HH:MM 형식)
        'end_time': '08:00',  # 종료 시간 (HH:MM 형식)
        'all_day': False,  # 하루 종일 방해금지
        'days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']  # 적용 요일
    })
    
    def set_password(self, password):
        """패스워드를 해시화해서 저장"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """패스워드 확인"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        """사용자 정보를 딕셔너리로 변환 (보안 정보 제외)"""
        user_dict = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
            'role': self.role,
            'email_verified': self.email_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'notification_preferences': self.notification_preferences,
            'fcm_token': self.fcm_token,
            'fcm_enabled': self.fcm_enabled,
            'fcm_topics': self.fcm_topics,
            'device_info': self.device_info,
            'do_not_disturb': self.do_not_disturb or {
                'enabled': False,
                'start_time': '22:00',
                'end_time': '08:00',
                'all_day': False,
                'days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            },
            'is_deleted': self.is_deleted,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'deletion_reason': self.deletion_reason
        }
        
        # 민감한 정보는 관리자만 볼 수 있도록
        if include_sensitive:
            user_dict['password_hash'] = self.password_hash
            
        return user_dict
    
    def to_public_dict(self):
        """공개용 사용자 정보 (최소한의 정보만)"""
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'is_active': self.is_active
        }
    
    def update_fcm_token(self, token, device_info=None):
        """FCM 토큰 업데이트"""
        self.fcm_token = token
        if device_info:
            self.device_info = device_info
        self.updated_at = datetime.utcnow()
    
    def subscribe_to_topic(self, topic):
        """FCM 주제 구독"""
        if not self.fcm_topics:
            self.fcm_topics = []
        if topic not in self.fcm_topics:
            self.fcm_topics.append(topic)
            self.updated_at = datetime.utcnow()
    
    def unsubscribe_from_topic(self, topic):
        """FCM 주제 구독 해제"""
        if self.fcm_topics and topic in self.fcm_topics:
            self.fcm_topics.remove(topic)
            self.updated_at = datetime.utcnow()
    
    def enable_fcm(self):
        """FCM 알림 활성화"""
        self.fcm_enabled = True
        self.updated_at = datetime.utcnow()
    
    def disable_fcm(self):
        """FCM 알림 비활성화"""
        self.fcm_enabled = False
        self.updated_at = datetime.utcnow()
    
    def can_receive_fcm(self):
        """FCM 알림 수신 가능 여부"""
        return (self.is_active and
                self.fcm_enabled and
                self.fcm_token is not None)

    def is_in_do_not_disturb_time(self, check_time=None):
        """
        현재 시간이 방해금지 시간인지 확인

        Args:
            check_time: 확인할 시간 (datetime). None이면 현재 시간 사용

        Returns:
            bool: 방해금지 시간이면 True, 아니면 False
        """
        dnd = self.do_not_disturb

        # 방해금지 설정이 없거나 비활성화된 경우
        if not dnd or not dnd.get('enabled', False):
            return False

        # 하루 종일 방해금지 모드
        if dnd.get('all_day', False):
            return True

        # 현재 시간 가져오기 (또는 지정된 시간 사용)
        if check_time is None:
            check_time = datetime.now()

        # 요일 확인 (월=0, 일=6)
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        current_day = day_names[check_time.weekday()]
        days = dnd.get('days', [])

        # 오늘이 방해금지 적용 요일이 아니면
        if days and current_day not in days:
            return False

        # 시작/종료 시간 가져오기
        start_time_str = dnd.get('start_time', '22:00')
        end_time_str = dnd.get('end_time', '08:00')

        try:
            # 시간 파싱 (HH:MM 형식)
            start_hour, start_minute = map(int, start_time_str.split(':'))
            end_hour, end_minute = map(int, end_time_str.split(':'))

            current_minutes = check_time.hour * 60 + check_time.minute
            start_minutes = start_hour * 60 + start_minute
            end_minutes = end_hour * 60 + end_minute

            # 시작 시간이 종료 시간보다 늦은 경우 (예: 22:00 ~ 08:00, 자정 넘김)
            if start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            else:
                # 일반적인 경우 (예: 12:00 ~ 14:00)
                return start_minutes <= current_minutes < end_minutes

        except (ValueError, AttributeError) as e:
            # 시간 파싱 오류 시 방해금지 아님으로 처리
            return False

    def update_do_not_disturb(self, settings: dict):
        """
        방해금지 설정 업데이트

        Args:
            settings: 업데이트할 설정 딕셔너리
        """
        if self.do_not_disturb is None:
            self.do_not_disturb = {
                'enabled': False,
                'start_time': '22:00',
                'end_time': '08:00',
                'all_day': False,
                'days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            }

        # 기존 설정에 새로운 설정 병합
        self.do_not_disturb.update(settings)
        self.updated_at = datetime.utcnow()

        # SQLAlchemy가 JSON 변경을 감지하도록 플래그 설정
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, 'do_not_disturb')
    
    def is_admin(self):
        """관리자 권한 확인"""
        return self.role == 'admin'
    
    def make_admin(self):
        """관리자 권한 부여"""
        self.role = 'admin'
        self.updated_at = datetime.utcnow()
    
    def make_user(self):
        """일반 사용자 권한으로 변경"""
        self.role = 'user'
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def create_admin(cls, name, email, password, phone=None, location=None):
        """관리자 계정 생성"""
        admin = cls(
            name=name,
            email=email,
            phone=phone,
            location=location,
            role='admin',
            email_verified=True  # 관리자는 기본적으로 이메일 인증됨
        )
        admin.set_password(password)
        return admin

class UserMarketInterest(db.Model):
    """사용자-시장 관심목록 연결 테이블"""
    __tablename__ = 'user_market_interests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    market_id = db.Column(db.Integer, db.ForeignKey('markets.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    notification_enabled = db.Column(db.Boolean, default=True)  # 해당 시장 알림 활성화 여부
    
    # 복합 인덱스로 중복 방지
    __table_args__ = (db.UniqueConstraint('user_id', 'market_id', name='unique_user_market'),)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('market_interests', lazy=True))
    market = db.relationship('Market', backref=db.backref('interested_users', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'market_id': self.market_id,
            'market_name': self.market.name if self.market else None,
            'market_location': self.market.location if self.market else None,
            'market_coordinates': {
                'latitude': self.market.latitude,
                'longitude': self.market.longitude,
                'nx': self.market.nx,
                'ny': self.market.ny
            } if self.market else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'notification_enabled': self.notification_enabled
        }
    
    @classmethod
    def add_interest(cls, user_id, market_id):
        """관심 목록에 시장 추가"""
        existing = cls.query.filter_by(user_id=user_id, market_id=market_id).first()
        
        if existing:
            # 이미 존재하는 경우 활성화
            existing.is_active = True
            existing.notification_enabled = True
            return existing
        
        # 새로 생성
        interest = cls(user_id=user_id, market_id=market_id)
        return interest
    
    @classmethod
    def remove_interest(cls, user_id, market_id):
        """관심 목록에서 시장 제거"""
        interest = cls.query.filter_by(user_id=user_id, market_id=market_id).first()
        if interest:
            interest.is_active = False
        return interest

class Market(db.Model):
    __tablename__ = 'markets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    nx = db.Column(db.Integer)  # 기상청 격자 X 좌표
    ny = db.Column(db.Integer)  # 기상청 격자 Y 좌표
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # 날씨 알림 조건 설정 (JSON 형식)
    alert_conditions = db.Column(db.JSON, default=lambda: {
        'enabled': True,  # 알림 활성화 여부
        'rain_probability': 30,  # 강수확률 임계값 (%)
        'high_temp': 33,  # 폭염 임계값 (°C)
        'low_temp': -12,  # 한파 임계값 (°C)
        'wind_speed': 14,  # 강풍 임계값 (m/s)
        'snow_enabled': True,  # 눈 알림 활성화
        'rain_enabled': True,  # 비 알림 활성화
        'temp_enabled': True,  # 기온 알림 활성화
        'wind_enabled': True  # 강풍 알림 활성화
    })

    # Relationship with damage status
    damage_statuses = db.relationship('DamageStatus', backref='market', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'nx': self.nx,
            'ny': self.ny,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
            'alert_conditions': self.alert_conditions or self.get_default_alert_conditions()
        }

    @staticmethod
    def get_default_alert_conditions():
        """기본 알림 조건 반환"""
        return {
            'enabled': True,
            'rain_probability': 30,
            'high_temp': 33,
            'low_temp': -12,
            'wind_speed': 14,
            'snow_enabled': True,
            'rain_enabled': True,
            'temp_enabled': True,
            'wind_enabled': True
        }

    def update_alert_conditions(self, conditions: dict):
        """알림 조건 업데이트"""
        if self.alert_conditions is None:
            self.alert_conditions = self.get_default_alert_conditions()

        # 기존 조건에 새로운 조건 병합
        self.alert_conditions.update(conditions)
        self.updated_at = datetime.utcnow()

        # SQLAlchemy가 JSON 변경을 감지하도록 플래그 설정
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, 'alert_conditions')
    
    @classmethod
    def search_by_name(cls, query, limit=20):
        """시장 이름으로 검색"""
        return cls.query.filter(
            cls.name.contains(query),
            cls.is_active == True
        ).limit(limit).all()
    
    def get_interested_users(self):
        """이 시장에 관심을 가진 활성 사용자들 반환"""
        from models import UserMarketInterest
        interests = UserMarketInterest.query.filter_by(
            market_id=self.id,
            is_active=True,
            notification_enabled=True
        ).all()
        
        return [interest.user for interest in interests if interest.user.is_active and interest.user.can_receive_fcm()]

class DamageStatus(db.Model):
    __tablename__ = 'damage_statuses'
    
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('markets.id'), nullable=False)
    weather_event = db.Column(db.String(100), nullable=False)  # 태풍, 폭우, 폭설 등
    damage_level = db.Column(db.String(50), nullable=False)    # 경미, 보통, 심각
    description = db.Column(db.Text)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    estimated_recovery_time = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'market_id': self.market_id,
            'weather_event': self.weather_event,
            'damage_level': self.damage_level,
            'description': self.description,
            'reported_at': self.reported_at.isoformat() if self.reported_at else None,
            'estimated_recovery_time': self.estimated_recovery_time.isoformat() if self.estimated_recovery_time else None,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }

class Weather(db.Model):
    __tablename__ = 'weather'
    
    id = db.Column(db.Integer, primary_key=True)
    base_date = db.Column(db.String(8), nullable=False)  # YYYYMMDD
    base_time = db.Column(db.String(4), nullable=False)  # HHMM
    fcst_date = db.Column(db.String(8))  # 예보 날짜 (예보 조회시)
    fcst_time = db.Column(db.String(4))  # 예보 시간 (예보 조회시)
    nx = db.Column(db.Integer, nullable=False)  # 격자 X 좌표
    ny = db.Column(db.Integer, nullable=False)  # 격자 Y 좌표
    
    # 인덱스 추가 (조회 성능 최적화)
    __table_args__ = (
        db.Index('idx_weather_lookup', 'nx', 'ny', 'base_date', 'base_time', 'api_type'),
        db.Index('idx_weather_created_at', 'created_at'),
    )
    
    # 기상 요소들
    temp = db.Column(db.Float)          # T1H: 기온(℃)
    humidity = db.Column(db.Float)      # REH: 습도(%)
    rain_1h = db.Column(db.Float)       # RN1: 1시간 강수량(mm)
    east_west_wind = db.Column(db.Float)    # UUU: 동서바람성분(m/s)
    north_south_wind = db.Column(db.Float)  # VVV: 남북바람성분(m/s)
    wind_direction = db.Column(db.Float)    # VEC: 풍향(deg)
    wind_speed = db.Column(db.Float)        # WSD: 풍속(m/s)
    
    # 예보 요소들 (초단기예보에서만 사용)
    pop = db.Column(db.Float)           # POP: 강수확률(%)
    pty = db.Column(db.String(10))      # PTY: 강수형태 (없음(0), 비(1), 비/눈(2), 눈(3), 소나기(4))
    sky = db.Column(db.String(10))      # SKY: 하늘상태 (맑음(1), 구름많음(3), 흐림(4))
    lightning = db.Column(db.String(10))  # LGT: 낙뢰 (없음(0), 있음(1))
    
    # 메타데이터
    api_type = db.Column(db.String(20), nullable=False)  # 'current' 또는 'forecast'
    location_name = db.Column(db.String(100))  # 지역명
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'base_date': self.base_date,
            'base_time': self.base_time,
            'fcst_date': self.fcst_date,
            'fcst_time': self.fcst_time,
            'nx': self.nx,
            'ny': self.ny,
            'temp': self.temp,
            'humidity': self.humidity,
            'rain_1h': self.rain_1h,
            'east_west_wind': self.east_west_wind,
            'north_south_wind': self.north_south_wind,
            'wind_direction': self.wind_direction,
            'wind_speed': self.wind_speed,
            'pop': self.pop,
            'pty': self.pty,
            'sky': self.sky,
            'lightning': self.lightning,
            'api_type': self.api_type,
            'location_name': self.location_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MarketAlarmLog(db.Model):
    """시장별 날씨 알림 전송 이력"""
    __tablename__ = 'market_alarm_logs'

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('markets.id'), nullable=False)

    # 알림 유형 및 내용
    alert_type = db.Column(db.String(50), nullable=False)  # 'rain', 'high_temp', 'low_temp', 'strong_wind', 'snow'
    alert_title = db.Column(db.String(200), nullable=False)  # 알림 제목
    alert_body = db.Column(db.Text, nullable=False)  # 알림 내용

    # 전송 결과
    total_users = db.Column(db.Integer, default=0)  # 대상 사용자 수
    success_count = db.Column(db.Integer, default=0)  # 전송 성공 수
    failure_count = db.Column(db.Integer, default=0)  # 전송 실패 수

    # 날씨 데이터 (알림 발생 당시의 기상 정보)
    weather_data = db.Column(db.JSON)  # 상세 기상 정보 (JSON)
    temperature = db.Column(db.Float)  # 기온
    rain_probability = db.Column(db.Float)  # 강수확률
    wind_speed = db.Column(db.Float)  # 풍속
    precipitation_type = db.Column(db.String(20))  # 강수형태

    # 메타데이터
    forecast_time = db.Column(db.String(50))  # 예보 시간 (예: "11월 06일 15시")
    checked_hours = db.Column(db.Integer, default=24)  # 확인한 예보 시간 범위
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 관계
    market = db.relationship('Market', backref=db.backref('alarm_logs', lazy='dynamic'))

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'market_id': self.market_id,
            'market_name': self.market.name if self.market else None,
            'alert_type': self.alert_type,
            'alert_title': self.alert_title,
            'alert_body': self.alert_body,
            'total_users': self.total_users,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'weather_data': self.weather_data,
            'temperature': self.temperature,
            'rain_probability': self.rain_probability,
            'wind_speed': self.wind_speed,
            'precipitation_type': self.precipitation_type,
            'forecast_time': self.forecast_time,
            'checked_hours': self.checked_hours,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<MarketAlarmLog {self.id}: {self.market.name if self.market else "Unknown"} - {self.alert_type}>'


class PasswordVerificationAttempt(db.Model):
    """비밀번호 확인 시도 기록 (Rate limiting용)"""
    __tablename__ = 'password_verification_attempts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    success = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(45))  # IPv6 지원

    # 관계
    user = db.relationship('User', backref=db.backref('password_attempts', lazy='dynamic'))

    @classmethod
    def check_rate_limit(cls, user_id, minutes=1, max_attempts=5):
        """
        Rate limit 체크

        Args:
            user_id: 사용자 ID
            minutes: 확인할 시간 범위 (분)
            max_attempts: 최대 시도 횟수

        Returns:
            tuple: (is_allowed, remaining_attempts)
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        recent_attempts = cls.query.filter(
            cls.user_id == user_id,
            cls.attempted_at >= cutoff_time
        ).count()

        is_allowed = recent_attempts < max_attempts
        remaining = max(0, max_attempts - recent_attempts)

        return is_allowed, remaining

    @classmethod
    def check_account_lock(cls, user_id, minutes=15, max_failures=10):
        """
        계정 잠금 체크 (실패 횟수 기준)

        Args:
            user_id: 사용자 ID
            minutes: 확인할 시간 범위 (분)
            max_failures: 최대 실패 횟수

        Returns:
            tuple: (is_locked, failure_count)
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        failure_count = cls.query.filter(
            cls.user_id == user_id,
            cls.attempted_at >= cutoff_time,
            cls.success == False
        ).count()

        is_locked = failure_count >= max_failures

        return is_locked, failure_count

    @classmethod
    def record_attempt(cls, user_id, success, ip_address=None):
        """시도 기록"""
        attempt = cls(
            user_id=user_id,
            success=success,
            ip_address=ip_address
        )
        db.session.add(attempt)
        db.session.commit()
        return attempt

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'attempted_at': self.attempted_at.isoformat() if self.attempted_at else None,
            'success': self.success,
            'ip_address': self.ip_address
        }

class MarketReport(db.Model):
    """신고 접수 (이미지 포함)"""
    __tablename__ = 'market_reports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    market_id = db.Column(db.Integer, db.ForeignKey('markets.id'), nullable=False)
    
    # 신고 내용
    report_type = db.Column(db.String(50), nullable=False)  # drainage, fire, odor, other
    description = db.Column(db.Text)
    image_path = db.Column(db.String(255))  # 서버에 저장된 이미지 파일 경로
    
    # 메타데이터
    status = db.Column(db.String(20), default='pending')  # pending, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    # 관계
    user = db.relationship('User', backref=db.backref('reports', lazy=True))
    market = db.relationship('Market', backref=db.backref('reports', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else "Unknown",
            'market_id': self.market_id,
            'market_name': self.market.name if self.market else "Unknown",
            'report_type': self.report_type,
            'description': self.description,
            'image_path': self.image_path,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }