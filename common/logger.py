"""Structured logging for all OpenClaw agents.

Usage:
    from common.logger import get_logger
    log = get_logger("btc_agent")
    log.info("매매 사이클 시작")
    log.trade("BTC 매수", price=142000000, qty=0.001)
    log.warn("거래량 급감")
"""
from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from common.config import LOG_DIR

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FMT = "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Custom TRADE level (between INFO and WARNING)
TRADE_LEVEL = 25
logging.addLevelName(TRADE_LEVEL, "TRADE")

_loggers: dict[str, "AgentLogger"] = {}

_JSON_RESERVED = {
    "name", "msg", "args", "levelname", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created",
    "msecs", "relativeCreated", "thread", "threadName", "processName",
    "process", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    """로그 레코드를 JSON-line 으로 직렬화 (구조화 로그용)."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":  record.levelname,
            "logger": record.name,
            "event":  record.message,
        }
        # log.trade("BTC 매수", market="btc", action="buy", price=142000000)
        # → extra 필드로 JSON에 포함
        for key, val in record.__dict__.items():
            if key not in _JSON_RESERVED and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, ensure_ascii=False)


class AgentLogger:
    """Thin wrapper around stdlib logging with a TRADE level and emoji prefixes."""

    EMOJI = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "TRADE": "💰",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }

    def __init__(self, name: str, log_file: Optional[Path] = None):
        self._log = logging.getLogger(f"openclaw.{name}")
        if self._log.handlers:
            return  # already configured
        self._log.setLevel(logging.DEBUG)

        formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

        # Console handler (INFO+)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self._log.addHandler(ch)

        # File handler — stdout이 터미널일 때만 (cron 리다이렉트 시 중복 방지)
        if log_file is None:
            log_file = LOG_DIR / f"{name}.log"
        if sys.stdout.isatty():
            try:
                if log_file.exists() and not os.access(log_file, os.W_OK):
                    try:
                        log_file.unlink()
                    except PermissionError:
                        pass
                fh = RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5,
                    encoding="utf-8",
                )
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(formatter)
                self._log.addHandler(fh)
            except PermissionError:
                pass

        # JSON handler — 구조화 로그 (DEBUG+)
        json_dir = LOG_DIR / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = json_dir / f"{name}.jsonl"
        try:
            # 권한 문제(root가 먼저 생성한 경우)를 방어: 쓰기 가능하면 그대로, 아니면 삭제 후 재생성
            if jsonl_path.exists() and not os.access(jsonl_path, os.W_OK):
                try:
                    jsonl_path.unlink()
                except PermissionError:
                    pass  # 삭제도 안 되면 JSON 핸들러 없이 진행
            jfh = logging.FileHandler(jsonl_path, encoding="utf-8")
            jfh.setLevel(logging.DEBUG)
            jfh.setFormatter(JsonFormatter())
            self._log.addHandler(jfh)
        except PermissionError:
            pass  # JSON 구조화 로그 생략, 텍스트 로그는 정상 작동

    # ── convenience methods ──

    def debug(self, msg: str, **kw):
        self._log.debug(self._fmt(msg, "DEBUG", **kw), extra=kw)

    def info(self, msg: str, **kw):
        self._log.info(self._fmt(msg, "INFO", **kw), extra=kw)

    def trade(self, msg: str, **kw):
        self._log.log(TRADE_LEVEL, self._fmt(msg, "TRADE", **kw), extra=kw)

    def warn(self, msg: str, **kw):
        self._log.warning(self._fmt(msg, "WARNING", **kw), extra=kw)

    # Python logging 표준 메서드명 호환
    warning = warn

    def error(self, msg: str, **kw):
        self._log.error(self._fmt(msg, "ERROR", **kw), extra=kw)

    def critical(self, msg: str, **kw):
        self._log.critical(self._fmt(msg, "CRITICAL", **kw), extra=kw)

    @classmethod
    def _fmt(cls, msg: str, level: str, **kw) -> str:
        """텍스트 로그 포맷 (기존 형식 유지)."""
        prefix = cls.EMOJI.get(level, "")
        extra = ""
        if kw:
            parts = [f"{k}={v}" for k, v in kw.items()]
            extra = " | " + ", ".join(parts)
        return f"{prefix} {msg}{extra}"


def get_logger(name: str, log_file: Optional[Path] = None) -> AgentLogger:
    """Get or create a named logger (singleton per name)."""
    if name not in _loggers:
        _loggers[name] = AgentLogger(name, log_file)
    return _loggers[name]
