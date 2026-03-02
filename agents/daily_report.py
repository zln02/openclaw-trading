"""일일 리포트 — 매일 22:00 KST 발송.

BTC·KR·US 당일 손익 + 총자산 + 내일 전망 + INFO 버퍼 병합.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests as _req

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import Priority, flush_info_buffer, send_telegram

load_env()
log = get_logger("daily_report")

_WORKSPACE = Path(__file__).resolve().parents[1]
_BRAIN_MARKET = _WORKSPACE / "brain" / "market"


_FG_LABEL_KO = {
    "Extreme Fear": "극공포",
    "Fear": "공포",
    "Neutral": "중립",
    "Greed": "탐욕",
    "Extreme Greed": "극탐욕",
}


def _fg_label_ko(label: str) -> str:
    """F&G 라벨을 한국어로 변환."""
    return _FG_LABEL_KO.get(label, label)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


@dataclass
class DailyReportContext:
    date_str: str
    # BTC
    btc_pnl: float = 0.0
    btc_pnl_pct: float = 0.0
    btc_buys: int = 0
    btc_sells: int = 0
    # KR
    kr_pnl: float = 0.0
    kr_pnl_pct: float = 0.0
    kr_mode: str = "DRY-RUN"
    kr_buys: int = 0
    kr_sells: int = 0
    # US
    us_pnl_usd: float = 0.0
    us_mode: str = "DRY-RUN"
    us_buys: int = 0
    us_sells: int = 0
    # Overall
    total_asset: float = 0.0
    total_pnl: float = 0.0
    # Market state
    fg_value: int = 50
    fg_label: str = "중립"
    composite_score: int = 0
    trend: str = "UNKNOWN"
    # INFO 버퍼
    info_snippets: list = field(default_factory=list)


class DailyReportGenerator:
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client or get_supabase()

    def should_send_now(self, as_of: Optional[datetime] = None, target_hour_kst: int = 22) -> bool:
        now = as_of or datetime.now()
        return now.hour == int(target_hour_kst)

    def _get_today_start(self) -> str:
        return datetime.now().date().isoformat()

    def _load_btc_state(self) -> dict:
        """마지막 BTC 복합스코어/추세를 brain 파일에서 읽음."""
        state_file = _BRAIN_MARKET / "last_btc_state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _get_fg_from_api(self) -> tuple[int, str]:
        """alternative.me F&G API — 최신값 반환."""
        try:
            res = _req.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            val = int(res.json()["data"][0]["value"])
            if val <= 20:
                label = "극공포"
            elif val <= 40:
                label = "공포"
            elif val <= 60:
                label = "중립"
            elif val <= 80:
                label = "탐욕"
            else:
                label = "극탐욕"
            return val, label
        except Exception:
            return 50, "중립"

    def _get_total_asset_krw(self) -> float:
        """업비트 잔고 + 오픈 BTC 포지션 평가액."""
        try:
            access = os.environ.get("UPBIT_ACCESS_KEY", "")
            secret = os.environ.get("UPBIT_SECRET_KEY", "")
            if not access or not secret:
                return 0.0
            import pyupbit
            upbit = pyupbit.Upbit(access, secret)
            krw = float(upbit.get_balance("KRW") or 0)
            btc = float(upbit.get_balance("BTC") or 0)
            price = float(pyupbit.get_current_price("KRW-BTC") or 0)
            return krw + btc * price
        except Exception:
            return 0.0

    def collect_context(self) -> DailyReportContext:
        today = self._get_today_start()
        ctx = DailyReportContext(date_str=datetime.now().strftime("%m/%d"))

        if self.supabase:
            try:
                # ── BTC ─────────────────────────────────────
                btc_rows = (
                    self.supabase.table("btc_position")
                    .select("pnl,entry_krw,status")
                    .gte("entry_time", today)
                    .execute()
                    .data or []
                )
                ctx.btc_buys = len(btc_rows)
                closed_btc = [r for r in btc_rows if r.get("status") == "CLOSED"]
                ctx.btc_sells = len(closed_btc)
                ctx.btc_pnl = sum(_safe_float(r.get("pnl")) for r in closed_btc)
                btc_inv = sum(_safe_float(r.get("entry_krw")) for r in closed_btc)
                ctx.btc_pnl_pct = (ctx.btc_pnl / btc_inv * 100) if btc_inv > 0 else 0.0
            except Exception as e:
                log.warning(f"BTC 데이터 조회 실패: {e}")

            try:
                # ── KR 주식 — pnl 컬럼 없음, entry_price/price/quantity로 계산 ──
                kr_rows = (
                    self.supabase.table("trade_executions")
                    .select("trade_type,entry_price,price,quantity,created_at")
                    .gte("created_at", today)
                    .execute()
                    .data or []
                )
                kr_buys = [r for r in kr_rows if r.get("trade_type") == "BUY"]
                kr_sells = [r for r in kr_rows if r.get("trade_type") == "SELL"]
                ctx.kr_buys = len(kr_buys)
                ctx.kr_sells = len(kr_sells)
                for r in kr_sells:
                    ep = _safe_float(r.get("entry_price"))
                    xp = _safe_float(r.get("price"))
                    qty = _safe_float(r.get("quantity"))
                    if ep > 0 and qty > 0:
                        ctx.kr_pnl += (xp - ep) * qty
                kr_inv = sum(
                    _safe_float(r.get("entry_price")) * _safe_float(r.get("quantity"))
                    for r in kr_sells if r.get("entry_price")
                )
                ctx.kr_pnl_pct = (ctx.kr_pnl / kr_inv * 100) if kr_inv > 0 else 0.0
                ctx.kr_mode = "LIVE" if kr_rows else "장마감"
            except Exception as e:
                log.warning(f"KR 데이터 조회 실패: {e}")

            try:
                # ── US 주식 — pnl 컬럼 없음, price/exit_price/quantity로 계산 ──
                us_rows = (
                    self.supabase.table("us_trade_executions")
                    .select("trade_type,result,price,exit_price,quantity,created_at")
                    .gte("created_at", today)
                    .execute()
                    .data or []
                )
                ctx.us_buys = len([r for r in us_rows if r.get("trade_type") == "BUY"])
                us_closed = [r for r in us_rows if r.get("result") == "CLOSED"]
                ctx.us_sells = len(us_closed)
                for r in us_closed:
                    ep = _safe_float(r.get("price"))
                    xp = _safe_float(r.get("exit_price"))
                    qty = _safe_float(r.get("quantity"))
                    if ep > 0 and qty > 0:
                        ctx.us_pnl_usd += (xp - ep) * qty
                ctx.us_mode = "LIVE" if us_rows else "DRY-RUN"
            except Exception as e:
                log.warning(f"US 데이터 조회 실패: {e}")

        # ── 총자산 (업비트 잔고 + BTC 평가액) ──
        ctx.total_asset = self._get_total_asset_krw()
        ctx.total_pnl = ctx.btc_pnl + ctx.kr_pnl

        # ── 시장 상태 ─────────────────────────────────
        btc_state = self._load_btc_state()
        if btc_state:
            ctx.composite_score = int(btc_state.get("composite", 0))
            ctx.trend = btc_state.get("trend", "UNKNOWN")
            ctx.fg_value = int(btc_state.get("fg", 50))
            ctx.fg_label = _fg_label_ko(btc_state.get("fg_label", "중립"))
        else:
            ctx.fg_value, ctx.fg_label = self._get_fg_from_api()
            ctx.trend = "UNKNOWN"
            ctx.composite_score = 0

        # ── INFO 버퍼 병합 ─────────────────────────────
        ctx.info_snippets = flush_info_buffer()

        return ctx

    def build_message(self, ctx: DailyReportContext) -> str:
        SEP = "━━━━━━━━━━━━━━"

        def _signed(v: float) -> str:
            return "+" if v >= 0 else ""

        # BTC 줄
        btc_s = _signed(ctx.btc_pnl)
        btc_line = f"₿ BTC: {btc_s}₩{ctx.btc_pnl:,.0f} ({btc_s}{ctx.btc_pnl_pct:.2f}%)"

        # KR 줄
        if ctx.kr_mode != "LIVE":
            kr_line = f"🇰🇷 KR: {ctx.kr_mode}"
        else:
            kr_s = _signed(ctx.kr_pnl)
            kr_line = f"🇰🇷 KR: {kr_s}₩{ctx.kr_pnl:,.0f} ({kr_s}{ctx.kr_pnl_pct:.2f}%)"

        # US 줄
        if ctx.us_mode != "LIVE":
            us_line = f"🌐 US: {ctx.us_mode}"
        else:
            us_s = _signed(ctx.us_pnl_usd)
            us_line = f"🌐 US: {us_s}${ctx.us_pnl_usd:.2f}"

        # 총자산
        asset_str = f"₩{ctx.total_asset:,.0f}" if ctx.total_asset > 0 else "조회 불가"
        total_pnl_s = _signed(ctx.total_pnl)
        asset_line = f"총자산: {asset_str} ({total_pnl_s}₩{ctx.total_pnl:,.0f})"

        # 오늘 거래
        total_buys = ctx.btc_buys + ctx.kr_buys + ctx.us_buys
        total_sells = ctx.btc_sells + ctx.kr_sells + ctx.us_sells
        trade_line = f"오늘 거래: 매수 {total_buys}건 / 매도 {total_sells}건"

        # 복합스코어
        if ctx.composite_score > 0:
            comp_line = f"복합스코어: {ctx.composite_score} → {ctx.trend}"
        else:
            comp_line = f"추세: {ctx.trend}"

        # 내일 전망
        fg = ctx.fg_value
        fg_l = ctx.fg_label
        if fg <= 20:
            outlook = f"F&G {fg}({fg_l}), 추가 매수 가능성 높음"
        elif fg <= 40:
            outlook = f"F&G {fg}({fg_l}), 신중 매수 검토"
        elif fg >= 80:
            outlook = f"F&G {fg}({fg_l}), 과열 — 매수 자제"
        elif fg >= 60:
            outlook = f"F&G {fg}({fg_l}), 추세 유지 관망"
        else:
            outlook = f"F&G {fg}({fg_l}), 추세 관망"

        msg = (
            f"📊 <b>일일 리포트 ({ctx.date_str})</b>\n"
            f"{SEP}\n"
            f"{btc_line}\n"
            f"{kr_line}\n"
            f"{us_line}\n"
            f"{SEP}\n"
            f"{asset_line}\n"
            f"{trade_line}\n"
            f"{comp_line}\n"
            f"{SEP}\n"
            f"내일 전망: {outlook}"
        )

        # INFO 버퍼 스니펫 첨부 (있을 경우만)
        if ctx.info_snippets:
            # 너무 길면 요약 — 각 스니펫 첫 줄만
            snippets_summary = "\n".join(
                s.split("\n")[0][:60] for s in ctx.info_snippets[-5:]
            )
            msg += f"\n{SEP}\n🗒 오늘 알림 ({len(ctx.info_snippets)}건)\n{snippets_summary}"

        return msg

    def run(self, send: bool = True) -> dict:
        ctx = self.collect_context()
        text = self.build_message(ctx)

        sent = False
        if send:
            sent = send_telegram(text, priority=Priority.URGENT)
            log.info(f"일일 리포트 발송 {'성공' if sent else '실패'}")

        return {
            "ok": True,
            "sent": bool(sent),
            "report": text,
            "context": {
                "date_str": ctx.date_str,
                "btc_pnl": ctx.btc_pnl,
                "btc_buys": ctx.btc_buys,
                "btc_sells": ctx.btc_sells,
                "kr_mode": ctx.kr_mode,
                "us_mode": ctx.us_mode,
                "total_asset": ctx.total_asset,
                "fg_value": ctx.fg_value,
                "composite_score": ctx.composite_score,
                "info_count": len(ctx.info_snippets),
            },
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="일일 리포트 생성기")
    parser.add_argument("--no-send", action="store_true", help="텔레그램 발송 생략")
    parser.add_argument("--force", action="store_true", help="시간 체크 없이 즉시 실행")
    args = parser.parse_args()

    gen = DailyReportGenerator()

    if not args.force and not gen.should_send_now():
        log.info("발송 시각(22:00 KST)이 아님 — 스킵 (--force 로 강제 실행)")
        return 0

    out = gen.run(send=not args.no_send)
    import json as _json
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
