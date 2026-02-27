"""Universe provider for Phase 10 backtests.

Goals:
- Prefer date-aware universe snapshots (survivorship-bias free when available)
- Fall back safely to available tables in this repo
- Provide a unified interface for KR/US universes
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("quant_universe")


def _to_iso_day(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    return text


def _parse_day(value: str | None) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


@dataclass
class Sp500Membership:
    symbol: str
    start_date: Optional[date]
    end_date: Optional[date]


class UniverseProvider:
    """Date-aware universe source for walk-forward backtests."""

    def __init__(
        self,
        supabase_client=None,
        sp500_history_file: Optional[Path] = None,
    ):
        self.supabase = supabase_client or get_supabase()
        self.sp500_history_file = (
            Path(sp500_history_file)
            if sp500_history_file
            else Path(__file__).resolve().parent / "data" / "sp500_constituents_history.csv"
        )
        self._sp500_rows: Optional[List[Sp500Membership]] = None

    def get_universe(
        self,
        as_of: str | date | datetime,
        market: str = "kr",
        max_symbols: int = 200,
    ) -> List[str]:
        mk = market.lower().strip()
        as_of_iso = _to_iso_day(as_of)

        if mk == "btc":
            symbols = ["BTC-USD"]
        elif mk == "us":
            symbols = self._get_us_universe(as_of_iso)
        else:
            symbols = self._get_kr_universe(as_of_iso, max_symbols=max_symbols)

        out: List[str] = []
        seen = set()
        for sym in symbols:
            s = str(sym).strip().upper()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= max_symbols:
                break
        return out

    def get_universe_range(
        self,
        start: str | date | datetime,
        end: str | date | datetime,
        market: str = "kr",
        step_days: int = 21,
        max_symbols: int = 500,
    ) -> List[str]:
        """Union of symbols sampled through [start, end]."""
        s = _parse_day(_to_iso_day(start))
        e = _parse_day(_to_iso_day(end))
        if s is None or e is None or s > e:
            return []

        from datetime import timedelta

        ptr = s
        bag = set()
        while ptr <= e:
            for sym in self.get_universe(ptr.isoformat(), market=market, max_symbols=max_symbols):
                bag.add(sym)
            ptr += timedelta(days=max(step_days, 1))

        # ensure end date also sampled
        for sym in self.get_universe(e.isoformat(), market=market, max_symbols=max_symbols):
            bag.add(sym)

        return sorted(bag)

    def _get_kr_universe(self, as_of_iso: str, max_symbols: int = 200) -> List[str]:
        # 1) Prefer snapshot tables if they exist (survivorship-bias free intent)
        snap = self._get_kr_universe_from_snapshots(as_of_iso)
        if snap:
            return snap[:max_symbols]

        # 2) Fallback: symbols with historical rows up to as-of
        hist = self._get_kr_universe_from_ohlcv(as_of_iso, max_symbols=max_symbols)
        if hist:
            return hist[:max_symbols]

        # 3) Final fallback: current top50 table
        top50 = self._get_kr_universe_from_top50()
        if top50:
            return top50[:max_symbols]

        # 4) Static fallback for local/offline testing
        return self._kr_static_fallback()[:max_symbols]

    def _get_kr_universe_from_snapshots(self, as_of_iso: str) -> List[str]:
        if not self.supabase:
            return []

        candidates = [
            ("top50_stocks_snapshot", "snapshot_date"),
            ("top50_stocks_history", "date"),
            ("top50_stocks_daily", "date"),
        ]
        for table, date_col in candidates:
            try:
                res = (
                    self.supabase.table(table)
                    .select(f"stock_code,{date_col}")
                    .lte(date_col, as_of_iso)
                    .order(date_col, desc=True)
                    .limit(500)
                    .execute()
                )
                rows = res.data or []
                if not rows:
                    continue

                out = []
                seen = set()
                for row in rows:
                    code = str(row.get("stock_code") or "").strip()
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    out.append(code)
                if out:
                    return out
            except Exception:
                continue
        return []

    def _get_kr_universe_from_ohlcv(self, as_of_iso: str, max_symbols: int = 200) -> List[str]:
        if not self.supabase:
            return []

        try:
            rows = (
                self.supabase.table("daily_ohlcv")
                .select("stock_code,date")
                .lte("date", as_of_iso)
                .order("date", desc=True)
                .limit(max(3000, max_symbols * 20))
                .execute()
                .data
                or []
            )
            out = []
            seen = set()
            for row in rows:
                code = str(row.get("stock_code") or "").strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                out.append(code)
                if len(out) >= max_symbols:
                    break
            return out
        except Exception as exc:
            log.warn("KR universe from daily_ohlcv failed", error=exc)
            return []

    def _get_kr_universe_from_top50(self) -> List[str]:
        if not self.supabase:
            return []
        try:
            rows = self.supabase.table("top50_stocks").select("stock_code").execute().data or []
            return [str(r.get("stock_code") or "").strip() for r in rows if r.get("stock_code")]
        except Exception as exc:
            log.warn("KR universe fallback top50 failed", error=exc)
            return []

    def _kr_static_fallback(self) -> List[str]:
        # Large-cap KOSPI symbols for environments without DB snapshots.
        return [
            "005930",  # Samsung Electronics
            "000660",  # SK hynix
            "035420",  # NAVER
            "005380",  # Hyundai Motor
            "051910",  # LG Chem
            "068270",  # Celltrion
            "207940",  # Samsung Biologics
            "006400",  # Samsung SDI
            "035720",  # Kakao
            "105560",  # KB Financial
        ]

    def _load_sp500_history(self) -> List[Sp500Membership]:
        if self._sp500_rows is not None:
            return self._sp500_rows

        rows: List[Sp500Membership] = []
        p = self.sp500_history_file
        if p.exists():
            try:
                import csv

                with p.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        symbol = str(r.get("symbol") or r.get("ticker") or "").strip().upper()
                        if not symbol:
                            continue
                        start_date = _parse_day(r.get("start_date") or r.get("added") or r.get("date_added"))
                        end_date = _parse_day(r.get("end_date") or r.get("removed") or r.get("date_removed"))
                        rows.append(
                            Sp500Membership(
                                symbol=symbol,
                                start_date=start_date,
                                end_date=end_date,
                            )
                        )
            except Exception as exc:
                log.warn("sp500 history parse failed", path=str(p), error=exc)

        if not rows:
            # fallback to static large-cap universe
            fallback = [
                "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ADBE", "NFLX",
                "ORCL", "CRM", "AMD", "INTC", "QCOM", "MU", "AMAT", "LRCX", "ASML", "JPM",
                "BAC", "WFC", "GS", "MS", "C", "LLY", "JNJ", "MRK", "ABBV", "PFE",
                "UNH", "HD", "LOW", "COST", "TGT", "MCD", "SBUX", "NKE", "CAT", "BA",
                "GE", "HON", "XOM", "CVX", "SPY", "QQQ", "XLK", "XLF", "XLE", "XLV",
            ]
            rows = [Sp500Membership(symbol=s, start_date=None, end_date=None) for s in fallback]

        self._sp500_rows = rows
        return rows

    def _get_us_universe(self, as_of_iso: str) -> List[str]:
        as_of_day = _parse_day(as_of_iso)
        rows = self._load_sp500_history()
        if as_of_day is None:
            return [r.symbol for r in rows]

        out = []
        for r in rows:
            if r.start_date and as_of_day < r.start_date:
                continue
            if r.end_date and as_of_day > r.end_date:
                continue
            out.append(r.symbol)
        return out


if __name__ == "__main__":
    provider = UniverseProvider()
    today = datetime.now().date().isoformat()
    kr = provider.get_universe(today, market="kr", max_symbols=20)
    us = provider.get_universe(today, market="us", max_symbols=20)
    log.info("universe sample", as_of=today, kr=len(kr), us=len(us))
