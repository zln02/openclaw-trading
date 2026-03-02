"""Trading Agent Team — 5-에이전트 Claude 팀 (Phase 14).

에이전트 구성:
  Orchestrator  (claude-opus-4-6,   adaptive thinking) — 최종 의사결정
  MarketAnalyst (claude-sonnet-4-6)                  — 기술 지표 분석
  NewsAnalyst   (claude-haiku-4-5)                   — 뉴스 감성 (저비용 배치)
  RiskManager   (claude-sonnet-4-6)                  — 리스크 평가
  Reporter      (claude-haiku-4-5)                   — 텔레그램/시트 리포트

실행:
  python -m agents.trading_agent_team --market btc
  python -m agents.trading_agent_team --market kr --symbol 005930
  python -m agents.trading_agent_team --market us --symbol AAPL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_WS = str(Path(__file__).resolve().parents[1])
if _WS not in sys.path:
    sys.path.insert(0, _WS)

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("trading_agent_team")

# ── Anthropic SDK ─────────────────────────────────────────────────────────
try:
    import anthropic
    from anthropic import beta_tool
except ImportError as e:
    log.error("anthropic SDK 미설치: pip install anthropic>=0.40.0")
    raise

# ── 모델 상수 ──────────────────────────────────────────────────────────────
MODEL_ORCHESTRATOR = "claude-opus-4-6"
MODEL_ANALYST      = "claude-sonnet-4-6"
MODEL_HAIKU        = "claude-haiku-4-5-20251001"

# ── 공통 클라이언트 ────────────────────────────────────────────────────────
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# ══════════════════════════════════════════════════════════════════════════
# 1. 도구 정의 (@beta_tool)
# ══════════════════════════════════════════════════════════════════════════

@beta_tool
def get_btc_indicators() -> str:
    """BTC 핵심 기술 지표를 반환합니다. RSI, MACD, Bollinger Bands, 거래량 분석 포함."""
    try:
        import pyupbit
        import pandas as pd

        df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)
        if df is None or df.empty:
            return json.dumps({"error": "데이터 없음"})

        close = df["close"]
        # RSI
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss
        rsi   = float((100 - 100 / (1 + rs)).iloc[-1])

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd  = float((ema12 - ema26).iloc[-1])

        # Bollinger Bands
        ma20  = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = float((ma20 + 2 * std20).iloc[-1])
        bb_lower = float((ma20 - 2 * std20).iloc[-1])
        bb_pct   = float((close.iloc[-1] - bb_lower) / (bb_upper - bb_lower + 1e-9))

        # 거래량 비율
        vol_ratio = float(df["volume"].iloc[-1] / df["volume"].rolling(20).mean().iloc[-1])

        return json.dumps({
            "price": float(close.iloc[-1]),
            "rsi": round(rsi, 2),
            "macd": round(macd, 0),
            "bb_pct": round(bb_pct, 3),
            "vol_ratio": round(vol_ratio, 2),
            "ret_7d": round((close.iloc[-1] / close.iloc[-8] - 1) * 100, 2),
        })
    except Exception as exc:
        log.warning(f"get_btc_indicators: {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def get_fear_greed_index() -> str:
    """암호화폐 공포·탐욕 지수를 alternative.me API에서 가져옵니다."""
    try:
        import requests
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=8)
        r.raise_for_status()
        data = r.json()["data"]
        return json.dumps({
            "value":       int(data[0]["value"]),
            "label":       data[0]["value_classification"],
            "prev_value":  int(data[1]["value"]),
            "prev_label":  data[1]["value_classification"],
        })
    except Exception as exc:
        log.warning(f"get_fear_greed_index: {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def get_kimchi_premium() -> str:
    """업비트 vs Binance 가격 차이(김치프리미엄 %)를 계산합니다."""
    try:
        import requests
        upbit_r = requests.get(
            "https://api.upbit.com/v1/ticker?markets=KRW-BTC", timeout=8
        ).json()
        binance_r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=8
        ).json()
        krw_usd = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD", timeout=8
        ).json()["rates"].get("KRW", 1350.0)

        upbit_price   = float(upbit_r[0]["trade_price"])
        binance_price = float(binance_r["price"]) * krw_usd
        premium_pct   = (upbit_price / binance_price - 1) * 100

        return json.dumps({
            "upbit_krw":    round(upbit_price, 0),
            "binance_krw":  round(binance_price, 0),
            "premium_pct":  round(premium_pct, 2),
            "krw_usd_rate": round(krw_usd, 2),
        })
    except Exception as exc:
        log.warning(f"get_kimchi_premium: {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def get_portfolio_summary(market: str) -> str:
    """현재 포트폴리오 요약을 반환합니다.

    Args:
        market: 시장 구분 ('btc' | 'kr' | 'us')
    """
    try:
        from common.supabase_client import get_client
        sb = get_client()
        market = market.lower()

        if market == "btc":
            table = "btc_trades"
            filter_col = "status"
            filter_val = "open"
        else:
            table = "trade_executions"
            filter_col = "market"
            filter_val = market

        rows = (
            sb.table(table)
            .select("*")
            .eq(filter_col, filter_val)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        ) or []

        return json.dumps({
            "market":        market,
            "open_positions": len(rows),
            "positions":     rows[:5],   # 최대 5개 상세
        })
    except Exception as exc:
        log.warning(f"get_portfolio_summary({market}): {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def get_risk_metrics(market: str) -> str:
    """시장별 리스크 지표를 반환합니다 (일일 손익, MDD, 승률).

    Args:
        market: 시장 구분 ('btc' | 'kr' | 'us')
    """
    try:
        from common.supabase_client import get_client
        from datetime import timedelta
        sb = get_client()
        market = market.lower()
        today = datetime.now(timezone.utc).date()
        week_ago = today - timedelta(days=7)

        table = "btc_trades" if market == "btc" else "trade_executions"
        rows = (
            sb.table(table)
            .select("pnl, pnl_pct, created_at")
            .gte("created_at", str(week_ago))
            .execute()
            .data
        ) or []

        pnl_values = [float(r.get("pnl", 0) or 0) for r in rows]
        pnl_pct    = [float(r.get("pnl_pct", 0) or 0) for r in rows]
        wins       = sum(1 for p in pnl_values if p > 0)
        total_pnl  = sum(pnl_values)
        win_rate   = wins / len(pnl_values) * 100 if pnl_values else 0

        # MDD
        cum, peak, mdd = 0.0, 0.0, 0.0
        for p in pnl_values:
            cum += p
            if cum > peak:
                peak = cum
            dd = (peak - cum) / (abs(peak) + 1e-9) * 100
            if dd > mdd:
                mdd = dd

        return json.dumps({
            "market":    market,
            "period":    "7d",
            "trades":    len(rows),
            "win_rate":  round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "mdd_pct":   round(mdd, 2),
        })
    except Exception as exc:
        log.warning(f"get_risk_metrics({market}): {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def fetch_recent_news(symbol: str, limit: int = 10) -> str:
    """최근 뉴스 헤드라인과 감성 점수를 반환합니다.

    Args:
        symbol: 종목 또는 자산 심볼 (예: 'BTC', '005930', 'AAPL')
        limit:  반환할 뉴스 최대 건수 (기본 10)
    """
    try:
        from common.supabase_client import get_client
        from datetime import timedelta
        sb = get_client()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        rows = (
            sb.table("news_items")
            .select("title, sentiment_score, published_at, source")
            .gte("published_at", cutoff.isoformat())
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data
        ) or []

        # symbol 필터링 (간이)
        keyword = symbol.upper()
        filtered = [r for r in rows if keyword in (r.get("title") or "").upper()] or rows

        return json.dumps({
            "symbol": symbol,
            "count":  len(filtered),
            "items": [
                {
                    "title":   r.get("title", ""),
                    "score":   r.get("sentiment_score"),
                    "source":  r.get("source", ""),
                    "at":      r.get("published_at", ""),
                }
                for r in filtered[:limit]
            ],
        })
    except Exception as exc:
        log.warning(f"fetch_recent_news({symbol}): {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def get_market_regime() -> str:
    """현재 시장 레짐 (RISK_ON / TRANSITION / RISK_OFF / CRISIS)을 반환합니다."""
    try:
        regime_file = Path(_WS) / "brain" / "market" / "regime_current.json"
        if regime_file.exists():
            data = json.loads(regime_file.read_text(encoding="utf-8"))
            return json.dumps(data)
        return json.dumps({"regime": "UNKNOWN", "confidence": 0})
    except Exception as exc:
        log.warning(f"get_market_regime: {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def send_telegram_report(message: str, priority: str = "info") -> str:
    """텔레그램 메시지를 전송합니다.

    Args:
        message:  전송할 메시지 (마크다운 지원)
        priority: 우선순위 ('urgent' | 'important' | 'info')
    """
    try:
        from common.telegram import Priority, send_telegram
        pmap = {
            "urgent":    Priority.URGENT,
            "important": Priority.IMPORTANT,
            "info":      Priority.INFO,
        }
        p = pmap.get(priority.lower(), Priority.INFO)
        send_telegram(message, priority=p)
        return json.dumps({"sent": True, "priority": priority})
    except Exception as exc:
        log.warning(f"send_telegram_report: {exc}")
        return json.dumps({"error": str(exc)})


@beta_tool
def log_agent_decision(
    market: str,
    decision: str,
    reasoning: str,
    confidence: float,
    action: str,
) -> str:
    """에이전트 의사결정 결과를 Supabase에 저장합니다.

    Args:
        market:     시장 구분 ('btc' | 'kr' | 'us')
        decision:   결정 (BUY | SELL | HOLD)
        reasoning:  결정 근거 요약
        confidence: 확신도 0~100
        action:     실행 여부 ('executed' | 'skipped' | 'pending')
    """
    try:
        from common.supabase_client import get_client
        sb = get_client()
        row = {
            "market":     market,
            "decision":   decision,
            "reasoning":  reasoning,
            "confidence": confidence,
            "action":     action,
            "agent_team": "claude_5agent",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        sb.table("agent_decisions").insert(row).execute()
        return json.dumps({"saved": True})
    except Exception as exc:
        log.warning(f"log_agent_decision: {exc}")
        return json.dumps({"error": str(exc)})


# ══════════════════════════════════════════════════════════════════════════
# 2. 개별 에이전트 실행 함수
# ══════════════════════════════════════════════════════════════════════════

def run_market_analyst(market: str, symbol: str) -> str:
    """MarketAnalyst — 기술 지표 + 레짐 기반 시장 분석 (claude-sonnet-4-6).

    Returns:
        분석 결과 텍스트
    """
    log.info(f"[MarketAnalyst] 시작: market={market}, symbol={symbol}")

    if market == "btc":
        tools = [get_btc_indicators, get_fear_greed_index, get_kimchi_premium, get_market_regime]
        prompt = (
            f"BTC 시장을 분석해주세요.\n"
            f"- get_btc_indicators()로 기술 지표 확인\n"
            f"- get_fear_greed_index()로 투자 심리 확인\n"
            f"- get_kimchi_premium()으로 김치 프리미엄 확인\n"
            f"- get_market_regime()으로 레짐 확인\n\n"
            f"분석 결과: 현재 시장 상황 요약, 매수/매도/홀드 권고, 핵심 근거 3가지를 한국어로 작성하세요."
        )
    else:
        tools = [get_market_regime]
        prompt = (
            f"{market.upper()} 시장의 {symbol} 종목을 분석해주세요.\n"
            f"- get_market_regime()으로 전체 시장 레짐 확인\n\n"
            f"현재 가능한 데이터로 시장 상황을 요약하고 권고 의견을 한국어로 작성하세요."
        )

    try:
        runner = _client.beta.messages.tool_runner(
            model=MODEL_ANALYST,
            max_tokens=1024,
            tools=tools,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = ""
        for message in runner:
            for block in message.content:
                if hasattr(block, "text"):
                    result_text = block.text
        log.info(f"[MarketAnalyst] 완료: {len(result_text)}자")
        return result_text or "(분석 결과 없음)"
    except Exception as exc:
        log.error(f"[MarketAnalyst] 오류: {exc}")
        return f"시장 분석 오류: {exc}"


def run_news_analyst(symbol: str, limit: int = 15) -> str:
    """NewsAnalyst — 뉴스 감성 배치 분석 (claude-haiku-4-5, 저비용).

    Returns:
        뉴스 감성 요약 텍스트
    """
    log.info(f"[NewsAnalyst] 시작: symbol={symbol}, limit={limit}")
    try:
        runner = _client.beta.messages.tool_runner(
            model=MODEL_HAIKU,
            max_tokens=512,
            tools=[fetch_recent_news],
            messages=[{
                "role": "user",
                "content": (
                    f"fetch_recent_news(symbol='{symbol}', limit={limit})를 호출해서 "
                    f"최근 뉴스를 가져온 뒤, 뉴스 감성을 요약해주세요.\n"
                    f"출력 형식:\n"
                    f"- 전체 감성: POSITIVE/NEGATIVE/NEUTRAL\n"
                    f"- 강도: 1(약) ~ 5(강)\n"
                    f"- 핵심 뉴스 2줄 요약\n"
                    f"(한국어로 간결하게)"
                ),
            }],
        )
        result_text = ""
        for message in runner:
            for block in message.content:
                if hasattr(block, "text"):
                    result_text = block.text
        log.info(f"[NewsAnalyst] 완료: {len(result_text)}자")
        return result_text or "(뉴스 없음)"
    except Exception as exc:
        log.error(f"[NewsAnalyst] 오류: {exc}")
        return f"뉴스 분석 오류: {exc}"


def run_risk_manager(market: str) -> str:
    """RiskManager — 포트폴리오 + 리스크 한도 평가 (claude-sonnet-4-6).

    Returns:
        리스크 평가 텍스트
    """
    log.info(f"[RiskManager] 시작: market={market}")
    try:
        runner = _client.beta.messages.tool_runner(
            model=MODEL_ANALYST,
            max_tokens=512,
            tools=[get_portfolio_summary, get_risk_metrics],
            messages=[{
                "role": "user",
                "content": (
                    f"get_portfolio_summary(market='{market}')와 "
                    f"get_risk_metrics(market='{market}')를 호출해서 "
                    f"리스크 상태를 평가하세요.\n\n"
                    f"출력 형식:\n"
                    f"- 리스크 수준: LOW/MEDIUM/HIGH\n"
                    f"- 추가 매수 가능 여부: YES/NO 및 이유\n"
                    f"- 주의 사항 (있는 경우)\n"
                    f"(한국어로 간결하게)"
                ),
            }],
        )
        result_text = ""
        for message in runner:
            for block in message.content:
                if hasattr(block, "text"):
                    result_text = block.text
        log.info(f"[RiskManager] 완료: {len(result_text)}자")
        return result_text or "(리스크 평가 없음)"
    except Exception as exc:
        log.error(f"[RiskManager] 오류: {exc}")
        return f"리스크 평가 오류: {exc}"


def run_orchestrator(
    market: str,
    symbol: str,
    market_analysis: str,
    news_analysis: str,
    risk_assessment: str,
) -> Dict[str, Any]:
    """Orchestrator — 3가지 분석을 종합해 최종 결정 (claude-opus-4-6 + adaptive thinking).

    Returns:
        dict: {decision, confidence, reasoning, raw_text}
    """
    log.info(f"[Orchestrator] 시작: market={market}, symbol={symbol}")

    system_prompt = (
        "당신은 자동매매 시스템의 최종 의사결정 에이전트입니다. "
        "시장 분석, 뉴스 감성, 리스크 평가를 종합하여 BUY/SELL/HOLD 결정을 내립니다. "
        "결정 시 리스크 관리를 최우선으로 하고, 확신이 낮을 때는 HOLD를 권고하세요. "
        "반드시 JSON 형식으로 답하세요."
    )
    user_prompt = (
        f"## 시장: {market.upper()} | 종목: {symbol}\n\n"
        f"### 기술적 시장 분석\n{market_analysis}\n\n"
        f"### 뉴스 감성 분석\n{news_analysis}\n\n"
        f"### 리스크 평가\n{risk_assessment}\n\n"
        f"---\n"
        f"위 3가지 분석을 종합해 최종 결정을 내려주세요.\n"
        f"다음 JSON 형식으로만 응답하세요:\n"
        f'{{"decision": "BUY|SELL|HOLD", "confidence": 0~100, '
        f'"reasoning": "결정 근거 2~3문장", "key_risks": ["리스크1", "리스크2"]}}'
    )

    try:
        result_text = ""
        # 스트리밍 + adaptive thinking
        with _client.messages.stream(
            model=MODEL_ORCHESTRATOR,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "text")
                ):
                    result_text += event.delta.text
            final = stream.get_final_message()
            # 텍스트 블록만 추출
            for block in final.content:
                if block.type == "text":
                    result_text = block.text
                    break

        # JSON 파싱
        parsed: Dict[str, Any] = {}
        try:
            # ```json ... ``` 감싸기 제거
            clean = result_text.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
        except json.JSONDecodeError:
            log.warning("[Orchestrator] JSON 파싱 실패 — HOLD 폴백")
            parsed = {
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": "파싱 오류로 HOLD 처리",
                "key_risks": [],
            }

        parsed["raw_text"] = result_text
        log.info(
            f"[Orchestrator] 결정={parsed.get('decision')} "
            f"확신도={parsed.get('confidence')}%"
        )
        return parsed

    except Exception as exc:
        log.error(f"[Orchestrator] 오류: {exc}")
        return {
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"에이전트 오류: {exc}",
            "key_risks": [],
            "raw_text": "",
        }


def run_reporter(
    market: str,
    symbol: str,
    decision: Dict[str, Any],
    market_analysis: str,
    news_analysis: str,
) -> bool:
    """Reporter — 결과를 텔레그램으로 발송 + Supabase 기록 (claude-haiku-4-5).

    Returns:
        True if report sent successfully
    """
    log.info(f"[Reporter] 시작: market={market}, decision={decision.get('decision')}")

    dec    = decision.get("decision", "HOLD")
    conf   = decision.get("confidence", 0)
    reason = decision.get("reasoning", "")
    risks  = decision.get("key_risks", [])

    emoji_map = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}
    emoji = emoji_map.get(dec, "⚪")

    report_prompt = (
        f"다음 자동매매 결정을 텔레그램용 짧은 리포트로 요약하세요 (150자 이내):\n\n"
        f"시장: {market.upper()} | 종목: {symbol}\n"
        f"결정: {emoji} {dec} (확신도 {conf}%)\n"
        f"근거: {reason}\n"
        f"리스크: {', '.join(risks) if risks else '없음'}\n\n"
        f"리포트는 한국어로, 이모지를 활용해 읽기 쉽게 작성하세요."
    )

    try:
        runner = _client.beta.messages.tool_runner(
            model=MODEL_HAIKU,
            max_tokens=256,
            tools=[send_telegram_report, log_agent_decision],
            messages=[{
                "role": "user",
                "content": (
                    f"{report_prompt}\n\n"
                    f"1. 리포트 작성 후 send_telegram_report()로 발송하세요 "
                    f"(priority='important' if BUY/SELL else 'info').\n"
                    f"2. log_agent_decision(market='{market}', "
                    f"decision='{dec}', reasoning='{reason[:100]}', "
                    f"confidence={conf}, action='pending')으로 기록하세요."
                ),
            }],
        )
        for _ in runner:
            pass
        log.info("[Reporter] 텔레그램 발송 + DB 기록 완료")
        return True
    except Exception as exc:
        log.error(f"[Reporter] 오류: {exc}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# 3. TradingAgentTeam — 파이프라인 오케스트레이터
# ══════════════════════════════════════════════════════════════════════════

class TradingAgentTeam:
    """5-에이전트 자동매매 팀 메인 클래스."""

    def __init__(self, market: str = "btc", symbol: str = "BTC"):
        self.market = market.lower()
        self.symbol = symbol.upper()

    def run(self) -> Dict[str, Any]:
        """전체 파이프라인 실행.

        Returns:
            {decision, confidence, reasoning, market_analysis,
             news_analysis, risk_assessment, elapsed_sec}
        """
        started = datetime.now()
        log.info(
            f"=== TradingAgentTeam 시작 "
            f"| market={self.market} | symbol={self.symbol} | {started:%Y-%m-%d %H:%M} ==="
        )

        # Step 1: 병렬 분석 (Market + News + Risk)
        # 실제 병렬화는 asyncio 또는 concurrent.futures로 가능하나
        # Anthropic SDK beta_tool_runner가 동기이므로 순차 실행.
        log.info("[Step 1/4] MarketAnalyst 실행 중...")
        market_analysis = run_market_analyst(self.market, self.symbol)

        log.info("[Step 2/4] NewsAnalyst 실행 중...")
        news_analysis = run_news_analyst(self.symbol)

        log.info("[Step 3/4] RiskManager 실행 중...")
        risk_assessment = run_risk_manager(self.market)

        # Step 2: Orchestrator 최종 결정
        log.info("[Step 4/5] Orchestrator 최종 결정 중 (adaptive thinking)...")
        decision = run_orchestrator(
            market=self.market,
            symbol=self.symbol,
            market_analysis=market_analysis,
            news_analysis=news_analysis,
            risk_assessment=risk_assessment,
        )

        # Step 3: Reporter 발송
        log.info("[Step 5/5] Reporter 발송 중...")
        run_reporter(
            market=self.market,
            symbol=self.symbol,
            decision=decision,
            market_analysis=market_analysis,
            news_analysis=news_analysis,
        )

        elapsed = (datetime.now() - started).total_seconds()
        result = {
            "market":          self.market,
            "symbol":          self.symbol,
            "decision":        decision.get("decision", "HOLD"),
            "confidence":      decision.get("confidence", 0),
            "reasoning":       decision.get("reasoning", ""),
            "key_risks":       decision.get("key_risks", []),
            "market_analysis": market_analysis,
            "news_analysis":   news_analysis,
            "risk_assessment": risk_assessment,
            "elapsed_sec":     round(elapsed, 1),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }
        log.info(
            f"=== TradingAgentTeam 완료 "
            f"| 결정={result['decision']} | 확신도={result['confidence']}% "
            f"| 소요={elapsed:.1f}s ==="
        )
        return result

    def run_and_print(self) -> None:
        """실행 후 결과를 로거에 출력."""
        result = self.run()
        sep = "=" * 60
        log.info(sep)
        log.info(f"  {result['market'].upper()} 에이전트 팀 결정")
        log.info(sep)
        log.info(f"  결정:    {result['decision']} (확신도 {result['confidence']}%)")
        log.info(f"  근거:    {result['reasoning']}")
        if result['key_risks']:
            log.info(f"  리스크:  {', '.join(result['key_risks'])}")
        log.info(f"  소요:    {result['elapsed_sec']}초")
        log.info(sep)


# ══════════════════════════════════════════════════════════════════════════
# 4. CLI 진입점
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenClaw Trading Agent Team — 5-에이전트 Claude 팀"
    )
    parser.add_argument(
        "--market",
        default="btc",
        choices=["btc", "kr", "us"],
        help="시장 선택 (기본: btc)",
    )
    parser.add_argument(
        "--symbol",
        default="",
        help="종목 심볼 (kr: 005930, us: AAPL, btc: BTC 기본)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="결과를 JSON으로 출력",
    )
    args = parser.parse_args()

    # 기본 심볼 설정
    symbol_defaults = {"btc": "BTC", "kr": "005930", "us": "SPY"}
    symbol = args.symbol or symbol_defaults.get(args.market, "BTC")

    team   = TradingAgentTeam(market=args.market, symbol=symbol)

    if args.json:
        result = team.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        team.run_and_print()


if __name__ == "__main__":
    main()
