#!/usr/bin/env python3
"""
종목코드(stock_code)를 DART 고유번호(corp_code)로 변환.

Usage:
    python3 get_corp_code.py 035420
    python3 get_corp_code.py 005930 000660 035720
"""

import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

DART_API_KEY = os.getenv("DART_API_KEY", "")
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
CACHE_DIR = Path("/tmp/dart_cache")
CORP_CODE_XML = CACHE_DIR / "CORPCODE.xml"


def download_corp_code_file() -> bool:
    """고유번호 파일 다운로드 및 압축 해제."""
    if not DART_API_KEY:
        print("Error: DART_API_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        return False

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_DIR / "corpcode.zip"

    try:
        response = requests.get(
            CORP_CODE_URL,
            params={"crtfc_key": DART_API_KEY},
            timeout=30,
        )
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            f.write(response.content)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(CACHE_DIR)

        return CORP_CODE_XML.exists()
    except Exception as e:
        print(f"Error downloading corp code file: {e}", file=sys.stderr)
        return False


def get_corp_code(stock_code: str) -> str | None:
    """종목코드로 corp_code 조회."""
    if not CORP_CODE_XML.exists():
        if not download_corp_code_file():
            return None

    try:
        tree = ET.parse(CORP_CODE_XML)
        root = tree.getroot()

        for corp in root.findall("list"):
            sc = corp.find("stock_code")
            if sc is not None and sc.text and sc.text.strip() == stock_code:
                cc = corp.find("corp_code")
                return cc.text if cc is not None else None

        return None
    except Exception as e:
        print(f"Error parsing corp code file: {e}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 get_corp_code.py <stock_code> [stock_code2 ...]")
        sys.exit(1)

    for stock_code in sys.argv[1:]:
        corp_code = get_corp_code(stock_code)
        if corp_code:
            print(f"{stock_code}: {corp_code}")
        else:
            print(f"{stock_code}: Not found", file=sys.stderr)


if __name__ == "__main__":
    main()
