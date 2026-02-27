"""Telegram message sender utility with retry."""
import os
import time
import requests

_last_send_ts = 0.0
_MIN_INTERVAL = 1.0  # rate-limit: 1 msg/sec


def send_telegram(msg: str, parse_mode: str = "HTML", retries: int = 2) -> bool:
    """Send a telegram message with retry and rate-limiting.

    Returns True on success, False otherwise.
    """
    global _last_send_ts
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    # rate-limit
    elapsed = time.time() - _last_send_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": parse_mode},
                timeout=10,
            )
            _last_send_ts = time.time()
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue
            return resp.ok
        except Exception:
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
    return False
