"""Environment variable loader - openclaw.json + .env files."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from common.config import OPENCLAW_JSON, OPENCLAW_ROOT, WORKSPACE

_loaded = False
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not _ENV_KEY_RE.match(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        hash_index = value.find(" #")
        if hash_index != -1:
            value = value[:hash_index].rstrip()
        parsed[key] = value.replace("\\n", "\n")
    return parsed


def _load_secret_dir(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists() or not path.is_dir():
        return parsed
    for child in path.iterdir():
        if not child.is_file():
            continue
        key = child.name.strip()
        if not _ENV_KEY_RE.match(key):
            continue
        try:
            parsed[key] = child.read_text(encoding="utf-8").strip()
        except Exception:
            continue
    return parsed


def load_env() -> None:
    """Load openclaw.json env + .env files into os.environ (idempotent)."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    if OPENCLAW_JSON.exists():
        try:
            data = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
            for k, v in (data.get("env") or {}).items():
                if k != "shellEnv" and isinstance(v, str):
                    os.environ.setdefault(k, v)
            telegram_token = ((data.get("channels") or {}).get("telegram") or {}).get("botToken")
            if isinstance(telegram_token, str) and telegram_token:
                os.environ.setdefault("TELEGRAM_BOT_TOKEN", telegram_token)
        except Exception:
            pass

    env_files = [
        OPENCLAW_ROOT / ".env",
        WORKSPACE / ".env",
        WORKSPACE / "skills" / "kiwoom-api" / ".env",
    ]
    for p in env_files:
        if not p.exists():
            continue
        try:
            for k, v in _parse_env_file(p).items():
                os.environ.setdefault(k, v)
        except Exception:
            continue

    secret_dirs = [
        Path("/run/secrets/openclaw"),
        WORKSPACE / ".docker-secrets",
        OPENCLAW_ROOT / ".docker-secrets",
    ]
    for p in secret_dirs:
        try:
            for k, v in _load_secret_dir(p).items():
                os.environ.setdefault(k, v)
        except Exception:
            continue
