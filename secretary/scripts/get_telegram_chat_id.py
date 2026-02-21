#!/usr/bin/env python3
"""
봇이 받은 최근 메시지의 chat.id를 출력.
텔레그램에서 "채팅 ID 알려줘" 라고 보낸 뒤 이 스크립트를 실행하면 해당 채팅 ID가 나옴.
"""
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트 기준 .env
_root = Path(__file__).resolve().parent.parent
_openclaw = _root.parent / ".openclaw"
for _env in (_openclaw / ".env", _root / ".env"):
    if _env.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_env)
            break
        except ImportError:
            pass

token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not token:
    # openclaw.json에서 읽기 (OPENCLAW_CONFIG_DIR 또는 secretary 기준 상위 .openclaw)
    _cfg_dirs = [os.getenv("OPENCLAW_CONFIG_DIR"), str(_openclaw), str(_root.parent.parent)]
    for _d in _cfg_dirs:
        if not _d:
            continue
        _p = Path(_d) / "openclaw.json"
        if not _p.exists():
            _p = Path(_d) / ".openclaw" / "openclaw.json" if Path(_d).name != ".openclaw" else Path(_d) / "openclaw.json"
        try:
            if _p.exists():
                with open(_p) as f:
                    cfg = json.load(f)
                token = (cfg.get("channels", {}).get("telegram", {}).get("botToken") or "").strip()
                if token:
                    break
        except Exception:
            pass

if not token:
    print("TELEGRAM_BOT_TOKEN 또는 openclaw.json의 channels.telegram.botToken이 필요합니다.", file=sys.stderr)
    sys.exit(1)

try:
    import urllib.request
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=5"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
except Exception as e:
    print(f"getUpdates 실패: {e}", file=sys.stderr)
    sys.exit(1)

results = data.get("result") or []
if not results:
    print("아직 봇이 받은 메시지가 없습니다. 텔레그램에서 봇에게 메시지를 보낸 뒤 다시 실행하세요.", file=sys.stderr)
    sys.exit(1)

# 가장 최근 메시지의 chat.id
last = results[-1]
msg = last.get("message") or last.get("edited_message") or {}
chat = msg.get("chat") or {}
chat_id = chat.get("id")
if chat_id is None:
    print("chat_id를 찾을 수 없습니다.", file=sys.stderr)
    sys.exit(1)

print(chat_id)
print("위 숫자를 .env에 TELEGRAM_CHAT_ID= 로 넣으세요.", file=sys.stderr)
