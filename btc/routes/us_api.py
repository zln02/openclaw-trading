"""US stock-related API endpoints."""
import time as _time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.supabase_client import get_supabase
from common.config import US_TRADING_LOG, US_FX_CACHE_TTL
from common.logger import get_logger

log = get_logger("us_api")

supabase = get_supabase()
router = APIRouter()

_fx_cache = {"ts": 0, "rate": 0}


def _batch_fetch_prices(symbols: list) -> dict:
    """여러 심볼의 현재가를 한 번에 조회 (N+1 방지)."""
    if not symbols:
        return {}
    try:
        import yfinance as yf
        data = yf.download(symbols, period="2d", progress=False, threads=True, auto_adjust=True)
        prices = {}
        close = data.get("Close") if hasattr(data, "get") else None
        if close is None:
            return {}
        if len(symbols) == 1:
            sym = symbols[0]
            if hasattr(close, "dropna") and len(close.dropna()) > 0:
                prices[sym] = float(close.dropna().iloc[-1])
        else:
            for sym in symbols:
                if sym in close.columns:
                    col = close[sym].dropna()
                    if len(col) > 0:
                        prices[sym] = float(col.iloc[-1])
        return prices
    except Exception as e:
        log.warning(f"yfinance 배치 조회 실패: {e}")
        return {}


# @router.get("/us", response_class=HTMLResponse)
# async def us_page():
#     from btc.templates.us_html import US_DASHBOARD_HTML
#     return US_DASHBOARD_HTML


@router.get("/api/us/composite")
async def get_us_composite():
    """US 종합 점수"""
    try:
        # 기본 점수 구조
        composite = {
            "total": 52,
            "spy": 50,
            "qqq": 48,
            "volume": 55,
            "trend": "NEUTRAL",
            "sentiment": 54
        }
        
        # 실제 데이터가 있다면 업데이트
        if supabase:
            try:
                # 최신 US 모멘텀 신호 조회
                res = supabase.table("us_momentum_signals").select("*").order("created_at", desc=True).limit(50).execute()
                if res.data:
                    scores = [item.get("score", 50) for item in res.data]
                    avg_score = sum(scores) / len(scores) if scores else 50
                    composite["total"] = int(avg_score)
            except Exception:
                pass
        
        return composite
    except Exception as e:
        log.error(f"US composite error: {e}")
        return {"total": 52, "spy": 50, "qqq": 48, "volume": 55, "trend": "NEUTRAL", "sentiment": 54}


@router.get("/api/us/portfolio")
async def get_us_portfolio():
    """US 포트폴리오 정보"""
    try:
        if not supabase:
            return {"open_positions": [], "closed_positions": [], "summary": {}}
        
        # US 오픈 포지션 조회
        open_res = supabase.table("us_trade_executions").select("*").eq("result", "OPEN").execute()
        open_positions = open_res.data or []
        
        # US 체결 내역 조회
        closed_res = supabase.table("us_trade_executions").select("*").eq("result", "CLOSED").order("created_at", desc=True).limit(100).execute()
        closed_positions = closed_res.data or []
        
        # 현재 가격 계산 (배치 조회로 N+1 방지)
        symbols = list({p.get("symbol", "") for p in open_positions if p.get("symbol")})
        batch_prices = await asyncio.to_thread(_batch_fetch_prices, symbols)
        total_invested = 0
        total_current = 0

        for p in open_positions:
            sym = p.get("symbol", "")
            entry = float(p.get("price", 0))
            qty = float(p.get("quantity", 0))
            invested = entry * qty
            total_invested += invested

            cur = batch_prices.get(sym, entry)
            p["current_price"] = round(cur, 2)
            p["pnl_pct"] = round((cur / entry - 1) * 100, 2) if entry else 0
            p["pnl_usd"] = round((cur - entry) * qty, 2)
            total_current += cur * qty
        
        total_pnl_pct = round((total_current / total_invested - 1) * 100, 2) if total_invested > 0 else 0
        
        summary = {
            "usd_balance": None,
            "open_count": len(open_positions),
            "closed_count": len(closed_positions),
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "unrealized_pnl": round(total_current - total_invested, 2),
            "unrealized_pnl_pct": total_pnl_pct,
            "realized_pnl": sum(p.get("pnl_usd", 0) for p in closed_positions)
        }
        
        return {
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "summary": summary
        }
    except Exception as e:
        log.error(f"US portfolio error: {e}")
        return {"open_positions": [], "closed_positions": [], "summary": {}}


@router.get("/api/us/system")
async def get_us_system():
    """US 시스템 상태"""
    try:
        import psutil
        import os
        alpaca_ok = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"))
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {
            "cpu": round(psutil.cpu_percent(interval=0), 1),
            "mem_used": round(mem.used / (1024**3), 1),
            "mem_total": round(mem.total / (1024**3), 1),
            "mem_pct": mem.percent,
            "disk_used": round(disk.used / (1024**3), 1),
            "disk_total": round(disk.total / (1024**3), 1),
            "disk_pct": disk.percent,
            "alpaca_ok": alpaca_ok,
            "last_cron": f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}][us_agent][INFO]",
        }
    except Exception as e:
        log.error(f"US system error: {e}")
        return {"cpu": 0, "mem_pct": 0, "disk_pct": 0, "alpaca_ok": False}


@router.get("/api/us/trades")
async def get_us_trades(
    limit: int = Query(default=50, le=500),
    result: str = Query(default=None, pattern="^(OPEN|CLOSED)$"),
    hours: int = Query(default=None, ge=1, le=168)
):
    """US 거래 내역 (필터링 지원)"""
    try:
        if not supabase:
            return []
        
        query = supabase.table("us_trade_executions").select("*")
        
        if result:
            query = query.eq("result", result)
        
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            query = query.gte("created_at", cutoff)

        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        log.error(f"US trades error: {e}")
        return []


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
        syms = list({p.get("symbol", "") for p in positions if p.get("symbol")})
        prices = await asyncio.to_thread(_batch_fetch_prices, syms)
        total_invested = 0
        total_current = 0
        for p in positions:
            sym = p.get("symbol", "")
            entry = float(p.get("price", 0))
            qty = float(p.get("quantity", 0))
            invested = entry * qty
            total_invested += invested
            cur = prices.get(sym, entry)
            p["current_price"] = round(cur, 2)
            p["pnl_pct"] = round((cur / entry - 1) * 100, 2) if entry else 0
            p["pnl_usd"] = round((cur - entry) * qty, 2)
            total_current += cur * qty
        total_pnl_pct = round((total_current / total_invested - 1) * 100, 2) if total_invested > 0 else 0
        return {
            "positions": positions,
            "summary": {
                "total_invested": round(total_invested, 2),
                "total_current": round(total_current, 2),
                "total_pnl_pct": total_pnl_pct,
                "total_pnl_usd": round(total_current - total_invested, 2),
                "count": len(positions),
            },
        }
    except Exception as e:
        log.error(f"us positions: {e}")
        return {"positions": [], "summary": {}}


@router.get("/api/us/chart/{symbol}")
async def api_us_chart(symbol: str, period: str = Query("3mo"), interval: str = Query("1d")):
    try:
        import yfinance as _yf_chart
        t = _yf_chart.Ticker(symbol)
        h = t.history(period=period, interval=interval)
        if h is None or h.empty:
            return {"candles": [], "symbol": symbol}
        intraday = interval not in ("1d", "1wk", "1mo")
        candles = []
        for ts, row in h.iterrows():
            candles.append({
                "time": ts.strftime("%Y-%m-%dT%H:%M") if intraday else ts.strftime("%Y-%m-%d"),
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


@router.get("/api/us/market")
async def api_us_market():
    try:
        data = await asyncio.to_thread(_get_us_market_summary)
        regime = _get_market_regime()
        top_payload = _fetch_us_signals()
        flat = {
            "sp500": 0.0,
            "sp500_change_pct": 0.0,
            "nasdaq": 0.0,
            "nasdaq_change_pct": 0.0,
            "dji": 0.0,
            "dji_change_pct": 0.0,
            "vix": 0.0,
            "vix_change_pct": 0.0,
        }
        for item in data:
            name = item.get("name")
            if name == "S&P 500":
                flat["sp500"] = item.get("price", 0.0)
                flat["sp500_change_pct"] = item.get("change_pct", 0.0)
            elif name == "NASDAQ":
                flat["nasdaq"] = item.get("price", 0.0)
                flat["nasdaq_change_pct"] = item.get("change_pct", 0.0)
            elif name == "Dow Jones":
                flat["dji"] = item.get("price", 0.0)
                flat["dji_change_pct"] = item.get("change_pct", 0.0)
            elif name == "VIX":
                flat["vix"] = item.get("price", 0.0)
                flat["vix_change_pct"] = item.get("change_pct", 0.0)
        return {
            "indices": data,
            "regime": regime,
            "top": top_payload.get("items", []),
            "momentum": top_payload.get("items", []),
            **flat,
        }
    except Exception as e:
        log.error(f"us market: {e}")
        return {
            "indices": [],
            "regime": {"regime": "UNKNOWN", "vix": 0.0, "spy_above_200ma": False},
            "top": [],
            "momentum": [],
            "sp500": 0.0,
            "sp500_change_pct": 0.0,
            "nasdaq": 0.0,
            "nasdaq_change_pct": 0.0,
            "dji": 0.0,
            "dji_change_pct": 0.0,
            "vix": 0.0,
            "vix_change_pct": 0.0,
        }


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
    if _time.time() - _fx_cache["ts"] < US_FX_CACHE_TTL and _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"], "rate": _fx_cache["rate"], "change_pct": 0.0}
    try:
        import yfinance as _yf_fx
        t = _yf_fx.Ticker("USDKRW=X")
        h = t.history(period="5d")
        if h is not None and not h.empty:
            rate = round(float(h["Close"].iloc[-1]), 2)
            change_pct = 0.0
            if len(h) >= 2 and float(h["Close"].iloc[-2]) != 0:
                change_pct = round((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2]) * 100, 2)
            _fx_cache["ts"] = _time.time()
            _fx_cache["rate"] = rate
            return {"usdkrw": rate, "rate": rate, "change_pct": change_pct}
    except Exception as e:
        log.error(f"fx: {e}")
    if _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"], "rate": _fx_cache["rate"], "change_pct": 0.0}
    return {"usdkrw": 1450, "rate": 1450, "change_pct": 0.0}


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
