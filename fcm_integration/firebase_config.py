#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Firebase 설정 파일

Firebase Admin SDK 초기화 및 FCM 서비스 설정을 관리합니다.
"""

import os
import firebase_admin
from firebase_admin import credentials, messaging
import json
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class FirebaseConfig:
    """Firebase 설정 관리 클래스"""
    
    def __init__(self):
        self.app = None
        self.initialized = False
    
    def initialize(self, service_account_path=None, service_account_json=None):
        """
        Firebase Admin SDK 초기화
        
        Args:
            service_account_path (str): 서비스 계정 키 파일 경로
            service_account_json (dict): 서비스 계정 키 JSON 객체
        """
        try:
            if self.initialized:
                logger.info("Firebase already initialized")
                return self.app
            
            # 서비스 계정 키 설정
            cred = None
            
            if service_account_json:
                # JSON 객체로 직접 초기화
                cred = credentials.Certificate(service_account_json)
                logger.info("Firebase initialized with JSON credentials")
            elif service_account_path:
                # 파일 경로로 초기화
                cred = credentials.Certificate(service_account_path)
                logger.info(f"Firebase initialized with file: {service_account_path}")
            else:
                # 환경변수에서 키 파일 경로 확인
                key_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
                logger.info(f"debug log 1")
                if key_path and os.path.exists(key_path):
                    cred = credentials.Certificate(key_path)
                    logger.info(f"Firebase initialized with env key: {key_path}")
                else:
                    # 환경변수에서 JSON 문자열 확인
                    key_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
                    logger.info(f"debug log 2")
                    if key_json:
                        logger.info(f"debug log 3")
                        service_account_info = json.loads(key_json)
                        cred = credentials.Certificate(service_account_info)
                        logger.info("Firebase initialized with env JSON")
                    else:
                        logger.info(f"debug log 4")
                        logger.warning("No Firebase credentials found")
                        return None
            
            # Firebase 앱 초기화
            self.app = firebase_admin.initialize_app(cred)
            self.initialized = True
            logger.info("Firebase Admin SDK initialized successfully")
            
            return self.app
            
        except Exception as e:
            logger.error(f"Firebase initialization failed: {e}")
            return None
    
    def is_initialized(self):
        """Firebase 초기화 상태 확인"""
        return self.initialized
    
    def get_app(self):
        """Firebase 앱 인스턴스 반환"""
        return self.app

# 전역 Firebase 설정 인스턴스
firebase_config = FirebaseConfig()

def get_firebase_app():
    """Firebase 앱 인스턴스 반환"""
    if not firebase_config.is_initialized():
        firebase_config.initialize()
    return firebase_config.get_app()

def is_firebase_available():
    """Firebase 사용 가능 여부 확인"""
    return firebase_config.is_initialized()