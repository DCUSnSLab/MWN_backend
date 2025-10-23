#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
엑셀 파일에서 시장 정보를 읽어와 데이터베이스에 저장하는 스크립트

Excel 파일의 열 정보:
- 시장/상점가명: 시장 이름
- 위도: latitude
- 경도: longitude
- nx: 기상청 격자 X 좌표
- ny: 기상청 격자 Y 좌표

PostgreSQL/SQLite 호환
"""

import pandas as pd
import sys
import os
from datetime import datetime
from app import app, db
from models import Market

def read_excel_file(file_path):
    """엑셀 파일 읽기"""
    try:
        print(f"엑셀 파일 읽기: {file_path}")
        
        # xlsm 파일 읽기 (openpyxl 엔진 사용)
        df = pd.read_excel(file_path, engine='openpyxl')
        
        print(f"총 {len(df)}개의 행을 읽었습니다.")
        print("컬럼 목록:", df.columns.tolist())
        
        return df
    
    except Exception as e:
        print(f"엑셀 파일 읽기 실패: {e}")
        return None

def clean_data(df):
    """데이터 정리 및 검증"""
    print("\n데이터 정리 중...")
    
    # 컬럼명 정규화 (공백 제거)
    df.columns = df.columns.str.strip()
    
    # 필요한 컬럼 매핑
    column_mapping = {
        '시장/상점가명': 'name',
        '위도': 'latitude', 
        '경도': 'longitude',
        'nx': 'nx',
        'ny': 'ny'
    }
    
    # 컬럼명 확인
    missing_columns = []
    for original_col in column_mapping.keys():
        if original_col not in df.columns:
            missing_columns.append(original_col)
    
    if missing_columns:
        print(f"누락된 컬럼: {missing_columns}")
        print(f"사용 가능한 컬럼: {df.columns.tolist()}")
        return None
    
    # 필요한 컬럼만 선택하고 이름 변경
    df_clean = df[list(column_mapping.keys())].copy()
    df_clean = df_clean.rename(columns=column_mapping)
    
    # 빈 값 제거
    print(f"정리 전 행 수: {len(df_clean)}")
    df_clean = df_clean.dropna(subset=['name', 'latitude', 'longitude'])
    print(f"정리 후 행 수: {len(df_clean)}")
    
    # 데이터 타입 변환
    try:
        df_clean['latitude'] = pd.to_numeric(df_clean['latitude'], errors='coerce')
        df_clean['longitude'] = pd.to_numeric(df_clean['longitude'], errors='coerce')
        df_clean['nx'] = pd.to_numeric(df_clean['nx'], errors='coerce').astype('Int64')
        df_clean['ny'] = pd.to_numeric(df_clean['ny'], errors='coerce').astype('Int64')
    except Exception as e:
        print(f"데이터 타입 변환 실패: {e}")
        return None
    
    # NaN 값이 있는 행 제거
    df_clean = df_clean.dropna(subset=['latitude', 'longitude'])
    print(f"최종 행 수: {len(df_clean)}")
    
    return df_clean

def import_to_database(df):
    """데이터베이스에 데이터 저장"""
    print("\n데이터베이스에 저장 중...")
    
    success_count = 0
    error_count = 0
    duplicate_count = 0
    
    with app.app_context():
        try:
            for index, row in df.iterrows():
                try:
                    # 이름으로 중복 확인
                    existing_market = Market.query.filter_by(name=row['name']).first()
                    
                    if existing_market:
                        print(f"중복 건너뜀: {row['name']}")
                        duplicate_count += 1
                        continue
                    
                    # 새 시장 생성
                    market = Market(
                        name=row['name'],
                        location=row['name'],  # 위치는 이름과 동일하게 설정
                        latitude=float(row['latitude']),
                        longitude=float(row['longitude']),
                        nx=int(row['nx']) if pd.notna(row['nx']) else None,
                        ny=int(row['ny']) if pd.notna(row['ny']) else None,
                        category='전통시장'  # 기본 카테고리 설정
                    )
                    
                    db.session.add(market)
                    success_count += 1
                    
                    # 주기적으로 커밋 (대용량 데이터 처리 시 메모리 효율성)
                    if success_count % 50 == 0:
                        db.session.commit()
                        print(f"진행 상황: {success_count}개 처리됨")
                
                except Exception as e:
                    print(f"행 {index} 처리 실패: {e}")
                    print(f"  - 데이터: {row['name']}, 위도: {row['latitude']}, 경도: {row['longitude']}")
                    error_count += 1
                    continue
            
            # 최종 커밋
            db.session.commit()
            print(f"\n데이터베이스 저장 완료!")
            print(f"성공: {success_count}개")
            print(f"중복: {duplicate_count}개") 
            print(f"실패: {error_count}개")
            
            return True
        
        except Exception as e:
            db.session.rollback()
            print(f"데이터베이스 저장 실패: {e}")
            return False

def verify_import():
    """임포트 결과 검증"""
    print("\n임포트 결과 검증 중...")
    
    with app.app_context():
        try:
            # 전체 시장 수 확인
            total_markets = Market.query.count()
            print(f"총 시장 수: {total_markets}")
            
            # 좌표가 있는 시장 수 확인
            markets_with_coords = Market.query.filter(
                Market.latitude.isnot(None),
                Market.longitude.isnot(None)
            ).count()
            print(f"좌표가 있는 시장: {markets_with_coords}")
            
            # nx, ny가 있는 시장 수 확인
            markets_with_grid = Market.query.filter(
                Market.nx.isnot(None),
                Market.ny.isnot(None)
            ).count()
            print(f"격자 좌표가 있는 시장: {markets_with_grid}")
            
            # 샘플 데이터 출력
            print("\n샘플 데이터:")
            sample_markets = Market.query.limit(5).all()
            for market in sample_markets:
                print(f"  - {market.name}: 위도{market.latitude}, 경도{market.longitude}, nx{market.nx}, ny{market.ny}")
            
            return True
            
        except Exception as e:
            print(f"검증 중 오류: {e}")
            return False

def main():
    """메인 함수"""
    print("=" * 60)
    print("시장 데이터 엑셀 임포트 스크립트")
    print("=" * 60)
    
    # 엑셀 파일 경로
    excel_file = "data/market_info.xlsm"
    
    # 파일 존재 확인
    if not os.path.exists(excel_file):
        print(f"엑셀 파일을 찾을 수 없습니다: {excel_file}")
        return 1
    
    # 1. 엑셀 파일 읽기
    df = read_excel_file(excel_file)
    if df is None:
        return 1
    
    # 2. 데이터 정리
    df_clean = clean_data(df)
    if df_clean is None:
        return 1
    
    # 3. 데이터 미리보기
    print("\n데이터 미리보기:")
    print(df_clean.head())
    print(f"\n데이터 요약:")
    print(df_clean.info())
    
    # 4. 자동 진행
    print(f"\n{len(df_clean)}개의 시장 데이터를 데이터베이스에 저장합니다.")
    
    # 5. 데이터베이스에 저장
    if not import_to_database(df_clean):
        return 1
    
    # 6. 결과 검증
    if not verify_import():
        return 1
    
    print("\n✅ 시장 데이터 임포트가 성공적으로 완료되었습니다!")
    return 0

if __name__ == "__main__":
    # pandas와 openpyxl 설치 확인
    try:
        import pandas as pd
        import openpyxl
    except ImportError as e:
        print(f"필요한 패키지가 설치되지 않았습니다: {e}")
        print("다음 명령어로 설치하세요:")
        print("pip install pandas openpyxl")
        sys.exit(1)
    
    sys.exit(main())