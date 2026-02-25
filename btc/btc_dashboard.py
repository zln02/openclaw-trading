#!/usr/bin/env python3
"""
BTC 자동매매 대시보드 — 업비트 스타일 프로 버전
포트: 8080
"""

import os, json, subprocess, requests, time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from supabase import create_client
import psutil

# Upbit API 60초 캐시 (KRW 잔고, upbit_ok)
_upbit_cache = {"time": 0, "krw": None, "ok": False}

# Cryptopanic 뉴스 5분 캐시 (429 한도 회피)
_news_cache = {"data": [], "ts": 0}
NEWS_CACHE_TTL = 300

# 1시간봉 추세 5분 캐시
_trend_cache = {"value": "SIDEWAYS", "time": 0}


def _refresh_upbit_cache():
    global _upbit_cache
    if time.time() - _upbit_cache["time"] <= 60:
        return
    _upbit_cache["time"] = time.time()
    _upbit_cache["krw"] = None
    _upbit_cache["ok"] = False
    try:
        upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
        upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
        if upbit_key and upbit_secret:
            import pyupbit
            upbit = pyupbit.Upbit(upbit_key, upbit_secret)
            bal = upbit.get_balance("KRW")
            _upbit_cache["krw"] = float(bal) if bal is not None else None
            _upbit_cache["ok"] = True
    except Exception as e:
        print(f"[ERROR] {e}")


def _get_hourly_trend():
    """1시간봉 추세 (btc_trading_agent 로직 동일). 실패 시 SIDEWAYS."""
    global _trend_cache
    if time.time() - _trend_cache["time"] < 300:
        return _trend_cache["value"]
    try:
        import pyupbit
        df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=50)
        if df is None or df.empty:
            result = "SIDEWAYS"
            _trend_cache["value"] = result
            _trend_cache["time"] = time.time()
            return result
        from ta.trend import EMAIndicator
        from ta.momentum import RSIIndicator
        close = df["close"]
        ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
        price = close.iloc[-1]
        if ema20 > ema50 and price > ema20:
            result = "UPTREND"
            _trend_cache["value"] = result
            _trend_cache["time"] = time.time()
            return result
        if ema20 < ema50 and price < ema20:
            result = "DOWNTREND"
            _trend_cache["value"] = result
            _trend_cache["time"] = time.time()
            return result
        result = "SIDEWAYS"
        _trend_cache["value"] = result
        _trend_cache["time"] = time.time()
        return result
    except Exception as e:
        print(f"[ERROR] {e}")
        result = "SIDEWAYS"
        _trend_cache["value"] = result
        _trend_cache["time"] = time.time()
        return result

# sudo 등으로 실행 시 env가 비어있을 수 있음 → openclaw.json에서 로드
_OPENCLAW_JSON = Path(__file__).resolve().parents[2] / "openclaw.json"
if not os.environ.get("SUPABASE_URL") and _OPENCLAW_JSON.exists():
    try:
        with open(_OPENCLAW_JSON, encoding="utf-8") as f:
            data = json.load(f)
        env = data.get("env") or {}
        for k, v in env.items():
            if k != "shellEnv" and isinstance(v, str):
                os.environ.setdefault(k, v)
    except Exception:
        pass

# .openclaw/.env 또는 workspace/.env 로드 (CRYPTOPANIC_API_KEY, TELEGRAM_CHAT_ID 등)
def _load_dotenv():
    base = Path(__file__).resolve().parents[2]  # .openclaw
    for env_path in [base / ".env", base / "workspace" / ".env"]:
        if not env_path.exists():
            continue
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k = k.strip()
                        v = v.strip().strip("'\"").replace("\\n", "\n")
                        if k:
                            os.environ.setdefault(k, v)
        except Exception as e:
            print(f"[ERROR] .env load {env_path}: {e}")

_load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None

app = FastAPI()

WORKSPACE = "/home/wlsdud5035/.openclaw/workspace"
LOG_PATH = "/home/wlsdud5035/.openclaw/logs/btc_trading.log"
BRAIN_PATH = f"{WORKSPACE}/brain"
MEMORY_PATH = f"{WORKSPACE}/memory"

_kiwoom_client = None

def _get_kiwoom():
    """지연 초기화된 KiwoomClient 반환 (환경 미설정 시 None)."""
    global _kiwoom_client
    if _kiwoom_client is None:
        try:
            import sys
            if WORKSPACE not in sys.path:
                sys.path.insert(0, WORKSPACE)
            from stocks.kiwoom_client import KiwoomClient
            _kiwoom_client = KiwoomClient()
        except Exception as e:
            print(f"[WARN] Kiwoom init: {e}")
    return _kiwoom_client


def is_market_open_now() -> bool:
    """한국 주식장 (정규장) 개장 여부."""
    now = datetime.now()
    if now.weekday() >= 5:  # 토/일
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530

HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenClaw Trading</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0a0e17;
    --bg2:      #0f1422;
    --bg3:      #141928;
    --border:   #1e2537;
    --accent:   #00d4ff;
    --green:    #00e676;
    --red:      #ff3d57;
    --yellow:   #ffd600;
    --text:     #e8eaf0;
    --muted:    #4a5068;
    --font:     'Syne', sans-serif;
    --mono:     'DM Mono', monospace;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* 배경 그리드 */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .wrapper { position: relative; z-index: 1; }

  /* 헤더 */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
    background: rgba(10,14,23,0.9);
    backdrop-filter: blur(10px);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: -0.5px;
  }

  .logo-icon {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--accent), #7c3aed);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
  }

  .live-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--green);
    background: rgba(0,230,118,0.1);
    border: 1px solid rgba(0,230,118,0.2);
    padding: 4px 10px;
    border-radius: 20px;
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--green);
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.8); }
  }

  .header-time {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--muted);
  }

  /* 메인 레이아웃 */
  main {
    padding: 20px 28px;
    max-width: 1600px;
    margin: 0 auto;
  }

  /* BTC 히어로 섹션 */
  .hero {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 20px;
    align-items: center;
    padding: 24px 28px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
  }

  .hero::after {
    content: '₿';
    position: absolute;
    right: -20px;
    top: -20px;
    font-size: 180px;
    color: rgba(255,214,0,0.03);
    font-weight: 900;
    pointer-events: none;
  }

  .btc-price {
    font-size: 42px;
    font-weight: 800;
    letter-spacing: -2px;
    font-family: var(--mono);
    line-height: 1;
  }

  .btc-label {
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 8px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  .price-change {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--mono);
    font-size: 14px;
    padding: 4px 10px;
    border-radius: 6px;
    margin-top: 8px;
  }

  .price-change.up { background: rgba(0,230,118,0.1); color: var(--green); }
  .price-change.down { background: rgba(255,61,87,0.1); color: var(--red); }

  .hero-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }

  .signal-badge {
    font-size: 13px;
    font-weight: 700;
    padding: 8px 16px;
    border-radius: 8px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .signal-badge.buy { background: rgba(0,230,118,0.15); color: var(--green); border: 1px solid rgba(0,230,118,0.3); }
  .signal-badge.sell { background: rgba(255,61,87,0.15); color: var(--red); border: 1px solid rgba(255,61,87,0.3); }
  .signal-badge.hold { background: rgba(74,80,104,0.3); color: var(--muted); border: 1px solid var(--border); }

  /* 스탯 카드 그리드 */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    transition: border-color 0.2s;
  }

  .stat-card:hover { border-color: var(--accent); }

  .stat-label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 8px;
    font-weight: 600;
  }

  .stat-value {
    font-family: var(--mono);
    font-size: 22px;
    font-weight: 500;
    line-height: 1;
  }

  .stat-sub {
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
    font-family: var(--mono);
  }

  .positive { color: var(--green); }
  .negative { color: var(--red); }
  .neutral  { color: var(--accent); }

  /* 차트 + 테이블 레이아웃 */
  .content-grid {
    display: grid;
    grid-template-columns: 1fr 400px;
    gap: 16px;
    margin-bottom: 20px;
  }

  .card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
  }

  .card-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
  }

  .card-body { padding: 20px; }

  canvas { max-height: 240px; }

  /* 인디케이터 바 */
  .indicators {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .indicator-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
  }

  .indicator-name {
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 10px;
    font-weight: 600;
  }

  .indicator-value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 500;
    line-height: 1;
    margin-bottom: 8px;
  }

  .progress-bar {
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-top: 8px;
  }

  .progress-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.5s ease;
  }

  /* 거래 내역 테이블 */
  .trade-table {
    width: 100%;
    border-collapse: collapse;
  }

  .trade-table th {
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--muted);
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
  }

  .trade-table td {
    padding: 10px 12px;
    font-family: var(--mono);
    font-size: 12px;
    border-bottom: 1px solid rgba(30,37,55,0.5);
  }

  .trade-table tr:last-child td { border-bottom: none; }
  .trade-table tr:hover td { background: rgba(255,255,255,0.02); }

  .trade-table-empty td {
    text-align: center !important;
    padding: 32px 16px !important;
    font-size: 14px !important;
    color: var(--muted) !important;
    border-bottom: 1px solid var(--border);
    background: rgba(0,212,255,0.04);
  }

  .trade-filters {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    background: rgba(0,0,0,0.2);
  }
  .filter-btn {
    padding: 4px 10px;
    font-size: 11px;
    font-family: var(--mono);
    color: var(--muted);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    transition: color 0.2s, border-color 0.2s, background 0.2s;
  }
  .filter-btn:hover {
    color: var(--text);
    border-color: var(--accent);
  }
  .filter-btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(0,212,255,0.1);
  }

  .action-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
  }

  .action-pill.buy  { background: rgba(0,230,118,0.15); color: var(--green); }
  .action-pill.sell { background: rgba(255,61,87,0.15); color: var(--red); }
  .action-pill.hold { background: rgba(74,80,104,0.2); color: var(--muted); }

  /* 포지션 카드 */
  .position-section {
    margin-bottom: 20px;
  }

  .position-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 20px;
    align-items: center;
  }

  .position-card.active {
    border-color: rgba(0,212,255,0.3);
    background: linear-gradient(135deg, rgba(0,212,255,0.05), var(--bg2));
  }

  .position-empty {
    text-align: center;
    color: var(--muted);
    padding: 30px;
    font-size: 13px;
  }

  /* Fear & Greed 게이지 */
  .fg-section {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 24px;
    align-items: center;
  }

  .fg-gauge {
    position: relative;
    width: 120px;
    height: 60px;
  }

  .fg-value {
    font-family: var(--mono);
    font-size: 36px;
    font-weight: 500;
    text-align: center;
    line-height: 1;
  }

  .fg-label {
    font-size: 11px;
    text-align: center;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  /* 스크롤바 */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* 반응형 */
  @media (max-width: 1200px) {
    .stats-grid { grid-template-columns: repeat(3, 1fr); }
    .content-grid { grid-template-columns: 1fr; }
    .indicators { grid-template-columns: repeat(3, 1fr); }
  }

  @media (max-width: 768px) {
    main { padding: 12px; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .btc-price { font-size: 28px; }
    .indicators { grid-template-columns: 1fr; }
    .position-card { grid-template-columns: repeat(2, 1fr); }
  }

  /* 로딩 */
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--muted);
    font-size: 13px;
    gap: 8px;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .refresh-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    cursor: pointer;
    font-family: var(--mono);
    transition: all 0.2s;
  }

  .refresh-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  header a.nav-tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    color: var(--muted);
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
    font-family: var(--mono);
    text-decoration: none;
  }
  header a.nav-tab:hover {
    color: var(--text);
    border-color: var(--border);
  }
  header a.nav-tab.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(0,212,255,0.08);
  }

  .interval-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    font-family: var(--mono);
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .interval-btn:hover { color: var(--text); border-color: var(--accent); }
  .interval-btn.active { color: var(--accent); border-color: var(--accent); background: rgba(0,212,255,0.08); }

  .trend-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    font-family: var(--mono);
    font-weight: 500;
  }

  .trend-chip.up   { background: rgba(0,230,118,0.1); color: var(--green); }
  .trend-chip.down { background: rgba(255,61,87,0.1); color: var(--red); }
  .trend-chip.side { background: rgba(255,214,0,0.1); color: var(--yellow); }
  .log-line.log-buy   { color: var(--green); }
  .log-line.log-sell  { color: var(--red); }
  .log-line.log-error { color: var(--red); }
  .log-line.log-cycle { color: var(--accent); }
  .log-line.log-hold  { color: var(--muted); }
</style>
</head>
<body>
<div class="wrapper">

  <header>
    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
      <div class="logo">
        <div class="logo-icon">🤖</div>
        OpenClaw Trading
      </div>
      <nav style="display:flex;align-items:center;gap:4px;margin-left:24px;">
        <a href="/" style="text-decoration:none" class="nav-tab active">₿ BTC</a>
        <a href="/stocks" style="text-decoration:none" class="nav-tab">📈 주식</a>
      </nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="live-badge">
        <div class="live-dot"></div>
        LIVE
      </div>
      <div class="header-time" id="clock">--:--:--</div>
      <a href="/stocks" class="refresh-btn" style="text-decoration:none">📈 주식</a>
      <button class="refresh-btn" onclick="loadAll()">↻ 새로고침</button>
    </div>
  </header>

  <main>

    <!-- BTC 히어로 -->
    <div class="hero" id="hero">
      <div>
        <div class="btc-label">BTC / KRW</div>
        <div class="btc-price" id="hero-price">--</div>
        <div id="hero-change"></div>
        <div id="connection-notice" style="font-size:11px;color:var(--muted);margin-top:6px"></div>
      </div>
      <div class="hero-right">
        <div class="signal-badge hold" id="hero-signal">HOLD</div>
        <div id="hero-trend"></div>
        <div style="font-family:var(--mono);font-size:11px;color:var(--muted)" id="hero-time"></div>
      </div>
    </div>

    <!-- 스탯 카드 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">누적 손익</div>
        <div class="stat-value" id="stat-pnl">+0원</div>
        <div class="stat-sub" id="stat-pnl-pct">0.00%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">승률</div>
        <div class="stat-value neutral" id="stat-winrate">0.0%</div>
        <div class="stat-sub" id="stat-wl">0승 0패</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">총 거래</div>
        <div class="stat-value" id="stat-total">0회</div>
        <div class="stat-sub" id="stat-buysell">매수 0 / 매도 0</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">평균 신뢰도</div>
        <div class="stat-value neutral" id="stat-confidence">0%</div>
        <div class="stat-sub">AI 판단 정확도</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">KRW 잔고</div>
        <div class="stat-value" id="stat-krw">--</div>
        <div class="stat-sub">사용 가능</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">오늘 거래</div>
        <div class="stat-value" id="stat-today">0회</div>
        <div class="stat-sub" id="stat-today-pnl">손익 0원</div>
      </div>
    </div>

    <!-- 인디케이터 -->
    <div class="indicators">
      <div class="indicator-card">
        <div class="indicator-name">RSI (14)</div>
        <div class="indicator-value" id="ind-rsi">--</div>
        <div class="progress-bar">
          <div class="progress-fill" id="ind-rsi-bar" style="width:50%;background:var(--accent)"></div>
        </div>
        <div class="stat-sub" id="ind-rsi-label" style="margin-top:6px"></div>
      </div>
      <div class="indicator-card">
        <div class="indicator-name">MACD</div>
        <div class="indicator-value" id="ind-macd">--</div>
        <div class="stat-sub" id="ind-macd-label" style="margin-top:6px"></div>
      </div>
      <div class="indicator-card">
        <div class="indicator-name">Fear & Greed</div>
        <div class="indicator-value" id="ind-fg">--</div>
        <div class="progress-bar">
          <div class="progress-fill" id="ind-fg-bar" style="width:50%;background:var(--accent)"></div>
        </div>
        <div class="stat-sub" id="ind-fg-label" style="margin-top:6px"></div>
      </div>
    </div>

    <!-- 차트 + 포지션 -->
    <div class="content-grid">
      <div class="card">
        <div class="card-header">
          <span class="card-title">BTC/KRW 차트</span>
          <div style="display:flex;gap:8px;">
            <button class="refresh-btn" onclick="setCandleInterval('minute1')" id="btn-1m">1분</button>
            <button class="refresh-btn" onclick="setCandleInterval('minute5')" id="btn-5m">5분</button>
            <button class="refresh-btn" onclick="setCandleInterval('minute15')" id="btn-15m">15분</button>
            <button class="refresh-btn" onclick="setCandleInterval('minute60')" id="btn-1h">1시간</button>
          </div>
        </div>
        <div id="candle-chart" style="width:100%;height:300px"></div>
        <div id="volume-chart" style="width:100%;height:80px"></div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">현재 포지션</span>
          <span class="stat-sub" id="pos-status"></span>
        </div>
        <div class="card-body" id="position-body">
          <div class="position-empty">포지션 없음<br><span style="font-size:11px">다음 BUY 신호 대기 중</span></div>
        </div>
      </div>
    </div>

    <!-- 최근 거래 내역 (항상 표시) -->
    <div class="card" id="section-trades" style="margin-bottom:20px;min-height:140px">
      <div class="card-header">
        <span class="card-title">최근 거래 내역</span>
        <span class="stat-sub" id="trade-count">최근 0건</span>
      </div>
      <div class="trade-filters">
        <span style="color:var(--muted);font-size:11px;margin-right:8px">표시 건수:</span>
        <button type="button" class="filter-btn active" data-limit="10" onclick="setTradeLimit(10)">10</button>
        <button type="button" class="filter-btn" data-limit="30" onclick="setTradeLimit(30)">30</button>
        <button type="button" class="filter-btn" data-limit="50" onclick="setTradeLimit(50)">50</button>
        <button type="button" class="filter-btn" data-limit="100" onclick="setTradeLimit(100)">100</button>
        <span style="color:var(--muted);font-size:11px;margin:0 8px 0 16px">신호:</span>
        <button type="button" class="filter-btn active" data-signal="" onclick="setTradeSignal('')">전체</button>
        <button type="button" class="filter-btn" data-signal="BUY" onclick="setTradeSignal('BUY')">BUY</button>
        <button type="button" class="filter-btn" data-signal="SELL" onclick="setTradeSignal('SELL')">SELL</button>
        <button type="button" class="filter-btn" data-signal="HOLD" onclick="setTradeSignal('HOLD')">HOLD</button>
      </div>
      <div style="overflow-x:auto;min-height:60px">
        <table class="trade-table">
          <thead>
            <tr>
              <th>시간</th>
              <th>신호</th>
              <th>가격</th>
              <th>RSI</th>
              <th>MACD</th>
              <th>신뢰도</th>
              <th>근거</th>
              <th>손익</th>
            </tr>
          </thead>
          <tbody id="trade-tbody">
            <tr class="trade-table-empty"><td colspan="8">거래 내역 없음</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 뉴스 카드 섹션 -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        <span class="card-title">📰 BTC 실시간 뉴스</span>
        <span class="stat-sub" id="news-time"></span>
      </div>
      <div style="padding:16px;display:grid;grid-template-columns:repeat(2,1fr);gap:12px" id="news-grid">
        <div class="loading"><div class="spinner"></div> 뉴스 로딩 중...</div>
      </div>
    </div>

    <!-- 실시간 로그 + 시스템/Brain -->
    <div style="display:grid;grid-template-columns:1fr 400px;gap:16px;margin-top:20px">
      <div class="card">
        <div class="card-header"><span class="card-title">실시간 로그 (btc_trading)</span></div>
        <div class="card-body" style="height:400px;overflow:auto">
          <pre id="log-viewer" style="margin:0;font-size:13px;line-height:1.8;color:var(--text);white-space:pre-wrap;word-break:break-all"></pre>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">시스템 / Brain</span></div>
        <div class="card-body">
          <div id="system-box" style="font-size:12px;margin-bottom:12px"></div>
          <div id="brain-box" style="font-size:11px;color:var(--muted);white-space:pre-wrap"></div>
        </div>
      </div>
    </div>

  </main>
</div>

<script>
let allTrades = [];
let tradeLimit = 10;
let tradeSignalFilter = '';

// lightweight-charts 로드
const lwScript = document.createElement('script');
lwScript.src = 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
document.head.appendChild(lwScript);

let candleChart = null;
let candleSeries = null;
let volumeSeries = null;
let currentInterval = 'minute5';

lwScript.onload = function() {
  const container = document.getElementById('candle-chart');
  candleChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: 300,
    layout: {
      background: { color: '#0f1422' },
      textColor: '#4a5068',
    },
    grid: {
      vertLines: { color: '#1e2537' },
      horzLines: { color: '#1e2537' },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: {
      borderColor: '#1e2537',
      formatter: (price) => (price/1000000).toFixed(2) + "M",
    },
    timeScale: {
      borderColor: '#1e2537',
      timeVisible: true,
      secondsVisible: false,
    },
  });

  candleSeries = candleChart.addCandlestickSeries({
    upColor:   '#00e676',
    downColor: '#ff3d57',
    borderUpColor:   '#00e676',
    borderDownColor: '#ff3d57',
    wickUpColor:   '#00e676',
    wickDownColor: '#ff3d57',
  });

  const volContainer = document.getElementById('volume-chart');
  const volChart = LightweightCharts.createChart(volContainer, {
    width: volContainer.clientWidth,
    height: 80,
    layout: { background: { color: '#0f1422' }, textColor: '#4a5068' },
    grid: {
      vertLines: { color: '#1e2537' },
      horzLines: { color: '#1e2537' },
    },
    timeScale: { borderColor: '#1e2537', timeVisible: true },
    rightPriceScale: { borderColor: '#1e2537' },
  });

  volumeSeries = volChart.addHistogramSeries({
    color: "rgba(0,212,255,0.3)",
    priceFormat: { type: "volume" },
    priceScaleId: "",
  });

  setCandleInterval('minute5');
  setInterval(loadCandles, 10000);
};

async function loadCandles() {
  try {
    const res = await fetch('/api/candles?interval=' + currentInterval);
    const data = await res.json();
    if (!data.length) return;
    if (!candleSeries || !volumeSeries) return;

    candleSeries.setData(data.map(d => ({
      time:  d.time,
      open:  d.open,
      high:  d.high,
      low:   d.low,
      close: d.close,
    })));

    const volUp = "rgba(0,230,118,0.4)", volDn = "rgba(255,61,87,0.4)";
    volumeSeries.setData(data.map(d => ({
      time:  d.time,
      value: d.volume,
      color: d.close >= d.open ? volUp : volDn,
    })));

    if (allTrades && allTrades.length) {
      const markers = allTrades
        .filter(t => t.action === 'BUY' || t.action === 'SELL')
        .map(t => ({
          time:     Math.floor(new Date(t.timestamp).getTime() / 1000),
          position: t.action === 'BUY' ? 'belowBar' : 'aboveBar',
          color:    t.action === 'BUY' ? '#00e676' : '#ff3d57',
          shape:    t.action === 'BUY' ? 'arrowUp' : 'arrowDown',
          text:     t.action,
        }));
      candleSeries.setMarkers(markers);
    }
  } catch(e) {
    console.error('candles error', e);
  }
}

async function setCandleInterval(interval) {
  currentInterval = interval;
  ['1m','5m','15m','1h'].forEach(m => {
    const btn = document.getElementById('btn-' + m);
    if (btn) btn.style.color = '';
  });
  const map = {'minute1':'1m','minute5':'5m','minute15':'15m','minute60':'1h'};
  const btn = document.getElementById('btn-' + map[interval]);
  if (btn) btn.style.color = 'var(--accent)';
  await loadCandles();
}

function setTradeLimit(n) {
  tradeLimit = n;
  document.querySelectorAll('.trade-filters .filter-btn[data-limit]').forEach(function(btn) {
    btn.classList.toggle('active', parseInt(btn.getAttribute('data-limit'), 10) === n);
  });
  renderTradesTable();
}

function setTradeSignal(s) {
  tradeSignalFilter = s;
  document.querySelectorAll('.trade-filters .filter-btn[data-signal]').forEach(function(btn) {
    btn.classList.toggle('active', btn.getAttribute('data-signal') === s);
  });
  renderTradesTable();
}

function renderTradesTable() {
  const tbody = document.getElementById('trade-tbody');
  const countEl = document.getElementById('trade-count');
  if (!tbody || !countEl) return;
  let list = allTrades;
  if (tradeSignalFilter) list = list.filter(function(t) { return (t.action || 'HOLD') === tradeSignalFilter; });
  const showing = list.length;
  countEl.textContent = (tradeSignalFilter ? tradeSignalFilter + ' ' : '') + '최근 ' + Math.min(showing, tradeLimit) + '건' + (showing > tradeLimit ? ' (전체 ' + showing + '건)' : '');
  if (!list.length) {
    tbody.innerHTML = '<tr class="trade-table-empty"><td colspan="8">거래 내역 없음</td></tr>';
    return;
  }
  const slice = list.slice(0, tradeLimit);
  tbody.innerHTML = slice.map(function(t) {
    const action = t.action || 'HOLD';
    const pnl = t.pnl;
    const pnlStr = pnl != null ? '<span class="' + (pnl >= 0 ? 'positive' : 'negative') + '">' + (pnl >= 0 ? '+' : '') + fmt(Math.round(pnl)) + '원</span>' : '<span style="color:var(--muted)">—</span>';
    const time = t.timestamp ? t.timestamp.substring(0,16).replace('T',' ') : '--';
    return '<tr><td style="color:var(--muted)">' + time + '</td><td><span class="action-pill ' + action.toLowerCase() + '">' + action + '</span></td><td>' + fmt(t.price) + '원</td><td class="' + (t.rsi >= 70 ? 'negative' : t.rsi <= 30 ? 'positive' : '') + '">' + (t.rsi ? t.rsi.toFixed(1) : '--') + '</td><td class="' + (t.macd > 0 ? 'positive' : 'negative') + '">' + (t.macd ? fmt(Math.round(t.macd)) : '--') + '</td><td class="neutral">' + (t.confidence ? t.confidence + '%' : '--') + '</td><td style="color:var(--muted);font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (t.reason || '—') + '</td><td>' + pnlStr + '</td></tr>';
  }).join('');
}

(function(){
  var h = document.getElementById('hero-price');
  if (h) h.textContent = '--';
})();

// 시계
setInterval(function(){
  var c = document.getElementById('clock');
  if (c) c.textContent = new Date().toLocaleTimeString('ko-KR');
}, 1000);

// 숫자 포맷
const fmt = n => n ? Number(n).toLocaleString('ko-KR') : '--';
const fmtPct = n => n ? (n > 0 ? '+' : '') + Number(n).toFixed(2) + '%' : '0.00%';

async function loadAll() {
  await Promise.allSettled([loadStats(), loadTrades(), loadFG(), loadLogs(), loadSystem(), loadBrain()]);
}

async function loadLogs() {
  try {
    const res = await fetch('/api/logs');
    const d = await res.json();
    const el = document.getElementById('log-viewer');
    const escape = (s) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    const cls = (line) => {
      if (/매수|BUY/.test(line)) return "log-line log-buy";
      if (/매도|SELL|손절/.test(line)) return "log-line log-sell";
      if (/ERROR|실패/.test(line)) return "log-line log-error";
      if (/매매 사이클 시작/.test(line)) return "log-line log-cycle";
      if (/HOLD/.test(line)) return "log-line log-hold";
      return "log-line";
    };
    const nl = String.fromCharCode(10);
    const colored = (d.lines || []).map(line => {
      const c = cls(line), t = escape(line);
      return "<span class=" + JSON.stringify(c) + ">" + t + "</span>";
    }).join(nl);
    el.innerHTML = colored || "(비어 있음)";
    el.scrollTop = el.scrollHeight;
  } catch(e) { document.getElementById('log-viewer').textContent = '로딩 실패'; }
}
async function loadSystem() {
  try {
    const res = await fetch('/api/system');
    const d = await res.json();
    if (d.error) { document.getElementById('system-box').innerHTML = d.error; return; }
    const up = d.upbit_ok ? '<span class="positive">Upbit 연결됨</span>' : '<span class="negative">Upbit 끊김</span>';
    document.getElementById('system-box').innerHTML = 'CPU ' + d.cpu + '% | MEM ' + d.mem_used + '/' + d.mem_total + 'GB (' + d.mem_pct + '%) | 디스크 ' + d.disk_used + '/' + d.disk_total + 'GB (' + d.disk_pct + '%)<br>마지막 Cron: ' + d.last_cron + '<br>' + up;
  } catch(e) { document.getElementById('system-box').textContent = '로딩 실패'; }
}
async function loadBrain() {
  try {
    const res = await fetch('/api/brain');
    const d = await res.json();
    if (d.error) { document.getElementById('brain-box').textContent = d.error; return; }
    const br = (t) => (t || '').replace(/\\n/g, '<br>');
    document.getElementById('brain-box').innerHTML = '<strong>요약</strong><br>' + br(d.summary) + '<br><br><strong>할일</strong><br>' + br(d.todos) + '<br><br><strong>기억</strong><br>' + br(d.memory);
  } catch(e) { document.getElementById('brain-box').textContent = '로딩 실패'; }
}

async function loadNews() {
  var timeEl = document.getElementById('news-time');
  var grid = document.getElementById('news-grid');
  if (!timeEl || !grid) return;
  var done = function(html) {
    if (grid) grid.innerHTML = html;
    if (timeEl) timeEl.textContent = '업데이트: ' + new Date().toLocaleTimeString('ko-KR');
  };
  try {
    var ctrl = new AbortController();
    var t = setTimeout(function() { ctrl.abort(); }, 6000);
    var res = await fetch('/api/news', { signal: ctrl.signal });
    clearTimeout(t);
    var news = [];
    try { news = await res.json(); } catch(_) {}
    if (!Array.isArray(news)) news = [];
    var rateLimited = res.headers && res.headers.get('X-News-Rate-Limited') === 'true';
    if (!news.length) {
      var msg = rateLimited ? '요청 한도 초과 (5분마다 자동 재시도)' : '뉴스 없음';
      done('<div style="color:var(--muted);padding:20px">' + msg + '</div>');
      return;
    }
    var html = news.slice(0, 8).map(function(n) {
      if (!n) return '';
      var url = (n.url || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
      var title = (n.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      var source = (n.source || '').replace(/</g, '&lt;');
      var time = (n.time || '').replace(/</g, '&lt;');
      return '<a href="' + url + '" target="_blank" style="text-decoration:none;">' +
        '<div style="background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:border-color 0.2s;height:100%"' +
        ' onmouseover="this.style.borderColor=&quot;var(--accent)&quot;"' +
        ' onmouseout="this.style.borderColor=&quot;var(--border)&quot;">' +
        '<div style="font-size:11px;color:var(--accent);font-family:var(--mono);margin-bottom:6px">' + source + ' · ' + time + '</div>' +
        '<div style="font-size:13px;color:var(--text);line-height:1.5;font-weight:500">' + title + '</div>' +
        '</div></a>';
    }).join('');
    done(html);
  } catch(e) {
    done('<div style="color:var(--muted);padding:20px">뉴스 없음</div>');
  }
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error(res.status);
    const d = await res.json();
    if (d.error) throw new Error(d.error);

    // 히어로
    const price = d.last_price || 0;
    document.getElementById('hero-price').textContent = price ? fmt(price) + '원' : '--';

    const sig = d.last_signal || 'HOLD';
    const sigEl = document.getElementById('hero-signal');
    sigEl.textContent = sig;
    sigEl.className = 'signal-badge ' + sig.toLowerCase();

    document.getElementById('hero-time').textContent = d.last_time ? d.last_time.substring(0,16).replace('T',' ') : '';

    // 추세
    const trend = d.trend || 'SIDEWAYS';
    const trendEl = document.getElementById('hero-trend');
    const trendMap = { UPTREND: ['up','↑ UPTREND'], DOWNTREND: ['down','↓ DOWNTREND'], SIDEWAYS: ['side','→ SIDEWAYS'] };
    const tc = (trendMap[trend] || ['side','→ SIDEWAYS'])[0];
    const tl = (trendMap[trend] || ['side','→ SIDEWAYS'])[1];
    trendEl.innerHTML = '<span class="trend-chip ' + tc + '">' + tl + '</span>';

    // 스탯
    const pnl = d.total_pnl || 0;
    const pnlEl = document.getElementById('stat-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(Math.round(pnl)) + '원';
    pnlEl.className = 'stat-value ' + (pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : '');

    document.getElementById('stat-pnl-pct').textContent = fmtPct(d.total_pnl_pct);
    document.getElementById('stat-winrate').textContent = (d.winrate || 0).toFixed(1) + '%';
    document.getElementById('stat-wl').textContent = (d.wins || 0) + '승 ' + (d.losses || 0) + '패';
    document.getElementById('stat-total').textContent = (d.total_trades || 0) + '회';
    document.getElementById('stat-buysell').textContent = '매수 ' + (d.buys||0) + ' / 매도 ' + (d.sells||0);
    document.getElementById('stat-confidence').textContent = (d.avg_confidence || 0).toFixed(1) + '%';
    const krwEl = document.getElementById('stat-krw');
    if (krwEl) krwEl.textContent = (d.krw_balance != null && d.krw_balance !== '') ? (fmt(Math.round(d.krw_balance)) + '원') : '--';
    document.getElementById('stat-today').textContent = (d.today_trades || 0) + '회';

    const tp = d.today_pnl || 0;
    const tpEl = document.getElementById('stat-today-pnl');
    tpEl.textContent = '손익 ' + (tp >= 0 ? '+' : '') + fmt(Math.round(tp)) + '원';
    tpEl.className = 'stat-sub ' + (tp > 0 ? 'positive' : tp < 0 ? 'negative' : '');

    // 인디케이터
    const rsi = d.last_rsi || 50;
    const rsiEl = document.getElementById('ind-rsi');
    rsiEl.textContent = rsi.toFixed(1);
    rsiEl.className = 'indicator-value ' + (rsi >= 70 ? 'negative' : rsi <= 30 ? 'positive' : '');
    document.getElementById('ind-rsi-bar').style.width = rsi + '%';
    document.getElementById('ind-rsi-bar').style.background = rsi >= 70 ? 'var(--red)' : rsi <= 30 ? 'var(--green)' : 'var(--accent)';
    document.getElementById('ind-rsi-label').textContent = rsi >= 70 ? '과매수' : rsi <= 30 ? '과매도' : '중립';

    const macd = d.last_macd || 0;
    const macdEl = document.getElementById('ind-macd');
    macdEl.textContent = fmt(Math.round(macd));
    macdEl.className = 'indicator-value ' + (macd > 0 ? 'positive' : 'negative');
    document.getElementById('ind-macd-label').textContent = macd > 0 ? '상승 전환 ↑' : '하락 중 ↓';

    // 포지션
    if (d.position) {
      const pos = d.position;
      const change = ((d.last_price - pos.entry_price) / pos.entry_price * 100).toFixed(2);
      const isPos = change >= 0;
      const posHtml = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">' +
        '<div><div class="stat-label">진입가</div><div style="font-family:var(--mono);font-size:18px;margin-top:4px">' + fmt(pos.entry_price) + '원</div></div>' +
        '<div><div class="stat-label">현재가</div><div style="font-family:var(--mono);font-size:18px;margin-top:4px;color:var(--accent)">' + fmt(d.last_price) + '원</div></div>' +
        '<div><div class="stat-label">수익률</div><div style="font-family:var(--mono);font-size:24px;margin-top:4px" class="' + (isPos ? 'positive' : 'negative') + '">' + (isPos ? '+' : '') + change + '%</div></div>' +
        '<div><div class="stat-label">투입금액</div><div style="font-family:var(--mono);font-size:18px;margin-top:4px">' + fmt(pos.entry_krw) + '원</div></div>' +
        '<div><div class="stat-label">손절가</div><div style="font-family:var(--mono);font-size:14px;margin-top:4px;color:var(--red)">' + fmt(Math.round(pos.entry_price*0.98)) + '원</div></div>' +
        '<div><div class="stat-label">익절가</div><div style="font-family:var(--mono);font-size:14px;margin-top:4px;color:var(--green)">' + fmt(Math.round(pos.entry_price*1.04)) + '원</div></div>' +
        '</div>';
      document.getElementById('position-body').innerHTML = posHtml;
      document.getElementById('pos-status').innerHTML = '<span class="action-pill buy">OPEN</span>';
    } else {
      document.getElementById('position-body').innerHTML = '<div class="position-empty">포지션 없음<br><span style="font-size:11px">다음 BUY 신호 대기 중</span></div>';
      document.getElementById('pos-status').innerHTML = '<span class="action-pill hold">대기</span>';
    }

  } catch(e) {
    console.error('stats error', e);
    try { var h = document.getElementById('hero-price'); if (h) h.textContent = '--'; } catch(_) {}
  }
}

async function loadFG() {
  try {
    const res = await fetch('https://api.alternative.me/fng/?limit=1');
    const d = await res.json();
    if (!d.data || !d.data[0]) return;
    const val = parseInt(d.data[0].value);
    const label = d.data[0].value_classification;

    const fgEl = document.getElementById('ind-fg');
    fgEl.textContent = val;
    fgEl.className = 'indicator-value ' + (val <= 25 ? 'negative' : val >= 75 ? 'positive' : 'neutral');

    const bar = document.getElementById('ind-fg-bar');
    bar.style.width = val + '%';
    bar.style.background = val <= 25 ? 'var(--red)' : val >= 75 ? 'var(--green)' : 'var(--yellow)';
    document.getElementById('ind-fg-label').textContent = label;
  } catch(e) { console.error('FG error', e); }
}

async function loadTrades() {
  const tbody = document.getElementById('trade-tbody');
  const countEl = document.getElementById('trade-count');
  if (!tbody || !countEl) return;
  try {
    const res = await fetch('/api/trades');
    if (!res.ok) throw new Error(res.status);
    const raw = await res.json();
    allTrades = Array.isArray(raw) ? raw : [];
    renderTradesTable();
  } catch(e) {
    console.error('trades error', e);
    if (tbody) tbody.innerHTML = '<tr class="trade-table-empty"><td colspan="8">거래 로드 실패</td></tr>';
  }
}

// 초기 로드 + 30초 자동 갱신
loadAll();
setTimeout(loadNews, 1500);
setInterval(loadAll, 30000);
setInterval(loadNews, 30000);

// 5초 후에도 상단 가격이 '--'면 연결 안내 (거래 테이블은 항상 표시)
setTimeout(function(){
  var hero = document.querySelector('.hero-price');
  if (hero && hero.textContent.trim() === '--') {
    var notice = document.getElementById('connection-notice');
    if (notice) notice.textContent = '연결 실패. 서버 주소(예: http://서버:8080)로 열었는지 확인 후 새로고침(Ctrl+Shift+R) 해 주세요.';
  }
}, 5000);
</script>
</body>
</html>"""

STOCKS_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenClaw Stocks</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0e17;--bg2:#0f1422;--bg3:#141928;
    --border:#1e2537;--accent:#00d4ff;
    --green:#00e676;--red:#ff3d57;--yellow:#ffd600;
    --text:#e8eaf0;--muted:#4a5068;
    --font:'Syne',sans-serif;--mono:'DM Mono',monospace;
  }
  * { margin:0;padding:0;box-sizing:border-box; }
  body { background:var(--bg);color:var(--text);font-family:var(--font);min-height:100vh; }
  body::before {
    content:'';position:fixed;inset:0;
    background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);
    background-size:40px 40px;pointer-events:none;z-index:0;
  }
  .wrapper{position:relative;z-index:1;}
  header{display:flex;align-items:center;justify-content:space-between;padding:16px 28px;border-bottom:1px solid var(--border);background:rgba(10,14,23,0.9);backdrop-filter:blur(10px);position:sticky;top:0;z-index:100;}
  .logo{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:800;}
  .logo-icon{width:32px;height:32px;background:linear-gradient(135deg,var(--accent),#7c3aed);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;}
  .nav-tab{display:flex;align-items:center;gap:6px;padding:6px 16px;border-radius:8px;font-size:13px;font-weight:700;color:var(--muted);border:1px solid transparent;cursor:pointer;transition:all 0.2s;font-family:var(--mono);}
  .nav-tab:hover{color:var(--text);border-color:var(--border);}
  .nav-tab.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.08);}
  main{padding:20px 28px;max-width:1600px;margin:0 auto;}
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px;}
  .card-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);}
  .card-title{font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);}
  .card-body{padding:20px;}
  .stock-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
  .stock-card{position:relative;background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:border-color 0.2s;}
  .stock-card:hover{border-color:var(--accent);}
  .stock-card.selected{border-color:var(--accent);background:rgba(0,212,255,0.05);}
  .stock-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;font-weight:600;}
  .stock-name{font-size:15px;font-weight:700;margin-bottom:6px;}
  .stock-price{font-family:var(--mono);font-size:18px;font-weight:500;}
  .stock-change{font-family:var(--mono);font-size:12px;margin-top:4px;}
  .positive{color:var(--green);}
  .negative{color:var(--red);}
  .neutral{color:var(--accent);}
  .industry-badge{display:inline-block;font-size:10px;font-family:var(--mono);padding:2px 6px;border-radius:3px;background:rgba(0,212,255,0.1);color:var(--accent);margin-bottom:6px;}
  .indicator-badges{display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;}
  .badge{font-size:10px;padding:2px 6px;border-radius:3px;font-weight:bold;}
  .badge.rsi{background:#1a1a2e;color:#00d4ff;border:1px solid #00d4ff33;}
  .badge.macd{background:#1a1a2e;color:#ff6b6b;border:1px solid #ff6b6b33;}
  .badge.bb{background:#1a1a2e;color:#ffd93d;border:1px solid #ffd93d33;}
  .badge.vol{background:#1a1a2e;color:#6bcb77;border:1px solid #6bcb7733;}
  .badge.rsi.oversold{color:#ff4444;border-color:#ff444433;}
  .badge.rsi.low{color:#ffa500;border-color:#ffa50033;}
  .badge.rsi.overbought{color:#ff0000;border-color:#ff000033;}
  .stock-card.holding{border:1px solid #ff444466;box-shadow:0 0 8px rgba(255,68,68,0.15);}
  .stock-card.holding::before{content:'🏦 보유';position:absolute;top:4px;right:6px;font-size:9px;color:#ff8800;background:#ff880020;padding:1px 5px;border-radius:3px;}
  .chart-section{display:grid;grid-template-columns:1fr 320px;gap:16px;margin-bottom:20px;}
  .trade-table{width:100%;border-collapse:collapse;}
  .trade-table th{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);padding:10px 12px;text-align:left;border-bottom:1px solid var(--border);font-weight:600;}
  .trade-table td{padding:10px 12px;font-family:var(--mono);font-size:12px;border-bottom:1px solid rgba(30,37,55,0.5);}
  .trade-table tr:hover td{background:rgba(255,255,255,0.02);}
  .stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;font-weight:600;}
  .stat-value{font-family:var(--mono);font-size:22px;font-weight:500;}
  .stat-sub{font-size:11px;color:var(--muted);margin-top:4px;font-family:var(--mono);}
  ::-webkit-scrollbar{width:4px;}
  ::-webkit-scrollbar-track{background:var(--bg);}
  ::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
  @media(max-width:1200px){.stock-grid{grid-template-columns:repeat(2,1fr);}.chart-section{grid-template-columns:1fr;}}
  @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
  .interval-btn{background:transparent;border:1px solid var(--border);color:var(--muted);font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:4px;cursor:pointer;transition:all 0.2s;}
  .interval-btn:hover{color:var(--text);border-color:var(--accent);}
  .interval-btn.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.08);}
  .portfolio-bar{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px;}
  .port-card{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:16px;text-align:center;}
  .port-label{font-size:12px;color:var(--muted);margin-bottom:4px;}
  .port-value{font-size:18px;font-weight:bold;color:#fff;}
  .port-value.kr-up{color:#ff4444;}
  .port-value.kr-dn{color:#4488ff;}
  .holdings-section{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px;}
  .holdings-section h3{color:var(--text);margin:0 0 12px 0;font-size:14px;}
  .holdings-table{width:100%;border-collapse:collapse;font-size:13px;}
  .holdings-table th{text-align:right;padding:8px 12px;color:var(--muted);border-bottom:1px solid rgba(255,255,255,0.1);font-weight:600;}
  .holdings-table th:first-child{text-align:left;}
  .holdings-table td{text-align:right;padding:8px 12px;color:var(--text);}
  .holdings-table td:first-child{text-align:left;font-weight:bold;}
  .holdings-table tr:hover{background:rgba(255,255,255,0.03);}
  .pnl-pos{color:#ff4444;font-weight:bold;}
  .pnl-neg{color:#4488ff;font-weight:bold;}
  .daily-pnl-section{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px;}
  .daily-pnl-section h3{color:var(--text);margin:0 0 12px 0;font-size:14px;}
  .strategy-bar{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--muted);}
  .strategy-bar span{margin-right:12px;}
  .scanner-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;}
  .scanner-header h3{color:var(--text);font-size:14px;margin:0;}
  .scanner-filters{display:flex;gap:6px;flex-wrap:wrap;}
  .filter-btn{background:transparent;border:1px solid var(--border);color:var(--muted);font-size:12px;padding:6px 12px;border-radius:6px;cursor:pointer;transition:all 0.2s;}
  .filter-btn:hover{color:var(--accent);border-color:var(--accent);}
  .filter-btn.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.08);}
</style>
</head>
<body>
<div class="wrapper">
  <header>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="logo">
        <div class="logo-icon">🤖</div>
        OpenClaw Trading
      </div>
      <nav style="display:flex;gap:4px;margin-left:32px">
        <a href="/" style="text-decoration:none"><div class="nav-tab">₿ BTC</div></a>
        <a href="/stocks" style="text-decoration:none"><div class="nav-tab active">📈 주식</div></a>
      </nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="display:flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--green);background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.2);padding:4px 10px;border-radius:20px;">
        <div style="width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite"></div>
        LIVE
      </div>
      <div style="font-family:var(--mono);font-size:12px;color:var(--muted)" id="clock"></div>
    </div>
  </header>

  <main>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
      <h2 style="font-size:18px;margin:0;">📊 주식 모의투자 대시보드</h2>
      <div style="display:flex;align-items:center;gap:10px;">
        <span id="market-status" style="font-size:12px;color:var(--muted);"></span>
        <span style="font-family:var(--mono);font-size:12px;color:var(--muted)" id="update-time">마지막 업데이트: --</span>
      </div>
    </div>

    <div id="portfolio-summary" class="portfolio-bar">
      <div class="port-card"><div class="port-label">💰 총 자산</div><div class="port-value" id="total-asset">--</div></div>
      <div class="port-card"><div class="port-label">📈 총 평가</div><div class="port-value" id="total-eval">--</div></div>
      <div class="port-card"><div class="port-label">💵 예수금</div><div class="port-value" id="deposit">--</div></div>
      <div class="port-card"><div class="port-label">📊 누적 수익률</div><div class="port-value" id="cum-pnl">--</div></div>
      <div class="port-card"><div class="port-label">📅 오늘 수익</div><div class="port-value" id="today-pnl">--</div></div>
    </div>

    <div class="holdings-section">
      <h3>🏦 보유종목 (<span id="pos-count">0</span>/5)</h3>
      <table class="holdings-table">
        <thead><tr><th>종목</th><th>수량</th><th>평균단가</th><th>현재가</th><th>평가액</th><th>수익률</th><th>차수</th></tr></thead>
        <tbody id="holdings-body"></tbody>
      </table>
    </div>

    <div style="display:grid;grid-template-columns:320px 1fr;gap:16px;margin-bottom:16px;">
      <div class="daily-pnl-section">
        <h3>📈 일별 수익 추이 (7일)</h3>
        <canvas id="daily-pnl-chart" height="150" style="width:100%;max-width:100%;"></canvas>
      </div>
      <div class="chart-section">
      <div class="card">
        <div class="card-header">
          <span class="card-title" id="chart-title">종목 차트</span>
          <div style="display:flex;gap:6px;">
            <button type="button" class="interval-btn" data-interval="5m" onclick="setStockInterval('5m')">5분</button>
            <button type="button" class="interval-btn" data-interval="10m" onclick="setStockInterval('10m')">10분</button>
            <button type="button" class="interval-btn" data-interval="1h" onclick="setStockInterval('1h')">1시간</button>
            <button type="button" class="interval-btn active" data-interval="1d" onclick="setStockInterval('1d')">일봉</button>
          </div>
        </div>
        <div id="stock-candle-chart" style="width:100%;height:320px"></div>
        <div id="stock-volume-chart" style="width:100%;height:80px"></div>
        <div id="rsi-chart-container" style="height:80px;margin-top:4px;position:relative;display:none;">
          <canvas id="rsi-chart"></canvas>
          <div style="position:absolute;top:2px;left:8px;font-size:10px;color:#4a5068;">RSI(14)</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">종목 정보</span>
        </div>
        <div class="card-body" id="stock-detail">
          <div style="color:var(--muted);font-size:13px;text-align:center;padding:40px 0">
            종목을 선택하세요
          </div>
        </div>
      </div>
    </div>
    </div>

    <div id="strategy-bar" class="strategy-bar">
      <span>🎯 오늘 전략:</span>
      <span id="strat-outlook">--</span>
      <span id="strat-risk">--</span>
      <span id="strat-picks">--</span>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="scanner-header">
          <h3 class="card-title">📋 종목 스캐너 (TOP50)</h3>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <div class="scanner-filters">
              <button type="button" class="filter-btn active" data-filter="all">전체</button>
              <button type="button" class="filter-btn" data-filter="buy">🟢 매수신호</button>
              <button type="button" class="filter-btn" data-filter="holding">🏦 보유중</button>
              <button type="button" class="filter-btn" data-filter="oversold">🔴 과매도</button>
              <button type="button" class="filter-btn" data-filter="volume">🔥 거래량급등</button>
            </div>
            <select id="sort-stocks" onchange="sortStocks(this.value)" style="background:#1a1a2e;color:#fff;border:1px solid #ffffff20;border-radius:4px;padding:4px 8px;font-size:12px;">
              <option value="change">등락률순</option>
              <option value="rsi_asc">RSI 낮은순</option>
              <option value="rsi_desc">RSI 높은순</option>
              <option value="vol_desc">거래량 높은순</option>
            </select>
          </div>
        </div>
      </div>
      <div style="padding:16px;">
        <div class="stock-grid" id="stock-grid">
          <div style="color:var(--muted);padding:20px;font-size:13px">로딩 중...</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">🌅 오늘 AI 전략 상세</span>
        <span style="font-family:var(--mono);font-size:11px;color:var(--muted)" id="strategy-time"></span>
      </div>
      <div class="card-body" id="strategy-box">
        <div style="color:var(--muted);font-size:13px">전략 로딩 중...</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 400px;gap:16px;margin-bottom:20px">
      <div class="card">
        <div class="card-header">
          <span class="card-title">📋 실시간 로그 (stock_trading)</span>
          <span style="font-family:var(--mono);font-size:11px;color:var(--muted)" id="stock-log-time"></span>
        </div>
        <div class="card-body" style="height:300px;overflow:auto">
          <pre id="stock-log-viewer" style="margin:0;font-size:12px;line-height:1.8;color:var(--text);white-space:pre-wrap;word-break:break-all"></pre>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">📊 오늘 거래</span></div>
        <div class="card-body" id="stock-trade-summary">
          <div style="color:var(--muted);font-size:13px">로딩 중...</div>
        </div>
      </div>
    </div>

  </main>
</div>

<script>
const lwScript = document.createElement('script');
lwScript.src = 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
document.head.appendChild(lwScript);

let stockChart = null, stockSeries = null, stockVolSeries = null;
let stockBbUpper = null, stockBbMiddle = null, stockBbLower = null;
let selectedCode = null;
let currentStockInterval = '1d';

lwScript.onload = function() {
  const c = document.getElementById('stock-candle-chart');
  stockChart = LightweightCharts.createChart(c, {
    width: c.clientWidth, height: 320,
    layout: { background: { color: '#0f1422' }, textColor: '#4a5068' },
    grid: { vertLines: { color: '#1e2537' }, horzLines: { color: '#1e2537' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    timeScale: { borderColor: '#1e2537', timeVisible: true },
    rightPriceScale: { borderColor: '#1e2537' },
  });
  stockSeries = stockChart.addCandlestickSeries({
    upColor: '#00e676', downColor: '#ff3d57',
    borderUpColor: '#00e676', borderDownColor: '#ff3d57',
    wickUpColor: '#00e676', wickDownColor: '#ff3d57',
  });
  stockBbUpper = stockChart.addLineSeries({ color: 'rgba(255,68,68,0.6)', lineWidth: 1, lineStyle: 2 });
  stockBbMiddle = stockChart.addLineSeries({ color: 'rgba(255,217,61,0.5)', lineWidth: 1 });
  stockBbLower = stockChart.addLineSeries({ color: 'rgba(107,203,119,0.6)', lineWidth: 1, lineStyle: 2 });

  const vc = document.getElementById('stock-volume-chart');
  const volChart = LightweightCharts.createChart(vc, {
    width: vc.clientWidth, height: 80,
    layout: { background: { color: '#0f1422' }, textColor: '#4a5068' },
    grid: { vertLines: { color: '#1e2537' }, horzLines: { color: '#1e2537' } },
    timeScale: { borderColor: '#1e2537', timeVisible: true },
    rightPriceScale: { borderColor: '#1e2537' },
  });
  stockVolSeries = volChart.addHistogramSeries({
    color: 'rgba(0,212,255,0.3)', priceFormat: { type: 'volume' }, priceScaleId: '',
  });
};

const fmt = n => n ? Number(n).toLocaleString('ko-KR') : '--';
let stocksData = [];
let holdingCodes = [];

async function loadPortfolio() {
  try {
    const res = await fetch('/api/stocks/portfolio');
    const data = await res.json();
    if (data.error && !data.positions) return;
    document.getElementById('total-asset').textContent = (data.estimated_asset || 0).toLocaleString('ko-KR') + '원';
    document.getElementById('total-eval').textContent = (data.total_evaluation || 0).toLocaleString('ko-KR') + '원';
    document.getElementById('deposit').textContent = (data.deposit || 0).toLocaleString('ko-KR') + '원';
    var cumEl = document.getElementById('cum-pnl');
    var cumPct = data.cumulative_pnl_pct || 0;
    cumEl.textContent = (cumPct >= 0 ? '+' : '') + cumPct + '%';
    cumEl.className = 'port-value ' + (cumPct >= 0 ? 'kr-up' : 'kr-dn');
    var todayEl = document.getElementById('today-pnl');
    var todayPnl = data.today_pnl || 0;
    todayEl.textContent = (todayPnl >= 0 ? '+' : '') + todayPnl.toLocaleString('ko-KR') + '원';
    todayEl.className = 'port-value ' + (todayPnl >= 0 ? 'kr-up' : 'kr-dn');
    holdingCodes = (data.positions || []).map(function(p){ return p.code; });
    renderHoldings(data.positions || [], data.max_positions || 5);
    var statusEl = document.getElementById('market-status');
    if (statusEl) {
      if (data.is_market_open) {
        statusEl.innerHTML = '<span style="color:#00ff88">● 장 중</span>';
      } else {
        statusEl.innerHTML = '<span style="color:#ff8800">● 장 마감 (종가 기준)</span>';
      }
    }
    var ut = document.getElementById('update-time');
    if (ut) ut.textContent = '마지막 업데이트: ' + new Date().toLocaleTimeString('ko-KR');
  } catch(e) { console.error('portfolio', e); }
}

function renderHoldings(positions, maxPos) {
  document.getElementById('pos-count').textContent = positions.length;
  var tbody = document.getElementById('holdings-body');
  if (!positions.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px;">보유종목 없음</td></tr>';
    return;
  }
  tbody.innerHTML = positions.map(function(p) {
    var pnlClass = p.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg';
    var pnlSign = p.pnl_pct >= 0 ? '+' : '';
    var liveTag = p.is_live ? '' : ' <span style="color:#ff8800;font-size:9px;">(종가)</span>';
    return '<tr onclick="selectStock(\\'' + p.code + '\\',\\'' + (p.name || '').replace(/'/g, "\\'") + '\\')" style="cursor:pointer">' +
      '<td>' + (p.name || p.code) + '</td>' +
      '<td>' + p.quantity + '주</td>' +
      '<td>' + (p.avg_entry || 0).toLocaleString('ko-KR') + '</td>' +
      '<td>' + (p.current_price || 0).toLocaleString('ko-KR') + liveTag + '</td>' +
      '<td>' + (p.evaluation || 0).toLocaleString('ko-KR') + '</td>' +
      '<td class="' + pnlClass + '">' + pnlSign + (p.pnl_pct || 0) + '%<br><small>(' + pnlSign + (p.pnl_amount || 0).toLocaleString('ko-KR') + '원)</small></td>' +
      '<td>' + (p.split_count || 1) + '차</td></tr>';
  }).join('');

  var totalCost = positions.reduce(function(s, p) { return s + ((p.avg_entry || 0) * (p.quantity || 0)); }, 0);
  var totalEval = positions.reduce(function(s, p) { return s + (p.evaluation || 0); }, 0);
  var totalPnl = positions.reduce(function(s, p) { return s + (p.pnl_amount || 0); }, 0);
  var totalPnlPct = totalCost > 0 ? (totalPnl / totalCost * 100).toFixed(2) : 0;
  var pnlClass = totalPnl >= 0 ? 'pnl-pos' : 'pnl-neg';
  var sign = totalPnl >= 0 ? '+' : '';
  tbody.innerHTML += '<tr style="border-top: 1px solid #ffffff30; font-weight: bold;">' +
    '<td>합계</td>' +
    '<td>' + positions.length + '종목</td>' +
    '<td></td><td></td>' +
    '<td>' + totalEval.toLocaleString('ko-KR') + '원</td>' +
    '<td class="' + pnlClass + '">' + sign + totalPnlPct + '%<br><small>(' + sign + totalPnl.toLocaleString('ko-KR') + '원)</small></td>' +
    '<td>' + positions.length + '/' + (maxPos || 5) + '</td></tr>';
}

async function loadDailyPnL() {
  try {
    var res = await fetch('/api/stocks/daily-pnl?days=7');
    var data = await res.json();
    if (!data.daily || data.daily.length === 0) return;
    var canvas = document.getElementById('daily-pnl-chart');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    canvas.width = canvas.parentElement.clientWidth || 300;
    var w = canvas.width, h = canvas.height;
    ctx.fillStyle = '#0f1422';
    ctx.fillRect(0, 0, w, h);
    var points = data.daily;
    var values = points.map(function(p){ return p.total_pnl || 0; });
    var maxVal = Math.max.apply(null, values.map(Math.abs).concat([1]));
    var padding = { left: 50, right: 20, top: 20, bottom: 28 };
    var chartW = w - padding.left - padding.right;
    var chartH = h - padding.top - padding.bottom;
    var xScale = function(i){ return padding.left + (i / (points.length - 1)) * chartW; };
    var yScale = function(v){ return padding.top + chartH/2 - (v / maxVal) * (chartH/2); };
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.moveTo(padding.left, yScale(0));
    ctx.lineTo(w - padding.right, yScale(0));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(xScale(0), yScale(0));
    points.forEach(function(p, i){ ctx.lineTo(xScale(i), yScale(p.total_pnl || 0)); });
    ctx.lineTo(xScale(points.length - 1), yScale(0));
    ctx.closePath();
    ctx.fillStyle = values[values.length - 1] >= 0 ? 'rgba(255,68,68,0.1)' : 'rgba(68,136,255,0.1)';
    ctx.fill();
    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = values[values.length - 1] >= 0 ? '#ff4444' : '#4488ff';
    points.forEach(function(p, i){
      var x = xScale(i), y = yScale(p.total_pnl || 0);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = '#4a5068';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    points.forEach(function(p, i){
      if (i % 2 === 0 || i === points.length - 1) {
        var label = (p.date || '').slice(4, 6) + '/' + (p.date || '').slice(6, 8);
        ctx.fillText(label, xScale(i), h - 8);
      }
      ctx.beginPath();
      ctx.arc(xScale(i), yScale(p.total_pnl || 0), 3, 0, Math.PI * 2);
      ctx.fillStyle = (p.total_pnl || 0) >= 0 ? '#ff4444' : '#4488ff';
      ctx.fill();
    });
    var lastPnl = values[values.length - 1];
    ctx.fillStyle = lastPnl >= 0 ? '#ff4444' : '#4488ff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText((lastPnl >= 0 ? '+' : '') + lastPnl.toLocaleString('ko-KR') + '원', xScale(points.length - 1) + 6, yScale(lastPnl) + 4);
  } catch(e) { console.error('daily-pnl', e); }
}

function filterStocks(type) {
  document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-filter') === type); });
  document.querySelectorAll('.stock-card').forEach(function(card){
    var rsi = parseFloat(card.getAttribute('data-rsi') || 50);
    var vol = parseFloat(card.getAttribute('data-vol') || 1);
    var isHolding = card.getAttribute('data-holding') === 'true';
    var show = true;
    if (type === 'buy') show = rsi <= 45;
    else if (type === 'holding') show = isHolding;
    else if (type === 'oversold') show = rsi <= 30;
    else if (type === 'volume') show = vol >= 2.0;
    card.style.display = show ? '' : 'none';
  });
}

function sortStocks(by) {
  var container = document.querySelector('.stock-grid');
  if (!container) return;
  var cards = Array.prototype.slice.call(container.querySelectorAll('.stock-card'));
  cards.sort(function(a, b) {
    var ra = parseFloat(a.getAttribute('data-rsi') || '50');
    var rb = parseFloat(b.getAttribute('data-rsi') || '50');
    var va = parseFloat(a.getAttribute('data-vol') || '1');
    var vb = parseFloat(b.getAttribute('data-vol') || '1');
    var ca = parseFloat(a.getAttribute('data-change') || '0');
    var cb = parseFloat(b.getAttribute('data-change') || '0');
    switch(by) {
      case 'rsi_asc': return ra - rb;
      case 'rsi_desc': return rb - ra;
      case 'vol_desc': return vb - va;
      case 'change': default: return cb - ca;
    }
  });
  cards.forEach(function(card){ container.appendChild(card); });
}

async function loadStocks() {
  try {
    var res = await fetch('/api/stocks/overview');
    var stocks = await res.json();
    stocksData = stocks;
    var grid = document.getElementById('stock-grid');
    var timeEl = document.getElementById('update-time');
    if (timeEl) timeEl.textContent = '마지막 업데이트: ' + new Date().toLocaleTimeString('ko-KR');

    if (!stocks.length) {
      grid.innerHTML = '<div style="color:var(--muted);padding:20px">데이터 없음</div>';
      return;
    }

    grid.innerHTML = stocks.map(function(s) {
      var isPos = s.change >= 0;
      var selected = selectedCode === s.code ? ' selected' : '';
      var isHolding = holdingCodes.indexOf(s.code) >= 0;
      return '<div class="stock-card' + (isHolding ? ' holding' : '') + selected + '" onclick="selectStock(\\'' + s.code + '\\',\\'' + (s.name || '').replace(/'/g, "\\'") + '\\')" data-rsi="50" data-vol="1" data-holding="' + isHolding + '" data-change="' + (s.change || 0) + '">' +
        '<div class="industry-badge">' + (s.industry || '') + '</div>' +
        '<div class="stock-name">' + s.name + '</div>' +
        '<div class="stock-price">' + fmt(Math.round(s.price)) + '원</div>' +
        '<div class="stock-change ' + (isPos ? 'positive' : 'negative') + '">' +
          (isPos ? '▲' : '▼') + ' ' + Math.abs(s.change).toFixed(2) + '%' +
        '</div>' +
        '<div class="indicator-badges">' +
        '<span class="badge rsi" id="rsi-' + s.code + '">RSI --</span>' +
        '<span class="badge macd" id="macd-' + s.code + '">MACD --</span>' +
        '<span class="badge bb" id="bb-' + s.code + '">BB --</span>' +
        '<span class="badge vol" id="vol-' + s.code + '">Vol --</span>' +
        '</div>' +
        '</div>';
    }).join('');
    stocks.forEach(function(s){ loadStockIndicators(s.code); });
    document.querySelectorAll('.filter-btn').forEach(function(btn){
      btn.onclick = function(){ filterStocks(btn.getAttribute('data-filter')); };
    });
  } catch(e) { console.error('stocks error', e); }
}

async function loadStockIndicators(code) {
  try {
    var res = await fetch('/api/stocks/indicators/' + code);
    var data = await res.json();
    if (data.error) return;
    var rsiEl = document.getElementById('rsi-' + code);
    if (rsiEl) {
      var card = rsiEl.closest('.stock-card');
      if (card) {
        card.setAttribute('data-rsi', data.rsi != null ? data.rsi : 50);
        card.setAttribute('data-vol', data.vol_ratio != null ? data.vol_ratio : 1);
      }
    }
    var macdEl = document.getElementById('macd-' + code);
    var bbEl = document.getElementById('bb-' + code);
    var volEl = document.getElementById('vol-' + code);
    if (rsiEl) {
      rsiEl.textContent = 'RSI ' + data.rsi;
      rsiEl.className = 'badge rsi';
      if (data.rsi <= 30) rsiEl.classList.add('oversold');
      else if (data.rsi <= 45) rsiEl.classList.add('low');
      else if (data.rsi >= 70) rsiEl.classList.add('overbought');
    }
    if (macdEl) macdEl.textContent = 'MACD ' + (data.macd > 0 ? '+' : '') + data.macd;
    if (bbEl) bbEl.textContent = 'BB ' + data.bb_pos + '%';
    if (volEl) volEl.textContent = 'Vol ' + data.vol_ratio + 'x';
  } catch(e) { console.log('지표 로드 실패:', code); }
}

function setStockInterval(interval) {
  currentStockInterval = interval;
  document.querySelectorAll('.interval-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-interval') === interval);
  });
  if (selectedCode) loadStockChart(selectedCode);
}

function computeBBRSI(candles) {
  if (!candles || candles.length === 0) return candles;
  var closes = candles.map(function(d){ return Number(d.close); });
  var i, j, window, ma, std, gains, losses, avgGain, avgLoss, rs;
  for (i = 0; i < candles.length; i++) {
    if (i < 19) {
      candles[i].bb_upper = candles[i].bb_middle = candles[i].bb_lower = null;
    } else {
      window = closes.slice(i - 19, i + 1);
      ma = window.reduce(function(a,b){ return a+b; }, 0) / 20;
      std = Math.sqrt(window.reduce(function(s,c){ return s + (c - ma)*(c - ma); }, 0) / 20);
      candles[i].bb_upper = Math.round(ma + 2 * std);
      candles[i].bb_middle = Math.round(ma);
      candles[i].bb_lower = Math.round(ma - 2 * std);
    }
    if (i < 14) {
      candles[i].rsi = null;
    } else {
      gains = []; losses = [];
      for (j = i - 13; j <= i; j++) {
        var diff = closes[j] - closes[j-1];
        gains.push(diff > 0 ? diff : 0);
        losses.push(diff < 0 ? -diff : 0);
      }
      avgGain = gains.reduce(function(a,b){ return a+b; }, 0) / 14;
      avgLoss = losses.reduce(function(a,b){ return a+b; }, 0) / 14;
      rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      candles[i].rsi = Math.round((100 - (100 / (1 + rs))) * 10) / 10;
    }
  }
  return candles;
}

async function loadStockChart(code) {
  if (!code || !stockSeries || !stockVolSeries) return;
  try {
    const res = await fetch('/api/stocks/chart/' + code + '?interval=' + encodeURIComponent(currentStockInterval));
    const raw = await res.json();
    var candles = raw.candles && raw.candles.length ? raw.candles : (Array.isArray(raw) ? raw : []);
    if (!candles.length) return;
    if (candles[0].bb_upper == null && candles[0].rsi == null) candles = computeBBRSI(candles);

    stockSeries.setData(candles.map(d => ({
      time: d.time, open: d.open, high: d.high, low: d.low, close: d.close,
    })));
    stockVolSeries.setData(candles.map(d => ({
      time: d.time, value: d.volume,
      color: d.close >= d.open ? 'rgba(0,230,118,0.4)' : 'rgba(255,61,87,0.4)',
    })));

    if (stockBbUpper && stockBbMiddle && stockBbLower) {
      const bbUpper = candles.filter(d => d.bb_upper != null).map(d => ({ time: d.time, value: d.bb_upper }));
      const bbMiddle = candles.filter(d => d.bb_middle != null).map(d => ({ time: d.time, value: d.bb_middle }));
      const bbLower = candles.filter(d => d.bb_lower != null).map(d => ({ time: d.time, value: d.bb_lower }));
      stockBbUpper.setData(bbUpper);
      stockBbMiddle.setData(bbMiddle);
      stockBbLower.setData(bbLower);
    }

    var rsiContainer = document.getElementById('rsi-chart-container');
    if (rsiContainer) {
      rsiContainer.style.display = candles.some(function(c){ return c.rsi != null; }) ? 'block' : 'none';
      drawRSIChart(candles);
    }

    const last = candles[candles.length - 1];
    const prev = candles.length > 1 ? candles[candles.length - 2] : null;
    const chg = prev ? ((last.close - prev.close) / prev.close * 100).toFixed(2) : 0;
    const isPos = chg >= 0;
    document.getElementById('stock-detail').innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
      '<div><div class="stat-label">현재가</div><div class="stat-value neutral">' + fmt(Math.round(last.close)) + '원</div></div>' +
      '<div><div class="stat-label">전일대비</div><div class="stat-value ' + (isPos?'positive':'negative') + '">' + (isPos?'+':'') + chg + '%</div></div>' +
      '<div><div class="stat-label">고가</div><div class="stat-value" style="font-size:16px;color:var(--green)">' + fmt(Math.round(last.high)) + '원</div></div>' +
      '<div><div class="stat-label">저가</div><div class="stat-value" style="font-size:16px;color:var(--red)">' + fmt(Math.round(last.low)) + '원</div></div>' +
      '<div><div class="stat-label">거래량</div><div class="stat-value" style="font-size:16px">' + fmt(last.volume) + '</div></div>' +
      '<div><div class="stat-label">종목코드</div><div class="stat-value" style="font-size:16px">' + code + '</div></div>' +
      '</div>';
  } catch(e) { console.error('chart error', e); }
}

function drawRSIChart(candles) {
  var container = document.getElementById('rsi-chart-container');
  var canvas = document.getElementById('rsi-chart');
  if (!canvas || !container) return;
  canvas.width = container.clientWidth;
  canvas.height = 80;
  var ctx = canvas.getContext('2d');
  var w = canvas.width;
  var h = canvas.height;
  ctx.fillStyle = '#0f1422';
  ctx.fillRect(0, 0, w, h);
  var rsiData = candles.map(function(c){ return c.rsi; }).filter(function(v){ return v != null; });
  if (rsiData.length < 2) return;
  var padding = { left: 40, right: 10 };
  var chartW = w - padding.left - padding.right;
  var yScale = function(v){ return h - (v / 100) * h; };
  var xScale = function(i){ return padding.left + (i / (rsiData.length - 1)) * chartW; };
  ctx.fillStyle = 'rgba(255,68,68,0.08)';
  ctx.fillRect(padding.left, yScale(100), chartW, yScale(70) - yScale(100));
  ctx.fillStyle = 'rgba(107,203,119,0.08)';
  ctx.fillRect(padding.left, yScale(30), chartW, yScale(0) - yScale(30));
  [30, 50, 70].forEach(function(level){
    ctx.beginPath();
    ctx.strokeStyle = level === 50 ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)';
    ctx.setLineDash(level === 50 ? [] : [2, 4]);
    ctx.lineWidth = 0.5;
    ctx.moveTo(padding.left, yScale(level));
    ctx.lineTo(w - padding.right, yScale(level));
    ctx.stroke();
  });
  ctx.setLineDash([]);
  ctx.fillStyle = '#4a5068';
  ctx.font = '9px monospace';
  ctx.textAlign = 'right';
  [30, 50, 70].forEach(function(v){
    ctx.fillText(v, padding.left - 4, yScale(v) + 3);
  });
  ctx.beginPath();
  ctx.lineWidth = 1.5;
  rsiData.forEach(function(v, i){
    var x = xScale(i);
    var y = yScale(v);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  var lastRSI = rsiData[rsiData.length - 1];
  if (lastRSI <= 30) ctx.strokeStyle = '#ff4444';
  else if (lastRSI <= 45) ctx.strokeStyle = '#ffa500';
  else if (lastRSI >= 70) ctx.strokeStyle = '#ff4444';
  else ctx.strokeStyle = '#00d4ff';
  ctx.stroke();
  ctx.fillStyle = ctx.strokeStyle;
  ctx.font = 'bold 11px monospace';
  ctx.textAlign = 'left';
  ctx.fillText(lastRSI.toFixed(1), xScale(rsiData.length - 1) + 4, yScale(lastRSI) + 3);
}

async function selectStock(code, name) {
  selectedCode = code;
  document.getElementById('chart-title').textContent = name + ' 차트';

  document.querySelectorAll('.stock-card').forEach(el => el.classList.remove('selected'));
  var t = event && event.currentTarget;
  if (t) t.classList.add('selected');

  await loadStockChart(code);
}

async function loadStrategy() {
  try {
    var res = await fetch('/api/stocks/strategy');
    var raw = await res.json();
    var d = raw.strategy || raw;
    if (!d || raw.error) {
      document.getElementById('strategy-box').innerHTML = '<div style="color:var(--muted)">오늘 전략 없음 (08:00 브리핑 대기)</div>';
      var so = document.getElementById('strat-outlook'); if (so) so.textContent = '--';
      var sr = document.getElementById('strat-risk'); if (sr) sr.textContent = '--';
      var sp = document.getElementById('strat-picks'); if (sp) sp.textContent = '--';
      return;
    }
    var outlook = d.market_outlook || '?';
    var risk = d.risk_level || '?';
    var picks = d.top_picks || [];
    var buys = picks.filter(function(p){ return p.action === 'BUY'; }).length;
    var watches = picks.filter(function(p){ return p.action === 'WATCH'; }).length;
    var sells = picks.filter(function(p){ return p.action === 'SELL'; }).length;
    var so = document.getElementById('strat-outlook'); if (so) so.textContent = '전망: ' + outlook;
    var sr = document.getElementById('strat-risk'); if (sr) sr.textContent = '리스크: ' + risk;
    var sp = document.getElementById('strat-picks'); if (sp) sp.textContent = '추천: BUY ' + buys + ' / WATCH ' + watches + (sells ? ' / SELL ' + sells : '');

    var picksHtml = picks.map(function(p) {
      return '<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">' +
        '<span style="font-size:18px">' + (p.action==='BUY'?'🟢':p.action==='WATCH'?'👀':'🔴') + '</span>' +
        '<div><div style="font-weight:700">' + (p.name||'') + ' <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">(' + (p.code||'') + ')</span></div>' +
        '<div style="font-size:12px;color:var(--muted);margin-top:2px">' + (p.reason||'') + '</div></div>' +
        '<span style="margin-left:auto;font-family:var(--mono);font-size:11px;padding:3px 8px;border-radius:4px;background:' +
          (p.action==='BUY'?'rgba(0,230,118,0.1)':p.action==='WATCH'?'rgba(255,214,0,0.1)':'rgba(255,61,87,0.1)') + ';color:' +
          (p.action==='BUY'?'var(--green)':p.action==='WATCH'?'var(--yellow)':'var(--red)') + '">' + (p.action||'') + '</span></div>';
    }).join('');
    document.getElementById('strategy-box').innerHTML =
      '<div style="display:flex;gap:16px;margin-bottom:16px">' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.2);font-family:var(--mono);font-size:12px">시장: <b>' + outlook + '</b></div>' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(255,214,0,0.1);border:1px solid rgba(255,214,0,0.2);font-family:var(--mono);font-size:12px">리스크: <b>' + risk + '</b></div>' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(74,80,104,0.2);border:1px solid var(--border);font-family:var(--mono);font-size:12px;flex:1">' + (d.summary||'') + '</div>' +
      '</div>' + picksHtml;
    var timeEl = document.getElementById('strategy-time');
    if (timeEl && d.date) timeEl.textContent = d.date;
  } catch(e) {
    document.getElementById('strategy-box').innerHTML = '<div style="color:var(--muted)">전략 로드 실패</div>';
  }
}

setInterval(function(){ var c=document.getElementById('clock'); if(c) c.textContent=new Date().toLocaleTimeString('ko-KR'); }, 1000);
loadPortfolio().then(function(){ loadStocks(); });
loadStrategy();
loadDailyPnL();
setInterval(loadPortfolio, 30000);
setInterval(loadStocks, 60000);
setInterval(loadDailyPnL, 300000);
setInterval(function(){ if (stocksData.length) stocksData.forEach(function(s){ loadStockIndicators(s.code); }); }, 60000);

async function loadStockLogs() {
  try {
    const res = await fetch('/api/stocks/logs');
    const d = await res.json();
    const el = document.getElementById('stock-log-viewer');
    const timeEl = document.getElementById('stock-log-time');
    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('ko-KR');

    const escape = s => String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;');

    const cls = line => {
      if (/매수|BUY/.test(line)) return 'color:var(--green)';
      if (/매도|SELL|손절/.test(line)) return 'color:var(--red)';
      if (/ERROR|실패/.test(line)) return 'color:var(--red)';
      if (/사이클 시작/.test(line)) return 'color:var(--accent)';
      if (/HOLD|SKIP/.test(line)) return 'color:var(--muted)';
      if (/익절/.test(line)) return 'color:var(--green)';
      return 'color:var(--text)';
    };

    el.innerHTML = (d.lines || [])
      .map(l => '<span style="' + cls(l) + '">' + escape(l) + '</span>')
      .join('\\n') || '(비어 있음)';
    el.scrollTop = el.scrollHeight;
  } catch(e) {
    const v = document.getElementById('stock-log-viewer');
    if (v) v.textContent = '로딩 실패';
  }
}

async function loadStockTradeSummary() {
  try {
    const res = await fetch('/api/stocks/trades');
    const d = await res.json();
    const el = document.getElementById('stock-trade-summary');
    if (!el) return;
    if (!d || !d.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center;padding:20px">오늘 거래 없음</div>';
      return;
    }
    el.innerHTML = d.map(t =>
      '<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:12px">' +
      '<span style="color:' + (t.trade_type==='BUY'?'var(--green)':'var(--red)') + '">' + t.trade_type + '</span>' +
      '<span>' + (t.stock_name || t.stock_code || '') + '</span>' +
      '<span>' + Number(t.price||0).toLocaleString() + '원</span>' +
      '<span style="color:var(--muted)">' + t.quantity + '주</span>' +
      '</div>'
    ).join('');
  } catch(e) {}
}

loadStockLogs();
loadStockTradeSummary();
setInterval(loadStockLogs, 30000);
setInterval(loadStockTradeSummary, 30000);
</script>
</body>
</html>"""

@app.get("/stocks", response_class=HTMLResponse)
async def stocks_page():
    return STOCKS_HTML

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML

def _empty_stats():
    return {
        "last_price": 0, "last_signal": "HOLD", "last_time": "", "last_rsi": 50.0, "last_macd": 0.0,
        "total_pnl": 0, "total_pnl_pct": 0, "winrate": 0, "wins": 0, "losses": 0, "total_trades": 0,
        "buys": 0, "sells": 0, "avg_confidence": 0, "today_trades": 0, "today_pnl": 0,         "position": None, "trend": "SIDEWAYS",
        "krw_balance": None,
    }

@app.get("/api/stats")
async def get_stats():
    if not supabase:
        return _empty_stats()
    try:
        # 전체 거래 통계
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(200).execute()
        trades = res.data or []

        buys   = [t for t in trades if t.get("action") == "BUY"]
        sells  = [t for t in trades if t.get("action") == "SELL"]
        closed = supabase.table("btc_position").select("*").eq("status","CLOSED").execute().data or []

        wins   = len([p for p in closed if (p.get("pnl") or 0) > 0])
        losses = len([p for p in closed if (p.get("pnl") or 0) < 0])
        total_pnl = sum(float(p.get("pnl") or 0) for p in closed)
        total_krw = sum(float(p.get("entry_krw") or 0) for p in closed)

        # 오늘 통계
        today = datetime.now().date().isoformat()
        today_closed = [p for p in closed if (p.get("exit_time") or "")[:10] == today]
        today_trades = len([t for t in trades if (t.get("timestamp") or "")[:10] == today])
        today_pnl = sum(float(p.get("pnl") or 0) for p in today_closed)

        # 포지션
        pos_res = supabase.table("btc_position").select("*").eq("status","OPEN").order("entry_time",desc=True).limit(1).execute()
        position = pos_res.data[0] if pos_res.data else None

        last = trades[0] if trades else {}

        # KRW 잔고: 60초 캐시
        _refresh_upbit_cache()
        krw_balance = _upbit_cache["krw"]

        # 1시간봉 추세 (실패 시 SIDEWAYS)
        trend = _get_hourly_trend()

        return {
            "last_price":     last.get("price", 0),
            "last_signal":    last.get("action", "HOLD"),
            "last_time":      (last.get("timestamp", "") or "")[:19],
            "last_rsi":       float(last.get("rsi") or 50),
            "last_macd":      float(last.get("macd") or 0),
            "total_pnl":      total_pnl,
            "total_pnl_pct":  (total_pnl / total_krw * 100) if total_krw else 0,
            "winrate":        (wins / (wins + losses) * 100) if (wins + losses) else 0,
            "wins":           wins,
            "losses":         losses,
            "total_trades":   len(trades),
            "buys":           len(buys),
            "sells":          len(sells),
            "avg_confidence": sum(float(t.get("confidence") or 0) for t in trades) / len(trades) if trades else 0,
            "today_trades":   today_trades,
            "today_pnl":      today_pnl,
            "position":       position,
            "trend":          trend,
            "krw_balance":    krw_balance,
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}

@app.get("/api/trades")
async def get_trades():
    if not supabase:
        return []
    try:
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(100).execute()
        data = res.data or []
        for t in data:
            if t.get("timestamp"):
                t["timestamp"] = t["timestamp"][:19]
        return data
    except Exception as e:
        print(f"[ERROR] {e}")
        return []


@app.get("/api/logs")
async def get_logs():
    try:
        result = subprocess.run(
            ["tail", "-50", LOG_PATH],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        return {"lines": lines}
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"lines": [f"로그 읽기 실패: {e}"]}


@app.get("/api/news")
async def get_news():
    try:
        import xml.etree.ElementTree as ET
        res = requests.get(
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:8]
        return [
            {
                "title":  item.findtext("title", ""),
                "url":    item.findtext("link", ""),
                "time":   (item.findtext("pubDate", "") or "")[:16],
                "source": "CoinDesk",
            }
            for item in items
        ]
    except Exception as e:
        print(f"[ERROR] news: {e}")
        return []


@app.get("/api/candles")
async def get_candles(interval: str = Query("minute5")):
    try:
        import pyupbit
        df = pyupbit.get_ohlcv("KRW-BTC", interval=interval, count=100)
        if df is None or df.empty:
            return []
        result = []
        for ts, row in df.iterrows():
            result.append({
                "time":  int(ts.timestamp()),
                "open":  float(row["open"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return result
    except Exception as e:
        print(f"[ERROR] candles: {e}")
        return []


@app.get("/api/system")
async def get_system():
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        result = subprocess.run(
            ["bash", "-c", f"tail -200 {LOG_PATH} | grep '매매 사이클 시작'"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        last_cron = lines[-1][:50] if lines else "기록 없음"

        _refresh_upbit_cache()
        upbit_ok = _upbit_cache["ok"]

        return {
            "cpu": round(cpu, 1),
            "mem_used": round(mem.used / 1024**3, 1),
            "mem_total": round(mem.total / 1024**3, 1),
            "mem_pct": mem.percent,
            "disk_used": round(disk.used / 1024**3, 1),
            "disk_total": round(disk.total / 1024**3, 1),
            "disk_pct": disk.percent,
            "last_cron": last_cron,
            "upbit_ok": upbit_ok,
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}


@app.get("/api/brain")
async def get_brain():
    try:
        summary_dir = Path(f"{BRAIN_PATH}/daily-summary")
        files = sorted(summary_dir.glob("*.md")) if summary_dir.exists() else []
        summary = files[-1].read_text(encoding="utf-8")[:500] if files else "요약 없음"

        todos_path = Path(f"{BRAIN_PATH}/todos.md")
        todos = todos_path.read_text(encoding="utf-8")[:300] if todos_path.exists() else "할일 없음"

        watch_path = Path(f"{BRAIN_PATH}/watchlist.md")
        watchlist = watch_path.read_text(encoding="utf-8")[:300] if watch_path.exists() else "없음"

        mem_dir = Path(MEMORY_PATH)
        mem_files = sorted(mem_dir.glob("*.md")) if mem_dir.exists() else []
        memory = mem_files[-1].read_text(encoding="utf-8")[:300] if mem_files else "기억 없음"

        return {
            "summary": summary,
            "todos": todos,
            "watchlist": watchlist,
            "memory": memory,
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}


@app.get("/api/stocks/overview")
async def get_stocks_overview():
    if not supabase:
        return []
    try:
        stocks = supabase.table("top50_stocks").select("*").execute().data or []
        result = []
        for s in stocks:
            try:
                ohlcv = supabase.table("daily_ohlcv").select("*").eq("stock_code", s["stock_code"]).order("date", desc=True).limit(2).execute().data or []
                price = ohlcv[0]["close_price"] if ohlcv else 0
                prev = ohlcv[1]["close_price"] if len(ohlcv) > 1 else price
                change = ((price - prev) / prev * 100) if prev else 0
                result.append({
                    "code": s["stock_code"],
                    "name": s["stock_name"],
                    "industry": s.get("industry", ""),
                    "price": price,
                    "change": round(change, 2),
                    "volume": ohlcv[0]["volume"] if ohlcv else 0,
                })
            except Exception:
                pass
        return sorted(result, key=lambda x: abs(x["change"]), reverse=True)
    except Exception as e:
        print(f"[ERROR] stocks overview: {e}")
        return []


@app.get("/api/stocks/chart/{code}")
async def get_stock_chart(code: str, interval: str = Query("1d")):
    if not supabase:
        return {"candles": [], "name": "", "code": code}
    try:
        # 분봉: intraday_ohlcv (5m/1h). 10m 요청 시 5m 데이터 사용
        if interval in ("5m", "10m", "1h"):
            db_interval = "5m" if interval == "10m" else interval
            rows = (
                supabase.table("intraday_ohlcv")
                .select("*")
                .eq("stock_code", code)
                .eq("time_interval", db_interval)
                .order("datetime", desc=False)
                .limit(200)
                .execute()
                .data
                or []
            )
            if not rows:
                return {"candles": [], "name": _stock_name(code), "code": code}
            candles = []
            for r in rows:
                dt = (r.get("datetime") or "")[:16]  # YYYY-MM-DDTHH:MM (lightweight-charts)
                if len(dt) < 16:
                    dt = (r.get("datetime") or "").replace("Z", "")[:19]
                candles.append({
                    "time": dt,
                    "open": r["open_price"],
                    "high": r["high_price"],
                    "low": r["low_price"],
                    "close": r["close_price"],
                    "volume": r.get("volume") or 0,
                })
            return {"candles": candles, "name": _stock_name(code), "code": code}

        # 일봉: daily_ohlcv
        rows = supabase.table("daily_ohlcv").select("*").eq("stock_code", code).order("date", desc=False).limit(30).execute().data or []
        if not rows:
            return {"candles": [], "name": _stock_name(code), "code": code}
        closes = [float(r["close_price"]) for r in rows]

        # BB(20)
        bb_data = []
        for i in range(len(closes)):
            if i < 19:
                bb_data.append({"upper": None, "middle": None, "lower": None})
            else:
                window = closes[i - 19 : i + 1]
                ma = sum(window) / 20
                std = (sum((c - ma) ** 2 for c in window) / 20) ** 0.5
                bb_data.append({
                    "upper": round(ma + 2 * std, 0),
                    "middle": round(ma, 0),
                    "lower": round(ma - 2 * std, 0),
                })

        # RSI(14)
        rsi_data = []
        for i in range(len(closes)):
            if i < 14:
                rsi_data.append(None)
            else:
                gains, losses = [], []
                for j in range(i - 13, i + 1):
                    diff = closes[j] - closes[j - 1]
                    gains.append(max(diff, 0))
                    losses.append(max(-diff, 0))
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss == 0:
                    rsi_data.append(100)
                else:
                    rs = avg_gain / avg_loss
                    rsi_data.append(round(100 - (100 / (1 + rs)), 1))

        candles = []
        for i, r in enumerate(rows):
            c = {
                "time": r["date"],
                "open": r["open_price"],
                "high": r["high_price"],
                "low": r["low_price"],
                "close": r["close_price"],
                "volume": r.get("volume") or 0,
            }
            if i < len(bb_data):
                c["bb_upper"] = bb_data[i]["upper"]
                c["bb_middle"] = bb_data[i]["middle"]
                c["bb_lower"] = bb_data[i]["lower"]
            else:
                c["bb_upper"] = c["bb_middle"] = c["bb_lower"] = None
            c["rsi"] = rsi_data[i] if i < len(rsi_data) else None
            candles.append(c)

        return {"candles": candles, "name": _stock_name(code), "code": code}
    except Exception as e:
        print(f"[ERROR] stock chart: {e}")
        return {"candles": [], "name": "", "code": code}


def _stock_name(code: str) -> str:
    if not supabase:
        return ""
    try:
        r = supabase.table("top50_stocks").select("stock_name").eq("stock_code", code).limit(1).execute().data or []
        return r[0].get("stock_name", "") if r else ""
    except Exception:
        return ""


@app.get("/api/stocks/indicators/{code}")
async def get_stock_indicators(code: str):
    """종목별 기술적 지표 반환 (RSI, MACD, BB, vol_ratio)"""
    if not supabase:
        return {"error": "Supabase 미연결"}
    try:
        rows = (
            supabase.table("daily_ohlcv")
            .select("close_price,volume,date")
            .eq("stock_code", code)
            .order("date", desc=False)
            .limit(30)
            .execute()
            .data or []
        )
        if len(rows) < 14:
            return {"error": "데이터 부족"}

        closes = [float(r["close_price"]) for r in rows]
        volumes = [float(r.get("volume") or 0) for r in rows]

        # RSI(14)
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        # MACD(12,26)
        def ema(data, period):
            k = 2 / (period + 1)
            e = data[0]
            for d in data[1:]:
                e = d * k + e * (1 - k)
            return e

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd = round(ema12 - ema26, 0)

        # BB(20)
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        std20 = (sum((c - ma20) ** 2 for c in closes[-20:]) / 20) ** 0.5 if len(closes) >= 20 else 0
        bb_upper = round(ma20 + 2 * std20, 0)
        bb_lower = round(ma20 - 2 * std20, 0)
        bb_pos = round((closes[-1] - bb_lower) / (bb_upper - bb_lower) * 100, 1) if (bb_upper - bb_lower) > 0 else 50

        # 거래량 비율
        avg_vol = sum(volumes[-20:]) / min(len(volumes[-20:]), 20)
        vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

        return {
            "rsi": rsi,
            "macd": macd,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_pos": bb_pos,
            "vol_ratio": vol_ratio,
            "ma20": round(ma20, 0),
        }
    except Exception as e:
        print(f"[ERROR] stock indicators: {e}")
        return {"error": str(e)}


@app.get("/api/stocks/portfolio")
async def get_stocks_portfolio():
    """키움 계좌 평가 + Supabase OPEN 포지션 통합"""
    try:
        kiwoom = _get_kiwoom()
        if not kiwoom:
            return {"error": "키움 연동 없음", "positions": [], "deposit": 0, "total_evaluation": 0, "estimated_asset": 0}
        account = kiwoom.get_account_evaluation()
        summary = account.get("summary", {})
        holdings = account.get("holdings", [])

        positions = []
        market_open = is_market_open_now()
        if supabase:
            try:
                rows = (
                    supabase.table("trade_executions")
                    .select("*")
                    .eq("result", "OPEN")
                    .execute()
                    .data or []
                )
                from collections import defaultdict
                by_code = defaultdict(list)
                for p in rows:
                    by_code[p["stock_code"]].append(p)
                for code, trades in by_code.items():
                    total_qty = sum(int(t.get("quantity") or 0) for t in trades)
                    total_cost = sum(float(t.get("price") or 0) * int(t.get("quantity") or 0) for t in trades)
                    avg_entry = total_cost / total_qty if total_qty > 0 else 0
                    holding = next((h for h in holdings if h.get("code") == code), None)
                    current_price = holding["current_price"] if holding else 0

                    # 현재가 0 또는 None일 때 보정: 1) Supabase 일봉 종가, 2) 매수가
                    if not current_price or current_price == 0:
                        try:
                            last_row = (
                                supabase.table("daily_ohlcv")
                                .select("close_price")
                                .eq("stock_code", code)
                                .order("date", desc=True)
                                .limit(1)
                                .execute()
                                .data
                            )
                            if last_row:
                                current_price = float(last_row[0].get("close_price") or 0)
                        except Exception:
                            pass
                    if not current_price or current_price == 0:
                        current_price = avg_entry

                    evaluation = current_price * total_qty
                    pnl_amount = evaluation - total_cost
                    pnl_pct = (pnl_amount / total_cost * 100) if total_cost > 0 else 0
                    positions.append({
                        "code": code,
                        "name": (trades[0].get("stock_name") or code),
                        "quantity": total_qty,
                        "avg_entry": round(avg_entry, 0),
                        "current_price": round(current_price, 0),
                        "evaluation": round(evaluation, 0),
                        "pnl_amount": round(pnl_amount, 0),
                        "pnl_pct": round(pnl_pct, 2),
                        "split_count": len(trades),
                        "strategy": trades[0].get("strategy", ""),
                        "is_live": market_open,
                    })
            except Exception as e:
                print(f"[ERROR] portfolio positions: {e}")
                positions = []

        if not positions and holdings:
            for h in holdings:
                current_price = h.get("current_price", 0) or 0
                qty = h.get("quantity", 0) or 0
                avg_entry = h.get("avg_price", 0) or 0
                evaluation = h.get("evaluation", 0) or (current_price * qty)
                pnl_amount = h.get("pnl_amount", 0) or (evaluation - avg_entry * qty)
                pnl_pct = h.get("pnl_pct", 0) or 0
                positions.append({
                    "code": h.get("code", ""),
                    "name": h.get("name", ""),
                    "quantity": qty,
                    "avg_entry": avg_entry,
                    "current_price": current_price,
                    "evaluation": evaluation,
                    "pnl_amount": round(pnl_amount, 0),
                    "pnl_pct": round(pnl_pct or 0, 2),
                    "split_count": 1,
                    "strategy": "",
                    "is_live": market_open,
                })

        deposit = summary.get("deposit", 0) or 0
        total_eval = summary.get("total_evaluation", 0) or 0
        estimated = summary.get("estimated_asset", 0) or 0
        if not estimated:
            estimated = deposit + total_eval

        return {
            "deposit": deposit,
            "total_evaluation": total_eval,
            "estimated_asset": estimated,
            "today_pnl": summary.get("today_pnl", 0),
            "today_pnl_pct": summary.get("today_pnl_pct", 0) or 0,
            "cumulative_pnl": summary.get("cumulative_pnl", 0),
            "cumulative_pnl_pct": summary.get("cumulative_pnl_pct", 0) or 0,
            "positions": positions,
            "max_positions": 5,
            "is_market_open": market_open,
        }
    except Exception as e:
        print(f"[ERROR] portfolio: {e}")
        return {"error": str(e), "positions": [], "deposit": 0, "total_evaluation": 0, "estimated_asset": 0}


@app.get("/api/stocks/daily-pnl")
async def get_stocks_daily_pnl(days: int = Query(7, ge=1, le=31)):
    """최근 N일 수익 추이"""
    try:
        kiwoom = _get_kiwoom()
        if not kiwoom:
            return {"daily": []}
        results = []
        for i in range(days, -1, -1):
            d = datetime.now() - timedelta(days=i)
            date = d.strftime("%Y%m%d")
            try:
                data = kiwoom.get_daily_balance_pnl(date)
                s = data.get("summary", {})
                results.append({
                    "date": data.get("date", date),
                    "total_evaluation": s.get("total_evaluation", 0),
                    "total_pnl": s.get("total_pnl", 0),
                    "total_pnl_pct": s.get("total_pnl_pct", 0) or 0,
                    "deposit": s.get("deposit", 0),
                })
            except Exception:
                results.append({
                    "date": date,
                    "total_evaluation": 0,
                    "total_pnl": 0,
                    "total_pnl_pct": 0,
                    "deposit": 0,
                })
        return {"daily": results}
    except Exception as e:
        print(f"[ERROR] daily-pnl: {e}")
        return {"daily": []}


@app.get("/api/stocks/strategy")
async def get_stocks_strategy():
    try:
        path = Path("/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json")
        if not path.exists():
            return {"error": "없음", "strategy": None}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"strategy": data}
    except Exception as e:
        return {"error": str(e), "strategy": None}


@app.get("/api/stocks/logs")
async def get_stocks_logs():
    try:
        log_path = Path("/home/wlsdud5035/.openclaw/logs/stock_trading.log")
        if not log_path.exists():
            return {"lines": []}
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return {"lines": lines[-50:]}
    except Exception as e:
        return {"lines": [str(e)]}


@app.get("/api/stocks/trades")
async def get_stocks_trades():
    try:
        if not supabase:
            return []
        today = datetime.now().date().isoformat()
        res = (
            supabase.table("trade_executions")
            .select("*")
            .order("trade_id", desc=True)
            .limit(20)
            .execute()
        )
        data = res.data or []
        if data and isinstance(data[0], dict) and "created_at" in data[0]:
            data = [r for r in data if str(r.get("created_at") or "")[:10] == today]
        return data
    except Exception as e:
        try:
            res = supabase.table("trade_executions").select("*").order("trade_id", desc=True).limit(20).execute()
            return res.data or []
        except Exception:
            pass
        print(f"[ERROR] stocks trades: {e}")
        return []


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
