#!/usr/bin/env python3
"""
OpenClaw 알림 시스템
- 특정 손실률 도달 시 알림
- 목표가 도달 시 알림
- 일일 요약 전송
- 위험 경고 알림
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import Priority, send_telegram

load_env()
log = get_logger("alert_system")

# 일일 요약 알림은 하루 1회만 발송 (10분마다 중복 방지)
_LAST_DAILY_ALERT_FILE = Path(__file__).resolve().parents[1] / ".last_daily_alert_sent"


def _already_sent_daily_summary_today() -> bool:
    try:
        if _LAST_DAILY_ALERT_FILE.exists():
            with open(_LAST_DAILY_ALERT_FILE) as f:
                return f.read().strip() == datetime.now().strftime("%Y-%m-%d")
    except Exception:
        pass
    return False


def _mark_daily_summary_sent() -> None:
    try:
        _LAST_DAILY_ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_DAILY_ALERT_FILE.write_text(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        log.warning("일일 요약 발송일 기록 실패: %s", e)


class AlertSystem:
    """OpenClaw 알림 시스템"""

    def __init__(self):
        self.supabase = get_supabase()
        self.alert_thresholds = {
            "loss_warning": -5.0,    # 5% 손실 경고
            "loss_critical": -10.0,   # 10% 손실 위험
            "profit_target": 10.0,    # 10% 수익 목표
            "position_size_limit": 100000000,  # 1억 포지션 제한
        }

    def _safe_float(self, value) -> float:
        """안전한 float 변환 (NoneType 방지)"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def check_portfolio_alerts(self) -> List[Dict[str, Any]]:
        """포트폴리오 알림 체크"""
        alerts = []

        try:
            # 현재 포지션 조회
            positions = self._get_current_positions()

            for pos in positions:
                market = pos.get("market", "")
                symbol = pos.get("symbol", "")
                current_price = self._safe_float(pos.get("current_price", 0))
                entry_price = self._safe_float(pos.get("entry_price", 0))
                quantity = self._safe_float(pos.get("quantity", 0))

                if entry_price > 0 and current_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    position_value = current_price * quantity

                    # 손실 경고 체크
                    if pnl_pct <= self.alert_thresholds["loss_critical"]:
                        alerts.append({
                            "type": "CRITICAL_LOSS",
                            "message": f"🚨 **위험 손실**: {market.upper()} {symbol} {pnl_pct:.2f}% 손실",
                            "severity": "critical",
                            "data": pos
                        })
                    elif pnl_pct <= self.alert_thresholds["loss_warning"]:
                        alerts.append({
                            "type": "LOSS_WARNING",
                            "message": f"⚠️ **손실 경고**: {market.upper()} {symbol} {pnl_pct:.2f}% 손실",
                            "severity": "warning",
                            "data": pos
                        })

                    # 수익 목표 달성 체크
                    if pnl_pct >= self.alert_thresholds["profit_target"]:
                        alerts.append({
                            "type": "PROFIT_TARGET",
                            "message": f"🎯 **목표 달성**: {market.upper()} {symbol} {pnl_pct:.2f}% 수익",
                            "severity": "info",
                            "data": pos
                        })

                    # 포지션 크기 제한 체크
                    if position_value >= self.alert_thresholds["position_size_limit"]:
                        alerts.append({
                            "type": "POSITION_SIZE_LIMIT",
                            "message": f"📊 **포지션 과다**: {market.upper()} {symbol} {position_value:,.0f}원",
                            "severity": "warning",
                            "data": pos
                        })

        except Exception as e:
            log.error(f"포트폴리오 알림 체크 실패: {e}")

        return alerts

    def _get_current_positions(self) -> List[Dict[str, Any]]:
        """현재 포지션 조회"""
        positions = []

        try:
            if self.supabase:
                # BTC 포지션
                btc_res = self.supabase.table("btc_position").select("*").eq("status", "OPEN").execute()
                for pos in (btc_res.data or []):
                    positions.append({
                        "market": "btc",
                        "symbol": "BTC",
                        "entry_price": self._safe_float(pos.get("entry_price", 0)),
                        "current_price": self._safe_float(pos.get("current_price", pos.get("entry_price", 0))),
                        "quantity": self._safe_float(pos.get("quantity", 0)),
                    })

                # KR 포지션
                kr_res = self.supabase.table("trade_executions").select("*").eq("result", "OPEN").execute()
                for pos in (kr_res.data or []):
                    positions.append({
                        "market": "kr",
                        "symbol": pos.get("stock_code", ""),
                        "entry_price": self._safe_float(pos.get("entry_price", 0)),
                        "current_price": self._safe_float(pos.get("current_price", pos.get("entry_price", 0))),
                        "quantity": self._safe_float(pos.get("quantity", 0)),
                    })

                # US 포지션
                us_res = self.supabase.table("us_trade_executions").select("*").eq("result", "OPEN").execute()
                for pos in (us_res.data or []):
                    positions.append({
                        "market": "us",
                        "symbol": pos.get("symbol", ""),
                        "entry_price": self._safe_float(pos.get("price", 0)),
                        "current_price": self._safe_float(pos.get("current_price", pos.get("price", 0))),
                        "quantity": self._safe_float(pos.get("quantity", 0)),
                    })

        except Exception as e:
            log.error(f"포지션 조회 실패: {e}")

        return positions

    def check_daily_summary_alerts(self) -> List[Dict[str, Any]]:
        """일일 요약 알림 체크"""
        alerts = []

        try:
            # 오늘 거래 통계
            today_stats = self._get_today_statistics()

            # 일일 요약 메시지 생성
            if today_stats["total_trades"] > 0:
                summary_msg = (
                    f"📊 **일일 거래 요약**\n"
                    f"• 총 거래: {today_stats['total_trades']}건\n"
                    f"• 수익 거래: {today_stats['profitable_trades']}건\n"
                    f"• 손실 거래: {today_stats['losing_trades']}건\n"
                    f"• 승률: {today_stats['win_rate']:.1f}%\n"
                    f"• 총 손익: {today_stats['total_pnl']:+,.0f}원"
                )

                alerts.append({
                    "type": "DAILY_SUMMARY",
                    "message": summary_msg,
                    "severity": "info",
                    "data": today_stats
                })

        except Exception as e:
            log.error(f"일일 요약 알림 체크 실패: {e}")

        return alerts

    def _get_today_statistics(self) -> Dict[str, Any]:
        """오늘 통계 조회"""
        stats = {
            "total_trades": 0,
            "profitable_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0
        }

        try:
            if self.supabase:
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

                # BTC 거래
                btc_res = self.supabase.table("btc_trades").select("*").gte("timestamp", today_start).execute()
                for trade in (btc_res.data or []):
                    pnl = float(trade.get("pnl", 0) or 0)
                    stats["total_trades"] += 1
                    stats["total_pnl"] += pnl
                    if pnl > 0:
                        stats["profitable_trades"] += 1
                    elif pnl < 0:
                        stats["losing_trades"] += 1

                # KR 거래
                kr_res = self.supabase.table("trade_executions").select("*").gte("created_at", today_start).execute()
                for trade in (kr_res.data or []):
                    if trade.get("trade_type") == "SELL":
                        entry_price = float(trade.get("entry_price", 0))
                        exit_price = float(trade.get("price", 0))
                        quantity = int(trade.get("quantity", 0))
                        pnl = (exit_price - entry_price) * quantity

                        stats["total_trades"] += 1
                        stats["total_pnl"] += pnl
                        if pnl > 0:
                            stats["profitable_trades"] += 1
                        elif pnl < 0:
                            stats["losing_trades"] += 1

                # US 거래
                us_res = self.supabase.table("us_trade_executions").select("*").gte("created_at", today_start).execute()
                for trade in (us_res.data or []):
                    if trade.get("result") == "CLOSED":
                        entry_price = float(trade.get("price", 0))
                        exit_price = float(trade.get("exit_price", 0))
                        quantity = float(trade.get("quantity", 0))
                        pnl = (exit_price - entry_price) * quantity

                        stats["total_trades"] += 1
                        stats["total_pnl"] += pnl
                        if pnl > 0:
                            stats["profitable_trades"] += 1
                        elif pnl < 0:
                            stats["losing_trades"] += 1

                # 승률 계산
                if stats["total_trades"] > 0:
                    stats["win_rate"] = (stats["profitable_trades"] / stats["total_trades"]) * 100

        except Exception as e:
            log.error(f"통계 조회 실패: {e}")

        return stats

    def check_system_alerts(self) -> List[Dict[str, Any]]:
        """시스템 알림 체크"""
        alerts = []

        try:
            # API 연결 상태 체크
            api_status = self._check_api_status()

            if not api_status["supabase"]:
                alerts.append({
                    "type": "SYSTEM_ERROR",
                    "message": "🔴 **Supabase 연결 실패**: 데이터베이스 연결을 확인하세요",
                    "severity": "critical",
                    "data": {"component": "supabase"}
                })

            if not api_status["telegram"]:
                alerts.append({
                    "type": "SYSTEM_ERROR",
                    "message": "🔴 **Telegram 연결 실패**: 알림 전송을 확인하세요",
                    "severity": "warning",
                    "data": {"component": "telegram"}
                })

        except Exception as e:
            log.error(f"시스템 알림 체크 실패: {e}")

        return alerts

    def _check_api_status(self) -> Dict[str, bool]:
        """API 상태 체크"""
        status = {
            "supabase": False,
            "telegram": False
        }

        try:
            # Supabase 연결 체크
            if self.supabase:
                self.supabase.table("btc_trades").select("id", count="exact").limit(1).execute()
                status["supabase"] = True

            # Telegram 연결 체크 (getMe: 즉시 응답, getUpdates는 long-polling이라 타임아웃 발생)
            import requests as _req
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            if token:
                r = _req.get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout=10,
                )
                status["telegram"] = r.ok

        except Exception as e:
            log.error(f"API 상태 체크 실패: {e}")

        return status

    def send_alerts(self, alerts: List[Dict[str, Any]]) -> bool:
        """알림 전송"""
        if not alerts:
            return True

        try:
            # 심각도별로 그룹화
            critical_alerts = [a for a in alerts if a["severity"] == "critical"]
            warning_alerts = [a for a in alerts if a["severity"] == "warning"]
            info_alerts = [a for a in alerts if a["severity"] == "info"]

            # 심각도 순으로 전송
            all_alerts = critical_alerts + warning_alerts + info_alerts

            for alert in all_alerts:
                message = alert["message"]
                # info 심각도는 일일 리포트 버퍼에만 저장 (개별 발송 안 함)
                prio = Priority.INFO if alert.get("severity") == "info" else Priority.URGENT
                success = send_telegram(message, parse_mode="Markdown", priority=prio)

                if not success:
                    log.error(f"알림 전송 실패: {alert['type']}")
                    return False

                # 연속 전송 방지를 위한 딜레이 (즉시 발송 알림만)
                if prio != Priority.INFO:
                    import time
                    time.sleep(1)

            log.info(f"알림 {len(alerts)}건 전송 완료")
            return True

        except Exception as e:
            log.error(f"알림 전송 실패: {e}")
            return False

    def run_alert_check(self) -> bool:
        """전체 알림 체크 실행"""
        try:
            log.info("알림 시스템 체크 시작...")

            all_alerts = []

            # 포트폴리오 알림 체크
            portfolio_alerts = self.check_portfolio_alerts()
            all_alerts.extend(portfolio_alerts)

            # 일일 요약 알림 체크 (하루 1회만 발송)
            daily_alerts = self.check_daily_summary_alerts()
            if daily_alerts and not _already_sent_daily_summary_today():
                all_alerts.extend(daily_alerts)

            # 시스템 알림 체크
            system_alerts = self.check_system_alerts()
            all_alerts.extend(system_alerts)

            # 알림 전송
            success = self.send_alerts(all_alerts)
            if daily_alerts and success:
                _mark_daily_summary_sent()

            log.info(f"알림 체크 완료: {len(all_alerts)}건 발견, 전송 {'성공' if success else '실패'}")
            return success

        except Exception as e:
            log.error(f"알림 체크 실패: {e}")
            return False


def main():
    """메인 실행 함수"""
    alert_system = AlertSystem()
    success = alert_system.run_alert_check()

    if success:
        print("✅ 알림 시스템 체크 완료")
        sys.exit(0)
    else:
        print("❌ 알림 시스템 체크 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
