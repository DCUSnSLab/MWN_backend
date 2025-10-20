#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
인증 API 테스트 스크립트

회원가입, 로그인, 토큰 갱신 등을 테스트합니다.
"""

import requests
import json
import time
import random

BASE_URL = "http://localhost:8002"

def test_auth_flow():
    """전체 인증 플로우 테스트"""
    print("🔐 인증 API 테스트 시작")
    print("=" * 60)
    
    # 랜덤 사용자 데이터 생성
    user_id = int(time.time()) % 10000
    test_user = {
        "name": f"테스트사용자{user_id}",
        "email": f"test{user_id}@example.com",
        "password": "TestPass123!",
        "phone": "010-1234-5678",
        "location": "서울시 강남구"
    }
    
    print(f"테스트 사용자: {test_user['email']}")
    print()
    
    # 1. 회원가입 테스트
    print("1️⃣ 회원가입 테스트")
    register_response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json=test_user,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"응답 코드: {register_response.status_code}")
    if register_response.status_code == 201:
        register_data = register_response.json()
        print("✅ 회원가입 성공")
        print(f"사용자 ID: {register_data['user']['id']}")
        print(f"액세스 토큰: {register_data['tokens']['access_token'][:50]}...")
        
        # 토큰 저장
        access_token = register_data['tokens']['access_token']
        refresh_token = register_data['tokens']['refresh_token']
    else:
        print(f"❌ 회원가입 실패: {register_response.text}")
        return
    
    print()
    
    # 2. 중복 회원가입 테스트
    print("2️⃣ 중복 회원가입 테스트")
    duplicate_response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json=test_user,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"응답 코드: {duplicate_response.status_code}")
    if duplicate_response.status_code == 400:
        print("✅ 중복 이메일 검증 정상")
    else:
        print("❌ 중복 이메일 검증 실패")
    
    print()
    
    # 3. 로그인 테스트
    print("3️⃣ 로그인 테스트")
    login_data = {
        "email": test_user["email"],
        "password": test_user["password"]
    }
    
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"응답 코드: {login_response.status_code}")
    if login_response.status_code == 200:
        login_result = login_response.json()
        print("✅ 로그인 성공")
        print(f"마지막 로그인: {login_result['user']['last_login']}")
        
        # 새 토큰으로 업데이트
        access_token = login_result['tokens']['access_token']
        refresh_token = login_result['tokens']['refresh_token']
    else:
        print(f"❌ 로그인 실패: {login_response.text}")
        return
    
    print()
    
    # 4. 잘못된 비밀번호로 로그인 테스트
    print("4️⃣ 잘못된 비밀번호 로그인 테스트")
    wrong_login_data = {
        "email": test_user["email"],
        "password": "wrongpassword"
    }
    
    wrong_login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=wrong_login_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"응답 코드: {wrong_login_response.status_code}")
    if wrong_login_response.status_code == 401:
        print("✅ 잘못된 비밀번호 검증 정상")
    else:
        print("❌ 잘못된 비밀번호 검증 실패")
    
    print()
    
    # 5. 프로필 조회 테스트 (인증 필요)
    print("5️⃣ 인증된 프로필 조회 테스트")
    profile_response = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    print(f"응답 코드: {profile_response.status_code}")
    if profile_response.status_code == 200:
        profile_data = profile_response.json()
        print("✅ 프로필 조회 성공")
        print(f"사용자 이름: {profile_data['user']['name']}")
        print(f"이메일 인증: {profile_data['user']['email_verified']}")
    else:
        print(f"❌ 프로필 조회 실패: {profile_response.text}")
    
    print()
    
    # 6. 토큰 없이 프로필 조회 테스트
    print("6️⃣ 인증 없이 프로필 조회 테스트")
    no_auth_response = requests.get(f"{BASE_URL}/api/auth/me")
    
    print(f"응답 코드: {no_auth_response.status_code}")
    if no_auth_response.status_code == 401:
        print("✅ 인증 없음 검증 정상")
    else:
        print("❌ 인증 없음 검증 실패")
    
    print()
    
    # 7. 토큰 갱신 테스트
    print("7️⃣ 토큰 갱신 테스트")
    refresh_response = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Content-Type": "application/json"}
    )
    
    print(f"응답 코드: {refresh_response.status_code}")
    if refresh_response.status_code == 200:
        refresh_result = refresh_response.json()
        print("✅ 토큰 갱신 성공")
        print(f"새 액세스 토큰: {refresh_result['tokens']['access_token'][:50]}...")
        
        # 새 토큰으로 업데이트
        new_access_token = refresh_result['tokens']['access_token']
    else:
        print(f"❌ 토큰 갱신 실패: {refresh_response.text}")
        return
    
    print()
    
    # 8. 새 토큰으로 프로필 조회
    print("8️⃣ 새 토큰으로 프로필 조회 테스트")
    new_profile_response = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    
    print(f"응답 코드: {new_profile_response.status_code}")
    if new_profile_response.status_code == 200:
        print("✅ 새 토큰으로 프로필 조회 성공")
    else:
        print("❌ 새 토큰으로 프로필 조회 실패")
    
    print()
    
    # 9. 로그아웃 테스트
    print("9️⃣ 로그아웃 테스트")
    logout_response = requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    
    print(f"응답 코드: {logout_response.status_code}")
    if logout_response.status_code == 200:
        print("✅ 로그아웃 성공")
    else:
        print("❌ 로그아웃 실패")
    
    print()
    print("=" * 60)
    print("🎉 인증 API 테스트 완료!")

def test_password_validation():
    """패스워드 검증 테스트"""
    print("\n🔒 패스워드 검증 테스트")
    print("-" * 40)
    
    weak_passwords = [
        ("short", "짧은 패스워드"),
        ("onlylowercase", "소문자만"),
        ("ONLYUPPERCASE", "대문자만"),
        ("NoNumbers", "숫자 없음"),
        ("nonumber", "소문자만+숫자없음")
    ]
    
    for password, description in weak_passwords:
        user_data = {
            "name": "테스트",
            "email": f"test{random.randint(1000,9999)}@example.com",
            "password": password
        }
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"{description}: {response.status_code} - ", end="")
        if response.status_code == 400:
            print("✅ 약한 패스워드 거부됨")
        else:
            print("❌ 약한 패스워드 허용됨")

def test_email_validation():
    """이메일 검증 테스트"""
    print("\n📧 이메일 검증 테스트")
    print("-" * 40)
    
    invalid_emails = [
        "invalid-email",
        "@example.com",
        "test@",
        "test..test@example.com",
        "test space@example.com"
    ]
    
    for email in invalid_emails:
        user_data = {
            "name": "테스트",
            "email": email,
            "password": "ValidPass123!"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"{email}: {response.status_code} - ", end="")
        if response.status_code == 400:
            print("✅ 잘못된 이메일 거부됨")
        else:
            print("❌ 잘못된 이메일 허용됨")

if __name__ == "__main__":
    test_auth_flow()
    test_password_validation()
    test_email_validation()