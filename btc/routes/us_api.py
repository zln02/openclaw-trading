"""US stock-related API endpoints."""
import time as _time
import asyncio
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.supabase_client import get_supabase
from common.config import US_TRADING_LOG
from common.logger import get_logger

log = get_logger("us_api")

supabase = get_supabase()
router = APIRouter()

_fx_cache = {"ts": 0, "rate": 0}


@router.get("/us", response_class=HTMLResponse)
async def us_page():
    from btc.templates.us_html import US_DASHBOARD_HTML
    return US_DASHBOARD_HTML


@router.get("/api/us/top", response_class=JSONResponse)
async def api_us_top():
    return _fetch_us_signals()


@router.get("/api/us/positions")
async def api_us_positions():
    try:
        if not supabase:
            return {"positions": [], "summary": {}}
        res = supabase.table("us_trade_executions").select("*").eq("result", "OPEN").execute()
        positions = res.data or []
        import yfinance as _yf_pos
        total_invested = 0
        total_current = 0
        for p in positions:
            sym = p.get("symbol", "")
            entry = float(p.get("price", 0))
            qty = float(p.get("quantity", 0))
            invested = entry * qty
            total_invested += invested
            try:
                t = _yf_pos.Ticker(sym)
                h = t.history(period="2d")
                if not h.empty:
                    cur = float(h["Close"].iloc[-1])
                    p["current_price"] = round(cur, 2)
                    p["pnl_pct"] = round((cur / entry - 1) * 100, 2) if entry else 0
                    p["pnl_usd"] = round((cur - entry) * qty, 2)
                    total_current += cur * qty
                else:
                    p["current_price"] = entry
                    p["pnl_pct"] = 0
                    p["pnl_usd"] = 0
                    total_current += invested
            except Exception:
                p["current_price"] = entry
                p["pnl_pct"] = 0
                p["pnl_usd"] = 0
                total_current += invested
        total_pnl_pct = round((total_current / total_invested - 1) * 100, 2) if total_invested > 0 else 0
        return {
            "positions": positions,
            "summary": {
                "total_invested": round(total_invested, 2),
                "total_current": round(total_current, 2),
                "total_pnl_pct": total_pnl_pct,
                "total_pnl_usd": round(total_current - total_invested, 2),
                "count": len(positions),
                "virtual_capital": 10000,
            },
        }
    except Exception as e:
        log.error(f"us positions: {e}")
        return {"positions": [], "summary": {}}


@router.get("/api/us/chart/{symbol}")
async def api_us_chart(symbol: str, period: str = Query("3mo")):
    try:
        import yfinance as _yf_chart
        t = _yf_chart.Ticker(symbol)
        h = t.history(period=period)
        if h is None or h.empty:
            return {"candles": [], "symbol": symbol}
        candles = []
        for ts, row in h.iterrows():
            candles.append({
                "time": ts.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return {"candles": candles, "symbol": symbol}
    except Exception as e:
        log.error(f"us chart: {e}")
        return {"candles": [], "symbol": symbol}


@router.get("/api/us/logs")
async def api_us_logs():
    try:
        if not US_TRADING_LOG.exists():
            return {"lines": ["아직 US 에이전트 로그가 없습니다."]}
        text = US_TRADING_LOG.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return {"lines": lines[-80:]}
    except Exception as e:
        return {"lines": [f"로그 읽기 실패: {e}"]}


@router.get("/api/us/trades")
async def api_us_trades():
    try:
        if not supabase:
            return []
        res = (
            supabase.table("us_trade_executions")
            .select("*")
            .order("id", desc=True)
            .limit(50)
            .execute()
        )
        return res.data or []
    except Exception as e:
        log.error(f"us trades: {e}")
        return []


@router.get("/api/us/market")
async def api_us_market():
    data = _get_us_market_summary()
    regime = _get_market_regime()
    return {"indices": data, "regime": regime}


@router.get("/api/us/realtime/news")
async def api_us_realtime_news(
    symbol: str = Query("BTC"),
    limit: int = Query(10, ge=1, le=50),
):
    """Phase 9: normalized news snapshot for US-side dashboard widgets."""
    try:
        from common.data import collect_news_once

        rows = await asyncio.to_thread(
            collect_news_once,
            symbol.upper(),
            int(limit),
        )
        return {"items": rows, "count": len(rows)}
    except Exception as e:
        log.error(f"us realtime news: {e}")
        return {"items": [], "count": 0}


@router.get("/api/us/realtime/price/{symbol}")
async def api_us_realtime_price(symbol: str):
    """Phase 9: realtime-like US price snapshot."""
    try:
        from common.data import get_price_snapshot

        return await asyncio.to_thread(get_price_snapshot, symbol, "us")
    except Exception as e:
        log.error(f"us realtime price: {e}")
        return {
            "symbol": symbol.upper(),
            "price": 0.0,
            "volume": 0.0,
            "source": "us",
        }


@router.get("/api/us/realtime/alt/{symbol}")
async def api_us_realtime_alt(symbol: str):
    """Phase 9: alternative-data snapshot for US symbol."""
    try:
        from common.data import get_alternative_data

        return await asyncio.to_thread(get_alternative_data, symbol)
    except Exception as e:
        log.error(f"us realtime alt: {e}")
        return {
            "symbol": symbol.upper(),
            "search_trend_7d": 0.0,
            "social_mentions_24h": 0,
            "sentiment_score": 0.0,
        }


def _get_market_regime() -> dict:
    """SPY 200MA + VIX 기반 마켓 레짐 — common 모듈 위임."""
    from common.market_data import get_market_regime
    return get_market_regime()


@router.get("/api/us/fx")
async def api_us_fx():
    if _time.time() - _fx_cache["ts"] < 300 and _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"]}
    try:
        import yfinance as _yf_fx
        t = _yf_fx.Ticker("USDKRW=X")
        h = t.history(period="5d")
        if h is not None and not h.empty:
            rate = round(float(h["Close"].iloc[-1]), 2)
            _fx_cache["ts"] = _time.time()
            _fx_cache["rate"] = rate
            return {"usdkrw": rate}
    except Exception as e:
        log.error(f"fx: {e}")
    if _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"]}
    return {"usdkrw": 1450}


# ── helpers ─────────────────────────────────────────────
def _fetch_us_signals() -> dict:
    if not supabase:
        return {"run_date": None, "items": []}
    try:
        res = (
            supabase.table("us_momentum_signals")
            .select("*")
            .order("run_date", desc=True)
            .order("score", desc=True)
            .limit(200)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"run_date": None, "items": []}
        latest_date = rows[0].get("run_date")
        items = [r for r in rows if r.get("run_date") == latest_date]
        return {"run_date": latest_date, "items": items}
    except Exception as e:
        log.error(f"us Supabase 조회 실패: {e}")
        return {"run_date": None, "items": []}


def _get_us_market_summary() -> list:
    cache_key = "_us_mkt_cache"
    cached = getattr(_get_us_market_summary, cache_key, None)
    if cached and _time.time() - cached.get("ts", 0) < 300:
        return cached.get("data", [])
    indices = [
        {"symbol": "^GSPC", "name": "S&P 500"},
        {"symbol": "^IXIC", "name": "NASDAQ"},
        {"symbol": "^DJI", "name": "Dow Jones"},
        {"symbol": "^VIX", "name": "VIX"},
    ]
    results = []
    try:
        import yfinance as _yf
        for idx in indices:
            try:
                t = _yf.Ticker(idx["symbol"])
                h = t.history(period="5d")
                if len(h) >= 2:
                    prev = float(h["Close"].iloc[-2])
                    last = float(h["Close"].iloc[-1])
                    chg = (last / prev - 1) * 100 if prev else 0
                    results.append({"name": idx["name"], "price": last, "change_pct": round(chg, 2)})
                elif len(h) == 1:
                    results.append({"name": idx["name"], "price": float(h["Close"].iloc[-1]), "change_pct": 0})
            except Exception:
                continue
    except Exception:
        pass
    setattr(_get_us_market_summary, cache_key, {"ts": _time.time(), "data": results})
    return results
