#!/usr/bin/env python3
"""
yfinance 기반 주식 데이터 수집 스크립트
- 코스피 상위 50종목 OHLCV 수집
- 관심 종목 실시간 시세 조회
- Supabase에 저장
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yfinance as yf

# 경로 설정
ROOT = Path(__file__).resolve().parent
BRAIN_DIR = ROOT / "brain"
LOG_DIR = BRAIN_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Supabase 연결 정보 로드
def _load_supabase_config() -> Dict[str, str]:
    """openclaw.json에서 Supabase 설정 로드"""
    candidates = [
        Path.home() / ".openclaw" / "openclaw.json",
        Path("/home/node/.openclaw/openclaw.json"),
    ]
    
    for p in candidates:
        try:
            with p.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            env = cfg.get("env", {})
            db_url = env.get("SUPABASE_DB_URL")
            if db_url:
                return {"db_url": db_url}
        except Exception:
            continue
    
    raise RuntimeError("SUPABASE_DB_URL을 찾을 수 없습니다.")


def _get_kospi_top50() -> List[str]:
    """코스피 상위 50종목 코드 리스트 반환 (yfinance 형식: 005930.KS)"""
    # 실제로는 웹에서 코스피 상위 종목을 가져오거나, 고정 리스트 사용
    # 여기서는 관심 종목 + 주요 대형주 리스트 사용
    top_stocks = [
        "005930.KS",  # 삼성전자
        "000660.KS",  # SK하이닉스
        "035420.KS",  # NAVER
        "035720.KS",  # 카카오
        "051910.KS",  # LG화학
        "006400.KS",  # 삼성SDI
        "028260.KS",  # 삼성물산
        "005380.KS",  # 현대차
        "012330.KS",  # 현대모비스
        "105560.KS",  # KB금융
        "055550.KS",  # 신한지주
        "032830.KS",  # 삼성생명
        "003550.KS",  # LG
        "034730.KS",  # SK
        "017670.KS",  # SK텔레콤
        "096770.KS",  # SK이노베이션
        "066570.KS",  # LG전자
        "207940.KS",  # 삼성바이오로직스
        "068270.KS",  # 셀트리온
        "251270.KS",  # 넷마블
    ]
    return top_stocks


def _fetch_ohlcv(ticker: str, period: str = "1d") -> Optional[Dict[str, Any]]:
    """yfinance로 OHLCV 데이터 수집"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty:
            return None
        
        latest = hist.iloc[-1]
        info = stock.info
        
        return {
            "ticker": ticker,
            "date": latest.name.strftime("%Y-%m-%d"),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "close": float(latest["Close"]),
            "volume": int(latest["Volume"]),
            "name": info.get("longName", ticker),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "KRW"),
        }
    except Exception as e:
        print(f"⚠️ {ticker} 수집 실패: {e}", file=sys.stderr)
        return None


def _save_to_supabase(data: List[Dict[str, Any]], table: str = "stock_ohlcv") -> bool:
    """Supabase에 데이터 저장"""
    try:
        config = _load_supabase_config()
        db_url = config["db_url"]
        
        # psycopg2 또는 httpx로 Supabase REST API 사용
        # 여기서는 간단히 psycopg2 사용 (없으면 설치 필요)
        try:
            import psycopg2
            from psycopg2.extras import execute_values
        except ImportError:
            print("⚠️ psycopg2가 설치되지 않았습니다. pip install psycopg2-binary 필요", file=sys.stderr)
            return False
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # 테이블이 없으면 생성
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id BIGSERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open NUMERIC(12, 2),
                high NUMERIC(12, 2),
                low NUMERIC(12, 2),
                close NUMERIC(12, 2),
                volume BIGINT,
                name TEXT,
                market_cap BIGINT,
                currency TEXT DEFAULT 'KRW',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(ticker, date)
            );
        """)
        
        # 데이터 삽입 (ON CONFLICT로 중복 방지)
        for row in data:
            cur.execute(f"""
                INSERT INTO {table} (ticker, date, open, high, low, close, volume, name, market_cap, currency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    market_cap = EXCLUDED.market_cap;
            """, (
                row["ticker"],
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row.get("name"),
                row.get("market_cap"),
                row.get("currency", "KRW"),
            ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"⚠️ Supabase 저장 실패: {e}", file=sys.stderr)
        return False


def collect_kospi_top50() -> List[Dict[str, Any]]:
    """코스피 상위 50종목 OHLCV 수집"""
    print("📊 코스피 상위 50종목 OHLCV 수집 시작...")
    
    tickers = _get_kospi_top50()
    results = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker} 수집 중...", end=" ", flush=True)
        data = _fetch_ohlcv(ticker)
        if data:
            results.append(data)
            print(f"✅ {data['close']:,.0f}원")
        else:
            print("❌ 실패")
    
    print(f"\n✅ 총 {len(results)}개 종목 수집 완료")
    return results


def get_watchlist_realtime() -> List[Dict[str, Any]]:
    """관심 종목 실시간 시세 조회"""
    print("📈 관심 종목 실시간 시세 조회...")
    
    watchlist_path = BRAIN_DIR / "watchlist.md"
    tickers = []
    
    if watchlist_path.exists():
        with watchlist_path.open("r", encoding="utf-8") as f:
            for line in f:
                if "|" in line and ".KS" not in line and len(line.split("|")) >= 3:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 6:
                        tickers.append(f"{parts[1]}.KS")
    
    if not tickers:
        tickers = ["005930.KS", "000660.KS"]  # 기본값
    
    results = []
    for ticker in tickers:
        data = _fetch_ohlcv(ticker, period="1d")
        if data:
            results.append(data)
            print(f"  {data.get('name', ticker)}: {data.get('close', 0):,.0f}원 ({data.get('volume', 0):,}주)")
    
    return results


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="yfinance 기반 주식 데이터 수집")
    parser.add_argument("--watchlist", action="store_true", help="관심 종목만 조회")
    parser.add_argument("--no-save", action="store_true", help="Supabase 저장 안 함")
    args = parser.parse_args()
    
    if args.watchlist:
        results = get_watchlist_realtime()
    else:
        results = collect_kospi_top50()
        if not args.no_save and results:
            print("\n💾 Supabase에 저장 중...")
            if _save_to_supabase(results):
                print("✅ 저장 완료")
            else:
                print("⚠️ 저장 실패 (데이터는 수집됨)")
    
    # JSON 출력
    print("\n📋 수집 결과:")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
