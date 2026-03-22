"""agents/trading_agent_team.py — Claude 5-에이전트 자동매매 팀 (Phase 14).

아키텍처:
  Orchestrator (opus-4-6) → MarketAnalyst + NewsAnalyst + RiskManager → Reporter
  최종 BUY / SELL / HOLD 결정을 내리고 Supabase에 기록 후 텔레그램 발송.

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
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_WS = str(Path(__file__).resolve().parents[1])
if _WS not in sys.path:
    sys.path.insert(0, _WS)

from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import send_telegram, Priority as _TgPriority

load_env()
log = get_logger("agent_team")

import anthropic
from anthropic import beta_tool

try:
    from common.supabase_client import get_supabase
    _supabase = get_supabase()
except Exception:
    _supabase = None

# ── 모델 설정 ─────────────────────────────────────────────────────────────
MODEL_ORCHESTRATOR = "claude-opus-4-6"
MODEL_ANALYST      = "claude-sonnet-4-6"
MODEL_LITE         = "claude-haiku-4-5-20251001"

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


# ══════════════════════════════════════════════════════════════════════════
# @beta_tool 데이터 도구 정의
# ══════════════════════════════════════════════════════════════════════════

@beta_tool
def get_btc_indicators() -> dict:
    """BTC 현재 기술적 지표를 반환합니다 (RSI, EMA, BB, MACD 등)."""
    try:
        sys.path.insert(0, _WS)
        from btc.btc_trading_agent import get_market_data, calculate_indicators, get_volume_analysis
        df = get_market_data()
        indicators = calculate_indicators(df)
        volume = get_volume_analysis(df)
        return {**indicators, "volume_score": volume.get("score", 0),
                "volume_ratio": volume.get("ratio", 1.0)}
    except Exception as e:
        log.warning(f"BTC 지표 조회 실패: {e}")
        return {"rsi": 50, "error": str(e)}


@beta_tool
def get_fear_greed_index() -> dict:
    """Crypto Fear & Greed Index를 반환합니다 (0=극도공포, 100=극도탐욕)."""
    try:
        from btc.btc_trading_agent import get_fear_greed
        return get_fear_greed()
    except Exception as e:
        log.warning(f"F&G 조회 실패: {e}")
        return {"value": 50, "label": "Unknown", "msg": "⚪ 중립(50)"}


@beta_tool
def get_kimchi_premium() -> dict:
    """업비트-바이낸스 간 BTC 김치프리미엄(%)을 반환합니다."""
    try:
        from btc.btc_trading_agent import get_kimchi_premium as _kp
        val = _kp()
        return {"premium_pct": val, "blocked": (val or 0) >= 5.0}
    except Exception as e:
        log.warning(f"김치프리미엄 조회 실패: {e}")
        return {"premium_pct": None, "blocked": False}


@beta_tool
def get_portfolio_summary(market: str = "btc") -> dict:
    """현재 포트폴리오 요약 (보유 포지션, 평가손익, 투자금액)을 반환합니다.

    Args:
        market: 'btc' | 'kr' | 'us'
    """
    try:
        if market == "btc":
            from btc.btc_trading_agent import get_open_position
            pos = get_open_position()
            if pos:
                return {
                    "has_position": True,
                    "entry_price": pos.get("entry_price"),
                    "current_pnl_pct": pos.get("pnl_pct"),
                    "amount_krw": pos.get("amount_krw"),
                    "strategy": pos.get("strategy"),
                }
            return {"has_position": False}
        elif _supabase:
            rows = _supabase.table("trade_executions") \
                .select("symbol,side,entry_price,quantity,status") \
                .eq("status", "OPEN").eq("market", market.upper()) \
                .limit(20).execute()
            return {"positions": rows.data or [], "count": len(rows.data or [])}
    except Exception as e:
        log.warning(f"포트폴리오 조회 실패: {e}")
    return {"has_position": False, "error": "조회 실패"}


@beta_tool
def get_risk_metrics(market: str = "btc") -> dict:
    """최근 트레이딩 리스크 지표 (MDD, 승률, 연속손실 등)를 반환합니다.

    Args:
        market: 'btc' | 'kr' | 'us'
    """
    try:
        if _supabase:
            rows = _supabase.table("trade_executions") \
                .select("pnl_pct,side,created_at") \
                .eq("market", market.upper()) \
                .eq("status", "CLOSED") \
                .order("created_at", desc=True) \
                .limit(50).execute()
            trades = rows.data or []
            if not trades:
                return {"total": 0, "win_rate": 0.0, "mdd": 0.0}
            pnls = [float(t.get("pnl_pct") or 0) for t in trades]
            wins = sum(1 for p in pnls if p > 0)
            cum = 0.0
            peak = 0.0
            mdd = 0.0
            for p in reversed(pnls):
                cum += p
                peak = max(peak, cum)
                dd = peak - cum
                mdd = max(mdd, dd)
            return {
                "total": len(pnls),
                "win_rate": round(wins / len(pnls) * 100, 1),
                "avg_pnl": round(sum(pnls) / len(pnls), 2),
                "mdd": round(mdd, 2),
                "recent_5": pnls[:5],
            }
    except Exception as e:
        log.warning(f"리스크 지표 조회 실패: {e}")
    return {"total": 0, "win_rate": 0.0, "mdd": 0.0}


@beta_tool
def fetch_recent_news(market: str = "btc", limit: int = 5) -> dict:
    """최근 관련 뉴스 헤드라인을 반환합니다.

    Args:
        market: 'btc' | 'kr' | 'us'
        limit: 최대 뉴스 수 (기본 5)
    """
    try:
        if market == "btc":
            sys.path.insert(0, os.path.join(_WS, "stocks"))
            from btc_news_collector import get_news_summary
            summary = get_news_summary()
            return {"summary": summary, "market": market}
    except Exception:
        pass
    try:
        from agents.news_analyst import NewsAnalyst
        analyst = NewsAnalyst()
        items = analyst.fetch_latest(market=market, limit=limit)
        return {"items": items[:limit], "market": market}
    except Exception as e:
        log.warning(f"뉴스 조회 실패: {e}")
    return {"summary": "뉴스 없음", "items": []}


@beta_tool
def get_market_regime_info() -> dict:
    """현재 글로벌 시장 레짐 (BULL/BEAR/CORRECTION/RECOVERY/TRANSITION)을 반환합니다."""
    try:
        from common.market_data import get_market_regime
        return get_market_regime()
    except Exception as e:
        log.warning(f"시장 레짐 조회 실패: {e}")
        return {"regime": "UNKNOWN"}


@beta_tool
def send_telegram_report(message: str, priority: str = "normal") -> dict:
    """텔레그램으로 트레이딩 리포트를 전송합니다.

    Args:
        message: 전송할 메시지
        priority: 'high' | 'normal' | 'low'
    """
    try:
        _prio_map = {"high": _TgPriority.URGENT, "normal": _TgPriority.IMPORTANT, "low": _TgPriority.INFO}
        send_telegram(message, priority=_prio_map.get(priority, _TgPriority.IMPORTANT))
        return {"ok": True}
    except Exception as e:
        log.warning(f"텔레그램 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


@beta_tool
def log_agent_decision(
    market: str,
    decision: str,
    reasoning: str,
    confidence: float = 50.0,
    action: str = "pending",
) -> dict:
    """에이전트 의사결정을 Supabase agent_decisions 테이블에 기록합니다.

    Args:
        market: 'btc' | 'kr' | 'us'
        decision: 'BUY' | 'SELL' | 'HOLD'
        reasoning: 결정 근거 (자연어)
        confidence: 확신도 0~100
        action: 'executed' | 'skipped' | 'pending'
    """
    try:
        if _supabase:
            row = {
                "market": market,
                "decision": decision.upper(),
                "reasoning": reasoning[:2000],
                "confidence": round(float(confidence), 2),
                "action": action,
                "agent_team": "claude_5agent",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _supabase.table("agent_decisions").insert(row).execute()
            log.info(f"[agent_decisions] {market} {decision} (conf={confidence:.0f}%) 저장 완료")
            return {"ok": True, "row": row}
    except Exception as e:
        log.warning(f"agent_decisions 저장 실패: {e}")
    return {"ok": False}


# ── 도구 목록 ─────────────────────────────────────────────────────────────
_DATA_TOOLS = [
    get_btc_indicators, get_fear_greed_index, get_kimchi_premium,
    get_portfolio_summary, get_risk_metrics, fetch_recent_news,
    get_market_regime_info,
]
_REPORT_TOOLS = [send_telegram_report, log_agent_decision]
_ALL_TOOLS = _DATA_TOOLS + _REPORT_TOOLS


# ══════════════════════════════════════════════════════════════════════════
# 서브에이전트 실행 헬퍼
# ══════════════════════════════════════════════════════════════════════════

_VALID_DECISIONS = {"BUY", "SELL", "HOLD", "NO_POSITION"}
_AGENT_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# 사이클 내 도구 결과 캐시 (중복 API 호출 방지)
_tool_cache: Dict[str, Any] = {}


def _clear_tool_cache() -> None:
    """사이클 시작 시 캐시 초기화."""
    _tool_cache.clear()


def _run_sub_agent(
    role: str,
    system: str,
    task: str,
    tools: list,
    model: str,
    max_tokens: int = 4096,
    timeout_sec: int = 90,
) -> str:
    """서브에이전트를 tool_runner로 실행. 타임아웃 90초."""
    log.info(f"[{role}] 분석 시작: {task[:60]}...")
    start = time.time()

    def _do_run() -> str:
        runner = _client.beta.messages.tool_runner(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=[{"role": "user", "content": task}],
        )
        result_text = ""
        for message in runner:
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    result_text = block.text
        return result_text or "(결과 없음)"

    try:
        future = _AGENT_EXECUTOR.submit(_do_run)
        result = future.result(timeout=timeout_sec)
        elapsed = round(time.time() - start, 1)
        log.info(f"[{role}] 완료 ({elapsed}s, {len(result)}자)")
        return result
    except FutureTimeout:
        log.warning(f"[{role}] 타임아웃 ({timeout_sec}s) — 기본값 반환")
        return f"[{role}] 응답 시간 초과 ({timeout_sec}s) — 기본 분석 사용"
    except Exception as e:
        log.warning(f"[{role}] 실행 실패: {e}")
        return f"[{role} 오류] {e}"


def _validate_orchestrator_decision(decision_text: str) -> bool:
    """오케스트레이터 결정 유효성 검증."""
    text_upper = decision_text.upper()
    for d in _VALID_DECISIONS:
        if d in text_upper:
            return True
    log.warning(f"오케스트레이터 결정에 유효한 값 없음: {decision_text[:100]}")
    return False


# ══════════════════════════════════════════════════════════════════════════
# TradingAgentTeam 클래스
# ══════════════════════════════════════════════════════════════════════════

class TradingAgentTeam:
    """5-에이전트 Claude 자동매매 팀.

    Orchestrator가 MarketAnalyst, NewsAnalyst, RiskManager의 분석을 종합해
    최종 BUY/SELL/HOLD를 결정하고, Reporter가 결과를 텔레그램으로 발송.
    """

    def __init__(self, market: str = "btc", symbol: Optional[str] = None) -> None:
        self.market = market.lower()
        self.symbol = symbol or ("BTC" if market == "btc" else "")

    # ── 서브에이전트 시스템 프롬프트 ────────────────────────────────────────

    def _market_analyst_prompt(self) -> str:
        return (
            f"당신은 {self.market.upper()} 시장 전문 기술적 분석가입니다. "
            "제공된 도구를 사용해 현재 시장 지표를 수집하고 "
            "매수/매도/보유 관점에서 간결하게 분석해주세요. "
            "RSI, 볼린저밴드, MACD, 거래량, 시장레짐을 반드시 언급하세요."
        )

    def _news_analyst_prompt(self) -> str:
        return (
            f"당신은 {self.market.upper()} 관련 뉴스 감성 분석 전문가입니다. "
            "최근 뉴스 헤드라인에서 시장 심리(긍정/중립/부정)와 "
            "주요 리스크 이벤트를 파악하세요."
        )

    def _risk_manager_prompt(self) -> str:
        return (
            "당신은 트레이딩 리스크 관리 전문가입니다. "
            "현재 포트폴리오, 리스크 지표(MDD, 승률, 연속손실)를 확인하고 "
            "추가 포지션 진입 여부와 적정 포지션 크기를 판단하세요."
        )

    def _orchestrator_prompt(self) -> str:
        return (
            "당신은 헤지펀드 수준의 자동매매 오케스트레이터입니다. "
            "MarketAnalyst, NewsAnalyst, RiskManager의 분석 결과를 종합해 "
            f"{self.market.upper()} 시장에 대한 최종 BUY/SELL/HOLD 결정을 내리세요. "
            "결정 근거를 명확히 하고, 확신도(0~100)를 제시하세요. "
            "log_agent_decision 도구로 반드시 결정을 기록하세요."
        )

    def _reporter_prompt(self) -> str:
        return (
            "당신은 트레이딩 리포트 작성 전문가입니다. "
            "오케스트레이터의 최종 결정을 바탕으로 "
            "텔레그램용 간결한 한국어 리포트를 작성하고 "
            "send_telegram_report 도구로 전송하세요."
        )

    # ── 각 에이전트 실행 ─────────────────────────────────────────────────

    def _run_market_analyst(self) -> str:
        return _run_sub_agent(
            role="MarketAnalyst",
            system=self._market_analyst_prompt(),
            task=f"{self.market.upper()} 현재 기술적 지표를 수집하고 매매 신호를 분석해주세요.",
            tools=_DATA_TOOLS,
            model=MODEL_ANALYST,
        )

    def _run_news_analyst(self) -> str:
        return _run_sub_agent(
            role="NewsAnalyst",
            system=self._news_analyst_prompt(),
            task=f"{self.market.upper()} 관련 최근 뉴스 5건의 감성을 분석해주세요.",
            tools=[fetch_recent_news],
            model=MODEL_LITE,
        )

    def _run_risk_manager(self) -> str:
        return _run_sub_agent(
            role="RiskManager",
            system=self._risk_manager_prompt(),
            task=f"{self.market.upper()} 포트폴리오 상태와 리스크 지표를 확인하고 포지션 진입 가능 여부를 판단해주세요.",
            tools=[get_portfolio_summary, get_risk_metrics],
            model=MODEL_ANALYST,
        )

    def _run_orchestrator(
        self,
        market_analysis: str,
        news_analysis: str,
        risk_analysis: str,
    ) -> str:
        task = (
            f"다음 세 전문가의 분석을 종합해 {self.market.upper()} 최종 매매 결정을 내리세요.\n\n"
            f"### MarketAnalyst 분석\n{market_analysis}\n\n"
            f"### NewsAnalyst 분석\n{news_analysis}\n\n"
            f"### RiskManager 분석\n{risk_analysis}\n\n"
            "BUY / SELL / HOLD 중 하나를 결정하고 log_agent_decision 도구로 기록하세요."
        )
        return _run_sub_agent(
            role="Orchestrator",
            system=self._orchestrator_prompt(),
            task=task,
            tools=[log_agent_decision],
            model=MODEL_ORCHESTRATOR,
            max_tokens=8192,
        )

    def _run_reporter(
        self,
        market_analysis: str,
        news_analysis: str,
        risk_analysis: str,
        orchestrator_decision: str,
    ) -> str:
        task = (
            f"다음 분석 결과를 바탕으로 텔레그램용 리포트를 작성하고 전송하세요.\n\n"
            f"[시장 분석] {market_analysis[:500]}\n"
            f"[뉴스 감성] {news_analysis[:300]}\n"
            f"[리스크] {risk_analysis[:300]}\n"
            f"[최종 결정] {orchestrator_decision[:500]}"
        )
        return _run_sub_agent(
            role="Reporter",
            system=self._reporter_prompt(),
            task=task,
            tools=[send_telegram_report],
            model=MODEL_LITE,
        )

    # ── 메인 실행 진입점 ─────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """5-에이전트 팀 전체 실행 후 결과 딕셔너리 반환."""
        log.info(f"[TradingAgentTeam] {self.market.upper()} 분석 시작")
        _clear_tool_cache()  # 사이클 시작 시 도구 캐시 초기화
        ts = datetime.now(timezone.utc).isoformat()

        market_analysis  = self._run_market_analyst()
        news_analysis    = self._run_news_analyst()
        risk_analysis    = self._run_risk_manager()

        orchestrator_out = self._run_orchestrator(
            market_analysis, news_analysis, risk_analysis
        )

        # 오케스트레이터 결정 검증
        if not _validate_orchestrator_decision(orchestrator_out):
            log.warning("유효한 결정 없음 — HOLD로 처리")
            orchestrator_out = f"[검증 실패] {orchestrator_out}\n최종 결정: HOLD (신뢰도: 0%)"

        reporter_out = self._run_reporter(
            market_analysis, news_analysis, risk_analysis, orchestrator_out
        )

        log.info(f"[TradingAgentTeam] {self.market.upper()} 완료")
        return {
            "market": self.market,
            "timestamp": ts,
            "market_analysis": market_analysis,
            "news_analysis": news_analysis,
            "risk_analysis": risk_analysis,
            "decision": orchestrator_out,
            "report": reporter_out,
        }


# ══════════════════════════════════════════════════════════════════════════
# CLI 진입점
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Trading Agent Team — 5-에이전트 자동매매")
    parser.add_argument("--market", choices=["btc", "kr", "us"], default="btc")
    parser.add_argument("--symbol", default=None, help="종목 코드 (KR: 005930, US: AAPL)")
    args = parser.parse_args()

    team = TradingAgentTeam(market=args.market, symbol=args.symbol)
    result = team.run()
    log.info(json.dumps(result, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
