#!/usr/bin/env python3
"""
미국장 프리마켓 분석 v1.0 (KST 22:30 실행 — 미국장 개장 1시간 전)

- 미국 주요 지수 현황 (S&P500, 나스닥, 다우, VIX)
- 모멘텀 상위 종목 스캔
- 보유 포지션 현황
- 텔레그램 브리핑
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.telegram import send_telegram
from common.supabase_client import get_supabase
from common.logger import get_logger
from common.config import US_TRADING_LOG

load_env()
_log = get_logger("us_premarket", US_TRADING_LOG)

sys.path.insert(0, str(Path(__file__).parent))
from us_momentum_backtest import scan_today_top_us

supabase = get_supabase()


def log(msg: str, level: str = "INFO"):
    """Backward-compat wrapper routing to structured logger."""
    _dispatch = {
        "INFO": _log.info, "WARN": _log.warning,
        "ERROR": _log.error, "OK": _log.info,
    }
    _dispatch.get(level, _log.info)(msg)


def get_us_indices() -> list:
    try:
        import yfinance as yf
        indices = [
            {"symbol": "^GSPC", "name": "S&P500"},
            {"symbol": "^IXIC", "name": "나스닥"},
            {"symbol": "^DJI", "name": "다우"},
            {"symbol": "^VIX", "name": "VIX"},
        ]
        results = []
        for idx in indices:
            try:
                t = yf.Ticker(idx["symbol"])
                h = t.history(period="2d")
                if len(h) >= 2:
                    prev = float(h["Close"].iloc[-2])
                    last = float(h["Close"].iloc[-1])
                    chg = (last - prev) / prev * 100
                    results.append({
                        "name": idx["name"],
                        "price": round(last, 2),
                        "change_pct": round(chg, 2),
                    })
            except Exception:
                continue
        return results
    except Exception as e:
        log(f"US 지수 조회 실패: {e}", "WARN")
        return []


def get_open_positions() -> list:
    if not supabase:
        return []
    try:
        rows = (
            supabase.table("us_trade_executions")
            .select("*")
            .eq("result", "OPEN")
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def run_us_premarket():
    log("=" * 50)
    log("미국장 프리마켓 분석 시작 (KST 22:30)")

    log("미국 지수 조회...")
    indices = get_us_indices()
    for m in indices:
        log(f"  {m['name']}: {m['price']:,.2f} ({m['change_pct']:+.2f}%)")

    log("모멘텀 상위 종목 스캔...")
    try:
        top_stocks = scan_today_top_us(top_n=10)
        log(f"  {len(top_stocks)}개 종목 스캔 완료")
    except Exception as e:
        log(f"  스캔 실패: {e}", "WARN")
        top_stocks = []

    log("보유 포지션 조회...")
    positions = get_open_positions()
    log(f"  {len(positions)}개 보유 중")

    idx_text = "\n".join(
        f"  {m['name']}: {m['price']:,.2f} ({m['change_pct']:+.2f}%)"
        for m in indices
    ) if indices else "  데이터 없음"

    top_text = ""
    if top_stocks:
        lines = []
        for i, s in enumerate(top_stocks[:10], 1):
            sym = s.get("symbol", "?")
            score = s.get("score", 0)
            price = s.get("price", 0)
            lines.append(f"  {i}. {sym}: ${price:,.2f} (점수: {score:.0f})")
        top_text = "\n".join(lines)
    else:
        top_text = "  스캔 데이터 없음"

    pos_text = ""
    if positions:
        lines = []
        for p in positions:
            sym = p.get("symbol", "?")
            entry = p.get("entry_price") or p.get("price", 0)
            lines.append(f"  {sym}: ${float(entry):,.2f}")
        pos_text = "\n".join(lines)
    else:
        pos_text = "  보유 종목 없음"

    msg = (
        f"📊 <b>미국장 프리마켓 브리핑 — US</b>\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d')} 22:30 KST\n"
        f"━━━━━━━━━━━━━\n"
        f"🇺🇸 <b>미국 지수 현황</b>\n{idx_text}\n"
        f"━━━━━━━━━━━━━\n"
        f"🎯 <b>모멘텀 TOP 10</b>\n{top_text}\n"
        f"━━━━━━━━━━━━━\n"
        f"💼 <b>보유 포지션</b> ({len(positions)}개)\n{pos_text}\n"
        f"━━━━━━━━━━━━━\n"
        f"⚠️ 모의투자 | 미국장 23:30 개장"
    )
    send_telegram(msg)
    log("텔레그램 브리핑 전송 완료", "OK")
    log("=" * 50)


if __name__ == "__main__":
    run_us_premarket()
