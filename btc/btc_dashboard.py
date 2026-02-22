#!/usr/bin/env python3
"""
BTC 자동매매 대시보드 — 업비트 스타일 프로 버전
포트: 8080
"""

import os, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from supabase import create_client
import psutil

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
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
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
</style>
</head>
<body>
<div class="wrapper">

  <header>
    <div class="logo">
      <div class="logo-icon">🤖</div>
      OpenClaw Trading
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="live-badge">
        <div class="live-dot"></div>
        LIVE
      </div>
      <div class="header-time" id="clock">--:--:--</div>
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
          <span class="card-title">가격 추이</span>
          <div style="display:flex;gap:8px;">
            <button class="refresh-btn" onclick="setChartMode('price')" id="btn-price">가격</button>
            <button class="refresh-btn" onclick="setChartMode('pnl')" id="btn-pnl">손익</button>
            <button class="refresh-btn" onclick="setChartMode('rsi')" id="btn-rsi">RSI</button>
          </div>
        </div>
        <div class="card-body">
          <canvas id="mainChart"></canvas>
        </div>
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

    <!-- 실시간 로그 + 시스템/Brain -->
    <div class="content-grid" style="margin-top:20px">
      <div class="card">
        <div class="card-header"><span class="card-title">실시간 로그 (btc_trading)</span></div>
        <div class="card-body" style="max-height:220px;overflow:auto">
          <pre id="log-viewer" style="margin:0;font-size:11px;color:var(--muted);white-space:pre-wrap;word-break:break-all"></pre>
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
let chartInstance = null;
let allTrades = [];
let tradeLimit = 10;
let tradeSignalFilter = '';

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
  updateChart();
}
let chartMode = 'price';

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
    el.textContent = (d.lines || []).join("\\n") || "(비어 있음)";
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
    const [tc, tl] = trendMap[trend] || ['side','→ SIDEWAYS'];
    trendEl.innerHTML = `<span class="trend-chip ${tc}">${tl}</span>`;

    // 스탯
    const pnl = d.total_pnl || 0;
    const pnlEl = document.getElementById('stat-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(Math.round(pnl)) + '원';
    pnlEl.className = 'stat-value ' + (pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : '');

    document.getElementById('stat-pnl-pct').textContent = fmtPct(d.total_pnl_pct);
    document.getElementById('stat-winrate').textContent = (d.winrate || 0).toFixed(1) + '%';
    document.getElementById('stat-wl').textContent = `${d.wins || 0}승 ${d.losses || 0}패`;
    document.getElementById('stat-total').textContent = (d.total_trades || 0) + '회';
    document.getElementById('stat-buysell').textContent = `매수 ${d.buys||0} / 매도 ${d.sells||0}`;
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
      document.getElementById('position-body').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
          <div>
            <div class="stat-label">진입가</div>
            <div style="font-family:var(--mono);font-size:18px;margin-top:4px">${fmt(pos.entry_price)}원</div>
          </div>
          <div>
            <div class="stat-label">현재가</div>
            <div style="font-family:var(--mono);font-size:18px;margin-top:4px;color:var(--accent)">${fmt(d.last_price)}원</div>
          </div>
          <div>
            <div class="stat-label">수익률</div>
            <div style="font-family:var(--mono);font-size:24px;margin-top:4px" class="${isPos?'positive':'negative'}">${isPos?'+':''}${change}%</div>
          </div>
          <div>
            <div class="stat-label">투입금액</div>
            <div style="font-family:var(--mono);font-size:18px;margin-top:4px">${fmt(pos.entry_krw)}원</div>
          </div>
          <div>
            <div class="stat-label">손절가</div>
            <div style="font-family:var(--mono);font-size:14px;margin-top:4px;color:var(--red)">${fmt(Math.round(pos.entry_price*0.98))}원</div>
          </div>
          <div>
            <div class="stat-label">익절가</div>
            <div style="font-family:var(--mono);font-size:14px;margin-top:4px;color:var(--green)">${fmt(Math.round(pos.entry_price*1.04))}원</div>
          </div>
        </div>`;
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

function setChartMode(mode) {
  chartMode = mode;
  ['price','pnl','rsi'].forEach(m => {
    document.getElementById('btn-' + m).style.color = m === mode ? 'var(--accent)' : '';
    document.getElementById('btn-' + m).style.borderColor = m === mode ? 'var(--accent)' : '';
  });
  updateChart();
}

function updateChart() {
  if (!allTrades.length) return;

  const sorted = [...allTrades].reverse();
  const labels = sorted.map(t => t.timestamp ? t.timestamp.substring(11,16) : '');

  let data, label, color;
  if (chartMode === 'price') {
    data = sorted.map(t => t.price);
    label = 'BTC 가격 (원)';
    color = 'rgba(0,212,255,1)';
  } else if (chartMode === 'pnl') {
    let cum = 0;
    data = sorted.map(t => { cum += (t.pnl || 0); return cum; });
    label = '누적 손익 (원)';
    color = 'rgba(0,230,118,1)';
  } else {
    data = sorted.map(t => t.rsi || null);
    label = 'RSI';
    color = 'rgba(255,214,0,1)';
  }

  const ctx = document.getElementById('mainChart').getContext('2d');
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label,
        data,
        borderColor: color,
        backgroundColor: color.replace('1)', '0.05)'),
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#141928',
          borderColor: '#1e2537',
          borderWidth: 1,
          titleColor: '#4a5068',
          bodyColor: '#e8eaf0',
          bodyFont: { family: 'DM Mono' },
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(30,37,55,0.8)', drawBorder: false },
          ticks: { color: '#4a5068', font: { family: 'DM Mono', size: 10 }, maxTicksLimit: 8 }
        },
        y: {
          grid: { color: 'rgba(30,37,55,0.8)', drawBorder: false },
          ticks: { color: '#4a5068', font: { family: 'DM Mono', size: 10 },
            callback: v => chartMode === 'price' ? (v/1000000).toFixed(1) + 'M' : chartMode === 'pnl' ? v.toLocaleString() : v.toFixed(1)
          }
        }
      }
    }
  });
}

// 초기 로드 + 30초 자동 갱신
loadAll();
setInterval(loadAll, 30000);
setChartMode('price');

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

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML

def _empty_stats():
    return {
        "last_price": 0, "last_signal": "HOLD", "last_time": "", "last_rsi": 50.0, "last_macd": 0.0,
        "total_pnl": 0, "total_pnl_pct": 0, "winrate": 0, "wins": 0, "losses": 0, "total_trades": 0,
        "buys": 0, "sells": 0, "avg_confidence": 0, "today_trades": 0, "today_pnl": 0, "position": None, "trend": "UPTREND",
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

        # KRW 잔고: Upbit API (env에 키 있으면 조회)
        krw_balance = None
        try:
            upbit_key = os.environ.get("UPBIT_ACCESS_KEY", "")
            upbit_secret = os.environ.get("UPBIT_SECRET_KEY", "")
            if upbit_key and upbit_secret:
                import pyupbit
                upbit = pyupbit.Upbit(upbit_key, upbit_secret)
                bal = upbit.get_balance("KRW")
                krw_balance = float(bal) if bal is not None else None
        except Exception:
            pass

        return {
            "last_price":     last.get("price", 0),
            "last_signal":    last.get("action", "HOLD"),
            "last_time":      last.get("timestamp", ""),
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
            "trend":          "UPTREND",
            "krw_balance":    krw_balance,
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/trades")
async def get_trades():
    if not supabase:
        return []
    try:
        res = supabase.table("btc_trades").select("*").order("timestamp", desc=True).limit(100).execute()
        return res.data or []
    except Exception as e:
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
        return {"lines": [f"로그 읽기 실패: {e}"]}


@app.get("/api/system")
async def get_system():
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        result = subprocess.run(
            ["grep", "매매 사이클 시작", LOG_PATH],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        last_cron = lines[-1][:50] if lines else "기록 없음"

        try:
            import pyupbit
            upbit = pyupbit.Upbit(
                os.environ.get("UPBIT_ACCESS_KEY", ""),
                os.environ.get("UPBIT_SECRET_KEY", "")
            )
            upbit.get_balance("KRW")
            upbit_ok = True
        except Exception:
            upbit_ok = False

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
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
