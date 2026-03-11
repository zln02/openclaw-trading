"""DEX/CEX BTC arbitrage monitor (Phase D-1).

Collects best-effort price snapshots from:
- Upbit KRW-BTC
- Binance BTCUSDT
- Uniswap V3 WBTC/USDC
- SushiSwap WBTC/WETH

Network failures degrade to partial snapshots instead of aborting.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from btc.signals.arb_detector import compute_kimchi_premium
from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call
from common.telegram import send_telegram

load_env()
log = get_logger("dex_price_monitor")

DEX_REPORT_PATH = BRAIN_PATH / "arb" / "dex_monitor.json"
DEX_ALERT_THRESHOLD_PCT = 0.75
DEFAULT_GAS_GWEI = 25.0
DEFAULT_ETH_USD = 3000.0
DEFAULT_GAS_LIMIT = 200_000
DEFAULT_NOTIONAL_USD = 10_000.0
DEFAULT_SLIPPAGE_BPS = 20.0

UNISWAP_POOL = "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"
SUSHI_POOL = "0xceff51756c56ceffca006cd410b03ffc46dd3a58"
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/pairs/ethereum/{pair}"
ETH_GAS_URL = "https://ethgasstation.info/api/ethgasAPI.json"
COINGECKO_ETH_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _http_json(url: str, *, params: dict | None = None, timeout: float = 5.0) -> dict | list | None:
    resp = retry_call(
        requests.get,
        args=(url,),
        kwargs={"params": params or {}, "timeout": timeout, "headers": {"User-Agent": "OpenClaw/1.0"}},
        max_attempts=2,
        base_delay=0.5,
        default=None,
    )
    if resp is None or not getattr(resp, "ok", False):
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _fetch_upbit_binance_fx() -> dict:
    upbit_krw = 0.0
    binance_usdt = 0.0
    usd_krw = 0.0

    bn = _http_json(BINANCE_TICKER_URL, params={"symbol": "BTCUSDT"}, timeout=4.0)
    if isinstance(bn, dict):
        binance_usdt = _safe_float(bn.get("price"), 0.0)

    up = _http_json(UPBIT_TICKER_URL, params={"markets": "KRW-BTC"}, timeout=4.0)
    if isinstance(up, list) and up:
        upbit_krw = _safe_float(up[0].get("trade_price"), 0.0)

    fx = _http_json(UPBIT_TICKER_URL, params={"markets": "KRW-USDT"}, timeout=4.0)
    if isinstance(fx, list) and fx:
        usd_krw = _safe_float(fx[0].get("trade_price"), 0.0)

    return {
        "upbit_krw": upbit_krw,
        "binance_usdt": binance_usdt,
        "usd_krw": usd_krw,
        "kimchi_premium_pct": compute_kimchi_premium(upbit_krw, binance_usdt, usd_krw),
    }


def _fetch_dex_pair(pair_address: str, name: str) -> dict:
    payload = _http_json(DEXSCREENER_URL.format(pair=pair_address), timeout=6.0)
    pairs = payload.get("pairs") if isinstance(payload, dict) else None
    row = pairs[0] if isinstance(pairs, list) and pairs else {}
    price_usd = _safe_float(row.get("priceUsd"), 0.0)
    liquidity = _safe_float((row.get("liquidity") or {}).get("usd"), 0.0)
    price_native = _safe_float(row.get("priceNative"), 0.0)
    return {
        "name": name,
        "pair_address": pair_address,
        "price_usd": price_usd,
        "price_native": price_native,
        "liquidity_usd": liquidity,
        "source": "dexscreener" if price_usd > 0 else "unavailable",
    }


def _fetch_gas_gwei() -> float:
    payload = _http_json(ETH_GAS_URL, timeout=4.0)
    if isinstance(payload, dict):
        fast = _safe_float(payload.get("fast"), 0.0)
        if fast > 0:
            return round(fast / 10.0, 4)
    return DEFAULT_GAS_GWEI


def _fetch_eth_usd() -> float:
    payload = _http_json(COINGECKO_ETH_URL, params={"ids": "ethereum", "vs_currencies": "usd"}, timeout=4.0)
    if isinstance(payload, dict):
        eth = payload.get("ethereum") or {}
        usd = _safe_float(eth.get("usd"), 0.0)
        if usd > 0:
            return usd
    return DEFAULT_ETH_USD


def _estimate_gas_cost_usd(gas_gwei: float, eth_usd: float, gas_limit: int = DEFAULT_GAS_LIMIT) -> float:
    gas_eth = _safe_float(gas_gwei, DEFAULT_GAS_GWEI) * 1e-9 * gas_limit
    return round(gas_eth * _safe_float(eth_usd, DEFAULT_ETH_USD), 4)


def build_snapshot(notional_usd: float = DEFAULT_NOTIONAL_USD, slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> dict:
    cex = _fetch_upbit_binance_fx()
    uni = _fetch_dex_pair(UNISWAP_POOL, "uniswap_v3_wbtc_usdc")
    sushi = _fetch_dex_pair(SUSHI_POOL, "sushiswap_wbtc_weth")
    gas_gwei = _fetch_gas_gwei()
    eth_usd = _fetch_eth_usd()
    gas_cost_usd = _estimate_gas_cost_usd(gas_gwei, eth_usd)

    binance_usdt = _safe_float(cex.get("binance_usdt"), 0.0)
    usd_krw = _safe_float(cex.get("usd_krw"), 0.0)
    upbit_krw = _safe_float(cex.get("upbit_krw"), 0.0)
    upbit_usd = (upbit_krw / usd_krw) if upbit_krw > 0 and usd_krw > 0 else 0.0

    dex_candidates = [row for row in (uni, sushi) if _safe_float(row.get("price_usd"), 0.0) > 0]
    best_dex = max(dex_candidates, key=lambda row: _safe_float(row.get("liquidity_usd"), 0.0), default={"name": "unavailable", "price_usd": 0.0, "liquidity_usd": 0.0})
    dex_usd = _safe_float(best_dex.get("price_usd"), 0.0)

    upbit_premium_pct = compute_kimchi_premium(upbit_krw, binance_usdt, usd_krw)
    dex_premium_pct = ((dex_usd - binance_usdt) / binance_usdt * 100.0) if dex_usd > 0 and binance_usdt > 0 else 0.0
    cross_arb_pct = ((dex_usd - upbit_usd) / upbit_usd * 100.0) if dex_usd > 0 and upbit_usd > 0 else 0.0
    spread_abs_usd = dex_usd - upbit_usd if dex_usd > 0 and upbit_usd > 0 else 0.0
    gross_profit_usd = spread_abs_usd / max(upbit_usd, 1e-9) * notional_usd if upbit_usd > 0 else 0.0
    slippage_cost_usd = _safe_float(slippage_bps, 0.0) / 10_000.0 * _safe_float(notional_usd, 0.0)
    net_profit_usd = gross_profit_usd - gas_cost_usd - slippage_cost_usd

    alert = abs(cross_arb_pct) >= DEX_ALERT_THRESHOLD_PCT and net_profit_usd > 0
    direction = "cex_to_dex" if cross_arb_pct > 0 else "dex_to_cex"
    status = "OPPORTUNITY" if alert else "MONITOR"
    if dex_usd <= 0 or binance_usdt <= 0 or upbit_usd <= 0:
        status = "PARTIAL"
        direction = "unknown"

    return {
        "timestamp": _utc_now_iso(),
        "status": status,
        "direction": direction,
        "cex": {
            "upbit_krw": round(upbit_krw, 4),
            "upbit_usd": round(upbit_usd, 6),
            "binance_usdt": round(binance_usdt, 6),
            "usd_krw": round(usd_krw, 6),
            "upbit_premium_pct": round(upbit_premium_pct, 6),
        },
        "dex": {
            "best_pair": best_dex.get("name", "unavailable"),
            "best_price_usd": round(dex_usd, 6),
            "dex_premium_pct": round(dex_premium_pct, 6),
            "uniswap_v3": uni,
            "sushiswap": sushi,
        },
        "arb": {
            "cross_arb_pct": round(cross_arb_pct, 6),
            "spread_abs_usd": round(spread_abs_usd, 6),
            "notional_usd": round(notional_usd, 2),
            "slippage_bps": round(slippage_bps, 4),
            "slippage_cost_usd": round(slippage_cost_usd, 4),
            "gas_gwei": round(gas_gwei, 4),
            "gas_cost_usd": round(gas_cost_usd, 4),
            "gross_profit_usd": round(gross_profit_usd, 4),
            "net_profit_usd": round(net_profit_usd, 4),
        },
        "thresholds": {
            "alert_cross_arb_pct": DEX_ALERT_THRESHOLD_PCT,
            "default_gas_limit": DEFAULT_GAS_LIMIT,
        },
    }


def save_snapshot(snapshot: dict) -> Path:
    DEX_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEX_REPORT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEX_REPORT_PATH


def maybe_notify(snapshot: dict) -> None:
    if str(snapshot.get("status") or "") != "OPPORTUNITY":
        return
    arb = snapshot.get("arb") or {}
    dex = snapshot.get("dex") or {}
    send_telegram(
        "\n".join(
            [
                "🧪 <b>DEX Arb Opportunity</b>",
                f"Direction: {snapshot.get('direction')}",
                f"Pair: {dex.get('best_pair')}",
                f"Cross Arb: {float(arb.get('cross_arb_pct', 0.0) or 0.0):+.2f}%",
                f"Net Profit: ${float(arb.get('net_profit_usd', 0.0) or 0.0):+.2f}",
            ]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="DEX/CEX price monitor")
    parser.add_argument("--notional-usd", type=float, default=DEFAULT_NOTIONAL_USD)
    parser.add_argument("--slippage-bps", type=float, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()

    snapshot = build_snapshot(notional_usd=args.notional_usd, slippage_bps=args.slippage_bps)
    path = save_snapshot(snapshot)
    log.info(
        "dex monitor snapshot saved",
        path=str(path),
        status=snapshot.get("status"),
        direction=snapshot.get("direction"),
    )
    if not args.no_send:
        maybe_notify(snapshot)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
