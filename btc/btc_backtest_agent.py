#!/usr/bin/env python3
"""
btc_backtest_agent.py

BTC 자동매매 에이전트(btc_trading_agent.py)의 핵심 리스크/모멘텀 로직을
단순화해서 1시간봉 기반으로 백테스트하는 스크립트.

포함 요소:
- 1시간봉 RSI / EMA20·50 / MACD / 거래량 비율
- RISK:
  - invest_ratio: 30%
  - stop_loss:   -3% (수수료 포함)
  - take_profit: +15% (수수료 포함)
  - trailing_stop: 2% (수익 1.5% 이상 구간에서 고점 대비)
  - fee_buy/sell: 0.1% / 0.1%
  - max_trades_per_day: 3

NOTE:
- 실제 에이전트의 GPT·뉴스·Fear&Greed·김치프리미엄까지 모두 반영한 것은 아니고,
  "현재 코드의 하드 리스크/분할·트레일링 구조"를 근사한 단순 버전입니다.
"""

import sys
from datetime import datetime

import numpy as np
import pyupbit
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD


RISK = {
    "invest_ratio": 0.30,
    "stop_loss": -0.03,
    "take_profit": 0.15,
    "trailing_stop": 0.02,
    "trailing_activate": 0.015,
    "max_trades_per_day": 3,
    "fee_buy": 0.001,
    "fee_sell": 0.001,
}


def backtest_agent_style(days: int = 250, initial_krw: float = 3_000_000.0):
    print(f"📊 BTC 에이전트 스타일 백테스트 — {days}일, 초기자본 {initial_krw:,.0f}원")

    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=days * 24)
    if df is None or len(df) < 100:
        print("❌ 데이터 부족")
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]

    df["ema20"] = EMAIndicator(close=close, window=20).ema_indicator()
    df["ema50"] = EMAIndicator(close=close, window=50).ema_indicator()
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()
    df["macd"] = MACD(close=close, window_slow=26, window_fast=12, window_sign=9).macd_diff()
    df["vol20"] = vol.rolling(20).mean()

    krw = float(initial_krw)
    btc = 0.0
    entry_price = 0.0
    highest_price = 0.0
    trades = []
    daily_new_trades = {}

    for i in range(60, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        price = float(row["close"])
        if np.isnan(row["rsi"]) or np.isnan(row["macd"]) or np.isnan(row["ema20"]) or np.isnan(row["ema50"]):
            continue

        date_key = row.name.strftime("%Y-%m-%d")
        daily_new_trades.setdefault(date_key, 0)

        rsi = float(row["rsi"])
        macd = float(row["macd"])
        ema20 = float(row["ema20"])
        ema50 = float(row["ema50"])
        cur_vol = float(row["volume"])
        avg_vol20 = float(row["vol20"] or 0) or cur_vol
        vol_ratio = cur_vol / avg_vol20 if avg_vol20 > 0 else 1.0

        # 포지션 보유 중일 때: 손절/익절/트레일링 스탑
        if btc > 0:
            change = (price - entry_price) / entry_price
            fee_cost = RISK["fee_buy"] + RISK["fee_sell"]
            net_change = change - fee_cost

            # 고점 갱신
            if price > highest_price:
                highest_price = price

            # 트레일링 스탑
            if net_change > RISK["trailing_activate"] and highest_price > 0:
                drop = (highest_price - price) / highest_price
                if drop >= RISK["trailing_stop"]:
                    # 매도
                    fee = btc * price * RISK["fee_sell"]
                    krw = btc * price - fee
                    pnl_pct = net_change * 100
                    trades.append(
                        {
                            "type": "SELL",
                            "time": str(row.name),
                            "price": price,
                            "pnl_pct": round(pnl_pct, 2),
                            "reason": f"TRAILING({drop*100:.1f}%)",
                        }
                    )
                    btc = 0.0
                    entry_price = 0.0
                    highest_price = 0.0
                    continue

            # 손절
            if net_change <= RISK["stop_loss"]:
                fee = btc * price * RISK["fee_sell"]
                krw = btc * price - fee
                pnl_pct = net_change * 100
                trades.append(
                    {
                        "type": "SELL",
                        "time": str(row.name),
                        "price": price,
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": "STOP_LOSS",
                    }
                )
                btc = 0.0
                entry_price = 0.0
                highest_price = 0.0
                continue

            # 고정 익절
            if net_change >= RISK["take_profit"]:
                fee = btc * price * RISK["fee_sell"]
                krw = btc * price - fee
                pnl_pct = net_change * 100
                trades.append(
                    {
                        "type": "SELL",
                        "time": str(row.name),
                        "price": price,
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": "TAKE_PROFIT",
                    }
                )
                btc = 0.0
                entry_price = 0.0
                highest_price = 0.0
                continue

        # 신규 매수 시도 (포지션 없음 + 하루 3건 이하)
        if btc == 0 and daily_new_trades[date_key] < RISK["max_trades_per_day"]:
            # 에이전트의 코드 레벨 BUY 필터를 근사:
            # - 1시간봉 UPTREND 비슷한 조건: ema20 > ema50
            # - RSI 45 이하
            # - MACD 양수
            # - 거래량 급감(0.5배 이하) 매수 금지
            if (
                ema20 > ema50
                and rsi <= 45
                and macd > 0
                and vol_ratio > 0.5
                and krw > 10_000
            ):
                invest_krw = krw * RISK["invest_ratio"]
                fee = invest_krw * RISK["fee_buy"]
                btc = (invest_krw - fee) / price
                entry_price = price
                highest_price = price
                krw = krw - invest_krw
                daily_new_trades[date_key] += 1
                trades.append(
                    {
                        "type": "BUY",
                        "time": str(row.name),
                        "price": price,
                        "invest_krw": round(invest_krw, 0),
                    }
                )

    # 마지막 시점 평가
    final = krw + btc * df["close"].iloc[-1]
    profit_pct = (final - initial_krw) / initial_krw * 100

    sells = [t for t in trades if t["type"] == "SELL"]
    pnls = [t["pnl_pct"] for t in sells if "pnl_pct" in t]
    wins = [p for p in pnls if p > 0]
    win_rate = (len(wins) / len(pnls) * 100) if pnls else 0.0

    print(f"\n{'='*48}")
    print(f"💰 초기자본:   {initial_krw:>15,.0f}원")
    print(f"💵 최종자본:   {final:>15,.0f}원")
    print(f"📈 총 수익률: {profit_pct:>14.2f}%")
    print(f"🔄 거래횟수:  {len(pnls)}회 (BUY {sum(1 for t in trades if t['type']=='BUY')}건)")
    print(f"🎯 승률:      {win_rate:>14.1f}%")
    if pnls:
        print(f"📊 평균 수익률: {sum(pnls)/len(pnls):>10.2f}%")
        print(f"최고/최저:   {max(pnls):>7.2f}% / {min(pnls):.2f}%")
    print(f"{'='*48}")

    return {
        "initial_krw": initial_krw,
        "final_krw": final,
        "profit_pct": profit_pct,
        "trades": len(pnls),
        "win_rate": win_rate,
        "avg_pnl": (sum(pnls) / len(pnls)) if pnls else 0.0,
    }


if __name__ == "__main__":
    days = 250
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        days = int(sys.argv[1])
    backtest_agent_style(days=days)

