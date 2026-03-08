"""
memory/trade_memory.py
최근 거래 기억을 AI 프롬프트에 주입하는 단기 기억 시스템.

사용법:
    from memory.trade_memory import TradeMemory
    memory = TradeMemory(supabase_client)
    context = memory.get_recent_context("btc", limit=10)
    # context를 GPT 프롬프트에 삽입
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.logger import get_logger

log = get_logger("trade_memory")

_TABLE_MAP = {
    "btc": "btc_trades",
    "kr":  "trade_executions",
    "us":  "us_trade_executions",
}

_ORDER_COL = {
    "btc": "timestamp",
    "kr":  "created_at",
    "us":  "created_at",
}


class TradeMemory:
    """단기 기억: 최근 N건 거래를 GPT 프롬프트에 주입하는 형태로 요약."""

    def __init__(self, supabase_client: Any) -> None:
        self.sb = supabase_client

    # ── 공개 API ─────────────────────────────────────────────────────────

    def get_recent_context(self, market: str, limit: int = 10) -> str:
        """
        최근 limit건 거래를 자연어 요약으로 반환.
        GPT 프롬프트 [최근 거래 기억] 섹션에 삽입용.
        """
        rows = self._fetch_recent(market, limit)
        if not rows:
            return "최근 거래 기록 없음"

        lines = []

        # 통계
        closed = self._closed_rows(market, rows)
        if closed:
            pnls = [self._pnl_pct(market, r) for r in closed]
            pnls = [p for p in pnls if p is not None]
            wins = [p for p in pnls if p > 0]
            avg  = sum(pnls) / len(pnls) if pnls else 0
            lines.append(
                f"최근 {len(closed)}건 청산: 승률 {len(wins)/len(pnls)*100:.0f}%"
                f" | 평균 {avg:+.2f}% | 연속손절 {self._loss_streak(market, rows)}회"
            )
        else:
            lines.append(f"최근 {len(rows)}건 기록 (청산 없음)")

        # 최근 5건 상세
        lines.append("최근 5건:")
        for r in rows[:5]:
            action  = self._action(market, r)
            pnl_pct = self._pnl_pct(market, r)
            reason  = str(r.get("reason", "") or "")[:60]
            date    = str(r.get(_ORDER_COL[market], "") or "")[:16]
            pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "미청산"
            lines.append(f"  {date} {action} → {pnl_str}  ({reason})")

        return "\n".join(lines)

    def get_loss_streak(self, market: str) -> int:
        """현재 연속 손절 횟수."""
        rows = self._fetch_recent(market, 20)
        return self._loss_streak(market, rows)

    def get_win_rate(self, market: str, days: int = 30) -> float | None:
        """최근 N일 승률 (청산 건 기준). 데이터 없으면 None."""
        rows = self._fetch_recent(market, 50)
        closed = self._closed_rows(market, rows)
        if not closed:
            return None
        pnls = [self._pnl_pct(market, r) for r in closed]
        pnls = [p for p in pnls if p is not None]
        if not pnls:
            return None
        return len([p for p in pnls if p > 0]) / len(pnls) * 100

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────

    def _fetch_recent(self, market: str, limit: int) -> list[dict]:
        table = _TABLE_MAP.get(market)
        order_col = _ORDER_COL.get(market, "created_at")
        if not table or not self.sb:
            return []
        try:
            return (
                self.sb.table(table)
                .select("*")
                .order(order_col, desc=True)
                .limit(limit)
                .execute()
                .data
            ) or []
        except Exception as e:
            log.warning("trade_memory fetch 실패 (%s): %s", market, e)
            return []

    def _closed_rows(self, market: str, rows: list[dict]) -> list[dict]:
        """청산 완료된 행만 필터."""
        if market == "btc":
            return [r for r in rows if r.get("pnl_pct") is not None]
        if market == "kr":
            return [r for r in rows if r.get("result") in ("CLOSED", "SELL")]
        if market == "us":
            return [r for r in rows if r.get("result") == "CLOSED"]
        return []

    def _pnl_pct(self, market: str, row: dict) -> float | None:
        """손익률 반환 (없으면 None)."""
        val = row.get("pnl_pct")
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _action(self, market: str, row: dict) -> str:
        if market == "btc":
            return str(row.get("action", "?"))
        return str(row.get("trade_type", "?"))

    def _loss_streak(self, market: str, rows: list[dict]) -> int:
        """가장 최근 청산부터 역순으로 연속 손절 횟수."""
        streak = 0
        for r in rows:
            pnl = self._pnl_pct(market, r)
            if pnl is None:
                continue          # 미청산 → skip
            if pnl < 0:
                streak += 1
            else:
                break             # 수익 거래 나오면 스트릭 끊김
        return streak
