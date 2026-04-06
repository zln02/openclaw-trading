"""README.md 실시간 트레이딩 통계 자동 업데이트 스크립트.

GitHub Actions에서 매일 KST 10:00에 실행되어 Supabase에서 실적을 읽고
README.md의 <!-- LIVE-STATS:START/END --> 마커 사이를 교체한다.

실행: python scripts/update_readme_stats.py
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone

# PYTHONPATH가 workspace root여야 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_supabase():
    """Supabase 클라이언트 — CI 환경에서는 환경변수 직접 사용."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def _calc_stats(trades: list, pnl_field: str = "pnl_pct") -> dict:
    if not trades:
        return {"trades": 0, "win_rate": "—", "avg_pnl": "—", "color": "lightgrey"}
    wins = sum(1 for t in trades if (t.get(pnl_field) or 0) > 0)
    total = len(trades)
    win_rate = wins / total * 100
    avg_pnl = sum(float(t.get(pnl_field) or 0) for t in trades) / total
    color = "brightgreen" if win_rate >= 55 else "yellow" if win_rate >= 45 else "red"
    return {
        "trades": total,
        "win_rate": f"{win_rate:.1f}%",
        "avg_pnl": f"{avg_pnl:+.2f}%",
        "color": color,
    }


def fetch_all_stats(sb) -> dict:
    """Supabase에서 BTC/KR/US 실적 조회."""
    # BTC
    btc_rows = (
        sb.table("btc_position")
        .select("pnl,entry_krw,status")
        .eq("status", "CLOSED")
        .execute()
        .data or []
    )
    btc_stats = _calc_stats(btc_rows, pnl_field="pnl")
    if btc_rows:
        total_pnl = sum(float(t.get("pnl") or 0) for t in btc_rows)
        total_inv = sum(float(t.get("entry_krw") or 0) for t in btc_rows) or 1
        btc_stats["avg_pnl"] = f"{total_pnl / total_inv * 100:+.2f}%"

    # KR
    kr_rows = (
        sb.table("trade_executions")
        .select("result,pnl_pct")
        .not_.is_("pnl_pct", "null")
        .execute()
        .data or []
    )
    kr_stats = _calc_stats(kr_rows)

    # US
    us_rows = (
        sb.table("us_trade_executions")
        .select("trade_type,pnl_pct")
        .eq("trade_type", "SELL")
        .execute()
        .data or []
    )
    us_stats = _calc_stats(us_rows)

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {"btc": btc_stats, "kr": kr_stats, "us": us_stats, "updated": updated}


def build_stats_block(stats: dict) -> str:
    """README에 삽입할 통계 테이블 생성."""
    rows = []
    for market, emoji in [("btc", "BTC"), ("kr", "KR"), ("us", "US")]:
        s = stats[market]
        rows.append(
            f"| {emoji} | {s['trades']} | {s['win_rate']} | {s['avg_pnl']} |"
        )

    return f"""<!-- LIVE-STATS:START -->
> Last updated: `{stats['updated']}` via GitHub Actions

| Market | Trades | Win Rate | Avg PnL |
|--------|--------|----------|---------|
{chr(10).join(rows)}
<!-- LIVE-STATS:END -->"""


def update_readme(stats: dict, readme_path: str = "README.md"):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    block = build_stats_block(stats)
    new_content = re.sub(
        r"<!-- LIVE-STATS:START -->.*?<!-- LIVE-STATS:END -->",
        block,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"README updated: {stats['updated']}")
        return True
    print("README unchanged — stats identical")
    return False


def main():
    sb = _get_supabase()
    if sb is None:
        print("SUPABASE_URL/KEY not set — using placeholder stats")
        stats = {
            "btc": {"trades": 0, "win_rate": "—", "avg_pnl": "—"},
            "kr": {"trades": 0, "win_rate": "—", "avg_pnl": "—"},
            "us": {"trades": 0, "win_rate": "—", "avg_pnl": "—"},
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
    else:
        stats = fetch_all_stats(sb)

    update_readme(stats)


if __name__ == "__main__":
    main()
