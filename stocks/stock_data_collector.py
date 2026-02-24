#!/usr/bin/env python3
"""
주식 데이터 수집기
- DART: top50 종목 + 재무제표
- 키움: OHLCV 데이터
"""

import os, json, time, requests, sys
from datetime import datetime, timedelta
from pathlib import Path
from supabase import create_client

# env 로드
def _load_env():
    openclaw_json = Path('/home/wlsdud5035/.openclaw/openclaw.json')
    if openclaw_json.exists():
        d = json.loads(openclaw_json.read_text())
        for k,v in (d.get('env') or {}).items():
            if isinstance(v,str): os.environ.setdefault(k,v)
    for p in [
        Path('/home/wlsdud5035/.openclaw/.env'),
        Path('/home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env'),
    ]:
        if not p.exists(): continue
        for line in p.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k,_,v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
_load_env()

DART_KEY = os.environ.get('DART_API_KEY', '') or os.environ.get('OPENDART_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '') or os.environ.get('SUPABASE_KEY', '')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None

# KOSPI 주요 종목 (top50 대신 핵심 30개)
TOP_STOCKS = [
    {"code": "005930", "name": "삼성전자",     "industry": "반도체"},
    {"code": "000660", "name": "SK하이닉스",   "industry": "반도체"},
    {"code": "042700", "name": "한미반도체",   "industry": "반도체장비"},
    {"code": "035420", "name": "NAVER",        "industry": "IT"},
    {"code": "035720", "name": "카카오",       "industry": "IT"},
    {"code": "005380", "name": "현대차",       "industry": "자동차"},
    {"code": "000270", "name": "기아",         "industry": "자동차"},
    {"code": "068270", "name": "셀트리온",     "industry": "바이오"},
    {"code": "207940", "name": "삼성바이오로직스", "industry": "바이오"},
    {"code": "006400", "name": "삼성SDI",      "industry": "배터리"},
    {"code": "051910", "name": "LG화학",       "industry": "배터리"},
    {"code": "373220", "name": "LG에너지솔루션", "industry": "배터리"},
    {"code": "003550", "name": "LG",           "industry": "지주"},
    {"code": "012330", "name": "현대모비스",   "industry": "자동차부품"},
    {"code": "028260", "name": "삼성물산",     "industry": "건설"},
    {"code": "034730", "name": "SK",           "industry": "지주"},
    {"code": "015760", "name": "한국전력",     "industry": "에너지"},
    {"code": "032830", "name": "삼성생명",     "industry": "금융"},
    {"code": "105560", "name": "KB금융",       "industry": "금융"},
    {"code": "055550", "name": "신한지주",     "industry": "금융"},
]

def get_dart_corp_code(stock_code: str) -> str:
    """DART corp_code 조회 (종목코드 → corp_code 변환)"""
    try:
        res = requests.get(
            'https://opendart.fss.or.kr/api/company.json',
            params={'crtfc_key': DART_KEY, 'stock_code': stock_code},
            timeout=5
        )
        data = res.json()
        if data.get('status') == '000':
            return data.get('corp_code', '')
    except Exception as e:
        print(f'DART corp_code 조회 실패 {stock_code}: {e}')
    return ''

def get_dart_financials(corp_code: str, stock_code: str) -> dict:
    """DART 재무제표 조회"""
    try:
        year = str(datetime.now().year - 1)
        res = requests.get(
            'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',
            params={
                'crtfc_key': DART_KEY,
                'corp_code': corp_code,
                'bsns_year': year,
                'reprt_code': '11011',  # 사업보고서
                'fs_div': 'CFS',        # 연결재무제표
            },
            timeout=10
        )
        data = res.json()
        if data.get('status') != '000':
            return {}

        result = {}
        for item in data.get('list', []):
            name = item.get('account_nm', '')
            val = item.get('thstrm_amount', '0').replace(',', '')
            try:
                val = float(val)
            except Exception:
                val = 0.0

            if '매출액' in name and 'revenue' not in result:
                result['revenue'] = val
            elif '영업이익' in name and 'operating_income' not in result:
                result['operating_income'] = val
            elif '당기순이익' in name and 'net_income' not in result:
                result['net_income'] = val

        return result
    except Exception as e:
        print(f'DART 재무제표 조회 실패 {corp_code}: {e}')
        return {}

def collect_top50():
    """top50_stocks 테이블 채우기"""
    if not supabase:
        print('❌ Supabase 연결 없음')
        return
    print(f'\n[{datetime.now()}] top50_stocks 수집 시작')
    success = 0
    for stock in TOP_STOCKS:
        try:
            supabase.table('top50_stocks').upsert({
                'stock_code': stock['code'],
                'stock_name': stock['name'],
                'industry':   stock['industry'],
                'volume':     0,
                'market_cap': 0,
            }).execute()
            success += 1
            print(f'  ✅ {stock["name"]} ({stock["code"]})')
        except Exception as e:
            print(f'  ❌ {stock["name"]}: {e}')
        time.sleep(0.2)

    print(f'top50_stocks 완료: {success}/{len(TOP_STOCKS)}')

def collect_financials():
    """financial_statements 테이블 채우기 (DART)"""
    if not supabase:
        print('❌ Supabase 연결 없음')
        return
    if not DART_KEY:
        print('❌ DART_API_KEY 없음')
        return

    print(f'\n[{datetime.now()}] financial_statements 수집 시작')
    success = 0
    for stock in TOP_STOCKS[:10]:
        print(f'  {stock["name"]} 재무 조회 중...')
        corp_code = get_dart_corp_code(stock['code'])
        if not corp_code:
            print(f'  ❌ {stock["name"]} corp_code 없음')
            continue

        financials = get_dart_financials(corp_code, stock['code'])
        if not financials:
            print(f'  ❌ {stock["name"]} 재무 없음')
            continue

        try:
            supabase.table('financial_statements').upsert({
                'stock_code':       stock['code'],
                'revenue':          financials.get('revenue', 0),
                'operating_income': financials.get('operating_income', 0),
                'net_income':       financials.get('net_income', 0),
                'per':              0,
                'pbr':              0,
                'roe':              0,
            }).execute()
            success += 1
            print(f'  ✅ {stock["name"]} 재무 저장')
        except Exception as e:
            print(f'  ❌ {stock["name"]} 저장 실패: {e}')

        time.sleep(1)

    print(f'financial_statements 완료: {success}개')

def collect_ohlcv():
    """daily_ohlcv 테이블 채우기 (yfinance)"""
    if not supabase:
        print('❌ Supabase 연결 없음')
        return
    print(f'\n[{datetime.now()}] daily_ohlcv 수집 시작')
    try:
        import yfinance as yf
    except Exception:
        print('❌ yfinance 없음')
        return

    success = 0
    for stock in TOP_STOCKS:
        try:
            ticker = yf.Ticker(stock['code'] + '.KS')
            hist = ticker.history(period='30d')
            if hist.empty:
                print(f'  ❌ {stock["name"]} 데이터 없음')
                continue

            rows = []
            for date, row in hist.iterrows():
                rows.append({
                    'stock_code':  stock['code'],
                    'date':        date.date().isoformat(),
                    'open_price':  float(row['Open']),
                    'high_price':  float(row['High']),
                    'low_price':   float(row['Low']),
                    'close_price': float(row['Close']),
                    'volume':      int(row['Volume']),
                })

            supabase.table('daily_ohlcv').upsert(rows).execute()
            success += 1
            print(f'  ✅ {stock["name"]} {len(rows)}일치 저장')
        except Exception as e:
            print(f'  ❌ {stock["name"]}: {e}')
        time.sleep(0.5)

    print(f'daily_ohlcv 완료: {success}/{len(TOP_STOCKS)}')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if cmd == 'top50' or cmd == 'all':
        collect_top50()
    if cmd == 'financials' or cmd == 'all':
        collect_financials()
    if cmd == 'ohlcv' or cmd == 'all':
        collect_ohlcv()

    print('\n✅ 데이터 수집 완료')
