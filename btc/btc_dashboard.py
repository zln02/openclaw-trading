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
  .stock-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:border-color 0.2s;}
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
    <div class="card">
      <div class="card-header">
        <span class="card-title">📊 관심 종목</span>
        <span style="font-family:var(--mono);font-size:11px;color:var(--muted)" id="update-time"></span>
      </div>
      <div style="padding:16px;">
        <div class="stock-grid" id="stock-grid">
          <div style="color:var(--muted);padding:20px;font-size:13px">로딩 중...</div>
        </div>
      </div>
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

    <div class="card">
      <div class="card-header">
        <span class="card-title">🌅 오늘 AI 전략</span>
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

async function loadStocks() {
  try {
    const res = await fetch('/api/stocks/overview');
    const stocks = await res.json();
    const grid = document.getElementById('stock-grid');
    const timeEl = document.getElementById('update-time');
    if (timeEl) timeEl.textContent = '업데이트: ' + new Date().toLocaleTimeString('ko-KR');

    if (!stocks.length) {
      grid.innerHTML = '<div style="color:var(--muted);padding:20px">데이터 없음</div>';
      return;
    }

    grid.innerHTML = stocks.map(s => {
      const isPos = s.change >= 0;
      const selected = selectedCode === s.code ? ' selected' : '';
      return '<div class="stock-card' + selected + '" onclick="selectStock(\\'' + s.code + '\\',\\'' + s.name + '\\')">' +
        '<div class="industry-badge">' + (s.industry || '') + '</div>' +
        '<div class="stock-name">' + s.name + '</div>' +
        '<div class="stock-price">' + fmt(Math.round(s.price)) + '원</div>' +
        '<div class="stock-change ' + (isPos ? 'positive' : 'negative') + '">' +
          (isPos ? '▲' : '▼') + ' ' + Math.abs(s.change).toFixed(2) + '%' +
        '</div>' +
        '</div>';
    }).join('');
  } catch(e) { console.error('stocks error', e); }
}

function setStockInterval(interval) {
  currentStockInterval = interval;
  document.querySelectorAll('.interval-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-interval') === interval);
  });
  if (selectedCode) loadStockChart(selectedCode);
}

async function loadStockChart(code) {
  if (!code || !stockSeries || !stockVolSeries) return;
  try {
    const res = await fetch('/api/stocks/chart/' + code + '?interval=' + encodeURIComponent(currentStockInterval));
    const data = await res.json();
    if (!data.length) return;

    stockSeries.setData(data.map(d => ({
      time: d.time, open: d.open, high: d.high, low: d.low, close: d.close,
    })));
    stockVolSeries.setData(data.map(d => ({
      time: d.time, value: d.volume,
      color: d.close >= d.open ? 'rgba(0,230,118,0.4)' : 'rgba(255,61,87,0.4)',
    })));

    const last = data[data.length - 1];
    const prev = data[data.length - 2];
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
    const res = await fetch('/api/stocks/strategy');
    const d = await res.json();
    if (!d || d.error) {
      document.getElementById('strategy-box').innerHTML =
        '<div style="color:var(--muted)">오늘 전략 없음 (08:00 브리핑 대기)</div>';
      return;
    }
    const picks = (d.top_picks || []).map(p =>
      '<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">' +
      '<span style="font-size:18px">' + (p.action==='BUY'?'🟢':p.action==='WATCH'?'👀':'🔴') + '</span>' +
      '<div><div style="font-weight:700">' + p.name + ' <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">(' + p.code + ')</span></div>' +
      '<div style="font-size:12px;color:var(--muted);margin-top:2px">' + p.reason + '</div></div>' +
      '<span style="margin-left:auto;font-family:var(--mono);font-size:11px;padding:3px 8px;border-radius:4px;background:' +
        (p.action==='BUY'?'rgba(0,230,118,0.1)':p.action==='WATCH'?'rgba(255,214,0,0.1)':'rgba(255,61,87,0.1)') + ';color:' +
        (p.action==='BUY'?'var(--green)':p.action==='WATCH'?'var(--yellow)':'var(--red)') + '">' + p.action + '</span>' +
      '</div>'
    ).join('');

    const outlook = d.market_outlook || '?';
    const risk = d.risk_level || '?';
    document.getElementById('strategy-box').innerHTML =
      '<div style="display:flex;gap:16px;margin-bottom:16px">' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.2);font-family:var(--mono);font-size:12px">시장: <b>' + outlook + '</b></div>' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(255,214,0,0.1);border:1px solid rgba(255,214,0,0.2);font-family:var(--mono);font-size:12px">리스크: <b>' + risk + '</b></div>' +
      '<div style="padding:8px 16px;border-radius:8px;background:rgba(74,80,104,0.2);border:1px solid var(--border);font-family:var(--mono);font-size:12px;flex:1">' + (d.summary||'') + '</div>' +
      '</div>' + picks;

    const timeEl = document.getElementById('strategy-time');
    if (timeEl && d.date) timeEl.textContent = d.date;
  } catch(e) {
    document.getElementById('strategy-box').innerHTML =
      '<div style="color:var(--muted)">전략 로드 실패</div>';
  }
}

setInterval(function(){ var c=document.getElementById('clock'); if(c) c.textContent=new Date().toLocaleTimeString('ko-KR'); }, 1000);
loadStocks();
loadStrategy();
setInterval(loadStocks, 60000);

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
        return []
    try:
        rows = supabase.table("daily_ohlcv").select("*").eq("stock_code", code).order("date", desc=False).limit(30).execute().data or []
        return [
            {"time": r["date"], "open": r["open_price"], "high": r["high_price"], "low": r["low_price"], "close": r["close_price"], "volume": r["volume"]}
            for r in rows
        ]
    except Exception as e:
        print(f"[ERROR] stock chart: {e}")
        return []


@app.get("/api/stocks/strategy")
async def get_stocks_strategy():
    try:
        path = Path("/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json")
        if not path.exists():
            return {"error": "없음"}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}


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
