#!/usr/bin/env python3
"""
주식 장 전 분석 (08:00 실행)
- 전날 종가 수집
- 미국 증시 마감 결과 (yfinance)
- 뉴스 감정분석 (CoinDesk RSS 대신 네이버 금융 RSS)
- AI 오늘 전략 수립
- 텔레그램 브리핑 발송
"""

import os, json, requests
from datetime import datetime, timedelta
from pathlib import Path

# 환경변수 로드
def _load_env():
    for p in [
        Path('/home/wlsdud5035/.openclaw/.env'),
        Path('/home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env'),
    ]:
        if not p.exists(): continue
        for line in p.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
_load_env()

# openclaw.json env (Supabase 등)
_openclaw_json = Path('/home/wlsdud5035/.openclaw/openclaw.json')
if _openclaw_json.exists():
    try:
        data = json.loads(_openclaw_json.read_text())
        for k, v in (data.get('env') or {}).items():
            if k != 'shellEnv' and isinstance(v, str):
                os.environ.setdefault(k, v)
    except Exception:
        pass

TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT  = os.environ.get('TELEGRAM_CHAT_ID', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')

try:
    from supabase import create_client
    _supabase_url = os.environ.get('SUPABASE_URL', '')
    _supabase_key = os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_KEY', '')
    supabase = create_client(_supabase_url, _supabase_key) if (_supabase_url and _supabase_key) else None
except Exception:
    supabase = None

# 종목 리스트
WATCHLIST = [
    {"code": "005930", "name": "삼성전자",     "sector": "반도체"},
    {"code": "000660", "name": "SK하이닉스",   "sector": "반도체"},
    {"code": "042700", "name": "한미반도체",   "sector": "HBM"},
    {"code": "035420", "name": "NAVER",        "sector": "IT"},
    {"code": "005380", "name": "현대차",       "sector": "자동차"},
]

# 미국 지수 (yfinance)
US_INDICES = [
    {"symbol": "^GSPC",  "name": "S&P500"},
    {"symbol": "^IXIC",  "name": "나스닥"},
    {"symbol": "NVDA",   "name": "엔비디아"},
    {"symbol": "TSM",    "name": "TSMC"},
]

def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=5
        )
    except Exception as e:
        print(f'텔레그램 실패: {e}')

def get_us_market():
    """미국 증시 마감 데이터"""
    results = []
    try:
        import yfinance as yf
        for item in US_INDICES:
            ticker = yf.Ticker(item['symbol'])
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                prev = hist['Close'].iloc[-2]
                last = hist['Close'].iloc[-1]
                chg = (last - prev) / prev * 100
                results.append({
                    'name': item['name'],
                    'price': round(last, 2),
                    'change': round(chg, 2),
                })
    except Exception as e:
        print(f'미국 시장 조회 실패: {e}')
    return results

def get_korean_stock_news():
    import xml.etree.ElementTree as ET
    sources = [
        'https://www.yna.co.kr/rss/economy.xml',
        'https://rss.hankyung.com/economy.xml',
    ]
    for url in sources:
        try:
            res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            root = ET.fromstring(res.content)
            items = root.findall('.//item')[:5]
            headlines = [item.findtext('title', '').strip() for item in items if item.findtext('title')]
            if headlines:
                return headlines
        except Exception as e:
            print(f'뉴스 RSS 실패 {url}: {e}')
    return []

def get_kiwoom_stock_prices():
    """키움 API로 종목 현재가 조회"""
    import time
    try:
        from kiwoom_client import KiwoomClient
        client = KiwoomClient()
        results = []
        for stock in WATCHLIST:
            time.sleep(1)
            try:
                info = client.get_stock_info(stock['code'])
                # 키움 API: cur_prc(현재가), flu_rt(등락률) 또는 stck_prpr, prdy_ctrt
                price = info.get('cur_prc') or info.get('stck_prpr', 0)
                change = info.get('flu_rt') or info.get('prdy_ctrt', 0)
                try:
                    price = int(price) if price else 0
                except (ValueError, TypeError):
                    price = 0
                try:
                    change = float(change) if change else 0.0
                except (ValueError, TypeError):
                    change = 0.0
                results.append({
                    'code': stock['code'],
                    'name': stock['name'],
                    'price': price,
                    'change': change,
                })
            except Exception as e:
                print(f"{stock['name']} 조회 실패: {e}")
        return results
    except Exception as e:
        print(f'키움 클라이언트 실패: {e}')
        return []

def analyze_with_ai(us_market, news, stocks):
    """AI 오늘 전략 수립"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        us_summary = '\n'.join([
            f"{m['name']}: {m['price']} ({m['change']:+.2f}%)"
            for m in us_market
        ]) or '조회 실패'

        news_summary = '\n'.join(news[:5]) or '뉴스 없음'

        stock_summary = '\n'.join([
            f"{s['name']}({s['code']}): {s['price']}원 ({s['change']:+.2f}%)"
            for s in stocks
        ]) or '조회 실패'

        prompt = f"""당신은 한국 주식 퀀트 트레이더입니다.
오늘 장 시작 전 데이터를 분석해서 전략을 JSON으로만 출력하세요.

[미국 증시 마감]
{us_summary}

[오늘 주요 뉴스]
{news_summary}

[관심 종목 현황]
{stock_summary}

[출력 형식 - JSON만]
{{
  "market_outlook": "강세/약세/중립",
  "top_picks": [
    {{"code": "종목코드", "name": "종목명", "action": "BUY/WATCH/AVOID", "reason": "한줄이유"}}
  ],
  "risk_level": "낮음/보통/높음",
  "summary": "오늘 전략 한줄요약"
}}"""

        res = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        raw = res.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        return json.loads(raw)
    except Exception as e:
        print(f'AI 분석 실패: {e}')
        return {
            'market_outlook': '중립',
            'top_picks': [],
            'risk_level': '보통',
            'summary': 'AI 분석 실패'
        }

def run_premarket():
    print(f'\n[{datetime.now()}] 장 전 분석 시작')

    us_market = get_us_market()
    news      = get_korean_stock_news()
    stocks    = get_kiwoom_stock_prices()
    strategy  = analyze_with_ai(us_market, news, stocks)

    # 텔레그램 브리핑
    now = datetime.now().strftime('%m/%d %H:%M')

    us_lines = '\n'.join([
        f"  {'📈' if m['change'] >= 0 else '📉'} {m['name']}: {m['change']:+.2f}%"
        for m in us_market
    ]) or '  조회 실패'

    picks_lines = '\n'.join([
        f"  {'🟢' if p['action']=='BUY' else '👀' if p['action']=='WATCH' else '🔴'} "
        f"{p['name']}: {p['action']} — {p['reason']}"
        for p in strategy.get('top_picks', [])
    ]) or '  추천 없음'

    msg = (
        f"🌅 <b>장 전 브리핑</b> {now}\n\n"
        f"🇺🇸 <b>미국 증시</b>\n{us_lines}\n\n"
        f"📊 <b>AI 전략</b> [{strategy.get('market_outlook','?')}장 / 리스크:{strategy.get('risk_level','?')}]\n"
        f"{picks_lines}\n\n"
        f"💡 {strategy.get('summary','')}"
    )

    send_telegram(msg)
    print(msg)

    # 전략 저장
    strategy_path = Path('/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json')
    strategy['date'] = datetime.now().date().isoformat()
    strategy['us_market'] = us_market
    strategy_path.write_text(json.dumps(strategy, ensure_ascii=False, indent=2))
    print(f'✅ 전략 저장: {strategy_path}')

    if supabase:
        try:
            supabase.table('daily_reports').upsert({
                'date': datetime.now().date().isoformat(),
                'report_type': 'premarket',
                'market_outlook': strategy.get('market_outlook', '중립'),
                'risk_level': strategy.get('risk_level', '보통'),
                'summary': strategy.get('summary', ''),
                'top_picks': json.dumps(strategy.get('top_picks', []), ensure_ascii=False),
                'us_market': json.dumps(us_market, ensure_ascii=False),
            }).execute()
            print('✅ Supabase daily_reports 저장 완료')
        except Exception as e:
            print(f'❌ Supabase 저장 실패: {e}')

if __name__ == '__main__':
    run_premarket()
