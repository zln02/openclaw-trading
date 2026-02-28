"""
매매 체결 시 Google Sheets 자동 기록 (OpenClaw gog 연동).

사용법:
  1. gog CLI: brew install steipete/tap/gogcli 후 gog auth add --services sheets
  2. 또는 gspread: GOOGLE_SHEETS_CREDENTIALS_JSON 경로 설정

환경변수:
  - GOOGLE_SHEET_ID: 시트 ID (필수)
  - GOOGLE_SHEET_TAB: 탭명 (기본 "거래기록")
  - GOG_KEYRING_PASSWORD: gog 사용 시 (openclaw-gog-secret)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ── 환경 로드 ──────────────────────────────────────
try:
    from common.env_loader import load_env
    load_env()
except ImportError:
    pass

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
SHEET_TAB = os.environ.get("GOOGLE_SHEET_TAB", "거래기록")
GOG_PASSWORD = os.environ.get("GOG_KEYRING_PASSWORD", "openclaw-gog-secret")


def _escape(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t.replace('"', '""').replace("\n", " ").replace("\r", "")


def _row(
    date: str,
    market: str,
    action: str,
    symbol: str,
    symbol_name: str,
    price: str,
    quantity: str,
    pnl_pct: str,
    reason: str,
    news_summary: str = "",
    agent: str = "",
) -> list[str]:
    return [
        date,
        market,
        action,
        symbol,
        symbol_name,
        price,
        quantity,
        pnl_pct,
        reason,
        news_summary,
        agent,
    ]


def _append_via_gog(rows: list[list[str]]) -> bool:
    """gog CLI로 시트에 append."""
    # gog-docker를 직접 사용
    import sys
    workspace_dir = Path(__file__).resolve().parents[1]
    gog_path = workspace_dir / "gog-docker"
    
    if not gog_path.exists():
        # fallback to system gog
        gog_path = shutil.which("gog")
        if not gog_path:
            return False
    if not SHEET_ID:
        return False
    try:
        range_str = f"{SHEET_TAB}!A:K"
        values_json = json.dumps(rows, ensure_ascii=False)
        env = os.environ.copy()
        env["GOG_KEYRING_PASSWORD"] = GOG_PASSWORD
        result = subprocess.run(
            [
                str(gog_path),
                "sheets",
                "append",
                SHEET_ID,
                range_str,
                "--values-json",
                values_json,
                "--insert",
                "INSERT_ROWS",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _append_via_gspread(rows: list[list[str]]) -> bool:
    """gspread로 시트에 append (fallback)."""
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if not creds_path or not Path(creds_path).exists():
        return False
    if not SHEET_ID:
        return False
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False


def append_trade(
    market: str,
    action: str,
    symbol: str,
    price: float,
    quantity: float,
    pnl_pct: Optional[float] = None,
    reason: str = "",
    news_summary: str = "",
    symbol_name: str = "",
    agent: str = "",
) -> bool:
    """
    매매 체결 시 구글 시트에 한 행 추가 (개선된 버전).

    Args:
        market: "btc" | "kr" | "us"
        action: "매수" | "매도" | "손절" | "익절"
        symbol: "BTC" | "005930" | "AAPL" 등 종목코드
        symbol_name: "비트코인" | "삼성전자" | "애플" 등 종목명
        price: 체결가
        quantity: 수량
        pnl_pct: 수익률 (매도/손절/익절 시)
        reason: 진입/청산 근거
        news_summary: 당시 뉴스 요약 (선택)
        agent: "btc_agent" | "kr_agent" | "us_agent" 등 에이전트명
    """
    if not SHEET_ID:
        return False
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 가격 포맷팅
    if isinstance(price, (int, float)):
        if market.lower() == "btc":
            price_str = f"{price:,.0f}"
        elif market.lower() == "us":
            price_str = f"${price:,.2f}"
        else:  # kr
            price_str = f"{price:,.0f}"
    else:
        price_str = str(price)
    
    # 수량 포맷팅
    if isinstance(quantity, (int, float)):
        if market.lower() == "btc":
            qty_str = f"{quantity:.6f}"
        elif market.lower() == "us":
            qty_str = f"{quantity:.2f}"
        else:  # kr
            qty_str = f"{quantity:.0f}"
    else:
        qty_str = str(quantity)
    
    # 수익률 포맷팅
    pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else ""
    
    # 종목명 자동 완성
    if not symbol_name:
        symbol_names = {
            "BTC": "비트코인",
            "005930": "삼성전자",
            "000660": "SK하이닉스",
            "AAPL": "애플",
            "TSLA": "테슬라",
            "MSFT": "마이크로소프트",
        }
        symbol_name = symbol_names.get(symbol.upper(), symbol)
    
    # 에이전트명 자동 완성
    if not agent:
        agent = f"{market}_agent"
    
    row = _row(
        date=date_str,
        market=market.upper(),
        action=action,
        symbol=symbol,
        symbol_name=symbol_name,
        price=price_str,
        quantity=qty_str,
        pnl_pct=pnl_str,
        reason=_escape(reason)[:200],
        news_summary=_escape(news_summary)[:150],
        agent=agent,
    )
    if _append_via_gog([row]):
        return True
    if _append_via_gspread([row]):
        return True
    return False


def is_configured() -> bool:
    """구글 시트 연동이 설정되어 있는지 확인."""
    # gog-docker 확인
    workspace_dir = Path(__file__).resolve().parents[1]
    gog_docker_path = workspace_dir / "gog-docker"
    
    has_gog = gog_docker_path.exists() or shutil.which("gog")
    return bool(SHEET_ID and (has_gog or os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")))
