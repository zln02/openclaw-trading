"""Cross-market correlation and concentration monitoring."""
from __future__ import annotations

import asyncio
from typing import Any

from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram

log = get_logger("cross_market_risk")


class CrossMarketRisk:
    async def calc_rolling_correlations(self, window: int = 30) -> dict[str, float]:
        def _calc() -> dict[str, float]:
            import pandas as pd
            import yfinance as yf

            tickers = {
                "btc_us": "BTC-USD",
                "kr": "^KS11",
                "us": "^GSPC",
            }
            closes = {}
            for key, symbol in tickers.items():
                hist = yf.download(symbol, period=f"{max(window * 3, 90)}d", progress=False)
                if hist is not None and not hist.empty:
                    closes[key] = hist["Close"].pct_change().dropna().tail(window)

            if len(closes) < 2:
                return {}

            df = pd.DataFrame(closes).dropna()
            if df.empty:
                return {}

            return {
                "btc_kr": round(float(df["btc_us"].corr(df["kr"])), 4) if {"btc_us", "kr"} <= set(df.columns) else 0.0,
                "btc_us": round(float(df["btc_us"].corr(df["us"])), 4) if {"btc_us", "us"} <= set(df.columns) else 0.0,
                "kr_us": round(float(df["kr"].corr(df["us"])), 4) if {"kr", "us"} <= set(df.columns) else 0.0,
            }

        return await asyncio.to_thread(_calc)

    async def get_all_positions(self) -> dict[str, dict[str, Any]]:
        supabase = get_supabase()
        if not supabase:
            return {}

        def _load() -> dict[str, dict[str, Any]]:
            btc = supabase.table("btc_position").select("id").eq("status", "OPEN").limit(1).execute().data or []
            kr = supabase.table("trade_executions").select("trade_id").eq("result", "OPEN").limit(1).execute().data or []
            us = supabase.table("us_trade_executions").select("id").eq("result", "OPEN").limit(1).execute().data or []
            return {
                "btc": {"side": "LONG" if btc else "FLAT", "count": len(btc)},
                "kr": {"side": "LONG" if kr else "FLAT", "count": len(kr)},
                "us": {"side": "LONG" if us else "FLAT", "count": len(us)},
            }

        return await asyncio.to_thread(_load)

    async def check_exposure(self) -> dict[str, Any]:
        positions = await self.get_all_positions()
        correlations = await self.calc_rolling_correlations(window=30)
        avg_corr = round(sum(correlations.values()) / len(correlations), 4) if correlations else 0.0

        risk_level = "NORMAL"
        if positions and all(item.get("side") == "LONG" for item in positions.values()) and avg_corr > 0.6:
            risk_level = "CONCENTRATED"
            await asyncio.to_thread(
                send_telegram,
                f"⚠️ Cross-market risk: 전 시장 LONG, avg correlation {avg_corr:.2f}",
            )

        return {
            "risk_level": risk_level,
            "correlations": correlations,
            "positions": positions,
            "avg_correlation": avg_corr,
        }
