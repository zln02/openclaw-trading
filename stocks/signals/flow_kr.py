"""KR investor flow factor (Phase 15).

Signals:
- Foreign net-buy streak (5-day)
- Foreign + Institution co-buy strength
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("flow_kr")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def classify_investor_flow(rows: list[dict]) -> dict:
    clean = [r for r in rows if isinstance(r, dict)]
    if not clean:
        return {
            "signal": "NO_DATA",
            "foreign_streak_days": 0,
            "foreign_5d_sum": 0,
            "inst_5d_sum": 0,
            "retail_5d_sum": 0,
            "score": 0.0,
            "reason": "no investor flow rows",
        }

    # Assume rows in chronological order; sort by date if present.
    clean.sort(key=lambda x: str(x.get("date") or x.get("trade_date") or ""))

    recent = clean[-5:]
    foreign_5d = sum(_safe_float(r.get("foreign_net"), 0.0) for r in recent)
    inst_5d = sum(_safe_float(r.get("institution_net", r.get("inst_net")), 0.0) for r in recent)
    retail_5d = sum(_safe_float(r.get("retail_net", r.get("individual_net")), 0.0) for r in recent)

    streak = 0
    for r in reversed(clean):
        f = _safe_float(r.get("foreign_net"), 0.0)
        if f > 0:
            streak += 1
        else:
            break

    latest = clean[-1]
    latest_foreign = _safe_float(latest.get("foreign_net"), 0.0)
    latest_inst = _safe_float(latest.get("institution_net", latest.get("inst_net")), 0.0)

    score = 50.0
    reason_parts: list[str] = []

    if streak >= 5:
        score += 25.0
        reason_parts.append("foreign 5d net-buy streak")
    elif streak >= 3:
        score += 12.0
        reason_parts.append("foreign positive streak")

    if latest_foreign > 0 and latest_inst > 0:
        score += 20.0
        signal = "STRONG_BUY"
        reason_parts.append("foreign+institution co-buy")
    elif latest_foreign > 0 or latest_inst > 0:
        score += 8.0
        signal = "BUY"
    elif latest_foreign < 0 and latest_inst < 0:
        score -= 20.0
        signal = "SELL"
        reason_parts.append("foreign+institution co-sell")
    else:
        signal = "NEUTRAL"

    if foreign_5d < 0 and inst_5d < 0:
        score -= 12.0
        reason_parts.append("5d flow negative")

    score = max(0.0, min(score, 100.0))
    reason = "; ".join(reason_parts) if reason_parts else "mixed flows"

    return {
        "signal": signal,
        "foreign_streak_days": streak,
        "foreign_5d_sum": round(foreign_5d, 2),
        "inst_5d_sum": round(inst_5d, 2),
        "retail_5d_sum": round(retail_5d, 2),
        "score": round(score, 2),
        "reason": reason,
    }


@dataclass
class KRFlowSignal:
    symbol: str
    signal: str
    score: float
    foreign_streak_days: int
    foreign_5d_sum: float
    inst_5d_sum: float
    retail_5d_sum: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class KRFlowFactor:
    def __init__(self, data_fetcher: Optional[Callable[[str], list[dict]]] = None):
        self.data_fetcher = data_fetcher

    def _fetch_from_pykrx(self, symbol: str, lookback_days: int = 10) -> list[dict]:
        try:
            from pykrx import stock
        except Exception:
            return []

        code = str(symbol or "").upper().lstrip("A")
        end = date.today()
        start = end - timedelta(days=max(int(lookback_days), 5) * 2)

        try:
            df = stock.get_market_trading_volume_by_date(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code)
            if df is None or df.empty:
                return []

            rows = []
            for idx, row in df.tail(lookback_days).iterrows():
                rows.append(
                    {
                        "date": str(getattr(idx, "date", lambda: idx)()) if hasattr(idx, "date") else str(idx),
                        "foreign_net": _safe_float(row.get("외국인합계", 0.0), 0.0),
                        "institution_net": _safe_float(row.get("기관합계", 0.0), 0.0),
                        "retail_net": _safe_float(row.get("개인", 0.0), 0.0),
                    }
                )
            return rows
        except Exception as exc:
            log.warn("pykrx flow fetch failed", symbol=code, error=exc)
            return []

    def fetch(self, symbol: str, kiwoom_client=None, lookback_days: int = 10) -> list[dict]:
        if self.data_fetcher is not None:
            return self.data_fetcher(symbol)

        pykrx_rows = self._fetch_from_pykrx(symbol, lookback_days=lookback_days)
        if pykrx_rows:
            return pykrx_rows

        if kiwoom_client is not None:
            row = kiwoom_client.get_investor_trend(str(symbol).lstrip("A")) or {}
            if row:
                return [
                    {
                        "date": date.today().isoformat(),
                        "foreign_net": _safe_float(row.get("foreign_net"), 0.0),
                        "institution_net": _safe_float(row.get("inst_net"), 0.0),
                        "retail_net": _safe_float(row.get("individual_net"), 0.0),
                    }
                ]
        return []

    def analyze(self, symbol: str, kiwoom_client=None, lookback_days: int = 10) -> dict:
        rows = self.fetch(symbol, kiwoom_client=kiwoom_client, lookback_days=lookback_days)
        cls = classify_investor_flow(rows)

        out = KRFlowSignal(
            symbol=str(symbol or "").upper(),
            signal=str(cls.get("signal") or "NO_DATA"),
            score=_safe_float(cls.get("score"), 0.0),
            foreign_streak_days=_safe_int(cls.get("foreign_streak_days"), 0),
            foreign_5d_sum=_safe_float(cls.get("foreign_5d_sum"), 0.0),
            inst_5d_sum=_safe_float(cls.get("inst_5d_sum"), 0.0),
            retail_5d_sum=_safe_float(cls.get("retail_5d_sum"), 0.0),
            reason=str(cls.get("reason") or ""),
            timestamp=_utc_now_iso(),
        ).to_dict()
        out["rows"] = rows
        return out


def _cli() -> int:
    parser = argparse.ArgumentParser(description="KR investor flow factor")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--lookback", type=int, default=10)
    parser.add_argument("--sample-file", default="", help="json rows file")
    args = parser.parse_args()

    if args.sample_file:
        with open(args.sample_file, "r", encoding="utf-8") as f:
            rows = json.load(f)
        cls = classify_investor_flow(rows if isinstance(rows, list) else [])
        out = {
            "symbol": args.symbol.upper(),
            **cls,
            "timestamp": _utc_now_iso(),
            "rows": rows,
        }
    else:
        out = KRFlowFactor().analyze(args.symbol, lookback_days=args.lookback)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
