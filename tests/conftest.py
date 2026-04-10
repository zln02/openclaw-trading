"""pytest 공통 픽스처 — OpenClaw Trading System."""
import os
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 테스트 환경변수 (실제 API 호출 차단)
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "mock-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("UPBIT_ACCESS_KEY", "test-key")
os.environ.setdefault("UPBIT_SECRET_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")

import pytest


@pytest.fixture
def sample_kr_trade():
    return {
        "trade_id": "test-001",
        "symbol": "005930",
        "trade_type": "SELL",
        "entry_price": 70000,
        "price": 72100,
        "quantity": 10,
        "pnl_pct": 3.0,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }


@pytest.fixture
def sample_us_trade():
    return {
        "trade_id": "test-002",
        "symbol": "AAPL",
        "trade_type": "SELL",
        "entry_price": 180.0,
        "exit_price": 185.4,
        "quantity": 5,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }


@pytest.fixture
def sample_btc_trade():
    return {
        "id": "test-003",
        "action": "SELL",
        "entry_price": 95000000,
        "price": 97850000,
        "pnl": 2850000,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }
