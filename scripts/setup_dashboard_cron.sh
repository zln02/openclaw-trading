#!/bin/bash
# OpenClaw 대시보드 자동 업데이트 크론 설정

echo "🕐 OpenClaw 대시보드 자동 업데이트 크론 설정"
echo "=========================================="

# 현재 크론 확인
echo "현재 크론 설정:"
crontab -l 2>/dev/null || echo "크론 설정 없음"

echo ""
echo "추가할 크론 작업:"
echo "# 매 10분마다 대시보드 업데이트"
echo "*/10 * * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python scripts/dashboard_runner.py >> /var/log/openclaw_dashboard.log 2>&1"
echo ""
echo "# 매일 자정에 일일 손실 분석 실행"
echo "0 0 * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python agents/daily_loss_analyzer.py >> /var/log/openclaw_analyzer.log 2>&1"
echo ""
echo "# 매일 09:00에 알림 시스템 실행"
echo "0 9 * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python common/alert_system.py >> /var/log/openclaw_alerts.log 2>&1"

echo ""
read -p "위 크론 작업을 추가하시겠습니까? (y/n): " answer

if [[ $answer == "y" || $answer == "Y" ]]; then
    # 기존 크론에 새 작업 추가
    (crontab -l 2>/dev/null; echo "# OpenClaw 대시보드 자동 업데이트"; echo "*/10 * * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python scripts/dashboard_runner.py >> /var/log/openclaw_dashboard.log 2>&1"; echo "# OpenClaw 일일 분석"; echo "0 0 * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python agents/daily_loss_analyzer.py >> /var/log/openclaw_analyzer.log 2>&1"; echo "# OpenClaw 알림 시스템"; echo "0 9 * * * cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python common/alert_system.py >> /var/log/openclaw_alerts.log 2>&1") | crontab -
    
    echo ""
    echo "✅ 크론 설정 완료!"
    echo ""
    echo "업데이트된 크론 설정:"
    crontab -l
else
    echo "❌ 크론 설정이 취소되었습니다."
fi
