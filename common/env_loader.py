"""Environment variable loader - openclaw.json + .env files."""
import os
import json
from pathlib import Path

_OPENCLAW_ROOT = Path("/home/wlsdud5035/.openclaw")
_loaded = False


def load_env() -> None:
    """Load openclaw.json env + .env files into os.environ (idempotent)."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    openclaw_json = _OPENCLAW_ROOT / "openclaw.json"
    if openclaw_json.exists():
        try:
            data = json.loads(openclaw_json.read_text())
            for k, v in (data.get("env") or {}).items():
                if k != "shellEnv" and isinstance(v, str):
                    os.environ.setdefault(k, v)
        except Exception:
            pass

    env_files = [
        _OPENCLAW_ROOT / ".env",
        _OPENCLAW_ROOT / "workspace" / ".env",
        _OPENCLAW_ROOT / "workspace" / "skills" / "kiwoom-api" / ".env",
    ]
    for p in env_files:
        if not p.exists():
            continue
        try:
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip("'\"").replace("\\n", "\n")
                    if k:
                        os.environ.setdefault(k, v)
        except Exception:
            continue
