#!/usr/bin/env python3
"""
백테스트 시스템 v1.0

DB에 쌓인 daily_ohlcv 데이터로 과거 매매 시뮬레이션.
현재 전략(룰 기반)을 그대로 적용해서 성과 측정.

사용법:
    python3 stocks/backtester.py              # 전체 종목
    python3 stocks/backtester.py 005930       # 특정 종목
    python3 stocks/backtester.py --days 60    # 최근 60일
"""

import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def _load_env():
    p = Path('/home/wlsdud5035/.openclaw/openclaw.json')
    if p.exists():
        d = json.loads(p.read_text())
        for k, v in (d.get('env') or {}).items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)


_load_env()

from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# ── 전략 파라미터 (trading_agent와 동일) ──
RISK = {
    "stop_loss": -0.02,
    "take_profit": 0.10,
    "trailing_stop": 0.015,
    "trailing_activate": 0.01,
    "fee_buy": 0.00015,
    "fee_sell": 0.00015,
    "tax_sell": 0.0018,
}

RULES = {
    "buy_rsi_max": 45,
    "buy_bb_max": 40,
    "buy_vol_min": 0.7,
    "sell_rsi_min": 65,
    "sell_bb_min": 75,
}


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calc_bb_pos(closes, period=20):
    if len(closes) < period:
        return 50
    window = closes[-period:]
    ma = sum(window) / period
    std = (sum((c - ma) ** 2 for c in window) / period) ** 0.5
    upper = ma + 2 * std
    lower = ma - 2 * std
    width = upper - lower
    if width <= 0:
        return 50
    return round((closes[-1] - lower) / width * 100, 1)


def calc_vol_ratio(volumes, period=20):
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1 : -1]) / period
    return round(volumes[-1] / avg, 2) if avg > 0 else 1.0


def should_buy(closes, volumes):
    """룰 기반 매수 판단"""
    rsi = calc_rsi(closes)
    bb = calc_bb_pos(closes)
    vol = calc_vol_ratio(volumes)

    if vol < RULES['buy_vol_min']:
        return False, rsi, bb, vol
    if rsi <= RULES['buy_rsi_max'] and bb <= RULES['buy_bb_max']:
        return True, rsi, bb, vol
    if rsi <= 35:  # 공포 매수
        return True, rsi, bb, vol
    return False, rsi, bb, vol


def should_sell(closes):
    """룰 기반 매도 판단"""
    rsi = calc_rsi(closes)
    bb = calc_bb_pos(closes)
    return rsi >= RULES['sell_rsi_min'] and bb >= RULES['sell_bb_min']


def run_backtest(stock_code: str, days: int = 30) -> dict:
    """단일 종목 백테스트"""
    if not supabase:
        return {"error": "Supabase 연결 안 됨"}

    rows = (
        supabase.table('daily_ohlcv')
        .select('date,close_price,volume')
        .eq('stock_code', stock_code)
        .order('date', desc=False)
        .limit(days + 30)  # 지표 계산용 여유분
        .execute()
        .data
        or []
    )

    if len(rows) < 30:
        return {'error': f'데이터 부족: {len(rows)}일'}

    closes = [float(r['close_price']) for r in rows]
    volumes = [float(r.get('volume', 0)) for r in rows]
    dates = [r['date'] for r in rows]

    # ── 시뮬레이션 ──
    trades = []
    position = None  # {'entry_price': x, 'entry_date': d, 'highest': x}
    fee_total = RISK['fee_buy'] + RISK['fee_sell'] + RISK['tax_sell']

    start_idx = 25  # 지표 계산에 최소 25일 필요

    for i in range(start_idx, len(closes)):
        price = closes[i]
        date = dates[i]
        hist_closes = closes[: i + 1]
        hist_volumes = volumes[: i + 1]

        if position is None:
            # 매수 판단
            buy, rsi, bb, vol = should_buy(hist_closes, hist_volumes)
            if buy:
                position = {
                    'entry_price': price,
                    'entry_date': date,
                    'highest': price,
                }
        else:
            # 고점 갱신
            if price > position['highest']:
                position['highest'] = price

            entry = position['entry_price']
            raw_pnl = (price - entry) / entry
            net_pnl = raw_pnl - fee_total

            sell = False
            reason = ''

            # 손절
            if net_pnl <= RISK['stop_loss']:
                sell = True
                reason = '손절'
            # 트레일링 스탑
            elif net_pnl > RISK['trailing_activate']:
                drop = (position['highest'] - price) / position['highest']
                if drop >= RISK['trailing_stop']:
                    sell = True
                    reason = f'트레일링(고점 대비 -{drop*100:.1f}%)'
            # 고정 익절
            elif net_pnl >= RISK['take_profit']:
                sell = True
                reason = '익절'
            # 룰 기반 매도
            elif should_sell(hist_closes):
                sell = True
                reason = '시그널매도'

            if sell:
                trades.append(
                    {
                        'entry_date': position['entry_date'],
                        'exit_date': date,
                        'entry_price': entry,
                        'exit_price': price,
                        'pnl_pct': round(net_pnl * 100, 2),
                        'pnl_raw': round(raw_pnl * 100, 2),
                        'holding_days': (
                            datetime.strptime(date, '%Y-%m-%d')
                            - datetime.strptime(position['entry_date'], '%Y-%m-%d')
                        ).days,
                        'reason': reason,
                    }
                )
                position = None

    # 미청산 포지션
    if position:
        entry = position['entry_price']
        price = closes[-1]
        raw_pnl = (price - entry) / entry
        net_pnl = raw_pnl - fee_total
        trades.append(
            {
                'entry_date': position['entry_date'],
                'exit_date': dates[-1],
                'entry_price': entry,
                'exit_price': price,
                'pnl_pct': round(net_pnl * 100, 2),
                'holding_days': 0,
                'reason': '미청산',
            }
        )

    # ── 성과 계산 ──
    if not trades:
        return {'trades': 0, 'message': '매매 신호 없음'}

    pnls = [t['pnl_pct'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    return {
        'stock_code': stock_code,
        'period': f'{dates[start_idx]} ~ {dates[-1]}',
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(len(wins) / len(trades) * 100, 1),
        'total_pnl': round(sum(pnls), 2),
        'avg_pnl': round(sum(pnls) / len(pnls), 2),
        'avg_win': round(sum(wins) / len(wins), 2) if wins else 0,
        'avg_loss': round(sum(losses) / len(losses), 2) if losses else 0,
        'best': round(max(pnls), 2),
        'worst': round(min(pnls), 2),
        'avg_hold_days': round(sum(t['holding_days'] for t in trades) / len(trades), 1),
        'trade_details': trades,
    }


def run_all_backtest(days: int = 30):
    """전체 종목 백테스트"""
    if not supabase:
        print('Supabase 미연결')
        return

    stocks = (
        supabase.table('top50_stocks')
        .select('stock_code,stock_name')
        .execute()
        .data
        or []
    )
    print(f'백테스트 시작: {len(stocks)}종목 × {days}일\n')

    all_results = []
    for s in stocks:
        code = s['stock_code']
        name = s.get('stock_name', code)
        result = run_backtest(code, days)
        if result.get('trades', 0) > 0:
            result['name'] = name
            all_results.append(result)
            emoji = '✅' if result['total_pnl'] > 0 else '❌'
            print(
                f"  {emoji} {name}: {result['trades']}건 | 승률 {result['win_rate']}% | "
                f"수익 {result['total_pnl']:+.2f}% | 평균 {result['avg_pnl']:+.2f}%"
            )

    if not all_results:
        print('매매 신호 없음')
        return

    # 전체 요약
    total_trades = sum(r['trades'] for r in all_results)
    total_wins = sum(r['wins'] for r in all_results)
    all_pnls = [t['pnl_pct'] for r in all_results for t in r['trade_details']]
    avg_pnl = sum(all_pnls) / len(all_pnls) if all_pnls else 0
    win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0

    print(f'\n{"="*50}')
    print(f'전체 요약: {len(all_results)}종목 / {total_trades}건')
    print(f'승률: {win_rate:.1f}% | 평균수익: {avg_pnl:+.2f}%')
    print(f'총 수익: {sum(all_pnls):+.2f}%')
    print(f'최고: {max(all_pnls):+.2f}% | 최저: {min(all_pnls):.2f}%')

    # 텔레그램 요약
    import requests

    tg_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    tg_chat = os.environ.get('TELEGRAM_CHAT_ID', '')
    if tg_token and tg_chat:
        sorted_results = sorted(all_results, key=lambda r: r['total_pnl'], reverse=True)
        top5 = '\n'.join(
            f"  ✅ {r['name']}: {r['total_pnl']:+.2f}%" for r in sorted_results[:5]
        )
        bottom5 = '\n'.join(
            f"  ❌ {r['name']}: {r['total_pnl']:+.2f}%" for r in sorted_results[-5:]
        )

        msg = (
            f"📊 <b>백테스트 결과</b> ({days}일)\n\n"
            f"종목: {len(all_results)}개 / 거래: {total_trades}건\n"
            f"승률: {win_rate:.1f}% | 평균: {avg_pnl:+.2f}%\n"
            f"누적: {sum(all_pnls):+.2f}%\n\n"
            f"<b>🏆 TOP 5</b>\n{top5}\n\n"
            f"<b>💀 WORST 5</b>\n{bottom5}\n\n"
            f"⚠️ 과거 성과가 미래를 보장하지 않음"
        )
        try:
            requests.post(
                f'https://api.telegram.org/bot{tg_token}/sendMessage',
                json={'chat_id': tg_chat, 'text': msg, 'parse_mode': 'HTML'},
                timeout=5,
            )
        except Exception:
            pass


if __name__ == '__main__':
    args = sys.argv[1:]
    days = 30

    # --days 파싱
    if '--days' in args:
        idx = args.index('--days')
        days = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if args and args[0].isdigit():
        # 특정 종목
        result = run_backtest(args[0], days)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # 전체
        run_all_backtest(days)

