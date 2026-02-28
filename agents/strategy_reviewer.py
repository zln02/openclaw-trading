"""Weekly strategy reviewer (Phase 12).

Purpose:
- Analyze last-week performance/logs
- Propose/commit strategy parameter updates
- Store history in brain/strategy-history/YYYY-MM-DD.json
"""
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config import BRAIN_PATH, STRATEGY_JSON
from common.env_loader import load_env
from common.logger import get_logger
from common.market_data import get_market_regime
from common.supabase_client import get_supabase
from common.telegram import send_telegram
from common.utils import safe_float as _safe_float

load_env()
log = get_logger("strategy_reviewer")

HISTORY_DIR = BRAIN_PATH / "strategy-history"


def _to_date(value: str | date | datetime | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _slice_iso(dt: str) -> str:
    return str(dt or "")[:10]


def _json_parse(raw: str) -> dict:
    text = raw.strip().replace("```json", "").replace("```", "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    s = text.find("{")
    e = text.rfind("}")
    if s >= 0 and e > s:
        return json.loads(text[s : e + 1])
    raise ValueError("JSON object not found")


def _normalize_factor_weights(weights: dict) -> dict:
    defaults = {
        "momentum": 0.3,
        "value": 0.2,
        "quality": 0.2,
        "sentiment": 0.2,
        "technical": 0.1,
    }
    if not isinstance(weights, dict) or not weights:
        return defaults

    cleaned = {k: max(_safe_float(weights.get(k), defaults.get(k, 0.0)), 0.0) for k in defaults.keys()}

    # Preserve extra keys if provided (future factor categories), but keep non-negative.
    for k, v in weights.items():
        kk = str(k)
        if kk not in cleaned:
            cleaned[kk] = max(_safe_float(v, 0.0), 0.0)

    total = sum(cleaned.values())
    if total <= 0:
        return defaults
    return {k: round(v / total, 4) for k, v in cleaned.items()}


class StrategyReviewer:
    def __init__(
        self,
        supabase_client=None,
        model: str = "gpt-4o-mini",
        strategy_path: Path = STRATEGY_JSON,
    ):
        self.supabase = supabase_client or get_supabase()
        self.model = model
        self.strategy_path = Path(strategy_path)

    def is_review_day(self, as_of: str | date | datetime | None = None) -> bool:
        # Sunday = 6
        return _to_date(as_of).weekday() == 6

    def load_current_strategy(self) -> dict:
        if not self.strategy_path.exists():
            return {
                "date": datetime.now().date().isoformat(),
                "market_outlook": "중립",
                "risk_level": "보통",
                "factor_weights": {
                    "momentum": 0.3,
                    "value": 0.2,
                    "quality": 0.2,
                    "sentiment": 0.2,
                    "technical": 0.1,
                },
                "top_picks": [],
                "summary": "초기 전략",
                "source": "INIT",
            }
        try:
            return json.loads(self.strategy_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("today_strategy load failed", error=exc)
            return {}

    def collect_weekly_metrics(self, as_of: str | date | datetime | None = None) -> dict:
        end_day = _to_date(as_of)
        start_day = end_day - timedelta(days=7)
        start_iso = start_day.isoformat()
        end_iso = (end_day + timedelta(days=1)).isoformat()

        out = {
            "period_start": start_iso,
            "period_end": end_day.isoformat(),
            "kr": {"trades": 0, "closed": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0},
            "us": {"trades": 0, "closed": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0},
            "btc": {"trades": 0, "closed": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0},
        }

        if not self.supabase:
            return out

        # KR
        try:
            rows = (
                self.supabase.table("trade_executions")
                .select("*")
                .gte("created_at", start_iso)
                .lt("created_at", end_iso)
                .execute()
                .data
                or []
            )
            out["kr"]["trades"] = len(rows)
            for r in rows:
                if str(r.get("result") or "").upper() in {"CLOSED", "SELL"}:
                    out["kr"]["closed"] += 1
                    pnl = _safe_float(r.get("pnl") or r.get("pnl_krw"), 0.0)
                    out["kr"]["pnl_sum"] += pnl
                    if pnl > 0:
                        out["kr"]["wins"] += 1
                    elif pnl < 0:
                        out["kr"]["losses"] += 1
        except Exception as exc:
            log.warning("weekly KR metrics failed", error=exc)

        # US
        try:
            rows = (
                self.supabase.table("us_trade_executions")
                .select("*")
                .gte("created_at", start_iso)
                .lt("created_at", end_iso)
                .execute()
                .data
                or []
            )
            out["us"]["trades"] = len(rows)
            for r in rows:
                if str(r.get("result") or "").upper() in {"CLOSED", "SELL"}:
                    out["us"]["closed"] += 1
                    pnl = _safe_float(r.get("pnl") or r.get("pnl_usd"), 0.0)
                    out["us"]["pnl_sum"] += pnl
                    if pnl > 0:
                        out["us"]["wins"] += 1
                    elif pnl < 0:
                        out["us"]["losses"] += 1
        except Exception as exc:
            log.warning("weekly US metrics failed", error=exc)

        # BTC
        try:
            rows = (
                self.supabase.table("btc_position")
                .select("*")
                .eq("status", "CLOSED")
                .gte("exit_time", start_iso)
                .lt("exit_time", end_iso)
                .execute()
                .data
                or []
            )
            out["btc"]["trades"] = len(rows)
            out["btc"]["closed"] = len(rows)
            for r in rows:
                pnl = _safe_float(r.get("pnl"), 0.0)
                out["btc"]["pnl_sum"] += pnl
                if pnl > 0:
                    out["btc"]["wins"] += 1
                elif pnl < 0:
                    out["btc"]["losses"] += 1
        except Exception as exc:
            log.warning("weekly BTC metrics failed", error=exc)

        # aggregate winrate
        total_closed = out["kr"]["closed"] + out["us"]["closed"] + out["btc"]["closed"]
        total_wins = out["kr"]["wins"] + out["us"]["wins"] + out["btc"]["wins"]
        out["total_closed"] = total_closed
        out["total_wins"] = total_wins
        out["overall_win_rate"] = round((total_wins / total_closed * 100.0) if total_closed > 0 else 0.0, 2)
        out["overall_pnl_sum"] = round(
            out["kr"]["pnl_sum"] + out["us"]["pnl_sum"] + out["btc"]["pnl_sum"],
            4,
        )
        return out

    def collect_factor_context(self) -> dict:
        # lightweight context to avoid expensive full factor re-analysis in this step.
        try:
            from quant.factors.registry import available_factors

            names = available_factors()
            return {
                "registered_factor_count": len(names),
                "sample_factors": names[:10],
            }
        except Exception as exc:
            log.warning("factor context failed", error=exc)
            return {"registered_factor_count": 0, "sample_factors": []}

    def collect_market_context(self) -> dict:
        try:
            regime = get_market_regime()
        except Exception:
            regime = {"regime": "UNKNOWN", "vix": 20}
        return {"us_regime": regime}

    def _build_prompt(self, current_strategy: dict, weekly_metrics: dict, factor_ctx: dict, market_ctx: dict) -> str:
        return f"""
당신은 퀀트 트레이딩 전략 리뷰어입니다.
지난주 성과를 반영해 다음 주 전략 방향을 제안하세요.

[현재 전략 JSON]
{json.dumps(current_strategy, ensure_ascii=False)}

[주간 성과]
{json.dumps(weekly_metrics, ensure_ascii=False)}

[팩터 컨텍스트]
{json.dumps(factor_ctx, ensure_ascii=False)}

[시장 레짐]
{json.dumps(market_ctx, ensure_ascii=False)}

요구사항:
1) market_outlook / risk_level / summary를 업데이트
2) top_picks를 최대 10개 유지
3) factor_weights를 조정 (총합 1.0)
4) notes에 "why_changed"를 간단히 기록
5) 출력은 아래 JSON 포맷만

{{
  "market_outlook": "강세|중립|약세",
  "risk_level": "낮음|보통|높음",
  "factor_weights": {{"momentum":0.3,"value":0.2,"quality":0.2,"sentiment":0.2,"technical":0.1}},
  "top_picks": [{{"code":"005930","name":"삼성전자","action":"BUY","reason":"..."}}],
  "summary": "한줄 요약",
  "notes": {{"why_changed": "..."}}
}}
""".strip()

    def _fallback_review(self, current_strategy: dict, weekly_metrics: dict) -> dict:
        next_strategy = deepcopy(current_strategy) if current_strategy else {}
        win_rate = _safe_float(weekly_metrics.get("overall_win_rate"), 0.0)
        pnl = _safe_float(weekly_metrics.get("overall_pnl_sum"), 0.0)
        factor_weights = _normalize_factor_weights(next_strategy.get("factor_weights") or {})

        if pnl < 0 or win_rate < 40:
            risk_level = "높음"
            outlook = "약세"
            msg = "최근 성과 부진으로 방어적 운영"
            factor_weights["momentum"] = max(_safe_float(factor_weights.get("momentum"), 0.0) - 0.05, 0.0)
            factor_weights["sentiment"] = max(_safe_float(factor_weights.get("sentiment"), 0.0) - 0.03, 0.0)
            factor_weights["quality"] = _safe_float(factor_weights.get("quality"), 0.0) + 0.05
            factor_weights["value"] = _safe_float(factor_weights.get("value"), 0.0) + 0.03
        elif win_rate >= 60 and pnl > 0:
            risk_level = "보통"
            outlook = "강세"
            msg = "성과 양호, 모멘텀 전략 유지"
            factor_weights["momentum"] = _safe_float(factor_weights.get("momentum"), 0.0) + 0.05
            factor_weights["sentiment"] = _safe_float(factor_weights.get("sentiment"), 0.0) + 0.03
            factor_weights["quality"] = max(_safe_float(factor_weights.get("quality"), 0.0) - 0.04, 0.0)
        else:
            risk_level = "보통"
            outlook = "중립"
            msg = "성과 혼조, 선택적 진입"

        factor_weights = _normalize_factor_weights(factor_weights)

        picks = list(next_strategy.get("top_picks") or [])[:10]
        next_strategy.update(
            {
                "market_outlook": outlook,
                "risk_level": risk_level,
                "factor_weights": factor_weights,
                "top_picks": picks,
                "summary": msg,
                "notes": {"why_changed": "RULE_FALLBACK"},
                "source": "STRATEGY_REVIEW_FALLBACK",
            }
        )
        return next_strategy

    def _llm_review(self, prompt: str) -> Optional[dict]:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800,
            )
            raw = (res.choices[0].message.content or "").strip()
            return _json_parse(raw)
        except Exception as exc:
            log.warning("strategy review llm failed", error=exc)
            return None

    def _merge_review(self, base: dict, review: dict, as_of: date) -> dict:
        out = deepcopy(base) if base else {}
        out["date"] = as_of.isoformat()
        out["market_outlook"] = review.get("market_outlook", out.get("market_outlook", "중립"))
        out["risk_level"] = review.get("risk_level", out.get("risk_level", "보통"))
        out["factor_weights"] = _normalize_factor_weights(
            review.get("factor_weights") or out.get("factor_weights") or {}
        )
        out["top_picks"] = (review.get("top_picks") or out.get("top_picks") or [])[:10]
        out["summary"] = review.get("summary", out.get("summary", ""))
        out["notes"] = review.get("notes", {})
        out["source"] = "STRATEGY_REVIEW_AI"
        return out

    def save_strategy(self, strategy: dict) -> None:
        self.strategy_path.parent.mkdir(parents=True, exist_ok=True)
        self.strategy_path.write_text(json.dumps(strategy, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_history(self, payload: dict, as_of: date) -> Path:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        p = HISTORY_DIR / f"{as_of.isoformat()}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def collect_daily_metrics(self, as_of: str | date | datetime | None = None) -> dict:
        """Collect today's trade summary across KR / US / BTC."""
        day = _to_date(as_of)
        start_iso = day.isoformat()
        end_iso = (day + timedelta(days=1)).isoformat()

        out: Dict[str, Any] = {
            "date": day.isoformat(),
            "kr": {"trades": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0, "open_positions": 0},
            "us": {"trades": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0, "open_positions": 0},
            "btc": {"trades": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0, "open_positions": 0},
        }

        if not self.supabase:
            return out

        # KR
        try:
            rows = (
                self.supabase.table("trade_executions")
                .select("*")
                .gte("created_at", start_iso)
                .lt("created_at", end_iso)
                .execute()
                .data
                or []
            )
            out["kr"]["trades"] = len(rows)
            for r in rows:
                status = str(r.get("result") or "").upper()
                if status in {"CLOSED", "SELL"}:
                    pnl = _safe_float(r.get("pnl") or r.get("pnl_krw"), 0.0)
                    out["kr"]["pnl_sum"] += pnl
                    if pnl > 0:
                        out["kr"]["wins"] += 1
                    elif pnl < 0:
                        out["kr"]["losses"] += 1
                elif status in {"OPEN", "BUY", "HOLD"}:
                    out["kr"]["open_positions"] += 1
        except Exception as exc:
            log.warning("daily KR metrics failed", error=exc)

        # US
        try:
            rows = (
                self.supabase.table("us_trade_executions")
                .select("*")
                .gte("created_at", start_iso)
                .lt("created_at", end_iso)
                .execute()
                .data
                or []
            )
            out["us"]["trades"] = len(rows)
            for r in rows:
                status = str(r.get("result") or "").upper()
                if status in {"CLOSED", "SELL"}:
                    pnl = _safe_float(r.get("pnl") or r.get("pnl_usd"), 0.0)
                    out["us"]["pnl_sum"] += pnl
                    if pnl > 0:
                        out["us"]["wins"] += 1
                    elif pnl < 0:
                        out["us"]["losses"] += 1
                elif status in {"OPEN", "BUY", "HOLD"}:
                    out["us"]["open_positions"] += 1
        except Exception as exc:
            log.warning("daily US metrics failed", error=exc)

        # BTC
        try:
            closed_rows = (
                self.supabase.table("btc_position")
                .select("*")
                .eq("status", "CLOSED")
                .gte("exit_time", start_iso)
                .lt("exit_time", end_iso)
                .execute()
                .data
                or []
            )
            out["btc"]["trades"] = len(closed_rows)
            for r in closed_rows:
                pnl = _safe_float(r.get("pnl"), 0.0)
                out["btc"]["pnl_sum"] += pnl
                if pnl > 0:
                    out["btc"]["wins"] += 1
                elif pnl < 0:
                    out["btc"]["losses"] += 1

            open_rows = (
                self.supabase.table("btc_position")
                .select("id")
                .eq("status", "OPEN")
                .execute()
                .data
                or []
            )
            out["btc"]["open_positions"] = len(open_rows)
        except Exception as exc:
            log.warning("daily BTC metrics failed", error=exc)

        # Aggregate
        total_trades = out["kr"]["trades"] + out["us"]["trades"] + out["btc"]["trades"]
        total_wins = out["kr"]["wins"] + out["us"]["wins"] + out["btc"]["wins"]
        total_closed = total_wins + out["kr"]["losses"] + out["us"]["losses"] + out["btc"]["losses"]
        total_pnl = round(out["kr"]["pnl_sum"] + out["us"]["pnl_sum"] + out["btc"]["pnl_sum"], 4)
        out["total_trades"] = total_trades
        out["total_closed"] = total_closed
        out["total_wins"] = total_wins
        out["overall_win_rate"] = round((total_wins / total_closed * 100.0) if total_closed > 0 else 0.0, 2)
        out["overall_pnl_sum"] = total_pnl
        return out

    def run_daily_check(self, as_of: str | date | datetime | None = None, notify: bool = True) -> dict:
        """Lightweight daily summary: collect today's metrics and send Telegram report.

        No heavy LLM call is made — this is designed to run every evening quickly.
        """
        day = _to_date(as_of)

        daily = self.collect_daily_metrics(day)
        market_ctx = self.collect_market_context()
        regime = market_ctx.get("us_regime", {}).get("regime", "UNKNOWN")
        vix = market_ctx.get("us_regime", {}).get("vix", "?")

        kr = daily["kr"]
        us = daily["us"]
        btc = daily["btc"]

        def _pnl_sign(v: float) -> str:
            return "+" if v >= 0 else ""

        msg = (
            f"📊 <b>일간 매매 요약 ({day.isoformat()})</b>\n"
            f"레짐: {regime} | VIX: {vix}\n\n"
            f"🇰🇷 KR주식: {kr['trades']}건 | "
            f"수익 {_pnl_sign(kr['pnl_sum'])}{kr['pnl_sum']:,.0f}원 | "
            f"보유 {kr['open_positions']}종목\n"
            f"🌐 US주식: {us['trades']}건 | "
            f"수익 {_pnl_sign(us['pnl_sum'])}{us['pnl_sum']:,.2f}$ | "
            f"보유 {us['open_positions']}종목\n"
            f"₿ BTC: {btc['trades']}건 | "
            f"수익 {_pnl_sign(btc['pnl_sum'])}{btc['pnl_sum']:,.4f}₿ | "
            f"보유 {btc['open_positions']}포지션\n\n"
            f"합계: {daily['total_closed']}건 결산 | "
            f"승률 {daily['overall_win_rate']:.1f}% | "
            f"총손익 {_pnl_sign(daily['overall_pnl_sum'])}{daily['overall_pnl_sum']}"
        )

        if notify:
            try:
                send_telegram(msg)
            except Exception as exc:
                log.warning("daily check telegram send failed", error=exc)

        # Save daily snapshot to brain
        history_payload = {
            "type": "daily_check",
            "date": day.isoformat(),
            "daily_metrics": daily,
            "market_context": market_ctx,
        }
        try:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            p = HISTORY_DIR / f"daily-{day.isoformat()}.json"
            p.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("daily check save failed", error=exc)

        return {
            "ok": True,
            "type": "daily_check",
            "date": day.isoformat(),
            "daily_metrics": daily,
            "market_context": market_ctx,
        }

    def run(self, force: bool = False, as_of: str | date | datetime | None = None) -> dict:
        day = _to_date(as_of)
        if not force and not self.is_review_day(day):
            return {"ok": True, "skipped": True, "reason": "not_review_day", "date": day.isoformat()}

        current = self.load_current_strategy()
        weekly = self.collect_weekly_metrics(day)
        factor_ctx = self.collect_factor_context()
        market_ctx = self.collect_market_context()

        prompt = self._build_prompt(current, weekly, factor_ctx, market_ctx)
        llm_review = self._llm_review(prompt)
        if llm_review:
            next_strategy = self._merge_review(current, llm_review, day)
        else:
            next_strategy = self._fallback_review(current, weekly)
            next_strategy["date"] = day.isoformat()

        self.save_strategy(next_strategy)

        history_payload = {
            "date": day.isoformat(),
            "current_strategy": current,
            "next_strategy": next_strategy,
            "weekly_metrics": weekly,
            "factor_context": factor_ctx,
            "market_context": market_ctx,
            "llm_used": bool(llm_review),
        }
        history_path = self.save_history(history_payload, day)

        msg = (
            f"🧠 <b>주간 전략 리뷰 완료</b>\n"
            f"날짜: {day.isoformat()}\n"
            f"리스크: {next_strategy.get('risk_level','?')}\n"
            f"전망: {next_strategy.get('market_outlook','?')}\n"
            f"요약: {next_strategy.get('summary','')}"
        )
        send_telegram(msg)

        return {
            "ok": True,
            "skipped": False,
            "date": day.isoformat(),
            "strategy_path": str(self.strategy_path),
            "history_path": str(history_path),
            "llm_used": bool(llm_review),
        }


def _cli() -> int:
    p = argparse.ArgumentParser(description="Strategy reviewer (weekly + daily)")
    p.add_argument("--force", action="store_true", help="run weekly review even if not Sunday")
    p.add_argument("--date", default=None, help="as-of date YYYY-MM-DD")
    p.add_argument("--daily", action="store_true", help="run lightweight daily check instead of weekly review")
    p.add_argument("--no-notify", action="store_true", help="skip Telegram notification (daily mode)")
    args = p.parse_args()

    reviewer = StrategyReviewer()
    if args.daily:
        out = reviewer.run_daily_check(as_of=args.date, notify=not args.no_notify)
    else:
        out = reviewer.run(force=args.force, as_of=args.date)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
