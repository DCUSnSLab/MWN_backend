#!/bin/bash
# 로컬 개발 환경에서 마이그레이션 초기화 스크립트
#
# 사용법:
#   ./init_migration.sh                    # 새로운 마이그레이션 생성
#   ./init_migration.sh "Custom message"   # 커스텀 메시지로 마이그레이션 생성
#   ./init_migration.sh --reset            # 마이그레이션 완전 초기화 (주의!)

set -e

# Flask 앱 설정
export FLASK_APP=app.py

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔧 Flask-Migrate 마이그레이션 관리 도구"
echo "=========================================="

# --reset 옵션 확인
if [ "$1" = "--reset" ]; then
    echo -e "${RED}⚠️  경고: migrations 디렉토리를 삭제하고 완전히 초기화합니다!${NC}"
    echo -e "${RED}   모든 마이그레이션 히스토리가 삭제됩니다.${NC}"
    read -p "계속하시겠습니까? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "취소되었습니다."
        exit 0
    fi

    echo -e "${YELLOW}📁 migrations 디렉토리 삭제 중...${NC}"
    rm -rf migrations
    echo -e "${GREEN}✅ migrations 디렉토리가 삭제되었습니다.${NC}"
fi

# migrations 디렉토리가 없으면 초기화
if [ ! -d "migrations" ]; then
    echo -e "${YELLOW}📁 migrations 디렉토리가 없습니다. 초기화 중...${NC}"
    flask db init
    echo -e "${GREEN}✅ 마이그레이션 초기화 완료!${NC}"
fi

# 마이그레이션 메시지 설정
MESSAGE="${1:-Model changes}"

# 마이그레이션 생성
echo -e "${YELLOW}🔍 모델 변경사항 확인 및 마이그레이션 생성 중...${NC}"
flask db migrate -m "$MESSAGE"

echo ""
echo -e "${GREEN}✅ 마이그레이션 생성 완료!${NC}"
echo ""
echo "다음 단계:"
echo "  1. migrations/versions/ 폴더의 마이그레이션 파일을 검토하세요"
echo "  2. 로컬에서 테스트: flask db upgrade"
echo "  3. 문제없으면 Git에 커밋: git add migrations/ && git commit -m 'Add migration: $MESSAGE'"
echo "  4. Docker 이미지 빌드 시 migrations가 포함되어 Pod에서 자동 적용됩니다"
echo ""
echo "마이그레이션 적용:"
echo "  flask db upgrade           # 최신 버전으로 업그레이드"
echo "  flask db downgrade         # 이전 버전으로 다운그레이드"
echo "  flask db history           # 마이그레이션 히스토리 확인"
echo "  flask db current           # 현재 버전 확인"
