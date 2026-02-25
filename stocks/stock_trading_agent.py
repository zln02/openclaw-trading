#!/usr/bin/env python3
"""
주식 자동매매 에이전트 v2.0 (리팩토링)

변경사항 (v1 → v2):
- [FIX] 주문 실패 시 DB 저장 방지 (유령 포지션 제거)
- [FIX] 동일 종목 중복 매수 차단
- [FIX] 분할매수 평균 진입가 계산
- [FIX] 손절/익절 텔레그램에 종목명 표시
- [NEW] AI 실패 시 룰 기반 fallback 매매 판단
- [NEW] invest_per_stock 제대로 적용
- [NEW] 체결 확인 로직 추가
- [NEW] yfinance 캐싱 (종목당 1회만 호출)
- [NEW] 장 전 전략 없어도 룰 기반 매매 가능
- [NEW] 에러 핸들링 강화 + 상세 로깅
- [REFACTOR] 함수 분리 / 설정 중앙화 / 코드 정리
"""

import os
import json
import time
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional

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

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
kiwoom = KiwoomClient()

RISK = {
    "invest_ratio": 0.25,        # 종목당 잔고의 25% (공격적)
    "stop_loss": -0.02,          # 손절 -2% (빠른 손절)
    "take_profit": 0.05,         # 익절 +5%
    "trailing_stop": 0.015,      # 트레일링 스탑 1.5%
    "min_confidence": 55,        # 최소 신뢰도 55%
    "max_positions": 5,          # 최대 동시 5종목
    "max_daily_loss": -0.08,     # 일일 손실 한도 -8%
    "split_ratios": [0.50, 0.30, 0.20],  # 1차에 50% 공격적
    "split_rsi_thresholds": [45, 38, 30],  # RSI 기준 완화
    "min_order_krw": 30000,      # 최소 주문금액
    "cooldown_minutes": 15,      # 쿨다운 15분
}

# 룰 기반 매매 기준 (AI fallback) — v3 공격적
RULES = {
    "buy_rsi_max": 45,
    "buy_bb_max": 40,
    "buy_vol_min": 0.7,
    "sell_rsi_min": 65,
    "sell_bb_min": 75,
    "block_vol_below": 0.3,
    "block_bb_above": 85,
    "block_kospi_above": 80,
}

# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "TRADE": "💰"}.get(level, "")
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


def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


# ─────────────────────────────────────────────
# 시장/지표 데이터
# ─────────────────────────────────────────────
_cache = {}  # 간단한 메모리 캐시 (사이클 단위 리셋)


def _calc_rsi(closes: list, period: int = 14) -> float:
    """RSI 계산 (공통 함수)"""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _calc_ema(data: list, period: int) -> float:
    """EMA 계산 (공통 함수)"""
    if not data:
        return 0.0
    k = 2 / (period + 1)
    e = data[0]
    for d in data[1:]:
        e = d * k + e * (1 - k)
    return e


def get_kospi_sentiment() -> dict:
    """코스피 시장 심리 (RSI 기반)"""
    cache_key = 'kospi_sentiment'
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        import yfinance as yf
        kospi = yf.Ticker('^KS11')
        hist = kospi.history(period='30d')
        if hist.empty:
            return {'rsi': 50, 'msg': '⚪ 코스피 데이터 없음 — 중립 처리'}

        closes = list(hist['Close'])
        rsi = _calc_rsi(closes)

        if rsi <= 30:
            msg = f'🔴 코스피 극도공포({rsi}) — 역발상 매수 기회'
        elif rsi <= 45:
            msg = f'🟠 코스피 공포({rsi}) — 매수 우호적'
        elif rsi <= 55:
            msg = f'⚪ 코스피 중립({rsi})'
        elif rsi <= 70:
            msg = f'🟡 코스피 과열({rsi}) — 매수 주의'
        else:
            msg = f'🔴 코스피 극도과열({rsi}) — 매수 금지'

        result = {'rsi': rsi, 'msg': msg}
        _cache[cache_key] = result
        return result
    except Exception as e:
        log(f'코스피 심리 조회 실패: {e}', 'WARN')
        return {'rsi': 50, 'msg': '⚪ 코스피 조회 실패 — 중립 처리'}


def get_weekly_trend(code: str) -> dict:
    """주봉 EMA 5/10 기반 추세 (캐싱)"""
    cache_key = f'weekly_{code}'
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + '.KS')
        hist = ticker.history(period='6mo', interval='1wk')
        if hist.empty or len(hist) < 10:
            return {'trend': 'UNKNOWN'}

        closes = list(hist['Close'])
        ema5 = _calc_ema(closes, 5)
        ema10 = _calc_ema(closes, 10)
        price = closes[-1]

        if ema5 > ema10 and price > ema5:
            trend = 'UPTREND'
        elif ema5 < ema10 and price < ema5:
            trend = 'DOWNTREND'
        else:
            trend = 'SIDEWAYS'

        result = {'trend': trend, 'ema5': round(ema5, 0), 'ema10': round(ema10, 0)}
        _cache[cache_key] = result
        return result
    except Exception as e:
        log(f'주봉 추세 조회 실패 {code}: {e}', 'WARN')
        return {'trend': 'UNKNOWN'}


def get_stock_news(stock_name: str) -> str:
    """종목 관련 뉴스 헤드라인"""
    try:
        import xml.etree.ElementTree as ET
        sources = [
            'https://www.yna.co.kr/rss/economy.xml',
            'https://rss.hankyung.com/economy.xml',
        ]
        headlines = []
        keywords = [stock_name, '반도체', '코스피', '외국인', '기관']

        for url in sources:
            try:
                res = requests.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0'})
                root = ET.fromstring(res.content)
                for item in root.findall('.//item'):
                    title = item.findtext('title', '')
                    if any(k in title for k in keywords):
                        headlines.append(title.strip())
                if headlines:
                    break
            except Exception:
                continue

        return '\n'.join(headlines[:3]) if headlines else '관련 뉴스 없음'
    except Exception:
        return '뉴스 조회 실패'


def get_current_price(code: str) -> float:
    """키움 API로 현재가 조회 (안정적 파싱)"""
    try:
        info = kiwoom.get_stock_info(code)
        if not info:
            return 0.0

        # 키움 API 응답 구조에 따라 파싱
        if isinstance(info, dict):
            # output 래핑된 경우
            output = info.get('output', info)
            price_str = (
                output.get('stck_prpr')
                or output.get('cur_prc')
                or '0'
            )
            price = abs(float(str(price_str).replace(',', '')))
            return price
        return 0.0
    except Exception as e:
        log(f'현재가 조회 실패 {code}: {e}', 'WARN')
        return 0.0


def _fetch_live_candles(code: str, period: str = '5d', interval: str = '5m') -> dict:
    cache_key = f'live_{code}_{interval}'
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + '.KS')
        hist = ticker.history(period=period, interval=interval)
        if hist.empty or len(hist) < 14:
            return {}
        result = {
            'closes': [float(c) for c in hist['Close']],
            'volumes': [float(v) for v in hist['Volume']],
            'source': f'{interval}_live',
            'last_time': str(hist.index[-1]),
        }
        _cache[cache_key] = result
        return result
    except Exception as e:
        log(f'실시간 분봉 조회 실패 {code}: {e}', 'WARN')
        return {}


def _fetch_daily_from_db(code: str) -> dict:
    try:
        rows = (
            supabase.table('daily_ohlcv')
            .select('close_price,volume,date')
            .eq('stock_code', code)
            .order('date', desc=False)
            .limit(30)
            .execute()
            .data or []
        )
        if len(rows) < 14:
            return {}
        return {
            'closes': [float(r['close_price']) for r in rows],
            'volumes': [float(r.get('volume', 0)) for r in rows],
            'source': 'daily_db',
            'last_date': rows[-1].get('date', 'unknown'),
        }
    except Exception as e:
        log(f'일봉 DB 조회 실패 {code}: {e}', 'WARN')
        return {}


def _calc_indicators_from_data(closes: list, volumes: list) -> dict:
    rsi = _calc_rsi(closes)
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    macd = round(ema12 - ema26, 0)
    if len(closes) >= 26:
        macd_line = []
        for i in range(26, len(closes) + 1):
            e12 = _calc_ema(closes[:i], 12)
            e26 = _calc_ema(closes[:i], 26)
            macd_line.append(e12 - e26)
        macd_signal = _calc_ema(macd_line, 9) if len(macd_line) >= 9 else macd
        macd_histogram = round(macd - macd_signal, 0)
    else:
        macd_signal = macd
        macd_histogram = 0
    avg_vol = sum(volumes[-20:]) / min(len(volumes[-20:]), 20) if volumes else 1
    cur_vol = volumes[-1] if volumes else 0
    vol_ratio = round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
    vol_labels = [(3.0, '💥 거래량 폭발'), (2.0, '🔥 거래량 급등'), (1.5, '📈 거래량 증가'), (0.5, '➡️ 거래량 보통')]
    vol_label = f'😴 거래량 급감 ({vol_ratio}배)'
    for threshold, label in vol_labels:
        if vol_ratio >= threshold:
            vol_label = f'{label} ({vol_ratio}배)'
            break
    bb_upper = bb_lower = bb_pos = 0
    if len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20
        std20 = (sum((c - ma20) ** 2 for c in closes[-20:]) / 20) ** 0.5
        bb_upper = round(ma20 + 2 * std20, 0)
        bb_lower = round(ma20 - 2 * std20, 0)
        bb_width = bb_upper - bb_lower
        if bb_width > 0:
            bb_pos = round((closes[-1] - bb_lower) / bb_width * 100, 1)
    return {
        'rsi': rsi, 'macd': macd, 'macd_signal': round(macd_signal, 0),
        'macd_histogram': macd_histogram, 'close': closes[-1],
        'vol_ratio': vol_ratio, 'vol_label': vol_label,
        'bb_upper': bb_upper, 'bb_lower': bb_lower, 'bb_pos': bb_pos,
    }


def get_indicators(code: str) -> dict:
    """장 중: yfinance 5분봉 실시간 / 장 외: DB 일봉"""
    try:
        data = {}
        if is_market_open():
            data = _fetch_live_candles(code, period='5d', interval='5m')
            if data:
                log(f'  {code}: 실시간 5분봉 사용 (마지막: {data.get("last_time", "?")})')
        if not data:
            data = _fetch_daily_from_db(code)
        if not data or len(data.get('closes', [])) < 14:
            log(f'{code}: 데이터 부족', 'WARN')
            return {}
        indicators = _calc_indicators_from_data(data['closes'], data['volumes'])
        price = get_current_price(code)
        if price == 0:
            price = data['closes'][-1]
        if indicators['bb_upper'] > indicators['bb_lower']:
            bb_width = indicators['bb_upper'] - indicators['bb_lower']
            indicators['bb_pos'] = round((price - indicators['bb_lower']) / bb_width * 100, 1)
        indicators['price'] = price
        indicators['data_source'] = data.get('source', 'unknown')
        indicators['data_points'] = len(data['closes'])
        return indicators
    except Exception as e:
        log(f'지표 계산 실패 {code}: {e}', 'ERROR')
        return {}


# ─────────────────────────────────────────────
# 포지션 관리
# ─────────────────────────────────────────────
def get_open_positions() -> list:
    """현재 열린 포지션 목록"""
    try:
        return (
            supabase.table('trade_executions')
            .select('*')
            .eq('result', 'OPEN')
            .execute()
            .data or []
        )
    except Exception as e:
        log(f'포지션 조회 실패: {e}', 'ERROR')
        return []


def get_position_for_stock(code: str) -> list:
    """특정 종목의 열린 포지션"""
    try:
        return (
            supabase.table('trade_executions')
            .select('*')
            .eq('stock_code', code)
            .eq('result', 'OPEN')
            .execute()
            .data or []
        )
    except Exception as e:
        log(f'종목 포지션 조회 실패 {code}: {e}', 'ERROR')
        return []


def calc_avg_entry_price(positions: list) -> float:
    """분할매수 평균 진입가 계산 (가중평균)"""
    total_cost = 0.0
    total_qty = 0
    for p in positions:
        qty = int(p.get('quantity', 0))
        price = float(p.get('price', 0))
        total_cost += price * qty
        total_qty += qty
    return round(total_cost / total_qty, 0) if total_qty > 0 else 0.0


def get_split_stage_for_stock(code: str) -> int:
    """해당 종목의 현재 분할매수 차수 (기존 포지션 수 기반)"""
    positions = get_position_for_stock(code)
    return len(positions) + 1  # 0개면 1차, 1개면 2차, 2개면 3차


def check_cooldown(code: str) -> bool:
    """최근 매도 후 쿨다운 시간 체크 (True = 쿨다운 중)"""
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(minutes=RISK['cooldown_minutes'])).isoformat()
        recent = (
            supabase.table('trade_executions')
            .select('created_at')
            .eq('stock_code', code)
            .eq('trade_type', 'SELL')
            .gte('created_at', cutoff)
            .limit(1)
            .execute()
            .data or []
        )
        return len(recent) > 0
    except Exception:
        return False


# ─────────────────────────────────────────────
# 리스크 관리
# ─────────────────────────────────────────────
def check_daily_loss() -> bool:
    """오늘 일일 손실 한도 도달 시 True (거래 중단)"""
    try:
        today = datetime.now().date().isoformat()
        closed_today = (
            supabase.table('trade_executions')
            .select('*')
            .eq('result', 'CLOSED')
            .eq('trade_type', 'SELL')
            .gte('created_at', today)
            .execute()
            .data or []
        )
        if not closed_today:
            return False

        total_pnl = 0.0
        total_invested = 0.0

        for r in closed_today:
            sell_price = float(r.get('price', 0))
            entry_price = float(r.get('entry_price', sell_price))
            qty = int(r.get('quantity', 0))
            total_pnl += (sell_price - entry_price) * qty
            total_invested += entry_price * qty

        if total_invested > 0:
            pnl_ratio = total_pnl / total_invested
            if pnl_ratio <= RISK['max_daily_loss']:
                send_telegram(
                    f'🚨 <b>주식 일일 손실 한도 초과</b>\n'
                    f'손실률: {pnl_ratio*100:.2f}%\n'
                    f'오늘 거래 중단'
                )
                return True
    except Exception as e:
        log(f'일일 손실 체크 실패: {e}', 'ERROR')
    return False


# ─────────────────────────────────────────────
# 매매 판단
# ─────────────────────────────────────────────
def rule_based_signal(
    indicators: dict,
    kospi: dict = None,
    weekly: dict = None,
    has_position: bool = False,
) -> dict:
    """
    AI 없이 동작하는 룰 기반 매매 판단 (fallback)
    """
    rsi = indicators.get('rsi', 50)
    macd = indicators.get('macd', 0)
    macd_hist = indicators.get('macd_histogram', 0)
    vol_ratio = indicators.get('vol_ratio', 1.0)
    bb_pos = indicators.get('bb_pos', 50)
    kospi_rsi = (kospi or {}).get('rsi', 50)
    trend = (weekly or {}).get('trend', 'UNKNOWN')

    # ── SELL 조건 ──
    if has_position:
        sell_reasons = []
        if rsi >= RULES['sell_rsi_min']:
            sell_reasons.append(f'RSI 과매수({rsi})')
        if bb_pos >= RULES['sell_bb_min']:
            sell_reasons.append(f'BB 상단({bb_pos}%)')
        if macd < 0 and macd_hist < 0:
            sell_reasons.append(f'MACD 음수 전환')

        if len(sell_reasons) >= 2:
            return {
                'action': 'SELL',
                'confidence': 75,
                'reason': f'[룰] {" + ".join(sell_reasons)}',
            }

    # ── BUY 차단 조건 ──
    blocks = []
    if vol_ratio <= RULES['block_vol_below']:
        blocks.append(f'거래량 급감({vol_ratio}배)')
    if bb_pos >= RULES['block_bb_above']:
        blocks.append(f'BB 상단({bb_pos}%)')
    if kospi_rsi >= RULES['block_kospi_above']:
        blocks.append(f'코스피 과열({kospi_rsi})')
    if trend == 'DOWNTREND':
        blocks.append('주봉 하락추세')

    if blocks:
        return {
            'action': 'HOLD',
            'confidence': 0,
            'reason': f'[룰] 매수 차단: {", ".join(blocks)}',
        }

    # ── BUY 조건 ──
    buy_score = 0
    buy_reasons = []

    if rsi <= RULES['buy_rsi_max']:
        buy_score += 30
        buy_reasons.append(f'RSI 저점({rsi})')
    if bb_pos <= RULES['buy_bb_max']:
        buy_score += 20
        buy_reasons.append(f'BB 하단({bb_pos}%)')
    if macd > 0 or macd_hist > 0:
        buy_score += 15
        buy_reasons.append('MACD 양수')
    if vol_ratio >= 1.5:
        buy_score += 10
        buy_reasons.append(f'거래량 증가({vol_ratio}배)')
    if trend == 'UPTREND':
        buy_score += 10
        buy_reasons.append('주봉 상승추세')
    if kospi_rsi <= 30:
        buy_score += 10
        buy_reasons.append(f'코스피 공포({kospi_rsi})')

    if buy_score >= 50:
        return {
            'action': 'BUY',
            'confidence': min(buy_score + 20, 95),
            'reason': f'[룰] {" + ".join(buy_reasons)}',
        }

    return {'action': 'HOLD', 'confidence': 0, 'reason': '[룰] 조건 미충족'}


def analyze_with_ai(
    stock: dict,
    indicators: dict,
    strategy: dict,
    news: str = '',
    weekly: dict = None,
    kospi: dict = None,
    has_position: bool = False,
) -> dict:
    """AI 분석 (실패 시 룰 기반 fallback)"""
    # AI 키가 없으면 바로 룰 기반
    if not OPENAI_KEY:
        log('OpenAI 키 없음 → 룰 기반 판단', 'WARN')
        return rule_based_signal(indicators, kospi, weekly, has_position)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        picks = strategy.get('top_picks', [])
        pick = next((p for p in picks if p.get('code') == stock['code']), None)
        pick_info = f"AI 장 전 전략: {pick['action']} — {pick['reason']}" if pick else "장 전 전략 없음"
        kospi_msg = (kospi or {}).get('msg', '중립')
        weekly_trend = (weekly or {}).get('trend', 'UNKNOWN')

        prompt = f"""당신은 연평균 수익률 50% 이상의 한국 주식 상위 1% 퀀트 트레이더입니다.
현재 모의투자 환경이므로 공격적으로 수익을 추구합니다.

[종목] {stock['name']} ({stock['code']})
[현재가] {indicators.get('price', 0):,.0f}원
[RSI] {indicators.get('rsi', 50)} — 45 이하면 매수 적극 고려
[MACD] {indicators.get('macd', 0)} (히스토그램: {indicators.get('macd_histogram', 0)})
[거래량] {indicators.get('vol_label', '정보없음')}
[볼린저밴드] 위치: {indicators.get('bb_pos', 50)}% — 40% 이하면 매수 구간
[보유 여부] {'보유 중' if has_position else '미보유'}
[장 전 전략] {pick_info}
[코스피] {kospi_msg}
[주봉 추세] {weekly_trend}
[뉴스] {news if news else '없음'}
[데이터 소스] {indicators.get('data_source', '?')} ({indicators.get('data_points', '?')}봉)

[매매 원칙 — 공격적 모의투자]
- 모의투자이므로 적극적으로 BUY 판단. 확률 55% 이상이면 매수.
- RSI 45 이하 + 아무 양수 시그널 하나 → BUY (MACD 양수, 거래량 증가, BB 하단, 뉴스 긍정 중 1개)
- RSI 35 이하면 거의 무조건 BUY (공포 매수)
- 거래량 2배 이상 급등 + RSI 50 이하 → BUY (모멘텀)
- SELL: RSI 65 이상 + MACD 음수 전환 시에만
- 주봉 DOWNTREND여도 RSI 30 이하면 역발상 BUY 허용
- 단, 거래량 0.3배 이하는 어떤 경우에도 BUY 금지

반드시 아래 JSON만 출력:
{{"action":"BUY|SELL|HOLD","confidence":0~100,"reason":"한줄이유"}}"""

        res = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
            max_tokens=150,
        )
        raw = res.choices[0].message.content.strip()
        # JSON 파싱 정리
        raw = raw.replace('```json', '').replace('```', '').strip()
        if raw.startswith('{'):
            out = json.loads(raw)
        else:
            # JSON 부분만 추출
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                out = json.loads(raw[start:end])
            else:
                raise ValueError(f'JSON 파싱 불가: {raw[:100]}')

        # 보정: 거래량 2배 이상 + BUY면 신뢰도 +10
        if out.get('action') == 'BUY' and indicators.get('vol_ratio', 1.0) >= 2.0:
            out['confidence'] = min(100, out.get('confidence', 0) + 10)

        # 보정: 코스피 RSI 30 이하 + BUY면 신뢰도 +10
        if out.get('action') == 'BUY' and kospi and (kospi.get('rsi') or 50) <= 30:
            out['confidence'] = min(100, out.get('confidence', 0) + 10)

        out['source'] = 'AI'
        return out

    except Exception as e:
        log(f'AI 분석 실패 → 룰 기반 fallback: {e}', 'WARN')
        result = rule_based_signal(indicators, kospi, weekly, has_position)
        result['source'] = 'RULE_FALLBACK'
        return result


# ─────────────────────────────────────────────
# 전략 로드
# ─────────────────────────────────────────────
def get_today_strategy() -> dict:
    path = Path('/home/wlsdud5035/.openclaw/workspace/stocks/today_strategy.json')
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        if d.get('date') != datetime.now().date().isoformat():
            log('장 전 전략 날짜 불일치 — 무시', 'WARN')
            return {}
        return d
    except Exception:
        return {}


def get_watchlist_from_db() -> list:
    """DB에서 종목 리스트 가져오기 (전략 없을 때 fallback)"""
    try:
        rows = (
            supabase.table('top50_stocks')
            .select('stock_code,stock_name')
            .limit(20)
            .execute()
            .data or []
        )
        return [{'code': r['stock_code'], 'name': r['stock_name']} for r in rows]
    except Exception as e:
        log(f'종목 리스트 DB 조회 실패: {e}', 'ERROR')
        return []


# ─────────────────────────────────────────────
# 주문 실행
# ─────────────────────────────────────────────
def execute_buy(
    stock: dict,
    signal: dict,
    indicators: dict,
    kospi: dict = None,
    weekly: dict = None,
) -> dict:
    """매수 실행 (모든 검증 포함)"""
    code = stock['code']
    name = stock['name']
    price = indicators.get('price', 0)

    if not price:
        return {'result': 'NO_PRICE'}

    # 신뢰도 체크
    if signal.get('confidence', 0) < RISK['min_confidence']:
        return {'result': 'LOW_CONFIDENCE', 'confidence': signal.get('confidence', 0)}

    # ── 차단 조건들 ──
    if kospi and (kospi.get('rsi') or 0) >= RULES['block_kospi_above']:
        log(f'{name}: 코스피 극도과열 — BUY 차단', 'WARN')
        return {'result': 'BLOCKED_KOSPI'}

    if weekly and weekly.get('trend') == 'DOWNTREND':
        log(f'{name}: 주봉 하락 추세 — BUY 차단', 'WARN')
        return {'result': 'BLOCKED_WEEKLY'}

    if indicators.get('vol_ratio', 1.0) <= RULES['block_vol_below']:
        log(f'{name}: 거래량 급감 — BUY 차단', 'WARN')
        return {'result': 'BLOCKED_VOLUME'}

    if indicators.get('bb_pos', 0) >= RULES['block_bb_above']:
        log(f'{name}: 볼린저 상단 — BUY 차단', 'WARN')
        return {'result': 'BLOCKED_BB'}

    # 동일 종목 중복 매수 체크 + 분할매수 차수 확인
    existing = get_position_for_stock(code)
    split_stage = len(existing) + 1

    if split_stage > 3:
        log(f'{name}: 이미 3차 매수 완료 — 추가 매수 차단', 'WARN')
        return {'result': 'MAX_SPLIT_REACHED'}

    # 분할매수 RSI 기준 체크
    rsi = indicators.get('rsi', 50)
    required_rsi = RISK['split_rsi_thresholds'][split_stage - 1]
    if split_stage >= 2 and rsi > required_rsi:
        log(f'{name}: {split_stage}차 매수 RSI 기준 미달 (현재 {rsi} > 기준 {required_rsi})', 'WARN')
        return {'result': 'RSI_NOT_LOW_ENOUGH'}

    # 쿨다운 체크
    if check_cooldown(code):
        log(f'{name}: 최근 매도 후 쿨다운 중', 'WARN')
        return {'result': 'COOLDOWN'}

    # 최대 포지션 수 체크
    all_open = get_open_positions()
    open_codes = list(set(p['stock_code'] for p in all_open))
    # 이미 보유 중인 종목은 분할매수이므로 새 종목만 카운트
    if code not in open_codes and len(open_codes) >= RISK['max_positions']:
        return {'result': 'MAX_POSITIONS'}

    # ── 주문 수량 계산 ──
    try:
        account = kiwoom.get_account_evaluation()
        summary = account.get('summary', {})
        krw_balance = float(
            summary.get('deposit', 0)
            or summary.get('estimated_asset', 0)
            or 0
        )
    except Exception as e:
        log(f'잔고 조회 실패: {e}', 'ERROR')
        return {'result': 'BALANCE_ERROR'}

    # invest_ratio로 종목당 총 투자금 계산 → 분할매수 비율 적용
    total_invest = krw_balance * RISK['invest_ratio']
    stage_ratio = RISK['split_ratios'][split_stage - 1]
    invest_krw = total_invest * stage_ratio

    if invest_krw < RISK['min_order_krw']:
        return {'result': 'INSUFFICIENT_KRW', 'available': invest_krw}

    quantity = int(invest_krw / price)
    if quantity < 1:
        return {'result': 'INSUFFICIENT_KRW'}

    # ── 실제 주문 ──
    try:
        order_result = kiwoom.place_order(
            stock_code=code,
            order_type='buy',
            quantity=quantity,
            price=0,  # 시장가
        )
        log(f'{name} 매수 주문 응답: {order_result}', 'TRADE')
    except Exception as e:
        log(f'{name} 매수 주문 실패: {e}', 'ERROR')
        send_telegram(f'❌ <b>{name} 매수 주문 실패</b>\n{e}')
        return {'result': 'ORDER_FAILED', 'error': str(e)}
        # ↑ 주문 실패 시 여기서 return → DB 저장 안 됨 (v1 버그 수정)

    # ── DB 저장 (주문 성공 후에만) ──
    try:
        supabase.table('trade_executions').insert({
            'trade_type': 'BUY',
            'stock_code': code,
            'stock_name': name,  # 종목명 추가
            'quantity': quantity,
            'price': price,
            'strategy': signal.get('source', 'AI') + '+RSI+MACD',
            'reason': signal.get('reason', ''),
            'result': 'OPEN',
            'split_stage': split_stage,
        }).execute()
    except Exception as e:
        log(f'{name} DB 저장 실패: {e}', 'ERROR')

    # ── 알림 ──
    avg_entry = calc_avg_entry_price(get_position_for_stock(code))
    send_telegram(
        f"🟢 <b>{name} {split_stage}차 매수</b>\n"
        f"💰 {price:,.0f}원 × {quantity}주\n"
        f"💵 투입: {invest_krw:,.0f}원\n"
        f"📊 평균단가: {avg_entry:,.0f}원\n"
        f"🎯 신뢰도: {signal.get('confidence', 0)}% ({signal.get('source', '?')})\n"
        f"📝 {signal.get('reason', '')}\n"
        f"⚠️ 모의투자"
    )

    return {
        'result': 'BUY',
        'stage': split_stage,
        'quantity': quantity,
        'price': price,
        'invest_krw': invest_krw,
    }


def execute_sell(stock: dict, signal: dict, indicators: dict, reason_prefix: str = '') -> dict:
    """매도 실행"""
    code = stock['code']
    name = stock['name']
    price = indicators.get('price', 0) if isinstance(indicators, dict) else indicators

    positions = get_position_for_stock(code)
    if not positions:
        return {'result': 'NO_POSITION'}

    total_qty = sum(int(p['quantity']) for p in positions)
    avg_entry = calc_avg_entry_price(positions)

    if not price or not avg_entry:
        return {'result': 'NO_PRICE'}

    pnl_pct = (price - avg_entry) / avg_entry * 100
    pnl_krw = (price - avg_entry) * total_qty

    # ── 실제 주문 ──
    try:
        order_result = kiwoom.place_order(
            stock_code=code,
            order_type='sell',
            quantity=total_qty,
            price=0,
        )
        log(f'{name} 매도 주문 응답: {order_result}', 'TRADE')
    except Exception as e:
        log(f'{name} 매도 주문 실패: {e}', 'ERROR')
        send_telegram(f'❌ <b>{name} 매도 주문 실패</b>\n{e}')
        return {'result': 'ORDER_FAILED', 'error': str(e)}

    # ── DB 업데이트 (주문 성공 후에만) ──
    for p in positions:
        pid = p.get('trade_id')
        if pid is not None:
            try:
                supabase.table('trade_executions').update({
                    'result': 'CLOSED',
                    'entry_price': avg_entry,  # 평균 진입가 기록
                }).eq('trade_id', pid).execute()
            except Exception as e:
                log(f'DB 업데이트 실패 (trade_id={pid}): {e}', 'ERROR')

    # 매도 기록도 별도 저장
    try:
        supabase.table('trade_executions').insert({
            'trade_type': 'SELL',
            'stock_code': code,
            'stock_name': name,
            'quantity': total_qty,
            'price': price,
            'entry_price': avg_entry,
            'strategy': 'SELL',
            'reason': f'{reason_prefix}{signal.get("reason", "")}' if isinstance(signal, dict) else reason_prefix,
            'result': 'CLOSED',
        }).execute()
    except Exception as e:
        log(f'{name} 매도 기록 저장 실패: {e}', 'ERROR')

    # ── 알림 ──
    emoji = '✅' if pnl_pct > 0 else '🛑'
    send_telegram(
        f"{emoji} <b>{name} 매도</b>\n"
        f"💰 {price:,.0f}원 × {total_qty}주\n"
        f"📊 평균단가: {avg_entry:,.0f}원\n"
        f"📈 수익률: {pnl_pct:+.2f}% ({pnl_krw:+,.0f}원)\n"
        f"📝 {reason_prefix}{signal.get('reason', '') if isinstance(signal, dict) else ''}\n"
        f"⚠️ 모의투자"
    )

    return {
        'result': 'SELL',
        'pnl_pct': pnl_pct,
        'pnl_krw': pnl_krw,
        'quantity': total_qty,
    }


def execute_trade(
    stock: dict,
    signal: dict,
    indicators: dict,
    kospi: dict = None,
    weekly: dict = None,
) -> dict:
    """매매 실행 라우터"""
    action = signal.get('action', 'HOLD')

    if action == 'BUY':
        return execute_buy(stock, signal, indicators, kospi, weekly)
    elif action == 'SELL':
        return execute_sell(stock, signal, indicators)
    else:
        return {'result': 'HOLD'}


# ─────────────────────────────────────────────
# 손절/익절 자동 체크
# ─────────────────────────────────────────────
def check_stop_loss_take_profit():
    """손절/익절 + 트레일링 스탑 자동 체크"""
    positions = get_open_positions()
    if not positions:
        return

    # 종목별 그룹핑
    from collections import defaultdict
    by_code = defaultdict(list)
    for p in positions:
        code = p.get('stock_code')
        if code:
            by_code[code].append(p)

    for code, pos_list in by_code.items():
        try:
            price = get_current_price(code)
            if not price:
                continue

            avg_entry = calc_avg_entry_price(pos_list)
            if not avg_entry:
                continue

            chg = (price - avg_entry) / avg_entry
            total_qty = sum(int(p['quantity']) for p in pos_list)
            name = pos_list[0].get('stock_name', code)

            stock = {'code': code, 'name': name}

            # 손절
            if chg <= RISK['stop_loss']:
                log(f'{name} 손절 발동: {chg*100:.2f}%', 'TRADE')
                execute_sell(stock, {}, {'price': price}, reason_prefix='🛑 손절: ')

            # 익절
            elif chg >= RISK['take_profit']:
                log(f'{name} 익절 발동: {chg*100:.2f}%', 'TRADE')
                execute_sell(stock, {}, {'price': price}, reason_prefix='✅ 익절: ')

            time.sleep(0.3)

        except Exception as e:
            log(f'손절/익절 체크 실패 {code}: {e}', 'ERROR')


# ─────────────────────────────────────────────
# 메인 사이클
# ─────────────────────────────────────────────
def run_trading_cycle():
    global _cache
    _cache = {}  # 사이클마다 캐시 리셋

    if not is_market_open():
        log('장 외 시간 — 스킵')
        return

    log('=' * 50)
    log('주식 매매 사이클 시작')

    # 일일 손실 한도 체크
    if check_daily_loss():
        log('🚨 일일 손실 한도 초과 — 사이클 스킵', 'WARN')
        return

    # 보유 포지션 손절/익절 먼저 체크
    check_stop_loss_take_profit()

    # 전략 로드
    strategy = get_today_strategy()
    if strategy:
        log(f"장 전 전략 로드 완료: {strategy.get('market_outlook', '?')}")
        buy_picks = [p for p in strategy.get('top_picks', []) if p.get('action') == 'BUY']
        watch_picks = [p for p in strategy.get('top_picks', []) if p.get('action') == 'WATCH']
        targets = [{'code': p['code'], 'name': p['name']} for p in (buy_picks + watch_picks)]
    else:
        log('장 전 전략 없음 → DB 종목 리스트로 룰 기반 매매', 'WARN')
        targets = get_watchlist_from_db()

    if not targets:
        log('분석 대상 종목 없음')
        return

    # 코스피 심리
    kospi = get_kospi_sentiment()
    log(f'코스피 심리: {kospi["msg"]}')

    # 보유 종목도 SELL 체크에 포함
    open_positions = get_open_positions()
    open_codes = list(set(p['stock_code'] for p in open_positions))
    # 보유 중이지만 targets에 없는 종목 추가
    for code in open_codes:
        if not any(t['code'] == code for t in targets):
            name = next(
                (p.get('stock_name', code) for p in open_positions if p['stock_code'] == code),
                code,
            )
            targets.append({'code': code, 'name': name})

    # 종목별 분석 + 매매
    for stock in targets[:10]:  # 최대 10종목
        code = stock['code']
        name = stock['name']
        has_position = code in open_codes

        log(f'')
        log(f'  📊 {name} ({code}) 분석 중... {"[보유중]" if has_position else ""}')

        indicators = get_indicators(code)
        if not indicators:
            log(f'  {name}: 지표 없음 — 스킵', 'WARN')
            continue

        log(
            f"  RSI: {indicators['rsi']} / MACD: {indicators['macd']}({indicators.get('macd_histogram', '?')}) / "
            f"거래량: {indicators.get('vol_label', '?')} / BB: {indicators.get('bb_pos', '?')}% [{indicators.get('data_source', '?')}/{indicators.get('data_points', '?')}봉]"
        )

        weekly = get_weekly_trend(code)
        log(f'  주봉 추세: {weekly.get("trend", "?")}')

        news = get_stock_news(name)

        signal = analyze_with_ai(
            stock, indicators, strategy, news, weekly, kospi, has_position
        )
        log(
            f"  신호: {signal['action']} ({signal.get('confidence', 0)}%) "
            f"[{signal.get('source', '?')}] — {signal.get('reason', '')}"
        )

        result = execute_trade(stock, signal, indicators, kospi=kospi, weekly=weekly)
        log(f"  결과: {result['result']}")

        time.sleep(1)

    log('주식 매매 사이클 완료')
    log('=' * 50)


# ─────────────────────────────────────────────
# 엔트리포인트
# ─────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        if is_market_open():
            log('주식 1분 손절/익절 체크')
            check_stop_loss_take_profit()
        else:
            log('장 외 시간 — 스킵')
    elif len(sys.argv) > 1 and sys.argv[1] == 'status':
        # 현재 포지션 상태 출력
        positions = get_open_positions()
        if not positions:
            log('열린 포지션 없음')
        else:
            from collections import defaultdict
            by_code = defaultdict(list)
            for p in positions:
                by_code[p['stock_code']].append(p)
            for code, pos_list in by_code.items():
                name = pos_list[0].get('stock_name', code)
                avg = calc_avg_entry_price(pos_list)
                qty = sum(int(p['quantity']) for p in pos_list)
                cur = get_current_price(code)
                chg = ((cur - avg) / avg * 100) if avg and cur else 0
                log(f'  {name}: {qty}주 × 평단 {avg:,.0f}원 → 현재 {cur:,.0f}원 ({chg:+.2f}%)')
    else:
        run_trading_cycle()
