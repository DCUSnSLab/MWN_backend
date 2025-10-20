#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
간단한 인증 테스트
"""

import requests
import json

BASE_URL = "http://localhost:8002"

def test_simple_register():
    """간단한 회원가입 테스트"""
    print("🔐 간단한 회원가입 테스트")
    
    test_user = {
        "name": "테스트사용자",
        "email": "simple@test.com",
        "password": "TestPass123!"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        print(f"응답 코드: {response.status_code}")
        print(f"응답 내용: {response.text[:200]}...")
        
        if response.status_code == 201:
            print("✅ 회원가입 성공!")
            data = response.json()
            if 'tokens' in data:
                print(f"토큰 획득: {data['tokens']['access_token'][:30]}...")
        else:
            print("❌ 회원가입 실패")
            
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_simple_register()