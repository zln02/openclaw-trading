#!/usr/bin/env python3
"""
미국 주식 자동매매 에이전트 v2.0 (Top-tier Quant)

v2 변경사항:
- [NEW] 멀티팩터 스코어 (모멘텀+밸류+퀄리티) — 기존 순수 모멘텀에서 확장
- [NEW] 어닝 캘린더 필터 — 발표 5일 전 매수 차단
- [NEW] 변동성 조절 포지션 사이징
- [NEW] 섹터 분산 (동일 섹터 max 2종목)
- [IMPROVE] 복합 스코어에 밸류/퀄리티 반영

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
from common.logger import get_logger
from common.retry import retry, retry_call
from common.config import US_TRADING_LOG

try:
    from common.sheets_logger import append_trade as _sheets_append
except ImportError:
    _sheets_append = None

load_env()
_log = get_logger("us_agent", US_TRADING_LOG)

sys.path.insert(0, str(Path(__file__).parent))
from us_momentum_backtest import scan_today_top_us, US_UNIVERSE, MomentumScore

supabase = get_supabase()

# ─────────────────────────────────────────────
# 리스크 설정 (미주용)
# ─────────────────────────────────────────────
RISK = {
    "stop_loss": -0.03,
    "take_profit": 0.06,
    "partial_tp_pct": 0.06,
    "partial_tp_ratio": 0.50,
    "trailing_stop": 0.02,
    "trailing_activate": 0.025,
    "trailing_adaptive": True,
    "max_positions": 5,
    "max_trades_per_day": 3,
    "min_score": 50,
    "min_order_usd": 50,
    "fee_rate": 0.001,
    "timecut_days": 12,
    "virtual_capital": 10000,
    "invest_ratio_A": 0.30,
    "invest_ratio_B": 0.20,
    "invest_ratio_C": 0.15,
    "market_regime_filter": True,
    "vix_max": 35,
    "relative_strength": True,
    "multifactor": True,          # 밸류+퀄리티 팩터 반영
    "earnings_filter": True,      # 어닝 5일 전 매수 차단
    "max_sector_positions": 2,    # 동일 섹터 최대 2종목
    "volatility_sizing": True,    # ATR 기반 포지션 사이징
    "dry_run": True,
}

RULES = {
    "buy_composite_min": 50,
    "buy_rsi_hard_max": 80,
    "buy_vol_hard_min": 0.3,
    "sell_rsi_min": 78,
    "momentum_accel_bonus": True,
}

US_TRADE_TABLE = "us_trade_executions"
STOP_FLAG = Path(__file__).parent / "US_STOP_TRADING"

# 레짐 가중치 사이클 캐시
_us_regime_adj_cache: Dict = {}


def get_us_risk_regime() -> str:
    """US 신규 진입 차단용 상위 레짐 분류."""
    try:
        result = RegimeClassifier().classify()
        return str(result.get("regime", "TRANSITION")).upper()
    except Exception as e:
        log(f"US 상위 레짐 조회 실패: {e}", "WARN")
        return "TRANSITION"


def _get_us_regime_adj() -> Dict:
    """레짐별 US 팩터 가중치 조정값 반환 (Phase 3-B)."""
    global _us_regime_adj_cache
    if _us_regime_adj_cache:
        return _us_regime_adj_cache
    defaults = {"momentum_mult": 1.0, "value_mult": 1.0, "quality_mult": 1.0, "regime": "UNKNOWN"}
    try:
        regime = get_us_risk_regime()
        _us_regime_adj_cache = {
            "RISK_ON":     {"momentum_mult": 1.25, "value_mult": 0.85, "quality_mult": 1.00},
            "TRANSITION":  {"momentum_mult": 1.00, "value_mult": 1.00, "quality_mult": 1.00},
            "RISK_OFF":    {"momentum_mult": 0.75, "value_mult": 1.25, "quality_mult": 1.25},
            "CRISIS":      {"momentum_mult": 0.50, "value_mult": 1.40, "quality_mult": 1.40},
        }.get(regime, defaults)
        _us_regime_adj_cache["regime"] = regime
        log(
            f"US 레짐 적응형 가중치: {regime} "
            f"(mom×{_us_regime_adj_cache['momentum_mult']} val×{_us_regime_adj_cache['value_mult']})"
        )
    except Exception as e:
        log(f"US 레짐 조회 실패 (기본값): {e}", "WARN")
        _us_regime_adj_cache = defaults
    return _us_regime_adj_cache


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    """Backward-compat wrapper routing to structured logger."""
    _dispatch = {
        "INFO": _log.info, "WARN": _log.warn,
        "ERROR": _log.error, "TRADE": _log.trade,
    }
    _dispatch.get(level, _log.info)(msg)


def send_telegram(msg: str):
    _tg_send(msg)


def is_us_market_open() -> bool:
    """미국장 대략 개장 여부 (한국 시간 기준 23:30~06:00, 서머타임 무시)."""
    now = datetime.now()
    h = now.hour
    return h >= 23 or h < 6


# ─────────────────────────────────────────────
# 시장 레짐 필터 (SPY 200MA + VIX) — common 모듈 위임
# ─────────────────────────────────────────────
from common.market_data import get_market_regime  # noqa: E402
from agents.regime_classifier import RegimeClassifier  # noqa: E402


def calc_relative_strength(symbol: str, days: int = 20) -> float:
    """종목의 SPY 대비 상대강도. 1.0 이상이면 아웃퍼폼."""
    try:
        data = yf.download([symbol, "SPY"], period=f"{days + 5}d", progress=False)
        if data.empty:
            return 1.0
        close = data["Close"]
        if symbol not in close.columns or "SPY" not in close.columns:
            return 1.0
        sym_ret = float(close[symbol].iloc[-1] / close[symbol].iloc[-days] - 1)
        spy_ret = float(close["SPY"].iloc[-1] / close["SPY"].iloc[-days] - 1)
        if spy_ret == 0:
            return 1.0
        return round(sym_ret / spy_ret if spy_ret > 0 else sym_ret - spy_ret + 1, 2)
    except Exception:
        return 1.0


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
    """매수 판단: 복합 스코어 + 마켓 레짐 + 상대강도 + 멀티팩터 + 어닝."""
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

    risk_regime = get_us_risk_regime()
    if risk_regime in {"RISK_OFF", "CRISIS"}:
        return {"action": "HOLD", "reason": f"{risk_regime} 레짐 — 신규 매수 차단"}

    # 마켓 레짐 필터
    if RISK.get("market_regime_filter"):
        regime = get_market_regime()
        if regime["regime"] == "BEAR":
            return {"action": "HOLD", "reason": f"BEAR 마켓 (SPY < 200MA, VIX: {regime['vix']})"}
        if regime.get("vix", 20) > RISK.get("vix_max", 35):
            return {"action": "HOLD", "reason": f"VIX 과열 ({regime['vix']:.0f} > {RISK['vix_max']})"}

    # v2: 어닝 캘린더 필터
    if RISK.get("earnings_filter"):
        try:
            from common.market_data import check_earnings_proximity
            earnings = check_earnings_proximity(symbol, days=5)
            if earnings.get("near_earnings"):
                days_to = earnings.get("days_to_earnings", "?")
                return {"action": "HOLD", "reason": f"어닝 {days_to}일 전 — 매수 차단"}
        except Exception:
            pass

    cs = 0
    reasons = []

    # 레짐 적응형 팩터 가중치 (Phase 3-B)
    _regime_adj = _get_us_regime_adj()
    _mom_mult = _regime_adj.get("momentum_mult", 1.0)
    _val_mult = _regime_adj.get("value_mult", 1.0)

    # 1) 모멘텀 등급 (35점 × 레짐 배수)
    if score >= 75:
        cs += round(35 * _mom_mult); reasons.append(f"모멘텀A({score:.0f})")
    elif score >= 65:
        cs += round(25 * _mom_mult); reasons.append(f"모멘텀B({score:.0f})")
    elif score >= 55:
        cs += round(18 * _mom_mult); reasons.append(f"모멘텀C({score:.0f})")
    elif score >= 50:
        cs += round(12 * _mom_mult); reasons.append(f"모멘텀D({score:.0f})")

    # 2) RSI 구간 (15점)
    if rsi <= 35:
        cs += 15; reasons.append(f"RSI과매도({rsi:.0f})")
    elif rsi <= 45:
        cs += 12; reasons.append(f"RSI저점({rsi:.0f})")
    elif rsi <= 55:
        cs += 8; reasons.append(f"RSI중립({rsi:.0f})")
    elif rsi <= 65:
        cs += 5; reasons.append(f"RSI적정({rsi:.0f})")
    elif rsi <= 75:
        cs += 2

    # 3) 볼린저밴드 (10점)
    if bb_pos <= 30:
        cs += 10; reasons.append(f"BB하단({bb_pos:.0f}%)")
    elif bb_pos <= 50:
        cs += 7; reasons.append(f"BB중간({bb_pos:.0f}%)")
    elif bb_pos <= 70:
        cs += 3

    # 4) 거래량 (10점)
    if vol_ratio >= 2.0:
        cs += 10; reasons.append(f"거래량폭증({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.2:
        cs += 7; reasons.append(f"거래량증가({vol_ratio:.1f}x)")
    elif vol_ratio >= 0.8:
        cs += 4
    elif vol_ratio >= 0.5:
        cs += 2

    # 5) 신고가 근접도 (8점)
    if near_high >= 95:
        cs += 8; reasons.append("신고가근접")
    elif near_high >= 90:
        cs += 5
    elif near_high >= 80:
        cs += 3

    # 6) 상대강도 (5점)
    if RISK.get("relative_strength"):
        rs = calc_relative_strength(symbol)
        if rs >= 1.5:
            cs += 5; reasons.append(f"RS강({rs:.1f}x)")
        elif rs >= 1.2:
            cs += 3; reasons.append(f"RS양호({rs:.1f}x)")
        elif rs < 0.8:
            cs -= 3

    # 7) 마켓 레짐 (3점)
    if RISK.get("market_regime_filter"):
        regime = get_market_regime()
        if regime["regime"] == "BULL":
            cs += 3
        elif regime["regime"] == "CORRECTION":
            cs -= 2

    # 8) v2: 멀티팩터 보너스 (밸류+퀄리티 — 15점 × 레짐 val 배수)
    if RISK.get("multifactor"):
        try:
            from common.market_data import calc_us_multifactor
            mf = calc_us_multifactor(symbol)
            mf_grade = mf.get("grade", "N/A")
            mf_score = mf.get("score", 0)
            if mf_grade == "A":
                cs += round(15 * _val_mult); reasons.append(f"팩터A({mf_score})")
            elif mf_grade == "B":
                cs += round(10 * _val_mult); reasons.append(f"팩터B({mf_score})")
            elif mf_grade == "C":
                cs += round(4 * _val_mult)
            elif mf_grade == "D":
                cs -= 5; reasons.append(f"팩터D({mf_score})")
        except Exception:
            pass

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

    # v2: 섹터 분산 체크
    max_sector = RISK.get("max_sector_positions", 2)
    try:
        ticker_info = yf.Ticker(symbol).info or {}
        sym_sector = ticker_info.get("sector", "")
        if sym_sector:
            sector_count = 0
            for os_sym in open_symbols:
                try:
                    os_info = yf.Ticker(os_sym).info or {}
                    if os_info.get("sector") == sym_sector:
                        sector_count += 1
                except Exception:
                    pass
            if sector_count >= max_sector:
                return {"result": "MAX_SECTOR", "sector": sym_sector}
    except Exception:
        pass

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

    # v2: ATR 기반 변동성 사이징
    if RISK.get("volatility_sizing"):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="30d")
            if hist is not None and len(hist) >= 14:
                close = hist["Close"]
                diffs = [abs(float(close.iloc[i] - close.iloc[i - 1])) for i in range(1, len(close))]
                atr = sum(diffs[-14:]) / min(len(diffs), 14)
                atr_pct = atr / price if price > 0 else 0.02
                if atr_pct > 0.04:
                    invest_usd *= 0.6
                    log(f"  {symbol}: 고변동성({atr_pct*100:.1f}%) — 40% 축소")
                elif atr_pct > 0.03:
                    invest_usd *= 0.8
                    log(f"  {symbol}: 중변동성({atr_pct*100:.1f}%) — 20% 축소")
        except Exception:
            pass

    qty = invest_usd / price
    if qty < 0.01:
        return {"result": "INSUFFICIENT"}

    qty = round(qty, 4)

    log(f"🟢 {symbol} 매수: ${price:.2f} × {qty}주 ≈ ${invest_usd:.0f}", "TRADE")

    # 팩터 스냅샷 수집 (Phase Level 4: 팩터 로깅)
    _factor_snapshot: str | None = None
    try:
        import sys as _sys
        _WORKSPACE_ROOT = str(Path(__file__).resolve().parents[1])
        if _WORKSPACE_ROOT not in _sys.path:
            _sys.path.insert(0, _WORKSPACE_ROOT)
        from quant.factors.registry import calc_all, FactorContext
        import json as _json
        from datetime import datetime as _dt
        _fctx = FactorContext()
        _today_iso = _dt.now().date().isoformat()
        _all_factors = calc_all(_today_iso, symbol=symbol, market='us', context=_fctx)
        _top5 = dict(
            sorted(_all_factors.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        )
        _factor_snapshot = _json.dumps(_top5, ensure_ascii=False)
        log(f"  {symbol} 팩터 스냅샷: {list(_top5.keys())}")
    except Exception as _fe:
        log(f"  {symbol} 팩터 스냅샷 건너뜀: {_fe}", "WARN")

    save_trade("BUY", symbol, qty, price, reason=f"모멘텀 {score:.0f}", score=score)

    # factor_snapshot 컬럼에 별도 저장 (graceful)
    if _factor_snapshot and supabase:
        try:
            supabase.table(US_TRADE_TABLE).update(
                {"factor_snapshot": _factor_snapshot}
            ).eq("symbol", symbol).eq("result", "OPEN").eq("trade_type", "BUY").execute()
        except Exception as _ue:
            log(f"  {symbol} 팩터 snapshot upsert 실패 (graceful): {_ue}", "WARN")

    send_telegram(
        f"🇺🇸🟢 <b>{symbol} 매수</b>\n"
        f"💰 ${price:.2f} × {qty}주\n"
        f"💵 투입: ${invest_usd:.0f}\n"
        f"📊 모멘텀: {score:.0f}\n"
        f"⚠️ 모의투자"
    )
    if _sheets_append:
        try:
            _sheets_append("us", "매수", symbol, price, qty, None, f"모멘텀 {score:.0f}")
        except Exception:
            pass

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
    if _sheets_append:
        try:
            action = "손절" if pnl_pct < -3 else "익절" if pnl_pct > 5 else "매도"
            _sheets_append("us", action, symbol, price, qty, pnl_pct, reason)
        except Exception:
            pass

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
    global _us_regime_adj_cache
    _us_regime_adj_cache = {}          # 사이클 시작 시 레짐 캐시 초기화 → _get_us_regime_adj() 재호출
    _get_us_regime_adj()               # 사이클 초기에 레짐 로드

    log("=" * 50)
    log("🇺🇸 US 자동매매 사이클 시작 (DRY-RUN)")

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

    # 시장 레짐 확인
    regime = get_market_regime()
    risk_regime = get_us_risk_regime()
    log(f"시장 레짐: {regime['regime']} | SPY: {regime.get('spy_price',0):.0f} (200MA: {regime.get('spy_ma200',0):.0f}) | VIX: {regime.get('vix',0):.1f}")
    log(f"상위 레짐: {risk_regime}")

    if regime["regime"] == "BEAR" and RISK.get("market_regime_filter"):
        log("🐻 BEAR 마켓 — 신규 매수 전면 차단")
        return
    if risk_regime in {"RISK_OFF", "CRISIS"}:
        log(f"⛔ {risk_regime} 레짐 — US 신규 매수 전면 차단")
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

        # v2: 멀티팩터 로깅
        if RISK.get("multifactor"):
            try:
                from common.market_data import calc_us_multifactor
                mf = calc_us_multifactor(symbol)
                if mf.get("grade") != "N/A":
                    log(f"  팩터: {mf['grade']}({mf['score']}) | {mf.get('detail', '')}")
            except Exception:
                pass

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
