---
name: opendart-api
description: This skill should be used when working with OpenDART (금융감독원 전자공시시스템) API for retrieving corporate disclosures, financial statements, dividend information, and major shareholder reports. Use this skill when the user needs to query Korean stock disclosures, check company earnings, retrieve financial data from DART, or analyze corporate filings.
version: 1.0.0
tags: [opendart, dart, disclosure, financial-statements, korea, fss]
---

# OpenDART API

OpenDART(금융감독원 전자공시시스템) REST API를 사용한 기업 공시 및 재무 데이터 조회.

## Overview

OpenDART API enables retrieval of:
- Corporate disclosures (earnings, dividends, capital changes)
- Financial statements (quarterly, annual)
- Major shareholder reports (5%+ ownership)
- Executive stock transactions

## 설치

```bash
npx dlabs install trading-tools
```

## 환경 설정

### .env 파일 구성

프로젝트 루트에 `.env` 파일이 없으면 이 스킬의 `.env.example`을 복사하여 생성:

```bash
# 프로젝트 루트로 이동
cd /path/to/your-project

# .env 파일이 없으면 스킬의 .env.example 복사
if [ ! -f .env ]; then
    cp .claude/skills/opendart-api/.env.example .env
    echo "✅ .env 파일 생성됨. DART_API_KEY를 입력하세요."
fi

# .env 파일 편집
nano .env  # 또는 vim, code 등
```

**필수 환경 변수:**

```bash
# OpenDART API 키 (https://opendart.fss.or.kr/ 에서 발급)
DART_API_KEY=your_dart_api_key_here
```

### Python에서 로드

```python
import os
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
load_dotenv()

dart_api_key = os.getenv("DART_API_KEY")
```

## Quick Start

### corp_code vs stock_code

OpenDART uses `corp_code` (DART unique ID), not `stock_code` (exchange ticker).

| Type | Description | Example |
|------|-------------|---------|
| `stock_code` | Exchange ticker | 035420 |
| `corp_code` | DART unique ID | 00266961 |

To convert stock_code to corp_code, use `scripts/get_corp_code.py`:

```bash
python3 scripts/get_corp_code.py 035420
# Output: 00266961
```

### Common corp_codes

Frequently used mappings (see `references/corp_codes.md` for full list):

| Stock | Name | corp_code |
|-------|------|-----------|
| 005930 | 삼성전자 | 00126380 |
| 035420 | NAVER | 00266961 |
| 000660 | SK하이닉스 | 00164779 |
| 035720 | 카카오 | 00401731 |

## Disclosure Search

Retrieve recent disclosures for a company.

```bash
# .env 로드 후 사용
source .env

curl -s "https://opendart.fss.or.kr/api/list.json?\
crtfc_key=$DART_API_KEY&\
corp_code=00266961&\
page_count=10"
```

**Parameters:**
- `corp_code`: DART unique ID
- `bgn_de`: Start date (YYYYMMDD)
- `end_de`: End date (YYYYMMDD)
- `pblntf_ty`: Disclosure type (A=정기, B=주요사항, K=수시공시)
- `page_count`: Results per page (max 100)

**Important disclosure types to filter:**

| Disclosure | Importance | Description |
|------------|------------|-------------|
| 영업(잠정)실적 | ⭐⭐⭐ | Earnings report |
| 현금·현물배당결정 | ⭐⭐⭐ | Dividend decision |
| 유상증자결정 | ⭐⭐⭐ | Capital increase |
| 자기주식취득결정 | ⭐⭐ | Stock buyback |

## Financial Statements

Retrieve quarterly or annual financial data.

```bash
source .env

curl -s "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?\
crtfc_key=$DART_API_KEY&\
corp_code=00266961&\
bsns_year=2025&\
reprt_code=11014&\
fs_div=CFS"
```

**Parameters:**
- `bsns_year`: Fiscal year (YYYY)
- `reprt_code`: Report type
  - `11011`: Q1
  - `11012`: Half-year
  - `11013`: Q3
  - `11014`: Annual
- `fs_div`: Statement type (OFS=Individual, CFS=Consolidated)

## Dividend Information

```bash
source .env

curl -s "https://opendart.fss.or.kr/api/alotMatter.json?\
crtfc_key=$DART_API_KEY&\
corp_code=00266961&\
bsns_year=2025&\
reprt_code=11014"
```

## Major Shareholders

5%+ ownership reports:

```bash
source .env

curl -s "https://opendart.fss.or.kr/api/majorstock.json?\
crtfc_key=$DART_API_KEY&\
corp_code=00266961"
```

## Error Handling

| Code | Message | Cause |
|------|---------|-------|
| 000 | 정상 | Success |
| 010 | 등록되지 않은 인증키 | Invalid API key |
| 013 | 조회된 데이터 없음 | No results |
| 020 | 요청 제한 초과 | Daily limit exceeded (10,000/day) |

## Resources

### scripts/

- `get_corp_code.py` - Convert stock_code to corp_code
- `get_disclosures.py` - Fetch recent disclosures for a company

### references/

- `api_reference.md` - Complete API endpoint documentation
- `corp_codes.md` - Stock code to corp_code mapping table
