#!/usr/bin/env python3
"""
BTC 자동매매 에이전트 — 최종 완성본
기능: 5분봉+1시간봉 멀티타임프레임, Fear&Greed, 뉴스감정,
      거래량분석, 분할매수, 포지션추적, 손절/익절, 일일손실한도
"""

import os, json, sys, requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.env_loader import load_env
from common.telegram import send_telegram as _tg_send
from common.supabase_client import get_supabase

load_env()

import pyupbit
from openai import OpenAI
from btc_news_collector import get_news_summary

# ── 환경변수 ──────────────────────────────────────
UPBIT_ACCESS  = os.environ.get("UPBIT_ACCESS_KEY", "")
UPBIT_SECRET  = os.environ.get("UPBIT_SECRET_KEY", "")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY", "")
DRY_RUN       = os.environ.get("DRY_RUN", "0") == "1"

if not all([UPBIT_ACCESS, UPBIT_SECRET, OPENAI_KEY]):
    print("필수 환경변수 없음: UPBIT keys + OPENAI_API_KEY 필요", file=sys.stderr)
    sys.exit(1)
upbit   = pyupbit.Upbit(UPBIT_ACCESS, UPBIT_SECRET)
supabase = get_supabase()
client  = OpenAI(api_key=OPENAI_KEY)

# ── 리스크 설정 ───────────────────────────────────
RISK = {
    "split_ratios":    [0.30, 0.30, 0.30],
    "split_rsi":       [55,   45,   35  ],
    "invest_ratio":     0.30,
    "stop_loss":       -0.03,
    "take_profit":      0.15,
    "trailing_stop":    0.02,
    "trailing_activate":0.015,
    "max_daily_loss":  -0.10,
    "min_confidence":   65,
    "max_trades_per_day": 3,
    "fee_buy":          0.001,
    "fee_sell":         0.001,
    "buy_composite_min": 45,
    "sell_composite_max": 20,
    "timecut_days":      7,
    "cooldown_minutes":  30,
}

# ── 텔레그램 ──────────────────────────────────────
def send_telegram(msg: str):
    _tg_send(msg)

# ── 시장 데이터 ───────────────────────────────────
def get_market_data():
    return pyupbit.get_ohlcv("KRW-BTC", interval="minute5", count=200)

# ── 기술적 지표 ───────────────────────────────────
def calculate_indicators(df) -> dict:
    from ta.trend import EMAIndicator, MACD
    from ta.momentum import RSIIndicator
    from ta.volatility import BollingerBands

    close = df["close"]
    ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
    ema50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
    rsi   = RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_obj = MACD(close)
    macd  = macd_obj.macd_diff().iloc[-1]
    bb    = BollingerBands(close, window=20)

    return {
        "price":    df["close"].iloc[-1],
        "ema20":    round(ema20, 0),
        "ema50":    round(ema50, 0),
        "rsi":      round(rsi, 1),
        "macd":     round(macd, 0),
        "bb_upper": round(bb.bollinger_hband().iloc[-1], 0),
        "bb_lower": round(bb.bollinger_lband().iloc[-1], 0),
        "volume":   round(df["volume"].iloc[-1], 4),
    }

# ── 거래량 분석 ───────────────────────────────────
def get_volume_analysis(df) -> dict:
    try:
        if df is None or df.empty or "volume" not in df.columns:
            return {"ratio": 1.0, "label": "거래량 분석 실패"}
        cur   = df["volume"].iloc[-1]
        avg20 = df["volume"].rolling(20).mean().iloc[-1]
        ratio = round(cur / avg20, 2) if avg20 > 0 else 1.0

        # 5분봉 거래량이 비정상적으로 0일 때 1시간봉으로 fallback
        if ratio < 0.01:
            try:
                h_df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=30)
                if h_df is not None and not h_df.empty:
                    h_cur = h_df["volume"].iloc[-1]
                    h_avg = h_df["volume"].rolling(20).mean().iloc[-1]
                    if h_avg > 0:
                        ratio = round(h_cur / h_avg, 2)
            except Exception:
                pass

        if ratio >= 2.0:
            label = "🔥 거래량 급등 (강한 신호)"
        elif ratio >= 1.5:
            label = "📈 거래량 증가 (신호 강화)"
        elif ratio <= 0.5:
            label = "😴 거래량 급감 (신호 약함)"
        else:
            label = "➡️ 거래량 보통"

        return {"current": round(cur, 4), "avg20": round(avg20, 4),
                "ratio": ratio, "label": label}
    except Exception:
        return {"ratio": 1.0, "label": "거래량 분석 실패"}

# ── Fear & Greed ──────────────────────────────────
def get_fear_greed() -> dict:
    try:
        res   = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data  = res.json()["data"][0]
        value = int(data["value"])
        label = data["value_classification"]
        if value <= 25:
            msg = f"🔴 극도 공포({value}) — 역발상 매수 기회"
        elif value <= 45:
            msg = f"🟠 공포({value}) — 매수 우호적"
        elif value <= 55:
            msg = f"⚪ 중립({value})"
        elif value <= 75:
            msg = f"🟡 탐욕({value}) — 매수 주의"
        else:
            msg = f"🔴 극도 탐욕({value}) — 매수 금지"
        return {"value": value, "label": label, "msg": msg}
    except Exception:
        return {"value": 50, "label": "Unknown", "msg": "⚪ 중립(50)"}

# ── 1시간봉 추세 ──────────────────────────────────
def get_hourly_trend() -> dict:
    try:
        df    = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=50)
        from ta.trend import EMAIndicator
        from ta.momentum import RSIIndicator
        close = df["close"]
        ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
        rsi   = RSIIndicator(close, window=14).rsi().iloc[-1]
        price = close.iloc[-1]

        if ema20 > ema50 and price > ema20:
            trend = "UPTREND"
        elif ema20 < ema50 and price < ema20:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        return {"trend": trend, "ema20": round(ema20, 0),
                "ema50": round(ema50, 0), "rsi_1h": round(rsi, 1)}
    except Exception as e:
        print(f"1시간봉 조회 실패: {e}")
        return {"trend": "UNKNOWN", "ema20": 0, "ema50": 0, "rsi_1h": 50}

def get_kimchi_premium():
    try:
        import requests as req
        binance = req.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=3
        ).json()
        binance_price = float(binance["price"])
        usdt = req.get(
            "https://api.upbit.com/v1/ticker?markets=KRW-USDT",
            timeout=3
        ).json()
        usd_krw = float(usdt[0]["trade_price"])
        binance_krw = binance_price * usd_krw
        upbit_price = pyupbit.get_current_price("KRW-BTC")
        if upbit_price is None:
            return None
        premium = (float(upbit_price) - binance_krw) / binance_krw * 100
        return round(premium, 2)
    except Exception as e:
        print(f"[ERROR] 김치 프리미엄: {e}")
        return None

# ── 일봉 모멘텀 분석 ─────────────────────────────
def get_daily_momentum() -> dict:
    """yfinance BTC-USD 일봉으로 RSI/BB/거래량/수익률 분석."""
    try:
        import yfinance as yf
        df = yf.download("BTC-USD", period="90d", interval="1d", progress=False)
        if df.empty:
            return {"rsi_d": 50, "bb_pct": 50, "vol_ratio_d": 1.0,
                    "ret_7d": 0, "ret_30d": 0}
        close = df["Close"].squeeze()
        from ta.momentum import RSIIndicator
        from ta.volatility import BollingerBands
        rsi_d = RSIIndicator(close, window=14).rsi().iloc[-1]
        bb = BollingerBands(close, window=20)
        bb_h, bb_l = bb.bollinger_hband().iloc[-1], bb.bollinger_lband().iloc[-1]
        bb_pct = (close.iloc[-1] - bb_l) / (bb_h - bb_l) * 100 if bb_h > bb_l else 50
        vol = df["Volume"].squeeze()
        vol_avg = vol.rolling(20).mean().iloc[-1]
        vol_ratio_d = vol.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
        ret_7d = (close.iloc[-1] / close.iloc[-8] - 1) * 100 if len(close) > 8 else 0
        ret_30d = (close.iloc[-1] / close.iloc[-31] - 1) * 100 if len(close) > 31 else 0
        return {
            "rsi_d": round(float(rsi_d), 1),
            "bb_pct": round(float(bb_pct), 1),
            "vol_ratio_d": round(float(vol_ratio_d), 2),
            "ret_7d": round(float(ret_7d), 1),
            "ret_30d": round(float(ret_30d), 1),
        }
    except Exception as e:
        print(f"일봉 모멘텀 조회 실패: {e}")
        return {"rsi_d": 50, "bb_pct": 50, "vol_ratio_d": 1.0,
                "ret_7d": 0, "ret_30d": 0}


# ── BTC 복합 스코어 ──────────────────────────────
def calc_btc_composite(fg_value, rsi_d, bb_pct, vol_ratio_d, trend, ret_7d=0):
    """
    BTC 매수 복합 스코어 (0~100).
    F&G 30점 + RSI일봉 25점 + BB 15점 + 거래량 15점 + 추세 15점.
    """
    # F&G (낮을수록 매수 기회, 최대 30)
    if fg_value <= 10:   fg_sc = 30
    elif fg_value <= 20: fg_sc = 25
    elif fg_value <= 30: fg_sc = 18
    elif fg_value <= 45: fg_sc = 10
    elif fg_value <= 55: fg_sc = 5
    else:                fg_sc = 0

    # 일봉 RSI (낮을수록 매수, 최대 25)
    if rsi_d <= 30:   rsi_sc = 25
    elif rsi_d <= 38:  rsi_sc = 20
    elif rsi_d <= 45:  rsi_sc = 15
    elif rsi_d <= 55:  rsi_sc = 8
    elif rsi_d <= 65:  rsi_sc = 3
    else:              rsi_sc = 0

    # BB 포지션 (하단일수록 매수, 최대 15)
    if bb_pct <= 10:   bb_sc = 15
    elif bb_pct <= 25: bb_sc = 12
    elif bb_pct <= 40: bb_sc = 8
    elif bb_pct <= 55: bb_sc = 4
    else:              bb_sc = 0

    # 일봉 거래량 (높을수록 확신, 최대 15)
    if vol_ratio_d >= 2.0:   vol_sc = 15
    elif vol_ratio_d >= 1.5: vol_sc = 12
    elif vol_ratio_d >= 1.0: vol_sc = 8
    elif vol_ratio_d >= 0.6: vol_sc = 4
    else:                    vol_sc = 0

    # 추세 (최대 15)
    if trend == "UPTREND":    tr_sc = 15
    elif trend == "SIDEWAYS": tr_sc = 8
    else:                     tr_sc = 0

    # 7일 하락 시 보너스 (과매도 반등 기대)
    bonus = 0
    if ret_7d <= -15: bonus = 5
    elif ret_7d <= -10: bonus = 3

    total = min(fg_sc + rsi_sc + bb_sc + vol_sc + tr_sc + bonus, 100)
    return {
        "total": total,
        "fg": fg_sc, "rsi": rsi_sc, "bb": bb_sc,
        "vol": vol_sc, "trend": tr_sc, "bonus": bonus,
    }


# ── 포지션 관리 ───────────────────────────────────
def get_open_position():
    try:
        res = supabase.table("btc_position")\
                      .select("*").eq("status", "OPEN")\
                      .order("entry_time", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def open_position(entry_price, quantity, entry_krw) -> bool:
    row = {
        "entry_price": entry_price,
        "entry_time":  datetime.now().isoformat(),
        "quantity":    quantity,
        "entry_krw":   entry_krw,
        "status":      "OPEN",
    }
    try:
        supabase.table("btc_position").insert({**row, "highest_price": entry_price}).execute()
        return True
    except Exception:
        pass
    try:
        supabase.table("btc_position").insert(row).execute()
        return True
    except Exception as e:
        print(f"포지션 오픈 실패: {e}")
        return False

def close_all_positions(exit_price):
    try:
        res = supabase.table("btc_position")\
                      .select("*").eq("status", "OPEN").execute()
        for pos in res.data:
            pnl     = (exit_price - pos["entry_price"]) * pos["quantity"]
            pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            supabase.table("btc_position").update({
                "status":     "CLOSED",
                "exit_price": exit_price,
                "exit_time":  datetime.now().isoformat(),
                "pnl":        round(pnl, 2),
                "pnl_pct":    round(pnl_pct, 2),
            }).eq("id", pos["id"]).execute()
    except Exception as e:
        print(f"포지션 종료 실패: {e}")

# ── 일일 손실 한도 ────────────────────────────────
def check_daily_loss() -> bool:
    try:
        today = datetime.now().date().isoformat()
        res   = supabase.table("btc_position")\
                        .select("pnl, entry_krw")\
                        .eq("status", "CLOSED")\
                        .gte("exit_time", today).execute()
        if not res.data:
            return False
        total_pnl = sum(float(r["pnl"] or 0) for r in res.data)
        total_krw = sum(float(r["entry_krw"] or 0) for r in res.data)
        if total_krw > 0 and (total_pnl / total_krw) <= RISK["max_daily_loss"]:
            send_telegram("🚨 <b>일일 손실 한도 -5% 초과</b>\n봇 자동 정지 — 내일 재시작")
            return True
    except Exception:
        pass
    return False

# ── AI 분석 ───────────────────────────────────────
def analyze_with_ai(indicators, news_summary, fg, htf, volume) -> dict:

    trend_map = {
        "UPTREND":   "📈 상승 추세 — 매수 우호적",
        "DOWNTREND": "📉 하락 추세 — 매수 금지",
        "SIDEWAYS":  "➡️ 횡보 — 신중 판단",
        "UNKNOWN":   "❓ 불명확 — HOLD 우선",
    }

    if volume["ratio"] >= 2.0:
        vol_comment = f"🔥 거래량 급등({volume['ratio']}배) — 신뢰도 높음"
    elif volume["ratio"] >= 1.5:
        vol_comment = f"📈 거래량 증가({volume['ratio']}배)"
    elif volume["ratio"] <= 0.5:
        vol_comment = f"😴 거래량 급감({volume['ratio']}배) — BUY 금지"
    else:
        vol_comment = f"➡️ 거래량 보통({volume['ratio']}배)"

    prompt = f"""당신은 비트코인 퀀트 트레이더입니다.
아래 데이터로 매매 신호를 JSON으로만 출력하세요.

[5분봉 지표]
{json.dumps(indicators, ensure_ascii=False)}

[거래량 분석]
{vol_comment}

[1시간봉 추세]
{trend_map.get(htf['trend'], '❓ 불명확')} / RSI: {htf['rsi_1h']}

[시장 심리]
{fg['msg']}

[매매 규칙]
- BUY 조건:
  1. 1시간봉 DOWNTREND가 아닐 것
  2. Fear&Greed <= 55 (공포 구간 우선 매수)
  3. 거래량 0.3배 이하면 BUY 금지 (단, F&G<=20이면 면제)
  4. 거래량 2배 이상이면 신뢰도 +10
  5. F&G <= 25 구간은 적극 매수 (역발상)

- SELL 조건 (하나라도):
  1. 1시간봉 DOWNTREND + RSI 65 이상
  2. Fear&Greed >= 75

- HOLD: 위 미충족 또는 불확실
- 신뢰도 65% 미만 → HOLD

[최근 뉴스]
{news_summary}

[출력 형식 - JSON만]
{{"action":"BUY또는SELL또는HOLD","confidence":0~100,"reason":"한줄근거"}}"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        raw  = res.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"AI 분석 실패: {e}")
        return {"action": "HOLD", "confidence": 0, "reason": "AI 오류"}

# ── 분할 매수 단계 (복합 스코어 기반) ─────────────
def get_split_stage(composite_total: float) -> int:
    """복합 스코어가 높을수록 큰 비중으로 매수."""
    if composite_total >= 70: return 3
    if composite_total >= 55: return 2
    return 1

# ── 주문 실행 ─────────────────────────────────────
def execute_trade(signal, indicators, fg=None, volume=None, comp=None) -> dict:

    # ── 코드 레벨 안전 필터 (복합 스코어 기반) ──
    if signal["action"] == "BUY":
        if fg and fg["value"] > 75:
            print(f"⚠️ F&G {fg['value']} > 75 (극도 탐욕) — BUY 차단")
            return {"result": "BLOCKED_FG"}
        is_extreme_fear = fg and fg["value"] <= 20
        if volume and volume["ratio"] <= 0.15 and not is_extreme_fear:
            print(f"⚠️ 5분봉 거래량 {volume['ratio']}x 거의 0 — BUY 차단")
            return {"result": "BLOCKED_VOLUME"}

    # ── 신뢰도 필터 ──
    if signal["confidence"] < RISK["min_confidence"]:
        return {"result": "SKIP"}

    btc_balance = upbit.get_balance("BTC") or 0
    krw_balance = upbit.get_balance("KRW") or 0
    pos         = get_open_position()
    price       = indicators["price"]

    # ── 손절/익절 + 트레일링 스탑 ──
    if btc_balance > 0.00001 and pos:
        entry_price = float(pos["entry_price"])
        change = (price - entry_price) / entry_price
        fee_cost = RISK["fee_buy"] + RISK["fee_sell"]
        net_change = change - fee_cost

        # 고점 추적 (highest_price — 컬럼 없으면 무시)
        highest = float(pos.get("highest_price") or entry_price)
        if price > highest:
            highest = price
            if not DRY_RUN:
                try:
                    supabase.table("btc_position").update(
                        {"highest_price": highest}
                    ).eq("id", pos["id"]).execute()
                except Exception:
                    pass

        # 트레일링 스탑: 수익 1.5% 이상 구간에서 고점 대비 2% 이상 하락
        if net_change > RISK["trailing_activate"] and highest > 0:
            drop = (highest - price) / highest
            if drop >= RISK["trailing_stop"]:
                if not DRY_RUN:
                    upbit.sell_market_order("KRW-BTC", btc_balance * 0.9995)
                    close_all_positions(price)
                send_telegram(
                    f"📉 <b>트레일링 스탑</b>\n"
                    f"고점: {highest:,.0f}원 → 현재가: {price:,.0f}원\n"
                    f"하락폭: {drop*100:.1f}% / 수익: {net_change*100:.2f}%"
                )
                return {"result": "TRAILING_STOP"}

        # 손절
        if net_change <= RISK["stop_loss"]:
            if not DRY_RUN:
                upbit.sell_market_order("KRW-BTC", btc_balance * 0.9995)
                close_all_positions(price)
            send_telegram(
                f"🛑 <b>손절 실행</b>\n"
                f"진입가: {pos['entry_price']:,}원\n"
                f"현재가: {price:,}원\n"
                f"손실(비용 포함): {net_change*100:.2f}%"
            )
            return {"result": "STOP_LOSS"}

        # 최대 익절
        if net_change >= RISK["take_profit"]:
            if not DRY_RUN:
                upbit.sell_market_order("KRW-BTC", btc_balance * 0.9995)
                close_all_positions(price)
            send_telegram(
                f"✅ <b>익절 실행</b>\n"
                f"진입가: {pos['entry_price']:,}원\n"
                f"현재가: {price:,}원\n"
                f"수익(비용 포함): +{net_change*100:.2f}%"
            )
            return {"result": "TAKE_PROFIT"}

    # ── 분할 매수 ──
    if signal["action"] == "BUY":
        comp_total = comp["total"] if comp else 50
        stage      = get_split_stage(comp_total)
        invest_krw = krw_balance * RISK["split_ratios"][stage - 1]

        if invest_krw < 5000:
            return {"result": "INSUFFICIENT_KRW"}

        if not DRY_RUN:
            result = upbit.buy_market_order("KRW-BTC", invest_krw)
            qty    = float(result.get("executed_volume", 0)) or (invest_krw / price)
            ok = open_position(price, qty, invest_krw)
            if not ok:
                print("⚠️ 포지션 기록 실패 → 즉시 되팔기")
                try:
                    upbit.sell_market_order("KRW-BTC", qty * 0.9995)
                except Exception as e2:
                    print(f"되팔기도 실패: {e2}")
                send_telegram("🚨 BTC 매수 후 포지션 기록 실패 → 자동 되팔기 시도")
                return {"result": "POSITION_ROLLBACK"}
        else:
            print(f"[DRY_RUN] {stage}차 매수 — {invest_krw:,.0f}원")

        send_telegram(
            f"🟢 <b>BTC {stage}차 매수</b>\n"
            f"💰 가격: {price:,}원\n"
            f"📊 RSI: {indicators['rsi']} ({stage}차)\n"
            f"💵 투입: {invest_krw:,.0f}원\n"
            f"🎯 신뢰도: {signal['confidence']}%\n"
            f"📝 {signal['reason']}"
        )
        return {"result": f"BUY_{stage}차"}

    # ── AI SELL ──
    elif signal["action"] == "SELL" and btc_balance > 0.00001:
        if not DRY_RUN:
            upbit.sell_market_order("KRW-BTC", btc_balance * 0.9995)
            close_all_positions(price)
        send_telegram(
            f"🔴 <b>BTC 매도</b>\n"
            f"💰 가격: {price:,}원\n"
            f"📊 RSI: {indicators['rsi']}\n"
            f"🎯 신뢰도: {signal['confidence']}%\n"
            f"📝 {signal['reason']}"
        )
        return {"result": "SELL"}

    return {"result": "HOLD"}

# ── Supabase 로그 ─────────────────────────────────
def save_log(indicators, signal, result):
    try:
        supabase.table("btc_trades").insert({
            "timestamp":          datetime.now().isoformat(),
            "action":             signal.get("action", "HOLD"),
            "price":              indicators["price"],
            "rsi":                indicators["rsi"],
            "macd":               indicators["macd"],
            "confidence":         signal.get("confidence", 0),
            "reason":             signal.get("reason", ""),
            "indicator_snapshot": json.dumps(indicators),
            "order_raw":          json.dumps(result),
        }).execute()
        print("✅ Supabase 저장 완료")
    except Exception as e:
        print(f"❌ Supabase 저장 실패: {e}")

# ── 메인 사이클 ───────────────────────────────────
def run_trading_cycle():

    # 일일 손실 한도 체크
    if check_daily_loss():
        print("🚨 일일 손실 한도 초과 — 사이클 스킵")
        return {"result": "DAILY_LOSS_LIMIT"}

    # 오늘 신규 매수 건수 한도 체크
    today = datetime.now().date().isoformat()
    try:
        res = supabase.table("btc_position")\
                      .select("id")\
                      .gte("entry_time", today).execute()
        today_trades = len(res.data or [])
        if today_trades >= RISK.get("max_trades_per_day", 999):
            print("오늘 BTC 매수 한도 도달 — 사이클 스킵")
            return {"result": "MAX_TRADES_PER_DAY"}
    except Exception as e:
        print(f"오늘 BTC 매수 건수 조회 실패: {e}")

    print(f"\n[{datetime.now()}] 매매 사이클 시작")

    df         = get_market_data()
    indicators = calculate_indicators(df)
    volume     = get_volume_analysis(df)
    fg         = get_fear_greed()
    htf        = get_hourly_trend()
    momentum   = get_daily_momentum()
    news       = get_news_summary()
    pos        = get_open_position()
    kimchi     = get_kimchi_premium()

    fg_value = fg["value"]
    rsi_5m   = indicators["rsi"]
    rsi_d    = momentum["rsi_d"]

    comp = calc_btc_composite(
        fg_value, rsi_d, momentum["bb_pct"],
        momentum["vol_ratio_d"], htf["trend"], momentum["ret_7d"]
    )

    print(f"Fear & Greed: {fg['label']}({fg_value})")
    print(f"1시간봉 추세: {htf['trend']} | 일봉 RSI: {rsi_d} | 5분봉 RSI: {rsi_5m}")
    print(f"BB 포지션: {momentum['bb_pct']:.0f}% | 일봉 거래량: {momentum['vol_ratio_d']}x")
    print(f"7일 수익률: {momentum['ret_7d']:+.1f}% | 30일: {momentum['ret_30d']:+.1f}%")
    print(f"복합스코어: {comp['total']}/100 (F&G:{comp['fg']} RSI:{comp['rsi']} BB:{comp['bb']} Vol:{comp['vol']} Trend:{comp['trend']} Bonus:{comp['bonus']})")
    print(f"거래량(5분봉): {volume['label']} ({volume['ratio']}x)")
    print(f"포지션: {'있음 @ {:,}원'.format(int(pos['entry_price'])) if pos else '없음 (대기 중)'}")
    if kimchi is not None:
        print(f"🇰🇷 김치 프리미엄: {kimchi:+.2f}%")

    # ── 복합 스코어 기반 매매 결정 ──
    signal = None
    buy_min = RISK["buy_composite_min"]

    # 1) 복합 스코어 매수 (핵심 로직)
    if comp["total"] >= buy_min and not pos and htf["trend"] != "DOWNTREND":
        conf = min(60 + comp["total"] - buy_min, 90)
        signal = {
            "action": "BUY", "confidence": int(conf),
            "reason": f"복합스코어 {comp['total']}/{buy_min} (F&G={fg_value}, dRSI={rsi_d}) [룰기반]"
        }
        print(f"🚨 복합스코어 매수 발동: {comp['total']}점 >= {buy_min}")

    # 2) 극단 공포 오버라이드: F&G<=15면 일봉 RSI<=55까지 매수 허용
    elif fg_value <= 15 and rsi_d <= 55 and not pos and htf["trend"] != "DOWNTREND":
        signal = {
            "action": "BUY", "confidence": 78,
            "reason": f"극도공포 오버라이드 F&G={fg_value}, dRSI={rsi_d} [룰기반]"
        }
        print(f"🚨 극도공포 오버라이드: F&G={fg_value}, dRSI={rsi_d}")

    # 3) 기술적 과매수 매도: 일봉 RSI>=75 + 하락 추세
    elif rsi_d >= 75 and htf["trend"] == "DOWNTREND" and pos:
        signal = {
            "action": "SELL", "confidence": 78,
            "reason": f"과매수+하락추세 dRSI={rsi_d:.0f} [룰기반]"
        }

    # 4) 타임컷: 보유 기간 초과 + 수익 미미
    if pos and not signal:
        from datetime import timedelta
        entry_dt = datetime.fromisoformat(pos["entry_time"].replace("Z", "+00:00")) \
            if "Z" in str(pos["entry_time"]) else datetime.fromisoformat(str(pos["entry_time"]))
        held_days = (datetime.now() - entry_dt.replace(tzinfo=None)).days
        if held_days >= RISK["timecut_days"]:
            entry_p = float(pos["entry_price"])
            cur_p = indicators["price"]
            pnl_pct = (cur_p - entry_p) / entry_p
            if pnl_pct < 0.02:
                signal = {
                    "action": "SELL", "confidence": 70,
                    "reason": f"타임컷 {held_days}일 보유, 수익 {pnl_pct*100:+.1f}% [룰기반]"
                }
                print(f"⏰ 타임컷 발동: {held_days}일, 수익 {pnl_pct*100:+.1f}%")

    # 5) 룰기반 미발동 → AI 분석
    if not signal:
        signal = analyze_with_ai(indicators, news, fg, htf, volume)

    # ── 보조 보정 ──

    # 거래량 폭발
    vol_r = volume["ratio"]
    if vol_r >= 3.0:
        print(f"💥 거래량 폭발 감지 ({vol_r:.1f}x)")
        if signal["action"] == "BUY":
            signal["confidence"] = max(signal["confidence"], 78)
        elif signal["action"] == "HOLD" and indicators["macd"] > 0 and rsi_d < 60:
            signal["action"] = "BUY"
            signal["confidence"] = 72
            signal["reason"] += " [거래량 폭발]"

    # 김치 프리미엄 저평가
    if kimchi is not None and kimchi <= -2.0 and signal["action"] == "HOLD" and rsi_d < 55:
        signal["action"] = "BUY"
        signal["confidence"] = max(signal.get("confidence", 0), 72)
        signal["reason"] += f" [김치 저평가 {kimchi:+.2f}%]"

    result = execute_trade(signal, indicators, fg, volume, comp)

    print(f"신호: {signal['action']} (신뢰도: {signal['confidence']}%) → {result['result']}")

    save_log(indicators, signal, result)
    return result

def build_hourly_summary() -> str:
    """매시 요약 텍스트 생성 (가격·포지션·오늘 손익·F&G·1시간봉 추세)."""
    try:
        df = get_market_data()
        ind = calculate_indicators(df)
        price = int(ind["price"])
        rsi = ind["rsi"]
        fg = get_fear_greed()
        htf = get_hourly_trend()
        pos = get_open_position()

        today = datetime.now().date().isoformat()
        try:
            res = supabase.table("btc_position").select("pnl").eq("status", "CLOSED").gte("exit_time", today).execute()
            today_pnl = sum(float(r["pnl"] or 0) for r in (res.data or []))
        except Exception:
            today_pnl = 0

        pos_line = "포지션 없음"
        if pos:
            entry = int(float(pos["entry_price"]))
            pos_line = f"포지션 있음 @ {entry:,}원"

        msg = (
            f"⏰ <b>BTC 매시 요약</b> {datetime.now().strftime('%m/%d %H:%M')}\n"
            f"💰 가격: {price:,}원 | RSI: {rsi}\n"
            f"📊 {pos_line}\n"
            f"📈 1시간봉: {htf['trend']} | F&G: {fg['label']}({fg['value']})\n"
            f"📉 오늘 손익: {today_pnl:+,.0f}원"
        )
        return msg
    except Exception as e:
        return f"⏰ BTC 매시 요약 생성 실패: {e}"

def send_hourly_report():
    """매시 정각 요약 리포트 — 텔레그램으로 발송 (cron 'report' 호출용)."""
    msg = build_hourly_summary()
    send_telegram(msg)
    print(f"[매시 요약 발송] {(msg[:80] + '...') if len(msg) > 80 else msg}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        pos = get_open_position()
        if pos:
            df = get_market_data()
            ind = calculate_indicators(df)
            fg = get_fear_greed()
            vol = get_volume_analysis(df)
            execute_trade({"action": "HOLD", "confidence": 0, "reason": "1분 체크"}, ind, fg, vol, None)
            print(f"[{datetime.now()}] BTC 1분 손절/익절 체크 완료")
        else:
            print(f"[{datetime.now()}] BTC 포지션 없음 — 스킵")
    elif len(sys.argv) > 1 and sys.argv[1] == "report":
        send_hourly_report()
    else:
        run_trading_cycle()