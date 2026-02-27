"""Walk-forward backtest engine (Phase 10).

Key guarantees:
- Strategy sees only data through `data.as_of(date)` (look-ahead guard)
- Walk-forward train/test windows with sliding step
- Report includes sharpe/sortino/max_drawdown/calmar/win_rate/avg_hold_days/trades

CLI example:
    python -m quant.backtest.engine --strategy momentum --years 3
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call
from common.supabase_client import get_supabase
from quant.backtest.universe import UniverseProvider

load_env()
log = get_logger("wf_backtest")


Signal = Dict[str, float | str]
StrategyFn = Callable[[str, List[str], "AsOfData"], List[Signal] | List[str]]


def _to_iso_day(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10] if len(text) >= 10 else text


def _parse_day(value: str | date | datetime) -> date:
    text = _to_iso_day(value)
    return datetime.strptime(text, "%Y-%m-%d").date()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return float(math.sqrt(var))


@dataclass
class WalkForwardConfig:
    train_window: int = 252
    test_window: int = 63
    step: int = 21
    hold_days: int = 5
    top_n: int = 10
    max_universe: int = 200
    market: str = "kr"
    risk_free_rate: float = 0.0


class HistoricalDataPortal:
    """Historical OHLCV portal with `as_of` access only."""

    def __init__(self, market: str = "kr", supabase_client=None):
        self.market = market.lower().strip()
        self.supabase = supabase_client or get_supabase()
        self._series_cache: Dict[str, List[dict]] = {}

    def _norm_symbol(self, symbol: str) -> str:
        s = str(symbol or "").strip().upper()
        if self.market == "kr":
            return s.lstrip("A")
        return s

    def _yf_symbol(self, symbol: str) -> str:
        s = self._norm_symbol(symbol)
        if self.market == "kr":
            if s.endswith(".KS") or s.endswith(".KQ"):
                return s
            return f"{s}.KS"
        if self.market == "btc":
            return "BTC-USD"
        return s

    def _load_from_supabase(self, symbol: str) -> List[dict]:
        if not self.supabase or self.market != "kr":
            return []

        try:
            rows = (
                self.supabase.table("daily_ohlcv")
                .select("date,open_price,high_price,low_price,close_price,volume")
                .eq("stock_code", self._norm_symbol(symbol))
                .order("date", desc=False)
                .limit(5000)
                .execute()
                .data
                or []
            )
            out = []
            for r in rows:
                out.append(
                    {
                        "date": str(r.get("date") or "")[:10],
                        "open": _safe_float(r.get("open_price")),
                        "high": _safe_float(r.get("high_price")),
                        "low": _safe_float(r.get("low_price")),
                        "close": _safe_float(r.get("close_price")),
                        "volume": _safe_float(r.get("volume")),
                    }
                )
            return out
        except Exception as exc:
            log.warn("supabase series load failed", symbol=symbol, error=exc)
            return []

    def _load_from_yfinance(self, symbol: str) -> List[dict]:
        try:
            import yfinance as yf

            ticker = self._yf_symbol(symbol)
            t = yf.Ticker(ticker)
            hist = retry_call(
                t.history,
                kwargs={"period": "10y", "interval": "1d"},
                max_attempts=2,
                base_delay=1.0,
                default=None,
            )
            if hist is None or hist.empty:
                return []

            out = []
            for idx, row in hist.iterrows():
                out.append(
                    {
                        "date": str(getattr(idx, "date", lambda: idx)())[:10],
                        "open": _safe_float(row.get("Open")),
                        "high": _safe_float(row.get("High")),
                        "low": _safe_float(row.get("Low")),
                        "close": _safe_float(row.get("Close")),
                        "volume": _safe_float(row.get("Volume")),
                    }
                )
            return out
        except Exception as exc:
            log.warn("yfinance series load failed", symbol=symbol, error=exc)
            return []

    def ensure_series(self, symbol: str) -> None:
        sym = self._norm_symbol(symbol)
        if sym in self._series_cache:
            return

        rows = self._load_from_supabase(sym)
        if not rows:
            rows = self._load_from_yfinance(sym)
        self._series_cache[sym] = rows

    def get_series(self, symbol: str) -> List[dict]:
        sym = self._norm_symbol(symbol)
        self.ensure_series(sym)
        return self._series_cache.get(sym) or []

    def get_calendar(self, symbols: Iterable[str], start_iso: str, end_iso: str) -> List[str]:
        start = _to_iso_day(start_iso)
        end = _to_iso_day(end_iso)
        days = set()
        for s in symbols:
            rows = self.get_series(s)
            for r in rows:
                d = str(r.get("date") or "")[:10]
                if start <= d <= end:
                    days.add(d)
        return sorted(days)

    def as_of(self, as_of_iso: str) -> "AsOfData":
        return AsOfData(self, as_of_iso)

    def price_on_or_before(self, symbol: str, as_of_iso: str) -> float:
        rows = self.get_series(symbol)
        as_of = _to_iso_day(as_of_iso)
        last = 0.0
        for r in rows:
            d = str(r.get("date") or "")[:10]
            if d > as_of:
                break
            c = _safe_float(r.get("close"), 0.0)
            if c > 0:
                last = c
        return last


class AsOfData:
    """Read-only historical view restricted to <= as_of date."""

    def __init__(self, portal: HistoricalDataPortal, as_of_iso: str):
        self._portal = portal
        self._as_of_iso = _to_iso_day(as_of_iso)

    @property
    def as_of_date(self) -> str:
        return self._as_of_iso

    def ohlcv(self, symbol: str, lookback: int = 260) -> List[dict]:
        rows = self._portal.get_series(symbol)
        sliced = [r for r in rows if str(r.get("date") or "")[:10] <= self._as_of_iso]
        if lookback > 0:
            sliced = sliced[-lookback:]
        return sliced

    def close(self, symbol: str, lookback: int = 260) -> List[float]:
        return [_safe_float(r.get("close"), 0.0) for r in self.ohlcv(symbol, lookback=lookback)]

    def latest_price(self, symbol: str) -> float:
        rows = self.ohlcv(symbol, lookback=1)
        if not rows:
            return 0.0
        return _safe_float(rows[-1].get("close"), 0.0)


class WalkForwardBacktestEngine:
    def __init__(
        self,
        config: Optional[WalkForwardConfig] = None,
        universe_provider: Optional[UniverseProvider] = None,
        data_portal: Optional[HistoricalDataPortal] = None,
    ):
        self.config = config or WalkForwardConfig()
        self.universe_provider = universe_provider or UniverseProvider()
        self.data_portal = data_portal or HistoricalDataPortal(market=self.config.market)

    def run(
        self,
        strategy_fn: StrategyFn,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        strategy_name: str = "custom",
    ) -> dict:
        cfg = self.config
        start_iso = _to_iso_day(start_date)
        end_iso = _to_iso_day(end_date)

        if start_iso >= end_iso:
            return {"error": "invalid date range", "trades": []}

        union_universe = self.universe_provider.get_universe_range(
            start=start_iso,
            end=end_iso,
            market=cfg.market,
            step_days=cfg.step,
            max_symbols=cfg.max_universe,
        )
        if not union_universe:
            return {"error": "universe is empty", "trades": []}

        calendar = self.data_portal.get_calendar(union_universe, start_iso=start_iso, end_iso=end_iso)
        if len(calendar) < (cfg.train_window + cfg.test_window + 2):
            return {
                "error": f"not enough calendar days: {len(calendar)}",
                "calendar_days": len(calendar),
                "trades": [],
            }

        trades: List[dict] = []
        day_returns: List[float] = []
        fold_count = 0

        for anchor in range(cfg.train_window, len(calendar) - cfg.test_window, max(cfg.step, 1)):
            fold_count += 1
            train_start_idx = anchor - cfg.train_window
            train_end_idx = anchor - 1
            test_start_idx = anchor
            test_end_idx = min(anchor + cfg.test_window - 1, len(calendar) - 1)

            train_start = calendar[train_start_idx]
            train_end = calendar[train_end_idx]
            test_start = calendar[test_start_idx]
            test_end = calendar[test_end_idx]

            for idx in range(test_start_idx, test_end_idx + 1):
                signal_date = calendar[idx]
                as_of = self.data_portal.as_of(signal_date)
                universe = self.universe_provider.get_universe(
                    signal_date,
                    market=cfg.market,
                    max_symbols=cfg.max_universe,
                )
                if not universe:
                    day_returns.append(0.0)
                    continue

                raw_signals = strategy_fn(signal_date, universe, as_of)
                norm_signals = self._normalize_signals(raw_signals, top_n=cfg.top_n)
                if not norm_signals:
                    day_returns.append(0.0)
                    continue

                day_ret = 0.0
                for s in norm_signals:
                    sym = str(s["symbol"])
                    weight = _safe_float(s.get("weight"), 0.0)
                    score = _safe_float(s.get("score"), 0.0)

                    entry_price = self.data_portal.price_on_or_before(sym, signal_date)
                    if entry_price <= 0:
                        continue

                    exit_idx = min(idx + max(cfg.hold_days, 1), test_end_idx)
                    exit_date = calendar[exit_idx]
                    exit_price = self.data_portal.price_on_or_before(sym, exit_date)
                    if exit_price <= 0:
                        continue

                    ret = (exit_price / entry_price) - 1.0
                    weighted_ret = ret * weight
                    day_ret += weighted_ret

                    trades.append(
                        {
                            "fold": fold_count,
                            "strategy": strategy_name,
                            "market": cfg.market,
                            "signal_date": signal_date,
                            "train_start": train_start,
                            "train_end": train_end,
                            "test_start": test_start,
                            "test_end": test_end,
                            "symbol": sym,
                            "score": round(score, 6),
                            "weight": round(weight, 6),
                            "entry_date": signal_date,
                            "entry_price": round(entry_price, 6),
                            "exit_date": exit_date,
                            "exit_price": round(exit_price, 6),
                            "hold_days": (_parse_day(exit_date) - _parse_day(signal_date)).days,
                            "return_pct": round(ret * 100.0, 4),
                            "weighted_return_pct": round(weighted_ret * 100.0, 4),
                        }
                    )

                day_returns.append(day_ret)

        return self._build_report(
            strategy_name=strategy_name,
            start_iso=start_iso,
            end_iso=end_iso,
            calendar=calendar,
            day_returns=day_returns,
            trades=trades,
            folds=fold_count,
        )

    def _normalize_signals(self, raw_signals: List[Signal] | List[str] | None, top_n: int) -> List[dict]:
        if not raw_signals:
            return []

        rows: List[dict] = []
        for item in raw_signals:
            if isinstance(item, str):
                rows.append({"symbol": item.upper(), "score": 1.0})
                continue
            if isinstance(item, dict):
                sym = str(item.get("symbol") or "").strip().upper()
                if not sym:
                    continue
                rows.append(
                    {
                        "symbol": sym,
                        "score": _safe_float(item.get("score"), 0.0),
                        "weight": _safe_float(item.get("weight"), 0.0),
                    }
                )

        if not rows:
            return []

        dedup: Dict[str, dict] = {}
        for row in rows:
            sym = row["symbol"]
            prev = dedup.get(sym)
            if prev is None or _safe_float(row.get("score"), 0.0) > _safe_float(prev.get("score"), 0.0):
                dedup[sym] = row

        rows = sorted(dedup.values(), key=lambda r: _safe_float(r.get("score"), 0.0), reverse=True)
        rows = rows[: max(top_n, 1)]

        provided_sum = sum(max(_safe_float(r.get("weight"), 0.0), 0.0) for r in rows)
        if provided_sum > 0:
            for r in rows:
                r["weight"] = max(_safe_float(r.get("weight"), 0.0), 0.0) / provided_sum
        else:
            w = 1.0 / len(rows)
            for r in rows:
                r["weight"] = w
        return rows

    def _build_report(
        self,
        strategy_name: str,
        start_iso: str,
        end_iso: str,
        calendar: List[str],
        day_returns: List[float],
        trades: List[dict],
        folds: int,
    ) -> dict:
        sharpe = self._sharpe(day_returns)
        sortino = self._sortino(day_returns)
        max_dd = self._max_drawdown(day_returns)
        calmar = self._calmar(day_returns, max_dd)

        wins = [t for t in trades if _safe_float(t.get("return_pct"), 0.0) > 0]
        win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
        avg_hold_days = _mean([_safe_float(t.get("hold_days"), 0.0) for t in trades]) if trades else 0.0

        return {
            "strategy": strategy_name,
            "market": self.config.market,
            "start_date": start_iso,
            "end_date": end_iso,
            "calendar_days": len(calendar),
            "folds": folds,
            "train_window": self.config.train_window,
            "test_window": self.config.test_window,
            "step": self.config.step,
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "max_drawdown": round(max_dd, 4),
            "calmar": round(calmar, 4),
            "win_rate": round(win_rate, 2),
            "avg_hold_days": round(avg_hold_days, 2),
            "trades": trades,
        }

    def _sharpe(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        rf_daily = self.config.risk_free_rate / 252.0
        excess = [r - rf_daily for r in returns]
        s = _std(excess)
        if s <= 0:
            return 0.0
        return _mean(excess) / s * math.sqrt(252.0)

    def _sortino(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        rf_daily = self.config.risk_free_rate / 252.0
        excess = [r - rf_daily for r in returns]
        downside = [min(0.0, x) for x in excess]
        ds = _std(downside)
        if ds <= 0:
            return 0.0
        return _mean(excess) / ds * math.sqrt(252.0)

    def _max_drawdown(self, returns: List[float]) -> float:
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in returns:
            equity *= 1.0 + r
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
        return max_dd

    def _calmar(self, returns: List[float], max_dd: float) -> float:
        if not returns or max_dd <= 0:
            return 0.0
        equity = 1.0
        for r in returns:
            equity *= 1.0 + r
        ann = equity ** (252.0 / max(len(returns), 1)) - 1.0
        return ann / max_dd if max_dd > 0 else 0.0


def strategy_momentum(date_iso: str, universe: List[str], data: AsOfData) -> List[Signal]:
    scored = []
    for sym in universe:
        close = [x for x in data.close(sym, lookback=180) if x > 0]
        if len(close) < 70:
            continue
        mom_1m = (close[-1] / close[-22] - 1.0) if close[-22] > 0 else 0.0
        mom_3m = (close[-1] / close[-66] - 1.0) if close[-66] > 0 else 0.0
        score = mom_1m * 0.4 + mom_3m * 0.6
        if score <= 0:
            continue
        scored.append({"symbol": sym, "score": score})

    scored.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    return scored[:10]


STRATEGY_LIBRARY: Dict[str, StrategyFn] = {
    "momentum": strategy_momentum,
}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Phase 10 Walk-forward backtest engine")
    parser.add_argument("--strategy", default="momentum", help="strategy key (default: momentum)")
    parser.add_argument("--years", type=int, default=3, help="evaluation horizon in years")
    parser.add_argument("--market", default="kr", choices=["kr", "us", "btc"], help="target market")
    parser.add_argument("--train-window", type=int, default=252)
    parser.add_argument("--test-window", type=int, default=63)
    parser.add_argument("--step", type=int, default=21)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    strategy_key = str(args.strategy).strip().lower()
    strategy_fn = STRATEGY_LIBRARY.get(strategy_key)
    if strategy_fn is None:
        print(f"Unsupported strategy: {strategy_key}")
        print(f"Available: {', '.join(sorted(STRATEGY_LIBRARY.keys()))}")
        return 2

    cfg = WalkForwardConfig(
        train_window=max(args.train_window, 21),
        test_window=max(args.test_window, 5),
        step=max(args.step, 1),
        hold_days=max(args.hold_days, 1),
        top_n=max(args.top_n, 1),
        market=args.market,
    )

    today = datetime.now().date()
    start = today - timedelta(days=max(args.years, 1) * 365 + cfg.train_window + cfg.test_window)

    engine = WalkForwardBacktestEngine(config=cfg)
    report = engine.run(
        strategy_fn=strategy_fn,
        start_date=start.isoformat(),
        end_date=today.isoformat(),
        strategy_name=strategy_key,
    )

    if report.get("error"):
        print(f"[ERROR] {report['error']}")
        return 1

    print("=" * 60)
    print(f"Strategy: {report['strategy']} ({report['market']})")
    print(f"Period  : {report['start_date']} ~ {report['end_date']}")
    print(f"Windows : train={report['train_window']} test={report['test_window']} step={report['step']}")
    print(f"Folds   : {report['folds']} | Trades: {len(report.get('trades', []))}")
    print("-" * 60)
    print(f"Sharpe       : {report['sharpe']}")
    print(f"Sortino      : {report['sortino']}")
    print(f"Max Drawdown : {report['max_drawdown']}")
    print(f"Calmar       : {report['calmar']}")
    print(f"Win Rate     : {report['win_rate']}%")
    print(f"Avg Hold Days: {report['avg_hold_days']}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
