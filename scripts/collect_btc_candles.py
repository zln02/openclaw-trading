#!/usr/bin/env python3
"""BTC 캔들 데이터 수집 -> Supabase btc_candles 저장."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.logger import get_logger
from common.supabase_client import get_supabase

log = get_logger("collect_btc_candles")

try:
    import pyupbit
except ImportError:
    log.error("pyupbit 미설치")
    sys.exit(1)


def collect(interval: str = "minute5", count: int = 2000) -> int:
    sb = get_supabase()
    if not sb:
        log.error("Supabase 미연결")
        return 0

    df = pyupbit.get_ohlcv("KRW-BTC", interval=interval, count=count)
    if df is None or df.empty:
        log.warning("캔들 데이터 없음")
        return 0

    rows = []
    for ts, row in df.iterrows():
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "open_price": float(row["open"]),
                "high_price": float(row["high"]),
                "low_price": float(row["low"]),
                "close_price": float(row["close"]),
                "volume": float(row["volume"]),
                "volume_krw": float(row.get("value", 0)),
                "interval": interval,
            }
        )

    inserted = 0
    for i in range(0, len(rows), 100):
        batch = rows[i:i + 100]
        try:
            sb.table("btc_candles").upsert(
                batch,
                on_conflict="timestamp,interval",
                ignore_duplicates=True,
            ).execute()
            inserted += len(batch)
        except Exception as e:
            log.warning(f"upsert 실패 (batch {i}): {e}")

    log.info(f"BTC 캔들 수집 완료: {inserted}/{len(rows)}건 ({interval})")
    return inserted


if __name__ == "__main__":
    interval = sys.argv[1] if len(sys.argv) > 1 else "minute5"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    collect(interval=interval, count=count)
