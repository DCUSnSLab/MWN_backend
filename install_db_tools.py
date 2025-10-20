#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 GUI 도구 설치 가이드

SQLite 데이터베이스를 GUI로 볼 수 있는 도구들을 안내합니다.
"""

import os
import sys
import subprocess

def check_homebrew():
    """Homebrew 설치 확인"""
    try:
        result = subprocess.run(['brew', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Homebrew가 설치되어 있습니다.")
            return True
        else:
            print("❌ Homebrew가 설치되지 않았습니다.")
            return False
    except FileNotFoundError:
        print("❌ Homebrew가 설치되지 않았습니다.")
        return False

def install_sqlite_browser():
    """DB Browser for SQLite 설치"""
    print("\n📦 DB Browser for SQLite 설치 중...")
    try:
        if check_homebrew():
            # Homebrew로 설치
            result = subprocess.run(['brew', 'install', '--cask', 'db-browser-for-sqlite'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ DB Browser for SQLite 설치 완료!")
                print("💡 Applications 폴더에서 'DB Browser for SQLite'를 실행하세요.")
                return True
            else:
                print("❌ Homebrew 설치 실패. 수동 설치를 시도하세요.")
        else:
            print("❌ Homebrew가 없어 자동 설치할 수 없습니다.")
        
        print("\n🔗 수동 설치 방법:")
        print("1. https://sqlitebrowser.org/dl/ 에서 다운로드")
        print("2. macOS용 .dmg 파일 다운로드 후 설치")
        return False
        
    except Exception as e:
        print(f"❌ 설치 중 오류: {e}")
        return False

def show_database_info():
    """데이터베이스 정보 표시"""
    db_path = os.path.join(os.getcwd(), 'instance', 'weather_notification.db')
    
    print(f"\n📍 데이터베이스 위치:")
    print(f"   {db_path}")
    
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"   파일 크기: {file_size:,} bytes")
        print("   ✅ 데이터베이스 파일 존재")
    else:
        print("   ❌ 데이터베이스 파일이 없습니다.")
        print("   먼저 python app.py를 실행하여 데이터베이스를 생성하세요.")

def show_gui_tools():
    """GUI 도구 목록"""
    print("\n🛠️ SQLite GUI 도구들:")
    print("\n1. 🌐 웹 기반 뷰어 (이미 구현됨)")
    print("   - python web_db_viewer.py 실행")
    print("   - http://localhost:8000/db-viewer 접속")
    print("   - pgAdmin과 유사한 인터페이스")
    
    print("\n2. 📱 DB Browser for SQLite (무료)")
    print("   - 가장 인기 있는 SQLite GUI 도구")
    print("   - 설치: brew install --cask db-browser-for-sqlite")
    print("   - 다운로드: https://sqlitebrowser.org/")
    
    print("\n3. 💎 TablePlus (유료, 무료 체험)")
    print("   - 예쁜 인터페이스, 여러 DB 지원")
    print("   - 설치: brew install --cask tableplus")
    print("   - 다운로드: https://tableplus.com/")
    
    print("\n4. 🐘 pgAdmin (PostgreSQL 전용이지만 확장 가능)")
    print("   - 설치: brew install --cask pgadmin4")
    
    print("\n5. 💻 SQLiteStudio (무료)")
    print("   - 설치: brew install --cask sqlitestudio")
    print("   - 다운로드: https://sqlitestudio.pl/")

def show_command_line_tools():
    """명령줄 도구"""
    print("\n⚡ 명령줄 도구들:")
    print("\n1. 기본 sqlite3 명령")
    print("   sqlite3 instance/weather_notification.db")
    print("   .tables          # 테이블 목록")
    print("   .schema users    # 테이블 스키마")
    print("   SELECT * FROM users LIMIT 5;")
    
    print("\n2. litecli (향상된 SQLite CLI)")
    print("   pip install litecli")
    print("   litecli instance/weather_notification.db")

def main():
    """메인 함수"""
    print("🗄️ SQLite 데이터베이스 GUI 도구 가이드")
    print("=" * 60)
    
    # 데이터베이스 정보 표시
    show_database_info()
    
    # GUI 도구 소개
    show_gui_tools()
    
    # 명령줄 도구 소개
    show_command_line_tools()
    
    print("\n" + "=" * 60)
    
    # 설치 옵션
    install_choice = input("\nDB Browser for SQLite를 자동 설치하시겠습니까? (y/N): ").strip().lower()
    if install_choice in ['y', 'yes']:
        install_sqlite_browser()
    
    print("\n✨ 추천 방법:")
    print("1. 웹 뷰어: python web_db_viewer.py (즉시 사용 가능)")
    print("2. DB Browser for SQLite (가장 인기있는 무료 도구)")
    print("3. TablePlus (유료이지만 매우 예쁜 인터페이스)")

if __name__ == "__main__":
    main()