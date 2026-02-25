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
    "split_rsi":       [50,   42,   35  ],   # 완화: 45/38/30 -> 50/42/35
    "invest_ratio":     0.30,
    "stop_loss":       -0.03,
    "take_profit":      0.15,
    "trailing_stop":    0.02,
    "trailing_activate":0.015,
    "max_daily_loss":  -0.10,
    "min_confidence":   65,                  # 완화: 70 -> 65
    "max_trades_per_day": 3,
    "fee_buy":          0.001,
    "fee_sell":         0.001,
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

# ── 포지션 관리 ───────────────────────────────────
def get_open_position():
    try:
        res = supabase.table("btc_position")\
                      .select("*").eq("status", "OPEN")\
                      .order("entry_time", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def open_position(entry_price, quantity, entry_krw):
    try:
        supabase.table("btc_position").insert({
            "entry_price": entry_price,
            "entry_time":  datetime.now().isoformat(),
            "quantity":    quantity,
            "entry_krw":   entry_krw,
            "highest_price": entry_price,
            "status":      "OPEN",
        }).execute()
    except Exception as e:
        print(f"포지션 오픈 실패: {e}")

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

    prompt = f"""당신은 보수적인 비트코인 퀀트 트레이더입니다.
아래 데이터를 분석해 매매 신호를 JSON으로만 출력하세요.

[5분봉 지표]
{json.dumps(indicators, ensure_ascii=False)}

[거래량 분석]
{vol_comment}

[1시간봉 추세]
{trend_map.get(htf['trend'], '❓ 불명확')} / RSI: {htf['rsi_1h']}

[시장 심리]
{fg['msg']}

[매매 규칙 — 반드시 준수]
- BUY 조건 (모두 충족):
  1. 1시간봉 UPTREND 또는 SIDEWAYS
  2. 5분봉 RSI 45 이하
  3. 5분봉 MACD 상승 중 (양수)
  4. Fear&Greed 55 이하
  5. 거래량 0.5배 이하면 BUY 금지
     거래량 2배 이상이면 신뢰도 +10

- SELL 조건 (하나라도 해당):
  1. 1시간봉 DOWNTREND
  2. 5분봉 RSI 70 이상
  3. Fear&Greed 75 이상

- HOLD: 위 조건 미충족
- 신뢰도 65% 미만 → 무조건 HOLD

[최근 뉴스]
{news_summary}

[출력 형식 - JSON만, 다른 텍스트 금지]
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

# ── 분할 매수 단계 ────────────────────────────────
def get_split_stage(rsi: float) -> int:
    if rsi <= 35: return 3
    if rsi <= 42: return 2
    if rsi <= 50: return 1
    return 0

# ── 주문 실행 ─────────────────────────────────────
def execute_trade(signal, indicators, fg=None, volume=None) -> dict:

    # ── 코드 레벨 강제 필터 ──
    if signal["action"] == "BUY":
        if indicators["rsi"] > 55:
            print(f"⚠️ RSI {indicators['rsi']} > 55 — BUY 차단")
            return {"result": "BLOCKED_RSI"}
        if fg and fg["value"] > 60:
            print(f"⚠️ F&G {fg['value']} > 60 — BUY 차단")
            return {"result": "BLOCKED_FG"}
        # Extreme Fear(<20)이면 거래량 필터 면제
        is_extreme_fear = fg and fg["value"] <= 20
        if volume and volume["ratio"] <= 0.3 and not is_extreme_fear:
            print(f"⚠️ 거래량 {volume['ratio']}배 급감 — BUY 차단")
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

        # 고점 추적 (highest_price)
        highest = float(pos.get("highest_price") or entry_price)
        if price > highest:
            highest = price
            try:
                if not DRY_RUN:
                    supabase.table("btc_position").update(
                        {"highest_price": highest}
                    ).eq("id", pos["id"]).execute()
            except Exception as e:
                print(f"highest_price 업데이트 실패: {e}")

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
        stage      = get_split_stage(indicators["rsi"])
        invest_krw = krw_balance * RISK["split_ratios"][stage - 1]

        if invest_krw < 5000:
            return {"result": "INSUFFICIENT_KRW"}

        if not DRY_RUN:
            result = upbit.buy_market_order("KRW-BTC", invest_krw)
            qty    = float(result.get("executed_volume", 0)) or (invest_krw / price)
            open_position(price, qty, invest_krw)
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
    news       = get_news_summary()
    pos        = get_open_position()

    print(f"Fear & Greed: {fg['label']}({fg['value']})")
    print(f"1시간봉 추세: {htf['trend']}")
    print(f"거래량: {volume['label']} (평균比 {volume['ratio']}배)")
    print(f"포지션: {'있음 @ {:,}원'.format(int(pos['entry_price'])) if pos else '없음 (대기 중)'}")
    kimchi = get_kimchi_premium()
    print(f"김치 프리미엄: {kimchi:+.2f}%" if kimchi is not None else "김치 프리미엄: 조회 실패")

    # ── 룰 기반 1차 필터 (AI 전에 먼저 판단) ──
    fg_value, rsi = fg["value"], indicators["rsi"]
    volume_ratio = volume["ratio"]
    rule_signal = None

    # 1) Extreme Fear 공격 매수: F&G <= 20 + RSI <= 40
    if fg_value <= 20 and rsi <= 40 and htf["trend"] != "DOWNTREND":
        conf = 80 if fg_value <= 10 else 75 if fg_value <= 15 else 70
        rule_signal = {
            "action": "BUY", "confidence": conf,
            "reason": f"극도공포 F&G={fg_value}, RSI={rsi:.0f} [룰기반]"
        }
        print(f"🚨 룰기반 공포매수 발동: F&G={fg_value}, RSI={rsi:.0f}")

    # 2) 기술적 과매도 매수: RSI <= 30 + BB 하단 + 상승/횡보 추세
    elif rsi <= 30 and htf["trend"] in ("UPTREND", "SIDEWAYS"):
        bb_lower = indicators.get("bb_lower", 0)
        price = indicators["price"]
        if bb_lower > 0 and price <= bb_lower * 1.01:
            rule_signal = {
                "action": "BUY", "confidence": 72,
                "reason": f"과매도+BB하단 RSI={rsi:.0f} [룰기반]"
            }

    # 3) 기술적 과매수 매도 (포지션 있을 때): RSI >= 75 + 하락 추세
    elif rsi >= 75 and htf["trend"] == "DOWNTREND":
        rule_signal = {
            "action": "SELL", "confidence": 75,
            "reason": f"과매수+하락추세 RSI={rsi:.0f} [룰기반]"
        }

    # AI 분석 (룰 기반이 BUY/SELL을 발동하지 않은 경우에만)
    if rule_signal and rule_signal["action"] != "HOLD":
        signal = rule_signal
        print(f"📋 룰 기반 신호 사용: {signal['action']} conf={signal['confidence']}")
    else:
        signal = analyze_with_ai(indicators, news, fg, htf, volume)

    # ── 보조 전략 (AI 결과에 추가 보정) ──

    # 변동성 폭발: 거래량 3배 이상
    if volume_ratio >= 3.0:
        print(f"💥 거래량 폭발 감지 ({volume_ratio:.1f}배)")
        if signal["action"] == "BUY":
            signal["confidence"] = max(signal["confidence"], 75)
        elif signal["action"] == "HOLD" and indicators["macd"] > 0 and rsi < 60:
            signal["action"] = "BUY"
            signal["confidence"] = 70
            signal["reason"] = signal.get("reason", "") + " [변동성 폭발]"

    # 김치 프리미엄 활용
    if kimchi is not None:
        print(f"🇰🇷 김치 프리미엄: {kimchi:+.2f}%")
        if kimchi <= -2.0 and signal["action"] == "HOLD" and rsi < 50:
            signal["action"] = "BUY"
            signal["confidence"] = max(signal.get("confidence", 0), 70)
            signal["reason"] = signal.get("reason", "") + f" [김치 저평가 {kimchi:+.2f}%]"
        elif kimchi >= 5.0 and signal["action"] == "HOLD":
            signal["reason"] = signal.get("reason", "") + f" [김치 과열 {kimchi:+.2f}% 주의]"

    result = execute_trade(signal, indicators, fg, volume)

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
            execute_trade({"action": "HOLD", "confidence": 0, "reason": "1분 체크"}, ind, fg, vol)
            print(f"[{datetime.now()}] BTC 1분 손절/익절 체크 완료")
        else:
            print(f"[{datetime.now()}] BTC 포지션 없음 — 스킵")
    elif len(sys.argv) > 1 and sys.argv[1] == "report":
        send_hourly_report()
    else:
        run_trading_cycle()