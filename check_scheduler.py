#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Weather Scheduler 상태 확인 스크립트
"""

import sys
import os
from datetime import datetime

def check_scheduler_status():
    """스케줄러 상태를 확인합니다."""

    print("=" * 60)
    print("Weather Scheduler 상태 확인")
    print("=" * 60)

    try:
        from app import app
        from weather_scheduler import weather_scheduler

        with app.app_context():
            # 1. 스케줄러 실행 상태
            print("\n[1] 스케줄러 실행 상태")
            print("-" * 60)

            is_running = weather_scheduler.scheduler.running
            print(f"실행 중: {'✅ Yes' if is_running else '❌ No'}")

            if not is_running:
                print("\n⚠️ 스케줄러가 실행되지 않고 있습니다!")
                print("해결 방법:")
                print("1. Flask 앱을 재시작하세요 (스케줄러가 자동으로 시작됩니다)")
                print("2. 또는 다음 API를 호출하세요:")
                print("   curl -X POST http://localhost:5000/api/scheduler/start")
                return False

            # 2. 등록된 작업 목록
            print("\n[2] 등록된 작업")
            print("-" * 60)

            jobs = weather_scheduler.scheduler.get_jobs()
            print(f"등록된 작업 수: {len(jobs)}개")

            for job in jobs:
                print(f"\n작업 ID: {job.id}")
                print(f"  이름: {job.name}")
                print(f"  다음 실행: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'}")
                print(f"  트리거: {job.trigger}")

            # 3. 기상청 API 설정
            print("\n[3] 기상청 API 설정")
            print("-" * 60)

            kma_key = os.environ.get('KMA_SERVICE_KEY')
            if kma_key:
                print(f"✅ KMA_SERVICE_KEY 설정됨: {kma_key[:10]}***")
            else:
                print("❌ KMA_SERVICE_KEY가 설정되지 않았습니다!")
                print("   스케줄러가 실행되어도 날씨 데이터를 수집할 수 없습니다.")

            # 4. 데이터베이스 통계
            print("\n[4] 데이터베이스 통계")
            print("-" * 60)

            from models import Market, Weather

            total_markets = Market.query.count()
            active_markets = Market.query.filter_by(is_active=True).count()
            markets_with_coords = Market.query.filter(
                Market.nx.isnot(None),
                Market.ny.isnot(None)
            ).count()

            print(f"전체 시장 수: {total_markets}개")
            print(f"활성 시장 수: {active_markets}개")
            print(f"좌표 있는 시장: {markets_with_coords}개")

            total_weather = Weather.query.count()
            latest_weather = Weather.query.order_by(Weather.created_at.desc()).first()

            print(f"\n날씨 데이터 총 개수: {total_weather}개")
            if latest_weather:
                time_diff = datetime.utcnow() - latest_weather.created_at
                minutes_ago = int(time_diff.total_seconds() / 60)
                print(f"최근 수집 시간: {latest_weather.created_at.strftime('%Y-%m-%d %H:%M:%S')} ({minutes_ago}분 전)")

                if minutes_ago > 60:
                    print("⚠️ 최근 1시간 이내 데이터가 없습니다. 스케줄러가 제대로 작동하지 않을 수 있습니다.")
                else:
                    print("✅ 최근 데이터가 정상적으로 수집되고 있습니다.")
            else:
                print("❌ 날씨 데이터가 없습니다. 아직 수집이 시작되지 않았습니다.")

            # 5. 다음 실행 예정 시간
            print("\n[5] 다음 실행 예정")
            print("-" * 60)

            now = datetime.now()
            current_time = now.strftime('%H:%M')
            current_minute = now.minute

            print(f"현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"현재 분: {current_minute}분")

            # 다음 15분 또는 45분 계산
            if current_minute < 15:
                next_collection = f"{now.hour}:15"
            elif current_minute < 45:
                next_collection = f"{now.hour}:45"
            else:
                next_hour = (now.hour + 1) % 24
                next_collection = f"{next_hour:02d}:15"

            # 다음 정각 계산
            next_alert = f"{(now.hour + 1) % 24:02d}:00"

            print(f"\n다음 날씨 수집: {next_collection}")
            print(f"다음 비 알림 확인: {next_alert}")

            # 6. 수동 실행 테스트
            print("\n[6] 수동 실행 테스트")
            print("-" * 60)
            print("스케줄러를 기다리지 않고 즉시 날씨 데이터를 수집하려면:")
            print("  curl -X POST http://localhost:5000/api/scheduler/collect")
            print("\n스케줄러 상태 API:")
            print("  curl http://localhost:5000/api/scheduler/status")

            print("\n" + "=" * 60)
            print("스케줄러 상태 확인 완료!")
            print("=" * 60)

            return True

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    try:
        success = check_scheduler_status()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n중단됨")
        sys.exit(0)
