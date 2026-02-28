#!/usr/bin/env python3
"""
OpenClaw 고급 Google Sheets 관리 모듈
- 포트폴리오 요약 자동 업데이트
- 통계 분석 및 위험 관리 지표 계산
- 차트 생성 및 알림 시스템
"""

import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess

# 프로젝트 경로 설정
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.env_loader import load_env
from common.supabase_client import get_supabase
from common.logger import get_logger
from common.telegram import send_telegram

load_env()
log = get_logger("sheets_manager")

# 시트 ID 설정
MAIN_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
PORTFOLIO_SHEET_ID = "12nutQo_rA6BVo9xjbIrFhS6PLaz4uC_m82pdIMUIuZA"
STATISTICS_SHEET_ID = "16ai_PTJ6XfIpPaio-AnaNY7aQaDPrdqtrvpA91nUH14"
RISK_SHEET_ID = "1MijDcgoFp6hY1bhl9fhHKTBFpK4yBXZL9lzNZ_MaK-w"

class AdvancedSheetsManager:
    """고급 Google Sheets 관리자"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.gog_path = Path(__file__).resolve().parents[1] / "gog-docker"
        self.gog_password = os.getenv("GOG_KEYRING_PASSWORD", "openclaw-gog-secret")
        
    def _safe_float(self, value) -> float:
        """안전한 float 변환 (NoneType 방지)"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
        
    def _run_gog(self, args: List[str]) -> bool:
        """gog CLI 실행"""
        try:
            env = os.environ.copy()
            env["GOG_KEYRING_PASSWORD"] = self.gog_password
            
            cmd = [str(self.gog_path)] + args
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, env=env
            )
            return result.returncode == 0
        except Exception as e:
            log.error(f"gog 실행 실패: {e}")
            return False
    
    def update_portfolio_summary(self) -> bool:
        """포트폴리오 요약 업데이트"""
        try:
            # 현재 포지션 데이터 조회
            portfolio_data = self._get_portfolio_data()
            
            # 포트폴리오 요약 계산
            summary = self._calculate_portfolio_summary(portfolio_data)
            
            # Google Sheets 업데이트
            return self._update_portfolio_sheet(summary)
            
        except Exception as e:
            log.error(f"포트폴리오 요약 업데이트 실패: {e}")
            return False
    
    def _get_portfolio_data(self) -> Dict[str, Any]:
        """포트폴리오 데이터 조회"""
        data = {"btc": [], "kr": [], "us": []}
        
        try:
            # BTC 포지션
            if self.supabase:
                btc_res = self.supabase.table("btc_position").select("*").eq("status", "OPEN").execute()
                data["btc"] = btc_res.data or []
                
                # KR 포지션
                kr_res = self.supabase.table("trade_executions").select("*").eq("result", "OPEN").execute()
                data["kr"] = kr_res.data or []
                
                # US 포지션
                us_res = self.supabase.table("us_trade_executions").select("*").eq("result", "OPEN").execute()
                data["us"] = us_res.data or []
                
        except Exception as e:
            log.error(f"포트폴리오 데이터 조회 실패: {e}")
            
        return data
    
    def _calculate_portfolio_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """포트폴리오 요약 계산"""
        summary = {
            "current_value": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "total_pnl": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "pnl_pct": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "quantity": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "avg_price": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "daily_pnl": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        # BTC 계산
        for pos in data.get("btc", []):
            if pos.get("status") == "OPEN":
                quantity = self._safe_float(pos.get("quantity", 0))
                entry_price = self._safe_float(pos.get("entry_price", 0))
                current_price = self._safe_float(pos.get("current_price", entry_price))
                
                if quantity > 0 and entry_price > 0 and current_price > 0:
                    current_value = quantity * current_price
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price * 100)
                    
                    summary["current_value"]["btc"] += current_value
                    summary["total_pnl"]["btc"] += pnl
                    summary["pnl_pct"]["btc"] = pnl_pct
                    summary["quantity"]["btc"] += quantity
                    summary["avg_price"]["btc"] = entry_price
        
        # KR 계산
        for pos in data.get("kr", []):
            if pos.get("result") == "OPEN":
                quantity = self._safe_float(pos.get("quantity", 0))
                entry_price = self._safe_float(pos.get("entry_price", 0))
                current_price = self._safe_float(pos.get("current_price", entry_price))
                
                if quantity > 0 and entry_price > 0 and current_price > 0:
                    current_value = quantity * current_price
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price * 100)
                    
                    summary["current_value"]["kr"] += current_value
                    summary["total_pnl"]["kr"] += pnl
                    summary["pnl_pct"]["kr"] = pnl_pct
                    summary["quantity"]["kr"] += quantity
                    summary["avg_price"]["kr"] = entry_price
        
        # US 계산
        for pos in data.get("us", []):
            if pos.get("result") == "OPEN":
                quantity = self._safe_float(pos.get("quantity", 0))
                entry_price = self._safe_float(pos.get("price", 0))
                current_price = self._safe_float(pos.get("current_price", entry_price))
                
                if quantity > 0 and entry_price > 0 and current_price > 0:
                    current_value = quantity * current_price
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price * 100)
                    
                    summary["current_value"]["us"] += current_value
                    summary["total_pnl"]["us"] += pnl
                    summary["pnl_pct"]["us"] = pnl_pct
                    summary["quantity"]["us"] += quantity
                    summary["avg_price"]["us"] = entry_price
        
        # 합계 계산
        for market in ["btc", "kr", "us"]:
            summary["current_value"]["total"] += summary["current_value"][market]
            summary["total_pnl"]["total"] += summary["total_pnl"][market]
        
        # 전체 수익률 계산
        total_investment = summary["current_value"]["total"] - summary["total_pnl"]["total"]
        if total_investment > 0:
            summary["pnl_pct"]["total"] = (summary["total_pnl"]["total"] / total_investment * 100)
        
        return summary
    
    def _update_portfolio_sheet(self, summary: Dict[str, Any]) -> bool:
        """포트폴리오 시트 업데이트"""
        try:
            # 데이터 포맷팅
            rows = [
                ["현재가치", 
                 f"{summary['current_value']['btc']:,.0f}",
                 f"{summary['current_value']['kr']:,.0f}",
                 f"{summary['current_value']['us']:,.0f}",
                 f"{summary['current_value']['total']:,.0f}",
                 summary['update_time']],
                
                ["총 평가손익",
                 f"{summary['total_pnl']['btc']:+,.0f}",
                 f"{summary['total_pnl']['kr']:+,.0f}",
                 f"{summary['total_pnl']['us']:+,.0f}",
                 f"{summary['total_pnl']['total']:+,.0f}",
                 summary['update_time']],
                
                ["수익률(%)",
                 f"{summary['pnl_pct']['btc']:+.2f}%",
                 f"{summary['pnl_pct']['kr']:+.2f}%",
                 f"{summary['pnl_pct']['us']:+.2f}%",
                 f"{summary['pnl_pct']['total']:+.2f}%",
                 summary['update_time']],
                
                ["보유수량",
                 f"{summary['quantity']['btc']:.6f}",
                 f"{summary['quantity']['kr']:.0f}",
                 f"{summary['quantity']['us']:.2f}",
                 "0",
                 summary['update_time']],
                
                ["평균단가",
                 f"{summary['avg_price']['btc']:,.0f}",
                 f"{summary['avg_price']['kr']:,.0f}",
                 f"${summary['avg_price']['us']:.2f}",
                 "0",
                 summary['update_time']],
                
                ["오늘손익",
                 f"{summary['daily_pnl']['btc']:+,.0f}",
                 f"{summary['daily_pnl']['kr']:+,.0f}",
                 f"{summary['daily_pnl']['us']:+,.0f}",
                 f"{summary['daily_pnl']['total']:+,.0f}",
                 summary['update_time']]
            ]
            
            # 기존 데이터 삭제 (2행부터)
            self._run_gog(["sheets", "clear", PORTFOLIO_SHEET_ID, "시트1!A2:F7"])
            
            # 새 데이터 추가
            values_json = json.dumps(rows)
            return self._run_gog([
                "sheets", "append", PORTFOLIO_SHEET_ID, "시트1!A:F",
                "--values-json", values_json
            ])
            
        except Exception as e:
            log.error(f"포트폴리오 시트 업데이트 실패: {e}")
            return False
    
    def update_statistics(self) -> bool:
        """통계 분석 업데이트"""
        try:
            # 거래 데이터 조회
            trades_data = self._get_trades_data()
            
            # 통계 계산
            stats = self._calculate_statistics(trades_data)
            
            # Google Sheets 업데이트
            return self._update_statistics_sheet(stats)
            
        except Exception as e:
            log.error(f"통계 업데이트 실패: {e}")
            return False
    
    def _get_trades_data(self) -> Dict[str, List[Dict]]:
        """거래 데이터 조회"""
        data = {"daily": [], "weekly": [], "monthly": []}
        
        try:
            if self.supabase:
                now = datetime.now()
                
                # 일일 데이터 (오늘)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                daily_res = self.supabase.table("btc_trades").select("*").gte("timestamp", today_start).execute()
                data["daily"] = daily_res.data or []
                
                # 주간 데이터 (최근 7일)
                week_start = (now - timedelta(days=7)).isoformat()
                weekly_res = self.supabase.table("btc_trades").select("*").gte("timestamp", week_start).execute()
                data["weekly"] = weekly_res.data or []
                
                # 월간 데이터 (최근 30일)
                month_start = (now - timedelta(days=30)).isoformat()
                monthly_res = self.supabase.table("btc_trades").select("*").gte("timestamp", month_start).execute()
                data["monthly"] = monthly_res.data or []
                
        except Exception as e:
            log.error(f"거래 데이터 조회 실패: {e}")
            
        return data
    
    def _calculate_statistics(self, data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """통계 계산"""
        stats = {
            "daily": self._calc_period_stats(data["daily"]),
            "weekly": self._calc_period_stats(data["weekly"]),
            "monthly": self._calc_period_stats(data["monthly"])
        }
        return stats
    
    def _calc_period_stats(self, trades: List[Dict]) -> Dict[str, Any]:
        """기간별 통계 계산"""
        if not trades:
            return {
                "total_trades": 0,
                "profitable_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_return": 0,
                "max_loss": 0
            }
        
        total_trades = len(trades)
        profitable_trades = 0
        losing_trades = 0
        returns = []
        
        for trade in trades:
            pnl = float(trade.get("pnl", 0) or 0)
            if pnl > 0:
                profitable_trades += 1
            elif pnl < 0:
                losing_trades += 1
            
            # 수익률 계산
            if pnl != 0:
                entry_price = float(trade.get("entry_price", 1))
                return_pct = (pnl / (entry_price * float(trade.get("quantity", 1)))) * 100
                returns.append(return_pct)
        
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        avg_return = sum(returns) / len(returns) if returns else 0
        max_loss = min(returns) if returns else 0
        
        return {
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "max_loss": max_loss
        }
    
    def _update_statistics_sheet(self, stats: Dict[str, Any]) -> bool:
        """통계 시트 업데이트"""
        try:
            rows = [
                ["일간", 
                 stats["daily"]["total_trades"],
                 stats["daily"]["profitable_trades"],
                 stats["daily"]["losing_trades"],
                 f"{stats['daily']['win_rate']:.1f}",
                 f"{stats['daily']['avg_return']:.2f}",
                 f"{stats['daily']['max_loss']:.2f}"],
                
                ["주간",
                 stats["weekly"]["total_trades"],
                 stats["weekly"]["profitable_trades"],
                 stats["weekly"]["losing_trades"],
                 f"{stats['weekly']['win_rate']:.1f}",
                 f"{stats['weekly']['avg_return']:.2f}",
                 f"{stats['weekly']['max_loss']:.2f}"],
                
                ["월간",
                 stats["monthly"]["total_trades"],
                 stats["monthly"]["profitable_trades"],
                 stats["monthly"]["losing_trades"],
                 f"{stats['monthly']['win_rate']:.1f}",
                 f"{stats['monthly']['avg_return']:.2f}",
                 f"{stats['monthly']['max_loss']:.2f}"]
            ]
            
            # 기존 데이터 삭제
            self._run_gog(["sheets", "clear", STATISTICS_SHEET_ID, "시트1!A2:G4"])
            
            # 새 데이터 추가
            values_json = json.dumps(rows)
            return self._run_gog([
                "sheets", "append", STATISTICS_SHEET_ID, "시트1!A:G",
                "--values-json", values_json
            ])
            
        except Exception as e:
            log.error(f"통계 시트 업데이트 실패: {e}")
            return False
    
    def update_risk_indicators(self) -> bool:
        """위험 관리 지표 업데이트"""
        try:
            # 위험 지표 계산
            risk_data = self._calculate_risk_indicators()
            
            # Google Sheets 업데이트
            return self._update_risk_sheet(risk_data)
            
        except Exception as e:
            log.error(f"위험 관리 지표 업데이트 실패: {e}")
            return False
    
    def _calculate_risk_indicators(self) -> Dict[str, Any]:
        """위험 관리 지표 계산"""
        risk_data = {
            "mdd": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "win_loss_ratio": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "sharpe_ratio": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "max_position_size": {"btc": 0, "kr": 0, "us": 0, "total": 0},
            "risk_level": "낮음"
        }
        
        # 실제 위험 지표 계산 로직 (간소화됨)
        # 여기에 실제 데이터 기반 계산 로직 추가
        
        return risk_data
    
    def _update_risk_sheet(self, risk_data: Dict[str, Any]) -> bool:
        """위험 관리 시트 업데이트"""
        try:
            rows = [
                ["최대손실률(MDD)",
                 f"{risk_data['mdd']['btc']:.2f}%",
                 f"{risk_data['mdd']['kr']:.2f}%",
                 f"{risk_data['mdd']['us']:.2f}%",
                 f"{risk_data['mdd']['total']:.2f}%",
                 risk_data['risk_level']],
                
                ["손익비",
                 f"{risk_data['win_loss_ratio']['btc']:.2f}",
                 f"{risk_data['win_loss_ratio']['kr']:.2f}",
                 f"{risk_data['win_loss_ratio']['us']:.2f}",
                 f"{risk_data['win_loss_ratio']['total']:.2f}",
                 risk_data['risk_level']],
                
                ["샤프지표",
                 f"{risk_data['sharpe_ratio']['btc']:.2f}",
                 f"{risk_data['sharpe_ratio']['kr']:.2f}",
                 f"{risk_data['sharpe_ratio']['us']:.2f}",
                 f"{risk_data['sharpe_ratio']['total']:.2f}",
                 risk_data['risk_level']],
                
                ["최대포지션크기",
                 f"{risk_data['max_position_size']['btc']:.0f}",
                 f"{risk_data['max_position_size']['kr']:.0f}",
                 f"{risk_data['max_position_size']['us']:.0f}",
                 f"{risk_data['max_position_size']['total']:.0f}",
                 risk_data['risk_level']]
            ]
            
            # 기존 데이터 삭제
            self._run_gog(["sheets", "clear", RISK_SHEET_ID, "시트1!A2:F5"])
            
            # 새 데이터 추가
            values_json = json.dumps(rows)
            return self._run_gog([
                "sheets", "append", RISK_SHEET_ID, "시트1!A:F",
                "--values-json", values_json
            ])
            
        except Exception as e:
            log.error(f"위험 관리 시트 업데이트 실패: {e}")
            return False
    
    def send_alerts(self) -> bool:
        """알림 전송"""
        try:
            # 위험 알림 체크
            alerts = self._check_alert_conditions()
            
            if alerts:
                message = self._format_alert_message(alerts)
                return send_telegram(message, parse_mode="Markdown")
            
            return True
            
        except Exception as e:
            log.error(f"알림 전송 실패: {e}")
            return False
    
    def _check_alert_conditions(self) -> List[Dict[str, Any]]:
        """알림 조건 체크"""
        alerts = []
        
        # 손실률 알림 (5% 이상 손실 시)
        # 수익률 알림 (10% 이상 수익 시)
        # 거래량 이상 알림
        
        return alerts
    
    def _format_alert_message(self, alerts: List[Dict[str, Any]]) -> str:
        """알림 메시지 포맷팅"""
        if not alerts:
            return ""
        
        message = "🚨 **OpenClaw 트레이딩 알림**\n\n"
        
        for alert in alerts:
            message += f"• {alert.get('message', '')}\n"
        
        message += f"\n⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def run_full_update(self) -> bool:
        """전체 업데이트 실행"""
        try:
            log.info("고급 Google Sheets 전체 업데이트 시작...")
            
            success = True
            
            # 포트폴리오 요약 업데이트
            if not self.update_portfolio_summary():
                success = False
            
            # 통계 업데이트
            if not self.update_statistics():
                success = False
            
            # 위험 관리 지표 업데이트
            if not self.update_risk_indicators():
                success = False
            
            # 알림 전송
            if not self.send_alerts():
                success = False
            
            log.info(f"전체 업데이트 완료: {'성공' if success else '실패'}")
            return success
            
        except Exception as e:
            log.error(f"전체 업데이트 실패: {e}")
            return False


def main():
    """메인 실행 함수"""
    manager = AdvancedSheetsManager()
    success = manager.run_full_update()
    
    if success:
        print("✅ 고급 Google Sheets 업데이트 완료")
        sys.exit(0)
    else:
        print("❌ 고급 Google Sheets 업데이트 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
