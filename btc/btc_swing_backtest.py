#!/usr/bin/env python3
"""
극단 공포 스윙 전략 백테스트

- 1년에 몇 번 오는 극단 공포 구간만 진입, 소액(자본의 10%) 단일 매수
- 진입: Fear&Greed ≤ 20, 일봉 RSI ≤ 30, BB 하단 근처(bb_pos ≤ 15), 거래량 ≥ 0.8배
- 청산: 손절 -5%, 트레일링 3%, 익절 +15%, 최대 보유 10일

사용: .venv/bin/python btc/btc_swing_backtest.py [days]
"""

import sys
from datetime import datetime

import pandas as pd
import requests
import pyupbit
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# ── 파라미터 ──
INVEST_RATIO = 0.10          # 진입 시 자본의 10% (소액)
FEE_BUY = 0.001
FEE_SELL = 0.001
STOP_LOSS = -0.05           # -5%
TRAILING_STOP = 0.03        # 고점 대비 -3%
TAKE_PROFIT = 0.15          # +15%
MAX_HOLD_DAYS = 10

FNG_THRESHOLD = 20          # 극단 공포
RSI_THRESHOLD = 30
BB_POS_MAX = 15             # BB 하단 근처 (0~100 중 15 이하)
VOL_RATIO_MIN = 0.8


def fetch_fear_greed_history(days: int) -> dict:
    """과거 일별 Fear & Greed Index (날짜 문자열 -> value)"""
    try:
        r = requests.get(
            f"https://api.alternative.me/fng/?limit={days}",
            timeout=10,
        )
        data = r.json()
        out = {}
        for item in data.get("data", []):
            ts = int(item.get("timestamp", 0))
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            out[date_str] = int(item.get("value", 50))
        return out
    except Exception as e:
        print(f"⚠️ F&G API 실패: {e} → RSI만 사용")
        return {}


def run_swing_backtest(days: int = 365, initial_krw: float = 3_000_000.0) -> dict:
    print(f"📊 극단 공포 스윙 백테스트 — {days}일, 초기 {initial_krw:,.0f}원 (진입당 {INVEST_RATIO*100:.0f}%)")

    # 일봉
    df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=days + 60)
    if df is None or len(df) < 50:
        print("❌ 일봉 데이터 부족")
        return {}

    df = df.reset_index()
    df.rename(columns={"index": "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    close = df["close"]
    high = df["high"]
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    bb_width = df["bb_upper"] - df["bb_lower"]
    df["bb_pos"] = ((close - df["bb_lower"]) / bb_width.replace(0, 1) * 100)
    df["vol20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = (df["volume"] / df["vol20"]).fillna(1.0)

    fng_by_date = fetch_fear_greed_history(days + 60)

    krw = float(initial_krw)
    btc = 0.0
    entry_price = 0.0
    entry_idx = -1
    entry_date = ""
    highest_since_entry = 0.0
    trades = []

    for i in range(30, len(df)):
        row = df.iloc[i]
        date_str = row["date"]
        price = float(row["close"])
        high_i = float(row["high"])
        rsi = row["rsi"]
        bb_pos = row["bb_pos"]
        vol_ratio = row["vol_ratio"]
        fng = fng_by_date.get(date_str)

        if pd.isna(rsi) or pd.isna(bb_pos) or bb_pos < 0 or bb_pos > 100:
            continue

        # ── 보유 중: 청산 체크 ──
        if btc > 0 and entry_idx >= 0:
            ret = (price - entry_price) / entry_price
            ret_net = ret - FEE_BUY - FEE_SELL
            hold_days = i - entry_idx

            if highest_since_entry <= 0:
                highest_since_entry = price
            highest_since_entry = max(highest_since_entry, high_i)

            sell_reason = None
            if ret_net <= STOP_LOSS:
                sell_reason = "손절"
            elif ret_net >= TAKE_PROFIT:
                sell_reason = "익절"
            elif hold_days >= MAX_HOLD_DAYS:
                sell_reason = "타임컷"
            elif highest_since_entry > 0:
                drop = (highest_since_entry - price) / highest_since_entry
                if drop >= TRAILING_STOP and ret_net > 0:
                    sell_reason = "트레일링"

            if sell_reason:
                fee = btc * price * FEE_SELL
                krw += btc * price - fee
                pnl_pct = ret_net * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date_str,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "pnl_pct": round(pnl_pct, 2),
                    "reason": sell_reason,
                    "hold_days": hold_days,
                })
                btc = 0.0
                entry_price = 0.0
                entry_idx = -1
                highest_since_entry = 0.0
                continue

            # 고점 갱신만
            continue

        # ── 미보유: 극단 공포 진입 조건 ──
        if btc > 0 or krw < 50000:
            continue

        fng_ok = (fng is not None and fng <= FNG_THRESHOLD) or (fng is None and rsi <= 25)
        if not fng_ok:
            continue
        if rsi > RSI_THRESHOLD:
            continue
        if bb_pos > BB_POS_MAX:
            continue
        if vol_ratio < VOL_RATIO_MIN:
            continue

        # 진입 (자본의 10%)
        invest = krw * INVEST_RATIO
        if invest < 50000:
            continue
        fee = invest * FEE_BUY
        btc = (invest - fee) / price
        krw -= invest
        entry_price = price
        entry_idx = i
        entry_date = date_str
        highest_since_entry = high_i

    # 미청산 포지션 마감
    if btc > 0 and len(df) > 0:
        last = df.iloc[-1]
        price = float(last["close"])
        fee = btc * price * FEE_SELL
        krw += btc * price - fee
        ret_net = (price - entry_price) / entry_price - FEE_BUY - FEE_SELL
        trades.append({
            "entry_date": entry_date,
            "exit_date": last["date"],
            "entry_price": entry_price,
            "exit_price": price,
            "pnl_pct": round(ret_net * 100, 2),
            "reason": "미청산",
            "hold_days": len(df) - entry_idx,
        })

    final = krw
    total_return = (final - initial_krw) / initial_krw * 100
    sells = [t for t in trades if "pnl_pct" in t]
    pnls = [t["pnl_pct"] for t in sells]
    wins = [p for p in pnls if p > 0]
    win_rate = (len(wins) / len(pnls) * 100) if pnls else 0.0

    print(f"\n{'='*50}")
    print(f"💰 초기자본:   {initial_krw:>15,.0f}원")
    print(f"💵 최종자본:   {final:>15,.0f}원")
    print(f"📈 총 수익률: {total_return:>14.2f}%")
    print(f"🔄 거래 횟수: {len(pnls)}회")
    print(f"🎯 승률:      {win_rate:>14.1f}%")
    if pnls:
        print(f"📊 평균 수익/거래: {sum(pnls)/len(pnls):+.2f}%")
        print(f"최고/최저:   {max(pnls):+.2f}% / {min(pnls):.2f}%")
        for t in trades:
            print(f"  {t['entry_date']} → {t['exit_date']} | {t['reason']} | {t['pnl_pct']:+.2f}% ({t.get('hold_days', 0)}일)")
    print(f"{'='*50}")

    return {
        "initial_krw": initial_krw,
        "final_krw": final,
        "total_return_pct": total_return,
        "trades": len(pnls),
        "win_rate": win_rate,
        "avg_pnl": (sum(pnls) / len(pnls)) if pnls else 0,
    }


if __name__ == "__main__":
    days = 365
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        days = int(sys.argv[1])
    run_swing_backtest(days=days)
