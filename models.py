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
    notification_preferences = db.Column(db.JSON)
    email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    
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
            'email_verified': self.email_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'notification_preferences': self.notification_preferences
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

class Market(db.Model):
    __tablename__ = 'markets'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship with damage status
    damage_statuses = db.relationship('DamageStatus', backref='market', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active
        }

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