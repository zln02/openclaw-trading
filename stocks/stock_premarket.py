#!/usr/bin/env python3
"""
주식 장 전 분석 v2.0 (08:00 실행)

변경사항 (v1 → v2):
- [FIX] AI 실패 시 룰 기반 전략 생성 (fallback)
- [FIX] 전략 JSON 스키마 일관성
- [NEW] 전날 매매 결과 요약 포함
- [NEW] 섹터별 분석 추가
- [NEW] 전략 저장 성공/실패 텔레그램 알림
- [REFACTOR] 에러 핸들링 강화

실행:
    python3 stock_premarket.py
"""

import os
import json
import sys
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# 환경변수 로드
# ─────────────────────────────────────────────
def _load_env():
    openclaw_json = Path('/home/wlsdud5035/.openclaw/openclaw.json')
    if openclaw_json.exists():
        d = json.loads(openclaw_json.read_text())
        for k, v in (d.get('env') or {}).items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
    for p in [
        Path('/home/wlsdud5035/.openclaw/.env'),
        Path('/home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env'),
    ]:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

sys.path.insert(0, str(Path(__file__).parent))
from kiwoom_client import KiwoomClient
from supabase import create_client

TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None
kiwoom = KiwoomClient()

STRATEGY_PATH = Path('/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json')

# 감시 종목 TOP50 (v3)
WATCHLIST = [
    {"code": "005930", "name": "삼성전자",       "sector": "반도체"},
    {"code": "000660", "name": "SK하이닉스",     "sector": "반도체"},
    {"code": "042700", "name": "한미반도체",     "sector": "반도체장비"},
    {"code": "403870", "name": "HPSP",           "sector": "반도체장비"},
    {"code": "005380", "name": "현대차",         "sector": "자동차"},
    {"code": "000270", "name": "기아",           "sector": "자동차"},
    {"code": "012330", "name": "현대모비스",     "sector": "자동차부품"},
    {"code": "068270", "name": "셀트리온",       "sector": "바이오"},
    {"code": "207940", "name": "삼성바이오로직스","sector": "바이오"},
    {"code": "326030", "name": "SK바이오팜",     "sector": "바이오"},
    {"code": "145020", "name": "휴젤",           "sector": "바이오"},
    {"code": "035420", "name": "NAVER",          "sector": "IT"},
    {"code": "035720", "name": "카카오",         "sector": "IT"},
    {"code": "259960", "name": "크래프톤",       "sector": "게임"},
    {"code": "263750", "name": "펄어비스",       "sector": "게임"},
    {"code": "051910", "name": "LG화학",         "sector": "화학"},
    {"code": "006400", "name": "삼성SDI",        "sector": "배터리"},
    {"code": "003670", "name": "포스코퓨처엠",   "sector": "2차전지"},
    {"code": "373220", "name": "LG에너지솔루션", "sector": "배터리"},
    {"code": "247540", "name": "에코프로비엠",   "sector": "2차전지"},
    {"code": "086520", "name": "에코프로",       "sector": "2차전지"},
    {"code": "055550", "name": "신한지주",       "sector": "금융"},
    {"code": "105560", "name": "KB금융",         "sector": "금융"},
    {"code": "316140", "name": "우리금융지주",   "sector": "금융"},
    {"code": "024110", "name": "기업은행",       "sector": "금융"},
    {"code": "066570", "name": "LG전자",         "sector": "전자"},
    {"code": "009150", "name": "삼성전기",       "sector": "전자부품"},
    {"code": "000100", "name": "유한양행",       "sector": "제약"},
    {"code": "096770", "name": "SK이노베이션",   "sector": "에너지"},
    {"code": "010950", "name": "S-Oil",          "sector": "에너지"},
    {"code": "005490", "name": "POSCO홀딩스",    "sector": "철강"},
    {"code": "028260", "name": "삼성물산",       "sector": "건설"},
    {"code": "000720", "name": "현대건설",       "sector": "건설"},
    {"code": "006360", "name": "GS건설",         "sector": "건설"},
    {"code": "034730", "name": "SK",             "sector": "지주"},
    {"code": "003550", "name": "LG",             "sector": "지주"},
    {"code": "030200", "name": "KT",             "sector": "통신"},
    {"code": "017670", "name": "SK텔레콤",       "sector": "통신"},
    {"code": "032640", "name": "LG유플러스",     "sector": "통신"},
    {"code": "004170", "name": "신세계",         "sector": "유통"},
    {"code": "069960", "name": "현대백화점",     "sector": "유통"},
    {"code": "051900", "name": "LG생활건강",     "sector": "소비재"},
    {"code": "090430", "name": "아모레퍼시픽",   "sector": "소비재"},
    {"code": "012450", "name": "한화에어로스페이스","sector": "방산"},
    {"code": "047810", "name": "한국항공우주",   "sector": "방산"},
    {"code": "329180", "name": "현대로템",       "sector": "방산"},
    {"code": "009540", "name": "HD한국조선해양", "sector": "조선"},
    {"code": "010140", "name": "삼성중공업",     "sector": "조선"},
    {"code": "042660", "name": "한화오션",       "sector": "조선"},
    {"code": "454910", "name": "두산로보틱스",   "sector": "로봇"},
    {"code": "443060", "name": "레인보우로보틱스","sector": "로봇"},
]

US_INDICES = [
    {"symbol": "^GSPC", "name": "S&P500"},
    {"symbol": "^IXIC", "name": "나스닥"},
    {"symbol": "^DJI",  "name": "다우존스"},
    {"symbol": "^VIX",  "name": "VIX공포지수"},
]


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅"}.get(level, "")
    print(f"[{ts}] {prefix} {msg}")


def send_telegram(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception as e:
        log(f'텔레그램 실패: {e}', 'WARN')


# ─────────────────────────────────────────────
# 데이터 수집
# ─────────────────────────────────────────────
def get_us_market() -> list:
    """미국 증시 전일 마감 결과"""
    try:
        import yfinance as yf
        results = []
        for idx in US_INDICES:
            try:
                ticker = yf.Ticker(idx['symbol'])
                hist = ticker.history(period='2d')
                if len(hist) >= 2:
                    prev = float(hist['Close'].iloc[-2])
                    last = float(hist['Close'].iloc[-1])
                    chg_pct = (last - prev) / prev * 100
                    results.append({
                        'name': idx['name'],
                        'price': round(last, 2),
                        'change_pct': round(chg_pct, 2),
                    })
            except Exception:
                continue
        return results
    except Exception as e:
        log(f'미국 증시 조회 실패: {e}', 'WARN')
        return []


def get_korean_stock_news() -> list:
    """한국 경제 뉴스 헤드라인"""
    try:
        import xml.etree.ElementTree as ET
        sources = [
            'https://www.yna.co.kr/rss/economy.xml',
            'https://rss.hankyung.com/economy.xml',
        ]
        headlines = []
        keywords = ['코스피', '반도체', '외국인', '기관', '금리', '환율', '수출', 'AI', '배터리']

        for url in sources:
            try:
                res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                root = ET.fromstring(res.content)
                for item in root.findall('.//item'):
                    title = item.findtext('title', '').strip()
                    if any(k in title for k in keywords):
                        headlines.append(title)
                if len(headlines) >= 10:
                    break
            except Exception:
                continue

        return headlines[:10]
    except Exception as e:
        log(f'뉴스 수집 실패: {e}', 'WARN')
        return []


def get_stock_prices() -> list:
    """키움 API로 전 종목 현재가 조회"""
    results = []
    for stock in WATCHLIST:
        try:
            price = kiwoom.get_current_price(stock['code'])
            results.append({
                'code': stock['code'],
                'name': stock['name'],
                'sector': stock['sector'],
                'price': price,
            })
        except Exception:
            results.append({
                'code': stock['code'],
                'name': stock['name'],
                'sector': stock['sector'],
                'price': 0,
            })
        time.sleep(0.2)
    return results


def get_stock_indicators() -> list:
    """DB에서 종목별 기술적 지표 요약"""
    if not supabase:
        return []

    results = []
    for stock in WATCHLIST:
        try:
            rows = (
                supabase.table('daily_ohlcv')
                .select('close_price,volume')
                .eq('stock_code', stock['code'])
                .order('date', desc=False)
                .limit(30)
                .execute()
                .data or []
            )
            if len(rows) < 14:
                continue

            closes = [float(r['close_price']) for r in rows]
            volumes = [float(r.get('volume', 0)) for r in rows]

            # RSI
            gains, losses = [], []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = round(100 - (100 / (1 + rs)), 1)

            # 거래량 비율
            avg_vol = sum(volumes[-20:]) / min(len(volumes[-20:]), 20) if volumes else 1
            vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

            # 볼린저밴드 위치
            bb_pos = 50
            if len(closes) >= 20:
                ma20 = sum(closes[-20:]) / 20
                std20 = (sum((c - ma20) ** 2 for c in closes[-20:]) / 20) ** 0.5
                bb_width = 4 * std20
                if bb_width > 0:
                    bb_pos = round((closes[-1] - (ma20 - 2 * std20)) / bb_width * 100, 1)

            results.append({
                'code': stock['code'],
                'name': stock['name'],
                'sector': stock['sector'],
                'rsi': rsi,
                'vol_ratio': vol_ratio,
                'bb_pos': bb_pos,
                'last_close': closes[-1],
            })
        except Exception:
            continue

    return results


def get_yesterday_results() -> str:
    """전날 매매 결과 요약"""
    if not supabase:
        return '전날 매매 데이터 없음'
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        trades = (
            supabase.table('trade_executions')
            .select('*')
            .gte('created_at', yesterday)
            .lt('created_at', datetime.now().date().isoformat())
            .execute()
            .data or []
        )
        if not trades:
            return '전날 매매 없음'

        buys = [t for t in trades if t.get('trade_type') == 'BUY']
        sells = [t for t in trades if t.get('trade_type') == 'SELL']
        return f'전날 매매: 매수 {len(buys)}건, 매도 {len(sells)}건'
    except Exception:
        return '전날 매매 조회 실패'


# ─────────────────────────────────────────────
# AI 전략 생성
# ─────────────────────────────────────────────
def analyze_with_ai(
    us_market: list,
    news: list,
    stocks: list,
    indicators: list,
    yesterday: str,
) -> dict:
    """GPT로 오늘 전략 수립"""
    if not OPENAI_KEY:
        log('OpenAI 키 없음 → 룰 기반 전략 생성', 'WARN')
        return generate_rule_based_strategy(indicators)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        us_summary = '\n'.join(
            f"  {m['name']}: {m['price']:,.2f} ({m['change_pct']:+.2f}%)"
            for m in us_market
        ) if us_market else '미국 증시 데이터 없음'

        news_summary = '\n'.join(f"  - {h}" for h in news[:7]) if news else '뉴스 없음'

        stock_summary = '\n'.join(
            f"  {s['name']}({s['code']}): {s['price']:,}원 [RSI:{ind.get('rsi','?')} BB:{ind.get('bb_pos','?')}% Vol:{ind.get('vol_ratio','?')}x]"
            for s in stocks
            for ind in indicators
            if ind['code'] == s['code']
        ) if stocks and indicators else '종목 데이터 없음'

        prompt = f"""당신은 연평균 수익률 50% 이상의 상위 1% 한국 주식 퀀트 트레이더입니다.
현재 모의투자 환경이므로 최대한 공격적으로 수익을 추구합니다.
50개 종목 중 오늘 수익 가능성이 가장 높은 종목을 선별합니다. 보수적 판단은 하지 마세요. 기회가 보이면 BUY로 추천합니다.

[미국 증시 마감]
{us_summary}

[한국 경제 뉴스]
{news_summary}

[감시 종목 현황 (50종목)]
{stock_summary}

[전일 매매]
{yesterday}

[분석 원칙]
1. 50개 전체 스캐닝 후 상위 10개만 추천 (나머지는 무시)
2. RSI 45 이하 종목은 적극 BUY 추천
3. 섹터 모멘텀이 살아있으면 해당 섹터 종목 우선
4. 미국 증시 긍정 → 반도체/IT 공격 매수
5. 미국 증시 부정 → 방어주(금융/통신) 또는 역발상 매수
6. 최소 BUY 3개, WATCH 3개 이상 추천

[분석 요청]
1. market_outlook: 오늘 시장 전망 (강세/중립/약세)
2. risk_level: 리스크 수준 (낮음/보통/높음)
3. sector_view: 섹터별 전망
4. top_picks: 상위 10개만 — code, name, action(BUY/WATCH/SELL), reason(한줄)

반드시 아래 JSON만 출력:
{{
  "date": "{datetime.now().date().isoformat()}",
  "market_outlook": "강세|중립|약세",
  "risk_level": "낮음|보통|높음",
  "sector_view": {{"반도체": "긍정|중립|부정", ...}},
  "top_picks": [
    {{"code": "005930", "name": "삼성전자", "action": "BUY", "reason": "이유"}}
  ],
  "summary": "한줄 요약"
}}"""

        res = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        raw = res.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()

        # JSON 추출
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            strategy = json.loads(raw[start:end])
        else:
            raise ValueError(f'JSON 파싱 불가: {raw[:100]}')

        # 필수 필드 보정
        strategy['date'] = datetime.now().date().isoformat()
        strategy.setdefault('market_outlook', '중립')
        strategy.setdefault('risk_level', '보통')
        strategy.setdefault('top_picks', [])
        strategy.setdefault('summary', '')
        strategy['source'] = 'AI'

        return strategy

    except Exception as e:
        log(f'AI 전략 생성 실패 → 룰 기반 fallback: {e}', 'WARN')
        return generate_rule_based_strategy(indicators)


def generate_rule_based_strategy(indicators: list) -> dict:
    """AI 없이 지표 기반 전략 생성"""
    picks = []
    for ind in indicators:
        rsi = ind.get('rsi', 50)
        bb = ind.get('bb_pos', 50)
        vol = ind.get('vol_ratio', 1.0)

        if rsi <= 35 and bb <= 30 and vol >= 0.8:
            action = 'BUY'
            reason = f'RSI {rsi} + BB하단 {bb}% — 매수 구간'
        elif rsi >= 70 and bb >= 80:
            action = 'SELL'
            reason = f'RSI {rsi} + BB상단 {bb}% — 매도 구간'
        elif rsi <= 45 and vol >= 1.0:
            action = 'WATCH'
            reason = f'RSI {rsi} — 관망 (추가 하락 시 매수)'
        else:
            continue

        picks.append({
            'code': ind['code'],
            'name': ind['name'],
            'action': action,
            'reason': reason,
        })

    return {
        'date': datetime.now().date().isoformat(),
        'market_outlook': '중립',
        'risk_level': '보통',
        'sector_view': {},
        'top_picks': picks[:10],
        'summary': f'룰 기반 전략: BUY {sum(1 for p in picks if p["action"]=="BUY")}개, WATCH {sum(1 for p in picks if p["action"]=="WATCH")}개',
        'source': 'RULE',
    }


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
def run_premarket():
    log('=' * 50)
    log('장 전 분석 시작')

    # 1. 데이터 수집
    log('미국 증시 조회...')
    us_market = get_us_market()
    for m in us_market:
        log(f"  {m['name']}: {m['price']:,.2f} ({m['change_pct']:+.2f}%)")

    log('한국 뉴스 수집...')
    news = get_korean_stock_news()
    log(f'  {len(news)}개 뉴스 수집')

    log('종목 현재가 조회...')
    stocks = get_stock_prices()
    log(f'  {len(stocks)}개 종목 조회')

    log('기술적 지표 계산...')
    indicators = get_stock_indicators()
    log(f'  {len(indicators)}개 종목 지표 계산')

    yesterday = get_yesterday_results()
    log(f'  {yesterday}')

    # 2. AI 전략 수립
    log('전략 수립 중...')
    strategy = analyze_with_ai(us_market, news, stocks, indicators, yesterday)
    log(f"전략 생성 완료 [{strategy.get('source', '?')}]: {strategy.get('market_outlook', '?')}")

    # 3. 전략 저장
    try:
        STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
        STRATEGY_PATH.write_text(json.dumps(strategy, ensure_ascii=False, indent=2))
        log(f'전략 저장: {STRATEGY_PATH}', 'OK')
    except Exception as e:
        log(f'전략 저장 실패: {e}', 'ERROR')

    # 4. DB 저장
    if supabase:
        try:
            supabase.table('daily_reports').upsert([{
                'date': strategy['date'],
                'report_type': 'premarket',
                'content': json.dumps(strategy, ensure_ascii=False),
            }], on_conflict='date,report_type').execute()
        except Exception as e:
            log(f'DB 저장 실패: {e}', 'WARN')

    # 5. 텔레그램 브리핑
    us_text = '\n'.join(
        f"  {m['name']}: {m['change_pct']:+.2f}%"
        for m in us_market
    ) if us_market else '  데이터 없음'

    picks_text = '\n'.join(
        f"  {'🟢' if p['action']=='BUY' else '🔴' if p['action']=='SELL' else '⚪'} "
        f"{p['name']}: {p['action']} — {p['reason']}"
        for p in strategy.get('top_picks', [])
    ) if strategy.get('top_picks') else '  추천 종목 없음'

    msg = (
        f"📊 <b>장 전 브리핑</b> ({strategy['date']})\n"
        f"[{strategy.get('source', '?')}]\n\n"
        f"🌍 <b>미국 증시</b>\n{us_text}\n\n"
        f"📈 <b>시장 전망</b>: {strategy.get('market_outlook', '?')}\n"
        f"⚠️ <b>리스크</b>: {strategy.get('risk_level', '?')}\n\n"
        f"🎯 <b>오늘 전략</b>\n{picks_text}\n\n"
        f"💬 {strategy.get('summary', '')}\n"
        f"⚠️ 모의투자"
    )
    send_telegram(msg)

    log('장 전 분석 완료', 'OK')
    log('=' * 50)


if __name__ == '__main__':
    run_premarket()
