#!/usr/bin/env python3
"""
BTC 자동매매 대시보드 — 업비트 스타일 프로 버전
포트: 8080
"""

import os, json, subprocess, requests, time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import psutil
import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.supabase_client import get_supabase

load_env()

_sys.path.insert(0, str(Path(__file__).parent))
from templates.btc_html import BTC_HTML as HTML
from templates.stocks_html import STOCKS_HTML
from templates.us_html import US_DASHBOARD_HTML

supabase = get_supabase()

# Upbit API 60s cache
_upbit_cache = {"time": 0, "krw": None, "ok": False}

_news_cache = {"data": [], "ts": 0}
NEWS_CACHE_TTL = 300

_trend_cache = {"value": "SIDEWAYS", "time": 0}


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
        print(f"[ERROR] {e}")


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
        print(f"[ERROR] {e}")
        _trend_cache.update(value="SIDEWAYS", time=time.time())
        return "SIDEWAYS"

app = FastAPI()

WORKSPACE = "/home/wlsdud5035/.openclaw/workspace"
LOG_PATH = "/home/wlsdud5035/.openclaw/logs/btc_trading.log"
BRAIN_PATH = f"{WORKSPACE}/brain"
MEMORY_PATH = f"{WORKSPACE}/memory"

_kiwoom_client = None

def _get_kiwoom():
    """지연 초기화된 KiwoomClient 반환 (환경 미설정 시 None)."""
    global _kiwoom_client
    if _kiwoom_client is None:
        try:
            import sys
            if WORKSPACE not in sys.path:
                sys.path.insert(0, WORKSPACE)
            from stocks.kiwoom_client import KiwoomClient
            _kiwoom_client = KiwoomClient()
        except Exception as e:
            print(f"[WARN] Kiwoom init: {e}")
    return _kiwoom_client


def is_market_open_now() -> bool:
    """한국 주식장 (정규장) 개장 여부."""
    now = datetime.now()
    if now.weekday() >= 5:  # 토/일
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


# HTML templates loaded from btc/templates/


@app.get("/stocks", response_class=HTMLResponse)
async def stocks_page():
    return STOCKS_HTML

@app.get("/us", response_class=HTMLResponse)
async def us_page():
    return US_DASHBOARD_HTML

@app.get("/api/us/top", response_class=JSONResponse)
async def api_us_top():
    return _fetch_us_signals()


@app.get("/api/us/positions")
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
        print(f"[ERROR] us positions: {e}")
        return {"positions": [], "summary": {}}


@app.get("/api/us/chart/{symbol}")
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
        print(f"[ERROR] us chart: {e}")
        return {"candles": [], "symbol": symbol}


@app.get("/api/us/logs")
async def api_us_logs():
    try:
        log_path = Path("/home/wlsdud5035/.openclaw/logs/us_trading.log")
        if not log_path.exists():
            return {"lines": ["아직 US 에이전트 로그가 없습니다."]}
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return {"lines": lines[-80:]}
    except Exception as e:
        return {"lines": [f"로그 읽기 실패: {e}"]}


@app.get("/api/us/trades")
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
        print(f"[ERROR] us trades: {e}")
        return []


@app.get("/api/us/market")
async def api_us_market():
    return _get_us_market_summary()


_fx_cache = {"ts": 0, "rate": 0}


@app.get("/api/us/fx")
async def api_us_fx():
    """USD/KRW 환율 (yfinance, 5분 캐시)."""
    import time as _t
    if _t.time() - _fx_cache["ts"] < 300 and _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"]}
    try:
        import yfinance as _yf_fx
        t = _yf_fx.Ticker("USDKRW=X")
        h = t.history(period="5d")
        if h is not None and not h.empty:
            rate = round(float(h["Close"].iloc[-1]), 2)
            _fx_cache["ts"] = _t.time()
            _fx_cache["rate"] = rate
            return {"usdkrw": rate}
    except Exception as e:
        print(f"[ERROR] fx: {e}")
    if _fx_cache["rate"] > 0:
        return {"usdkrw": _fx_cache["rate"]}
    return {"usdkrw": 1450}

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML

def _empty_stats():
    return {
        "last_price": 0, "last_signal": "HOLD", "last_time": "", "last_rsi": 50.0, "last_macd": 0.0,
        "total_pnl": 0, "total_pnl_pct": 0, "winrate": 0, "wins": 0, "losses": 0, "total_trades": 0,
        "buys": 0, "sells": 0, "avg_confidence": 0, "today_trades": 0, "today_pnl": 0,         "position": None, "trend": "SIDEWAYS",
        "krw_balance": None,
    }

@app.get("/api/stats")
async def get_stats():
    if not supabase:
        return _empty_stats()
    try:
        # 전체 거래 통계
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(200).execute()
        trades = res.data or []

        buys   = [t for t in trades if t.get("action") == "BUY"]
        sells  = [t for t in trades if t.get("action") == "SELL"]
        closed = supabase.table("btc_position").select("*").eq("status","CLOSED").execute().data or []

        wins   = len([p for p in closed if (p.get("pnl") or 0) > 0])
        losses = len([p for p in closed if (p.get("pnl") or 0) < 0])
        total_pnl = sum(float(p.get("pnl") or 0) for p in closed)
        total_krw = sum(float(p.get("entry_krw") or 0) for p in closed)

        # 오늘 통계
        today = datetime.now().date().isoformat()
        today_closed = [p for p in closed if (p.get("exit_time") or "")[:10] == today]
        today_trades = len([t for t in trades if (t.get("timestamp") or "")[:10] == today])
        today_pnl = sum(float(p.get("pnl") or 0) for p in today_closed)

        # 포지션
        pos_res = supabase.table("btc_position").select("*").eq("status","OPEN").order("entry_time",desc=True).limit(1).execute()
        position = pos_res.data[0] if pos_res.data else None

        last = trades[0] if trades else {}

        # KRW 잔고: 60초 캐시
        _refresh_upbit_cache()
        krw_balance = _upbit_cache["krw"]

        # 1시간봉 추세 (실패 시 SIDEWAYS)
        trend = _get_hourly_trend()

        return {
            "last_price":     last.get("price", 0),
            "last_signal":    last.get("action", "HOLD"),
            "last_time":      (last.get("timestamp", "") or "")[:19],
            "last_rsi":       float(last.get("rsi") or 50),
            "last_macd":      float(last.get("macd") or 0),
            "total_pnl":      total_pnl,
            "total_pnl_pct":  (total_pnl / total_krw * 100) if total_krw else 0,
            "winrate":        (wins / (wins + losses) * 100) if (wins + losses) else 0,
            "wins":           wins,
            "losses":         losses,
            "total_trades":   len(trades),
            "buys":           len(buys),
            "sells":          len(sells),
            "avg_confidence": sum(float(t.get("confidence") or 0) for t in trades) / len(trades) if trades else 0,
            "today_trades":   today_trades,
            "today_pnl":      today_pnl,
            "position":       position,
            "trend":          trend,
            "krw_balance":    krw_balance,
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}

@app.get("/api/trades")
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
        print(f"[ERROR] {e}")
        return []


@app.get("/api/logs")
async def get_logs():
    try:
        result = subprocess.run(
            ["tail", "-50", LOG_PATH],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        return {"lines": lines}
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"lines": [f"로그 읽기 실패: {e}"]}


@app.get("/api/news")
async def get_news():
    try:
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
                "title":  item.findtext("title", ""),
                "url":    item.findtext("link", ""),
                "time":   (item.findtext("pubDate", "") or "")[:16],
                "source": "CoinDesk",
            }
            for item in items
        ]
    except Exception as e:
        print(f"[ERROR] news: {e}")
        return []


@app.get("/api/candles")
async def get_candles(interval: str = Query("minute5")):
    try:
        import pyupbit
        df = pyupbit.get_ohlcv("KRW-BTC", interval=interval, count=100)
        if df is None or df.empty:
            return []
        result = []
        for ts, row in df.iterrows():
            result.append({
                "time":  int(ts.timestamp()),
                "open":  float(row["open"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return result
    except Exception as e:
        print(f"[ERROR] candles: {e}")
        return []


@app.get("/api/system")
async def get_system():
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        result = subprocess.run(
            ["bash", "-c", f"tail -200 {LOG_PATH} | grep '매매 사이클 시작'"],
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
        print(f"[ERROR] {e}")
        return {"error": str(e)}


@app.get("/api/brain")
async def get_brain():
    try:
        summary_dir = Path(f"{BRAIN_PATH}/daily-summary")
        files = sorted(summary_dir.glob("*.md")) if summary_dir.exists() else []
        summary = files[-1].read_text(encoding="utf-8")[:500] if files else "요약 없음"

        todos_path = Path(f"{BRAIN_PATH}/todos.md")
        todos = todos_path.read_text(encoding="utf-8")[:300] if todos_path.exists() else "할일 없음"

        watch_path = Path(f"{BRAIN_PATH}/watchlist.md")
        watchlist = watch_path.read_text(encoding="utf-8")[:300] if watch_path.exists() else "없음"

        mem_dir = Path(MEMORY_PATH)
        mem_files = sorted(mem_dir.glob("*.md")) if mem_dir.exists() else []
        memory = mem_files[-1].read_text(encoding="utf-8")[:300] if mem_files else "기억 없음"

        return {
            "summary": summary,
            "todos": todos,
            "watchlist": watchlist,
            "memory": memory,
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}


@app.get("/api/stocks/overview")
async def get_stocks_overview():
    if not supabase:
        return []
    try:
        stocks = supabase.table("top50_stocks").select("*").execute().data or []
        result = []
        for s in stocks:
            try:
                ohlcv = supabase.table("daily_ohlcv").select("*").eq("stock_code", s["stock_code"]).order("date", desc=True).limit(2).execute().data or []
                price = ohlcv[0]["close_price"] if ohlcv else 0
                prev = ohlcv[1]["close_price"] if len(ohlcv) > 1 else price
                change = ((price - prev) / prev * 100) if prev else 0
                result.append({
                    "code": s["stock_code"],
                    "name": s["stock_name"],
                    "industry": s.get("industry", ""),
                    "price": price,
                    "change": round(change, 2),
                    "volume": ohlcv[0]["volume"] if ohlcv else 0,
                })
            except Exception:
                pass
        return sorted(result, key=lambda x: abs(x["change"]), reverse=True)
    except Exception as e:
        print(f"[ERROR] stocks overview: {e}")
        return []


@app.get("/api/stocks/chart/{code}")
async def get_stock_chart(code: str, interval: str = Query("1d")):
    if not supabase:
        return {"candles": [], "name": "", "code": code}
    try:
        # 분봉: intraday_ohlcv (5m/1h). 10m 요청 시 5m 데이터 사용
        if interval in ("5m", "10m", "1h"):
            db_interval = "5m" if interval == "10m" else interval
            rows = (
                supabase.table("intraday_ohlcv")
                .select("*")
                .eq("stock_code", code)
                .eq("time_interval", db_interval)
                .order("datetime", desc=False)
                .limit(200)
                .execute()
                .data
                or []
            )
            if not rows:
                return {"candles": [], "name": _stock_name(code), "code": code}
            candles = []
            for r in rows:
                dt = (r.get("datetime") or "")[:16]  # YYYY-MM-DDTHH:MM (lightweight-charts)
                if len(dt) < 16:
                    dt = (r.get("datetime") or "").replace("Z", "")[:19]
                candles.append({
                    "time": dt,
                    "open": r["open_price"],
                    "high": r["high_price"],
                    "low": r["low_price"],
                    "close": r["close_price"],
                    "volume": r.get("volume") or 0,
                })
            return {"candles": candles, "name": _stock_name(code), "code": code}

        # 일봉: daily_ohlcv
        rows = supabase.table("daily_ohlcv").select("*").eq("stock_code", code).order("date", desc=False).limit(30).execute().data or []
        if not rows:
            return {"candles": [], "name": _stock_name(code), "code": code}
        closes = [float(r["close_price"]) for r in rows]

        # BB(20)
        bb_data = []
        for i in range(len(closes)):
            if i < 19:
                bb_data.append({"upper": None, "middle": None, "lower": None})
            else:
                window = closes[i - 19 : i + 1]
                ma = sum(window) / 20
                std = (sum((c - ma) ** 2 for c in window) / 20) ** 0.5
                bb_data.append({
                    "upper": round(ma + 2 * std, 0),
                    "middle": round(ma, 0),
                    "lower": round(ma - 2 * std, 0),
                })

        # RSI(14)
        rsi_data = []
        for i in range(len(closes)):
            if i < 14:
                rsi_data.append(None)
            else:
                gains, losses = [], []
                for j in range(i - 13, i + 1):
                    diff = closes[j] - closes[j - 1]
                    gains.append(max(diff, 0))
                    losses.append(max(-diff, 0))
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss == 0:
                    rsi_data.append(100)
                else:
                    rs = avg_gain / avg_loss
                    rsi_data.append(round(100 - (100 / (1 + rs)), 1))

        candles = []
        for i, r in enumerate(rows):
            c = {
                "time": r["date"],
                "open": r["open_price"],
                "high": r["high_price"],
                "low": r["low_price"],
                "close": r["close_price"],
                "volume": r.get("volume") or 0,
            }
            if i < len(bb_data):
                c["bb_upper"] = bb_data[i]["upper"]
                c["bb_middle"] = bb_data[i]["middle"]
                c["bb_lower"] = bb_data[i]["lower"]
            else:
                c["bb_upper"] = c["bb_middle"] = c["bb_lower"] = None
            c["rsi"] = rsi_data[i] if i < len(rsi_data) else None
            candles.append(c)

        return {"candles": candles, "name": _stock_name(code), "code": code}
    except Exception as e:
        print(f"[ERROR] stock chart: {e}")
        return {"candles": [], "name": "", "code": code}


def _stock_name(code: str) -> str:
    if not supabase:
        return ""
    try:
        r = supabase.table("top50_stocks").select("stock_name").eq("stock_code", code).limit(1).execute().data or []
        return r[0].get("stock_name", "") if r else ""
    except Exception:
        return ""


@app.get("/api/stocks/indicators/{code}")
async def get_stock_indicators(code: str):
    """종목별 기술적 지표 반환 (RSI, MACD, BB, vol_ratio)"""
    if not supabase:
        return {"error": "Supabase 미연결"}
    try:
        rows = (
            supabase.table("daily_ohlcv")
            .select("close_price,volume,date")
            .eq("stock_code", code)
            .order("date", desc=False)
            .limit(30)
            .execute()
            .data or []
        )
        if len(rows) < 14:
            return {"error": "데이터 부족"}

        closes = [float(r["close_price"]) for r in rows]
        volumes = [float(r.get("volume") or 0) for r in rows]

        # RSI(14)
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        # MACD(12,26)
        def ema(data, period):
            k = 2 / (period + 1)
            e = data[0]
            for d in data[1:]:
                e = d * k + e * (1 - k)
            return e

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd = round(ema12 - ema26, 0)

        # BB(20)
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        std20 = (sum((c - ma20) ** 2 for c in closes[-20:]) / 20) ** 0.5 if len(closes) >= 20 else 0
        bb_upper = round(ma20 + 2 * std20, 0)
        bb_lower = round(ma20 - 2 * std20, 0)
        bb_pos = round((closes[-1] - bb_lower) / (bb_upper - bb_lower) * 100, 1) if (bb_upper - bb_lower) > 0 else 50

        # 거래량 비율
        avg_vol = sum(volumes[-20:]) / min(len(volumes[-20:]), 20)
        vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

        return {
            "rsi": rsi,
            "macd": macd,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_pos": bb_pos,
            "vol_ratio": vol_ratio,
            "ma20": round(ma20, 0),
        }
    except Exception as e:
        print(f"[ERROR] stock indicators: {e}")
        return {"error": str(e)}


@app.get("/api/stocks/portfolio")
async def get_stocks_portfolio():
    """키움 계좌 평가 + Supabase OPEN 포지션 통합"""
    try:
        kiwoom = _get_kiwoom()
        if not kiwoom:
            return {"error": "키움 연동 없음", "positions": [], "deposit": 0, "total_evaluation": 0, "estimated_asset": 0}
        account = kiwoom.get_account_evaluation()
        summary = account.get("summary", {})
        holdings = account.get("holdings", [])

        positions = []
        market_open = is_market_open_now()
        if supabase:
            try:
                rows = (
                    supabase.table("trade_executions")
                    .select("*")
                    .eq("result", "OPEN")
                    .execute()
                    .data or []
                )
                from collections import defaultdict
                by_code = defaultdict(list)
                for p in rows:
                    by_code[p["stock_code"]].append(p)
                for code, trades in by_code.items():
                    total_qty = sum(int(t.get("quantity") or 0) for t in trades)
                    total_cost = sum(float(t.get("price") or 0) * int(t.get("quantity") or 0) for t in trades)
                    avg_entry = total_cost / total_qty if total_qty > 0 else 0
                    holding = next((h for h in holdings if h.get("code") == code), None)
                    current_price = holding["current_price"] if holding else 0

                    # 현재가 0 또는 None일 때 보정: 1) Supabase 일봉 종가, 2) 매수가
                    if not current_price or current_price == 0:
                        try:
                            last_row = (
                                supabase.table("daily_ohlcv")
                                .select("close_price")
                                .eq("stock_code", code)
                                .order("date", desc=True)
                                .limit(1)
                                .execute()
                                .data
                            )
                            if last_row:
                                current_price = float(last_row[0].get("close_price") or 0)
                        except Exception:
                            pass
                    if not current_price or current_price == 0:
                        current_price = avg_entry

                    evaluation = current_price * total_qty
                    pnl_amount = evaluation - total_cost
                    pnl_pct = (pnl_amount / total_cost * 100) if total_cost > 0 else 0
                    positions.append({
                        "code": code,
                        "name": (trades[0].get("stock_name") or code),
                        "quantity": total_qty,
                        "avg_entry": round(avg_entry, 0),
                        "current_price": round(current_price, 0),
                        "evaluation": round(evaluation, 0),
                        "pnl_amount": round(pnl_amount, 0),
                        "pnl_pct": round(pnl_pct, 2),
                        "split_count": len(trades),
                        "strategy": trades[0].get("strategy", ""),
                        "is_live": market_open,
                    })
            except Exception as e:
                print(f"[ERROR] portfolio positions: {e}")
                positions = []

        if not positions and holdings:
            for h in holdings:
                current_price = h.get("current_price", 0) or 0
                qty = h.get("quantity", 0) or 0
                avg_entry = h.get("avg_price", 0) or 0
                evaluation = h.get("evaluation", 0) or (current_price * qty)
                pnl_amount = h.get("pnl_amount", 0) or (evaluation - avg_entry * qty)
                pnl_pct = h.get("pnl_pct", 0) or 0
                positions.append({
                    "code": h.get("code", ""),
                    "name": h.get("name", ""),
                    "quantity": qty,
                    "avg_entry": avg_entry,
                    "current_price": current_price,
                    "evaluation": evaluation,
                    "pnl_amount": round(pnl_amount, 0),
                    "pnl_pct": round(pnl_pct or 0, 2),
                    "split_count": 1,
                    "strategy": "",
                    "is_live": market_open,
                })

        deposit = summary.get("deposit", 0) or 0
        total_eval = summary.get("total_evaluation", 0) or 0
        estimated = summary.get("estimated_asset", 0) or 0
        if not estimated:
            estimated = deposit + total_eval

        return {
            "deposit": deposit,
            "total_evaluation": total_eval,
            "estimated_asset": estimated,
            "today_pnl": summary.get("today_pnl", 0),
            "today_pnl_pct": summary.get("today_pnl_pct", 0) or 0,
            "cumulative_pnl": summary.get("cumulative_pnl", 0),
            "cumulative_pnl_pct": summary.get("cumulative_pnl_pct", 0) or 0,
            "positions": positions,
            "max_positions": 5,
            "is_market_open": market_open,
        }
    except Exception as e:
        print(f"[ERROR] portfolio: {e}")
        return {"error": str(e), "positions": [], "deposit": 0, "total_evaluation": 0, "estimated_asset": 0}


@app.get("/api/stocks/daily-pnl")
async def get_stocks_daily_pnl(days: int = Query(7, ge=1, le=31)):
    """최근 N일 수익 추이"""
    try:
        kiwoom = _get_kiwoom()
        if not kiwoom:
            return {"daily": []}
        results = []
        for i in range(days, -1, -1):
            d = datetime.now() - timedelta(days=i)
            date = d.strftime("%Y%m%d")
            try:
                data = kiwoom.get_daily_balance_pnl(date)
                s = data.get("summary", {})
                results.append({
                    "date": data.get("date", date),
                    "total_evaluation": s.get("total_evaluation", 0),
                    "total_pnl": s.get("total_pnl", 0),
                    "total_pnl_pct": s.get("total_pnl_pct", 0) or 0,
                    "deposit": s.get("deposit", 0),
                })
            except Exception:
                results.append({
                    "date": date,
                    "total_evaluation": 0,
                    "total_pnl": 0,
                    "total_pnl_pct": 0,
                    "deposit": 0,
                })
        return {"daily": results}
    except Exception as e:
        print(f"[ERROR] daily-pnl: {e}")
        return {"daily": []}


@app.get("/api/stocks/strategy")
async def get_stocks_strategy():
    try:
        path = Path("/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json")
        if not path.exists():
            return {"error": "없음", "strategy": None}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"strategy": data}
    except Exception as e:
        return {"error": str(e), "strategy": None}


@app.get("/api/stocks/logs")
async def get_stocks_logs():
    try:
        log_path = Path("/home/wlsdud5035/.openclaw/logs/stock_trading.log")
        if not log_path.exists():
            return {"lines": []}
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return {"lines": lines[-50:]}
    except Exception as e:
        return {"lines": [str(e)]}


@app.get("/api/stocks/trades")
async def get_stocks_trades():
    try:
        if not supabase:
            return []
        today = datetime.now().date().isoformat()
        res = (
            supabase.table("trade_executions")
            .select("*")
            .order("trade_id", desc=True)
            .limit(20)
            .execute()
        )
        data = res.data or []
        if data and isinstance(data[0], dict) and "created_at" in data[0]:
            data = [r for r in data if str(r.get("created_at") or "")[:10] == today]
        return data
    except Exception as e:
        try:
            res = supabase.table("trade_executions").select("*").order("trade_id", desc=True).limit(20).execute()
            return res.data or []
        except Exception:
            pass
        print(f"[ERROR] stocks trades: {e}")
        return []


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
        print(f"[us] Supabase 조회 실패: {e}")
        return {"run_date": None, "items": []}


def _get_us_market_summary() -> list:
    """미국 주요 지수 최근 변동 (yfinance, 캐시 5분)."""
    import time as _time
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


def _fetch_us_positions() -> list:
    """Supabase에서 US OPEN 포지션 조회 + 현재가 포함."""
    try:
        if not supabase:
            return []
        res = supabase.table("us_trade_executions").select("*").eq("result", "OPEN").execute()
        positions = res.data or []
        try:
            import yfinance as _yf2
            for p in positions:
                sym = p.get("symbol", "")
                if not sym:
                    continue
                try:
                    t = _yf2.Ticker(sym)
                    h = t.history(period="5d")
                    if not h.empty:
                        p["current_price"] = float(h["Close"].iloc[-1])
                        entry = float(p.get("price", 0))
                        if entry > 0:
                            p["pnl_pct"] = round((p["current_price"] / entry - 1) * 100, 2)
                        else:
                            p["pnl_pct"] = 0
                except Exception:
                    p["current_price"] = 0
                    p["pnl_pct"] = 0
        except Exception:
            pass
        return positions
    except Exception:
        return []


def _build_us_html() -> str:
    data = _fetch_us_signals()
    run_date = data["run_date"]
    items = data["items"]

    positions = _fetch_us_positions()

    # 지수 요약 카드
    mkt = _get_us_market_summary()
    mkt_cards = ""
    for m in mkt:
        chg = m.get("change_pct", 0)
        color = "var(--green)" if chg > 0 else "var(--red)" if chg < 0 else "var(--text)"
        sign = "+" if chg > 0 else ""
        if m["name"] == "VIX":
            price_fmt = f'{m["price"]:.1f}'
        else:
            price_fmt = f'{m["price"]:,.0f}'
        mkt_cards += f'''<div class="idx-card">
          <div class="idx-name">{m["name"]}</div>
          <div class="idx-price">{price_fmt}</div>
          <div class="idx-chg" style="color:{color}">{sign}{chg:.2f}%</div>
        </div>'''

    if not mkt_cards:
        mkt_cards = '<div style="color:var(--muted);font-size:12px;">지수 데이터 로딩 중...</div>'

    # 상위 5개 = "TOP PICK" 하이라이트
    top_n = min(5, len(items))
    top_cards = ""
    for i, row in enumerate(items[:top_n]):
        ret5 = row.get("ret_5d", 0)
        ret20 = row.get("ret_20d", 0)
        c5 = "var(--green)" if ret5 > 0 else "var(--red)"
        c20 = "var(--green)" if ret20 > 0 else "var(--red)"
        s5 = "+" if ret5 > 0 else ""
        s20 = "+" if ret20 > 0 else ""
        top_cards += f'''<div class="top-card">
          <div class="top-rank">#{i+1}</div>
          <div class="top-sym">{row.get("symbol","")}</div>
          <div class="top-score">{row.get("score",0):.1f}</div>
          <div class="top-rets">
            <span style="color:{c5}">{s5}{ret5:.1f}%<small> 5D</small></span>
            <span style="color:{c20}">{s20}{ret20:.1f}%<small> 20D</small></span>
          </div>
        </div>'''

    # 전체 랭킹 테이블
    rows_html = ""
    for i, row in enumerate(items, start=1):
        ret5 = row.get("ret_5d", 0)
        ret20 = row.get("ret_20d", 0)
        score = row.get("score", 0)
        ret5_color = "var(--green)" if ret5 > 0 else "var(--red)" if ret5 < 0 else "var(--text)"
        ret20_color = "var(--green)" if ret20 > 0 else "var(--red)" if ret20 < 0 else "var(--text)"
        score_color = "var(--accent)" if score >= 70 else "var(--green)" if score >= 50 else "var(--yellow)" if score >= 35 else "var(--red)"
        is_top = "top-row" if i <= top_n else ""
        grade = "A" if score >= 75 else "B" if score >= 60 else "C" if score >= 40 else "D"
        rows_html += (
            f'<tr class="{is_top}">'
            f'<td>{i}</td>'
            f'<td style="font-family:var(--mono);font-weight:600">{row.get("symbol","")}</td>'
            f'<td><span style="color:{score_color};font-weight:700">{score:.1f}</span> <span class="grade grade-{grade.lower()}">{grade}</span></td>'
            f'<td style="color:{ret5_color}">{ret5:+.2f}%</td>'
            f'<td style="color:{ret20_color}">{ret20:+.2f}%</td>'
            f'<td>{row.get("vol_ratio",0):.2f}x</td>'
            f'<td>{row.get("near_high",0):.1f}%</td>'
            f'</tr>'
        )

    if not rows_html:
        rows_html = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px 0;">데이터 없음 — us_momentum_backtest.py scan 실행 필요</td></tr>'

    total_count = len(items)
    avg_score = sum(r.get("score", 0) for r in items) / total_count if total_count else 0

    # 보유 포지션 카드 생성
    pos_cards = ""
    total_invested = 0
    total_current = 0
    for p in positions:
        sym = p.get("symbol", "?")
        qty = float(p.get("quantity", 0))
        entry = float(p.get("price", 0))
        cur = float(p.get("current_price", 0))
        pnl = float(p.get("pnl_pct", 0))
        sc = float(p.get("score", 0))
        invested = entry * qty
        current_val = cur * qty if cur else invested
        total_invested += invested
        total_current += current_val
        pnl_color = "var(--green)" if pnl > 0 else "var(--red)" if pnl < 0 else "var(--text)"
        pnl_sign = "+" if pnl > 0 else ""
        pos_cards += f'''<div class="pos-card">
          <div class="pos-sym">{sym}</div>
          <div class="pos-detail">{qty:.2f}주 × ${entry:.2f}</div>
          <div class="pos-cur">${cur:.2f}</div>
          <div class="pos-pnl" style="color:{pnl_color}">{pnl_sign}{pnl:.2f}%</div>
          <div class="pos-score">M{sc:.0f}</div>
        </div>'''
    total_pnl_pct = ((total_current / total_invested - 1) * 100) if total_invested > 0 else 0
    pos_count = len(positions)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OpenClaw US Momentum</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{--bg:#0a0e17;--bg2:#0f1422;--bg3:#141928;--border:#1e2537;--accent:#00d4ff;--green:#00e676;--red:#ff3d57;--yellow:#ffd600;--text:#e8eaf0;--muted:#4a5068;--font:'Syne',sans-serif;--mono:'DM Mono',monospace;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--text);font-family:var(--font);min-height:100vh;overflow-x:hidden;}}
  body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}}
  .wrapper{{position:relative;z-index:1;}}
  header{{display:flex;align-items:center;justify-content:space-between;padding:16px 28px;border-bottom:1px solid var(--border);background:rgba(10,14,23,0.9);backdrop-filter:blur(10px);position:sticky;top:0;z-index:100;}}
  .logo{{display:flex;align-items:center;gap:8px;font-weight:700;font-size:16px;letter-spacing:0.04em;}}
  .logo-icon{{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--accent),#7c4dff);display:flex;align-items:center;justify-content:center;font-size:14px;}}
  .nav-tab{{padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;color:var(--muted);transition:all 0.2s;cursor:pointer;text-decoration:none;}}
  .nav-tab:hover{{color:var(--text);background:rgba(255,255,255,0.05);}}
  .nav-tab.active{{color:var(--accent);background:rgba(0,212,255,0.1);}}
  .live-badge{{display:flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--green);background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.2);padding:4px 10px;border-radius:20px;}}
  .live-dot{{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.3;}}}}
  main{{max-width:1200px;margin:0 auto;padding:24px;}}

  /* 지수 카드 */
  .idx-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px;}}
  .idx-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;}}
  .idx-name{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;}}
  .idx-price{{font-size:18px;font-weight:700;font-family:var(--mono);}}
  .idx-chg{{font-size:13px;font-family:var(--mono);margin-top:2px;}}

  /* 통계 카드 */
  .stat-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px;}}
  .stat-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;text-align:center;}}
  .stat-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;}}
  .stat-val{{font-size:22px;font-weight:700;font-family:var(--mono);}}

  /* TOP PICK 카드 */
  .top-row-cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:24px;}}
  .top-card{{background:linear-gradient(135deg,rgba(0,212,255,0.06),rgba(124,77,255,0.06));border:1px solid rgba(0,212,255,0.2);border-radius:12px;padding:14px 16px;position:relative;}}
  .top-rank{{position:absolute;top:8px;right:12px;font-size:11px;color:var(--accent);font-family:var(--mono);opacity:0.6;}}
  .top-sym{{font-size:16px;font-weight:700;margin-bottom:4px;}}
  .top-score{{font-size:24px;font-weight:800;color:var(--accent);font-family:var(--mono);}}
  .top-rets{{display:flex;gap:10px;margin-top:6px;font-size:12px;font-family:var(--mono);}}
  .top-rets small{{color:var(--muted);margin-left:2px;}}

  /* 테이블 */
  .section-title{{font-size:15px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
  .section-title span{{color:var(--accent);}}
  table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;}}
  thead tr{{background:var(--bg3);}}
  th,td{{padding:10px 14px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap;}}
  th:first-child,td:first-child{{text-align:center;width:40px;}}
  th:nth-child(2),td:nth-child(2){{text-align:left;}}
  th{{font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;font-size:11px;}}
  tbody tr:hover{{background:rgba(0,212,255,0.04);}}
  tr.top-row{{background:rgba(0,212,255,0.03);}}
  tr.top-row td:first-child{{position:relative;}}
  tr.top-row td:first-child::before{{content:'';position:absolute;left:0;top:4px;bottom:4px;width:3px;background:var(--accent);border-radius:2px;}}
  .grade{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;font-family:var(--mono);margin-left:4px;}}
  .grade-a{{background:rgba(0,230,118,0.15);color:var(--green);}}
  .grade-b{{background:rgba(0,212,255,0.15);color:var(--accent);}}
  .grade-c{{background:rgba(255,214,0,0.15);color:var(--yellow);}}
  .grade-d{{background:rgba(255,61,87,0.15);color:var(--red);}}

  /* 보유 포지션 */
  .pos-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:24px;}}
  .pos-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:4px;}}
  .pos-sym{{font-size:16px;font-weight:700;font-family:var(--mono);}}
  .pos-detail{{font-size:11px;color:var(--muted);font-family:var(--mono);}}
  .pos-cur{{font-size:14px;font-weight:600;font-family:var(--mono);}}
  .pos-pnl{{font-size:18px;font-weight:800;font-family:var(--mono);}}
  .pos-score{{font-size:10px;color:var(--accent);font-family:var(--mono);opacity:0.7;}}
  .portfolio-summary{{display:flex;gap:24px;align-items:center;margin-bottom:14px;padding:12px 16px;background:var(--bg3);border:1px solid var(--border);border-radius:10px;font-family:var(--mono);font-size:13px;}}
  .portfolio-summary .label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.06em;}}
  .portfolio-summary .val{{font-weight:700;font-size:16px;}}
</style>
</head>
<body>
<div class="wrapper">
  <header>
    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
      <div class="logo"><div class="logo-icon">🤖</div>OpenClaw Trading</div>
      <nav style="display:flex;align-items:center;gap:4px;margin-left:24px;">
        <a href="/" class="nav-tab">₿ BTC</a>
        <a href="/stocks" class="nav-tab">📈 주식</a>
        <a href="/us" class="nav-tab active">🇺🇸 US</a>
      </nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="live-badge"><div class="live-dot"></div>LIVE</div>
      <div style="font-family:var(--mono);font-size:12px;color:var(--muted);" id="clock"></div>
    </div>
  </header>
  <main>
    <!-- 헤더 -->
    <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:20px;">
      <div>
        <h2 style="font-size:20px;font-weight:700;">🇺🇸 US 모멘텀 자동매매 대시보드</h2>
        <div style="font-size:12px;color:var(--muted);font-family:var(--mono);margin-top:4px;">
          {("스캔 날짜: " + run_date + " · ") if run_date else ""}유니버스 {total_count}종 · 평균 스코어 {avg_score:.1f}
        </div>
      </div>
    </div>

    <!-- 미국 지수 요약 -->
    <div class="idx-row">{mkt_cards}</div>

    <!-- 통계 카드 -->
    <div class="stat-row">
      <div class="stat-card"><div class="stat-label">유니버스</div><div class="stat-val">{total_count}</div></div>
      <div class="stat-card"><div class="stat-label">평균 스코어</div><div class="stat-val">{avg_score:.1f}</div></div>
      <div class="stat-card"><div class="stat-label">TOP PICK</div><div class="stat-val" style="color:var(--accent)">{top_n}</div></div>
      <div class="stat-card"><div class="stat-label">보유 종목</div><div class="stat-val" style="color:{'var(--green)' if pos_count > 0 else 'var(--muted)'}">{pos_count}</div></div>
    </div>

    <!-- 보유 포지션 -->
    {f"""<div class="section-title"><span>💼</span> 보유 포지션</div>
    <div class="portfolio-summary">
      <div><div class="label">투자금</div><div class="val">${total_invested:,.0f}</div></div>
      <div><div class="label">평가금</div><div class="val">${total_current:,.0f}</div></div>
      <div><div class="label">수익률</div><div class="val" style="color:{'var(--green)' if total_pnl_pct > 0 else 'var(--red)' if total_pnl_pct < 0 else 'var(--text)'}">{'+'if total_pnl_pct>0 else ''}{total_pnl_pct:.2f}%</div></div>
    </div>
    <div class="pos-grid">{pos_cards}</div>""" if pos_count > 0 else ""}

    <!-- TOP PICK 하이라이트 -->
    <div class="section-title"><span>🏆</span> TOP PICKS</div>
    <div class="top-row-cards">{top_cards if top_cards else '<div style="color:var(--muted)">데이터 없음</div>'}</div>

    <!-- 전체 모멘텀 랭킹 -->
    <div class="section-title"><span>📊</span> 전체 모멘텀 랭킹</div>
    <table>
      <thead><tr><th>#</th><th>SYMBOL</th><th>SCORE</th><th>RET 5D</th><th>RET 20D</th><th>VOL RATIO</th><th>NEAR 60D HIGH</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </main>
</div>
<script>
setInterval(()=>{{
  const el=document.getElementById('clock');
  if(el) el.textContent=new Date().toLocaleTimeString('ko-KR');
}},1000);
</script>
</body>
</html>'''


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
