"""Telegram message sender utility with retry."""
import os
import time
from typing import Optional

import requests

_last_send_ts = 0.0
_MIN_INTERVAL = 1.0  # rate-limit: 1 msg/sec


def send_telegram(msg: str, parse_mode: str = "HTML", retries: int = 2) -> bool:
    """Send a telegram message with retry and rate-limiting.

    Returns True on success, False otherwise.
    """
    global _last_send_ts
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    # rate-limit
    elapsed = time.time() - _last_send_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": parse_mode},
                timeout=10,
            )
            _last_send_ts = time.time()
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue
            return resp.ok
        except Exception:
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
    return False


def send_trade_alert(
    market: str,
    action: str,
    symbol: str,
    price: float,
    quantity: float,
    entry_reason: str,
    stop_loss: float,
    take_profit: float,
    portfolio_weight: float,
    pnl_pct: Optional[float] = None,
    symbol_name: str = "",
) -> bool:
    """매수/매도 체결 알림 — 진입근거·손절가·목표가·비중 포함.

    Args:
        market: "btc" | "kr" | "us"
        action: "매수" | "매도" | "손절" | "익절"
        stop_loss: 손절 기준가 (절대 가격)
        take_profit: 목표가 (절대 가격)
        portfolio_weight: 포트폴리오 내 비중 (0~100 %)
        pnl_pct: 수익률 — 매도/손절/익절 시에만 전달
    """
    icon = {"매수": "🟢", "매도": "🔴", "손절": "🛑", "익절": "✅"}.get(action, "📌")
    mkt = market.upper()

    if mkt == "US":
        price_str = f"${price:,.2f}"
        sl_str    = f"${stop_loss:,.2f}"
        tp_str    = f"${take_profit:,.2f}"
        qty_str   = f"{quantity:.2f} shares"
    elif mkt == "BTC":
        price_str = f"{price:,.0f}원"
        sl_str    = f"{stop_loss:,.0f}원"
        tp_str    = f"{take_profit:,.0f}원"
        qty_str   = f"{quantity:.6f} BTC"
    else:  # KR
        price_str = f"{price:,.0f}원"
        sl_str    = f"{stop_loss:,.0f}원"
        tp_str    = f"{take_profit:,.0f}원"
        qty_str   = f"{quantity:.0f}주"

    pnl_line  = f"\n📈 <b>수익률:</b> {pnl_pct:+.2f}%" if pnl_pct is not None else ""
    name_part = f" ({symbol_name})" if symbol_name else ""

    msg = (
        f"{icon} <b>[{mkt}] {action} 체결</b> — {symbol}{name_part}\n"
        f"💰 <b>체결가:</b> {price_str}  |  {qty_str}\n"
        f"📝 <b>진입근거:</b> {entry_reason}\n"
        f"🛑 <b>손절가:</b> {sl_str}\n"
        f"🎯 <b>목표가:</b> {tp_str}\n"
        f"⚖️ <b>포트폴리오 비중:</b> {portfolio_weight:.1f}%"
        f"{pnl_line}"
    )
    return send_telegram(msg)


def send_daily_report(
    date_str: str,
    win_rate: float,
    daily_pnl: float,
    cumulative_pnl: float,
    total_trades: int,
    regime: str = "N/A",
    market_breakdown: Optional[dict] = None,
) -> bool:
    """일일 리포트 — 승률·당일 PnL·누적 PnL 포함.

    Args:
        date_str: 리포트 날짜 (예: "2026-03-01")
        win_rate: 승률 (0~100 %)
        daily_pnl: 당일 손익 (원화 기준)
        cumulative_pnl: 누적 손익 (원화 기준)
        total_trades: 당일 총 거래 건수
        regime: 시장 레짐 문자열 (예: "RISK_ON")
        market_breakdown: {"btc": {"pnl": 0, "trades": 0}, "kr": ..., "us": ...}
    """
    daily_sign = "+" if daily_pnl >= 0 else ""
    cum_sign   = "+" if cumulative_pnl >= 0 else ""

    breakdown_lines = ""
    if market_breakdown:
        for mkt, info in market_breakdown.items():
            pnl    = info.get("pnl", 0)
            trades = info.get("trades", 0)
            sign   = "+" if pnl >= 0 else ""
            breakdown_lines += f"\n  • {mkt.upper()}: {sign}{pnl:,.0f}원  ({trades}건)"

    msg = (
        f"📊 <b>일일 리포트 — {date_str}</b>\n"
        f"─────────────────────\n"
        f"🏆 <b>승률:</b> {win_rate:.1f}%  ({total_trades}건 거래)\n"
        f"💵 <b>당일 PnL:</b> {daily_sign}{daily_pnl:,.0f}원\n"
        f"📈 <b>누적 PnL:</b> {cum_sign}{cumulative_pnl:,.0f}원\n"
        f"🌐 <b>시장 레짐:</b> {regime}"
        f"{breakdown_lines}"
    )
    return send_telegram(msg)


def send_emergency_alert(
    alert_type: str,
    message: str,
    detail: str = "",
) -> bool:
    """이상 상황 긴급 알림 — 연속 손절·API 에러·낙폭 경보 구분.

    Args:
        alert_type: "consecutive_loss" | "api_error" | "drawdown"
        message: 핵심 경보 메시지 (1~2줄)
        detail: 추가 상세 정보 (선택)
    """
    icons = {
        "consecutive_loss": "🚨",
        "api_error":        "⛔",
        "drawdown":         "📉",
    }
    labels = {
        "consecutive_loss": "연속 손절 경보",
        "api_error":        "API 오류 긴급 알림",
        "drawdown":         "낙폭 경보",
    }
    icon  = icons.get(alert_type, "🔴")
    label = labels.get(alert_type, "긴급 알림")
    detail_line = f"\n🔍 <b>상세:</b> {detail}" if detail else ""

    import datetime as _dt
    msg = (
        f"{icon} <b>[긴급] {label}</b>\n"
        f"─────────────────────\n"
        f"{message}"
        f"{detail_line}\n"
        f"⏰ {_dt.datetime.now().strftime('%H:%M:%S')}"
    )
    return send_telegram(msg)
