"""Korean stock-related API endpoints."""
import json, time as _time, asyncio
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.supabase_client import get_supabase
from common.config import (
    WORKSPACE, STRATEGY_JSON,
    STOCK_TRADING_LOG, STOCK_CHECK_LOG, STOCK_PREMARKET_LOG, STOCK_COLLECTOR_LOG,
)
from common.logger import get_logger

log = get_logger("stock_api")

supabase = get_supabase()
router = APIRouter()

_kiwoom_client = None


def _get_kiwoom():
    global _kiwoom_client
    if _kiwoom_client is None:
        try:
            import sys
            ws = str(WORKSPACE)
            if ws not in sys.path:
                sys.path.insert(0, ws)
            from stocks.kiwoom_client import KiwoomClient
            _kiwoom_client = KiwoomClient()
        except Exception as e:
            log.warn(f"Kiwoom init: {e}")
    return _kiwoom_client


def is_market_open_now() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


def _stock_name(code: str) -> str:
    if not supabase:
        return ""
    try:
        db_code = code.lstrip("A") if code.startswith("A") else code
        r = supabase.table("top50_stocks").select("stock_name").eq("stock_code", db_code).limit(1).execute().data or []
        return r[0].get("stock_name", "") if r else ""
    except Exception:
        return ""


# ── Stock page ──────────────────────────────────────────
@router.get("/stocks", response_class=HTMLResponse)
async def stocks_page():
    from btc.templates.stocks_html import STOCKS_HTML
    return STOCKS_HTML


# ----- Market summary (TradingView: unified) -----
_market_summary_cache = {"data": None, "ts": 0}
MARKET_SUMMARY_TTL = 60

def _fetch_market_summary_dict():
    import yfinance as yf
    symbols = {
        "kospi": "^KS11", "kosdaq": "^KQ11",
        "sp500": "^GSPC", "nasdaq": "^NDX", "nikkei": "^N225",
        "usdkrw": "KRW=X", "btc": "BTC-USD",
    }
    result = {}
    for key, sym in symbols.items():
        try:
            t = yf.Ticker(sym)
            try:
                info = t.fast_info
                price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
                prev = float(info.get("previousClose") or info.get("regularMarketPreviousClose") or price)
            except Exception:
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    result[key] = {"price": 0, "change": 0, "change_pct": 0}
                    continue
                last, prev_row = hist.iloc[-1], hist.iloc[-2]
                price = float(last["Close"])
                prev = float(prev_row["Close"])
            change = price - prev
            change_pct = (change / prev * 100) if prev and prev > 0 else 0
            result[key] = {"price": round(price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2)}
        except Exception as e:
            log.warn(f"market-summary {key}: {e}")
            result[key] = {"price": 0, "change": 0, "change_pct": 0}
    return result

@router.get("/api/stocks/market-summary")
async def get_market_summary():
    now = _time.time()
    if _market_summary_cache["data"] is not None and now - _market_summary_cache["ts"] < MARKET_SUMMARY_TTL:
        return _market_summary_cache["data"]
    try:
        data = _fetch_market_summary_dict()
        _market_summary_cache["data"], _market_summary_cache["ts"] = data, now
        return data
    except Exception as e:
        log.error(f"market-summary: {e}")
        return {k: {"price": 0, "change": 0, "change_pct": 0} for k in ["kospi", "kosdaq", "sp500", "nasdaq", "nikkei", "usdkrw", "btc"]}




# ── Overview cache ──────────────────────────────────────
_overview_cache = {"data": [], "ts": 0}


@router.get("/api/stocks/overview")
async def get_stocks_overview():
    now = _time.time()
    if _overview_cache["data"] and now - _overview_cache["ts"] < 10:
        return _overview_cache["data"]

    if not supabase:
        return []
    try:
        stocks = supabase.table("top50_stocks").select("*").execute().data or []
        codes = [s["stock_code"] for s in stocks]
        if not codes:
            return []

        recent_ohlcv = (
            supabase.table("daily_ohlcv")
            .select("stock_code,date,close_price,volume")
            .in_("stock_code", codes)
            .order("date", desc=True)
            .limit(len(codes) * 2)
            .execute()
            .data or []
        )

        ohlcv_by_code = defaultdict(list)
        for r in recent_ohlcv:
            ohlcv_by_code[r["stock_code"]].append(r)

        market_open = is_market_open_now()
        kiwoom = _get_kiwoom() if market_open else None

        live_prices = {}
        if kiwoom and market_open:
            try:
                account = kiwoom.get_account_evaluation()
                for h in account.get("holdings", []):
                    c = h.get("code", "")
                    p = h.get("current_price", 0) or 0
                    if c and p:
                        live_prices[c] = p
            except Exception:
                pass

        result = []
        for s in stocks:
            code = s["stock_code"]
            rows = ohlcv_by_code.get(code, [])
            rows.sort(key=lambda r: r["date"], reverse=True)

            live_p = live_prices.get(code)
            price = live_p if live_p else (rows[0]["close_price"] if rows else 0)
            prev = rows[1]["close_price"] if len(rows) > 1 else price
            change = ((price - prev) / prev * 100) if prev else 0

            result.append({
                "code": code,
                "name": s["stock_name"],
                "industry": s.get("industry", ""),
                "price": price,
                "change": round(change, 2),
                "volume": rows[0].get("volume", 0) if rows else 0,
                "is_live": bool(live_p),
            })
        result.sort(key=lambda x: abs(x["change"]), reverse=True)
        _overview_cache["data"] = result
        _overview_cache["ts"] = now
        return result
    except Exception as e:
        log.error(f"stocks overview: {e}")
        return []


@router.get("/api/stocks/price/{code}")
async def get_stock_live_price(code: str):
    db_code = code.lstrip("A") if code.startswith("A") else code
    kiwoom = _get_kiwoom()
    if kiwoom:
        try:
            price = kiwoom.get_current_price(db_code)
            if price and price > 0:
                return {"price": price, "is_live": True, "code": code}
        except Exception:
            pass
    # 키움 실패/429 시 DB 일봉 최신가 폴백
    if supabase:
        try:
            row = (
                supabase.table("daily_ohlcv")
                .select("close_price")
                .eq("stock_code", db_code)
                .order("date", desc=True)
                .limit(1)
                .execute()
                .data
            )
            if row and row[0].get("close_price") is not None:
                return {"price": float(row[0]["close_price"]), "is_live": False, "code": code}
        except Exception:
            pass
    return {"price": 0, "is_live": False, "code": code}


@router.get("/api/stocks/realtime/price/{code}")
async def get_stock_realtime_price(code: str):
    """Phase 9: KR realtime-like price snapshot."""
    try:
        from common.data import get_price_snapshot

        kiwoom = _get_kiwoom()
        snap = await asyncio.to_thread(
            get_price_snapshot,
            code,
            "kr",
            kiwoom,
        )
        snap["code"] = code
        return snap
    except Exception as e:
        log.error(f"stocks realtime price: {e}")
        return {
            "symbol": code,
            "code": code,
            "price": 0.0,
            "volume": 0.0,
            "source": "kr",
        }


@router.get("/api/stocks/realtime/orderbook/{code}")
async def get_stock_realtime_orderbook(code: str):
    """Phase 9: KR orderbook snapshot (kiwoom fallback)."""
    try:
        from common.data import fetch_kr_orderbook_snapshot

        kiwoom = _get_kiwoom()
        snap = await asyncio.to_thread(fetch_kr_orderbook_snapshot, code, kiwoom)
        snap["code"] = code
        return snap
    except Exception as e:
        log.error(f"stocks realtime orderbook: {e}")
        return {
            "symbol": code,
            "code": code,
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "source": "kiwoom_fallback",
        }


@router.get("/api/stocks/realtime/alt/{symbol}")
async def get_stock_realtime_alt_data(symbol: str):
    """Phase 9: alternative-data snapshot for KR symbol."""
    try:
        from common.data import get_alternative_data

        return await asyncio.to_thread(get_alternative_data, symbol)
    except Exception as e:
        log.error(f"stocks realtime alt_data: {e}")
        return {
            "symbol": symbol.upper(),
            "search_trend_7d": 0.0,
            "social_mentions_24h": 0,
            "sentiment_score": 0.0,
        }


@router.get("/api/stocks/chart/{code}")
async def get_stock_chart(code: str, interval: str = Query("1d")):
    db_code = code.lstrip("A") if code.startswith("A") else code
    if not supabase:
        return {"candles": [], "name": "", "code": code}
    try:
        if interval in ("5m", "10m", "1h"):
            db_interval = "5m" if interval == "10m" else interval
            raw = (
                supabase.table("intraday_ohlcv")
                .select("*")
                .eq("stock_code", db_code)
                .eq("time_interval", db_interval)
                .order("datetime", desc=True)
                .limit(200)
                .execute()
                .data
                or []
            )
            rows = sorted(raw, key=lambda r: r.get("datetime", ""))
            if not rows:
                return {"candles": [], "name": _stock_name(code), "code": code}
            candles = []
            for r in rows:
                dt = (r.get("datetime") or "")[:16]
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

        raw = supabase.table("daily_ohlcv").select("*").eq("stock_code", db_code).order("date", desc=True).limit(60).execute().data or []
        rows = sorted(raw, key=lambda r: r["date"])
        if not rows:
            return {"candles": [], "name": _stock_name(code), "code": code}
        closes = [float(r["close_price"]) for r in rows]

        bb_data = []
        for i in range(len(closes)):
            if i < 19:
                bb_data.append({"upper": None, "middle": None, "lower": None})
            else:
                window = closes[i - 19: i + 1]
                ma = sum(window) / 20
                std = (sum((c - ma) ** 2 for c in window) / 20) ** 0.5
                bb_data.append({
                    "upper": round(ma + 2 * std, 0),
                    "middle": round(ma, 0),
                    "lower": round(ma - 2 * std, 0),
                })

        rsi_data = []
        for i in range(len(closes)):
            if i < 14:
                rsi_data.append(None)
            else:
                gains, loss_list = [], []
                for j in range(i - 13, i + 1):
                    diff = closes[j] - closes[j - 1]
                    gains.append(max(diff, 0))
                    loss_list.append(max(-diff, 0))
                avg_gain = sum(gains) / 14
                avg_loss = sum(loss_list) / 14
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
        log.error(f"stock chart: {e}")
        return {"candles": [], "name": "", "code": code}


@router.get("/api/stocks/indicators/{code}")
async def get_stock_indicators(code: str):
    db_code = code.lstrip("A") if code.startswith("A") else code
    if not supabase:
        return {"error": "Supabase 미연결"}
    try:
        rows = (
            supabase.table("daily_ohlcv")
            .select("close_price,volume,date")
            .eq("stock_code", db_code)
            .order("date", desc=False)
            .limit(30)
            .execute()
            .data or []
        )
        if len(rows) < 14:
            return {"error": "데이터 부족"}

        closes = [float(r["close_price"]) for r in rows]
        volumes = [float(r.get("volume") or 0) for r in rows]

        gains, loss_list = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            loss_list.append(max(-diff, 0))
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(loss_list[-14:]) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        def ema(data, period):
            k = 2 / (period + 1)
            e = data[0]
            for d in data[1:]:
                e = d * k + e * (1 - k)
            return e

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd = round(ema12 - ema26, 0)

        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        std20 = (sum((c - ma20) ** 2 for c in closes[-20:]) / 20) ** 0.5 if len(closes) >= 20 else 0
        bb_upper = round(ma20 + 2 * std20, 0)
        bb_lower = round(ma20 - 2 * std20, 0)
        bb_pos = round((closes[-1] - bb_lower) / (bb_upper - bb_lower) * 100, 1) if (bb_upper - bb_lower) > 0 else 50

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
        log.error(f"stock indicators: {e}")
        return {"error": str(e)}


@router.get("/api/stocks/portfolio")
async def get_stocks_portfolio():
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
                by_code = defaultdict(list)
                for p in rows:
                    by_code[p["stock_code"]].append(p)
                for code, trades in by_code.items():
                    total_qty = sum(int(t.get("quantity") or 0) for t in trades)
                    total_cost = sum(float(t.get("price") or 0) * int(t.get("quantity") or 0) for t in trades)
                    avg_entry = total_cost / total_qty if total_qty > 0 else 0
                    holding = next((h for h in holdings if h.get("code") == code), None)
                    current_price = holding["current_price"] if holding else 0

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
                log.error(f"portfolio positions: {e}")
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

        total_purchase = sum(
            (p.get("avg_entry", 0) or 0) * (p.get("quantity", 0) or 0)
            for p in positions
        )
        pos_total_eval = sum(p.get("evaluation", 0) or 0 for p in positions)
        pos_pnl = pos_total_eval - total_purchase
        pos_pnl_pct = (pos_pnl / total_purchase * 100) if total_purchase > 0 else 0

        cum_pnl = summary.get("cumulative_pnl", 0) or 0
        cum_pnl_pct = summary.get("cumulative_pnl_pct", 0) or 0
        if not cum_pnl and total_purchase > 0:
            cum_pnl = round(pos_pnl, 0)
            cum_pnl_pct = round(pos_pnl_pct, 2)

        today_pnl = summary.get("today_pnl", 0) or 0
        today_pnl_pct = summary.get("today_pnl_pct", 0) or 0

        return {
            "deposit": deposit,
            "total_evaluation": pos_total_eval if pos_total_eval > 0 else total_eval,
            "estimated_asset": estimated,
            "total_purchase": round(total_purchase, 0),
            "today_pnl": today_pnl,
            "today_pnl_pct": today_pnl_pct,
            "cumulative_pnl": cum_pnl,
            "cumulative_pnl_pct": cum_pnl_pct,
            "positions": positions,
            "max_positions": 5,
            "is_market_open": market_open,
        }
    except Exception as e:
        log.error(f"portfolio: {e}")
        return {"error": str(e), "positions": [], "deposit": 0, "total_evaluation": 0, "estimated_asset": 0}


@router.get("/api/stocks/daily-pnl")
async def get_stocks_daily_pnl(days: int = Query(7, ge=1, le=31)):
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
        log.error(f"daily-pnl: {e}")
        return {"daily": []}


@router.get("/api/stocks/strategy")
async def get_stocks_strategy():
    try:
        if not STRATEGY_JSON.exists():
            return {"error": "없음", "strategy": None}
        data = json.loads(STRATEGY_JSON.read_text(encoding="utf-8"))
        return {"strategy": data}
    except Exception as e:
        return {"error": str(e), "strategy": None}


@router.get("/api/stocks/logs")
async def get_stocks_logs(source: str = Query("all")):
    sources = {
        "trading": STOCK_TRADING_LOG,
        "check": STOCK_CHECK_LOG,
        "premarket": STOCK_PREMARKET_LOG,
        "collector": STOCK_COLLECTOR_LOG,
    }
    try:
        all_lines = []
        if source == "all":
            for tag, path in sources.items():
                if not path.exists():
                    continue
                raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                for line in raw[-30:]:
                    all_lines.append(f"[{tag}] {line}")
            all_lines.sort(key=lambda l: l[l.find("[20"):l.find("]", l.find("[20"))] if "[20" in l else "")
            return {"lines": all_lines[-80:]}
        else:
            path = sources.get(source, sources["trading"])
            if not path.exists():
                return {"lines": [f"로그 없음: {path.name}"]}
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return {"lines": lines[-80:]}
    except Exception as e:
        return {"lines": [str(e)]}


@router.get("/api/stocks/trades")
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
        log.error(f"stocks trades: {e}")
        return []
