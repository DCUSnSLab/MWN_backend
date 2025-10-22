#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
관리자 계정 생성 스크립트

이 스크립트는 서버에서만 실행되어야 하며, 관리자 계정을 생성하는 데 사용됩니다.
보안상 웹 API를 통해서는 관리자 계정을 생성할 수 없습니다.
"""

import sys
import os
from app import app, db
from models import User

def create_admin_account():
    """관리자 계정 생성"""
    
    print("=" * 50)
    print("관리자 계정 생성 스크립트")
    print("=" * 50)
    
    # 기본 관리자 계정 정보
    admin_email = "snslab"
    admin_password = "snslab@cu"
    admin_name = "시스템 관리자"
    admin_location = "관리자"
    
    with app.app_context():
        try:
            # 기존 관리자 계정 확인
            existing_admin = User.query.filter_by(email=admin_email).first()
            
            if existing_admin:
                print(f"⚠️ 관리자 계정이 이미 존재합니다: {admin_email}")
                print(f"   - 사용자 ID: {existing_admin.id}")
                print(f"   - 이름: {existing_admin.name}")
                print(f"   - 권한: {existing_admin.role}")
                print(f"   - 생성일: {existing_admin.created_at}")
                
                # 기존 계정이 관리자가 아닌 경우 권한 업그레이드
                if not existing_admin.is_admin():
                    print("   - 일반 사용자를 관리자로 권한 업그레이드 중...")
                    existing_admin.make_admin()
                    db.session.commit()
                    print("   ✅ 관리자 권한이 부여되었습니다.")
                else:
                    print("   ✅ 이미 관리자 권한을 가지고 있습니다.")
                
                return existing_admin
            
            # 새 관리자 계정 생성
            print(f"📝 새로운 관리자 계정 생성 중...")
            print(f"   - 이메일(ID): {admin_email}")
            print(f"   - 이름: {admin_name}")
            print(f"   - 위치: {admin_location}")
            
            admin_user = User.create_admin(
                name=admin_name,
                email=admin_email,
                password=admin_password,
                location=admin_location
            )
            
            # 데이터베이스에 저장
            db.session.add(admin_user)
            db.session.commit()
            
            print("✅ 관리자 계정이 성공적으로 생성되었습니다!")
            print(f"   - 사용자 ID: {admin_user.id}")
            print(f"   - 이메일(ID): {admin_user.email}")
            print(f"   - 이름: {admin_user.name}")
            print(f"   - 권한: {admin_user.role}")
            print(f"   - 생성일: {admin_user.created_at}")
            
            return admin_user
            
        except Exception as e:
            print(f"❌ 관리자 계정 생성 실패: {e}")
            db.session.rollback()
            return None

def verify_admin_login():
    """관리자 로그인 검증"""
    
    print("\n" + "=" * 50)
    print("관리자 로그인 검증")
    print("=" * 50)
    
    admin_email = "snslab"
    admin_password = "snslab@cu"
    
    with app.app_context():
        try:
            # 관리자 계정 조회
            admin = User.query.filter_by(email=admin_email).first()
            
            if not admin:
                print("❌ 관리자 계정을 찾을 수 없습니다.")
                return False
            
            # 패스워드 확인
            if not admin.check_password(admin_password):
                print("❌ 관리자 패스워드가 일치하지 않습니다.")
                return False
            
            # 관리자 권한 확인
            if not admin.is_admin():
                print("❌ 관리자 권한이 없습니다.")
                return False
            
            print("✅ 관리자 로그인 검증 성공!")
            print(f"   - 관리자 ID: {admin.id}")
            print(f"   - 이름: {admin.name}")
            print(f"   - 이메일: {admin.email}")
            print(f"   - 권한: {admin.role}")
            
            return True
            
        except Exception as e:
            print(f"❌ 관리자 로그인 검증 실패: {e}")
            return False

def list_all_users():
    """모든 사용자 목록 조회 (관리자용)"""
    
    print("\n" + "=" * 50)
    print("전체 사용자 목록")
    print("=" * 50)
    
    with app.app_context():
        try:
            users = User.query.all()
            
            if not users:
                print("📋 등록된 사용자가 없습니다.")
                return
            
            print(f"📊 총 {len(users)}명의 사용자가 등록되어 있습니다.\n")
            
            for user in users:
                print(f"🧑‍💼 사용자 ID: {user.id}")
                print(f"   - 이름: {user.name}")
                print(f"   - 이메일: {user.email}")
                print(f"   - 권한: {user.role}")
                print(f"   - 활성화: {user.is_active}")
                print(f"   - 생성일: {user.created_at}")
                print(f"   - 마지막 로그인: {user.last_login or 'None'}")
                print()
                
        except Exception as e:
            print(f"❌ 사용자 목록 조회 실패: {e}")

def main():
    """메인 함수"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "create":
            create_admin_account()
        elif command == "verify":
            verify_admin_login()
        elif command == "list":
            list_all_users()
        elif command == "all":
            admin = create_admin_account()
            if admin:
                verify_admin_login()
                list_all_users()
        else:
            print("사용법: python create_admin.py [create|verify|list|all]")
            print("  create: 관리자 계정 생성")
            print("  verify: 관리자 로그인 검증")
            print("  list: 전체 사용자 목록 조회")
            print("  all: 모든 작업 수행")
    else:
        # 기본 동작: 관리자 계정 생성
        admin = create_admin_account()
        if admin:
            verify_admin_login()

if __name__ == "__main__":
    main()