#!/usr/bin/env python3
"""
주식 데이터 수집기 v2.0

변경사항 (v1 → v2):
- [FIX] yfinance 실패 시 개별 종목 스킵 (전체 중단 방지)
- [FIX] upsert 충돌 처리 개선
- [NEW] 분봉 데이터 수집 (5분/1시간) — 장 중 실시간용
- [NEW] 수집 결과 요약 리포트
- [NEW] 텔레그램 알림 (수집 실패 시)
- [NEW] DART 재무제표 에러 핸들링 강화
- [REFACTOR] 공통 함수 분리, 로깅 개선

사용법:
    python3 stock_data_collector.py ohlcv        # 일봉 30일치
    python3 stock_data_collector.py intraday     # 분봉 (5분/1시간)
    python3 stock_data_collector.py top50        # 종목 기본정보
    python3 stock_data_collector.py financials   # DART 재무제표
    python3 stock_data_collector.py all          # 전체
"""

import os
import json
import time
import sys
import requests
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

from supabase import create_client

DART_KEY = os.environ.get('DART_API_KEY', '') or os.environ.get('OPENDART_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '') or os.environ.get('SUPABASE_KEY', '')
TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None

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
    except Exception:
        pass


# KOSPI 핵심 종목 (20개)
TOP_STOCKS = [
    {"code": "005930", "name": "삼성전자",     "industry": "반도체"},
    {"code": "000660", "name": "SK하이닉스",   "industry": "반도체"},
    {"code": "042700", "name": "한미반도체",   "industry": "반도체장비"},
    {"code": "005380", "name": "현대차",       "industry": "자동차"},
    {"code": "000270", "name": "기아",         "industry": "자동차"},
    {"code": "068270", "name": "셀트리온",     "industry": "바이오"},
    {"code": "035420", "name": "NAVER",        "industry": "IT/플랫폼"},
    {"code": "035720", "name": "카카오",       "industry": "IT/플랫폼"},
    {"code": "051910", "name": "LG화학",       "industry": "화학/배터리"},
    {"code": "006400", "name": "삼성SDI",      "industry": "배터리"},
    {"code": "003670", "name": "포스코퓨처엠", "industry": "2차전지소재"},
    {"code": "373220", "name": "LG에너지솔루션","industry": "배터리"},
    {"code": "055550", "name": "신한지주",     "industry": "금융"},
    {"code": "105560", "name": "KB금융",       "industry": "금융"},
    {"code": "034730", "name": "SK",           "industry": "지주"},
    {"code": "012330", "name": "현대모비스",   "industry": "자동차부품"},
    {"code": "066570", "name": "LG전자",       "industry": "전자"},
    {"code": "028260", "name": "삼성물산",     "industry": "건설/지주"},
    {"code": "207940", "name": "삼성바이오로직스","industry": "바이오"},
    {"code": "003550", "name": "LG",           "industry": "지주"},
]


# ─────────────────────────────────────────────
# 종목 기본정보 (top50)
# ─────────────────────────────────────────────
def collect_top50():
    """종목 기본정보를 Supabase에 저장"""
    if not supabase:
        log('Supabase 미연결', 'ERROR')
        return

    log(f'종목 기본정보 수집 시작 ({len(TOP_STOCKS)}개)')
    rows = []
    for s in TOP_STOCKS:
        rows.append({
            'stock_code': s['code'],
            'stock_name': s['name'],
            'industry': s.get('industry', ''),
            'market': 'KOSPI',
            'updated_at': datetime.now().isoformat(),
        })

    try:
        supabase.table('top50_stocks').upsert(rows, on_conflict='stock_code').execute()
        log(f'종목 기본정보 {len(rows)}개 저장 완료', 'OK')
    except Exception as e:
        log(f'종목 기본정보 저장 실패: {e}', 'ERROR')


# ─────────────────────────────────────────────
# 일봉 OHLCV 수집
# ─────────────────────────────────────────────
def collect_ohlcv():
    """yfinance로 20종목 30일치 일봉 수집 → daily_ohlcv"""
    if not supabase:
        log('Supabase 미연결', 'ERROR')
        return

    try:
        import yfinance as yf
    except ImportError:
        log('yfinance 미설치. pip install yfinance', 'ERROR')
        return

    log(f'일봉 OHLCV 수집 시작 ({len(TOP_STOCKS)}개)')
    success_count = 0
    fail_count = 0
    total_rows = 0

    for stock in TOP_STOCKS:
        code = stock['code']
        name = stock['name']
        try:
            ticker = yf.Ticker(code + '.KS')
            hist = ticker.history(period='30d')

            if hist.empty:
                log(f'  {name} ({code}): 데이터 없음', 'WARN')
                fail_count += 1
                continue

            rows = []
            for date, row in hist.iterrows():
                rows.append({
                    'stock_code': code,
                    'date': date.strftime('%Y-%m-%d'),
                    'open_price': round(float(row['Open']), 0),
                    'high_price': round(float(row['High']), 0),
                    'low_price': round(float(row['Low']), 0),
                    'close_price': round(float(row['Close']), 0),
                    'volume': int(row['Volume']),
                })

            if rows:
                supabase.table('daily_ohlcv').upsert(
                    rows, on_conflict='stock_code,date'
                ).execute()
                total_rows += len(rows)
                success_count += 1
                log(f'  {name}: {len(rows)}일치 저장')

            time.sleep(0.5)  # yfinance rate limit

        except Exception as e:
            log(f'  {name} ({code}) 실패: {e}', 'ERROR')
            fail_count += 1
            continue  # 개별 종목 실패 시 다음으로 계속

    log(f'일봉 수집 완료: 성공 {success_count} / 실패 {fail_count} / 총 {total_rows}행', 'OK')

    if fail_count > 0:
        send_telegram(
            f'⚠️ <b>OHLCV 수집 일부 실패</b>\n'
            f'성공: {success_count} / 실패: {fail_count}'
        )


# ─────────────────────────────────────────────
# 분봉 데이터 수집 (NEW)
# ─────────────────────────────────────────────
def collect_intraday():
    """
    yfinance로 5분봉/1시간봉 수집 → intraday_ohlcv 테이블
    장 중에 실행하면 당일 분봉, 장 외에 실행하면 최근 5일 분봉 수집

    Note: Supabase에 intraday_ohlcv 테이블이 필요합니다.
    migration_v2.sql 참고.
    """
    if not supabase:
        log('Supabase 미연결', 'ERROR')
        return

    try:
        import yfinance as yf
    except ImportError:
        log('yfinance 미설치', 'ERROR')
        return

    intervals = [
        ('5m', '5d'),    # 5분봉: 최근 5일 (yfinance 제한)
        ('1h', '30d'),   # 1시간봉: 최근 30일
    ]

    log(f'분봉 데이터 수집 시작 ({len(TOP_STOCKS)}개 × {len(intervals)}개 인터벌)')

    for interval, period in intervals:
        success = 0
        fail = 0
        total = 0

        for stock in TOP_STOCKS:
            code = stock['code']
            name = stock['name']
            try:
                ticker = yf.Ticker(code + '.KS')
                hist = ticker.history(period=period, interval=interval)

                if hist.empty:
                    fail += 1
                    continue

                rows = []
                for dt, row in hist.iterrows():
                    rows.append({
                        'stock_code': code,
                        'datetime': dt.isoformat(),
                        'time_interval': interval,
                        'open_price': round(float(row['Open']), 0),
                        'high_price': round(float(row['High']), 0),
                        'low_price': round(float(row['Low']), 0),
                        'close_price': round(float(row['Close']), 0),
                        'volume': int(row['Volume']),
                    })

                if rows:
                    for i in range(0, len(rows), 500):
                        batch = rows[i:i+500]
                        supabase.table('intraday_ohlcv').upsert(
                            batch, on_conflict='stock_code,datetime,time_interval'
                        ).execute()
                    total += len(rows)
                    success += 1

                time.sleep(0.5)

            except Exception as e:
                log(f'  {name} {interval} 실패: {e}', 'ERROR')
                fail += 1
                continue

        log(f'{interval} 수집 완료: 성공 {success} / 실패 {fail} / 총 {total}행', 'OK')


# ─────────────────────────────────────────────
# DART 재무제표
# ─────────────────────────────────────────────
def get_dart_corp_code(stock_code: str) -> str:
    """종목코드 → DART 고유번호 변환"""
    if not DART_KEY:
        return ''
    try:
        import zipfile
        import io
        import xml.etree.ElementTree as ET

        cache_path = Path('/tmp/dart_corp_codes.json')
        if cache_path.exists():
            codes = json.loads(cache_path.read_text())
            if stock_code in codes:
                return codes[stock_code]

        url = f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_KEY}'
        res = requests.get(url, timeout=30)

        codes = {}
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                tree = ET.parse(f)
                for item in tree.getroot().findall('list'):
                    sc = item.findtext('stock_code', '').strip()
                    cc = item.findtext('corp_code', '').strip()
                    if sc:
                        codes[sc] = cc

        cache_path.write_text(json.dumps(codes))
        return codes.get(stock_code, '')

    except Exception as e:
        log(f'DART 기업코드 조회 실패: {e}', 'ERROR')
        return ''


def get_dart_financials(corp_code: str, stock_code: str) -> dict:
    """DART에서 재무제표 조회"""
    if not DART_KEY or not corp_code:
        return {}
    try:
        year = datetime.now().year - 1
        url = (
            f'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json'
            f'?crtfc_key={DART_KEY}'
            f'&corp_code={corp_code}'
            f'&bsns_year={year}'
            f'&reprt_code=11011'  # 사업보고서
            f'&fs_div=CFS'  # 연결재무제표
        )
        res = requests.get(url, timeout=15)
        data = res.json()

        if data.get('status') != '000':
            return {}

        items = data.get('list', [])
        result = {}
        key_items = {
            '매출액': 'revenue',
            '영업이익': 'operating_profit',
            '당기순이익': 'net_income',
            '자산총계': 'total_assets',
            '부채총계': 'total_liabilities',
            '자본총계': 'total_equity',
        }
        for item in items:
            name = item.get('account_nm', '')
            for kr, en in key_items.items():
                if kr in name:
                    val = item.get('thstrm_amount', '0').replace(',', '')
                    try:
                        result[en] = int(val)
                    except ValueError:
                        result[en] = 0
                    break

        return result

    except Exception as e:
        log(f'DART 재무제표 조회 실패 {stock_code}: {e}', 'ERROR')
        return {}


def collect_financials():
    """20종목 재무제표 수집"""
    if not DART_KEY:
        log('DART API 키 없음 (OPENDART_API_KEY 환경변수 설정 필요)', 'ERROR')
        return

    if not supabase:
        log('Supabase 미연결', 'ERROR')
        return

    log(f'재무제표 수집 시작 ({len(TOP_STOCKS)}개)')
    success = 0

    for stock in TOP_STOCKS:
        code = stock['code']
        name = stock['name']
        try:
            corp_code = get_dart_corp_code(code)
            if not corp_code:
                log(f'  {name}: DART 기업코드 없음', 'WARN')
                continue

            financials = get_dart_financials(corp_code, code)
            if not financials:
                log(f'  {name}: 재무제표 데이터 없음', 'WARN')
                continue

            row = {
                'stock_code': code,
                'stock_name': name,
                'fiscal_year': datetime.now().year - 1,
                **financials,
                'updated_at': datetime.now().isoformat(),
            }

            supabase.table('financial_statements').upsert(
                [row], on_conflict='stock_code,fiscal_year'
            ).execute()

            success += 1
            log(f'  {name}: 재무제표 저장 완료')
            time.sleep(1)  # DART rate limit

        except Exception as e:
            log(f'  {name} 실패: {e}', 'ERROR')
            continue

    log(f'재무제표 수집 완료: {success}/{len(TOP_STOCKS)}', 'OK')


# ─────────────────────────────────────────────
# 오래된 데이터 정리
# ─────────────────────────────────────────────
def cleanup_old_data():
    """90일 이상 된 일봉, 7일 이상 된 분봉 삭제"""
    if not supabase:
        return

    try:
        cutoff_daily = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        supabase.table('daily_ohlcv').delete().lt('date', cutoff_daily).execute()
        log('90일 이전 일봉 데이터 정리 완료', 'OK')
    except Exception as e:
        log(f'일봉 정리 실패: {e}', 'WARN')

    try:
        cutoff_intraday = (datetime.now() - timedelta(days=7)).isoformat()
        supabase.table('intraday_ohlcv').delete().lt('datetime', cutoff_intraday).execute()
        log('7일 이전 분봉 데이터 정리 완료', 'OK')
    except Exception as e:
        log(f'분봉 정리 실패 (테이블 없을 수 있음): {e}', 'WARN')


# ─────────────────────────────────────────────
# 엔트리포인트
# ─────────────────────────────────────────────
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'

    log(f'데이터 수집기 시작: {cmd}')

    if cmd == 'top50' or cmd == 'all':
        collect_top50()
    if cmd == 'financials' or cmd == 'all':
        collect_financials()
    if cmd == 'ohlcv' or cmd == 'all':
        collect_ohlcv()
    if cmd == 'intraday':
        collect_intraday()
    if cmd == 'cleanup':
        cleanup_old_data()
    if cmd == 'all':
        cleanup_old_data()

    log('데이터 수집 완료', 'OK')
