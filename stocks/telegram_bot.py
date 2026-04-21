#!/usr/bin/env python3
"""
텔레그램 제어 봇 (KR 주식)

기능:
- /status   : 현재 계좌 요약 + 보유종목 요약 전송
- /stop     : 자동매매 중지 플래그 파일 생성 (에이전트가 플래그 보고 사이클 스킵)
- /resume   : 자동매매 재개
- /sell_all : 전량 매도 — 2단계 확인 (CONFIRM_SELL_ALL) 후 kiwoom.place_order 호출
- /regime   : 레짐 요약
- /allocation / /var : 리스크 요약

안전장치:
- /sell_all은 2단계 (확인 버튼) 필수. kiwoom_client.place_order(sell, qty, 0=시장가) 직접 호출.
- Supabase 미연결 시 /sell_all 거부.
- BTC 실거래 청산은 이 봇이 아닌 btc_trading_agent.py의 자체 로직 담당.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

try:
    from kiwoom_client import KiwoomClient
except Exception:
    from stocks.kiwoom_client import KiwoomClient

from common.config import WORKSPACE
from common.env_loader import load_env
from common.logger import get_logger
from supabase import create_client

log = get_logger(__name__)

AUDIT_LOG = Path.home() / ".openclaw" / "logs" / "telegram_command_audit.log"


def _load_env():
    load_env()


_load_env()

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


def _audit(event: str, chat_id: str, detail: str = "") -> None:
    try:
        line = f"{datetime.now().isoformat()} event={event} chat_id={chat_id} detail={detail}\n"
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def send_message(text: str, chat_id: str | None = None, reply_markup: dict | None = None):
    if not TG_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN 미설정")
        return
    cid = chat_id or TG_CHAT
    if not cid:
        log.warning("TELEGRAM_CHAT_ID 미설정")
        return
    payload: dict = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json=payload,
            timeout=5,
        )
    except Exception as e:
        log.error(f"send_message 실패: {e}")


def get_status_text() -> str:
    """현재 계좌 상태 + 보유종목 요약을 텍스트로 반환"""
    try:
        client = KiwoomClient()
        summary = client.get_asset_summary()
        s = summary
        lines = []
        lines.append("📊 <b>현재 계좌 상태</b>")
        lines.append(f"환경: {s['environment']}")
        lines.append(f"예수금: {s['deposit']:,}원")
        lines.append(f"추정자산: {s['estimated_asset']:,}원")
        lines.append(
            f"총매입/평가: {s['total_purchase']:,}원 → {s['total_evaluation']:,}원"
        )
        lines.append(
            f"누적 손익: {s['cumulative_pnl']:+,}원 ({s['cumulative_pnl_pct']:+.2f}%)"
        )
        lines.append(f"보유종목 수: {s['holdings_count']}개")
        if s["holdings"]:
            lines.append("")
            lines.append("📌 <b>보유종목</b>")
            for h in s["holdings"][:10]:
                lines.append(
                    f"  {h['name']} ({h['code']}) "
                    f"{h['quantity']}주 / 평단 {h['avg_price']:,}원 / "
                    f"손익 {h['pnl_pct']:+.2f}% ({h['pnl_amount']:+,}원)"
                )
            if s["holdings_count"] > 10:
                lines.append(f"  … 외 {s['holdings_count'] - 10}종목")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ 상태 조회 실패: {e}"


def set_stop_flag():
    """자동매매 중지 플래그 파일 생성 (에이전트는 이 파일을 보고 사이클 스킵하도록 향후 연계)"""
    flag = WORKSPACE / "stocks" / "STOP_TRADING"
    flag.write_text(datetime.now().isoformat())


def clear_stop_flag():
    flag = WORKSPACE / "stocks" / "STOP_TRADING"
    if flag.exists():
        flag.unlink()


def get_open_positions() -> list:
    """Supabase에서 OPEN 포지션 조회"""
    if not supabase:
        return []
    try:
        return (
            supabase.table("trade_executions")
            .select("*")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
    except Exception as e:
        log.error(f"get_open_positions 실패: {e}")
        return []


def group_by_code(positions: list) -> dict:
    from collections import defaultdict

    by_code: dict = defaultdict(list)
    for p in positions:
        code = p.get("stock_code")
        if code:
            by_code[code].append(p)
    return by_code


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def get_regime_text() -> str:
    try:
        from agents.regime_classifier import RegimeClassifier

        row = RegimeClassifier().classify()
        regime = row.get("regime", "TRANSITION")
        confidence = float(row.get("confidence", 0.0) or 0.0)
        factors = row.get("features", {}) or {}
        top_items = list(factors.items())[:5]
        lines = [
            "🌦 <b>현재 레짐</b>",
            f"Regime: <b>{regime}</b>",
            f"Confidence: {confidence:.2f}",
        ]
        if top_items:
            lines.append("")
            lines.append("주요 팩터:")
            for key, value in top_items:
                try:
                    rendered = f"{float(value):.4f}"
                except Exception:
                    rendered = str(value)
                lines.append(f"  {key}: {rendered}")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ 레짐 조회 실패: {e}"


def get_allocation_text() -> str:
    payload = _load_json(WORKSPACE / "brain/portfolio/market_allocation.json")
    allocation = payload.get("allocation") or {}
    if not allocation:
        return "⚠️ market_allocation.json이 없습니다."
    lines = [
        "🧭 <b>시장별 배분</b>",
        f"BTC: {float(allocation.get('btc', 0.0)) * 100:.1f}%",
        f"KR: {float(allocation.get('kr', 0.0)) * 100:.1f}%",
        f"US: {float(allocation.get('us', 0.0)) * 100:.1f}%",
        f"CASH: {float(allocation.get('cash', 0.0)) * 100:.1f}%",
        f"Updated: {payload.get('updated_at', '-')}",
        f"Regime: {payload.get('regime', '-')}",
    ]
    return "\n".join(lines)


def get_var_text() -> str:
    payload = _load_json(WORKSPACE / "brain/risk/latest_snapshot.json")
    if not payload:
        return "⚠️ latest_snapshot.json이 없습니다."
    lines = [
        "🛡 <b>리스크 스냅샷</b>",
        f"VaR 99: {float(payload.get('var_99', 0.0) or 0.0):.4f}",
        f"CVaR 95: {float(payload.get('cvar_95', 0.0) or 0.0):.4f}",
        f"Drawdown: {float(payload.get('drawdown', 0.0) or 0.0):.4f}",
        f"Positions: {len(payload.get('positions') or [])}",
        f"Updated: {payload.get('generated_at', '-')}",
    ]
    return "\n".join(lines)


def get_ml_status_text() -> str:
    kr_drift = _load_json(WORKSPACE / "brain/ml/drift_report.json")
    us_drift = _load_json(WORKSPACE / "brain/ml/us/drift_report.json")
    kr_meta = _load_json(WORKSPACE / "brain/ml/ensemble_meta.json")
    us_meta = _load_json(WORKSPACE / "brain/ml/us/ensemble_meta.json")
    lines = [
        "🤖 <b>ML 상태</b>",
        f"KR drift: {kr_drift.get('status', 'UNKNOWN')} (PSI {float(kr_drift.get('max_psi', 0.0) or 0.0):.3f})",
        f"US drift: {us_drift.get('status', 'UNKNOWN')} (PSI {float(us_drift.get('max_psi', 0.0) or 0.0):.3f})",
        f"KR OOS AUC: {float(kr_meta.get('oos_auc', 0.0) or 0.0):.3f}",
        f"US OOS AUC: {float(us_meta.get('oos_auc', 0.0) or 0.0):.3f}",
    ]
    return "\n".join(lines)


def get_arb_text() -> str:
    monitor = _load_json(WORKSPACE / "brain/arb/dex_monitor.json")
    execution = _load_json(WORKSPACE / "brain/arb/arb_execution.json")
    if not monitor:
        return "⚠️ dex_monitor.json이 없습니다."
    lines = [
        "🔁 <b>차익거래 상태</b>",
        f"Status: {monitor.get('status', 'UNKNOWN')}",
        f"Direction: {monitor.get('direction', 'unknown')}",
        f"Net Profit USD: {float(monitor.get('net_profit_usd', 0.0) or 0.0):.2f}",
        f"Gas USD: {float(monitor.get('gas_cost_usd', 0.0) or 0.0):.2f}",
        f"Executor Trigger: {execution.get('trigger', False)}",
        f"Reason: {execution.get('reason', '-')}",
    ]
    return "\n".join(lines)


def get_longshort_text() -> str:
    plan = _load_json(WORKSPACE / "brain/portfolio/long_short_plan.json")
    neutral = _load_json(WORKSPACE / "brain/portfolio/neutrality_report.json")
    if not plan:
        return "⚠️ long_short_plan.json이 없습니다."
    lines = [
        "⚖️ <b>롱숏 상태</b>",
        f"Regime: {plan.get('regime', '-')}",
        f"Long candidates: {len(plan.get('long_candidates') or [])}",
        f"Short candidates: {len(plan.get('short_candidates') or [])}",
        f"Net beta: {float(neutral.get('net_beta', 0.0) or 0.0):.3f}",
        f"Alert: {neutral.get('alert_level', 'UNKNOWN')}",
        f"Action: {neutral.get('recommendation', '-')}",
    ]
    return "\n".join(lines)


def get_api_usage_text() -> str:
    api_keys = []
    if supabase:
        try:
            api_keys = supabase.table("api_keys").select("id,tier,last_used_at").execute().data or []
        except Exception:
            api_keys = []
    webhooks = _load_json_list(WORKSPACE / "brain/webhooks/registry.json")
    push_devices = _load_json_list(WORKSPACE / "brain/push/devices.json")
    lines = [
        "📡 <b>Public API 상태</b>",
        f"API keys: {len(api_keys)}",
        f"Webhooks: {len(webhooks)}",
        f"Push devices: {len(push_devices)}",
    ]
    if api_keys:
        last_used = max((row.get("last_used_at") or "-" for row in api_keys), default="-")
        tiers = {}
        for row in api_keys:
            tier = row.get("tier") or "free"
            tiers[tier] = tiers.get(tier, 0) + 1
        lines.append(f"Last used: {last_used}")
        lines.append("Tiers: " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    else:
        lines.append("Last used: unavailable")
    return "\n".join(lines)


def build_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "⏹ 자동매매 중지(/stop)", "callback_data": "stop"},
                {"text": "💥 전량 매도(/sell_all)", "callback_data": "sell_all"},
            ],
            [
                {"text": "📊 상태 확인(/status)", "callback_data": "status"},
                {"text": "🌦 레짐(/regime)", "callback_data": "regime"},
            ],
            [
                {"text": "🧭 배분(/allocation)", "callback_data": "allocation"},
                {"text": "🛡 리스크(/var)", "callback_data": "var"},
            ],
        ]
    }


def handle_sell_all(chat_id: str):
    """1단계: 전량 매도 확인 요청"""
    positions = get_open_positions()
    if not positions:
        send_message("보유종목이 없습니다.", chat_id, reply_markup=build_keyboard())
        return

    by_code = group_by_code(positions)
    summary_lines = []
    for code, trades in by_code.items():
        qty = sum(int(t.get("quantity", 0)) for t in trades)
        name = trades[0].get("stock_name", code)
        summary_lines.append(f"  {name}: {qty}주")

    msg = (
        "⚠️ <b>전량 매도 확인</b>\n\n"
        "아래 종목을 시장가로 전량 매도합니다:\n"
        + "\n".join(summary_lines)
        + "\n\n정말 실행할까요?"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔴 전량 매도 실행", "callback_data": "CONFIRM_SELL_ALL"},
                {"text": "취소", "callback_data": "CANCEL_SELL_ALL"},
            ]
        ]
    }
    send_message(msg, chat_id, reply_markup=keyboard)


def handle_sell_all_confirm(chat_id: str):
    """2단계: 실제 전량 매도 실행"""
    if not supabase:
        send_message("Supabase 설정이 없습니다. 전량 매도를 실행할 수 없습니다.", chat_id)
        return

    from stocks.kiwoom_client import KiwoomClient as _KiwoomClient  # 안전한 재임포트

    kiwoom = _KiwoomClient()

    positions = get_open_positions()
    if not positions:
        send_message("보유종목이 없습니다.", chat_id, reply_markup=build_keyboard())
        return

    results: list[str] = []
    by_code = group_by_code(positions)

    for code, trades in by_code.items():
        qty = sum(int(t.get("quantity", 0)) for t in trades)
        if qty <= 0:
            continue
        name = trades[0].get("stock_name", code)
        try:
            result = kiwoom.place_order(code, "sell", qty, 0)  # 시장가
            if result.get("success"):
                # DB 포지션 CLOSED 처리
                for t in trades:
                    tid = t.get("trade_id")
                    if tid is None:
                        continue
                    try:
                        supabase.table("trade_executions").update(
                            {"result": "CLOSED_MANUAL"}
                        ).eq("trade_id", tid).execute()
                    except Exception as e:
                        results.append(f"❌ {name} DB 업데이트 실패: {e}")
                results.append(f"✅ {name} {qty}주 매도 완료")
            else:
                results.append(
                    f'❌ {name} 매도 실패: {result.get("message", "?")}'
                )
        except Exception as e:
            results.append(f"❌ {name} 매도 오류: {e}")

    if not results:
        results.append("실행 결과가 없습니다.")

    msg = "📊 <b>전량 매도 결과</b>\n\n" + "\n".join(results)
    send_message(msg, chat_id, reply_markup=build_keyboard())


def handle_command(cmd: str, chat_id: str):
    cmd = cmd.strip()
    if cmd.startswith("/status"):
        text = get_status_text()
        send_message(text, chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/stop"):
        set_stop_flag()
        send_message(
            "⏹ 자동매매 중지 플래그를 설정했습니다.\n"
            "※ 에이전트가 이 플래그를 보고 거래 사이클을 스킵하도록 연동 예정입니다.",
            chat_id,
            reply_markup=build_keyboard(),
        )
    elif cmd.startswith("/resume") or cmd.startswith("/start"):
        clear_stop_flag()
        send_message(
            "▶ 자동매매 중지 플래그를 해제했습니다.\n"
            "※ 실제 재개 여부는 에이전트 설정에 따라 달라집니다.",
            chat_id,
            reply_markup=build_keyboard(),
        )
    elif cmd.startswith("/sell_all"):
        handle_sell_all(chat_id)
    elif cmd.startswith("/regime"):
        send_message(get_regime_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/allocation"):
        send_message(get_allocation_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/var"):
        send_message(get_var_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/ml_status"):
        send_message(get_ml_status_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/arb"):
        send_message(get_arb_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/longshort"):
        send_message(get_longshort_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/api_usage"):
        send_message(get_api_usage_text(), chat_id, reply_markup=build_keyboard())
    elif cmd.startswith("/CONFIRM_SELL_ALL"):
        handle_sell_all_confirm(chat_id)
    elif cmd.startswith("/CANCEL_SELL_ALL"):
        send_message("전량 매도가 취소되었습니다.", chat_id, reply_markup=build_keyboard())
    else:
        send_message(
            "지원 명령:\n"
            "/status - 계좌 및 보유종목 상태\n"
            "/stop - 자동매매 중지 플래그 설정\n"
            "/resume - 자동매매 중지 플래그 해제\n"
            "/sell_all - 전량 매도 (2단계 확인)\n"
            "/regime - 현재 시장 레짐\n"
            "/allocation - BTC/KR/US 배분\n"
            "/var - 포트폴리오 VaR/CVaR\n"
            "/ml_status - KR/US ML 드리프트 상태\n"
            "/arb - DEX 차익거래 상태\n"
            "/longshort - 롱숏/넷베타 상태\n"
            "/api_usage - Public API 등록 상태\n",
            chat_id,
            reply_markup=build_keyboard(),
        )


def _is_authorized(chat_id: str) -> bool:
    """발신자 검증: TG_CHAT 미설정 시 모든 명령 차단."""
    if not TG_CHAT:
        log.warning(f"[보안] TELEGRAM_CHAT_ID 미설정 — 발신자({chat_id}) 차단")
        _audit("blocked_missing_chat_id", chat_id)
        return False
    allowed = str(chat_id) == str(TG_CHAT)
    if not allowed:
        _audit("blocked_unauthorized", chat_id)
    return allowed


def poll_updates():
    if not TG_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN 미설정. 종료.")
        return
    if not TG_CHAT:
        log.error("TELEGRAM_CHAT_ID 미설정. 보안상 봇을 시작하지 않습니다.")
        return

    last_update_id = None
    log.info("텔레그램 봇 폴링 시작...")
    while True:
        try:
            params = {"timeout": 30}
            if last_update_id is not None:
                params["offset"] = last_update_id + 1
            resp = requests.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                params=params,
                timeout=35,
            )
            data = resp.json()
            for upd in data.get("result", []):
                last_update_id = upd["update_id"]
                msg = upd.get("message") or upd.get("edited_message")
                cb = upd.get("callback_query")

                if cb:
                    cid = str(cb["message"]["chat"]["id"])
                    if not _is_authorized(cid):
                        continue
                    data_cmd = cb.get("data") or ""
                    _audit("callback_command", cid, data_cmd)
                    handle_command(f"/{data_cmd}", cid)
                    continue

                if not msg:
                    continue
                cid = str(msg["chat"]["id"])
                if not _is_authorized(cid):
                    continue
                text = msg.get("text") or ""
                if not text:
                    continue
                _audit("text_command", cid, text)
                handle_command(text, cid)
        except Exception as e:
            log.error(f"poll_updates 오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll_updates()
