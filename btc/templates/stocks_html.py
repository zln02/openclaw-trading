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
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px;transition:border-color 0.2s;}
  .card:hover{border-color:rgba(0,212,255,0.15);}
  .card-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);}
  .card-title{font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);}
  .card-body{padding:20px;}
  .stock-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
  .stock-card{position:relative;background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:border-color 0.2s;}
  .stock-card:hover{border-color:var(--accent);box-shadow:0 0 12px rgba(0,212,255,0.08);}
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
  .badge.live{background:rgba(0,230,118,0.1);color:#00e676;border:1px solid #00e67633;animation:pulse-live 2s infinite;}
  @keyframes pulse-live{0%,100%{opacity:1}50%{opacity:0.5}}
  .chart-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(15,20,34,0.8);z-index:10;transition:opacity 0.3s;}
  .chart-loading.hidden{opacity:0;pointer-events:none;}
  .spinner{width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;}
  @keyframes spin{to{transform:rotate(360deg)}}
  .stock-card{transition:border-color 0.2s,transform 0.15s,box-shadow 0.2s;}
  .stock-card:active{transform:scale(0.98);}
  .stock-price{transition:color 0.3s;}
  .price-flash-up{color:#00e676 !important;transition:color 0s !important;}
  .price-flash-down{color:#ff3d57 !important;transition:color 0s !important;}
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
  @media(max-width:1200px){.stock-grid{grid-template-columns:repeat(2,1fr);}.chart-section{grid-template-columns:1fr;}.portfolio-bar{grid-template-columns:repeat(3,1fr);}}
  @media(max-width:768px){main{padding:12px;}header{padding:12px 16px;}.stock-grid{grid-template-columns:1fr;}.portfolio-bar{grid-template-columns:repeat(2,1fr);}.port-value{font-size:16px;}}
  @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
  .interval-btn{background:transparent;border:1px solid var(--border);color:var(--muted);font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:4px;cursor:pointer;transition:all 0.2s;}
  .interval-btn:hover{color:var(--text);border-color:var(--accent);}
  .interval-btn.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.08);}
  .portfolio-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}
  .port-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px 20px;text-align:center;transition:border-color 0.2s,box-shadow 0.2s;}
  .port-card:hover{border-color:rgba(0,212,255,0.25);box-shadow:0 0 16px rgba(0,212,255,0.08);}
  .port-card.accent{border-color:rgba(0,212,255,0.3);background:linear-gradient(135deg,rgba(0,212,255,0.04),transparent);}
  .port-label{font-size:10px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;font-weight:600;}
  .port-value{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--text);}
  .port-value.kr-up{color:var(--red);}
  .port-value.kr-dn{color:#4488ff;}
  .port-sub{font-size:11px;color:var(--muted);margin-top:4px;font-family:var(--mono);}
  .port-sub.kr-up{color:#ff4444;}
  .port-sub.kr-dn{color:#4488ff;}
  .port-row2{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}
  .pnl-gauge{height:4px;background:var(--border);border-radius:2px;margin-top:4px;overflow:hidden;}
  .pnl-gauge-fill{height:100%;border-radius:2px;transition:width 0.5s ease;}
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
  .log-tab{background:transparent;border:1px solid var(--border);color:var(--muted);font-size:11px;padding:3px 10px;border-radius:4px;cursor:pointer;transition:all 0.2s;}
  .log-tab:hover{color:var(--accent);border-color:var(--accent);}
  .log-tab.active{color:#fff;border-color:var(--accent);background:var(--accent);}
  .market-summary-bar{display:flex;gap:24px;align-items:center;padding:12px 16px;margin-bottom:16px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;flex-wrap:wrap;}
  .market-summary-item{display:flex;align-items:center;gap:10px;font-family:var(--mono);}
  .ms-name{font-size:12px;color:var(--muted);font-weight:600;}
  .ms-price{font-size:15px;font-weight:700;}
  .ms-change{font-size:12px;font-weight:600;}
  .ms-change.up{color:var(--green);}
  .ms-change.dn{color:var(--red);}
  .view-btn{background:transparent;border:1px solid var(--border);color:var(--muted);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;}
  .view-btn:hover,.view-btn.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.08);}
  .tv-table{width:100%;border-collapse:collapse;font-size:13px;}
  .tv-table th{text-align:left;padding:8px;color:var(--muted);border-bottom:1px solid var(--border);font-size:11px;}
  .tv-table td{padding:8px;border-bottom:1px solid var(--border);}
  .tv-table tr:hover{background:rgba(255,255,255,0.03);}
  .tv-table .up{color:var(--red);}
  .tv-table .down{color:#089981;}
  .section-head{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
  .section-head::after{content:'';flex:1;height:1px;background:var(--border);}
  .market-summary-bar.second{background:var(--bg3);}
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
        <a href="/us" style="text-decoration:none"><div class="nav-tab">🇺🇸 US</div></a>
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
    <div class="section-head">시장 요약</div>
    <div id="market-summary-bar" class="market-summary-bar">
      <div class="market-summary-item"><span class="ms-name">KOSPI</span><span class="ms-price" id="ms-kospi-price">--</span><span class="ms-change" id="ms-kospi-change">--</span></div>
      <div class="market-summary-item"><span class="ms-name">KOSDAQ</span><span class="ms-price" id="ms-kosdaq-price">--</span><span class="ms-change" id="ms-kosdaq-change">--</span></div>
    </div>
    <div id="market-summary-world" class="market-summary-bar second" style="margin-top:8px;">
      <div class="market-summary-item"><span class="ms-name">S&P 500</span><span class="ms-price" id="ms-sp500-price">--</span><span class="ms-change" id="ms-sp500-change">--</span></div>
      <div class="market-summary-item"><span class="ms-name">나스닥100</span><span class="ms-price" id="ms-ndx-price">--</span><span class="ms-change" id="ms-ndx-change">--</span></div>
      <div class="market-summary-item"><span class="ms-name">USD/KRW</span><span class="ms-price" id="ms-usdkrw-price">--</span><span class="ms-change" id="ms-usdkrw-change">--</span></div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;margin-top:20px;">
      <h2 style="font-size:18px;margin:0;">📊 주식 모의투자 대시보드</h2>
      <div style="display:flex;align-items:center;gap:10px;">
        <span id="market-status" style="font-size:12px;color:var(--muted);"></span>
        <span style="font-family:var(--mono);font-size:12px;color:var(--muted)" id="update-time">마지막 업데이트: --</span>
      </div>
    </div>

    <div class="section-head" style="margin-top:24px;">내 포트폴리오</div>
    <div id="portfolio-summary" class="portfolio-bar">
      <div class="port-card accent">
        <div class="port-label">추정 총 자산</div>
        <div class="port-value" id="total-asset">--</div>
      </div>
      <div class="port-card">
        <div class="port-label">총 매입금</div>
        <div class="port-value" id="total-purchase">--</div>
        <div class="port-sub" id="total-purchase-sub"></div>
      </div>
      <div class="port-card">
        <div class="port-label">총 평가금</div>
        <div class="port-value" id="total-eval">--</div>
        <div class="port-sub" id="total-eval-sub"></div>
      </div>
      <div class="port-card">
        <div class="port-label">누적 수익</div>
        <div class="port-value" id="cum-pnl">--</div>
        <div class="port-sub" id="cum-pnl-sub"></div>
      </div>
    </div>
    <div class="port-row2">
      <div class="port-card">
        <div class="port-label">예수금 (현금)</div>
        <div class="port-value" id="deposit">--</div>
      </div>
      <div class="port-card">
        <div class="port-label">오늘 수익</div>
        <div class="port-value" id="today-pnl">--</div>
        <div class="port-sub" id="today-pnl-sub"></div>
      </div>
      <div class="port-card">
        <div class="port-label">보유종목 수</div>
        <div class="port-value" id="pos-count-big">0</div>
        <div class="port-sub">/ 5 종목</div>
      </div>
      <div class="port-card">
        <div class="port-label">현금 비중</div>
        <div class="port-value" id="cash-ratio">--</div>
      </div>
    </div>

    <div class="section-head" style="margin-top:24px;">보유 종목</div>
    <div class="holdings-section">
      <h3>🏦 보유종목 (<span id="pos-count">0</span>/<span id="max-pos">5</span>)</h3>
      <table class="holdings-table">
        <thead><tr><th>종목</th><th>수량</th><th>평균단가</th><th>현재가</th><th>투입금</th><th>평가액</th><th>수익률</th><th>비중</th></tr></thead>
        <tbody id="holdings-body"></tbody>
      </table>
    </div>

    <div class="section-head" style="margin-top:24px;">종목 차트 · 일별 수익</div>
    <div style="display:grid;grid-template-columns:320px 1fr;gap:16px;margin-bottom:16px;">
      <div class="daily-pnl-section">
        <h3>📈 일별 수익 추이 (7일)</h3>
        <div id="daily-pnl-lw" style="width:100%;height:180px;"></div>
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
        <div style="position:relative">
          <div id="chart-loading" class="chart-loading hidden"><div class="spinner"></div></div>
          <div id="stock-candle-chart" style="width:100%;height:400px"></div>
        </div>
        <div id="stock-volume-chart" style="width:100%;height:100px"></div>
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

    <div class="section-head" style="margin-top:24px;">오늘 전략</div>
    <div id="strategy-bar" class="strategy-bar">
      <span>🎯 오늘 전략:</span>
      <span id="strat-outlook">--</span>
      <span id="strat-risk">--</span>
      <span id="strat-picks">--</span>
    </div>

    <div class="section-head" style="margin-top:24px;">종목 스캐너</div>
    <div class="card">
      <div class="card-header">
        <div class="scanner-header">
          <h3 class="card-title">📋 TOP50 · 등락률/거래량/RSI</h3>
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
            <div class="scanner-views" style="display:flex;gap:4px;">
              <button type="button" class="view-btn active" data-view="grid" onclick="setScannerView('grid')">그리드</button>
              <button type="button" class="view-btn" data-view="heatmap" onclick="setScannerView('heatmap')">히트맵</button>
              <button type="button" class="view-btn" data-view="table" onclick="setScannerView('table')">테이블</button>
            </div>
          </div>
        </div>
      </div>
      <div style="padding:16px;">
        <div class="stock-grid" id="stock-grid">
          <div style="color:var(--muted);padding:20px;font-size:13px">로딩 중...</div>
        </div>
        <div id="heatmap-container" style="display:none;flex-wrap:wrap;gap:6px;"></div>
        <div id="stock-table-wrap" style="display:none;overflow:auto;"><table class="tv-table" id="stock-table"><thead><tr><th>종목</th><th>현재가</th><th>등락률</th><th>RSI</th><th>거래량</th></tr></thead><tbody></tbody></table></div>
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
        <div class="card-header" style="flex-wrap:wrap;gap:8px">
          <span class="card-title">📋 실시간 로그</span>
          <div style="display:flex;gap:4px;align-items:center">
            <button class="log-tab active" onclick="switchLogSource('all',this)">전체</button>
            <button class="log-tab" onclick="switchLogSource('trading',this)">매매</button>
            <button class="log-tab" onclick="switchLogSource('check',this)">체크</button>
            <button class="log-tab" onclick="switchLogSource('premarket',this)">프리마켓</button>
            <span style="font-family:var(--mono);font-size:11px;color:var(--muted);margin-left:8px" id="stock-log-time"></span>
          </div>
        </div>
        <div class="card-body" style="height:350px;overflow:auto">
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
    width: c.clientWidth, height: 400,
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
    width: vc.clientWidth, height: 100,
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

async function loadMarketSummary() {
  try {
    const res = await fetch('/api/stocks/market-summary');
    const data = await res.json();
    var map = [
      ['kospi', 'ms-kospi', true],
      ['kosdaq', 'ms-kosdaq', true],
      ['sp500', 'ms-sp500', false],
      ['nasdaq', 'ms-ndx', false],
      ['usdkrw', 'ms-usdkrw', true]
    ];
    map.forEach(function(m) {
      var key = m[0], prefix = m[1], isKr = m[2];
      var d = data[key];
      if (!d) return;
      var priceEl = document.getElementById(prefix + '-price');
      var changeEl = document.getElementById(prefix + '-change');
      if (priceEl) priceEl.textContent = isKr ? (d.price || 0).toLocaleString('ko-KR') : (d.price || 0).toLocaleString('en-US', {maximumFractionDigits: 2});
      if (changeEl) {
        var sign = (d.change_pct || 0) >= 0 ? '+' : '';
        changeEl.textContent = sign + (d.change_pct || 0) + '%';
        changeEl.className = 'ms-change ' + ((d.change_pct || 0) >= 0 ? 'up' : 'dn');
      }
    });
  } catch(e) { console.error('market-summary', e); }
}

function setScannerView(view) {
  document.querySelectorAll('.view-btn').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-view') === view); });
  document.getElementById('stock-grid').style.display = view === 'grid' ? 'grid' : 'none';
  document.getElementById('heatmap-container').style.display = view === 'heatmap' ? 'flex' : 'none';
  document.getElementById('stock-table-wrap').style.display = view === 'table' ? 'block' : 'none';
  if (view === 'heatmap' && stocksData.length) renderHeatmap(stocksData);
  if (view === 'table' && stocksData.length) renderStockTable(stocksData);
}
function renderHeatmap(stocks) {
  var c = document.getElementById('heatmap-container');
  c.innerHTML = '';
  (stocks || []).forEach(function(s) {
    var change = parseFloat(s.change) || 0;
    var size = Math.max(60, Math.min(140, 80 + Math.abs(change) * 8));
    var bg = change >= 3 ? '#f23645' : change >= 1 ? '#f2364588' : change >= 0 ? '#f236451a' : change >= -1 ? '#0899811a' : change >= -3 ? '#08998188' : '#089981';
    var el = document.createElement('div');
    el.style.cssText = 'width:' + size + 'px;height:' + (size*0.7) + 'px;background:' + bg + ';border-radius:4px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;font-size:11px;';
    el.innerHTML = '<div style="font-weight:bold">' + (s.name || s.code) + '</div><div>' + (change >= 0 ? '+' : '') + change.toFixed(1) + '%</div>';
    el.onclick = function(){ selectStock(s.code, s.name || ''); };
    c.appendChild(el);
  });
}
function renderStockTable(stocks) {
  var tbody = document.querySelector('#stock-table tbody');
  if (!tbody) return;
  var sorted = (stocks || []).slice().sort(function(a,b){ return (parseFloat(b.change)||0) - (parseFloat(a.change)||0); });
  tbody.innerHTML = sorted.map(function(s) {
    var change = parseFloat(s.change) || 0;
    var cls = change >= 0 ? 'up' : 'down';
    var rsi = parseFloat(s.rsi) || 50;
    return '<tr onclick="selectStock(\'' + s.code + '\',\'' + (s.name||'').replace(/'/g, "\\'") + '\')" style="cursor:pointer"><td><b>' + (s.name||s.code) + '</b><br><small style="color:var(--muted)">' + s.code + '</small></td><td>' + (s.price||0).toLocaleString('ko-KR') + '</td><td class="' + cls + '">' + (change >= 0 ? '+' : '') + change.toFixed(2) + '%</td><td>' + rsi.toFixed(0) + '</td><td>' + (s.volume ? (s.volume/1e6).toFixed(1) + 'M' : '--') + '</td></tr>';
  }).join('');
}

async function loadPortfolio() {
  try {
    const res = await fetch('/api/stocks/portfolio');
    const data = await res.json();
    if (data.error && !data.positions) return;

    var positions = data.positions || [];
    var deposit = data.deposit || 0;
    var totalEval = data.total_evaluation || 0;
    var estimated = data.estimated_asset || 0;
    var totalPurchase = data.total_purchase || 0;
    var cumPnl = data.cumulative_pnl || 0;
    var cumPct = data.cumulative_pnl_pct || 0;
    var todayPnl = data.today_pnl || 0;
    var todayPct = data.today_pnl_pct || 0;

    if (!estimated) estimated = deposit + totalEval;
    if (!totalPurchase && positions.length) {
      totalPurchase = positions.reduce(function(s,p){ return s + (p.avg_entry||0) * (p.quantity||0); }, 0);
    }
    if (!totalEval && positions.length) {
      totalEval = positions.reduce(function(s,p){ return s + (p.evaluation||0); }, 0);
    }
    var holdingPnl = totalEval - totalPurchase;
    var holdingPnlPct = totalPurchase > 0 ? (holdingPnl / totalPurchase * 100) : 0;

    // 1행: 추정자산, 총매입, 총평가, 누적수익
    document.getElementById('total-asset').textContent = estimated.toLocaleString('ko-KR') + '원';

    document.getElementById('total-purchase').textContent = totalPurchase.toLocaleString('ko-KR') + '원';
    var tpSub = document.getElementById('total-purchase-sub');
    if (tpSub) tpSub.textContent = positions.length + '종목 보유중';

    document.getElementById('total-eval').textContent = totalEval.toLocaleString('ko-KR') + '원';
    var teSub = document.getElementById('total-eval-sub');
    if (teSub) {
      var sign = holdingPnl >= 0 ? '+' : '';
      teSub.textContent = sign + holdingPnl.toLocaleString('ko-KR') + '원 (' + sign + holdingPnlPct.toFixed(2) + '%)';
      teSub.className = 'port-sub ' + (holdingPnl >= 0 ? 'kr-up' : 'kr-dn');
    }

    var cumEl = document.getElementById('cum-pnl');
    cumEl.textContent = (cumPnl >= 0 ? '+' : '') + cumPnl.toLocaleString('ko-KR') + '원';
    cumEl.className = 'port-value ' + (cumPnl >= 0 ? 'kr-up' : 'kr-dn');
    var cumSub = document.getElementById('cum-pnl-sub');
    if (cumSub) {
      cumSub.textContent = (cumPct >= 0 ? '+' : '') + cumPct + '%';
      cumSub.className = 'port-sub ' + (cumPct >= 0 ? 'kr-up' : 'kr-dn');
    }

    // 2행: 예수금, 오늘수익, 보유종목 수, 현금비중
    document.getElementById('deposit').textContent = deposit.toLocaleString('ko-KR') + '원';

    var todayEl = document.getElementById('today-pnl');
    todayEl.textContent = (todayPnl >= 0 ? '+' : '') + todayPnl.toLocaleString('ko-KR') + '원';
    todayEl.className = 'port-value ' + (todayPnl >= 0 ? 'kr-up' : 'kr-dn');
    var todaySub = document.getElementById('today-pnl-sub');
    if (todaySub) {
      todaySub.textContent = (todayPct >= 0 ? '+' : '') + todayPct + '%';
      todaySub.className = 'port-sub ' + (todayPnl >= 0 ? 'kr-up' : 'kr-dn');
    }

    document.getElementById('pos-count-big').textContent = positions.length;
    var cashRatio = estimated > 0 ? (deposit / estimated * 100).toFixed(1) : '--';
    document.getElementById('cash-ratio').textContent = cashRatio + '%';

    holdingCodes = positions.map(function(p){
      var c = p.code || '';
      return c.replace(/^A/, '');
    });
    renderHoldings(positions, data.max_positions || 5);

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
  var maxPosEl = document.getElementById('max-pos');
  if (maxPosEl) maxPosEl.textContent = maxPos || 5;
  var tbody = document.getElementById('holdings-body');
  if (!positions.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:20px;">보유종목 없음</td></tr>';
    return;
  }

  var totalCost = positions.reduce(function(s,p){ return s+((p.avg_entry||0)*(p.quantity||0));},0);
  var totalEval = positions.reduce(function(s,p){ return s+(p.evaluation||0);},0);
  var totalPnl = positions.reduce(function(s,p){ return s+(p.pnl_amount||0);},0);

  tbody.innerHTML = positions.map(function(p) {
    var pnlClass = p.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg';
    var pnlSign = p.pnl_pct >= 0 ? '+' : '';
    var liveTag = p.is_live ? '' : ' <span style="color:#ff8800;font-size:9px;">(종가)</span>';
    var cost = (p.avg_entry||0) * (p.quantity||0);
    var weight = totalEval > 0 ? ((p.evaluation||0) / totalEval * 100).toFixed(1) : '0';
    var splitBadge = (p.split_count||1) > 1 ? '<span style="color:#ffa500;font-size:9px;margin-left:4px;">' + (p.split_count||1) + '차</span>' : '';
    return '<tr onclick="selectStock(\\'' + p.code + '\\',\\'' + (p.name||'').replace(/'/g,"\\\\'") + '\\')" style="cursor:pointer">' +
      '<td>' + (p.name||p.code) + splitBadge + '</td>' +
      '<td>' + (p.quantity||0).toLocaleString('ko-KR') + '주</td>' +
      '<td>' + (p.avg_entry||0).toLocaleString('ko-KR') + '</td>' +
      '<td>' + (p.current_price||0).toLocaleString('ko-KR') + liveTag + '</td>' +
      '<td>' + cost.toLocaleString('ko-KR') + '</td>' +
      '<td>' + (p.evaluation||0).toLocaleString('ko-KR') + '</td>' +
      '<td class="' + pnlClass + '">' + pnlSign + (p.pnl_pct||0) + '%<br><small>(' + pnlSign + (p.pnl_amount||0).toLocaleString('ko-KR') + '원)</small>' +
      '<div class="pnl-gauge"><div class="pnl-gauge-fill" style="width:' + Math.min(Math.abs(p.pnl_pct||0)*5,100) + '%;background:' + (p.pnl_pct>=0?'var(--red)':'#4488ff') + '"></div></div></td>' +
      '<td>' + weight + '%</td></tr>';
  }).join('');

  var totalPnlPct = totalCost > 0 ? (totalPnl / totalCost * 100).toFixed(2) : 0;
  var pnlClass = totalPnl >= 0 ? 'pnl-pos' : 'pnl-neg';
  var sign = totalPnl >= 0 ? '+' : '';
  tbody.innerHTML += '<tr style="border-top:2px solid #ffffff20;font-weight:bold;background:rgba(255,255,255,0.02);">' +
    '<td>합계</td>' +
    '<td>' + positions.length + '종목</td>' +
    '<td></td><td></td>' +
    '<td>' + totalCost.toLocaleString('ko-KR') + '</td>' +
    '<td>' + totalEval.toLocaleString('ko-KR') + '</td>' +
    '<td class="' + pnlClass + '">' + sign + totalPnlPct + '%<br><small>(' + sign + totalPnl.toLocaleString('ko-KR') + '원)</small></td>' +
    '<td>100%</td></tr>';
}

let dailyPnlChart = null, dailyPnlSeries = null;

function initDailyPnlChart() {
  if (dailyPnlChart || typeof LightweightCharts === 'undefined') return;
  var el = document.getElementById('daily-pnl-lw');
  if (!el) return;
  dailyPnlChart = LightweightCharts.createChart(el, {
    width: el.clientWidth, height: 180,
    layout: { background: { color: '#0f1422' }, textColor: '#4a5068' },
    grid: { vertLines: { color: '#1e2537' }, horzLines: { color: '#1e2537' } },
    timeScale: { borderColor: '#1e2537', timeVisible: false },
    rightPriceScale: { borderColor: '#1e2537' },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });
  dailyPnlSeries = dailyPnlChart.addBaselineSeries({
    baseValue: { type: 'price', price: 0 },
    topLineColor: 'rgba(255,68,68,0.8)',
    topFillColor1: 'rgba(255,68,68,0.2)',
    topFillColor2: 'rgba(255,68,68,0.02)',
    bottomLineColor: 'rgba(68,136,255,0.8)',
    bottomFillColor1: 'rgba(68,136,255,0.02)',
    bottomFillColor2: 'rgba(68,136,255,0.2)',
    lineWidth: 2,
  });
}

async function loadDailyPnL() {
  try {
    var res = await fetch('/api/stocks/daily-pnl?days=7');
    var data = await res.json();
    if (!data.daily || data.daily.length === 0) return;
    initDailyPnlChart();
    if (!dailyPnlSeries) return;
    var chartData = data.daily.map(function(p) {
      var d = String(p.date || '');
      var yr = d.slice(0,4), mo = d.slice(4,6), dy = d.slice(6,8);
      return { time: yr + '-' + mo + '-' + dy, value: p.total_pnl || 0 };
    });
    dailyPnlSeries.setData(chartData);
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

var prevPrices = {};

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

    var existingCards = grid.querySelectorAll('.stock-card');
    var isFirstLoad = existingCards.length === 0;

    if (isFirstLoad) {
      grid.innerHTML = stocks.map(function(s) {
        return buildStockCard(s);
      }).join('');
      document.querySelectorAll('.filter-btn').forEach(function(btn){
        btn.onclick = function(){ filterStocks(btn.getAttribute('data-filter')); };
      });
      queueIndicators(stocks);
    } else {
      stocks.forEach(function(s) {
        var card = grid.querySelector('[data-code="' + s.code + '"]');
        if (!card) return;
        var priceEl = card.querySelector('.stock-price');
        if (priceEl) {
          var oldPrice = prevPrices[s.code] || 0;
          var newPrice = Math.round(s.price);
          if (oldPrice && newPrice !== oldPrice) {
            priceEl.classList.remove('price-flash-up','price-flash-down');
            void priceEl.offsetWidth;
            priceEl.classList.add(newPrice > oldPrice ? 'price-flash-up' : 'price-flash-down');
            setTimeout(function(){ priceEl.classList.remove('price-flash-up','price-flash-down'); }, 1500);
          }
          priceEl.textContent = fmt(newPrice) + '원';
        }
        var changeEl = card.querySelector('.stock-change');
        if (changeEl) {
          var isP = s.change >= 0;
          changeEl.textContent = (isP ? '▲' : '▼') + ' ' + Math.abs(s.change).toFixed(2) + '%';
          changeEl.className = 'stock-change ' + (isP ? 'positive' : 'negative');
        }
        updateCardIndicators(card, s);
        card.setAttribute('data-change', s.change || 0);
        var isHolding = holdingCodes.indexOf(s.code) >= 0;
        card.classList.toggle('holding', isHolding);
        card.setAttribute('data-holding', isHolding);
      });
    }

    stocks.forEach(function(s) {
      prevPrices[s.code] = Math.round(s.price);
    });

    if (selectedCode) {
      var selCard = grid.querySelector('[data-code="' + selectedCode + '"]');
      if (selCard) {
        grid.querySelectorAll('.stock-card').forEach(function(c){ c.classList.remove('selected'); });
        selCard.classList.add('selected');
      }
    }
  } catch(e) { console.error('stocks error', e); }
}

function buildStockCard(s) {
  var isPos = s.change >= 0;
  var selected = selectedCode === s.code ? ' selected' : '';
  var isHolding = holdingCodes.indexOf(s.code) >= 0;
  var liveTag = s.is_live ? '<span class="badge live">LIVE</span>' : '';
  return '<div class="stock-card' + (isHolding ? ' holding' : '') + selected + '" data-code="' + s.code + '" onclick="selectStock(\\'' + s.code + '\\',\\'' + (s.name || '').replace(/'/g, "\\\\'") + '\\')" data-rsi="50" data-vol="1" data-holding="' + isHolding + '" data-change="' + (s.change||0) + '">' +
    '<div style="display:flex;justify-content:space-between;align-items:center;">' +
      '<div class="industry-badge">' + (s.industry || '') + '</div>' +
      liveTag +
    '</div>' +
    '<div class="stock-name">' + s.name + '</div>' +
    '<div class="stock-price">' + fmt(Math.round(s.price)) + '원</div>' +
    '<div class="stock-change ' + (isPos ? 'positive' : 'negative') + '">' +
      (isPos ? '▲' : '▼') + ' ' + Math.abs(s.change).toFixed(2) + '%' +
    '</div>' +
    '<div class="indicator-badges">' +
      '<span class="badge rsi">RSI --</span>' +
      '<span class="badge macd">MACD --</span>' +
      '<span class="badge bb">BB --</span>' +
      '<span class="badge vol">Vol --</span>' +
    '</div></div>';
}

function updateCardIndicators(card, data) {
  var badges = card.querySelectorAll('.indicator-badges .badge');
  if (badges.length >= 4) {
    if (data.rsi != null) {
      badges[0].textContent = 'RSI ' + data.rsi;
      badges[0].className = 'badge rsi';
      if (data.rsi <= 30) badges[0].classList.add('oversold');
      else if (data.rsi <= 45) badges[0].classList.add('low');
      else if (data.rsi >= 70) badges[0].classList.add('overbought');
    }
    if (data.macd != null) badges[1].textContent = 'MACD ' + (data.macd > 0 ? '+' : '') + data.macd;
    if (data.bb_pos != null) badges[2].textContent = 'BB ' + data.bb_pos + '%';
    if (data.vol_ratio != null) badges[3].textContent = 'Vol ' + data.vol_ratio + 'x';
  }
  card.setAttribute('data-rsi', data.rsi != null ? data.rsi : 50);
  card.setAttribute('data-vol', data.vol_ratio != null ? data.vol_ratio : 1);
}

var indicatorQueue = [];
var indicatorLoading = false;

async function loadIndicatorsBatch() {
  if (indicatorLoading || indicatorQueue.length === 0) return;
  indicatorLoading = true;
  var batch = indicatorQueue.splice(0, 5);
  await Promise.allSettled(batch.map(function(code) {
    return fetch('/api/stocks/indicators/' + code)
      .then(function(r){ return r.json(); })
      .then(function(data) {
        if (data.error) return;
        var grid = document.getElementById('stock-grid');
        var card = grid ? grid.querySelector('[data-code="' + code + '"]') : null;
        if (card) updateCardIndicators(card, data);
      })
      .catch(function(){});
  }));
  indicatorLoading = false;
  if (indicatorQueue.length > 0) {
    setTimeout(loadIndicatorsBatch, 200);
  } else {
    var activeFilter = document.querySelector('.scanner-filters .filter-btn.active');
    if (activeFilter) {
      var f = activeFilter.getAttribute('data-filter');
      if (f && f !== 'all') filterStocks(f);
    }
  }
}

function queueIndicators(stocks) {
  indicatorQueue = stocks.map(function(s){ return s.code; });
  loadIndicatorsBatch();
}

function setStockInterval(interval) {
  currentStockInterval = interval;
  document.querySelectorAll('.interval-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-interval') === interval);
  });
  if (selectedCode) loadStockChart(selectedCode, false);
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

var chartLoadingEl = null;
function showChartLoading(show) {
  if (!chartLoadingEl) chartLoadingEl = document.getElementById('chart-loading');
  if (chartLoadingEl) chartLoadingEl.classList.toggle('hidden', !show);
}

async function loadStockChart(code, silent) {
  if (!code || !stockSeries || !stockVolSeries) return;
  if (!silent) showChartLoading(true);
  try {
    const res = await fetch('/api/stocks/chart/' + code + '?interval=' + encodeURIComponent(currentStockInterval));
    const raw = await res.json();
    var candles = raw.candles && raw.candles.length ? raw.candles : (Array.isArray(raw) ? raw : []);
    if (!candles.length) { showChartLoading(false); return; }
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

    var livePrice = null;
    try {
      var priceRes = await fetch('/api/stocks/price/' + code);
      var priceData = await priceRes.json();
      if (priceData.is_live && priceData.price > 0) livePrice = priceData.price;
    } catch(e) {}

    var displayPrice = livePrice || Math.round(last.close);
    var displayChg = livePrice && prev ? ((livePrice - prev.close) / prev.close * 100).toFixed(2) : chg;
    var dispPos = displayChg >= 0;
    var liveTag = livePrice ? '<span style="color:#00e676;font-size:10px;margin-left:6px">● LIVE</span>' : '';

    document.getElementById('stock-detail').innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
      '<div><div class="stat-label">현재가' + liveTag + '</div><div class="stat-value neutral" style="font-size:24px">' + fmt(displayPrice) + '원</div></div>' +
      '<div><div class="stat-label">전일대비</div><div class="stat-value ' + (dispPos?'positive':'negative') + '" style="font-size:24px">' + (dispPos?'+':'') + displayChg + '%</div></div>' +
      '<div><div class="stat-label">고가</div><div class="stat-value" style="font-size:16px;color:var(--green)">' + fmt(Math.round(last.high)) + '원</div></div>' +
      '<div><div class="stat-label">저가</div><div class="stat-value" style="font-size:16px;color:var(--red)">' + fmt(Math.round(last.low)) + '원</div></div>' +
      '<div><div class="stat-label">거래량</div><div class="stat-value" style="font-size:16px">' + fmt(last.volume) + '</div></div>' +
      '<div><div class="stat-label">종목코드</div><div class="stat-value" style="font-size:16px;color:var(--muted)">' + code + '</div></div>' +
      '</div>';
  } catch(e) { console.error('chart error', e); }
  showChartLoading(false);
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
  var grid = document.getElementById('stock-grid');
  var card = grid ? grid.querySelector('[data-code="' + code + '"]') : null;
  if (card) card.classList.add('selected');

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

loadMarketSummary();
loadPortfolio().then(function(){ loadStocks(); });
loadStrategy();
loadDailyPnL();

setInterval(loadPortfolio, 15000);
setInterval(loadMarketSummary, 60000);
setInterval(loadStocks, 10000);
setInterval(loadDailyPnL, 120000);

setInterval(function(){
  if (selectedCode) loadStockChart(selectedCode, true);
}, 15000);

setInterval(function(){
  if (stocksData.length) queueIndicators(stocksData);
}, 60000);

var currentLogSource = 'all';

function switchLogSource(source, btn) {
  currentLogSource = source;
  document.querySelectorAll('.log-tab').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  loadStockLogs();
}

async function loadStockLogs() {
  try {
    const res = await fetch('/api/stocks/logs?source=' + currentLogSource);
    const d = await res.json();
    const el = document.getElementById('stock-log-viewer');
    const timeEl = document.getElementById('stock-log-time');
    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('ko-KR');

    const escape = s => String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;');

    const cls = line => {
      if (/매수|BUY|💰/.test(line)) return 'color:var(--green);font-weight:600';
      if (/매도|SELL|손절/.test(line)) return 'color:var(--red);font-weight:600';
      if (/ERROR|실패|❌/.test(line)) return 'color:var(--red)';
      if (/WARN|⚠️/.test(line)) return 'color:#f0ad4e';
      if (/사이클 시작|═/.test(line)) return 'color:var(--accent);font-weight:600';
      if (/HOLD|SKIP|장 외/.test(line)) return 'color:var(--muted);font-size:11px';
      if (/익절|✅/.test(line)) return 'color:var(--green)';
      if (/전략|브리핑/.test(line)) return 'color:#9b59b6';
      return 'color:var(--text)';
    };

    var lines = d.lines || [];
    if (currentLogSource === 'all') {
      lines = lines.filter(function(l) { return !/장 외 시간/.test(l) && !/초기화 완료/.test(l); });
    }

    el.innerHTML = lines
      .map(l => '<span style="' + cls(l) + '">' + escape(l) + '</span>')
      .join('\\n') || '(비어 있음)';
    el.scrollTop = el.scrollHeight;
  } catch(e) {
    var v = document.getElementById('stock-log-viewer');
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
setInterval(loadStockLogs, 15000);
setInterval(loadStockTradeSummary, 15000);
</script>
</body>
</html>"""
