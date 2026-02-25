"""US 모멘텀 자동매매 대시보드 HTML (SPA) v2 — 실시간 차트 + 한국어 병기 + 환율"""

US_DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OpenClaw US Momentum</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
  :root{--bg:#0a0e17;--bg2:#0f1422;--bg3:#141928;--border:#1e2537;--accent:#00d4ff;--green:#00e676;--red:#ff3d57;--yellow:#ffd600;--text:#e8eaf0;--muted:#4a5068;--font:'Syne',sans-serif;--mono:'DM Mono',monospace;}
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:var(--font);min-height:100vh;overflow-x:hidden;}
  body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}
  .wrapper{position:relative;z-index:1;}
  header{display:flex;align-items:center;justify-content:space-between;padding:16px 28px;border-bottom:1px solid var(--border);background:rgba(10,14,23,0.9);backdrop-filter:blur(10px);position:sticky;top:0;z-index:100;}
  .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:16px;letter-spacing:0.04em;}
  .logo-icon{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--accent),#7c4dff);display:flex;align-items:center;justify-content:center;font-size:14px;}
  .nav-tab{padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;color:var(--muted);transition:all 0.2s;cursor:pointer;text-decoration:none;}
  .nav-tab:hover{color:var(--text);background:rgba(255,255,255,0.05);}
  .nav-tab.active{color:var(--accent);background:rgba(0,212,255,0.1);}
  .live-badge{display:flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--green);background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.2);padding:4px 10px;border-radius:20px;}
  .live-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
  @keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.3;}}
  main{max-width:1400px;margin:0 auto;padding:24px;}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;}
  @media(max-width:900px){.grid-2{grid-template-columns:1fr;}.pos-grid{grid-template-columns:1fr 1fr;}}
  @media(max-width:600px){.pos-grid{grid-template-columns:1fr;}.idx-row{grid-template-columns:1fr 1fr;}main{padding:12px;}header{padding:12px 16px;}}
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;overflow:hidden;transition:border-color 0.2s;}
  .card:hover{border-color:rgba(0,212,255,0.15);}
  .card-title{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
  .card-title span{color:var(--accent);}
  .stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px;}
  .stat-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;text-align:center;transition:border-color 0.2s,box-shadow 0.2s;}
  .stat-card:hover{border-color:rgba(0,212,255,0.25);box-shadow:0 0 12px rgba(0,212,255,0.08);}
  .stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;}
  .stat-val{font-size:22px;font-weight:700;font-family:var(--mono);}
  .idx-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px;}
  .idx-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;}
  .idx-name{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;}
  .idx-price{font-size:18px;font-weight:700;font-family:var(--mono);}
  .idx-chg{font-size:13px;font-family:var(--mono);margin-top:2px;}
  .pos-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:16px;}
  .pos-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;cursor:pointer;transition:all .2s;}
  .pos-card:hover,.pos-card.active{border-color:var(--accent);background:rgba(0,212,255,0.04);box-shadow:0 0 12px rgba(0,212,255,0.08);}
  .pos-sym{font-size:16px;font-weight:700;font-family:var(--mono);}
  .pos-detail{font-size:11px;color:var(--muted);font-family:var(--mono);margin-top:2px;}
  .pos-cur{font-size:14px;font-weight:600;font-family:var(--mono);margin-top:4px;}
  .pos-pnl{font-size:18px;font-weight:800;font-family:var(--mono);}
  .pos-score{font-size:10px;color:var(--accent);font-family:var(--mono);opacity:0.7;}
  .portfolio-bar{display:flex;gap:24px;align-items:center;margin-bottom:14px;padding:12px 16px;background:var(--bg3);border:1px solid var(--border);border-radius:10px;font-family:var(--mono);font-size:13px;flex-wrap:wrap;}
  .portfolio-bar .item{display:flex;flex-direction:column;gap:2px;}
  .portfolio-bar .label{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:0.06em;}
  .portfolio-bar .val{font-weight:700;font-size:16px;}
  .krw-sub{display:block;font-size:12px;color:var(--yellow);font-weight:500;margin-top:2px;opacity:0.85;}
  .pos-krw{font-size:11px;color:var(--yellow);font-family:var(--mono);opacity:0.8;}
  .chart-container{width:100%;height:400px;border-radius:8px;overflow:hidden;}
  .chart-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
  .chart-tabs{display:flex;gap:4px;}
  .chart-tab{padding:4px 12px;border-radius:6px;font-size:11px;font-weight:600;color:var(--muted);cursor:pointer;background:transparent;border:1px solid var(--border);font-family:var(--mono);}
  .chart-tab.active{color:var(--accent);border-color:var(--accent);background:rgba(0,212,255,0.1);}
  .chart-live-dot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;animation:pulse 1.5s infinite;margin-right:4px;}
  .section-title{font-size:15px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
  .section-title span{color:var(--accent);}
  .filter-bar{display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap;}
  .filter-bar input,.filter-bar select{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:6px 12px;color:var(--text);font-family:var(--mono);font-size:12px;outline:none;}
  .filter-bar input:focus,.filter-bar select:focus{border-color:var(--accent);}
  .filter-bar input{width:180px;}
  .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;font-family:var(--mono);margin-left:4px;}
  .badge-a{background:rgba(0,230,118,0.15);color:var(--green);}
  .badge-b{background:rgba(0,212,255,0.15);color:var(--accent);}
  .badge-c{background:rgba(255,214,0,0.15);color:var(--yellow);}
  .badge-d{background:rgba(255,61,87,0.15);color:var(--red);}
  table{width:100%;border-collapse:collapse;font-size:13px;background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;}
  thead tr{background:var(--bg3);}
  th,td{padding:10px 14px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap;}
  th:first-child,td:first-child{text-align:center;width:40px;}
  th:nth-child(2),td:nth-child(2){text-align:left;}
  th{font-weight:600;color:var(--muted);text-transform:none;letter-spacing:0.04em;font-size:11px;cursor:pointer;user-select:none;transition:color .2s;}
  th:hover{color:var(--accent);}
  tbody tr{transition:background .15s;}
  tbody tr:hover{background:rgba(0,212,255,0.04);}
  tr.holding-row{background:rgba(0,212,255,0.06);}
  tr.holding-row td:first-child{position:relative;}
  tr.holding-row td:first-child::before{content:'';position:absolute;left:0;top:4px;bottom:4px;width:3px;background:var(--accent);border-radius:2px;}
  .log-viewer{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-family:var(--mono);font-size:11px;line-height:1.7;max-height:350px;overflow-y:auto;color:var(--muted);white-space:pre-wrap;word-break:break-all;}
  .log-viewer .log-trade{color:var(--green);}
  .log-viewer .log-warn{color:var(--yellow);}
  .log-viewer .log-error{color:var(--red);}
  .log-viewer .log-info{color:var(--text);}
  .trade-list{max-height:300px;overflow-y:auto;}
  .trade-item{display:flex;align-items:center;gap:12px;padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px;font-family:var(--mono);}
  .trade-item:last-child{border-bottom:none;}
  .trade-buy{color:var(--green);}
  .trade-sell{color:var(--red);}
  .trade-sym{font-weight:700;width:50px;}
  .trade-time{color:var(--muted);font-size:10px;margin-left:auto;}
  .ko{color:var(--muted);font-size:10px;font-weight:400;}
</style>
</head>
<body>
<div class="wrapper">
  <header>
    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
      <div class="logo"><div class="logo-icon">&#x1F916;</div>OpenClaw Trading</div>
      <nav style="display:flex;align-items:center;gap:4px;margin-left:24px;">
        <a href="/" class="nav-tab">&#x20BF; BTC</a>
        <a href="/stocks" class="nav-tab">&#x1F4C8; &#xC8FC;&#xC2DD;</a>
        <a href="/us" class="nav-tab active">&#x1F1FA;&#x1F1F8; US</a>
      </nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <div id="fx-rate" style="font-family:var(--mono);font-size:11px;color:var(--yellow);background:rgba(255,214,0,0.08);border:1px solid rgba(255,214,0,0.15);padding:4px 10px;border-radius:8px;">USD/KRW ...</div>
      <div class="live-badge"><div class="live-dot"></div>LIVE</div>
      <div style="font-family:var(--mono);font-size:12px;color:var(--muted);" id="clock"></div>
    </div>
  </header>

  <main>
    <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:20px;">
      <div>
        <h2 style="font-size:20px;font-weight:700;">&#x1F1FA;&#x1F1F8; &#xBBF8;&#xAD6D;&#xC8FC;&#xC2DD; &#xBAA8;&#xBA58;&#xD140; &#xC790;&#xB3D9;&#xB9E4;&#xB9E4;</h2>
        <div style="font-size:12px;color:var(--muted);font-family:var(--mono);margin-top:4px;" id="sub-header">Loading...</div>
      </div>
      <div style="font-family:var(--mono);font-size:11px;color:var(--muted);" id="last-update"></div>
    </div>

    <!-- 시장 지수 -->
    <div class="idx-row" id="idx-row"><div class="idx-card"><div class="idx-name">Loading...</div></div></div>

    <!-- 통계 -->
    <div class="stat-row" id="stat-row"></div>

    <!-- 포트폴리오 -->
    <div id="portfolio-section"></div>

    <!-- 차트 + 로그 -->
    <div class="grid-2">
      <div class="card">
        <div class="chart-header">
          <div class="card-title"><span>&#x1F4CA;</span> <span id="chart-title">&#xC885;&#xBAA9; &#xCC28;&#xD2B8;</span> <span class="chart-live-dot" id="chart-live-dot" style="display:none;"></span></div>
          <div class="chart-tabs" id="chart-tabs">
            <div class="chart-tab" data-period="1mo">1&#xAC1C;&#xC6D4;</div>
            <div class="chart-tab active" data-period="3mo">3&#xAC1C;&#xC6D4;</div>
            <div class="chart-tab" data-period="6mo">6&#xAC1C;&#xC6D4;</div>
            <div class="chart-tab" data-period="1y">1&#xB144;</div>
          </div>
        </div>
        <div class="chart-container" id="stock-chart"></div>
      </div>
      <div class="card">
        <div class="card-title"><span>&#x1F4DD;</span> &#xC2E4;&#xC2DC;&#xAC04; &#xC5D0;&#xC774;&#xC804;&#xD2B8; &#xB85C;&#xADF8;</div>
        <div class="log-viewer" id="log-viewer">Loading...</div>
      </div>
    </div>

    <!-- 매매 내역 -->
    <div class="card" style="margin-bottom:20px;">
      <div class="card-title"><span>&#x1F4B0;</span> &#xCD5C;&#xADFC; &#xB9E4;&#xB9E4; &#xB0B4;&#xC5ED;</div>
      <div class="trade-list" id="trade-list">Loading...</div>
    </div>

    <!-- 모멘텀 랭킹 -->
    <div class="section-title"><span>&#x1F4CA;</span> &#xBAA8;&#xBA58;&#xD140; &#xB7AD;&#xD0B9;</div>
    <div class="filter-bar">
      <input type="text" id="search-input" placeholder="&#xC885;&#xBAA9; &#xAC80;&#xC0C9; (&#xC608;: AAPL)">
      <select id="grade-filter">
        <option value="all">&#xC804;&#xCCB4; &#xB4F1;&#xAE09;</option>
        <option value="A">A &#xB4F1;&#xAE09; (75+)</option>
        <option value="B">B &#xB4F1;&#xAE09; (60+)</option>
        <option value="C">C &#xB4F1;&#xAE09; (40+)</option>
        <option value="D">D &#xB4F1;&#xAE09; (&lt;40)</option>
      </select>
      <select id="sort-select">
        <option value="score-desc">&#xC2A4;&#xCF54;&#xC5B4; &#xB192;&#xC740;&#xC21C;</option>
        <option value="score-asc">&#xC2A4;&#xCF54;&#xC5B4; &#xB0AE;&#xC740;&#xC21C;</option>
        <option value="ret5-desc">5&#xC77C; &#xC218;&#xC775;&#xB960; &#xB192;&#xC740;&#xC21C;</option>
        <option value="ret20-desc">20&#xC77C; &#xC218;&#xC775;&#xB960; &#xB192;&#xC740;&#xC21C;</option>
        <option value="vol-desc">&#xAC70;&#xB798;&#xB7C9;&#xBE44; &#xB192;&#xC740;&#xC21C;</option>
        <option value="near-desc">&#xC2E0;&#xACE0;&#xAC00; &#xADFC;&#xC811; &#xB192;&#xC740;&#xC21C;</option>
      </select>
    </div>
    <table>
      <thead><tr>
        <th>#</th>
        <th>&#xC885;&#xBAA9;</th>
        <th>&#xC2A4;&#xCF54;&#xC5B4;</th>
        <th>5&#xC77C; &#xC218;&#xC775;&#xB960;</th>
        <th>20&#xC77C; &#xC218;&#xC775;&#xB960;</th>
        <th>&#xAC70;&#xB798;&#xB7C9;&#xBE44;</th>
        <th>&#xC2E0;&#xACE0;&#xAC00; &#xADFC;&#xC811;</th>
        <th>&#xC0C1;&#xD0DC;</th>
      </tr></thead>
      <tbody id="ranking-body"></tbody>
    </table>
  </main>
</div>

<script>
let allSignals = [];
let holdingSymbols = new Set();
let currentChartSymbol = '';
let currentPeriod = '3mo';
let stockChart = null;
let candleSeries = null;
let volumeSeries = null;
let usdkrw = 1450;
let chartRefreshTimer = null;

setInterval(() => {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleTimeString('ko-KR');
}, 1000);

function pnlColor(v) { return v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text)'; }
function pnlSign(v) { return v > 0 ? '+' : ''; }
function grade(s) { return s >= 75 ? 'A' : s >= 60 ? 'B' : s >= 40 ? 'C' : 'D'; }
function krw(usd) { return Math.round(usd * usdkrw).toLocaleString('ko-KR'); }
function krwTag(usd) { return `<span class="krw-sub">\u20A9${krw(usd)}</span>`; }

async function loadFx() {
  try {
    const res = await fetch('/api/us/fx');
    const data = await res.json();
    if (data.usdkrw) usdkrw = data.usdkrw;
    const fxEl = document.getElementById('fx-rate');
    if (fxEl) fxEl.textContent = `USD/KRW ${usdkrw.toLocaleString('ko-KR')}`;
  } catch(e) { console.error('fx', e); }
}

// ─── Market Indices (시장 지수) ───
async function loadMarket() {
  try {
    const res = await fetch('/api/us/market');
    const data = await res.json();
    const el = document.getElementById('idx-row');
    if (!data.length) { el.innerHTML = '<div style="color:var(--muted);font-size:12px;">지수 로딩 중...</div>'; return; }
    const nameKo = {'S&P 500':'S&P 500 (미국 대형주)','NASDAQ':'NASDAQ (기술주)','Dow Jones':'Dow Jones (산업주)','VIX':'VIX (공포지수)'};
    el.innerHTML = data.map(m => {
      const c = m.change_pct > 0 ? 'var(--green)' : m.change_pct < 0 ? 'var(--red)' : 'var(--text)';
      const s = m.change_pct > 0 ? '+' : '';
      const p = m.name === 'VIX' ? m.price.toFixed(1) : m.price.toLocaleString('en-US',{maximumFractionDigits:0});
      const label = nameKo[m.name] || m.name;
      return `<div class="idx-card"><div class="idx-name">${label}</div><div class="idx-price">${p}</div><div class="idx-chg" style="color:${c}">${s}${m.change_pct.toFixed(2)}%</div></div>`;
    }).join('');
  } catch(e) { console.error('market', e); }
}

// ─── Portfolio (포트폴리오) ───
async function loadPositions() {
  try {
    const res = await fetch('/api/us/positions');
    const data = await res.json();
    const positions = data.positions || [];
    const summary = data.summary || {};
    holdingSymbols = new Set(positions.map(p => p.symbol));
    const el = document.getElementById('portfolio-section');

    if (!positions.length) { el.innerHTML = ''; return; }

    const tc = pnlColor(summary.total_pnl_pct);
    const inv = summary.total_invested||0;
    const cur = summary.total_current||0;
    const pnlU = summary.total_pnl_usd||0;
    const cap = summary.virtual_capital||10000;
    let html = `
      <div class="card-title"><span>&#x1F4BC;</span> \uBCF4\uC720 \uD3EC\uC9C0\uC158</div>
      <div class="portfolio-bar">
        <div class="item"><div class="label">\uAC00\uC0C1\uC790\uBCF8</div><div class="val">$${cap.toLocaleString()}${krwTag(cap)}</div></div>
        <div class="item"><div class="label">\uD22C\uC790\uAE08</div><div class="val">$${inv.toLocaleString('en',{maximumFractionDigits:0})}${krwTag(inv)}</div></div>
        <div class="item"><div class="label">\uD3C9\uAC00\uAE08</div><div class="val">$${cur.toLocaleString('en',{maximumFractionDigits:0})}${krwTag(cur)}</div></div>
        <div class="item"><div class="label">\uC218\uC775\uB960</div><div class="val" style="color:${tc}">${pnlSign(summary.total_pnl_pct)}${(summary.total_pnl_pct||0).toFixed(2)}%</div></div>
        <div class="item"><div class="label">\uC190\uC775</div><div class="val" style="color:${tc}">${pnlSign(pnlU)}$${pnlU.toFixed(0)}${krwTag(pnlU)}</div></div>
      </div>
      <div class="pos-grid">`;

    for (const p of positions) {
      const pnl = p.pnl_pct || 0;
      const pc = pnlColor(pnl);
      const cls = currentChartSymbol === p.symbol ? 'pos-card active' : 'pos-card';
      const posPnlUsd = p.pnl_usd || 0;
      html += `<div class="${cls}" onclick="selectSymbol('${p.symbol}')">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div class="pos-sym">${p.symbol}</div>
          <div class="pos-score">M${(p.score||0).toFixed(0)}</div>
        </div>
        <div class="pos-detail">${(p.quantity||0).toFixed(2)}주 &times; $${(p.price||0).toFixed(2)}</div>
        <div class="pos-cur">$${(p.current_price||0).toFixed(2)} <span class="pos-krw">\u20A9${krw(p.current_price||0)}</span></div>
        <div class="pos-pnl" style="color:${pc}">${pnlSign(pnl)}${pnl.toFixed(2)}% <span class="pos-krw">(${pnlSign(posPnlUsd)}$${posPnlUsd.toFixed(0)} / \u20A9${krw(Math.abs(posPnlUsd))})</span></div>
      </div>`;
    }
    html += '</div>';
    el.innerHTML = html;
    updateStats(summary, positions.length);
    if (!currentChartSymbol && positions.length > 0) selectSymbol(positions[0].symbol);
  } catch(e) { console.error('positions', e); }
}

function updateStats(summary, posCount) {
  const el = document.getElementById('stat-row');
  const sigCount = allSignals.length;
  const avgScore = sigCount ? (allSignals.reduce((a,b) => a + (b.score||0), 0) / sigCount).toFixed(1) : '0';
  el.innerHTML = `
    <div class="stat-card"><div class="stat-label">\uC720\uB2C8\uBC84\uC2A4</div><div class="stat-val">${sigCount}</div></div>
    <div class="stat-card"><div class="stat-label">\uD3C9\uADE0 \uC2A4\uCF54\uC5B4</div><div class="stat-val">${avgScore}</div></div>
    <div class="stat-card"><div class="stat-label">\uBCF4\uC720\uC885\uBAA9</div><div class="stat-val" style="color:${posCount?'var(--green)':'var(--muted)'}">${posCount}</div></div>
    <div class="stat-card"><div class="stat-label">\uCD1D \uC218\uC775\uB960</div><div class="stat-val" style="color:${pnlColor(summary.total_pnl_pct||0)}">${pnlSign(summary.total_pnl_pct||0)}${(summary.total_pnl_pct||0).toFixed(2)}%</div></div>
  `;
}

// ─── Chart (종목 차트) — 실시간 갱신 ───
function selectSymbol(sym) {
  currentChartSymbol = sym;
  document.getElementById('chart-title').textContent = sym + ' 차트';
  document.querySelectorAll('.pos-card').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.pos-card').forEach(c => {
    if (c.querySelector('.pos-sym')?.textContent === sym) c.classList.add('active');
  });
  loadChart(sym, currentPeriod);
  startChartAutoRefresh();
}

async function loadChart(symbol, period) {
  if (!symbol) return;
  try {
    const res = await fetch(`/api/us/chart/${symbol}?period=${period}`);
    const data = await res.json();
    const candles = data.candles || [];
    if (!candles.length) return;

    const container = document.getElementById('stock-chart');
    container.innerHTML = '';

    stockChart = LightweightCharts.createChart(container, {
      layout: { background: { color: '#0f1422' }, textColor: '#4a5068' },
      grid: { vertLines: { color: '#1e2537' }, horzLines: { color: '#1e2537' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1e2537' },
      timeScale: { borderColor: '#1e2537', timeVisible: false },
      width: container.clientWidth,
      height: 400,
    });

    candleSeries = stockChart.addCandlestickSeries({
      upColor: '#00e676', downColor: '#ff3d57',
      borderUpColor: '#00e676', borderDownColor: '#ff3d57',
      wickUpColor: '#00e676', wickDownColor: '#ff3d57',
    });
    candleSeries.setData(candles);

    volumeSeries = stockChart.addHistogramSeries({
      color: 'rgba(0,212,255,0.2)',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeries.setData(candles.map(c => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? 'rgba(0,230,118,0.3)' : 'rgba(255,61,87,0.3)',
    })));

    stockChart.timeScale().fitContent();
    new ResizeObserver(() => {
      if (stockChart) stockChart.applyOptions({ width: container.clientWidth });
    }).observe(container);

    document.getElementById('chart-live-dot').style.display = 'inline-block';
  } catch(e) { console.error('chart', e); }
}

async function refreshChartData() {
  if (!currentChartSymbol || !candleSeries) return;
  try {
    const res = await fetch(`/api/us/chart/${currentChartSymbol}?period=${currentPeriod}`);
    const data = await res.json();
    const candles = data.candles || [];
    if (!candles.length) return;
    candleSeries.setData(candles);
    if (volumeSeries) {
      volumeSeries.setData(candles.map(c => ({
        time: c.time, value: c.volume,
        color: c.close >= c.open ? 'rgba(0,230,118,0.3)' : 'rgba(255,61,87,0.3)',
      })));
    }
  } catch(e) { /* silent */ }
}

function startChartAutoRefresh() {
  if (chartRefreshTimer) clearInterval(chartRefreshTimer);
  chartRefreshTimer = setInterval(refreshChartData, 5000);
}

document.getElementById('chart-tabs').addEventListener('click', e => {
  const tab = e.target.closest('.chart-tab');
  if (!tab) return;
  document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  currentPeriod = tab.dataset.period;
  if (currentChartSymbol) loadChart(currentChartSymbol, currentPeriod);
});

// ─── Agent Log (에이전트 로그) ───
async function loadLogs() {
  try {
    const res = await fetch('/api/us/logs');
    const data = await res.json();
    const lines = data.lines || [];
    const el = document.getElementById('log-viewer');
    el.innerHTML = lines.map(line => {
      let cls = 'log-info';
      if (/💰|BUY|SELL|매수|매도/.test(line)) cls = 'log-trade';
      else if (/⚠️|WARN/.test(line)) cls = 'log-warn';
      else if (/❌|ERROR/.test(line)) cls = 'log-error';
      return `<div class="${cls}">${line.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
  } catch(e) { console.error('logs', e); }
}

// ─── Trade History (매매 내역) ───
async function loadTrades() {
  try {
    const res = await fetch('/api/us/trades');
    const trades = await res.json();
    const el = document.getElementById('trade-list');
    if (!trades.length) { el.innerHTML = '<div style="color:var(--muted);padding:20px;text-align:center;">\uB9E4\uB9E4 \uB0B4\uC5ED \uC5C6\uC74C</div>'; return; }
    el.innerHTML = trades.map(t => {
      const isBuy = t.trade_type === 'BUY';
      const cls = isBuy ? 'trade-buy' : 'trade-sell';
      const icon = isBuy ? '&#x1F7E2;' : '&#x1F534;';
      const typeKo = isBuy ? '\uB9E4\uC218' : '\uB9E4\uB3C4';
      const time = (t.created_at || '').replace('T', ' ').slice(0, 19);
      const reason = t.reason || t.exit_reason || '';
      const total = (t.price||0) * (t.quantity||0);
      return `<div class="trade-item ${cls}">
        <span>${icon}</span>
        <span class="trade-sym">${t.symbol||''}</span>
        <span>${typeKo}</span>
        <span>$${(t.price||0).toFixed(2)} &times; ${(t.quantity||0).toFixed(2)}</span>
        <span style="color:var(--muted);font-size:10px;">$${total.toFixed(0)} <span class="pos-krw">(\u20A9${krw(total)})</span></span>
        <span style="color:var(--muted);font-size:10px;">${reason}</span>
        <span class="trade-time">${time}</span>
      </div>`;
    }).join('');
  } catch(e) { console.error('trades', e); }
}

// ─── Ranking Table (모멘텀 랭킹) ───
async function loadSignals() {
  try {
    const res = await fetch('/api/us/top');
    const data = await res.json();
    allSignals = data.items || [];
    const runDate = data.run_date || '';
    document.getElementById('sub-header').textContent =
      (runDate ? '\uC2A4\uCE94: ' + runDate + ' \xB7 ' : '') +
      '\uC720\uB2C8\uBC84\uC2A4 ' + allSignals.length + '\uC885 \xB7 \uD3C9\uADE0 ' +
      (allSignals.length ? (allSignals.reduce((a,b) => a + (b.score||0), 0) / allSignals.length).toFixed(1) : '0');
    renderTable();
  } catch(e) { console.error('signals', e); }
}

function renderTable() {
  const search = (document.getElementById('search-input').value || '').toUpperCase();
  const gradeFilter = document.getElementById('grade-filter').value;
  const sortVal = document.getElementById('sort-select').value;

  let filtered = allSignals.filter(s => {
    if (search && !(s.symbol || '').toUpperCase().includes(search)) return false;
    if (gradeFilter !== 'all' && grade(s.score || 0) !== gradeFilter) return false;
    return true;
  });

  const [sortKey, sortDir] = sortVal.split('-');
  const mul = sortDir === 'desc' ? -1 : 1;
  const keyMap = { score:'score', ret5:'ret_5d', ret20:'ret_20d', vol:'vol_ratio', near:'near_high' };
  filtered.sort((a, b) => mul * ((a[keyMap[sortKey]||'score']||0) - (b[keyMap[sortKey]||'score']||0)));

  const tbody = document.getElementById('ranking-body');
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:40px;">\uACB0\uACFC \uC5C6\uC74C</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map((row, i) => {
    const s = row.score || 0;
    const g = grade(s);
    const r5 = row.ret_5d || 0;
    const r20 = row.ret_20d || 0;
    const sym = row.symbol || '';
    const isHolding = holdingSymbols.has(sym);
    const rowCls = isHolding ? 'holding-row' : '';
    const sc = s >= 70 ? 'var(--accent)' : s >= 50 ? 'var(--green)' : s >= 35 ? 'var(--yellow)' : 'var(--red)';
    const status = isHolding ? '<span style="color:var(--accent);font-weight:700;">\uBCF4\uC720\uC911</span>' : '';
    return `<tr class="${rowCls}" style="cursor:pointer" onclick="selectSymbol('${sym}')">
      <td>${i+1}</td>
      <td style="font-family:var(--mono);font-weight:600">${sym}</td>
      <td><span style="color:${sc};font-weight:700">${s.toFixed(1)}</span> <span class="badge badge-${g.toLowerCase()}">${g}</span></td>
      <td style="color:${pnlColor(r5)}">${pnlSign(r5)}${r5.toFixed(2)}%</td>
      <td style="color:${pnlColor(r20)}">${pnlSign(r20)}${r20.toFixed(2)}%</td>
      <td>${(row.vol_ratio||0).toFixed(2)}x</td>
      <td>${(row.near_high||0).toFixed(1)}%</td>
      <td>${status}</td>
    </tr>`;
  }).join('');
}

document.getElementById('search-input').addEventListener('input', renderTable);
document.getElementById('grade-filter').addEventListener('change', renderTable);
document.getElementById('sort-select').addEventListener('change', renderTable);

// ─── Init & Polling ───
async function init() {
  await loadFx();
  await Promise.all([loadMarket(), loadSignals(), loadPositions(), loadLogs(), loadTrades()]);
  document.getElementById('last-update').textContent = '\uAC31\uC2E0: ' + new Date().toLocaleTimeString('ko-KR');
}

init();
setInterval(async () => {
  await Promise.all([loadPositions(), loadLogs(), loadTrades()]);
  document.getElementById('last-update').textContent = '\uAC31\uC2E0: ' + new Date().toLocaleTimeString('ko-KR');
}, 10000);
setInterval(loadMarket, 60000);
setInterval(loadSignals, 120000);
setInterval(loadFx, 300000);
</script>
</body>
</html>'''
