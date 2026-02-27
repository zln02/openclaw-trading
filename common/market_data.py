"""
공통 시장 데이터 모듈 — BTC 온체인/펀딩비, 공통 캐싱
"""
from __future__ import annotations

import time
import requests
from typing import Dict, Optional, Tuple
from functools import lru_cache

from common.cache import get_cached as _cached_get, set_cached as _set_cache_new
from common.retry import retry

CACHE_TTL = 300  # 5분


def _cached(key: str, ttl: int = CACHE_TTL):
    return _cached_get(key)


def _set_cache(key: str, val, ttl: int = CACHE_TTL):
    _set_cache_new(key, val, ttl=ttl)


# ── BTC 펀딩비 (Binance — 무료, 인증 불필요) ─────────
def get_btc_funding_rate() -> dict:
    """바이낸스 BTC 선물 펀딩비 조회. 양수=롱 과열, 음수=숏 과열."""
    cached = _cached("btc_funding")
    if cached:
        return cached
    try:
        @retry(max_attempts=2, base_delay=1.0)
        def _fetch():
            return requests.get(
                "https://fapi.binance.com/fapi/v1/fundingRate",
                params={"symbol": "BTCUSDT", "limit": 10},
                timeout=5,
            )
        res = _fetch()
        data = res.json()
        if not data:
            return {"rate": 0, "rates": [], "signal": "NEUTRAL"}

        rates = [float(d["fundingRate"]) for d in data]
        current = rates[-1]
        avg = sum(rates) / len(rates)

        if current > 0.001:
            signal = "LONG_CROWDED"
        elif current > 0.0005:
            signal = "SLIGHTLY_LONG"
        elif current < -0.001:
            signal = "SHORT_CROWDED"
        elif current < -0.0005:
            signal = "SLIGHTLY_SHORT"
        else:
            signal = "NEUTRAL"

        result = {
            "rate": round(current * 100, 4),
            "avg": round(avg * 100, 4),
            "rates": [round(r * 100, 4) for r in rates],
            "signal": signal,
        }
        _set_cache("btc_funding", result)
        return result
    except Exception as e:
        return {"rate": 0, "avg": 0, "rates": [], "signal": "NEUTRAL", "error": str(e)}


# ── BTC 오픈 인터레스트 (Binance) ────────────────────
def get_btc_open_interest() -> dict:
    """선물 미결제 약정량. 급증 시 변동성 확대 예고."""
    cached = _cached("btc_oi")
    if cached:
        return cached
    try:
        @retry(max_attempts=2, base_delay=1.0)
        def _fetch_oi():
            return requests.get(
                "https://fapi.binance.com/fapi/v1/openInterest",
                params={"symbol": "BTCUSDT"},
                timeout=5,
            )
        res = _fetch_oi()
        data = res.json()
        oi = float(data.get("openInterest", 0))

        @retry(max_attempts=2, base_delay=1.0)
        def _fetch_oi_hist():
            return requests.get(
                "https://fapi.binance.com/futures/data/openInterestHist",
                params={"symbol": "BTCUSDT", "period": "1h", "limit": 48},
                timeout=5,
            )
        hist = _fetch_oi_hist().json()

        oi_values = [float(h.get("sumOpenInterest", 0)) for h in hist] if hist else [oi]
        avg_oi = sum(oi_values) / len(oi_values) if oi_values else oi
        ratio = oi / avg_oi if avg_oi > 0 else 1.0

        if ratio > 1.15:
            signal = "OI_SURGE"
        elif ratio > 1.05:
            signal = "OI_HIGH"
        elif ratio < 0.85:
            signal = "OI_LOW"
        else:
            signal = "OI_NORMAL"

        result = {
            "oi_btc": round(oi, 2),
            "avg_48h": round(avg_oi, 2),
            "ratio": round(ratio, 3),
            "signal": signal,
        }
        _set_cache("btc_oi", result)
        return result
    except Exception:
        return {"oi_btc": 0, "ratio": 1.0, "signal": "OI_NORMAL"}


# ── BTC 롱/숏 비율 (Binance) ────────────────────────
def get_btc_long_short_ratio() -> dict:
    """글로벌 롱/숏 계좌 비율."""
    cached = _cached("btc_ls")
    if cached:
        return cached
    try:
        @retry(max_attempts=2, base_delay=1.0)
        def _fetch_ls():
            return requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": "BTCUSDT", "period": "1h", "limit": 24},
                timeout=5,
            )
        res = _fetch_ls()
        data = res.json()
        if not data:
            return {"long_ratio": 50, "short_ratio": 50, "signal": "NEUTRAL"}

        latest = data[-1]
        long_pct = float(latest.get("longAccount", 0.5)) * 100
        short_pct = float(latest.get("shortAccount", 0.5)) * 100

        ratios = [float(d.get("longShortRatio", 1.0)) for d in data]
        avg_ratio = sum(ratios) / len(ratios)
        current_ratio = ratios[-1]

        if current_ratio > 2.0:
            signal = "EXTREME_LONG"
        elif current_ratio > 1.5:
            signal = "LONG_BIAS"
        elif current_ratio < 0.7:
            signal = "EXTREME_SHORT"
        elif current_ratio < 0.85:
            signal = "SHORT_BIAS"
        else:
            signal = "NEUTRAL"

        result = {
            "long_ratio": round(long_pct, 1),
            "short_ratio": round(short_pct, 1),
            "ls_ratio": round(current_ratio, 3),
            "avg_24h": round(avg_ratio, 3),
            "signal": signal,
        }
        _set_cache("btc_ls", result)
        return result
    except Exception:
        return {"long_ratio": 50, "short_ratio": 50, "ls_ratio": 1.0, "signal": "NEUTRAL"}


# ── BTC 고래 지갑 추적 (blockchain.info — 무료) ──────
def get_btc_whale_activity() -> dict:
    """거래소 입출금량 기반 고래 활동 추정."""
    cached = _cached("btc_whale", ttl=600)
    if cached:
        return cached
    try:
        @retry(max_attempts=2, base_delay=2.0)
        def _fetch_blockchain(endpoint):
            return requests.get(f"https://blockchain.info/q/{endpoint}", timeout=5)

        res = _fetch_blockchain("totalbc")
        total_btc = float(res.text) / 1e8

        hash_rate = _fetch_blockchain("hashrate").text
        hash_rate_val = float(hash_rate) / 1e9  # GH/s → EH/s

        mempool = _fetch_blockchain("unconfirmedcount").text
        unconfirmed = int(mempool)

        if unconfirmed > 150000:
            signal = "HIGH_ACTIVITY"
        elif unconfirmed > 80000:
            signal = "MODERATE"
        else:
            signal = "LOW_ACTIVITY"

        result = {
            "total_btc_million": round(total_btc / 1e6, 2),
            "hash_rate_eh": round(hash_rate_val, 1),
            "unconfirmed_tx": unconfirmed,
            "signal": signal,
        }
        _set_cache("btc_whale", result)
        return result
    except Exception:
        return {"unconfirmed_tx": 0, "signal": "UNKNOWN"}


# ── BTC 청산 데이터 (CoinGlass 대안 — coinglass free API) ─
def get_btc_liquidations() -> dict:
    """최근 24시간 청산 데이터 추정 (바이낸스 기반)."""
    cached = _cached("btc_liq")
    if cached:
        return cached
    try:
        @retry(max_attempts=2, base_delay=1.0)
        def _fetch_liq():
            return requests.get(
                "https://fapi.binance.com/fapi/v1/ticker/24hr",
                params={"symbol": "BTCUSDT"},
                timeout=5,
            )
        res = _fetch_liq()
        data = res.json()
        vol_24h = float(data.get("quoteVolume", 0))
        price_change = float(data.get("priceChangePercent", 0))

        if abs(price_change) > 5 and vol_24h > 5e10:
            signal = "MASSIVE_LIQUIDATION"
        elif abs(price_change) > 3:
            signal = "MODERATE_LIQUIDATION"
        else:
            signal = "NORMAL"

        result = {
            "vol_24h_usd": round(vol_24h, 0),
            "price_change_24h": round(price_change, 2),
            "signal": signal,
        }
        _set_cache("btc_liq", result)
        return result
    except Exception:
        return {"vol_24h_usd": 0, "price_change_24h": 0, "signal": "NORMAL"}


# ── DART 재무 데이터 스코어링 (국내 주식용) ──────────
def get_dart_financial_score(stock_code: str, supabase_client) -> dict:
    """Supabase financial_statements에서 가져와 퀄리티 스코어 산출."""
    try:
        res = (
            supabase_client.table("financial_statements")
            .select("*")
            .eq("stock_code", stock_code)
            .order("fiscal_year", desc=True)
            .limit(3)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"score": 0, "grade": "N/A", "detail": "재무데이터 없음"}

        latest = rows[0]
        revenue = float(latest.get("revenue") or 0)
        op_income = float(latest.get("operating_income") or latest.get("operating_profit") or 0)
        net_income = float(latest.get("net_income") or 0)
        total_equity = float(latest.get("total_equity") or 0)
        total_assets = float(latest.get("total_assets") or 0)
        total_debt = float(
            latest.get("total_debt")
            or latest.get("total_liabilities")
            or 0
        )
        # total_equity가 자본금(capital stock)으로 저장된 경우 보정
        # 자본총계 = 총자산 - 총부채
        if total_assets > 0 and total_debt > 0:
            calc_equity = total_assets - total_debt
            if total_equity > 0 and calc_equity > total_equity * 5:
                total_equity = calc_equity
            elif total_equity == 0:
                total_equity = calc_equity

        if net_income == 0 and op_income > 0:
            net_income = op_income * 0.7

        score = 0
        details = []

        # 1) ROE (30점)
        roe = (net_income / total_equity * 100) if total_equity > 0 else 0
        if roe >= 20:
            score += 30; details.append(f"ROE우수({roe:.0f}%)")
        elif roe >= 12:
            score += 22; details.append(f"ROE양호({roe:.0f}%)")
        elif roe >= 7:
            score += 14; details.append(f"ROE보통({roe:.0f}%)")
        elif roe > 0:
            score += 5; details.append(f"ROE낮음({roe:.0f}%)")
        else:
            details.append(f"ROE적자({roe:.0f}%)")

        # 2) 영업이익률 (25점)
        op_margin = (op_income / revenue * 100) if revenue > 0 else 0
        if op_margin >= 20:
            score += 25; details.append(f"영익률↑({op_margin:.0f}%)")
        elif op_margin >= 10:
            score += 18; details.append(f"영익률○({op_margin:.0f}%)")
        elif op_margin >= 5:
            score += 10; details.append(f"영익률△({op_margin:.0f}%)")
        elif op_margin > 0:
            score += 3
        else:
            score -= 5; details.append(f"영업적자")

        # 3) 부채비율 (20점)
        debt_ratio = (total_debt / total_equity * 100) if total_equity > 0 else 999
        if debt_ratio < 50:
            score += 20; details.append(f"저부채({debt_ratio:.0f}%)")
        elif debt_ratio < 100:
            score += 14; details.append(f"부채양호({debt_ratio:.0f}%)")
        elif debt_ratio < 200:
            score += 7; details.append(f"부채보통({debt_ratio:.0f}%)")
        else:
            score -= 5; details.append(f"고부채({debt_ratio:.0f}%)")

        # 4) 매출 성장률 (25점) — 전년 대비
        if len(rows) >= 2:
            prev_revenue = float(rows[1].get("revenue") or 0)
            if prev_revenue > 0:
                growth = (revenue - prev_revenue) / prev_revenue * 100
                if growth >= 30:
                    score += 25; details.append(f"고성장({growth:.0f}%)")
                elif growth >= 15:
                    score += 18; details.append(f"성장({growth:.0f}%)")
                elif growth >= 5:
                    score += 10; details.append(f"완만({growth:.0f}%)")
                elif growth >= 0:
                    score += 3
                else:
                    score -= 3; details.append(f"역성장({growth:.0f}%)")

        score = max(0, min(100, score))
        if score >= 75:
            grade = "A"
        elif score >= 55:
            grade = "B"
        elif score >= 35:
            grade = "C"
        else:
            grade = "D"

        return {
            "score": score,
            "grade": grade,
            "roe": round(roe, 1),
            "op_margin": round(op_margin, 1),
            "debt_ratio": round(debt_ratio, 1),
            "detail": " | ".join(details),
            "fiscal_year": latest.get("fiscal_year", "?"),
        }
    except Exception as e:
        return {"score": 0, "grade": "N/A", "detail": str(e)}


# ── US 멀티팩터 스코어 (밸류 + 퀄리티 + 모멘텀) ────
def calc_us_multifactor(symbol: str) -> dict:
    """yfinance 기반 밸류/퀄리티/모멘텀 멀티팩터 스코어."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        hist = ticker.history(period="1y")
        if hist.empty or len(hist) < 60:
            return {"score": 0, "grade": "N/A"}

        score = 0
        details = []

        # Value (30점)
        pe = info.get("forwardPE") or info.get("trailingPE") or 0
        pb = info.get("priceToBook") or 0
        if 0 < pe <= 15:
            score += 20; details.append(f"PE저({pe:.0f})")
        elif pe <= 25:
            score += 12; details.append(f"PE보통({pe:.0f})")
        elif pe <= 40:
            score += 5
        elif pe > 40:
            score -= 3; details.append(f"PE고({pe:.0f})")

        if 0 < pb <= 3:
            score += 10; details.append(f"PB양호({pb:.1f})")
        elif pb <= 6:
            score += 5

        # Quality (35점)
        roe = info.get("returnOnEquity") or 0
        profit_margin = info.get("profitMargins") or 0
        debt_to_equity = info.get("debtToEquity") or 0

        if roe >= 0.25:
            score += 15; details.append(f"ROE우수({roe*100:.0f}%)")
        elif roe >= 0.15:
            score += 10; details.append(f"ROE양호({roe*100:.0f}%)")
        elif roe >= 0.08:
            score += 5
        elif roe < 0:
            score -= 5

        if profit_margin >= 0.20:
            score += 10; details.append(f"마진↑({profit_margin*100:.0f}%)")
        elif profit_margin >= 0.10:
            score += 7
        elif profit_margin >= 0.05:
            score += 3

        if 0 < debt_to_equity < 50:
            score += 10; details.append(f"저부채")
        elif debt_to_equity < 100:
            score += 5
        elif debt_to_equity > 200:
            score -= 5; details.append(f"고부채")

        # Momentum (35점)
        close = hist["Close"]
        ret_1m = float(close.iloc[-1] / close.iloc[-22] - 1) if len(close) >= 22 else 0
        ret_3m = float(close.iloc[-1] / close.iloc[-66] - 1) if len(close) >= 66 else 0
        ret_6m = float(close.iloc[-1] / close.iloc[-132] - 1) if len(close) >= 132 else 0

        combined_mom = ret_1m * 0.3 + ret_3m * 0.4 + ret_6m * 0.3
        if combined_mom >= 0.15:
            score += 25; details.append(f"모멘텀강")
        elif combined_mom >= 0.08:
            score += 18; details.append(f"모멘텀양호")
        elif combined_mom >= 0.02:
            score += 10
        elif combined_mom >= 0:
            score += 3
        else:
            score -= 5; details.append(f"모멘텀약")

        mom_accel = ret_1m - (ret_3m / 3)
        if mom_accel > 0.03:
            score += 10; details.append(f"가속↑")
        elif mom_accel > 0.01:
            score += 5

        score = max(0, min(100, score))
        grade = "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"

        return {
            "score": score,
            "grade": grade,
            "pe": round(pe, 1) if pe else None,
            "roe": round(roe * 100, 1) if roe else None,
            "profit_margin": round(profit_margin * 100, 1) if profit_margin else None,
            "ret_1m": round(ret_1m * 100, 1),
            "ret_3m": round(ret_3m * 100, 1),
            "mom_accel": round(mom_accel * 100, 1),
            "detail": " | ".join(details[:5]),
        }
    except Exception as e:
        return {"score": 0, "grade": "N/A", "detail": str(e)}


# ── US 마켓 레짐 (SPY 200MA + VIX) ──────────────────
def get_market_regime() -> dict:
    """SPY 200일/50일 이동평균 + VIX 기반 시장 레짐 판단.

    Returns dict with keys: regime, spy_price, spy_ma200, spy_ma50,
    spy_above_200ma, vix.
    Regimes: BULL, CORRECTION, RECOVERY, BEAR, UNKNOWN.
    """
    cached = _cached("us_market_regime")
    if cached:
        return cached
    try:
        import yfinance as yf

        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if spy_hist is None or len(spy_hist) < 200:
            return {"regime": "UNKNOWN", "spy_above_200ma": True, "vix": 20}

        close = spy_hist["Close"]
        ma200 = float(close.rolling(200).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        current = float(close.iloc[-1])
        above_200 = current > ma200
        above_50 = current > ma50

        vix_val = 20.0
        try:
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")
            if vix_hist is not None and not vix_hist.empty:
                vix_val = float(vix_hist["Close"].iloc[-1])
        except Exception:
            pass

        if above_200 and above_50:
            regime = "BULL"
        elif above_200 and not above_50:
            regime = "CORRECTION"
        elif not above_200 and above_50:
            regime = "RECOVERY"
        else:
            regime = "BEAR"

        result = {
            "regime": regime,
            "spy_price": round(current, 2),
            "spy_ma200": round(ma200, 2),
            "spy_ma50": round(ma50, 2),
            "spy_above_200ma": above_200,
            "vix": round(vix_val, 1),
        }
        _set_cache("us_market_regime", result, ttl=600)
        return result
    except Exception:
        return {"regime": "UNKNOWN", "spy_above_200ma": True, "vix": 20}


# ── US 어닝 캘린더 체크 ──────────────────────────────
def check_earnings_proximity(symbol: str, days: int = 5) -> dict:
    """향후 N일 내 어닝 발표 여부. 발표 직전은 매수 위험."""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        ticker = yf.Ticker(symbol)
        cal = ticker.calendar
        if cal is None:
            return {"near_earnings": False, "days_to_earnings": None}

        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        elif hasattr(cal, "iloc"):
            try:
                earnings_date = cal.iloc[0, 0] if cal.shape[0] > 0 else None
            except Exception:
                earnings_date = None
        else:
            earnings_date = None

        if earnings_date is None:
            return {"near_earnings": False, "days_to_earnings": None}

        if hasattr(earnings_date, "date"):
            ed = earnings_date.date()
        else:
            ed = earnings_date

        today = datetime.now().date()
        delta = (ed - today).days

        return {
            "near_earnings": 0 <= delta <= days,
            "days_to_earnings": delta,
            "earnings_date": str(ed),
        }
    except Exception:
        return {"near_earnings": False, "days_to_earnings": None}
