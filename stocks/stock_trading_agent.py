#!/usr/bin/env python3
"""
주식 자동매매 에이전트
- 평일 09:00~15:30만 실행
- 장 전 전략(today_strategy.json) 기반
- 키움 모의투자 API로 실제 주문
- RSI/MACD 기술적 지표
- Supabase trade_executions 저장
- 텔레그램 알림
"""

import os, json, time, requests
from datetime import datetime
from pathlib import Path
from supabase import create_client

# env 로드
def _load_env():
    openclaw_json = Path('/home/wlsdud5035/.openclaw/openclaw.json')
    if openclaw_json.exists():
        d = json.loads(openclaw_json.read_text())
        for k, v in (d.get('env') or {}).items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
    for p in [
        Path('/home/wlsdud5035/.openclaw/.env'),
        Path('/home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env'),
    ]:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

import sys

sys.path.insert(0, str(Path(__file__).parent))
from kiwoom_client import KiwoomClient

TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
kiwoom = KiwoomClient()

# 리스크 설정
RISK = {
    "invest_per_stock": 0.10,  # 종목당 잔고의 10%
    "stop_loss": -0.03,  # 손절 -3%
    "take_profit": 0.06,  # 익절 +6%
    "min_confidence": 65,
    "max_positions": 3,  # 최대 동시 보유 종목
}


def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception as e:
        print(f'텔레그램 실패: {e}')


def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


def get_today_strategy() -> dict:
    path = Path('/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json')
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        if d.get('date') != datetime.now().date().isoformat():
            return {}
        return d
    except Exception:
        return {}


def get_indicators(code: str) -> dict:
    """키움 API + 계산으로 RSI/MACD 지표"""
    try:
        rows = (
            supabase.table('daily_ohlcv')
            .select('close_price,volume')
            .eq('stock_code', code)
            .order('date', desc=False)
            .limit(30)
            .execute()
            .data
            or []
        )

        if len(rows) < 14:
            return {}

        closes = [float(r['close_price']) for r in rows]

        # RSI 계산
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        # MACD 계산 (12/26 EMA)
        def ema(data, period):
            k = 2 / (period + 1)
            e = data[0]
            for d in data[1:]:
                e = d * k + e * (1 - k)
            return e

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd = round(ema12 - ema26, 0)

        info = kiwoom.get_stock_info(code)
        raw = info or {}
        price = float(
            raw.get('cur_prc') or raw.get('stck_prpr') or raw.get('output', {}).get('stck_prpr') or 0
        )

        return {
            'price': price,
            'rsi': rsi,
            'macd': macd,
            'close': closes[-1],
        }
    except Exception as e:
        print(f'지표 계산 실패 {code}: {e}')
        return {}


def analyze_with_ai(stock: dict, indicators: dict, strategy: dict) -> dict:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_KEY)

        picks = strategy.get('top_picks', [])
        pick = next((p for p in picks if p.get('code') == stock['code']), None)
        pick_info = (
            f"AI 장 전 전략: {pick['action']} — {pick['reason']}" if pick else "장 전 전략 없음"
        )

        prompt = f"""한국 주식 퀀트 트레이더입니다.
아래 데이터로 매매 신호를 JSON으로만 출력하세요.

[종목] {stock['name']} ({stock['code']})
[현재가] {indicators.get('price', 0):,.0f}원
[RSI] {indicators.get('rsi', 50)}
[MACD] {indicators.get('macd', 0)}
[장 전 전략] {pick_info}
[시장 전망] {strategy.get('market_outlook', '중립')} / 리스크: {strategy.get('risk_level', '보통')}

[매매 규칙]
BUY: RSI 40 이하 + MACD 양수 + 장전전략 BUY
SELL: RSI 70 이상 OR MACD 음수 전환
HOLD: 조건 미충족

[출력 JSON만]
{{"action":"BUY또는SELL또는HOLD","confidence":0~100,"reason":"한줄이유"}}"""

        res = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
            max_tokens=150,
        )
        raw = res.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        return json.loads(raw)
    except Exception as e:
        print(f'AI 분석 실패: {e}')
        return {'action': 'HOLD', 'confidence': 0, 'reason': 'AI 오류'}


def execute_trade(stock: dict, signal: dict, indicators: dict) -> dict:
    if signal.get('confidence', 0) < RISK['min_confidence']:
        return {'result': 'SKIP'}

    price = indicators.get('price', 0)
    if not price:
        return {'result': 'NO_PRICE'}

    try:
        account = kiwoom.get_account_evaluation()
        summary = account.get('summary', {})
        krw_balance = float(
            summary.get('deposit', 0) or summary.get('estimated_asset', 0) or 0
        )
    except Exception as e:
        print(f'잔고 조회 실패: {e}')
        krw_balance = 0

    if signal['action'] == 'BUY':
        try:
            positions = (
                supabase.table('trade_executions')
                .select('stock_code')
                .eq('result', 'OPEN')
                .execute()
                .data
                or []
            )
            open_codes = list(set(p['stock_code'] for p in positions))
            if len(open_codes) >= RISK['max_positions']:
                return {'result': 'MAX_POSITIONS'}
        except Exception:
            pass

        invest_krw = krw_balance * RISK['invest_per_stock']
        if invest_krw < 10000:
            return {'result': 'INSUFFICIENT_KRW'}

        quantity = int(invest_krw / price)
        if quantity < 1:
            return {'result': 'INSUFFICIENT_KRW'}

        try:
            result = kiwoom.place_order(
                stock_code=stock['code'],
                order_type='buy',
                quantity=quantity,
                price=0,
            )
            print(f'매수 주문: {result}')
        except Exception as e:
            print(f'주문 실패: {e}')
            result = {'mock': True}

        try:
            supabase.table('trade_executions').insert(
                {
                    'trade_type': 'BUY',
                    'stock_code': stock['code'],
                    'quantity': quantity,
                    'price': price,
                    'strategy': 'AI+RSI+MACD',
                    'reason': signal.get('reason', ''),
                    'result': 'OPEN',
                }
            ).execute()
        except Exception as e:
            print(f'DB 저장 실패: {e}')

        send_telegram(
            f"🟢 <b>{stock['name']} 매수</b>\n"
            f"💰 {price:,.0f}원 × {quantity}주\n"
            f"💵 투입: {invest_krw:,.0f}원\n"
            f"🎯 신뢰도: {signal.get('confidence', 0)}%\n"
            f"📝 {signal.get('reason', '')}\n"
            f"⚠️ 모의투자"
        )
        return {'result': 'BUY', 'quantity': quantity}

    elif signal['action'] == 'SELL':
        try:
            pos = (
                supabase.table('trade_executions')
                .select('*')
                .eq('stock_code', stock['code'])
                .eq('result', 'OPEN')
                .execute()
                .data
            )
            if not pos:
                return {'result': 'NO_POSITION'}

            total_qty = sum(int(p['quantity']) for p in pos)
            entry_price = float(pos[0]['price'])
            pnl_pct = (price - entry_price) / entry_price * 100

            kiwoom.place_order(
                stock_code=stock['code'],
                order_type='sell',
                quantity=total_qty,
                price=0,
            )

            for p in pos:
                pid = p.get('trade_id')
                if pid is not None:
                    supabase.table('trade_executions').update({'result': 'CLOSED'}).eq(
                        'trade_id', pid
                    ).execute()

            send_telegram(
                f"🔴 <b>{stock['name']} 매도</b>\n"
                f"💰 {price:,.0f}원 × {total_qty}주\n"
                f"📊 수익률: {pnl_pct:+.2f}%\n"
                f"📝 {signal.get('reason', '')}\n"
                f"⚠️ 모의투자"
            )
            return {'result': 'SELL', 'pnl_pct': pnl_pct}
        except Exception as e:
            print(f'매도 실패: {e}')
            return {'result': 'SELL_ERROR'}

    return {'result': 'HOLD'}


def check_stop_loss_take_profit():
    """손절/익절 자동 체크"""
    try:
        positions = (
            supabase.table('trade_executions')
            .select('*')
            .eq('result', 'OPEN')
            .execute()
            .data
            or []
        )

        for pos in positions:
            code = pos.get('stock_code')
            if not code:
                continue
            try:
                info = kiwoom.get_stock_info(code)
                raw = info or {}
                price = float(
                    raw.get('cur_prc')
                    or raw.get('stck_prpr')
                    or raw.get('output', {}).get('stck_prpr')
                    or 0
                )
                if not price:
                    continue

                entry = float(pos.get('price', 0))
                if not entry:
                    continue
                chg = (price - entry) / entry

                name = pos.get('stock_name', code)

                if chg <= RISK['stop_loss']:
                    kiwoom.place_order(
                        stock_code=code,
                        order_type='sell',
                        quantity=int(pos.get('quantity', 0)),
                        price=0,
                    )
                    pid = pos.get('trade_id')
                    if pid is not None:
                        supabase.table('trade_executions').update(
                            {'result': 'CLOSED'}
                        ).eq('trade_id', pid).execute()
                    send_telegram(
                        f"🛑 <b>{code} 손절</b>\n"
                        f"진입: {entry:,.0f}원 → {price:,.0f}원\n"
                        f"손실: {chg*100:.2f}%\n⚠️ 모의투자"
                    )
                elif chg >= RISK['take_profit']:
                    kiwoom.place_order(
                        stock_code=code,
                        order_type='sell',
                        quantity=int(pos.get('quantity', 0)),
                        price=0,
                    )
                    pid = pos.get('trade_id')
                    if pid is not None:
                        supabase.table('trade_executions').update(
                            {'result': 'CLOSED'}
                        ).eq('trade_id', pid).execute()
                    send_telegram(
                        f"✅ <b>{code} 익절</b>\n"
                        f"진입: {entry:,.0f}원 → {price:,.0f}원\n"
                        f"수익: +{chg*100:.2f}%\n⚠️ 모의투자"
                    )
                time.sleep(0.5)
            except Exception as e:
                print(f'손절/익절 체크 실패 {code}: {e}')
    except Exception as e:
        print(f'포지션 조회 실패: {e}')


def run_trading_cycle():
    if not is_market_open():
        print(f'[{datetime.now()}] 장 외 시간 — 스킵')
        return

    print(f'\n[{datetime.now()}] 주식 매매 사이클 시작')

    check_stop_loss_take_profit()

    strategy = get_today_strategy()
    if not strategy:
        print('오늘 전략 없음 — 08:00 브리핑 실행 필요')
        return

    buy_picks = [p for p in strategy.get('top_picks', []) if p.get('action') == 'BUY']
    watch_picks = [
        p for p in strategy.get('top_picks', []) if p.get('action') == 'WATCH'
    ]
    targets = buy_picks + watch_picks

    if not targets:
        print('매수 대상 없음')
        return

    for pick in targets[:5]:
        stock = {'code': pick['code'], 'name': pick['name']}
        print(f'\n  {stock["name"]} ({stock["code"]}) 분석 중...')

        indicators = get_indicators(stock['code'])
        if not indicators:
            print('  지표 없음 — 스킵')
            continue

        print(f'  RSI: {indicators["rsi"]} / MACD: {indicators["macd"]}')

        signal = analyze_with_ai(stock, indicators, strategy)
        print(f'  신호: {signal["action"]} ({signal["confidence"]}%) — {signal["reason"]}')

        result = execute_trade(stock, signal, indicators)
        print(f'  결과: {result["result"]}')

        time.sleep(1)

    print(f'\n[{datetime.now()}] 주식 매매 사이클 완료')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        if is_market_open():
            print(f"[{datetime.now()}] 주식 1분 손절/익절 체크")
            check_stop_loss_take_profit()
        else:
            print(f"[{datetime.now()}] 장 외 시간 — 스킵")
    else:
        run_trading_cycle()
