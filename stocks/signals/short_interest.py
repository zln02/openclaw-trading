"""Short-interest factor analyzer (Phase 16)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass
class ShortInterestSignal:
    symbol: str
    short_interest_pct: float
    days_to_cover: float
    price_change_5d_pct: float
    squeeze_candidate: bool
    risk_level: str
    score: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_short_interest(
    symbol: str,
    short_interest_pct: float,
    days_to_cover: float,
    price_change_5d_pct: float,
) -> dict:
    si = max(_safe_float(short_interest_pct, 0.0), 0.0)
    dtc = max(_safe_float(days_to_cover, 0.0), 0.0)
    px = _safe_float(price_change_5d_pct, 0.0)

    score = 0.0
    reasons: list[str] = []

    if si >= 20.0:
        score += 45.0
        reasons.append("high SI%")
    elif si >= 12.0:
        score += 25.0
        reasons.append("elevated SI%")

    if dtc >= 5.0:
        score += 30.0
        reasons.append("high days-to-cover")
    elif dtc >= 3.0:
        score += 15.0

    if px > 0:
        score += min(px * 3.0, 20.0)
        reasons.append("price starting to rise")
    elif px < -5.0:
        score -= 12.0

    score = max(0.0, min(score, 100.0))
    squeeze = (si >= 20.0 and dtc >= 5.0 and px > 0)

    if score >= 70:
        level = "HIGH"
    elif score >= 45:
        level = "MEDIUM"
    else:
        level = "LOW"

    reason = "; ".join(reasons) if reasons else "no squeeze setup"

    return ShortInterestSignal(
        symbol=str(symbol or "").upper(),
        short_interest_pct=round(si, 6),
        days_to_cover=round(dtc, 6),
        price_change_5d_pct=round(px, 6),
        squeeze_candidate=bool(squeeze),
        risk_level=level,
        score=round(score, 6),
        reason=reason,
        timestamp=_utc_now_iso(),
    ).to_dict()


class ShortInterestAnalyzer:
    def fetch_yfinance(self, symbol: str) -> dict:
        try:
            import yfinance as yf
        except Exception:
            return {}

        sym = str(symbol or "").upper()
        try:
            tk = yf.Ticker(sym)
            info = tk.info or {}
            si_ratio = _safe_float(info.get("shortPercentOfFloat"), 0.0)
            si_pct = si_ratio * 100.0 if si_ratio <= 1 else si_ratio
            dtc = _safe_float(info.get("shortRatio"), 0.0)

            hist = tk.history(period="7d")
            px_change = 0.0
            if hist is not None and not hist.empty and len(hist) >= 2:
                start = _safe_float(hist["Close"].iloc[0], 0.0)
                end = _safe_float(hist["Close"].iloc[-1], 0.0)
                if start > 0:
                    px_change = (end / start - 1.0) * 100.0

            return {
                "short_interest_pct": si_pct,
                "days_to_cover": dtc,
                "price_change_5d_pct": px_change,
            }
        except Exception:
            return {}

    def analyze(
        self,
        symbol: str,
        short_interest_pct: float | None = None,
        days_to_cover: float | None = None,
        price_change_5d_pct: float | None = None,
    ) -> dict:
        if short_interest_pct is None or days_to_cover is None or price_change_5d_pct is None:
            fetched = self.fetch_yfinance(symbol)
            short_interest_pct = _safe_float(fetched.get("short_interest_pct"), 0.0)
            days_to_cover = _safe_float(fetched.get("days_to_cover"), 0.0)
            price_change_5d_pct = _safe_float(fetched.get("price_change_5d_pct"), 0.0)

        return evaluate_short_interest(
            symbol=symbol,
            short_interest_pct=short_interest_pct,
            days_to_cover=days_to_cover,
            price_change_5d_pct=price_change_5d_pct,
        )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Short interest analyzer")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--si", type=float, default=None, help="short interest pct")
    parser.add_argument("--dtc", type=float, default=None, help="days to cover")
    parser.add_argument("--price-5d", type=float, default=None, help="5d price change pct")
    args = parser.parse_args()

    out = ShortInterestAnalyzer().analyze(
        symbol=args.symbol,
        short_interest_pct=args.si,
        days_to_cover=args.dtc,
        price_change_5d_pct=args.price_5d,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
