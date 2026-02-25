#!/usr/bin/env python3
"""
잔고-DB 동기화 유틸리티

역할:
- 키움 실제 계좌 보유종목(평균단가/수량)을 조회
- Supabase trade_executions (result='OPEN')와 비교
- 유령 포지션(실제로는 0주인데 DB에는 OPEN으로 남은 것)을 정리

주의:
- 기본은 dry-run(check) 모드로 동작.
- apply 모드에서도 **실제 주문은 절대 내지 않고**, DB 상태만 보수적으로 정리한다.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

from supabase import create_client

from kiwoom_client import KiwoomClient


def _load_env():
    """openclaw.json + .env 로 Supabase/키움 환경 세팅"""
    openclaw_json = Path("/home/wlsdud5035/.openclaw/openclaw.json")
    if openclaw_json.exists():
        d = json.loads(openclaw_json.read_text())
        for k, v in (d.get("env") or {}).items():
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


def _log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅"}.get(level, "")
    print(f"[{ts}] {prefix} {msg}")


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY 환경변수가 필요합니다.")
    return create_client(url, key)


def fetch_open_positions(sb) -> list:
    """Supabase에서 result='OPEN' 포지션 전부 가져오기"""
    try:
        data = (
            sb.table("trade_executions")
            .select("*")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
        return data
    except Exception as e:
        _log(f"OPEN 포지션 조회 실패: {e}", "ERROR")
        return []


def plan_sync(holdings: list, open_positions: list) -> dict:
    """
    계좌 보유종목 vs DB OPEN 포지션 비교해서
    - 유령 포지션(실제 0주인데 DB OPEN) 만 보수적으로 정리하는 플랜 생성.
    """
    # 키움 실제 보유 수량
    actual_qty = {}
    for h in holdings:
        code = h.get("code")
        if not code:
            continue
        qty = int(h.get("quantity") or 0)
        actual_qty[code] = actual_qty.get(code, 0) + qty

    # DB OPEN 포지션 수량
    db_by_code = {}
    for p in open_positions:
        code = p.get("stock_code")
        if not code:
            continue
        db_by_code.setdefault(code, []).append(p)

    close_ids = []
    report = []

    for code, positions in db_by_code.items():
        db_qty = sum(int(p.get("quantity") or 0) for p in positions)
        ac_qty = int(actual_qty.get(code, 0))

        if db_qty > 0 and ac_qty == 0:
            # 유령 포지션: 실제로는 0주인데 DB에는 OPEN
            ids = [p.get("trade_id") for p in positions if p.get("trade_id") is not None]
            close_ids.extend(ids)
            report.append(
                {
                    "code": code,
                    "db_qty": db_qty,
                    "actual_qty": ac_qty,
                    "action": "CLOSE_GHOST",
                    "trade_ids": ids,
                }
            )
        elif db_qty != ac_qty:
            # 양쪽 수량 불일치 (부분 체결/수동 거래 등) — 일단은 로그만 남기고 손대지 않음
            report.append(
                {
                    "code": code,
                    "db_qty": db_qty,
                    "actual_qty": ac_qty,
                    "action": "MISMATCH_WARN",
                    "trade_ids": [
                        p.get("trade_id") for p in positions if p.get("trade_id") is not None
                    ],
                }
            )

    return {"close_ids": close_ids, "report": report}


def apply_sync(sb, plan: dict):
    """plan_sync 결과를 기반으로 DB에 최소한의 수정만 적용"""
    close_ids = plan.get("close_ids") or []
    if not close_ids:
        _log("적용할 유령 포지션 없음", "OK")
        return

    _log(f"유령 포지션 정리 대상 trade_id {len(close_ids)}개", "WARN")
    for tid in close_ids:
        try:
            sb.table("trade_executions").update(
                {"result": "CLOSED_SYNC"}
            ).eq("trade_id", tid).execute()
        except Exception as e:
            _log(f"trade_id={tid} CLOSED_SYNC 업데이트 실패: {e}", "ERROR")

    _log("유령 포지션 정리 완료", "OK")


def main():
    _load_env()
    sb = get_supabase_client()
    kiwoom = KiwoomClient()

    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in ("check", "apply"):
        print("사용법: python sync_manager.py [check|apply]")
        sys.exit(1)

    _log("계좌 평가/보유종목 조회 중...")
    account = kiwoom.get_account_evaluation()
    holdings = account.get("holdings", [])
    _log(f"  실제 보유종목: {len(holdings)}개")

    _log("DB OPEN 포지션 조회 중...")
    open_positions = fetch_open_positions(sb)
    _log(f"  DB OPEN 포지션: {len(open_positions)}개")

    plan = plan_sync(holdings, open_positions)

    # 리포트 출력
    ghosts = [r for r in plan["report"] if r["action"] == "CLOSE_GHOST"]
    mismatches = [r for r in plan["report"] if r["action"] == "MISMATCH_WARN"]

    if ghosts:
        _log("유령 포지션 후보:", "WARN")
        for g in ghosts:
            _log(
                f"  {g['code']}: DB {g['db_qty']}주 / 실제 {g['actual_qty']}주 "
                f"(trade_id={g['trade_ids']})",
                "WARN",
            )
    else:
        _log("유령 포지션 없음", "OK")

    if mismatches:
        _log("수량 불일치 경고 (자동 수정 안 함):", "WARN")
        for m in mismatches:
            _log(
                f"  {m['code']}: DB {m['db_qty']}주 / 실제 {m['actual_qty']}주 "
                f"(trade_id={m['trade_ids']})",
                "WARN",
            )

    if mode == "apply":
        apply_sync(sb, plan)
    else:
        _log("check 모드 — DB는 변경하지 않았습니다.", "INFO")


if __name__ == "__main__":
    main()

