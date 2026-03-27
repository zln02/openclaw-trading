#!/usr/bin/env python3
"""
일일 손실 분석 에이전트 (OpenClaw 연동)

- 지난 24시간 손실 거래 조회 (BTC + KR + US)
- 각 손실 건에 대해 뉴스/시장 검색
- 원인 분석 리포트 → 텔레그램 전송

실행: python agents/daily_loss_analyzer.py
크론: 0 0 * * * (매일 자정)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.logger import get_logger
from common.metrics import calc_trade_pnl
from common.supabase_client import get_supabase
from common.telegram import send_telegram

load_env()
log = get_logger("daily_loss_analyzer")

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
supabase = get_supabase()


def _search_news(symbol: str, market: str, date_str: str) -> str:
    """Brave Search API로 해당 종목/날짜 관련 뉴스 검색."""
    if not BRAVE_API_KEY:
        return "(뉴스 검색 미설정: BRAVE_API_KEY)"
    try:
        import requests
        query = f"{symbol} 주가 뉴스" if market == "kr" else f"{symbol} stock news"
        res = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"X-Subscription-Token": BRAVE_API_KEY},
            timeout=10,
        )
        if res.status_code != 200:
            return f"(검색 오류: HTTP {res.status_code})"
        data = res.json()
        web = data.get("web", {}).get("results", [])[:3]
        if not web:
            return "(관련 뉴스 없음)"
        lines = []
        for w in web:
            title = (w.get("title") or "")[:60]
            if title:
                lines.append(f"• {title}")
        return "\n".join(lines) if lines else "(관련 뉴스 없음)"
    except Exception as e:
        return f"(검색 실패: {e})"


def _fetch_loss_trades() -> list[dict]:
    """지난 24시간 손실 거래 조회 (BTC/KR/US 통합)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    losses = []

    # BTC: btc_position (CLOSED)
    try:
        if supabase:
            res = supabase.table("btc_position").select("*").eq("status", "CLOSED").gte("exit_time", since).execute()
            for r in (res.data or []):
                pnl = float(r.get("pnl", 0) or 0)
                if pnl < 0:
                    losses.append({
                        "market": "btc",
                        "symbol": "BTC",
                        "entry_price": r.get("entry_price"),
                        "exit_price": r.get("exit_price"),
                        "quantity": r.get("quantity"),
                        "pnl": pnl,
                        "pnl_pct": float(r.get("pnl_pct", 0) or 0),
                        "exit_time": r.get("exit_time"),
                    })
    except Exception:
        pass

    # KR: trade_executions (result=CLOSED)
    try:
        if supabase:
            res = supabase.table("trade_executions").select("*").eq("result", "CLOSED").gte("created_at", since).execute()
            for r in (res.data or []):
                if r.get("trade_type") != "SELL":
                    continue
                entry = float(r.get("entry_price", 0) or 0)
                exit_p = float(r.get("price", 0) or 0)
                qty = int(r.get("quantity", 0) or 0)
                if entry and exit_p and qty:
                    pnl = (exit_p - entry) * qty
                    if pnl < 0:
                        losses.append({
                            "market": "kr",
                            "symbol": r.get("stock_code", "") or r.get("stock_name", ""),
                            "entry_price": entry,
                            "exit_price": exit_p,
                            "quantity": qty,
                            "pnl": pnl,
                            "pnl_pct": calc_trade_pnl(r, market="kr") or 0,
                            "exit_time": r.get("created_at"),
                            "reason": r.get("reason", ""),
                        })
    except Exception:
        pass

    # US: us_trade_executions (result=CLOSED)
    try:
        if supabase:
            res = supabase.table("us_trade_executions").select("*").eq("result", "CLOSED").gte("created_at", since).execute()
            for r in (res.data or []):
                if r.get("result") != "CLOSED":
                    continue
                entry = float(r.get("price", 0) or 0)  # US: price = entry
                exit_p = float(r.get("exit_price", 0) or 0)
                qty = float(r.get("quantity", 0) or 0)
                if entry and exit_p and qty:
                    pnl = (exit_p - entry) * qty
                    if pnl < 0:
                        losses.append({
                            "market": "us",
                            "symbol": r.get("symbol", ""),
                            "entry_price": entry,
                            "exit_price": exit_p,
                            "quantity": qty,
                            "pnl": pnl,
                            "pnl_pct": calc_trade_pnl(r, market="us") or 0,
                            "exit_time": r.get("created_at", ""),
                            "reason": r.get("exit_reason", "") or r.get("reason", ""),
                        })
    except Exception:
        pass

    return sorted(losses, key=lambda x: x.get("exit_time", ""), reverse=True)


def run() -> dict:
    """메인 실행: 손실 분석 → 리포트 → 텔레그램."""
    losses = _fetch_loss_trades()

    if not losses:
        msg = "📊 **일일 손실 분석** (지난 24h)\n\n손실 거래 없음 ✅"
        send_telegram(msg)
        return {"ok": True, "loss_count": 0, "sent": True}

    total_pnl = sum(l.get("pnl", 0) for l in losses)
    has_krw = any(l.get("market") in ("btc", "kr") for l in losses)
    pnl_str = f"{total_pnl:+,.0f}원" if has_krw else f"${total_pnl:+,.0f}"
    lines = [
        f"📊 **일일 손실 분석** (지난 24h)",
        f"손실 건수: {len(losses)}건",
        f"총 손실: {pnl_str}",
        "",
    ]

    for i, L in enumerate(losses[:5], 1):  # 최대 5건
        market = L.get("market", "").upper()
        symbol = L.get("symbol", "?")
        pnl_pct = L.get("pnl_pct", 0)
        pnl = L.get("pnl", 0)
        exit_time = (L.get("exit_time") or "")[:16].replace("T", " ")

        pnl_disp = f"{pnl:+,.0f}원" if market in ("BTC", "KR") else f"${pnl:+,.0f}"
        lines.append(f"**{i}. [{market}] {symbol}**")
        lines.append(f"   수익률: {pnl_pct:+.2f}% | 손실: {pnl_disp}")
        lines.append(f"   청산: {exit_time}")

        news = _search_news(symbol, L.get("market", ""), exit_time[:10])
        lines.append(f"   뉴스: {news[:200]}{'...' if len(news) > 200 else ''}")
        lines.append("")

    msg = "\n".join(lines)
    send_telegram(msg)
    return {"ok": True, "loss_count": len(losses), "sent": True}


if __name__ == "__main__":
    result = run()
    log.info(result)
    sys.exit(0 if result.get("ok") else 1)
