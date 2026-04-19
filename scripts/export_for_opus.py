"""
export_for_opus.py
Supabase에서 Opus 컨설팅용 데이터 추출
사용법: python3 scripts/export_for_opus.py > supabase_snapshot.md
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env

load_env()
from common.supabase_client import get_supabase

supabase = get_supabase()


def export():
    lines = []
    lines.append("## 📊 Supabase 실제 데이터 스냅샷\n")
    lines.append(f"추출 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # ── 1. BTC 거래 내역 ─────────────────────────────────────
    # 실제 컬럼: id, timestamp, action, price, rsi, macd,
    #            confidence, reason, indicator_snapshot, order_raw, pnl, pnl_pct
    lines.append("### 1. BTC 거래 내역 (최근 30건)")
    try:
        rows = (
            supabase.table("btc_trades")
            .select("timestamp, action, price, confidence, pnl, pnl_pct, reason")
            .order("timestamp", desc=True)
            .limit(30)
            .execute()
            .data
        )
        closed = [r for r in rows if r.get("pnl_pct") is not None]
        wins   = [r for r in closed if (r.get("pnl_pct") or 0) > 0]
        losses = [r for r in closed if (r.get("pnl_pct") or 0) <= 0]
        total_pnl = sum(r.get("pnl") or 0 for r in closed)

        lines.append(f"- 총 기록: {len(rows)}건 | 청산 완료: {len(closed)}건")
        lines.append(f"- 승: {len(wins)} 패: {len(losses)} | 승률: {len(wins)/max(len(closed),1)*100:.1f}%")
        lines.append(f"- 누적 손익: {total_pnl:,.0f}원")
        if closed:
            pnls = [r.get("pnl_pct") or 0 for r in closed]
            lines.append(f"- 평균 수익률: {sum(pnls)/len(pnls):.2f}% | 최대: {max(pnls):.2f}% | 최소: {min(pnls):.2f}%")

        lines.append("\n| 날짜시각 | 방향 | 가격 | conf | 손익률 | 손익(원) | 이유(요약) |")
        lines.append("|----------|------|------|------|--------|----------|------------|")
        for r in rows[:15]:
            pnl_pct = r.get("pnl_pct")
            pnl_str = f"{pnl_pct:.2f}%" if pnl_pct is not None else "-"
            pnl_krw = r.get("pnl")
            krw_str = f"{pnl_krw:,.0f}" if pnl_krw is not None else "-"
            lines.append(
                f"| {str(r.get('timestamp',''))[:16]} "
                f"| {r.get('action','')} "
                f"| {r.get('price',0):,.0f} "
                f"| {r.get('confidence','-')} "
                f"| {pnl_str} "
                f"| {krw_str} "
                f"| {str(r.get('reason',''))[:50]} |"
            )
    except Exception as e:
        lines.append(f"- 조회 실패: {e}")

    # ── 2. KR 주식 거래 내역 ─────────────────────────────────
    # 실제 컬럼: trade_id, trade_type, stock_code, stock_name, quantity, price,
    #            strategy, reason, result, created_at, entry_price, split_stage,
    #            highest_price, ml_score, ml_confidence, composite_score, rsi,
    #            factor_snapshot, news_sentiment, pnl_pct
    lines.append("\n### 2. KR 주식 거래 내역 (최근 20건)")
    try:
        rows = (
            supabase.table("trade_executions")
            .select("created_at, trade_type, stock_code, stock_name, price, quantity, "
                    "result, pnl_pct, ml_score, composite_score, strategy, reason")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        closed = [r for r in rows if r.get("result") in ("CLOSED", "SELL")]
        wins   = [r for r in closed if (r.get("pnl_pct") or 0) > 0]
        lines.append(f"- 총 기록: {len(rows)}건 | 청산: {len(closed)}건 | 승률: {len(wins)/max(len(closed),1)*100:.1f}%")
        if closed:
            pnls = [r.get("pnl_pct") or 0 for r in closed]
            lines.append(f"- 평균 수익률: {sum(pnls)/len(pnls):.2f}% | 최대: {max(pnls):.2f}% | 최소: {min(pnls):.2f}%")

        lines.append("\n| 날짜 | 종목 | 유형 | 결과 | 손익률 | ML점수 | 전략 |")
        lines.append("|------|------|------|------|--------|--------|------|")
        for r in rows[:10]:
            pnl_pct = r.get("pnl_pct")
            lines.append(
                f"| {str(r.get('created_at',''))[:10]} "
                f"| {r.get('stock_name') or r.get('stock_code','')} "
                f"| {r.get('trade_type','')} "
                f"| {r.get('result','')} "
                f"| {f'{pnl_pct:.2f}%' if pnl_pct is not None else '-'} "
                f"| {r.get('ml_score','-')} "
                f"| {str(r.get('strategy',''))[:20]} |"
            )
    except Exception as e:
        lines.append(f"- 조회 실패: {e}")

    # ── 3. US 주식 거래 내역 ─────────────────────────────────
    # 실제 컬럼: id, trade_type, symbol, quantity, price, reason, score,
    #            result, highest_price, exit_price, exit_reason, created_at,
    #            factor_snapshot, pnl_pct
    lines.append("\n### 3. US 주식 거래 내역 (최근 20건)")
    try:
        rows = (
            supabase.table("us_trade_executions")
            .select("created_at, trade_type, symbol, price, quantity, "
                    "result, pnl_pct, score, exit_reason, exit_price")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        closed = [r for r in rows if r.get("result") == "CLOSED"]
        open_p = [r for r in rows if r.get("result") == "OPEN"]
        wins   = [r for r in closed if (r.get("pnl_pct") or 0) > 0]
        lines.append(f"- 총 기록: {len(rows)}건 | 오픈: {len(open_p)}개 | 청산: {len(closed)}건 | 승률: {len(wins)/max(len(closed),1)*100:.1f}%")
        if closed:
            pnls = [r.get("pnl_pct") or 0 for r in closed]
            lines.append(f"- 평균 수익률: {sum(pnls)/len(pnls):.2f}% | 최대: {max(pnls):.2f}% | 최소: {min(pnls):.2f}%")
        if open_p:
            lines.append(f"- 현재 보유: {', '.join(r.get('symbol','') for r in open_p)}")

        lines.append("\n| 날짜 | 종목 | 유형 | 결과 | 손익률 | 점수 | 청산이유 |")
        lines.append("|------|------|------|------|--------|------|----------|")
        for r in rows[:10]:
            pnl_pct = r.get("pnl_pct")
            lines.append(
                f"| {str(r.get('created_at',''))[:10]} "
                f"| {r.get('symbol','')} "
                f"| {r.get('trade_type','')} "
                f"| {r.get('result','')} "
                f"| {f'{pnl_pct:.2f}%' if pnl_pct is not None else '-'} "
                f"| {r.get('score','-')} "
                f"| {str(r.get('exit_reason',''))[:20]} |"
            )
    except Exception as e:
        lines.append(f"- 조회 실패: {e}")

    # ── 4. 최근 7일 핵심 요약 ────────────────────────────────
    lines.append("\n### 4. 최근 7일 핵심 성과")
    try:
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        btc_w = (
            supabase.table("btc_trades")
            .select("action, pnl_pct, pnl, confidence")
            .gte("timestamp", week_ago)
            .execute()
            .data
        )
        kr_w = (
            supabase.table("trade_executions")
            .select("result, pnl_pct")
            .gte("created_at", week_ago)
            .execute()
            .data
        )
        us_w = (
            supabase.table("us_trade_executions")
            .select("result, pnl_pct")
            .gte("created_at", week_ago)
            .execute()
            .data
        )

        btc_closed = [r for r in btc_w if r.get("pnl_pct") is not None]
        kr_closed  = [r for r in kr_w if r.get("result") in ("CLOSED", "SELL")]
        us_closed  = [r for r in us_w if r.get("result") == "CLOSED"]

        lines.append(f"- BTC: {len(btc_w)}건 기록 | 청산 {len(btc_closed)}건 | PnL 합계: {sum(r.get('pnl') or 0 for r in btc_closed):,.0f}원")
        lines.append(f"- KR:  {len(kr_w)}건 기록 | 청산 {len(kr_closed)}건")
        lines.append(f"- US:  {len(us_w)}건 기록 | 청산 {len(us_closed)}건")
    except Exception as e:
        lines.append(f"- 조회 실패: {e}")

    print("\n".join(lines))


if __name__ == "__main__":
    export()
