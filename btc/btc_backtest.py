#!/usr/bin/env python3
# btc_backtest.py — 추세+눌림목 매수 (R:R 손절/익절)
import pyupbit
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator


def backtest(days=90, initial_krw=1_000_000, strategy="trend_pullback"):
    print(f"📊 백테스팅 — {days}일 / 전략: {strategy}")

    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=days * 24)
    if df is None or len(df) < 100:
        print("❌ 데이터 부족")
        return 0.0, 0.0

    close = df["close"]
    df["ema20"] = EMAIndicator(close=close, window=20).ema_indicator()
    df["ema50"] = EMAIndicator(close=close, window=50).ema_indicator()
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()
    df["macd"] = MACD(close=close, window_slow=26, window_fast=12, window_sign=9).macd_diff()

    # 추세 확인 후 눌림목 매수 / 과매도 반등 매수
    strategies = {
        "trend_pullback": {
            "buy": lambda r, prev: (
                r["ema20"] > r["ema50"]
                and prev["rsi"] < 48
                and r["rsi"] > prev["rsi"]
                and r["macd"] > 0
            ),
            "stop_loss": -0.025,
            "take_profit": 0.05,
        },
        "oversold_bounce": {
            "buy": lambda r, prev: (
                prev["rsi"] < 38
                and r["rsi"] > prev["rsi"] + 2
                and r["macd"] > prev["macd"]
            ),
            "stop_loss": -0.02,
            "take_profit": 0.04,
        },
    }

    s = strategies.get(strategy, strategies["trend_pullback"])
    krw, btc = initial_krw, 0.0
    trades = []
    buy_price = 0

    for i in range(51, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        price = r["close"]
        if pd.isna(r.get("rsi")) or pd.isna(r.get("macd")) or pd.isna(prev.get("rsi")) or pd.isna(prev.get("macd")):
            continue
        if strategy == "trend_pullback" and (pd.isna(r.get("ema20")) or pd.isna(r.get("ema50"))):
            continue

        try:
            # 매수
            if s["buy"](r, prev) and krw > 5000:
                fee = krw * 0.0005
                btc = (krw - fee) / price
                buy_price = price
                trades.append({"type": "BUY", "price": price, "time": str(r.name)})
                krw = 0
            # 매도 — 손절 또는 익절 도달 시
            elif btc > 0:
                change = (price - buy_price) / buy_price
                if change <= s["stop_loss"] or change >= s["take_profit"]:
                    fee = btc * price * 0.0005
                    krw = btc * price - fee
                    pnl = change * 100
                    result = "✅익절" if change >= s["take_profit"] else "🛑손절"
                    trades.append({
                        "type": "SELL", "price": price,
                        "time": str(r.name), "pnl": round(pnl, 2), "result": result
                    })
                    btc = 0
        except (TypeError, KeyError):
            continue

    final = krw + btc * df.iloc[-1]["close"]
    profit_pct = (final - initial_krw) / initial_krw * 100
    sells = [t for t in trades if t["type"] == "SELL"]
    wins = [t for t in sells if t.get("pnl", 0) > 0]
    win_rate = len(wins) / len(sells) * 100 if sells else 0
    익절횟수 = sum(1 for t in sells if t.get("result", "") == "✅익절")
    손절횟수 = sum(1 for t in sells if t.get("result", "") == "🛑손절")

    print(f"\n{'='*45}")
    print(f"💰 초기:   {initial_krw:>15,.0f}원")
    print(f"💵 최종:   {final:>15,.0f}원")
    print(f"📈 수익률: {profit_pct:>14.2f}%")
    print(f"🔄 거래:   {len(sells)}회  ✅익절 {익절횟수}회  🛑손절 {손절횟수}회")
    print(f"🎯 승률:   {win_rate:.1f}%")
    print(f"{'='*45}")
    return profit_pct, win_rate


if __name__ == "__main__":
    for s in ["trend_pullback", "oversold_bounce"]:
        backtest(days=90, strategy=s)
        print()
