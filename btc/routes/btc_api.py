"""BTC-related API endpoints."""
import os, time, json, requests, subprocess, asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
import psutil

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.supabase_client import get_supabase
from common.config import BTC_LOG, BRAIN_PATH, MEMORY_PATH
from common.logger import get_logger

log = get_logger("btc_api")

supabase = get_supabase()
router = APIRouter()

# ── caches ──────────────────────────────────────────────
_upbit_cache = {"time": 0, "krw": None, "ok": False}
_news_cache = {"data": [], "ts": 0}
_trend_cache = {"value": "SIDEWAYS", "time": 0}
NEWS_CACHE_TTL = 300


def _refresh_upbit_cache():
    global _upbit_cache
    if time.time() - _upbit_cache["time"] <= 60:
        return
    _upbit_cache["time"] = time.time()
    _upbit_cache["krw"] = None
    _upbit_cache["ok"] = False
    try:
        upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
        upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
        if upbit_key and upbit_secret:
            import pyupbit
            upbit = pyupbit.Upbit(upbit_key, upbit_secret)
            bal = upbit.get_balance("KRW")
            _upbit_cache["krw"] = float(bal) if bal is not None else None
            _upbit_cache["ok"] = True
    except Exception as e:
        log.error(f"upbit cache: {e}")


def _get_hourly_trend():
    global _trend_cache
    if time.time() - _trend_cache["time"] < 300:
        return _trend_cache["value"]
    try:
        import pyupbit
        df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=50)
        if df is None or df.empty:
            _trend_cache.update(value="SIDEWAYS", time=time.time())
            return "SIDEWAYS"
        from ta.trend import EMAIndicator
        close = df["close"]
        ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
        price = close.iloc[-1]
        if ema20 > ema50 and price > ema20:
            result = "UPTREND"
        elif ema20 < ema50 and price < ema20:
            result = "DOWNTREND"
        else:
            result = "SIDEWAYS"
        _trend_cache.update(value=result, time=time.time())
        return result
    except Exception as e:
        log.error(f"trend: {e}")
        _trend_cache.update(value="SIDEWAYS", time=time.time())
        return "SIDEWAYS"


def get_upbit_cache():
    """Allow other modules to access upbit cache."""
    _refresh_upbit_cache()
    return _upbit_cache


# ── BTC page ────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def index():
    from btc.templates.btc_html import BTC_HTML
    return BTC_HTML


def _compute_composite_sync():
    """Blocking composite computation — run via asyncio.to_thread."""
    import yfinance as _yf_c
    from ta.momentum import RSIIndicator as _RSI
    from ta.volatility import BollingerBands as _BB

    df = _yf_c.download("BTC-USD", period="90d", interval="1d", progress=False)
    if df.empty:
        return {"error": "데이터 없음"}
    close = df["Close"].squeeze()
    rsi_d = float(_RSI(close, window=14).rsi().iloc[-1])
    bb = _BB(close, window=20)
    bb_h, bb_l = float(bb.bollinger_hband().iloc[-1]), float(bb.bollinger_lband().iloc[-1])
    bb_pct = (float(close.iloc[-1]) - bb_l) / (bb_h - bb_l) * 100 if bb_h > bb_l else 50
    vol = df["Volume"].squeeze()
    vol_avg = float(vol.rolling(20).mean().iloc[-1])
    vol_ratio_d = float(vol.iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
    ret_7d = (float(close.iloc[-1]) / float(close.iloc[-8]) - 1) * 100 if len(close) > 8 else 0
    ret_30d = (float(close.iloc[-1]) / float(close.iloc[-31]) - 1) * 100 if len(close) > 31 else 0

    fg_val = 50
    try:
        fg_r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        fg_val = int(fg_r.json()["data"][0]["value"])
    except Exception:
        pass

    trend = _get_hourly_trend()

    from btc.btc_trading_agent import calc_btc_composite
    comp = calc_btc_composite(fg_val, rsi_d, bb_pct, vol_ratio_d, trend, ret_7d)

    pos = None
    if supabase:
        pr = supabase.table("btc_position").select("*").eq("status", "OPEN").order("entry_time", desc=True).limit(1).execute()
        pos = pr.data[0] if pr.data else None

    cur_price = float(close.iloc[-1])
    pos_pnl = None
    if pos:
        entry_p = float(pos.get("entry_price", 0))
        if entry_p > 0:
            pos_pnl = {"pnl_pct": round((cur_price * 1450 - entry_p) / entry_p * 100, 2),
                       "entry_price": entry_p, "quantity": pos.get("quantity", 0),
                       "entry_krw": pos.get("entry_krw", 0)}

    return {
        "composite": comp,
        "fg_value": fg_val, "rsi_d": round(rsi_d, 1), "bb_pct": round(bb_pct, 1),
        "vol_ratio_d": round(vol_ratio_d, 2), "trend": trend,
        "ret_7d": round(ret_7d, 1), "ret_30d": round(ret_30d, 1),
        "buy_threshold": 45,
        "position": pos_pnl,
    }


@router.get("/api/btc/composite")
async def api_btc_composite():
    try:
        return await asyncio.to_thread(_compute_composite_sync)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/btc/portfolio")
async def api_btc_portfolio():
    if not supabase:
        return {"error": "DB 미연결", "open_positions": [], "closed_positions": [], "summary": {}}
    try:
        open_rows = supabase.table("btc_position").select("*").eq("status", "OPEN").order("entry_time", desc=True).execute().data or []
        closed_rows = supabase.table("btc_position").select("*").eq("status", "CLOSED").order("exit_time", desc=True).limit(50).execute().data or []

        cur_price_krw = 0
        try:
            import pyupbit
            cur_price_krw = float(pyupbit.get_current_price("KRW-BTC") or 0)
        except Exception:
            pass
        if not cur_price_krw:
            try:
                import yfinance as _yf
                df = _yf.download("BTC-USD", period="1d", interval="1d", progress=False)
                if not df.empty:
                    cur_price_krw = float(df["Close"].iloc[-1]) * 1450
            except Exception:
                pass

        open_positions = []
        total_invested_open = 0
        total_eval_open = 0
        for p in open_rows:
            entry_price = float(p.get("entry_price") or 0)
            entry_krw = float(p.get("entry_krw") or 0)
            qty = float(p.get("quantity") or 0)
            eval_krw = cur_price_krw * qty if cur_price_krw and qty else entry_krw
            pnl_krw = eval_krw - entry_krw
            pnl_pct = (pnl_krw / entry_krw * 100) if entry_krw > 0 else 0
            total_invested_open += entry_krw
            total_eval_open += eval_krw
            open_positions.append({
                "id": p.get("id"),
                "entry_price": entry_price,
                "entry_krw": entry_krw,
                "quantity": qty,
                "entry_time": (p.get("entry_time") or "")[:19],
                "current_price_krw": round(cur_price_krw),
                "eval_krw": round(eval_krw),
                "pnl_krw": round(pnl_krw),
                "pnl_pct": round(pnl_pct, 2),
                "strategy": p.get("strategy") or "",
                "stop_loss": p.get("stop_loss"),
                "take_profit": p.get("take_profit"),
            })

        closed_positions = []
        total_realized_pnl = 0
        wins = 0
        losses = 0
        for p in closed_rows:
            pnl = float(p.get("pnl") or 0)
            entry_krw = float(p.get("entry_krw") or 0)
            pnl_pct = (pnl / entry_krw * 100) if entry_krw > 0 else 0
            total_realized_pnl += pnl
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            closed_positions.append({
                "id": p.get("id"),
                "entry_price": float(p.get("entry_price") or 0),
                "exit_price": float(p.get("exit_price") or 0),
                "entry_krw": entry_krw,
                "exit_krw": float(p.get("exit_krw") or 0),
                "quantity": float(p.get("quantity") or 0),
                "pnl": round(pnl),
                "pnl_pct": round(pnl_pct, 2),
                "entry_time": (p.get("entry_time") or "")[:19],
                "exit_time": (p.get("exit_time") or "")[:19],
                "strategy": p.get("strategy") or "",
                "exit_reason": p.get("exit_reason") or "",
            })

        _refresh_upbit_cache()
        krw_balance = _upbit_cache.get("krw", 0) or 0

        unrealized_pnl = total_eval_open - total_invested_open
        total_pnl = total_realized_pnl + unrealized_pnl
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        summary = {
            "krw_balance": krw_balance,
            "btc_price_krw": round(cur_price_krw),
            "open_count": len(open_positions),
            "closed_count": len(closed_rows),
            "total_invested": round(total_invested_open),
            "total_eval": round(total_eval_open),
            "unrealized_pnl": round(unrealized_pnl),
            "unrealized_pnl_pct": round((unrealized_pnl / total_invested_open * 100) if total_invested_open > 0 else 0, 2),
            "realized_pnl": round(total_realized_pnl),
            "total_pnl": round(total_pnl),
            "wins": wins,
            "losses": losses,
            "winrate": round(winrate, 1),
            "estimated_asset": round(krw_balance + total_eval_open),
        }

        return {
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "summary": summary,
        }
    except Exception as e:
        log.error(f"btc portfolio: {e}")
        return {"error": str(e), "open_positions": [], "closed_positions": [], "summary": {}}


@router.get("/api/summary")
async def api_summary():
    result = {}
    try:
        if supabase:
            btc_pos = supabase.table("btc_position").select("entry_price,entry_krw,quantity").eq("status", "OPEN").execute().data or []
            result["btc"] = {"positions": len(btc_pos), "invested_krw": sum(float(p.get("entry_krw", 0)) for p in btc_pos)}

            kr_open = supabase.table("trade_executions").select("trade_id").eq("result", "OPEN").execute().data or []
            result["kr"] = {"positions": len(kr_open)}

            us_open = supabase.table("us_trade_executions").select("symbol,price,quantity").eq("result", "OPEN").execute().data or []
            us_invested = sum(float(p.get("price", 0)) * float(p.get("quantity", 0)) for p in us_open)
            result["us"] = {"positions": len(us_open), "invested_usd": round(us_invested, 2),
                            "symbols": [p["symbol"] for p in us_open]}
    except Exception as e:
        result["error"] = str(e)
    return result


def _empty_stats():
    return {
        "last_price": 0, "last_signal": "HOLD", "last_time": "", "last_rsi": 50.0, "last_macd": 0.0,
        "total_pnl": 0, "total_pnl_pct": 0, "winrate": 0, "wins": 0, "losses": 0, "total_trades": 0,
        "buys": 0, "sells": 0, "avg_confidence": 0, "today_trades": 0, "today_pnl": 0,
        "position": None, "trend": "SIDEWAYS", "krw_balance": None,
    }


@router.get("/api/stats")
async def get_stats():
    if not supabase:
        return _empty_stats()
    try:
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(200).execute()
        trades = res.data or []

        buys = [t for t in trades if t.get("action") == "BUY"]
        sells = [t for t in trades if t.get("action") == "SELL"]
        closed = supabase.table("btc_position").select("*").eq("status", "CLOSED").execute().data or []

        wins = len([p for p in closed if (p.get("pnl") or 0) > 0])
        losses_cnt = len([p for p in closed if (p.get("pnl") or 0) < 0])
        total_pnl = sum(float(p.get("pnl") or 0) for p in closed)
        total_krw = sum(float(p.get("entry_krw") or 0) for p in closed)

        today = datetime.now().date().isoformat()
        today_closed = [p for p in closed if (p.get("exit_time") or "")[:10] == today]
        today_trades = len([t for t in trades if (t.get("timestamp") or "")[:10] == today])
        today_pnl = sum(float(p.get("pnl") or 0) for p in today_closed)

        pos_res = supabase.table("btc_position").select("*").eq("status", "OPEN").order("entry_time", desc=True).limit(1).execute()
        position = pos_res.data[0] if pos_res.data else None

        last = trades[0] if trades else {}

        _refresh_upbit_cache()
        krw_balance = _upbit_cache["krw"]

        trend = _get_hourly_trend()

        return {
            "last_price": last.get("price", 0),
            "last_signal": last.get("action", "HOLD"),
            "last_time": (last.get("timestamp", "") or "")[:19],
            "last_rsi": float(last.get("rsi") or 50),
            "last_macd": float(last.get("macd") or 0),
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / total_krw * 100) if total_krw else 0,
            "winrate": (wins / (wins + losses_cnt) * 100) if (wins + losses_cnt) else 0,
            "wins": wins,
            "losses": losses_cnt,
            "total_trades": len(trades),
            "buys": len(buys),
            "sells": len(sells),
            "avg_confidence": sum(float(t.get("confidence") or 0) for t in trades) / len(trades) if trades else 0,
            "today_trades": today_trades,
            "today_pnl": today_pnl,
            "position": position,
            "trend": trend,
            "krw_balance": krw_balance,
        }
    except Exception as e:
        log.error(f"stats: {e}")
        return {"error": str(e)}


@router.get("/api/trades")
async def get_trades():
    if not supabase:
        return []
    try:
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(100).execute()
        data = res.data or []
        for t in data:
            if t.get("timestamp"):
                t["timestamp"] = t["timestamp"][:19]
        return data
    except Exception as e:
        log.error(f"trades: {e}")
        return []


@router.get("/api/logs")
async def get_logs():
    try:
        if not BTC_LOG.exists():
            return {"lines": ["로그 파일 없음"]}
        raw = BTC_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
        lines = [
            l for l in raw[-80:]
            if not l.startswith("declare -x ") and "CRON" not in l[:20]
        ]
        return {"lines": lines}
    except Exception as e:
        log.error(f"logs: {e}")
        return {"lines": [f"로그 읽기 실패: {e}"]}


def _fetch_news_sync():
    import xml.etree.ElementTree as ET
    res = requests.get(
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        timeout=5,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    root = ET.fromstring(res.content)
    items = root.findall(".//item")[:8]
    return [
        {
            "title": item.findtext("title", ""),
            "url": item.findtext("link", ""),
            "time": (item.findtext("pubDate", "") or "")[:16],
            "source": "CoinDesk",
        }
        for item in items
    ]


@router.get("/api/news")
async def get_news():
    try:
        return await asyncio.to_thread(_fetch_news_sync)
    except Exception as e:
        log.error(f"news: {e}")
        return []


def _fetch_candles_sync(interval):
    import pyupbit
    df = pyupbit.get_ohlcv("KRW-BTC", interval=interval, count=100)
    if df is None or df.empty:
        return []
    result = []
    for ts, row in df.iterrows():
        result.append({
            "time": int(ts.timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return result


@router.get("/api/candles")
async def get_candles(interval: str = Query("minute5")):
    try:
        return await asyncio.to_thread(_fetch_candles_sync, interval)
    except Exception as e:
        log.error(f"candles: {e}")
        return []


@router.get("/api/system")
async def get_system():
    try:
        cpu = psutil.cpu_percent(interval=0)  # non-blocking; uses delta from last call
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        result = subprocess.run(
            ["bash", "-c", f"tail -200 {BTC_LOG} | grep '매매 사이클 시작'"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        last_cron = lines[-1][:50] if lines else "기록 없음"

        _refresh_upbit_cache()
        upbit_ok = _upbit_cache["ok"]

        return {
            "cpu": round(cpu, 1),
            "mem_used": round(mem.used / 1024**3, 1),
            "mem_total": round(mem.total / 1024**3, 1),
            "mem_pct": mem.percent,
            "disk_used": round(disk.used / 1024**3, 1),
            "disk_total": round(disk.total / 1024**3, 1),
            "disk_pct": disk.percent,
            "last_cron": last_cron,
            "upbit_ok": upbit_ok,
        }
    except Exception as e:
        log.error(f"system: {e}")
        return {"error": str(e)}


@router.get("/api/realtime/news")
async def get_realtime_news(
    currencies: str = Query("BTC"),
    limit: int = Query(10, ge=1, le=50),
):
    """Phase 9: normalized news snapshot.

    Output records:
    {headline, source, timestamp, symbols[], sentiment_raw, url, id}
    """
    try:
        from common.data import collect_news_once

        rows = await asyncio.to_thread(
            collect_news_once,
            currencies.upper(),
            int(limit),
        )
        return {"items": rows, "count": len(rows)}
    except Exception as e:
        log.error(f"realtime news: {e}")
        return {"items": [], "count": 0}


@router.get("/api/realtime/orderbook")
async def get_realtime_orderbook(
    market: str = Query("binance"),
    symbol: str = Query("BTCUSDT"),
):
    """Phase 9: orderbook snapshot endpoint.

    market=binance -> symbol like BTCUSDT
    market=upbit   -> symbol like KRW-BTC
    """
    try:
        from common.data import fetch_binance_orderbook, fetch_upbit_orderbook

        mk = market.lower().strip()
        if mk == "upbit":
            snap = await asyncio.to_thread(fetch_upbit_orderbook, symbol.upper())
        else:
            snap = await asyncio.to_thread(fetch_binance_orderbook, symbol.upper())
        return snap
    except Exception as e:
        log.error(f"realtime orderbook: {e}")
        return {
            "symbol": symbol,
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "source": market,
        }


@router.get("/api/realtime/alt/{symbol}")
async def get_realtime_alt_data(symbol: str):
    """Phase 9: alternative-data snapshot endpoint."""
    try:
        from common.data import get_alternative_data

        return await asyncio.to_thread(get_alternative_data, symbol)
    except Exception as e:
        log.error(f"realtime alt_data: {e}")
        return {
            "symbol": symbol.upper(),
            "search_trend_7d": 0.0,
            "social_mentions_24h": 0,
            "sentiment_score": 0.0,
        }


@router.get("/api/realtime/price/{symbol}")
async def get_realtime_price(symbol: str, market: str = Query("auto")):
    """Phase 9: realtime price snapshot endpoint."""
    try:
        from common.data import get_price_snapshot

        return await asyncio.to_thread(get_price_snapshot, symbol, market)
    except Exception as e:
        log.error(f"realtime price: {e}")
        return {
            "symbol": symbol,
            "price": 0.0,
            "volume": 0.0,
            "source": market,
        }


@router.get("/api/brain")
async def get_brain():
    try:
        summary_dir = BRAIN_PATH / "daily-summary"
        files = sorted(summary_dir.glob("*.md")) if summary_dir.exists() else []
        summary = files[-1].read_text(encoding="utf-8")[:500] if files else "요약 없음"

        todos_path = BRAIN_PATH / "todos.md"
        todos = todos_path.read_text(encoding="utf-8")[:300] if todos_path.exists() else "할일 없음"

        watch_path = BRAIN_PATH / "watchlist.md"
        watchlist = watch_path.read_text(encoding="utf-8")[:300] if watch_path.exists() else "없음"

        mem_dir = MEMORY_PATH
        mem_files = sorted(mem_dir.glob("*.md")) if mem_dir.exists() else []
        memory = mem_files[-1].read_text(encoding="utf-8")[:300] if mem_files else "기억 없음"

        return {
            "summary": summary,
            "todos": todos,
            "watchlist": watchlist,
            "memory": memory,
        }
    except Exception as e:
        log.error(f"brain: {e}")
        return {"error": str(e)}
