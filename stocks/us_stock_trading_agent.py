#!/usr/bin/env python3
"""
미국 주식 모멘텀 자동매매 에이전트 v1.0

국내 stock_trading_agent.py 구조를 그대로 가져와서 미주용으로 확장.
- 모멘텀 스코어 상위 종목 자동 매수
- 손절/익절/트레일링 스탑 자동 청산
- Supabase DB 기록 (us_trade_executions)
- 텔레그램 알림
- yfinance 데이터 기반 (RSI/BB/거래량)

실행:
    .venv/bin/python stocks/us_stock_trading_agent.py          # 매매 사이클
    .venv/bin/python stocks/us_stock_trading_agent.py check    # 손절/익절만 체크
    .venv/bin/python stocks/us_stock_trading_agent.py status   # 보유 현황
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.telegram import send_telegram as _tg_send
from common.supabase_client import get_supabase

load_env()

sys.path.insert(0, str(Path(__file__).parent))
from us_momentum_backtest import scan_today_top_us, US_UNIVERSE, MomentumScore

supabase = get_supabase()

# ─────────────────────────────────────────────
# 리스크 설정 (미주용)
# ─────────────────────────────────────────────
RISK = {
    "stop_loss": -0.035,         # 손절 -3.5% (비용 포함 실질 -3%)
    "take_profit": 0.10,         # 익절 +10%
    "trailing_stop": 0.02,       # 트레일링 2%
    "trailing_activate": 0.025,  # 수익 2.5% 이상에서 트레일링 활성화
    "max_positions": 5,
    "max_trades_per_day": 3,
    "min_score": 50,             # 55 -> 50 완화
    "min_order_usd": 50,
    "fee_rate": 0.001,
    "timecut_days": 12,          # 10 -> 12일로 확대
    "virtual_capital": 10000,
    # 모멘텀 등급별 차등 포지션 사이징
    "invest_ratio_A": 0.30,      # A등급: 자본의 30%
    "invest_ratio_B": 0.20,      # B등급: 자본의 20%
    "invest_ratio_C": 0.15,      # C등급: 자본의 15%
}

RULES = {
    "buy_composite_min": 50,     # 55 -> 50 하향
    "buy_rsi_hard_max": 80,
    "buy_vol_hard_min": 0.3,
    "sell_rsi_min": 78,
}

US_TRADE_TABLE = "us_trade_executions"
STOP_FLAG = Path(__file__).parent / "US_STOP_TRADING"

# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "TRADE": "💰"}.get(level, "")
    print(f"[US_AGENT][{ts}] {prefix} {msg}")


def send_telegram(msg: str):
    _tg_send(msg)


def is_us_market_open() -> bool:
    """미국장 대략 개장 여부 (한국 시간 기준 23:30~06:00, 서머타임 무시)."""
    now = datetime.now()
    h = now.hour
    return h >= 23 or h < 6


# ─────────────────────────────────────────────
# 시장/지표 데이터
# ─────────────────────────────────────────────
_yf_cache: Dict[str, dict] = {}


def get_us_indicators(symbol: str) -> Optional[dict]:
    """yfinance에서 일봉 기반 RSI/BB/거래량 지표 계산."""
    if symbol in _yf_cache:
        return _yf_cache[symbol]

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="90d")
        if hist is None or len(hist) < 30:
            return None

        close = hist["Close"]
        high = hist["High"]
        volume = hist["Volume"]
        price = float(close.iloc[-1])

        rsi_s = RSIIndicator(close=close, window=14).rsi()
        rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0

        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])
        bb_width = bb_upper - bb_lower
        bb_pos = ((price - bb_lower) / bb_width * 100) if bb_width > 0 else 50.0

        vol_20 = float(volume.tail(20).mean())
        vol_5 = float(volume.tail(5).mean())
        vol_ratio = (vol_5 / vol_20) if vol_20 > 0 else 1.0

        high_60d = float(high.tail(60).max())
        near_high = (price / high_60d * 100) if high_60d > 0 else 50.0

        result = {
            "price": price,
            "rsi": round(rsi, 1),
            "bb_pos": round(bb_pos, 1),
            "vol_ratio": round(vol_ratio, 2),
            "near_high": round(near_high, 1),
            "high_60d": high_60d,
        }
        _yf_cache[symbol] = result
        return result
    except Exception as e:
        log(f"{symbol}: 지표 조회 실패: {e}", "WARN")
        return None


# ─────────────────────────────────────────────
# Supabase DB (포지션 관리)
# ─────────────────────────────────────────────
def get_open_positions() -> List[dict]:
    if not supabase:
        return []
    try:
        res = (
            supabase.table(US_TRADE_TABLE)
            .select("*")
            .eq("result", "OPEN")
            .execute()
        )
        return res.data or []
    except Exception as e:
        log(f"포지션 조회 실패: {e}", "WARN")
        return []


def get_position_for_symbol(symbol: str) -> List[dict]:
    return [p for p in get_open_positions() if p.get("symbol") == symbol]


def count_today_buys() -> int:
    if not supabase:
        return 0
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        res = (
            supabase.table(US_TRADE_TABLE)
            .select("id")
            .eq("trade_type", "BUY")
            .gte("created_at", today)
            .execute()
        )
        return len(res.data or [])
    except Exception:
        return 0


def save_trade(trade_type: str, symbol: str, quantity: float, price: float,
               reason: str = "", score: float = 0, result: str = "OPEN") -> None:
    if not supabase:
        return
    try:
        supabase.table(US_TRADE_TABLE).insert({
            "trade_type": trade_type,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "reason": reason,
            "score": score,
            "result": result,
            "highest_price": price,
        }).execute()
    except Exception as e:
        log(f"DB 저장 실패: {e}", "ERROR")


def close_position(symbol: str, exit_price: float, reason: str) -> None:
    if not supabase:
        return
    positions = get_position_for_symbol(symbol)
    for p in positions:
        pid = p.get("id")
        if pid:
            try:
                supabase.table(US_TRADE_TABLE).update({
                    "result": "CLOSED",
                    "exit_price": exit_price,
                    "exit_reason": reason,
                }).eq("id", pid).execute()
            except Exception as e:
                log(f"DB 클로즈 실패 (id={pid}): {e}", "ERROR")


def update_highest_price(symbol: str, new_high: float) -> None:
    if not supabase:
        return
    positions = get_position_for_symbol(symbol)
    for p in positions:
        pid = p.get("id")
        current_high = float(p.get("highest_price", 0) or 0)
        if new_high > current_high and pid:
            try:
                supabase.table(US_TRADE_TABLE).update({
                    "highest_price": new_high,
                }).eq("id", pid).execute()
            except Exception:
                pass


# ─────────────────────────────────────────────
# 매매 로직
# ─────────────────────────────────────────────
def should_buy(symbol: str, score: float, indicators: dict) -> dict:
    """매수 판단: 복합 스코어 시스템 (모멘텀 강도 + 기술적 분석 가중합)."""
    rsi = indicators.get("rsi", 50)
    bb_pos = indicators.get("bb_pos", 50)
    vol_ratio = indicators.get("vol_ratio", 1.0)
    near_high = indicators.get("near_high", 50)

    if score < RISK["min_score"]:
        return {"action": "HOLD", "reason": f"스코어 부족 ({score:.0f} < {RISK['min_score']})"}
    if rsi > RULES["buy_rsi_hard_max"]:
        return {"action": "HOLD", "reason": f"RSI 극과매수 ({rsi:.0f} > {RULES['buy_rsi_hard_max']})"}
    if vol_ratio < RULES["buy_vol_hard_min"]:
        return {"action": "HOLD", "reason": f"거래량 급감 ({vol_ratio:.2f}x)"}

    cs = 0
    reasons = []

    # 1) 모멘텀 등급 (45점 만점)
    if score >= 75:
        cs += 45; reasons.append(f"모멘텀A({score:.0f})")
    elif score >= 65:
        cs += 32; reasons.append(f"모멘텀B({score:.0f})")
    elif score >= 55:
        cs += 22; reasons.append(f"모멘텀C({score:.0f})")
    elif score >= 50:
        cs += 15; reasons.append(f"모멘텀D({score:.0f})")

    # 2) RSI 구간 (20점 만점) — 모멘텀 전략이므로 50~65도 허용
    if rsi <= 35:
        cs += 20; reasons.append(f"RSI과매도({rsi:.0f})")
    elif rsi <= 45:
        cs += 16; reasons.append(f"RSI저점({rsi:.0f})")
    elif rsi <= 55:
        cs += 12; reasons.append(f"RSI중립({rsi:.0f})")
    elif rsi <= 65:
        cs += 8; reasons.append(f"RSI적정({rsi:.0f})")
    elif rsi <= 75:
        cs += 4; reasons.append(f"RSI고점({rsi:.0f})")

    # 3) 볼린저밴드 위치 (15점 만점)
    if bb_pos <= 30:
        cs += 15; reasons.append(f"BB하단({bb_pos:.0f}%)")
    elif bb_pos <= 50:
        cs += 10; reasons.append(f"BB중간({bb_pos:.0f}%)")
    elif bb_pos <= 70:
        cs += 5

    # 4) 거래량 (15점 만점)
    if vol_ratio >= 2.0:
        cs += 15; reasons.append(f"거래량폭증({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.2:
        cs += 10; reasons.append(f"거래량증가({vol_ratio:.1f}x)")
    elif vol_ratio >= 0.8:
        cs += 6
    elif vol_ratio >= 0.5:
        cs += 3

    # 5) 신고가 근접도 (10점 만점)
    if near_high >= 95:
        cs += 10; reasons.append("신고가근접")
    elif near_high >= 90:
        cs += 7
    elif near_high >= 80:
        cs += 4

    if cs >= RULES["buy_composite_min"]:
        return {
            "action": "BUY",
            "confidence": min(95, cs),
            "reason": " + ".join(reasons),
        }

    top_reasons = reasons[:3] if reasons else ["조건미충족"]
    return {
        "action": "HOLD",
        "confidence": cs,
        "reason": f"복합스코어 {cs}/{RULES['buy_composite_min']}: {', '.join(top_reasons)}",
    }


def check_exit(symbol: str, position: dict, indicators: dict) -> Optional[str]:
    """보유 포지션 청산 조건 체크. 청산 사유 문자열 반환, 없으면 None."""
    entry_price = float(position.get("price", 0))
    highest = float(position.get("highest_price", 0) or entry_price)
    current_price = indicators.get("price", 0)
    if not entry_price or not current_price:
        return None

    pnl = (current_price - entry_price) / entry_price
    pnl_net = pnl - RISK["fee_rate"]

    # 손절
    if pnl_net <= RISK["stop_loss"]:
        return f"손절 ({pnl_net*100:.1f}%)"

    # 익절
    if pnl_net >= RISK["take_profit"]:
        return f"익절 ({pnl_net*100:.1f}%)"

    # 적응형 트레일링 스탑: 수익 구간별 차등
    if highest > 0 and pnl_net >= RISK["trailing_activate"]:
        # 수익이 클수록 트레일링 타이트하게
        if pnl_net >= 0.08:
            ts_pct = 0.015   # 8%+ 수익일 때 1.5% 트레일링
        elif pnl_net >= 0.05:
            ts_pct = 0.02    # 5%+ 수익일 때 2% 트레일링
        else:
            ts_pct = 0.025   # 기본 2.5% 트레일링

        drop = (highest - current_price) / highest
        if drop >= ts_pct:
            return f"트레일링 (고점 {highest:.2f} → {current_price:.2f}, -{drop*100:.1f}%)"

    # 타임컷
    created = position.get("created_at", "")
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            hold_days = (datetime.now(created_dt.tzinfo) - created_dt).days
            if hold_days >= RISK["timecut_days"]:
                return f"타임컷 ({hold_days}일 보유)"
        except Exception:
            pass

    rsi = indicators.get("rsi", 50)
    if rsi >= RULES["sell_rsi_min"] and pnl_net > 0:
        return f"RSI 과매수 ({rsi:.0f})"

    return None


def execute_buy(symbol: str, score: float, indicators: dict) -> dict:
    """매수 실행."""
    price = indicators.get("price", 0)
    if not price:
        return {"result": "NO_PRICE"}

    positions = get_open_positions()
    open_symbols = list(set(p.get("symbol") for p in positions))

    if symbol in open_symbols:
        return {"result": "ALREADY_HOLDING"}

    if len(open_symbols) >= RISK["max_positions"]:
        return {"result": "MAX_POSITIONS"}

    if count_today_buys() >= RISK["max_trades_per_day"]:
        return {"result": "MAX_DAILY_TRADES"}

    # 차등 포지션 사이징: 모멘텀 등급별
    if score >= 75:
        ratio = RISK["invest_ratio_A"]
    elif score >= 65:
        ratio = RISK["invest_ratio_B"]
    else:
        ratio = RISK["invest_ratio_C"]
    invest_usd = RISK["virtual_capital"] * ratio
    qty = invest_usd / price
    if qty < 0.01:
        return {"result": "INSUFFICIENT"}

    qty = round(qty, 4)

    log(f"🟢 {symbol} 매수: ${price:.2f} × {qty}주 ≈ ${invest_usd:.0f}", "TRADE")
    save_trade("BUY", symbol, qty, price, reason=f"모멘텀 {score:.0f}", score=score)

    send_telegram(
        f"🇺🇸🟢 <b>{symbol} 매수</b>\n"
        f"💰 ${price:.2f} × {qty}주\n"
        f"💵 투입: ${invest_usd:.0f}\n"
        f"📊 모멘텀: {score:.0f}\n"
        f"⚠️ 모의투자"
    )

    return {"result": "BUY", "symbol": symbol, "qty": qty, "price": price}


def execute_sell(symbol: str, position: dict, reason: str, indicators: dict) -> dict:
    """매도 실행."""
    price = indicators.get("price", 0)
    entry_price = float(position.get("price", 0))
    qty = float(position.get("quantity", 0))
    if not price or not entry_price:
        return {"result": "NO_PRICE"}

    pnl_pct = ((price - entry_price) / entry_price - RISK["fee_rate"]) * 100
    pnl_usd = (price - entry_price) * qty

    log(f"🔴 {symbol} 매도: ${price:.2f} × {qty}주 | {pnl_pct:+.2f}% (${pnl_usd:+.1f}) | {reason}", "TRADE")
    close_position(symbol, price, reason)

    send_telegram(
        f"🇺🇸🔴 <b>{symbol} 매도</b>\n"
        f"💰 ${price:.2f} × {qty}주\n"
        f"📊 수익: {pnl_pct:+.2f}% (${pnl_usd:+.1f})\n"
        f"📝 {reason}\n"
        f"⚠️ 모의투자"
    )

    return {"result": "SELL", "pnl_pct": pnl_pct, "reason": reason}


# ─────────────────────────────────────────────
# 손절/익절 체크 (보유 포지션 순회)
# ─────────────────────────────────────────────
def check_stop_loss_take_profit():
    """보유 포지션 전체 손절/익절/트레일링 체크."""
    positions = get_open_positions()
    if not positions:
        return

    log(f"보유 {len(positions)}개 포지션 체크 중...")
    for pos in positions:
        symbol = pos.get("symbol", "")
        if not symbol:
            continue

        indicators = get_us_indicators(symbol)
        if not indicators:
            continue

        current_price = indicators["price"]
        update_highest_price(symbol, current_price)

        exit_reason = check_exit(symbol, pos, indicators)
        if exit_reason:
            execute_sell(symbol, pos, exit_reason, indicators)
        else:
            entry = float(pos.get("price", 0))
            pnl = ((current_price - entry) / entry * 100) if entry else 0
            log(f"  {symbol}: ${current_price:.2f} ({pnl:+.2f}%) — HOLD")


# ─────────────────────────────────────────────
# 메인 사이클
# ─────────────────────────────────────────────
def run_trading_cycle():
    log("=" * 50)
    log("🇺🇸 US 자동매매 사이클 시작")

    if STOP_FLAG.exists():
        log("⛔ US_STOP_TRADING 플래그 감지 — 사이클 스킵")
        send_telegram("🇺🇸⛔ US 자동매매 중지 플래그 감지 — 이번 사이클 스킵")
        return

    # 보유 포지션 손절/익절 먼저
    check_stop_loss_take_profit()

    # 오늘 매수 한도 체크
    today_buys = count_today_buys()
    if today_buys >= RISK["max_trades_per_day"]:
        log(f"오늘 매수 한도 도달 ({today_buys}/{RISK['max_trades_per_day']}) — 신규 매수 스킵")
        log("US 매매 사이클 완료")
        return

    # 모멘텀 스캔 (상위 10% 대상으로 분석)
    log("모멘텀 스캔 중...")
    top_list = scan_today_top_us(universe=US_UNIVERSE, lookback_days=90, top_percent=10.0)
    if not top_list:
        log("상위 종목 없음 — 종료")
        return

    open_positions = get_open_positions()
    open_symbols = [p.get("symbol") for p in open_positions]

    # 종목별 분석 + 매수 판단
    for ms in top_list:
        symbol = ms.symbol
        score = ms.score

        if symbol in open_symbols:
            continue

        log(f"")
        log(f"  📊 {symbol} 분석 (스코어: {score:.1f})...")

        indicators = get_us_indicators(symbol)
        if not indicators:
            log(f"  {symbol}: 지표 없음 — 스킵", "WARN")
            continue

        log(f"  RSI: {indicators['rsi']} / BB: {indicators['bb_pos']:.0f}% / "
            f"Vol: {indicators['vol_ratio']:.2f}x / 60dHigh: {indicators['near_high']:.0f}%")

        signal = should_buy(symbol, score, indicators)
        log(f"  신호: {signal['action']} — {signal.get('reason', '')}")

        if signal["action"] == "BUY":
            result = execute_buy(symbol, score, indicators)
            log(f"  결과: {result['result']}")
            if result["result"] == "MAX_DAILY_TRADES":
                log("오늘 매수 한도 도달 — 스캔 종료")
                break

        time.sleep(0.5)

    log("🇺🇸 US 매매 사이클 완료")
    log("=" * 50)


# ─────────────────────────────────────────────
# 엔트리포인트
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        log("보유 포지션 손절/익절 체크")
        check_stop_loss_take_profit()
    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        positions = get_open_positions()
        if not positions:
            log("열린 포지션 없음")
        else:
            for p in positions:
                sym = p.get("symbol", "?")
                entry = float(p.get("price", 0))
                qty = float(p.get("quantity", 0))
                ind = get_us_indicators(sym)
                cur = ind["price"] if ind else 0
                pnl = ((cur - entry) / entry * 100) if entry and cur else 0
                log(f"  {sym}: {qty}주 × ${entry:.2f} → ${cur:.2f} ({pnl:+.2f}%)")
    else:
        run_trading_cycle()
