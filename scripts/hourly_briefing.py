#!/usr/bin/env python3
"""
텔레그램 매시 정각 요약 브리핑 스크립트.

- Priority.INFO 등급으로 기록된 메시지를 기반으로 직전 1시간 요약을 1건 전송
- 개별 이벤트 알림(손절/분할 진입/분할 익절/에러)은 그대로 즉시 발송
- HOLD 스킵, 스코어 체크, 일반 로그는 INFO 버퍼에만 쌓이고 여기서만 요약됨
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import _INFO_BUFFER_FILE, Priority, send_telegram

load_env()
log = get_logger("hourly_briefing")


def _load_info_data() -> dict:
    if not _INFO_BUFFER_FILE.exists():
        return {}
    try:
        return json.loads(_INFO_BUFFER_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("failed to load telegram info buffer", error=str(exc))
        return {}


def _save_info_data(data: dict) -> None:
    try:
        _INFO_BUFFER_FILE.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        log.warning("failed to save telegram info buffer", error=str(exc))


# 헬스체크/노이즈 필터 — 이 키워드가 포함된 메시지는 브리핑에서 제외
_NOISE_KEYWORDS = (
    "HOLD", "스코어 체크", "사이클 완료", "heartbeat", "체크 완료",
    "포지션 없음", "매매 대기", "대기 중", "check complete",
    "health ok", "헬스체크", "주기 체크",
)

# 중요 이벤트 키워드 — 이게 포함되면 무조건 포함
_IMPORTANT_KEYWORDS = (
    "매수", "매도", "진입", "익절", "손절", "청산", "에러", "ERROR",
    "경고", "WARNING", "분할", "포지션 진입", "포지션 종료",
)


def _is_noise(msg: str) -> bool:
    """헬스체크·노이즈 메시지 여부 판별."""
    lower = msg.lower()
    # 중요 이벤트는 노이즈가 아님
    for kw in _IMPORTANT_KEYWORDS:
        if kw in msg:
            return False
    # 노이즈 키워드 포함 시 제외
    for kw in _NOISE_KEYWORDS:
        if kw in msg:
            return True
    return False


def build_hourly_brief(prev_hour: datetime, msgs: list[str]) -> str:
    """직전 1시간 요약 메시지 문자열 생성."""
    if not msgs:
        return ""

    start = prev_hour.strftime("%H:00")
    end = (prev_hour + timedelta(hours=1)).strftime("%H:00")

    # 노이즈 필터링 후 중요 메시지만 추출
    filtered = [m for m in msgs if not _is_noise(m)]
    total = len(msgs)
    skipped = total - len(filtered)

    header = f"⏰ <b>{start}~{end} 요약 브리핑</b>\n─────────────────────"

    # 최대 8개, 첫 줄 기준 80자 요약
    lines: list[str] = []
    for raw in filtered[-8:]:
        first_line = (raw.splitlines() or [""])[0].strip()
        if not first_line:
            continue
        if len(first_line) > 80:
            first_line = first_line[:77] + "..."
        lines.append(f"• {first_line}")

    if not lines:
        # 중요 이벤트 없으면 조용히 스킵 (이상 없음 메시지도 안 보냄)
        return ""

    footer = f"\n─────────────────────\n로그 {total}건 중 {skipped}건 필터됨"
    return header + "\n" + "\n".join(lines) + footer


def run() -> int:
    now = datetime.now()
    prev = (now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1))

    data = _load_info_data()
    if not data:
        log.info("no info buffer data found")
        return 0

    date_str = prev.strftime("%Y-%m-%d")
    if data.get("date") != date_str:
        # 날짜가 다르면 해당 날짜에 대한 버퍼가 없다고 판단
        log.info("buffer date mismatch — skip briefing", buffer_date=data.get("date"), target=date_str)
        return 0

    hours = data.get("hours") or {}
    hour_key = prev.strftime("%H")
    hour_msgs = hours.get(hour_key) or []

    if not hour_msgs:
        log.info("no info messages for prev hour", hour=hour_key)
        return 0

    text = build_hourly_brief(prev, hour_msgs)
    if not text:
        log.info("empty hourly brief text — skip send", hour=hour_key)
        return 0

    ok = send_telegram(text, priority=Priority.IMPORTANT)
    log.info("hourly briefing send result", hour=hour_key, sent=ok)

    # 동일 시각 요약이 중복 발송되지 않도록 해당 버킷 비우기
    hours[hour_key] = []
    data["hours"] = hours
    _save_info_data(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
