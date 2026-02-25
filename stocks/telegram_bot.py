#!/usr/bin/env python3
"""
텔레그램 제어 봇 (초기 버전)

기능:
- /status  : 현재 계좌 요약 + 보유종목 요약 전송
- /stop    : 자동매매 중지 플래그 파일 생성 (크론은 그대로, 에이전트 쪽에서 추후 플래그를 참고하도록 설계)
- /sell_all: (안전 장치 설계 전) 현재는 안내 메시지/경고만 전송

주의:
- 키움/주식 매매는 이 봇에서 직접 호출하지 않는다. (추후 안전한 연계 설계 후 확장)
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime

import requests

from kiwoom_client import KiwoomClient
from supabase import create_client


def _load_env():
    openclaw_json = Path("/home/wlsdud5035/.openclaw/openclaw.json")
    if openclaw_json.exists():
        data = json.loads(openclaw_json.read_text())
        for k, v in (data.get("env") or {}).items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
    for p in [
        Path("/home/wlsdud5035/.openclaw/.env"),
        Path("/home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env"),
    ]:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


def send_message(text: str, chat_id: str | None = None, reply_markup: dict | None = None):
    if not TG_TOKEN:
        print("TELEGRAM_BOT_TOKEN 미설정")
        return
    cid = chat_id or TG_CHAT
    if not cid:
        print("TELEGRAM_CHAT_ID 미설정")
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
        print(f"send_message 실패: {e}")


def get_status_text() -> str:
    """현재 계좌 상태 + 보유종목 요약을 텍스트로 반환"""
    try:
        client = KiwoomClient()
        summary = client.get_asset_summary()
        s = summary
        lines = []
        lines.append(f"📊 <b>현재 계좌 상태</b>")
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
    flag = Path("/home/wlsdud5035/.openclaw/workspace/stocks/STOP_TRADING")
    flag.write_text(datetime.now().isoformat())


def clear_stop_flag():
    flag = Path("/home/wlsdud5035/.openclaw/workspace/stocks/STOP_TRADING")
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
        print(f"get_open_positions 실패: {e}")
        return []


def group_by_code(positions: list) -> dict:
    from collections import defaultdict

    by_code: dict = defaultdict(list)
    for p in positions:
        code = p.get("stock_code")
        if code:
            by_code[code].append(p)
    return by_code


def build_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "⏹ 자동매매 중지(/stop)", "callback_data": "stop"},
                {"text": "💥 전량 매도(/sell_all)", "callback_data": "sell_all"},
            ],
            [
                {"text": "📊 상태 확인(/status)", "callback_data": "status"},
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
            "/sell_all - (예정) 전량 매도\n",
            chat_id,
            reply_markup=build_keyboard(),
        )


def poll_updates():
    if not TG_TOKEN:
        print("TELEGRAM_BOT_TOKEN 미설정. 종료.")
        return

    last_update_id = None
    print("텔레그램 봇 폴링 시작...")
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
                    if TG_CHAT and cid != str(TG_CHAT):
                        continue
                    data_cmd = cb.get("data") or ""
                    handle_command(f"/{data_cmd}", cid)
                    continue

                if not msg:
                    continue
                cid = str(msg["chat"]["id"])
                if TG_CHAT and cid != str(TG_CHAT):
                    continue
                text = msg.get("text") or ""
                if not text:
                    continue
                handle_command(text, cid)
        except Exception as e:
            print(f"poll_updates 오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll_updates()

