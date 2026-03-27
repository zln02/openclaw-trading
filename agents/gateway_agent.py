#!/usr/bin/env python3
"""OpenClaw Gateway Agent - 텔레그램 자연어 인터페이스."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.logger import get_logger
from common.supabase_client import get_supabase

log = get_logger("gateway_agent")


def _fmt_value(value, suffix: str = "") -> str:
    if isinstance(value, (int, float)):
        if suffix == "원":
            return f"{value:,.0f}{suffix}"
        return f"{value}{suffix}"
    if value in (None, ""):
        return "?"
    return str(value)


def get_market_summary() -> dict:
    """3시장 현재 상태 요약."""
    summary: dict = {}

    try:
        import pyupbit

        btc_price = pyupbit.get_current_price("KRW-BTC")
        summary["btc"] = {"price": btc_price}
    except Exception as e:
        log.warning(f"BTC 시세 조회 실패: {e}")
        summary["btc"] = {"price": "조회실패"}

    try:
        import yfinance as yf

        spy = yf.Ticker("SPY").fast_info
        vix = yf.Ticker("^VIX").fast_info
        summary["us"] = {
            "spy": round(float(spy.get("lastPrice", 0) or 0), 1),
            "vix": round(float(vix.get("lastPrice", 0) or 0), 1),
        }
    except Exception as e:
        log.warning(f"미국 지표 조회 실패: {e}")
        summary["us"] = {"spy": "조회실패", "vix": "조회실패"}

    try:
        from agents.regime_classifier import RegimeClassifier

        regime = RegimeClassifier().classify()
        summary["regime"] = regime.get("regime", "UNKNOWN")
    except Exception as e:
        log.warning(f"레짐 분류 실패: {e}")
        summary["regime"] = "UNKNOWN"

    try:
        import requests

        resp = requests.get(
            "https://api.alternative.me/fng/?limit=1&format=json",
            timeout=5,
        )
        fg = resp.json()["data"][0]
        summary["fear_greed"] = int(fg["value"])
        summary["fg_label"] = fg["value_classification"]
    except Exception as e:
        log.warning(f"Fear & Greed 조회 실패: {e}")
        summary["fear_greed"] = None
        summary["fg_label"] = ""

    return summary


def get_portfolio_summary() -> dict:
    """3시장 포트폴리오 요약."""
    sb = get_supabase()
    if not sb:
        return {"error": "Supabase 미연결"}

    result: dict = {}

    try:
        pos = sb.table("btc_position").select("*").eq("status", "OPEN").execute().data
        result["btc_positions"] = len(pos or [])
    except Exception as e:
        log.warning(f"BTC 포지션 조회 실패: {e}")
        result["btc_positions"] = "조회실패"

    try:
        kr = (
            sb.table("trade_executions")
            .select("stock_code,result")
            .eq("result", "OPEN")
            .execute()
            .data
        )
        result["kr_positions"] = len(kr or [])
    except Exception as e:
        log.warning(f"KR 포지션 조회 실패: {e}")
        result["kr_positions"] = "조회실패"

    return result


def get_recent_performance() -> dict:
    """최근 성과 요약."""
    sb = get_supabase()
    if not sb:
        return {}

    try:
        trades = (
            sb.table("trade_executions")
            .select("pnl_pct,result,created_at")
            .in_("result", ["CLOSED", "SELL"])
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        )
        if not trades:
            return {"total_closed": 0}
        pnls = [float(t.get("pnl_pct") or 0) for t in trades]
        wins = sum(1 for pnl in pnls if pnl > 0)
        return {
            "total_closed": len(trades),
            "win_rate": round(wins / len(trades) * 100, 1),
            "avg_pnl": round(sum(pnls) / len(pnls), 2),
        }
    except Exception as e:
        log.warning(f"최근 성과 조회 실패: {e}")
        return {}


def ask_ai(question: str, context: dict) -> str:
    """Claude Haiku로 질문에 답변."""
    try:
        import anthropic

        client = anthropic.Anthropic()
        system = (
            "너는 OpenClaw 자동매매 시스템의 AI 어시스턴트야.\n"
            "다음 컨텍스트를 참고해서 간결한 한국어로 답변해.\n"
            "3-5문장 이내로 답하고, 모르면 단정하지 마.\n\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        if not resp.content:
            return "응답이 비어 있습니다."
        return resp.content[0].text
    except Exception as e:
        log.warning(f"AI 응답 실패: {e}")
        return "AI 응답을 생성하지 못했습니다."


def handle_query(query: str) -> str:
    """자연어 쿼리 처리."""
    q = query.lower().strip()

    if any(key in q for key in ["시장", "market", "레짐", "regime"]):
        summary = get_market_summary()
        lines = [
            "시장 현황",
            f"BTC: {_fmt_value(summary.get('btc', {}).get('price'), '원')}",
            f"SPY: {_fmt_value(summary.get('us', {}).get('spy'))}",
            f"VIX: {_fmt_value(summary.get('us', {}).get('vix'))}",
            f"레짐: {_fmt_value(summary.get('regime'))}",
            f"F&G: {_fmt_value(summary.get('fear_greed'))} ({summary.get('fg_label', '')})",
        ]
        return "\n".join(lines)

    if any(key in q for key in ["포트폴리오", "보유", "포지션"]):
        pf = get_portfolio_summary()
        lines = [
            "포트폴리오",
            f"BTC 포지션: {_fmt_value(pf.get('btc_positions'))}개",
            f"KR 포지션: {_fmt_value(pf.get('kr_positions'))}개",
        ]
        return "\n".join(lines)

    if any(key in q for key in ["성과", "수익", "승률", "리뷰"]):
        perf = get_recent_performance()
        if not perf or perf.get("total_closed", 0) == 0:
            return "최근 청산 거래가 없습니다."
        return (
            f"최근 성과 ({perf['total_closed']}건)\n"
            f"승률: {perf.get('win_rate', 0)}%\n"
            f"평균 PnL: {perf.get('avg_pnl', 0)}%"
        )

    context = get_market_summary()
    context["portfolio"] = get_portfolio_summary()
    context["performance"] = get_recent_performance()
    return ask_ai(query, context)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "시장 현황 알려줘"
    print(handle_query(question))
