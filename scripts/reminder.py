#!/usr/bin/env python3
"""
reminder.py — OpenClaw 리마인더 시스템

사용법:
  add --in "30m" --msg "메시지"           # 30분 후 1회
  add --in "2h" --msg "메시지"            # 2시간 후 1회
  add --at "09:00" --msg "메시지"         # 오늘(이미 지났으면 내일) 지정 시각
  add --daily "09:00" --msg "메시지"      # 매일 반복
  add --weekly "1 09:00" --msg "메시지"   # 매주 요일 반복 (1=월 ... 7=일)
  list                                    # 목록
  remove --id N                           # 삭제
  check                                   # 만료 확인 + 전송 (1분마다 cron 호출)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from common.env_loader import load_env

WORKSPACE = Path(__file__).resolve().parent.parent
BRAIN_DIR  = WORKSPACE / "brain"
REMINDERS  = BRAIN_DIR / "reminders.json"

WEEKDAY_KR = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}

load_env()


# ── Telegram ──────────────────────────────────────────────────────────────────

def _load_tg() -> tuple[str, str]:
    return os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def _send(msg: str) -> bool:
    if not requests:
        print("❌ requests 없음")
        return False
    token, chat_id = _load_tg()
    if not token or not chat_id:
        print(f"⚠️  Telegram 미설정 (TELEGRAM_CHAT_ID 확인)")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"❌ 전송 실패: {e}")
        return False


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    if REMINDERS.exists():
        return json.loads(REMINDERS.read_text(encoding="utf-8"))
    return {"reminders": [], "next_id": 1}


def _save(data: dict):
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    REMINDERS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_duration(s: str) -> timedelta:
    total = 0
    for val, unit in re.findall(r"(\d+)([hms])", s.lower()):
        v = int(val)
        if unit == "h":   total += v * 3600
        elif unit == "m": total += v * 60
        elif unit == "s": total += v
    if not total:
        raise ValueError(f"시간 형식 오류: {s}  (예: 30m, 2h, 1h30m)")
    return timedelta(seconds=total)


def _parse_hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _next_at(hour: int, minute: int) -> datetime:
    now = datetime.now()
    t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if t <= now:
        t += timedelta(days=1)
    return t


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args):
    data = load = _load()
    rid  = data["next_id"]
    msg  = args.msg

    if args.in_:
        delta = _parse_duration(args.in_)
        ft = datetime.now() + delta
        r = {"id": rid, "type": "once", "msg": msg,
             "fire_time": ft.strftime("%Y-%m-%dT%H:%M:%S"),
             "fired": False, "created": datetime.now().isoformat()}
        mins = int(delta.total_seconds() // 60)
        label = f"{mins}분 후 ({ft.strftime('%H:%M')})"

    elif args.at:
        h, m = _parse_hm(args.at)
        ft = _next_at(h, m)
        r = {"id": rid, "type": "once", "msg": msg,
             "fire_time": ft.strftime("%Y-%m-%dT%H:%M:%S"),
             "fired": False, "created": datetime.now().isoformat()}
        label = ft.strftime("%m/%d %H:%M")

    elif args.daily:
        h, m = _parse_hm(args.daily)
        r = {"id": rid, "type": "daily", "msg": msg,
             "hour": h, "minute": m, "active": True,
             "created": datetime.now().isoformat()}
        label = f"매일 {args.daily}"

    elif args.weekly:
        parts = args.weekly.split()
        wd = int(parts[0])
        h, m = _parse_hm(parts[1])
        r = {"id": rid, "type": "weekly", "msg": msg,
             "weekday": wd, "hour": h, "minute": m,
             "active": True, "created": datetime.now().isoformat()}
        label = f"매주 {WEEKDAY_KR.get(wd, wd)}요일 {parts[1]}"

    else:
        print("오류: --in / --at / --daily / --weekly 중 하나 필요")
        sys.exit(1)

    data["reminders"].append(r)
    data["next_id"] += 1
    _save(data)
    print(f"✅ 리마인더 #{rid} 등록: {label} — '{msg}'")


def cmd_list(args):
    data = _load()
    active = [r for r in data["reminders"] if not r.get("fired")]
    if not active:
        print("등록된 리마인더 없음")
        return
    print(f"{'ID':>3}  {'타입':<8}  {'시간':<20}  메시지")
    print("─" * 55)
    for r in active:
        if r["type"] == "once":
            ts = r["fire_time"][5:16].replace("T", " ")
        elif r["type"] == "daily":
            ts = f"매일 {r['hour']:02d}:{r['minute']:02d}"
        else:
            ts = f"매주 {WEEKDAY_KR.get(r['weekday'], r['weekday'])}요일 {r['hour']:02d}:{r['minute']:02d}"
        print(f"{r['id']:>3}  {r['type']:<8}  {ts:<20}  {r['msg']}")


def cmd_remove(args):
    data = _load()
    before = len(data["reminders"])
    data["reminders"] = [r for r in data["reminders"] if r["id"] != args.id]
    if len(data["reminders"]) < before:
        _save(data)
        print(f"✅ 리마인더 #{args.id} 삭제")
    else:
        print(f"⚠️  #{args.id} 없음")


def cmd_check(args):
    """1분마다 cron이 호출 — 만료된 리마인더 전송"""
    data  = _load()
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    changed = False

    for r in data["reminders"]:
        fire = False

        if r["type"] == "once" and not r.get("fired"):
            if now >= datetime.fromisoformat(r["fire_time"]):
                fire = True

        elif r["type"] == "daily" and r.get("active", True):
            if now.hour == r["hour"] and now.minute == r["minute"]:
                if r.get("last_fired") != today:
                    fire = True

        elif r["type"] == "weekly" and r.get("active", True):
            if (now.isoweekday() == r["weekday"]
                    and now.hour == r["hour"]
                    and now.minute == r["minute"]
                    and r.get("last_fired") != today):
                fire = True

        if fire:
            ok = _send(f"⏰ <b>리마인더</b>\n{r['msg']}")
            if ok:
                print(f"✅ #{r['id']} 전송: {r['msg']}")
                if r["type"] == "once":
                    r["fired"] = True
                else:
                    r["last_fired"] = today
                changed = True

    # 7일 이상 지난 1회성 정리
    cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    data["reminders"] = [
        r for r in data["reminders"]
        if not (r.get("fired") and r.get("fire_time", "9999") < cutoff)
    ]

    if changed:
        _save(data)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenClaw 리마인더")
    sub = parser.add_subparsers(dest="cmd")

    pa = sub.add_parser("add", help="리마인더 추가")
    pa.add_argument("--in", dest="in_",   help="지연 (예: 30m, 2h)")
    pa.add_argument("--at",               help="당일/익일 시각 (예: 09:00)")
    pa.add_argument("--daily",            help="매일 시각 (예: 09:00)")
    pa.add_argument("--weekly",           help="매주 (예: '1 09:00'=월요일)")
    pa.add_argument("--msg", required=True, help="알림 메시지")

    sub.add_parser("list",   help="목록")
    pr = sub.add_parser("remove", help="삭제")
    pr.add_argument("--id", type=int, required=True)
    sub.add_parser("check",  help="만료 확인 (cron용)")

    args = parser.parse_args()
    {"add": cmd_add, "list": cmd_list, "remove": cmd_remove, "check": cmd_check}.get(
        args.cmd, lambda _: parser.print_help()
    )(args)


if __name__ == "__main__":
    main()
