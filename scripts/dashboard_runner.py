#!/usr/bin/env python3
"""
OpenClaw 통합 대시보드 실행기
- 포트폴리오 요약 업데이트
- 통계 분석 업데이트  
- 위험 관리 지표 업데이트
- 알림 시스템 실행
- 차트 데이터 생성
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 경로 설정
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.env_loader import load_env
from common.logger import get_logger
from common.sheets_manager import AdvancedSheetsManager
from common.alert_system import AlertSystem

load_env()
log = get_logger("dashboard_runner")

class IntegratedDashboard:
    """OpenClaw 통합 대시보드"""
    
    def __init__(self):
        self.sheets_manager = AdvancedSheetsManager()
        self.alert_system = AlertSystem()
        
    def run_full_dashboard_update(self) -> bool:
        """전체 대시보드 업데이트 실행"""
        try:
            log.info("🚀 OpenClaw 통합 대시보드 업데이트 시작...")
            start_time = datetime.now(timezone.utc)
            
            success_count = 0
            total_tasks = 5
            
            # 1. 포트폴리오 요약 업데이트
            log.info("📊 1/5 포트폴리오 요약 업데이트...")
            if self.sheets_manager.update_portfolio_summary():
                success_count += 1
                log.info("✅ 포트폴리오 요약 업데이트 성공")
            else:
                log.error("❌ 포트폴리오 요약 업데이트 실패")
            
            # 2. 통계 분석 업데이트
            log.info("📈 2/5 통계 분석 업데이트...")
            if self.sheets_manager.update_statistics():
                success_count += 1
                log.info("✅ 통계 분석 업데이트 성공")
            else:
                log.error("❌ 통계 분석 업데이트 실패")
            
            # 3. 위험 관리 지표 업데이트
            log.info("⚠️ 3/5 위험 관리 지표 업데이트...")
            if self.sheets_manager.update_risk_indicators():
                success_count += 1
                log.info("✅ 위험 관리 지표 업데이트 성공")
            else:
                log.error("❌ 위험 관리 지표 업데이트 실패")
            
            # 4. 알림 시스템 실행
            log.info("🔔 4/5 알림 시스템 실행...")
            if self.alert_system.run_alert_check():
                success_count += 1
                log.info("✅ 알림 시스템 실행 성공")
            else:
                log.error("❌ 알림 시스템 실행 실패")
            
            # 5. 차트 데이터 생성 (추가 기능)
            log.info("📊 5/5 차트 데이터 생성...")
            if self._generate_chart_data():
                success_count += 1
                log.info("✅ 차트 데이터 생성 성공")
            else:
                log.error("❌ 차트 데이터 생성 실패")
            
            # 결과 요약
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            success_rate = (success_count / total_tasks) * 100
            
            log.info(f"🎯 대시보드 업데이트 완료: {success_count}/{total_tasks} ({success_rate:.1f}%)")
            log.info(f"⏱️ 실행 시간: {duration:.2f}초")
            
            return success_count >= 4  # 80% 이상 성공 시 성공으로 간주
            
        except Exception as e:
            log.error(f"대시보드 업데이트 실패: {e}")
            return False
    
    def _generate_chart_data(self) -> bool:
        """차트 데이터 생성"""
        try:
            # 여기에 차트 데이터 생성 로직 추가
            # 예: 수익률 추이 차트, 거래량 차트 등
            
            log.info("차트 데이터 생성 로직 실행 (개발 중)")
            return True
            
        except Exception as e:
            log.error(f"차트 데이터 생성 실패: {e}")
            return False
    
    def get_dashboard_links(self) -> dict:
        """대시보드 링크 정보 반환 — 환경변수 기반 URL 생성"""
        from common.sheets_manager import MAIN_SHEET_ID, PORTFOLIO_SHEET_ID, STATISTICS_SHEET_ID, RISK_SHEET_ID
        _BASE = "https://docs.google.com/spreadsheets/d"
        return {
            "main_sheet": f"{_BASE}/{MAIN_SHEET_ID}/edit" if MAIN_SHEET_ID else "",
            "portfolio": f"{_BASE}/{PORTFOLIO_SHEET_ID}/edit" if PORTFOLIO_SHEET_ID else "",
            "statistics": f"{_BASE}/{STATISTICS_SHEET_ID}/edit" if STATISTICS_SHEET_ID else "",
            "risk_management": f"{_BASE}/{RISK_SHEET_ID}/edit" if RISK_SHEET_ID else "",
        }


def main():
    """메인 실행 함수"""
    print("🎯 OpenClaw 통합 대시보드 실행기")
    print("=" * 50)
    
    dashboard = IntegratedDashboard()
    
    # 대시보드 업데이트 실행
    success = dashboard.run_full_dashboard_update()
    
    # 결과 출력
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 대시보드 업데이트 성공!")
        
        # 링크 정보 출력 (환경변수 설정된 항목만)
        links = dashboard.get_dashboard_links()
        active_links = {k: v for k, v in links.items() if v}
        if active_links:
            print("\n📊 대시보드 링크:")
            labels = {"main_sheet": "메인 거래기록", "portfolio": "포트폴리오 요약", "statistics": "통계 분석", "risk_management": "위험 관리"}
            for key, url in active_links.items():
                print(f"• {labels.get(key, key)}: {url}")
        
        sys.exit(0)
    else:
        print("❌ 대시보드 업데이트 실패")
        print("로그를 확인하여 문제를 해결하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
