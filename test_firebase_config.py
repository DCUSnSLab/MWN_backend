#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Firebase 설정 진단 스크립트
"""

import os
import json
import sys

def check_firebase_config():
    """Firebase 설정을 진단합니다."""

    print("=" * 60)
    print("Firebase 설정 진단")
    print("=" * 60)

    # 1. 환경변수 확인
    print("\n[1] 환경변수 확인")
    print("-" * 60)

    key_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
    credentials_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')

    print(f"FIREBASE_SERVICE_ACCOUNT_KEY: {key_path}")
    print(f"FIREBASE_CREDENTIALS_JSON 설정됨: {bool(credentials_json)}")

    if credentials_json:
        print(f"  - 길이: {len(credentials_json)} 문자")

    # 2. 파일 존재 및 내용 확인
    print("\n[2] 서비스 계정 키 파일 확인")
    print("-" * 60)

    if key_path:
        if os.path.exists(key_path):
            file_size = os.path.getsize(key_path)
            print(f"✓ 파일 존재: {key_path}")
            print(f"✓ 파일 크기: {file_size} bytes")

            if file_size == 0:
                print("✗ 오류: 파일이 비어있습니다!")
                return False

            # 파일 내용 읽기
            try:
                with open(key_path, 'r') as f:
                    content = f.read()

                # JSON 파싱 시도
                try:
                    service_account_data = json.loads(content)
                    print("✓ JSON 파싱 성공")

                    # 3. 서비스 계정 키 내용 확인
                    print("\n[3] 서비스 계정 키 내용 확인")
                    print("-" * 60)

                    required_fields = [
                        'type', 'project_id', 'private_key_id', 'private_key',
                        'client_email', 'client_id', 'auth_uri', 'token_uri'
                    ]

                    for field in required_fields:
                        if field in service_account_data:
                            if field == 'private_key':
                                print(f"✓ {field}: [존재, {len(service_account_data[field])} 문자]")
                            else:
                                print(f"✓ {field}: {service_account_data[field]}")
                        else:
                            print(f"✗ {field}: 없음")

                    # 4. Firebase 프로젝트 정보
                    print("\n[4] Firebase 프로젝트 정보")
                    print("-" * 60)

                    project_id = service_account_data.get('project_id')
                    client_email = service_account_data.get('client_email')

                    print(f"프로젝트 ID: {project_id}")
                    print(f"서비스 계정: {client_email}")

                    # 5. Firebase Admin SDK 초기화 테스트
                    print("\n[5] Firebase Admin SDK 초기화 테스트")
                    print("-" * 60)

                    try:
                        import firebase_admin
                        from firebase_admin import credentials

                        # 기존 앱이 있으면 삭제
                        try:
                            firebase_admin.delete_app(firebase_admin.get_app())
                            print("기존 Firebase 앱 삭제됨")
                        except ValueError:
                            pass

                        # 초기화
                        cred = credentials.Certificate(key_path)
                        app = firebase_admin.initialize_app(cred)
                        print("✓ Firebase Admin SDK 초기화 성공")
                        print(f"  앱 이름: {app.name}")
                        print(f"  프로젝트 ID: {app.project_id}")

                        # 6. FCM API 접근 테스트
                        print("\n[6] FCM 테스트 (잘못된 토큰으로 전송 시도)")
                        print("-" * 60)
                        print("주의: 이 테스트는 실패할 것으로 예상됩니다.")
                        print("오류 메시지를 통해 FCM API 접근 가능 여부를 확인합니다.")

                        from firebase_admin import messaging

                        # 잘못된 토큰으로 테스트 메시지 전송 시도
                        test_token = "invalid_test_token_for_diagnostics"
                        message = messaging.Message(
                            notification=messaging.Notification(
                                title="테스트",
                                body="진단 테스트 메시지"
                            ),
                            token=test_token
                        )

                        try:
                            response = messaging.send(message)
                            print(f"✓ FCM API 호출 성공 (예상치 못한 결과): {response}")
                        except Exception as e:
                            error_type = type(e).__name__
                            error_msg = str(e)

                            print(f"\nFCM API 호출 오류:")
                            print(f"  오류 타입: {error_type}")
                            print(f"  오류 메시지: {error_msg}")

                            # InvalidArgumentError는 정상 (잘못된 토큰 사용)
                            if 'InvalidArgumentError' in error_type or 'not a valid FCM registration token' in error_msg:
                                print("\n✓ FCM API 접근 가능 (잘못된 토큰 오류는 정상)")
                                print("  → 이것은 예상된 결과입니다. FCM API가 정상 작동합니다.")
                            # 404 오류 분석
                            elif '404' in error_msg or 'Not Found' in error_msg:
                                print("\n" + "!" * 60)
                                print("!!! 404 오류 감지 !!!")
                                print("!" * 60)
                                print("\n가능한 원인:")
                                print("1. Firebase Console에서 'Cloud Messaging API'가 활성화되지 않음")
                                print("   → https://console.firebase.google.com/project/{}/settings/cloudmessaging".format(project_id))
                                print("\n2. Google Cloud Console에서 'Firebase Cloud Messaging API' 활성화 필요")
                                print("   → https://console.cloud.google.com/apis/library/fcm.googleapis.com?project={}".format(project_id))
                                print("\n3. 서비스 계정 권한 부족")
                                print("   → https://console.cloud.google.com/iam-admin/serviceaccounts?project={}".format(project_id))
                                print("   → 'Firebase Cloud Messaging API Admin' 역할 필요")
                            else:
                                print(f"\n기타 오류: {e}")

                        # 7. 개별 send() 반복 테스트 (batch API 회피)
                        print("\n[7] 개별 send() 반복 테스트 (batch API 회피)")
                        print("-" * 60)
                        print("주의: 이 테스트는 실패할 것으로 예상됩니다.")

                        # Firebase Admin SDK 버전 확인
                        print(f"firebase-admin 버전: {firebase_admin.__version__}")
                        print("참고: firebase-admin 6.5.0은 send_all()이 /batch를 사용하여 404 오류 발생")
                        print("해결: 개별 send() 반복 호출로 회피")

                        # 개별 전송 테스트
                        test_tokens = [
                            "invalid_test_token_1",
                            "invalid_test_token_2"
                        ]

                        notification = messaging.Notification(
                            title="테스트",
                            body="개별 전송 진단 테스트"
                        )

                        success_count = 0
                        failure_count = 0

                        for idx, token in enumerate(test_tokens):
                            try:
                                message = messaging.Message(
                                    notification=notification,
                                    token=token
                                )
                                response = messaging.send(message)
                                success_count += 1
                                print(f"  토큰 {idx+1}: ✓ 전송 성공 (예상치 못한 결과)")
                            except Exception as e:
                                failure_count += 1
                                error_type = type(e).__name__
                                print(f"  토큰 {idx+1}: 전송 실패 - {error_type}")

                                if 'InvalidArgumentError' in error_type or 'not a valid FCM registration token' in str(e):
                                    print(f"    → 예상된 실패 (잘못된 토큰)")
                                elif '404' in str(e):
                                    print(f"    ⚠ 404 오류 발생!")

                        print(f"\n결과: {success_count} 성공, {failure_count} 실패")

                        if failure_count > 0 and success_count == 0:
                            # 모두 잘못된 토큰 오류로 실패 = 정상
                            print("✓ 개별 send() 방식이 정상 작동합니다!")
                            print("  → 이제 다중 토큰 전송도 문제없이 작동할 것입니다.")
                        elif '404' in str(e):
                            print("✗ 여전히 404 오류 발생 - 추가 조치 필요")

                        # 정리
                        firebase_admin.delete_app(app)

                    except ImportError as e:
                        print(f"✗ Firebase Admin SDK를 가져올 수 없습니다: {e}")
                        print("  pip install firebase-admin 실행이 필요합니다.")
                        return False

                    except Exception as e:
                        print(f"✗ Firebase 초기화 실패: {e}")
                        import traceback
                        traceback.print_exc()
                        return False

                except json.JSONDecodeError as e:
                    print(f"✗ JSON 파싱 실패: {e}")
                    print(f"파일 내용 미리보기 (처음 200자):")
                    print(content[:200])
                    return False

            except Exception as e:
                print(f"✗ 파일 읽기 실패: {e}")
                return False
        else:
            print(f"✗ 파일이 존재하지 않습니다: {key_path}")
            return False
    else:
        print("✗ FIREBASE_SERVICE_ACCOUNT_KEY 환경변수가 설정되지 않았습니다.")
        return False

    print("\n" + "=" * 60)
    print("진단 완료")
    print("=" * 60)

    return True

if __name__ == '__main__':
    try:
        success = check_firebase_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
