#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FCM (Firebase Cloud Messaging) 유틸리티

푸시 알림 전송, 주제 관리, 메시지 구성 등의 FCM 기능을 제공합니다.
"""

import logging
from typing import List, Dict, Optional, Union
from firebase_admin import messaging
from fcm_integration.firebase_config import get_firebase_app, is_firebase_available
from models import User
from database import db

# 로깅 설정
logger = logging.getLogger(__name__)

class FCMService:
    """FCM 서비스 클래스"""
    
    def __init__(self):
        self.app = get_firebase_app()
        self.available = is_firebase_available()
        
        if not self.available:
            logger.warning("Firebase is not available. FCM notifications will be disabled.")
    
    def _deactivate_invalid_tokens(self, tokens: List[str]) -> int:
        """영구 무효 FCM 토큰을 DB에서 비운다.

        UnregisteredError / SenderIdMismatchError가 난 토큰은 다시 살아나지 않으므로
        User.fcm_token을 None으로 만들어 다음 발송 대상에서 제외한다.
        fcm_enabled는 건드리지 않는다(사용자가 직접 끈 설정과 구분하기 위함).
        """
        cleaned = [t for t in set(tokens) if t]
        if not cleaned:
            return 0
        try:
            users = User.query.filter(User.fcm_token.in_(cleaned)).all()
            for user in users:
                user.fcm_token = None
            if users:
                db.session.commit()
                logger.info(f"무효 FCM 토큰 {len(users)}건을 정리했습니다.")
            return len(users)
        except Exception as e:
            logger.error(f"무효 FCM 토큰 정리 실패: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0

    def send_notification(self,
                         token: str,
                         title: str,
                         body: str,
                         data: Optional[Dict] = None,
                         image_url: Optional[str] = None) -> bool:
        """
        개별 기기에 푸시 알림 전송
        
        Args:
            token: FCM 등록 토큰
            title: 알림 제목
            body: 알림 내용
            data: 추가 데이터 (선택사항)
            image_url: 이미지 URL (선택사항)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.available:
            logger.error("Firebase not available")
            return False
        
        try:
            # 알림 메시지 구성
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Android 설정
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#FF6B35',
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            )
            
            # iOS 설정
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body
                        ),
                        sound='default',
                        badge=1
                    )
                )
            )
            
            # 메시지 생성
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=token,
                android=android_config,
                apns=apns_config
            )
            
            # 메시지 전송
            response = messaging.send(message)
            logger.info(f"FCM notification sent successfully: {response}")
            return True
            
        except messaging.UnregisteredError:
            logger.warning(f"FCM token is unregistered: {token}")
            self._deactivate_invalid_tokens([token])
            return False
        except messaging.SenderIdMismatchError:
            logger.error(f"FCM sender ID mismatch: {token}")
            self._deactivate_invalid_tokens([token])
            return False
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {e}")
            return False
    
    def send_multicast(self, 
                      tokens: List[str], 
                      title: str, 
                      body: str, 
                      data: Optional[Dict] = None) -> Dict:
        """
        여러 기기에 푸시 알림 전송
        
        Args:
            tokens: FCM 등록 토큰 리스트
            title: 알림 제목
            body: 알림 내용
            data: 추가 데이터
            
        Returns:
            dict: 전송 결과 통계
        """
        if not self.available:
            logger.error("Firebase not available")
            return {"success_count": 0, "failure_count": len(tokens)}
        
        if not tokens:
            return {"success_count": 0, "failure_count": 0}
        
        try:
            # 알림 메시지 구성
            notification = messaging.Notification(title=title, body=body)

            # Android 설정
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#FF6B35',
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            )

            # iOS 설정
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body
                        ),
                        sound='default',
                        badge=1
                    )
                )
            )

            # 개별 전송 (batch API 404 오류 회피)
            # firebase-admin 6.5.0에서 send_all()도 /batch를 사용하므로 개별 전송 필요
            success_count = 0
            failure_count = 0
            failed_tokens = []
            invalid_tokens = []  # 영구 무효 토큰 (DB 정리 대상)

            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=notification,
                        data=data or {},
                        token=token,
                        android=android_config,
                        apns=apns_config
                    )

                    # 개별 전송
                    response = messaging.send(message)
                    success_count += 1
                    logger.debug(f"Successfully sent to token: {token[:20]}...")

                except messaging.UnregisteredError:
                    failure_count += 1
                    failed_tokens.append(token)
                    invalid_tokens.append(token)
                    logger.warning(f"FCM token is unregistered: {token[:20]}...")
                except messaging.SenderIdMismatchError:
                    failure_count += 1
                    failed_tokens.append(token)
                    invalid_tokens.append(token)
                    logger.error(f"FCM sender ID mismatch: {token[:20]}...")
                except Exception as e:
                    # 네트워크 등 일시적 오류 — 토큰 자체는 유효할 수 있으므로 정리하지 않음
                    failure_count += 1
                    failed_tokens.append(token)
                    logger.warning(f"Failed to send to token {token[:20]}...: {type(e).__name__}: {e}")

            # 영구 무효 토큰을 DB에서 정리
            self._deactivate_invalid_tokens(invalid_tokens)

            logger.info(f"Multicast notification sent individually: {success_count} success, {failure_count} failure out of {len(tokens)} tokens")

            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "failed_tokens": failed_tokens,
                "invalid_tokens": invalid_tokens
            }

        except Exception as e:
            logger.error(f"Failed to send multicast notification: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success_count": 0, "failure_count": len(tokens)}
    
    def send_to_topic(self, 
                     topic: str, 
                     title: str, 
                     body: str, 
                     data: Optional[Dict] = None) -> bool:
        """
        주제 구독자들에게 푸시 알림 전송
        
        Args:
            topic: FCM 주제명
            title: 알림 제목
            body: 알림 내용
            data: 추가 데이터
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.available:
            logger.error("Firebase not available")
            return False
        
        try:
            # 알림 메시지 구성
            notification = messaging.Notification(title=title, body=body)
            
            # 주제 메시지 생성
            message = messaging.Message(
                notification=notification,
                data=data or {},
                topic=topic
            )
            
            # 메시지 전송
            response = messaging.send(message)
            logger.info(f"Topic notification sent successfully to '{topic}': {response}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send topic notification to '{topic}': {e}")
            return False
    
    def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict:
        """
        토큰들을 주제에 구독
        
        Args:
            tokens: FCM 등록 토큰 리스트
            topic: 구독할 주제명
            
        Returns:
            dict: 구독 결과
        """
        if not self.available:
            logger.error("Firebase not available")
            return {"success_count": 0, "failure_count": len(tokens)}
        
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            logger.info(f"Subscribed {response.success_count} tokens to topic '{topic}'")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Failed to subscribe to topic '{topic}': {e}")
            return {"success_count": 0, "failure_count": len(tokens)}
    
    def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> Dict:
        """
        토큰들을 주제에서 구독 해제
        
        Args:
            tokens: FCM 등록 토큰 리스트
            topic: 구독 해제할 주제명
            
        Returns:
            dict: 구독 해제 결과
        """
        if not self.available:
            logger.error("Firebase not available")
            return {"success_count": 0, "failure_count": len(tokens)}
        
        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            logger.info(f"Unsubscribed {response.success_count} tokens from topic '{topic}'")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic '{topic}': {e}")
            return {"success_count": 0, "failure_count": len(tokens)}

class WeatherNotificationService:
    """날씨 알림 서비스"""
    
    def __init__(self):
        self.fcm_service = FCMService()
    
    def send_weather_alert(self, 
                          users: List[User], 
                          weather_data: Dict, 
                          alert_type: str = "weather_alert") -> Dict:
        """
        사용자들에게 날씨 알림 전송
        
        Args:
            users: 알림을 받을 사용자 리스트
            weather_data: 날씨 데이터
            alert_type: 알림 타입
            
        Returns:
            dict: 전송 결과
        """
        # FCM 수신 가능한 사용자들 필터링
        fcm_users = [user for user in users if user.can_receive_fcm()]
        
        if not fcm_users:
            logger.info("No users available for FCM notifications")
            return {"success_count": 0, "failure_count": 0}
        
        # 토큰 수집
        tokens = [user.fcm_token for user in fcm_users]
        
        # 알림 메시지 구성
        title, body = self._create_weather_message(weather_data, alert_type)
        
        # 추가 데이터
        data = {
            "type": alert_type,
            "weather_data": str(weather_data),
            "timestamp": str(weather_data.get('created_at', ''))
        }
        
        # 멀티캐스트 전송
        result = self.fcm_service.send_multicast(tokens, title, body, data)
        
        logger.info(f"Weather alert sent: {result}")
        return result
    
    def send_severe_weather_alert(self, location: str, weather_condition: str) -> Dict:
        """
        [DEPRECATED] 심각한 날씨 상황에 대한 전체 알림 (토픽 기반)

        이 메서드는 더 이상 사용되지 않습니다.
        대신 weather_alerts.py의 check_all_markets_with_all_conditions()를 사용하세요.
        해당 메서드는 관심시장을 등록한 사용자에게만 알림을 전송합니다.

        Args:
            location: 지역명
            weather_condition: 날씨 상황

        Returns:
            dict: 전송 결과
        """
        logger.warning("send_severe_weather_alert() is deprecated. Use weather_alerts.py instead.")

        topic = "severe_weather"
        title = f"⚠️ {location} 기상 특보"
        body = f"{weather_condition} 상황이 발생했습니다. 주의하시기 바랍니다."

        data = {
            "type": "severe_weather",
            "location": location,
            "condition": weather_condition
        }

        success = self.fcm_service.send_to_topic(topic, title, body, data)
        return {"success": success}
    
    def _create_weather_message(self, weather_data: Dict, alert_type: str) -> tuple:
        """날씨 데이터를 기반으로 알림 메시지 생성"""
        location = weather_data.get('location_name', '해당 지역')
        temp = weather_data.get('temp')
        humidity = weather_data.get('humidity')
        rain = weather_data.get('rain_1h', 0)
        
        if alert_type == "severe_weather":
            if rain and rain > 10:
                return ("⛈️ 강우 주의보", f"{location}에 시간당 {rain}mm의 강우가 예상됩니다.")
            elif temp and temp > 35:
                return ("🌡️ 폭염 주의보", f"{location} 기온이 {temp}°C로 매우 높습니다.")
            elif temp and temp < -10:
                return ("❄️ 한파 주의보", f"{location} 기온이 {temp}°C로 매우 낮습니다.")
        
        # 일반 날씨 알림
        title = f"🌤️ {location} 날씨 알림"
        body = f"현재 기온 {temp}°C, 습도 {humidity}%"
        if rain and rain > 0:
            body += f", 강수량 {rain}mm"
        
        return (title, body)

# 전역 서비스 인스턴스
fcm_service = FCMService()
weather_notification_service = WeatherNotificationService()