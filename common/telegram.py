"""Telegram message sender utility."""
import os
import requests


def send_telegram(msg: str, parse_mode: str = "HTML") -> bool:
    """Send a telegram message. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": parse_mode},
            timeout=5,
        )
        return True
    except Exception:
        return False
