"""BTC-related API endpoints."""
import os, time, json, requests, asyncio, re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
import psutil

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.supabase_client import get_supabase
from common.config import BTC_LOG, BRAIN_PATH, LOG_DIR, MEMORY_PATH
from common.logger import get_logger

log = get_logger("btc_api")

supabase = get_supabase()
router = APIRouter()

# ── caches ──────────────────────────────────────────────
_upbit_cache = {
    "time": 0,
    # Legacy: historically used as "KRW available" balance
    "krw": None,
    # New: expose available/locked/total for clarity
    "krw_available": None,
    "krw_locked": None,
    "krw_total": None,
    "ok": False,
}
_news_cache = {"data": [], "ts": 0}
_trend_cache = {"value": "SIDEWAYS", "time": 0}
_fx_cache = {"rate": 1300.0, "time": 0}  # USD to KRW fallback
NEWS_CACHE_TTL = 300
FX_CACHE_TTL = 3600
_AGENT_DECISION_RE = re.compile(
    r"신호:\s*(BUY|SELL|HOLD|NO_POSITION)\s*\(신뢰도:\s*([0-9.]+)%\)(?:\s*→\s*([A-Z_]+))?"
)
_AGENT_STATUS_RE = re.compile(r"\s—\s(BUY|SELL|HOLD|NO_POSITION)\b")
_TRADE_RESULT_RE = re.compile(
    r"신호:\s*(BUY|SELL|HOLD|NO_POSITION)\s*\(신뢰도:\s*([0-9.]+)%\)\s*→\s*([A-Z_]+)"
)
KST = ZoneInfo("Asia/Seoul")


def _refresh_upbit_cache():
    global _upbit_cache
    # Cache TTL: 60s. However, if we have a KRW value but the extended fields
    # are still missing (e.g. after a hot reload/deploy), refresh immediately.
    if time.time() - _upbit_cache["time"] <= 60:
        if _upbit_cache.get("krw") is not None and (
            _upbit_cache.get("krw_locked") is None or _upbit_cache.get("krw_total") is None
        ):
            pass
        else:
            return
    _upbit_cache["time"] = time.time()
    _upbit_cache["krw"] = None
    _upbit_cache["krw_available"] = None
    _upbit_cache["krw_locked"] = None
    _upbit_cache["krw_total"] = None
    _upbit_cache["ok"] = False
    try:
        upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
        upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
        if upbit_key and upbit_secret:
            import pyupbit
            upbit = pyupbit.Upbit(upbit_key, upbit_secret)
            try:
                balances = upbit.get_balances() or []
                krw = next((b for b in balances if b.get("currency") == "KRW"), None)
                if krw is not None:
                    available = float(krw.get("balance") or 0)
                    locked = float(krw.get("locked") or 0)
                    total = available + locked
                    _upbit_cache["krw_available"] = available
                    _upbit_cache["krw_locked"] = locked
                    _upbit_cache["krw_total"] = total
                    # Keep legacy field as "available" so existing logic stays consistent.
                    _upbit_cache["krw"] = available
                else:
                    bal = upbit.get_balance("KRW")
                    _upbit_cache["krw"] = float(bal) if bal is not None else None
                    _upbit_cache["krw_available"] = _upbit_cache["krw"]
                    _upbit_cache["krw_locked"] = 0.0 if _upbit_cache["krw"] is not None else None
                    _upbit_cache["krw_total"] = _upbit_cache["krw"]
            except Exception:
                bal = upbit.get_balance("KRW")
                _upbit_cache["krw"] = float(bal) if bal is not None else None
                _upbit_cache["krw_available"] = _upbit_cache["krw"]
                _upbit_cache["krw_locked"] = 0.0 if _upbit_cache["krw"] is not None else None
                _upbit_cache["krw_total"] = _upbit_cache["krw"]
            _upbit_cache["ok"] = True
    except Exception as e:
        log.error(f"upbit cache: {e}")


def _get_fx_rate():
    """Fetch real-time USD to KRW exchange rate."""
    global _fx_cache
    if time.time() - _fx_cache["time"] < FX_CACHE_TTL:
        return _fx_cache["rate"]
    try:
        # Try Upbit first (most reliable for KRW pairs)
        import pyupbit
        price = pyupbit.get_current_price("KRW-USD")
        if price:
            _fx_cache["rate"] = float(price)
            _fx_cache["time"] = time.time()
            return _fx_cache["rate"]
    except Exception:
        pass
    
    try:
        # Fallback: Get rate from exchange API
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        if r.status_code == 200:
            rate = r.json().get("rates", {}).get("KRW", 1300.0)
            _fx_cache["rate"] = float(rate)
            _fx_cache["time"] = time.time()
            return _fx_cache["rate"]
    except Exception:
        pass
    
    return _fx_cache["rate"]  # Return cached or default (1300)


def _tail_text_log(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [
        line for line in raw[-limit:]
        if not line.startswith("declare -x ") and "CRON" not in line[:20]
    ]


def _tail_json_events(name: str, limit: int = 80) -> list[dict]:
    path = LOG_DIR / "json" / f"{name}.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _agent_decisions_from_local_logs(limit: int = 20) -> list[dict]:
    decisions: list[dict] = []
    sources = [
        ("btc", "btc_agent"),
        ("kr", "stock_agent"),
        ("us", "us_agent"),
    ]
    for market, logger_name in sources:
        for row in reversed(_tail_json_events(logger_name, limit=400)):
            event = str(row.get("event") or "").strip()
            if not event:
                continue
            match = _AGENT_DECISION_RE.search(event)
            if match:
                decision, confidence, action = match.groups()
                decisions.append(
                    {
                        "id": f"{logger_name}:{row.get('ts')}:{len(decisions)}",
                        "market": market,
                        "decision": decision,
                        "confidence": float(confidence),
                        "action": (action or "pending").lower(),
                        "reasoning": event,
                        "details": event,
                        "created_at": row.get("ts"),
                        "source": "local_jsonl",
                    }
                )
                continue
            if row.get("level") != "TRADE":
                continue
            status = _AGENT_STATUS_RE.search(event)
            if not status:
                continue
            decisions.append(
                {
                    "id": f"{logger_name}:{row.get('ts')}:{len(decisions)}",
                    "market": market,
                    "decision": status.group(1),
                    "confidence": None,
                    "action": "pending",
                    "reasoning": event,
                    "details": event,
                    "created_at": row.get("ts"),
                    "source": "local_jsonl",
                }
            )
    decisions.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return decisions[:limit]


def _recent_btc_activity_from_logs(limit: int = 20) -> list[dict]:
    candidate_paths = [
        Path("/app/external_logs/json/btc_agent.jsonl"),
        LOG_DIR / "json" / "btc_agent.jsonl",
    ]
    path = next((candidate for candidate in candidate_paths if candidate.exists()), None)
    if path is None:
        return []

    rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    activity: list[dict] = []
    for line in reversed(rows):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = str(payload.get("event") or "").strip()
        match = _TRADE_RESULT_RE.search(event)
        if not match:
            continue
        action, confidence, result = match.groups()
        raw_ts = str(payload.get("ts") or "").strip()
        timestamp_kst = raw_ts
        timestamp_utc = raw_ts
        try:
            utc_dt = datetime.strptime(raw_ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            timestamp_utc = utc_dt.isoformat()
            timestamp_kst = utc_dt.astimezone(KST).isoformat()
        except Exception:
            pass
        activity.append(
            {
                "timestamp": raw_ts,
                "timestamp_utc": timestamp_utc,
                "timestamp_kst": timestamp_kst,
                "action": action,
                "confidence": float(confidence),
                "result": result,
                "message": event,
                "source": "btc_agent_jsonl",
            }
        )
        if len(activity) >= limit:
            break
    return activity


def _closed_trade_batch_key(row: dict) -> tuple[str, int]:
    exit_time = str(row.get("exit_time") or "")[:19]
    exit_price = int(round(float(row.get("exit_price") or 0)))
    return exit_time, exit_price


def _summarize_closed_trade_batches(rows: list[dict]) -> dict:
    batches: dict[tuple[str, int], dict] = {}
    for row in rows:
        key = _closed_trade_batch_key(row)
        batch = batches.setdefault(
            key,
            {
                "exit_time": key[0],
                "exit_price": float(row.get("exit_price") or 0),
                "pnl": 0.0,
                "entry_krw": 0.0,
                "count": 0,
                "exit_reason": "",
            },
        )
        batch["pnl"] += float(row.get("pnl") or 0)
        batch["entry_krw"] += float(row.get("entry_krw") or 0)
        batch["count"] += 1
        if not batch["exit_reason"]:
            batch["exit_reason"] = row.get("exit_reason") or ""

    items = list(batches.values())
    wins = len([item for item in items if item["pnl"] > 0])
    losses = len([item for item in items if item["pnl"] < 0])
    return {
        "items": items,
        "wins": wins,
        "losses": losses,
        "closed_count": len(items),
        "raw_closed_count": len(rows),
    }


def _btc_live_log_lines(limit: int = 80) -> list[str]:
    text_lines = _tail_text_log(BTC_LOG, limit=limit)
    if text_lines:
        return text_lines
    json_lines = []
    for row in _tail_json_events("btc_agent", limit=limit):
        ts = row.get("ts", "")
        level = row.get("level", "")
        event = row.get("event", "")
        json_lines.append(f"[{ts}][openclaw.btc_agent][{level}] {event}".strip())
    return json_lines[-limit:]


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
# @router.get("/", response_class=HTMLResponse)
# async def index():
#     from btc.templates.btc_html import BTC_HTML
#     return BTC_HTML


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

    # v6.2 B3: PnL 환율 단위 통일
    # cur_price: yfinance BTC-USD (USD 단위)
    # entry_price: DB btc_position.entry_price (KRW 단위, Upbit KRW-BTC 기준으로 저장됨)
    # → cur_price * fx_rate = KRW 환산 현재가, entry_p(KRW)와 동일 단위로 비교
    cur_price = float(close.iloc[-1])
    fx_rate = _get_fx_rate()  # USD → KRW 실시간 환율
    pos_pnl = None
    if pos:
        entry_p = float(pos.get("entry_price", 0))  # KRW
        if entry_p > 0:
            cur_price_krw = cur_price * fx_rate  # USD → KRW 변환
            pos_pnl = {"pnl_pct": round((cur_price_krw - entry_p) / entry_p * 100, 2),
                       "entry_price": entry_p, "quantity": pos.get("quantity", 0),
                       "entry_krw": pos.get("entry_krw", 0),
                       "current_fx_rate": fx_rate}

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
        return {"error": "Internal server error"}


@router.get("/api/btc/portfolio")
async def api_btc_portfolio():
    if not supabase:
        return {"error": "DB 미연결", "open_positions": [], "closed_positions": [], "summary": {}}
    try:
        # NOTE: status values in DB are historically inconsistent in case (OPEN/open, CLOSED/closed)
        open_rows = await asyncio.to_thread(
            lambda: supabase.table("btc_position")
            .select("*")
            .in_("status", ["OPEN", "open"])
            .execute()
            .data or []
        )
        closed_rows = await asyncio.to_thread(
            lambda: supabase.table("btc_position")
            .select("*")
            .in_("status", ["CLOSED", "closed"])
            .order("exit_time", desc=True)
            .limit(50)
            .execute()
            .data or []
        )

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
                    fx_rate = _get_fx_rate()  # Use dynamic FX rate instead of hardcoded 1450
                    cur_price_krw = float(df["Close"].iloc[-1]) * fx_rate
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
            # Compute default stop_loss and take_profit if not set
            sl = p.get("stop_loss") or (entry_price * 0.97)  # 3% stop loss
            tp = p.get("take_profit") or (entry_price * 1.12)  # 12% take profit
            
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
                "stop_loss": round(float(sl), 2) if sl else None,
                "take_profit": round(float(tp), 2) if tp else None,
            })

        closed_positions = []
        total_realized_pnl = 0
        for p in closed_rows:
            pnl = float(p.get("pnl") or 0)
            entry_krw = float(p.get("entry_krw") or 0)
            pnl_pct = (pnl / entry_krw * 100) if entry_krw > 0 else 0
            total_realized_pnl += pnl
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
        closed_summary = _summarize_closed_trade_batches(closed_rows)
        wins = closed_summary["wins"]
        losses = closed_summary["losses"]

        _refresh_upbit_cache()
        krw_balance = _upbit_cache.get("krw", 0) or 0
        krw_locked = _upbit_cache.get("krw_locked")
        krw_total = _upbit_cache.get("krw_total")

        # Summary's estimated_asset should reflect *live Upbit balances*.
        # Keep DB-derived total_eval_open/total_invested_open for position analytics.
        upbit_btc_balance = None
        upbit_btc_value_krw = None
        try:
            upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
            upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
            if upbit_key and upbit_secret and _upbit_cache["ok"]:
                import pyupbit

                upbit = pyupbit.Upbit(upbit_key, upbit_secret)
                upbit_btc_balance = float(upbit.get_balance("BTC") or 0)
                upbit_btc_value_krw = float(upbit_btc_balance) * float(cur_price_krw or 0)
        except Exception as e:
            log.error(f"upbit balance(BTC) fetch failed: {e}")

        unrealized_pnl = total_eval_open - total_invested_open
        total_pnl = total_realized_pnl + unrealized_pnl
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        summary = {
            "krw_balance": krw_balance,
            "krw_locked": krw_locked,
            "krw_total": krw_total,
            "btc_price_krw": round(cur_price_krw),
            "open_count": len(open_positions),
            "closed_count": closed_summary["closed_count"],
            "raw_closed_count": closed_summary["raw_closed_count"],
            "total_invested": round(total_invested_open),
            "total_eval": round(total_eval_open),
            "unrealized_pnl": round(unrealized_pnl),
            "unrealized_pnl_pct": round((unrealized_pnl / total_invested_open * 100) if total_invested_open > 0 else 0, 2),
            "realized_pnl": round(total_realized_pnl),
            "total_pnl": round(total_pnl),
            "wins": wins,
            "losses": losses,
            "winrate": round(winrate, 1),
            "estimated_asset": round(
                krw_balance + (upbit_btc_value_krw if upbit_btc_value_krw is not None else total_eval_open)
            ),
            "upbit_btc_balance": upbit_btc_balance,
        }

        return {
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "summary": summary,
        }
    except Exception as e:
        log.error(f"btc portfolio: {e}")
        return {"error": "Internal server error", "open_positions": [], "closed_positions": [], "summary": {}}


@router.get("/api/summary")
async def api_summary():
    result = {}
    try:
        if supabase:
            def _sync_summary():
                btc_pos = supabase.table("btc_position").select("entry_price,entry_krw,quantity").eq("status", "OPEN").execute().data or []
                kr_open = supabase.table("trade_executions").select("trade_id").eq("result", "OPEN").execute().data or []
                us_open = supabase.table("us_trade_executions").select("symbol,price,quantity").eq("result", "OPEN").execute().data or []
                return btc_pos, kr_open, us_open
            btc_pos, kr_open, us_open = await asyncio.to_thread(_sync_summary)
            result["btc"] = {"positions": len(btc_pos), "invested_krw": sum(float(p.get("entry_krw", 0)) for p in btc_pos)}
            result["kr"] = {"positions": len(kr_open)}
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


@router.get("/api/btc/filters")
async def api_btc_filters():
    """매매 필터 상태 — 김치프리미엄·펀딩비·일일 횟수·손실 한도"""
    try:
        # 1. 김치 프리미엄
        from btc.btc_trading_agent import get_kimchi_premium
        kimchi = await asyncio.to_thread(get_kimchi_premium)

        # 2. 펀딩비 (rate는 이미 % 단위로 반환됨)
        from common.market_data import (
            get_btc_funding_rate,
            get_btc_long_short_ratio,
            get_btc_open_interest,
        )
        fr = await asyncio.to_thread(get_btc_funding_rate)
        ls = await asyncio.to_thread(get_btc_long_short_ratio)
        oi = await asyncio.to_thread(get_btc_open_interest)
        funding_rate = round(float(fr.get("rate", 0)), 4)
        funding_signal = fr.get("signal", "NEUTRAL")

        # 3. 오늘 매매 횟수 (btc_position open today)
        today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        today_count = 0
        today_pnl_pct = 0.0
        if supabase:
            pos_res = supabase.table("btc_position").select(
                "entry_krw,pnl,pnl_pct,status,entry_time"
            ).gte("entry_time", today).execute()
            rows = pos_res.data or []
            today_count = len(rows)
            closed_today = [r for r in rows if r.get("status") == "CLOSED"]
            total_inv = sum(float(r.get("entry_krw") or 0) for r in closed_today)
            total_pnl = sum(float(r.get("pnl") or 0) for r in closed_today)
            today_pnl_pct = round(total_pnl / total_inv * 100, 2) if total_inv > 0 else 0.0

        from common.config import BTC_RISK_DEFAULTS
        return {
            "kimchi_premium": round(float(kimchi or 0), 2),
            "kimchi_blocked": float(kimchi or 0) >= 5.0,
            "funding_rate": funding_rate,
            "funding_signal": funding_signal,
            "funding_overheated": funding_signal in ("LONG_CROWDED",),
            "long_short_ratio": round(float(ls.get("ls_ratio", 1.0) or 1.0), 3),
            "open_interest": round(float(oi.get("oi_btc", 0) or 0), 2),
            "today_trades": today_count,
            "max_trades_per_day": int(BTC_RISK_DEFAULTS.get("max_trades_per_day", 3)),
            "today_pnl_pct": today_pnl_pct,
            "max_daily_loss": round(BTC_RISK_DEFAULTS.get("max_daily_loss", -0.08) * 100, 1),
            "max_drawdown": round(BTC_RISK_DEFAULTS.get("max_drawdown", -0.15) * 100, 1),
        }
    except Exception as e:
        log.error(f"btc_filters: {e}")
        return {
            "kimchi_premium": None, "kimchi_blocked": False,
            "funding_rate": None, "funding_signal": "NEUTRAL", "funding_overheated": False,
            "long_short_ratio": 1.0, "open_interest": 0,
            "today_trades": 0, "max_trades_per_day": 3,
            "today_pnl_pct": 0, "max_daily_loss": -8.0, "max_drawdown": -15.0,
        }


@router.get("/api/stats")
async def get_stats():
    if not supabase:
        return _empty_stats()
    try:
        def _sync_stats():
            trades = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(200).execute().data or []
            closed = supabase.table("btc_position").select("*").eq("status", "CLOSED").execute().data or []
            pos_res = supabase.table("btc_position").select("*").eq("status", "OPEN").order("entry_time", desc=True).limit(1).execute()
            return trades, closed, pos_res.data
        trades, closed, pos_data = await asyncio.to_thread(_sync_stats)

        buys = [t for t in trades if t.get("action") == "BUY"]
        sells = [t for t in trades if t.get("action") == "SELL"]
        closed_summary = _summarize_closed_trade_batches(closed)
        wins = closed_summary["wins"]
        losses_cnt = closed_summary["losses"]
        total_pnl = sum(float(p.get("pnl") or 0) for p in closed)
        total_krw = sum(float(p.get("entry_krw") or 0) for p in closed)

        today = datetime.now().date().isoformat()
        today_closed = [p for p in closed if (p.get("exit_time") or "")[:10] == today]
        today_trades = len([t for t in trades if (t.get("timestamp") or "")[:10] == today])
        today_pnl = sum(float(p.get("pnl") or 0) for p in today_closed)

        position = pos_data[0] if pos_data else None

        last = trades[0] if trades else {}

        _refresh_upbit_cache()
        krw_balance = _upbit_cache["krw"]
        krw_locked = _upbit_cache.get("krw_locked")
        krw_total = _upbit_cache.get("krw_total")

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
            "closed_trade_batches": closed_summary["closed_count"],
            "raw_closed_positions": closed_summary["raw_closed_count"],
            "total_trades": len(trades),
            "buys": len(buys),
            "sells": len(sells),
            "avg_confidence": sum(float(t.get("confidence") or 0) for t in trades) / len(trades) if trades else 0,
            "today_trades": today_trades,
            "today_pnl": today_pnl,
            "position": position,
            "trend": trend,
            "krw_balance": krw_balance,
            "krw_locked": krw_locked,
            "krw_total": krw_total,
        }
    except Exception as e:
        log.error(f"stats: {e}")
        return {"error": "Internal server error"}


@router.get("/api/trades")
async def get_trades(
    limit: int = Query(default=50, le=500),
    action: str = Query(default=None, pattern="^(BUY|SELL|HOLD)$"),
    hours: int = Query(default=None, ge=1, le=168)  # 1시간~7일
):
    """거래 내역 조회 (필터링 지원)"""
    if not supabase:
        return []
    try:
        def _sync_trades():
            query = supabase.table("btc_trades").select("*")
            if action:
                query = query.eq("action", action)
            if hours:
                from datetime import timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                query = query.gte("timestamp", cutoff)
            return query.order("timestamp", desc=True).limit(limit).execute().data or []
        data = await asyncio.to_thread(_sync_trades)
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
        lines = _btc_live_log_lines(limit=80)
        if not lines:
            return {"lines": ["로그 파일 없음"]}
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

        # tail + grep: 리스트 방식으로 파이프 없이 처리
        try:
            log_lines = BTC_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
            cron_lines = [l for l in log_lines[-200:] if "매매 사이클 시작" in l]
        except Exception:
            cron_lines = []
        last_cron = cron_lines[-1][:50] if cron_lines else "기록 없음"

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
        return {"error": "Internal server error"}


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
        return {"error": "Internal server error"}


@router.get("/api/agents/decisions")
async def get_agent_decisions(limit: int = 20):
    """최근 에이전트 팀 결정 이력 반환."""
    try:
        if supabase:
            rows = await asyncio.to_thread(
                lambda: supabase.table("agent_decisions").select("*").order("created_at", desc=True).limit(limit).execute()
            )
            if rows.data:
                return {"decisions": rows.data}
        fallback = _agent_decisions_from_local_logs(limit=limit)
        return {"decisions": fallback, "source": "local_jsonl"}
    except Exception as e:
        log.warning(f"agent_decisions: {e}")
        fallback = _agent_decisions_from_local_logs(limit=limit)
        return {"decisions": fallback, "error": str(e), "source": "local_jsonl"}


@router.get("/api/btc/live-activity")
async def get_btc_live_activity(limit: int = 20):
    """최근 BTC 에이전트 활동 로그. 외부 에이전트 jsonl 우선."""
    try:
        rows = _recent_btc_activity_from_logs(limit=limit)
        if rows:
            return {"rows": rows, "source": "btc_agent_jsonl"}

        fallback = await get_trades(limit=limit)
        if isinstance(fallback, list):
            normalized = [
                {
                    "timestamp": row.get("timestamp"),
                    "action": row.get("action"),
                    "confidence": float(row.get("confidence") or 0),
                    "result": json.loads(row.get("order_raw") or "{}").get("result", "UNKNOWN")
                    if isinstance(row.get("order_raw"), str)
                    else "UNKNOWN",
                    "message": row.get("reason") or "",
                    "source": "btc_trades",
                }
                for row in fallback
            ]
            return {"rows": normalized, "source": "btc_trades"}

        return {"rows": [], "source": "empty"}
    except Exception as e:
        log.error(f"btc live activity: {e}")
        return {"rows": [], "error": str(e)}


@router.get("/api/btc/decision-log")
async def get_decision_log(limit: int = 20):
    """BTC 매매 판단 로그 (AI reason + 지표 스냅샷)."""
    try:
        rows = await asyncio.to_thread(
            lambda: supabase.table("btc_trades")
            .select("created_at, action, confidence, reason, composite_score, fear_greed, rsi")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"decisions": rows.data or []}
    except Exception as e:
        log.error(f"decision-log 조회 실패: {e}")
        from common.api_utils import api_error
        return api_error("판단 로그 조회 실패")


def _compute_risk_portfolio_sync() -> dict:
    """Blocking helper for /api/risk/portfolio — gather cross-market risk data."""
    from common.api_utils import api_success

    # ── 1. Total assets across BTC / KR / US ──
    total_assets = 0.0
    btc_value = 0.0
    kr_value = 0.0
    us_value = 0.0

    try:
        _refresh_upbit_cache()
        krw_balance = float(_upbit_cache.get("krw_total") or _upbit_cache.get("krw") or 0)
        btc_value += krw_balance
        # Add BTC position value
        upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
        upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
        if upbit_key and upbit_secret:
            import pyupbit
            upbit = pyupbit.Upbit(upbit_key, upbit_secret)
            btc_bal = float(upbit.get_balance("BTC") or 0)
            btc_price = float(pyupbit.get_current_price("KRW-BTC") or 0)
            btc_value += btc_bal * btc_price
    except Exception as e:
        log.error(f"risk/portfolio btc value: {e}")

    try:
        if supabase:
            kr_rows = (
                supabase.table("trade_executions")
                .select("price,quantity")
                .eq("result", "OPEN")
                .execute()
                .data or []
            )
            kr_value = sum(
                float(r.get("price") or 0) * float(r.get("quantity") or 0)
                for r in kr_rows
            )
    except Exception as e:
        log.error(f"risk/portfolio kr value: {e}")

    try:
        if supabase:
            us_rows = (
                supabase.table("us_trade_executions")
                .select("price,quantity")
                .eq("result", "OPEN")
                .execute()
                .data or []
            )
            fx_rate = _get_fx_rate()
            us_value = sum(
                float(r.get("price") or 0) * float(r.get("quantity") or 0)
                for r in us_rows
            ) * fx_rate
    except Exception as e:
        log.error(f"risk/portfolio us value: {e}")

    total_assets = round(btc_value + kr_value + us_value)

    # ── 2. Daily VaR (placeholder 2% if no real data) ──
    daily_var = round(total_assets * 0.02) if total_assets > 0 else 0

    # ── 3. MDD from closed BTC positions (equity curve) ──
    mdd = 0.0
    try:
        if supabase:
            closed = (
                supabase.table("btc_position")
                .select("entry_krw,pnl,exit_time")
                .in_("status", ["CLOSED", "closed"])
                .order("exit_time", desc=False)
                .execute()
                .data or []
            )
            if closed:
                equity = 0.0
                peak = 0.0
                max_dd = 0.0
                for row in closed:
                    equity += float(row.get("pnl") or 0)
                    if equity > peak:
                        peak = equity
                    dd = (equity - peak) if peak > 0 else 0.0
                    if dd < max_dd:
                        max_dd = dd
                mdd = round((max_dd / peak * 100) if peak > 0 else 0.0, 2)
    except Exception as e:
        log.error(f"risk/portfolio mdd: {e}")

    # ── 4. Current market regime ──
    regime = "UNKNOWN"
    try:
        from agents.regime_classifier import get_cached_regime
        regime = get_cached_regime() or "UNKNOWN"
    except Exception as e:
        log.error(f"risk/portfolio regime: {e}")

    # ── 5. ML drift status from brain/ml/drift_report.json ──
    drift_status = "NO_DATA"
    try:
        drift_path = BRAIN_PATH / "ml" / "drift_report.json"
        if drift_path.exists():
            drift_data = json.loads(drift_path.read_text(encoding="utf-8"))
            drift_status = drift_data.get("status", "NO_DATA")
    except Exception as e:
        log.error(f"risk/portfolio drift: {e}")

    # ── 6. IC health from brain/signal-ic/weights.json ──
    ic_health = {"active_weights": 0, "total_weights": 0}
    try:
        weights_path = BRAIN_PATH / "signal-ic" / "weights.json"
        if weights_path.exists():
            weights_data = json.loads(weights_path.read_text(encoding="utf-8"))
            if isinstance(weights_data, dict):
                total = len(weights_data)
                active = len([v for v in weights_data.values() if float(v or 0) > 0])
                ic_health = {"active_weights": active, "total_weights": total}
    except Exception as e:
        log.error(f"risk/portfolio ic_health: {e}")

    return api_success({
        "total_assets": total_assets,
        "btc_value": round(btc_value),
        "kr_value": round(kr_value),
        "us_value": round(us_value),
        "daily_var": daily_var,
        "mdd": mdd,
        "regime": regime,
        "drift_status": drift_status,
        "ic_health": ic_health,
    })


@router.get("/api/risk/portfolio")
async def api_risk_portfolio():
    """Cross-market portfolio risk summary — VaR, MDD, regime, drift, IC health."""
    try:
        return await asyncio.to_thread(_compute_risk_portfolio_sync)
    except Exception as e:
        log.error(f"risk/portfolio: {e}")
        from common.api_utils import api_error
        return api_error("포트폴리오 리스크 조회 실패")
