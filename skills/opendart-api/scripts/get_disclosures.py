#!/usr/bin/env python3
"""
기업 공시 조회.

Usage:
    python3 get_disclosures.py 00266961              # corp_code로 조회
    python3 get_disclosures.py 00266961 --days 30    # 최근 30일
    python3 get_disclosures.py 00266961 --important  # 중요 공시만
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

import requests

DART_API_KEY = os.getenv("DART_API_KEY", "")
BASE_URL = "https://opendart.fss.or.kr/api"

IMPORTANT_KEYWORDS = [
    "실적", "배당", "증자", "감자", "합병", "분할",
    "자기주식", "전환사채", "신주인수권", "주요계약",
    "유상증자", "무상증자", "주주총회",
]


def get_disclosures(
    corp_code: str,
    days: int = 30,
    page_count: int = 100,
) -> list[dict]:
    """최근 공시 조회."""
    if not DART_API_KEY:
        print("Error: DART_API_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        return []

    end_de = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    url = f"{BASE_URL}/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": page_count,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        if data.get("status") == "000":
            return data.get("list", [])
        else:
            print(f"API Error: {data.get('message')}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"Request Error: {e}", file=sys.stderr)
        return []


def filter_important(disclosures: list[dict]) -> list[dict]:
    """중요 공시만 필터링."""
    return [
        d for d in disclosures
        if any(kw in d.get("report_nm", "") for kw in IMPORTANT_KEYWORDS)
    ]


def main():
    parser = argparse.ArgumentParser(description="DART 공시 조회")
    parser.add_argument("corp_code", help="DART 고유번호 (예: 00266961)")
    parser.add_argument("--days", type=int, default=30, help="조회 기간 (일)")
    parser.add_argument("--important", action="store_true", help="중요 공시만")
    args = parser.parse_args()

    disclosures = get_disclosures(args.corp_code, days=args.days)

    if args.important:
        disclosures = filter_important(disclosures)

    if not disclosures:
        print("조회된 공시가 없습니다.")
        return

    print(f"=== 공시 목록 ({len(disclosures)}건) ===\n")
    for d in disclosures:
        print(f"[{d['rcept_dt']}] {d['report_nm']}")
        print(f"  제출인: {d['flr_nm']} | 접수번호: {d['rcept_no']}")
        print(f"  URL: https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d['rcept_no']}")
        print()


if __name__ == "__main__":
    main()
