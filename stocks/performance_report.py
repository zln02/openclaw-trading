#!/usr/bin/env python3
"""
성과 분석 리포트 v1.0
매일 16:00 실행 — 텔레그램으로 일일/주간/누적 성과 발송

지표:
- 승률 (Win Rate)
- 평균 수익 / 평균 손실
- 손익비 (Profit Factor)
- 최대 낙폭 (MDD)
- 샤프 비율 (Sharpe Ratio)
"""

import os
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import requests

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
TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


def send_telegram(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception:
        pass


def get_closed_trades(days: int = 30) -> list:
    """최근 N일 CLOSED 거래 조회"""
    if not supabase:
        return []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    trades = (
        supabase.table('trade_executions')
        .select('*')
        .in_('result', ['CLOSED', 'CLOSED_MANUAL', 'CLOSED_SYNC'])
        .gte('created_at', cutoff)
        .order('created_at', desc=False)
        .execute()
        .data
        or []
    )
    return trades


def calc_trade_pnl(trades: list) -> list:
    """거래별 수익률 계산"""
    results = []
    for t in trades:
        entry = float(t.get('entry_price') or t.get('price') or 0)
        exit_price = float(t.get('exit_price') or t.get('price') or 0)
        qty = int(t.get('quantity', 0))
        if entry <= 0 or qty <= 0:
            continue

        pnl_pct = (exit_price - entry) / entry * 100
        pnl_krw = (exit_price - entry) * qty
        results.append(
            {
                'name': t.get('stock_name', t.get('stock_code', '?')),
                'pnl_pct': pnl_pct,
                'pnl_krw': pnl_krw,
                'date': t.get('created_at', '')[:10],
                'type': t.get('result', ''),
            }
        )
    return results


def calc_metrics(pnl_list: list) -> dict:
    """성과 지표 계산"""
    if not pnl_list:
        return {}

    pcts = [p['pnl_pct'] for p in pnl_list]
    wins = [p for p in pcts if p > 0]
    losses = [p for p in pcts if p <= 0]

    total_trades = len(pcts)
    win_count = len(wins)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    # 손익비 (Profit Factor)
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # 평균 수익률
    avg_return = sum(pcts) / len(pcts) if pcts else 0

    # 표준편차
    if len(pcts) >= 2:
        mean = sum(pcts) / len(pcts)
        variance = sum((x - mean) ** 2 for x in pcts) / (len(pcts) - 1)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0

    # 샤프 비율 (일간 기준, 무위험수익률 0 가정)
    sharpe = (avg_return / std_dev) if std_dev > 0 else 0

    # MDD (Maximum Drawdown)
    cumulative = 0
    peak = 0
    mdd = 0
    for pct in pcts:
        cumulative += pct
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > mdd:
            mdd = drawdown

    # 누적 수익
    total_pnl_pct = sum(pcts)
    total_pnl_krw = sum(p['pnl_krw'] for p in pnl_list)

    return {
        'total_trades': total_trades,
        'win_count': win_count,
        'loss_count': total_trades - win_count,
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_return': round(avg_return, 2),
        'sharpe': round(sharpe, 2),
        'mdd': round(mdd, 2),
        'total_pnl_pct': round(total_pnl_pct, 2),
        'total_pnl_krw': round(total_pnl_krw, 0),
        'best_trade': max(pcts) if pcts else 0,
        'worst_trade': min(pcts) if pcts else 0,
    }


def generate_report():
    """성과 리포트 생성 + 텔레그램 발송"""
    # 오늘 거래
    today_trades = get_closed_trades(days=1)
    today_pnl = calc_trade_pnl(today_trades)
    today_metrics = calc_metrics(today_pnl)

    # 주간 거래
    week_trades = get_closed_trades(days=7)
    week_pnl = calc_trade_pnl(week_trades)
    week_metrics = calc_metrics(week_pnl)

    # 월간 거래
    month_trades = get_closed_trades(days=30)
    month_pnl = calc_trade_pnl(month_trades)
    month_metrics = calc_metrics(month_pnl)

    def format_section(label, m):
        if not m:
            return f"\n<b>{label}</b>\n  거래 없음"
        pf_display = f"{m['profit_factor']}" if m['profit_factor'] < 100 else "∞"
        return (
            f"\n<b>{label}</b>\n"
            f"  거래: {m['total_trades']}건 (승 {m['win_count']} / 패 {m['loss_count']})\n"
            f"  승률: {m['win_rate']}%\n"
            f"  평균수익: {m['avg_win']:+.2f}% / 평균손실: {m['avg_loss']:.2f}%\n"
            f"  손익비: {pf_display}\n"
            f"  샤프비율: {m['sharpe']}\n"
            f"  MDD: -{m['mdd']:.2f}%\n"
            f"  최고: {m['best_trade']:+.2f}% / 최저: {m['worst_trade']:.2f}%\n"
            f"  누적: {m['total_pnl_pct']:+.2f}% ({m['total_pnl_krw']:+,.0f}원)"
        )

    msg = f"📊 <b>성과 리포트</b> ({datetime.now().strftime('%Y-%m-%d')})"
    msg += format_section("📅 오늘", today_metrics)
    msg += format_section("📆 주간 (7일)", week_metrics)
    msg += format_section("📈 월간 (30일)", month_metrics)
    msg += "\n\n⚠️ 모의투자"

    print(msg.replace('<b>', '').replace('</b>', ''))
    send_telegram(msg)

    # DB에도 저장
    if supabase:
        try:
            supabase.table('daily_reports').upsert(
                [
                    {
                        'date': datetime.now().date().isoformat(),
                        'report_type': 'performance',
                        'content': json.dumps(
                            {
                                'today': today_metrics,
                                'week': week_metrics,
                                'month': month_metrics,
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
                on_conflict='date,report_type',
            ).execute()
        except Exception:
            pass


if __name__ == '__main__':
    generate_report()

