BTC_HTML = """<!DOCTYPE html>
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

  .stat-card:hover { border-color: var(--accent); box-shadow: 0 0 12px rgba(0,212,255,0.08); }
  .card:hover { border-color: rgba(0,212,255,0.2); }
  .indicator-card:hover { border-color: rgba(0,212,255,0.2); box-shadow: 0 0 12px rgba(0,212,255,0.06); }

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
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
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
    height: 6px;
    background: var(--border);
    border-radius: 3px;
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
  }

  @media (max-width: 768px) {
    main { padding: 12px; }
    header { padding: 12px 16px; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .btc-price { font-size: 28px; }
    .indicators { grid-template-columns: 1fr 1fr; }
    .position-card { grid-template-columns: repeat(2, 1fr); }
    .content-grid { gap: 12px; }
  }

  @media (max-width: 480px) {
    .stats-grid { grid-template-columns: 1fr; }
    .indicators { grid-template-columns: 1fr; }
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
        <a href="/us" style="text-decoration:none" class="nav-tab">🇺🇸 US</a>
      </nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="live-badge">
        <div class="live-dot"></div>
        LIVE
      </div>
      <span style="font-family:var(--mono);font-size:10px;color:var(--muted)" id="update-time"></span>
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
      <div class="indicator-card" style="border:1px solid var(--accent);background:linear-gradient(135deg,var(--bg2),rgba(0,212,255,0.05))">
        <div class="indicator-name" style="color:var(--accent)">복합 스코어 (매수 기준: 45)</div>
        <div class="indicator-value" id="ind-comp" style="font-size:36px">--</div>
        <div class="progress-bar">
          <div class="progress-fill" id="ind-comp-bar" style="width:0%;background:var(--accent)"></div>
        </div>
        <div class="stat-sub" id="ind-comp-detail" style="margin-top:6px;font-family:var(--mono);font-size:11px"></div>
      </div>
      <div class="indicator-card">
        <div class="indicator-name">일봉 RSI (Daily)</div>
        <div class="indicator-value" id="ind-rsi-d">--</div>
        <div class="progress-bar">
          <div class="progress-fill" id="ind-rsi-d-bar" style="width:50%;background:var(--accent)"></div>
        </div>
        <div class="stat-sub" id="ind-rsi-d-label" style="margin-top:6px"></div>
      </div>
      <div class="indicator-card">
        <div class="indicator-name">수익률</div>
        <div style="display:flex;gap:12px;margin-top:8px">
          <div><div class="stat-label">7일</div><div class="indicator-value" id="ind-ret7" style="font-size:18px">--</div></div>
          <div><div class="stat-label">30일</div><div class="indicator-value" id="ind-ret30" style="font-size:18px">--</div></div>
        </div>
      </div>
    </div>

    <!-- 포트폴리오 요약 -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        <span class="card-title">💼 BTC 포트폴리오</span>
        <span class="stat-sub" id="btc-port-update"></span>
      </div>
      <div class="card-body">
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px;" id="btc-port-summary">
          <div style="text-align:center;">
            <div class="stat-label">추정 총 자산</div>
            <div class="stat-value" id="btc-estimated" style="font-size:22px;">--</div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">보유 BTC 평가</div>
            <div class="stat-value" id="btc-total-eval" style="font-size:22px;">--</div>
            <div class="stat-sub" id="btc-total-eval-sub"></div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">미실현 수익</div>
            <div class="stat-value" id="btc-unrealized" style="font-size:22px;">--</div>
            <div class="stat-sub" id="btc-unrealized-pct"></div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">실현 수익 (확정)</div>
            <div class="stat-value" id="btc-realized" style="font-size:22px;">--</div>
            <div class="stat-sub" id="btc-realized-sub"></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;">
          <div style="text-align:center;">
            <div class="stat-label">KRW 잔고</div>
            <div class="stat-value" id="btc-krw" style="font-size:18px;">--</div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">총 투입금</div>
            <div class="stat-value" id="btc-invested" style="font-size:18px;">--</div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">BTC 현재가</div>
            <div class="stat-value" id="btc-cur-price" style="font-size:18px;color:var(--accent);">--</div>
          </div>
          <div style="text-align:center;">
            <div class="stat-label">승률</div>
            <div class="stat-value" id="btc-winrate" style="font-size:18px;">--</div>
            <div class="stat-sub" id="btc-winrate-sub"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 차트 + OPEN 포지션 -->
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
        <div id="candle-chart" style="width:100%;height:400px"></div>
        <div id="volume-chart" style="width:100%;height:100px"></div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">현재 보유 포지션</span>
          <span class="stat-sub" id="pos-status"></span>
        </div>
        <div class="card-body" id="position-body">
          <div class="position-empty">포지션 없음<br><span style="font-size:11px">다음 BUY 신호 대기 중</span></div>
        </div>
      </div>
    </div>

    <!-- CLOSED 포지션 히스토리 -->
    <div class="card" style="margin-bottom:20px;">
      <div class="card-header">
        <span class="card-title">📜 매매 이력 (CLOSED)</span>
        <span class="stat-sub" id="closed-count">0건</span>
      </div>
      <div style="overflow-x:auto;">
        <table class="trade-table" style="width:100%">
          <thead>
            <tr>
              <th>진입일</th>
              <th>청산일</th>
              <th>진입가</th>
              <th>청산가</th>
              <th>투입금</th>
              <th>수익</th>
              <th>수익률</th>
              <th>청산사유</th>
            </tr>
          </thead>
          <tbody id="closed-tbody">
            <tr><td colspan="8" style="text-align:center;color:var(--muted);padding:20px;">로딩 중...</td></tr>
          </tbody>
        </table>
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
    height: 400,
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
    height: 100,
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
  setInterval(loadCandles, 5000);
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

function openUsDashboard() {
  try {
    const proto = window.location.protocol || 'http:';
    const host = window.location.hostname || 'localhost';
    const url = proto + '//' + host + ':8081/';
    window.open(url, '_blank');
  } catch (e) {
    window.open('http://localhost:8081/', '_blank');
  }
}

async function loadAll() {
  await Promise.allSettled([loadStats(), loadTrades(), loadFG(), loadComposite(), loadLogs(), loadSystem(), loadBrain(), loadBtcPortfolio()]);
}

async function loadBtcPortfolio() {
  try {
    const res = await fetch('/api/btc/portfolio');
    if (!res.ok) return;
    const data = await res.json();
    if (data.error) return;
    const s = data.summary || {};
    const openPos = data.open_positions || [];
    const closedPos = data.closed_positions || [];

    // 포트폴리오 요약
    var el;
    el = document.getElementById('btc-estimated');
    if (el) el.textContent = fmt(s.estimated_asset) + '원';

    el = document.getElementById('btc-total-eval');
    if (el) el.textContent = fmt(s.total_eval) + '원';
    el = document.getElementById('btc-total-eval-sub');
    if (el) el.textContent = openPos.length + '개 포지션 보유중';

    el = document.getElementById('btc-unrealized');
    if (el) {
      var ur = s.unrealized_pnl || 0;
      el.textContent = (ur >= 0 ? '+' : '') + fmt(Math.round(ur)) + '원';
      el.className = 'stat-value ' + (ur >= 0 ? 'positive' : 'negative');
    }
    el = document.getElementById('btc-unrealized-pct');
    if (el) {
      var urp = s.unrealized_pnl_pct || 0;
      el.textContent = (urp >= 0 ? '+' : '') + urp.toFixed(2) + '%';
      el.className = 'stat-sub ' + (urp >= 0 ? 'positive' : 'negative');
    }

    el = document.getElementById('btc-realized');
    if (el) {
      var rp = s.realized_pnl || 0;
      el.textContent = (rp >= 0 ? '+' : '') + fmt(Math.round(rp)) + '원';
      el.className = 'stat-value ' + (rp >= 0 ? 'positive' : 'negative');
    }
    el = document.getElementById('btc-realized-sub');
    if (el) el.textContent = s.wins + '승 ' + s.losses + '패';

    el = document.getElementById('btc-krw');
    if (el) el.textContent = fmt(Math.round(s.krw_balance || 0)) + '원';

    el = document.getElementById('btc-invested');
    if (el) el.textContent = fmt(s.total_invested) + '원';

    el = document.getElementById('btc-cur-price');
    if (el) el.textContent = fmt(s.btc_price_krw) + '원';

    el = document.getElementById('btc-winrate');
    if (el) el.textContent = (s.winrate || 0).toFixed(1) + '%';
    el = document.getElementById('btc-winrate-sub');
    if (el) el.textContent = (s.closed_count || 0) + '건 완료';

    el = document.getElementById('btc-port-update');
    if (el) el.textContent = new Date().toLocaleTimeString('ko-KR');

    // OPEN 포지션 렌더링
    var posBody = document.getElementById('position-body');
    var posStatus = document.getElementById('pos-status');
    if (posBody && openPos.length > 0) {
      var totalInvested = openPos.reduce(function(a,p){ return a + (p.entry_krw||0); }, 0);
      var totalEval = openPos.reduce(function(a,p){ return a + (p.eval_krw||0); }, 0);
      var totalPnl = totalEval - totalInvested;
      var totalPct = totalInvested > 0 ? (totalPnl / totalInvested * 100) : 0;
      var isTotalPos = totalPnl >= 0;

      var posHtml = '<div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:12px 16px;margin-bottom:12px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
          '<span style="font-size:13px;color:var(--muted)">' + openPos.length + '개 포지션 합계</span>' +
          '<span style="font-family:var(--mono);font-size:20px;font-weight:700" class="' + (isTotalPos?'positive':'negative') + '">' + (isTotalPos?'+':'') + totalPct.toFixed(2) + '%</span>' +
        '</div>' +
        '<div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:13px">' +
          '<span style="color:var(--muted)">투입 ' + fmt(Math.round(totalInvested)) + '원</span>' +
          '<span style="color:var(--muted)">평가 ' + fmt(Math.round(totalEval)) + '원</span>' +
          '<span class="' + (isTotalPos?'positive':'negative') + '">' + (isTotalPos?'+':'') + fmt(Math.round(totalPnl)) + '원</span>' +
        '</div>' +
      '</div>';

      openPos.forEach(function(pos, idx) {
        var change = pos.pnl_pct || 0;
        var isPos = change >= 0;
        var entryTime = (pos.entry_time||'').replace('T',' ');
        var held = '';
        if (entryTime) {
          try {
            var diff = Date.now() - new Date(pos.entry_time).getTime();
            var hrs = Math.floor(diff / 3600000);
            var mins = Math.floor((diff % 3600000) / 60000);
            held = hrs > 0 ? hrs + '시간 ' + mins + '분' : mins + '분';
          } catch(e){}
        }

        posHtml += '<div style="background:linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.05));border:1px solid ' + (isPos ? 'rgba(0,255,136,0.15)' : 'rgba(255,68,68,0.15)') + ';border-radius:10px;padding:14px 16px;margin-bottom:8px">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
            '<span style="font-size:12px;color:var(--muted);background:rgba(255,255,255,0.06);padding:2px 8px;border-radius:4px">#' + (idx+1) + ' / ' + (held || entryTime) + ' 보유</span>' +
            '<span style="font-family:var(--mono);font-size:22px;font-weight:700" class="' + (isPos?'positive':'negative') + '">' + (isPos?'+':'') + change.toFixed(2) + '%</span>' +
          '</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">' +
            '<div><div style="font-size:11px;color:var(--muted);margin-bottom:2px">진입가</div><div style="font-family:var(--mono);font-size:14px">' + fmt(Math.round(pos.entry_price)) + '</div></div>' +
            '<div><div style="font-size:11px;color:var(--muted);margin-bottom:2px">현재가</div><div style="font-family:var(--mono);font-size:14px;color:var(--accent)">' + fmt(pos.current_price_krw) + '</div></div>' +
            '<div><div style="font-size:11px;color:var(--muted);margin-bottom:2px">손익</div><div style="font-family:var(--mono);font-size:14px" class="' + (isPos?'positive':'negative') + '">' + (isPos?'+':'') + fmt(pos.pnl_krw) + '원</div></div>' +
          '</div>' +
          '<div style="display:flex;justify-content:space-between;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);font-size:12px">' +
            '<span style="color:var(--muted)">투입 ' + fmt(Math.round(pos.entry_krw)) + '원 → 평가 ' + fmt(pos.eval_krw) + '원</span>' +
            '<span><span style="color:var(--red)">SL -3%</span> <span style="color:var(--muted)">/</span> <span style="color:var(--green)">TP +15%</span></span>' +
          '</div>' +
        '</div>';
      });

      posBody.innerHTML = posHtml;
      if (posStatus) posStatus.innerHTML = '<span class="action-pill buy">' + openPos.length + ' OPEN</span>';
    } else if (posBody && openPos.length === 0) {
      posBody.innerHTML = '<div class="position-empty">포지션 없음<br><span style="font-size:11px">다음 BUY 신호 대기 중</span></div>';
      if (posStatus) posStatus.innerHTML = '<span class="action-pill hold">대기</span>';
    }

    // CLOSED 히스토리 테이블
    var closedTbody = document.getElementById('closed-tbody');
    var closedCountEl = document.getElementById('closed-count');
    if (closedCountEl) closedCountEl.textContent = closedPos.length + '건';
    if (closedTbody) {
      if (closedPos.length === 0) {
        var emptyMsg = openPos.length > 0
          ? '현재 ' + openPos.length + '개 포지션 보유중 — 매도(청산) 완료 시 이력에 표시됩니다'
          : '아직 매매 이력이 없습니다';
        closedTbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px 20px;font-size:13px;line-height:1.6;">' + emptyMsg + '</td></tr>';
      } else {
        closedTbody.innerHTML = closedPos.map(function(p) {
          var isPos = (p.pnl || 0) >= 0;
          var cls = isPos ? 'positive' : 'negative';
          var sign = isPos ? '+' : '';
          var reason = p.exit_reason || '-';
          if (reason === 'stop_loss') reason = '🔴 손절';
          else if (reason === 'take_profit') reason = '🟢 익절';
          else if (reason === 'signal') reason = '📊 시그널';
          return '<tr>' +
            '<td>' + (p.entry_time || '-').replace('T', ' ').substring(0,16) + '</td>' +
            '<td>' + (p.exit_time || '-').replace('T', ' ').substring(0,16) + '</td>' +
            '<td style="font-family:var(--mono)">' + fmt(Math.round(p.entry_price)) + '</td>' +
            '<td style="font-family:var(--mono)">' + fmt(Math.round(p.exit_price)) + '</td>' +
            '<td style="font-family:var(--mono)">' + fmt(Math.round(p.entry_krw)) + '원</td>' +
            '<td style="font-family:var(--mono)" class="' + cls + '">' + sign + fmt(Math.round(p.pnl)) + '원</td>' +
            '<td style="font-family:var(--mono)" class="' + cls + '">' + sign + (p.pnl_pct || 0).toFixed(2) + '%</td>' +
            '<td>' + reason + '</td></tr>';
        }).join('');
      }
    }
  } catch(e) {
    console.error('btc portfolio error', e);
  }
}

async function loadComposite() {
  try {
    const res = await fetch('/api/btc/composite');
    if (!res.ok) return;
    const d = await res.json();
    if (d.error) return;
    const c = d.composite || {};
    const total = c.total || 0;
    const threshold = d.buy_threshold || 45;

    const el = document.getElementById('ind-comp');
    el.textContent = total + '/100';
    el.className = 'indicator-value ' + (total >= threshold ? 'positive' : total >= threshold - 10 ? '' : 'negative');

    const bar = document.getElementById('ind-comp-bar');
    bar.style.width = total + '%';
    bar.style.background = total >= threshold ? 'var(--green)' : total >= threshold - 10 ? 'var(--yellow)' : 'var(--red)';

    document.getElementById('ind-comp-detail').textContent =
      'F&G:' + (c.fg||0) + ' RSI:' + (c.rsi||0) + ' BB:' + (c.bb||0) + ' Vol:' + (c.vol||0) + ' Trend:' + (c.trend||0) +
      (total >= threshold ? ' → 매수 가능' : ' → 미달 (' + (threshold - total) + '점 부족)');

    // 일봉 RSI
    const rsiD = d.rsi_d || 50;
    const rsiDEl = document.getElementById('ind-rsi-d');
    rsiDEl.textContent = rsiD.toFixed(1);
    rsiDEl.className = 'indicator-value ' + (rsiD >= 70 ? 'negative' : rsiD <= 35 ? 'positive' : '');
    document.getElementById('ind-rsi-d-bar').style.width = rsiD + '%';
    document.getElementById('ind-rsi-d-bar').style.background = rsiD >= 70 ? 'var(--red)' : rsiD <= 35 ? 'var(--green)' : 'var(--accent)';
    document.getElementById('ind-rsi-d-label').textContent = rsiD >= 70 ? '과매수' : rsiD <= 35 ? '과매도' : '중립 (' + (d.trend||'') + ')';

    // 수익률
    const r7 = d.ret_7d || 0;
    const r30 = d.ret_30d || 0;
    const r7El = document.getElementById('ind-ret7');
    r7El.textContent = (r7 >= 0 ? '+' : '') + r7.toFixed(1) + '%';
    r7El.className = 'indicator-value ' + (r7 > 0 ? 'positive' : 'negative');
    const r30El = document.getElementById('ind-ret30');
    r30El.textContent = (r30 >= 0 ? '+' : '') + r30.toFixed(1) + '%';
    r30El.className = 'indicator-value ' + (r30 > 0 ? 'positive' : 'negative');
  } catch(e) { console.error('composite error', e); }
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

    // 포지션은 loadBtcPortfolio()에서 전체 렌더링 (충돌 방지)

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

async function refreshAll() {
  await loadAll();
  const ut = document.getElementById('update-time');
  if (ut) ut.textContent = '갱신 ' + new Date().toLocaleTimeString('ko-KR');
}
refreshAll();
setTimeout(loadNews, 1500);
setInterval(refreshAll, 10000);
setInterval(loadNews, 60000);

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
