#!/usr/bin/env python3
# btc_dashboard.py — FastAPI + Chart.js 경량 대시보드 (RAM 2GB 대응)
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from supabase import create_client
import os
import json

app = FastAPI()
url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_SECRET_KEY", "")
sb = create_client(url, key) if url and key else None


@app.get("/api/trades")
def api_trades():
    if not sb:
        return []
    return sb.table("btc_trades").select("*").order("timestamp", desc=True).limit(200).execute().data


@app.get("/api/summary")
def api_summary():
    if not sb:
        return []
    return sb.table("btc_daily_summary").select("*").execute().data


@app.get("/", response_class=HTMLResponse)
def dashboard():
    trades = api_trades()
    summary = api_summary() if sb else []

    trades_sorted = list(reversed(trades))
    prices = [t["price"] for t in trades_sorted if t.get("price")]
    times = [t["timestamp"][:16] for t in trades_sorted if t.get("price")]
    pnl_cum = []
    total = 0
    for t in trades_sorted:
        total += float(t.get("pnl") or 0)
        pnl_cum.append(round(total, 0))

    total_pnl = sum(float(t.get("pnl") or 0) for t in trades)
    buy_count = sum(1 for t in trades if t.get("action") == "BUY")
    sell_count = sum(1 for t in trades if t.get("action") == "SELL")
    sells = [t for t in trades if t.get("action") == "SELL"]
    wins = sum(1 for t in sells if (t.get("pnl") or 0) > 0)
    win_rate = round(wins / sell_count * 100, 1) if sell_count > 0 else 0
    avg_conf = round(sum(t.get("confidence") or 0 for t in trades) / len(trades), 1) if trades else 0
    last_signal = trades[0] if trades else {}

    rows_html = "".join(
        f"""
  <div class="sig-row">
    <span>{'🟢' if t.get('action')=='BUY' else '🔴' if t.get('action')=='SELL' else '⚪'} {t.get('action','—')}</span>
    <span>{t.get('timestamp','')[:16]}</span>
    <span>{int(t.get('price') or 0):,}원</span>
    <span>RSI {t.get('rsi','—')}</span>
    <span class="{'green' if (t.get('pnl') or 0)>0 else 'red'}">{f"{float(t['pnl']):+.2f}%" if t.get('pnl') is not None else '—'}</span>
  </div>"""
        for t in trades[:20]
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BTC 자동매매 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0d1117; color:#e6edf3; font-family:'Segoe UI',sans-serif; padding:20px; }}
  h1 {{ color:#58a6ff; margin-bottom:20px; font-size:1.4rem; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:24px; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; text-align:center; }}
  .card .val {{ font-size:1.6rem; font-weight:700; margin:6px 0; }}
  .card .lbl {{ font-size:0.75rem; color:#8b949e; }}
  .green {{ color:#3fb950; }} .red {{ color:#f85149; }} .blue {{ color:#58a6ff; }} .yellow {{ color:#d29922; }}
  .charts {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px; }}
  .chart-box {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }}
  .chart-box h3 {{ font-size:0.85rem; color:#8b949e; margin-bottom:12px; }}
  .signal-box {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:24px; }}
  .signal-box h3 {{ font-size:0.85rem; color:#8b949e; margin-bottom:10px; }}
  .sig-row {{ display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #21262d; font-size:0.85rem; }}
  @media(max-width:700px){{ .charts{{grid-template-columns:1fr;}} }}
</style>
</head>
<body>
<h1>🤖 BTC 자동매매 대시보드</h1>

<div class="cards">
  <div class="card">
    <div class="lbl">누적 손익</div>
    <div class="val {'green' if total_pnl >= 0 else 'red'}">{total_pnl:+,.0f}원</div>
  </div>
  <div class="card">
    <div class="lbl">승률</div>
    <div class="val {'green' if win_rate >= 50 else 'red'}">{win_rate}%</div>
    <div class="lbl">{wins}승 / {sell_count - wins}패</div>
  </div>
  <div class="card">
    <div class="lbl">총 거래</div>
    <div class="val blue">{buy_count + sell_count}회</div>
    <div class="lbl">매수 {buy_count} / 매도 {sell_count}</div>
  </div>
  <div class="card">
    <div class="lbl">평균 신뢰도</div>
    <div class="val yellow">{avg_conf}%</div>
  </div>
  <div class="card">
    <div class="lbl">마지막 신호</div>
    <div class="val {'green' if last_signal.get('action')=='BUY' else 'red' if last_signal.get('action')=='SELL' else 'blue'}">
      {last_signal.get('action','—')}
    </div>
    <div class="lbl">{str(last_signal.get('timestamp',''))[:16]}</div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h3>📈 BTC 가격 추이</h3>
    <canvas id="priceChart"></canvas>
  </div>
  <div class="chart-box">
    <h3>💰 누적 손익 (원)</h3>
    <canvas id="pnlChart"></canvas>
  </div>
</div>

<div class="signal-box">
  <h3>📋 최근 거래 내역</h3>
  {rows_html or '<div class="sig-row">거래 내역 없음</div>'}
</div>

<script>
const times  = {json.dumps(times)};
const prices = {json.dumps(prices)};
const pnlCum = {json.dumps(pnl_cum)};

if (times.length && document.getElementById('priceChart')) {{
  new Chart(document.getElementById('priceChart'), {{
    type:'line',
    data:{{ labels:times.slice(-50),
      datasets:[{{ label:'BTC(KRW)', data:prices.slice(-50),
        borderColor:'#58a6ff', backgroundColor:'rgba(88,166,255,0.1)',
        borderWidth:1.5, pointRadius:0, tension:0.3 }}]
    }},
    options:{{ plugins:{{legend:{{display:false}}}},
      scales:{{ x:{{ticks:{{color:'#8b949e',maxTicksLimit:6}},grid:{{color:'#21262d'}}}},
                y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}} }} }}
  }});
}}
if (pnlCum.length && document.getElementById('pnlChart')) {{
  new Chart(document.getElementById('pnlChart'), {{
    type:'line',
    data:{{ labels:times.slice(-50),
      datasets:[{{ label:'누적손익', data:pnlCum.slice(-50),
        borderColor:'#3fb950', backgroundColor:'rgba(63,185,80,0.1)',
        borderWidth:1.5, pointRadius:0, tension:0.3, fill:true }}]
    }},
    options:{{ plugins:{{legend:{{display:false}}}},
      scales:{{ x:{{ticks:{{color:'#8b949e',maxTicksLimit:6}},grid:{{color:'#21262d'}}}},
                y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}} }} }}
  }});
}}
</script>
</body></html>"""
    return html


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
