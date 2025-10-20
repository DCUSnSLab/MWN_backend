#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
인증 관련 유틸리티 함수들

JWT 토큰 생성, 검증, 데코레이터 등을 포함합니다.
"""

import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models import User

# JWT 설정
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # 24시간
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)  # 30일

def generate_tokens(user_id):
    """액세스 토큰과 리프레시 토큰 생성"""
    now = datetime.utcnow()
    
    # 액세스 토큰 페이로드
    access_payload = {
        'user_id': user_id,
        'type': 'access',
        'iat': now,
        'exp': now + JWT_ACCESS_TOKEN_EXPIRES
    }
    
    # 리프레시 토큰 페이로드
    refresh_payload = {
        'user_id': user_id,
        'type': 'refresh',
        'iat': now,
        'exp': now + JWT_REFRESH_TOKEN_EXPIRES
    }
    
    # 토큰 생성
    access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': int(JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    }

def verify_token(token, token_type='access'):
    """토큰 검증"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # 토큰 타입 확인
        if payload.get('type') != token_type:
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_current_user():
    """현재 요청의 사용자 정보 반환"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        # Bearer 토큰 형식 확인
        token_type, token = auth_header.split(' ')
        if token_type.lower() != 'bearer':
            return None
            
        # 토큰 검증
        payload = verify_token(token)
        if not payload:
            return None
            
        # 사용자 조회
        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return None
            
        return user
    except (ValueError, AttributeError):
        return None

def login_required(f):
    """로그인이 필요한 엔드포인트에 사용하는 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        
        # 함수에 current_user를 전달
        return f(current_user=user, *args, **kwargs)
    
    return decorated_function

def optional_auth(f):
    """선택적 인증 데코레이터 (로그인하지 않아도 접근 가능)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        return f(current_user=user, *args, **kwargs)
    
    return decorated_function

def validate_email(email):
    """이메일 형식 검증"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """패스워드 강도 검증"""
    if len(password) < 8:
        return False, "패스워드는 최소 8자 이상이어야 합니다."
    
    if not any(c.isupper() for c in password):
        return False, "패스워드에는 대문자가 포함되어야 합니다."
    
    if not any(c.islower() for c in password):
        return False, "패스워드에는 소문자가 포함되어야 합니다."
    
    if not any(c.isdigit() for c in password):
        return False, "패스워드에는 숫자가 포함되어야 합니다."
    
    return True, "패스워드가 유효합니다."