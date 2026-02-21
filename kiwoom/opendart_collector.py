#!/usr/bin/env python3
"""
OpenDART API 기반 재무제표 + 공시 데이터 수집 스크립트
- 상위 50종목 재무제표 수집
- 공시 데이터 수집
- Supabase에 저장
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 경로 설정
ROOT = Path(__file__).resolve().parent
BRAIN_DIR = ROOT / "brain"
LOG_DIR = BRAIN_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _load_opendart_config() -> Dict[str, str]:
    """openclaw.json에서 OpenDART API 키 로드"""
    candidates = [
        Path.home() / ".openclaw" / "openclaw.json",
        Path("/home/node/.openclaw/openclaw.json"),
    ]
    
    for p in candidates:
        try:
            with p.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            env = cfg.get("env", {})
            api_key = env.get("OPENDART_API_KEY") or env.get("DART_API_KEY")
            if api_key:
                return {"api_key": api_key}
        except Exception:
            continue
    
    raise RuntimeError("OPENDART_API_KEY를 찾을 수 없습니다.")


def _get_stock_codes() -> List[str]:
    """종목코드 리스트 반환 (6자리 숫자)"""
    watchlist_path = BRAIN_DIR / "watchlist.md"
    codes = []
    
    if watchlist_path.exists():
        with watchlist_path.open("r", encoding="utf-8") as f:
            for line in f:
                if "|" in line and len(line.split("|")) >= 3:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 6:
                        codes.append(parts[1])
    
    if not codes:
        codes = ["005930", "000660", "035420", "035720"]  # 기본값
    
    return codes


def _fetch_financials(corp_code: str, api_key: str, bsns_year: str = None) -> Optional[Dict[str, Any]]:
    """OpenDART API로 재무제표 조회"""
    if bsns_year is None:
        bsns_year = str(datetime.now().year - 1)  # 작년 기준
    
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": "11011",  # 사업보고서
        "fs_div": "CFS",  # 연결재무제표
    }
    
    try:
        resp = httpx.get(url, params=params, timeout=30.0)
        data = resp.json()
        
        if data.get("status") == "000":
            return data
        else:
            print(f"⚠️ {corp_code} 재무제표 조회 실패: {data.get(message)}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"⚠️ {corp_code} 재무제표 조회 중 오류: {e}", file=sys.stderr)
        return None


def _fetch_disclosures(corp_code: str, api_key: str, bgn_de: str = None, end_de: str = None) -> Optional[List[Dict[str, Any]]]:
    """OpenDART API로 공시 목록 조회"""
    if bgn_de is None:
        bgn_de = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    if end_de is None:
        end_de = datetime.now().strftime("%Y%m%d")
    
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": "1",
        "page_count": "100",
    }
    
    try:
        resp = httpx.get(url, params=params, timeout=30.0)
        data = resp.json()
        
        if data.get("status") == "000":
            return data.get("list", [])
        else:
            print(f"⚠️ {corp_code} 공시 목록 조회 실패: {data.get(message)}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"⚠️ {corp_code} 공시 목록 조회 중 오류: {e}", file=sys.stderr)
        return None


def collect_financials() -> List[Dict[str, Any]]:
    """상위 50종목 재무제표 수집"""
    print("📊 재무제표 데이터 수집 시작...")
    
    config = _load_opendart_config()
    api_key = config["api_key"]
    codes = _get_stock_codes()
    
    results = []
    for i, code in enumerate(codes, 1):
        print(f"[{i}/{len(codes)}] {code} 재무제표 수집 중...", end=" ", flush=True)
        data = _fetch_financials(code, api_key)
        if data:
            results.append({"corp_code": code, "financials": data})
            print("✅")
        else:
            print("❌")
    
    print(f"\n✅ 총 {len(results)}개 종목 재무제표 수집 완료")
    return results


def collect_disclosures() -> List[Dict[str, Any]]:
    """공시 데이터 수집"""
    print("📢 공시 데이터 수집 시작...")
    
    config = _load_opendart_config()
    api_key = config["api_key"]
    codes = _get_stock_codes()
    
    results = []
    for i, code in enumerate(codes, 1):
        print(f"[{i}/{len(codes)}] {code} 공시 수집 중...", end=" ", flush=True)
        data = _fetch_disclosures(code, api_key)
        if data:
            results.append({"corp_code": code, "disclosures": data, "count": len(data)})
            print(f"✅ {len(data)}건")
        else:
            print("❌")
    
    print(f"\n✅ 총 {len(results)}개 종목 공시 수집 완료")
    return results


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenDART API 기반 재무제표/공시 데이터 수집")
    parser.add_argument("--financials", action="store_true", help="재무제표만 수집")
    parser.add_argument("--disclosures", action="store_true", help="공시만 수집")
    args = parser.parse_args()
    
    results = {}
    
    if args.financials or not args.disclosures:
        results["financials"] = collect_financials()
    
    if args.disclosures or not args.financials:
        results["disclosures"] = collect_disclosures()
    
    # JSON 출력
    print("\n📋 수집 결과:")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    from datetime import timedelta
    main()
