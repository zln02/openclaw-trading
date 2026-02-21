---
name: kiwoom-api
description: 키움증권 REST API를 사용하여 주식 데이터 조회, 계좌 자산 현황 파악, OAuth 인증, 환경 관리(모의투자/실전투자)를 수행할 때 사용. 주가 조회, 자산 조회, API 인증, 환경 전환이 필요한 경우 이 스킬을 활용.
version: 1.0.0
tags: [kiwoom, stock, trading, korea, rest-api, oauth]
---

# Kiwoom API

## Overview

키움증권 REST API와 상호작용하기 위한 종합 가이드입니다. OAuth 2.0 인증, 주식 기본정보 조회(ka10001), 계좌 자산 현황(kt00004), 일별잔고수익률(ka01690), 모의투자/실전투자 환경 관리, Rate Limiting 대응을 포함합니다.

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
    cp .claude/skills/kiwoom-api/.env.example .env
    echo "✅ .env 파일 생성됨. API 키를 입력하세요."
fi

# .env 파일 편집
nano .env  # 또는 vim, code 등
```

**필수 환경 변수:**

```bash
# 거래 환경: mock (모의투자) | prod (실전투자)
TRADING_ENV=mock

# API 인증 정보 (openapi.kiwoom.com에서 발급)
KIWOOM_REST_API_KEY=your_api_key
KIWOOM_REST_API_SECRET=your_api_secret

# 계좌번호 (모의투자: 50으로 시작)
KIWOOM_ACCOUNT_NO=5012345678
```

### 환경 전환

`.env` 파일의 `TRADING_ENV` 값을 변경하여 환경 전환:

```bash
# 모의투자 (기본값, 권장)
TRADING_ENV=mock

# 실전투자 (신중히!)
TRADING_ENV=prod
```

**환경별 API 엔드포인트:**

| 환경 | TRADING_ENV | Base URL |
|------|-------------|----------|
| 모의투자 | `mock` | `https://mockapi.kiwoom.com` |
| 실전투자 | `prod` | `https://api.kiwoom.com` |

## 인증 (OAuth 2.0)

### 토큰 발급

```python
import httpx
import os
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
load_dotenv()

api_key = os.getenv("KIWOOM_REST_API_KEY")
api_secret = os.getenv("KIWOOM_REST_API_SECRET")
trading_env = os.getenv("TRADING_ENV", "mock")

# Base URL 결정
base_url = (
    "https://mockapi.kiwoom.com" if trading_env == "mock"
    else "https://api.kiwoom.com"
)

# 토큰 발급
url = f"{base_url}/oauth2/token"
data = {
    "grant_type": "client_credentials",
    "appkey": api_key,
    "secretkey": api_secret
}

response = httpx.post(url, json=data, timeout=30.0)
result = response.json()

if result.get('return_code') == 0:
    token = result['token']
    print(f"Token: {token}")
else:
    print(f"Error: {result.get('return_msg')}")
```

### 토큰 캐싱

토큰은 약 1시간 동안 유효합니다. 토큰을 캐싱하여 불필요한 재발급을 방지합니다:

```python
import time

class KiwoomAPIClient:
    def __init__(self):
        self.token = None
        self.token_expires = None

    def _get_token(self) -> str:
        # 캐시된 토큰이 유효하면 재사용
        if self.token and self.token_expires:
            if time.time() < self.token_expires:
                return self.token

        # 토큰 발급
        # ... (위 코드 참조)

        self.token = result['token']
        self.token_expires = time.time() + 3600
        return self.token
```

## 주식 데이터 조회 (ka10001)

### 기본 정보 조회

```python
def get_stock_info(self, stock_code: str) -> dict:
    """
    주식기본정보요청 (ka10001)

    Args:
        stock_code: 종목코드 6자리 (예: "005930" 삼성전자)

    Returns:
        주가 정보 딕셔너리
    """
    token = self._get_token()

    url = f"{self.base_url}/api/dostk/stkinfo"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "api-id": "ka10001",
        "authorization": f"Bearer {token}"
    }
    body = {"stk_cd": stock_code}

    response = httpx.post(url, headers=headers, json=body, timeout=30.0)
    result = response.json()

    if result.get('return_code') == 0:
        return result
    else:
        raise Exception(f"API 오류: {result.get('return_msg')}")
```

### 응답 데이터 구조

```json
{
  "return_code": 0,
  "return_msg": "정상적으로 처리되었습니다",
  "stk_cd": "005930",
  "stk_nm": "삼성전자",
  "cur_prc": "-160400",
  "pred_pre": "-8700",
  "flu_rt": "-5.14",
  "trde_qty": "31734276",
  "mac": "9512858",
  "per": "32.47",
  "eps": "4950",
  "pbr": "2.77",
  "roe": "9.0",
  "bps": "57930",
  "250hgst": "+169400",
  "250lwst": "-50800"
}
```

## 계좌 자산 조회

### 자산 요약 조회 (get_asset_summary)

투자 시작 전 자산 현황을 한눈에 파악:

```python
from kiwoom_api_client_template import KiwoomAPIClient

client = KiwoomAPIClient()
summary = client.get_asset_summary()

print(f"환경: {summary['environment']}")
print(f"예수금: {summary['deposit']:,}원")
print(f"추정예탁자산: {summary['estimated_asset']:,}원")
print(f"보유종목: {summary['holdings_count']}개")
print(f"누적손익: {summary['cumulative_pnl']:+,}원 ({summary['cumulative_pnl_pct']:+.2f}%)")
```

### 계좌평가현황 (kt00004, get_account_evaluation)

보유종목별 상세 평가 현황:

```python
data = client.get_account_evaluation()

# 계좌 요약
s = data["summary"]
# deposit, d2_deposit, total_evaluation, total_asset,
# total_purchase, estimated_asset,
# today_pnl, monthly_pnl, cumulative_pnl,
# today_pnl_pct, monthly_pnl_pct, cumulative_pnl_pct

# 보유종목 리스트
for h in data["holdings"]:
    print(f"{h['name']} | {h['quantity']}주 | 손익: {h['pnl_pct']:+.2f}%")
    # code, name, quantity, avg_price, current_price,
    # evaluation, pnl_amount, pnl_pct, purchase_amount
```

### 일별잔고수익률 (ka01690, get_daily_balance_pnl)

특정 일자 기준 잔고 및 수익률:

```python
# 오늘 기준
daily = client.get_daily_balance_pnl()

# 특정 일자
daily = client.get_daily_balance_pnl("20260207")

s = daily["summary"]
# total_purchase, total_evaluation, total_pnl, total_pnl_pct,
# deposit, estimated_asset, cash_ratio

for h in daily["holdings"]:
    print(f"{h['name']} | 비중: {h['buy_ratio']:.1f}% | 수익률: {h['pnl_pct']:+.2f}%")
    # code, name, current_price, quantity, avg_price,
    # buy_ratio, evaluation, eval_ratio, pnl_amount, pnl_pct
```

### 체결잔고 조회 (kt00005, get_settlement_balance) - 실전투자 전용

체결된 주문의 결제 잔고, 예수금, 신용/대출 현황:

```python
# ⚠️ 실전투자 전용 - 모의투자에서는 Exception 발생
client = KiwoomAPIClient(use_mock=False)  # 실전투자 명시
data = client.get_settlement_balance()

# 계좌 요약
s = data["summary"]
# deposit, deposit_d1, deposit_d2, orderable_cash,
# withdrawable, unsettled_cash,
# total_buy_amount, total_evaluation,
# total_pnl, total_pnl_pct,
# substitute_amount, credit_collateral_rate

# 종목별 체결잔고
for h in data["holdings"]:
    print(f"{h['name']} | 결제잔고: {h['settlement_balance']}주 | 현잔고: {h['current_quantity']}주")
    # code, name, settlement_balance, current_quantity,
    # current_price, avg_price, purchase_amount,
    # evaluation, pnl_amount, pnl_pct,
    # credit_type, loan_date, expire_date
```

### 계좌 API 비교

| API | 메서드 | 모의투자 | 용도 |
|-----|--------|---------|------|
| kt00004 | `get_account_evaluation()` | 지원 | 현재 보유종목 + 손익 현황 |
| ka01690 | `get_daily_balance_pnl()` | 지원 | 특정 일자 잔고 + 종목별 비중 |
| kt00005 | `get_settlement_balance()` | **미지원** | 체결잔고 (실전투자 전용) |

## Rate Limiting 관리

키움증권 API는 요청 횟수 제한이 있습니다. HTTP 429 오류를 방지하기 위해:

```python
import time

def get_multiple_stocks(self, stock_codes: list, delay: float = 1.0) -> dict:
    """
    여러 종목 조회 (Rate Limiting 대응)

    Args:
        stock_codes: 종목코드 리스트
        delay: 요청 간 대기 시간 (초)

    Returns:
        종목별 데이터 딕셔너리
    """
    results = {}

    for i, code in enumerate(stock_codes):
        if i > 0:
            time.sleep(delay)  # 첫 요청 제외하고 대기

        try:
            results[code] = self.get_stock_info(code)
        except Exception as e:
            results[code] = {"error": str(e)}

    return results
```

**권장 사항**:
- 요청 간 최소 0.5~1초 대기
- HTTP 429 오류 발생 시 대기 시간 증가
- 연속 조회 시 배치 처리 권장

## 클라이언트 템플릿 사용

재사용 가능한 클라이언트 템플릿이 제공됩니다:

```bash
# 템플릿 위치
.claude/skills/kiwoom-api/assets/kiwoom_api_client_template.py
```

**템플릿 특징**:
- OAuth 토큰 자동 캐싱 및 갱신
- 환경 변수 기반 설정 (프로젝트 루트 .env 사용)
- 에러 처리 내장
- 주식 기본정보 조회 (ka10001)
- 계좌평가현황 조회 (kt00004)
- 일별잔고수익률 조회 (ka01690)
- 체결잔고 조회 (kt00005, 실전투자 전용)
- 자산 요약 조회 (kt00004 래핑)

**사용 방법**:

```python
from kiwoom_api_client_template import KiwoomAPIClient

client = KiwoomAPIClient()              # .env 기준 자동 결정
client = KiwoomAPIClient(use_mock=True) # 명시적 모의투자

# 주식 정보
data = client.get_stock_info("005930")

# 자산 현황 (가장 자주 쓰는 메서드)
summary = client.get_asset_summary()
print(f"예수금: {summary['deposit']:,}원")

# 상세 계좌 평가
evaluation = client.get_account_evaluation()

# 일별 잔고 수익률
daily = client.get_daily_balance_pnl("20260207")
```

## 안전 수칙

### 모의투자 (권장)
- 개발 및 테스트
- 전략 검증
- 백테스팅
- 무제한 실험

### 실전투자 (신중히)
- 검증 완료 후에만
- 소액으로 시작
- 조회 API 위주
- 거래 API 극도로 신중

## 종목코드 형식

```python
# KRX (국내 주식)
"005930"        # 삼성전자

# NASDAQ
"039490_NX"     # 셀트리온

# NYSE
"039490_AL"     # 셀트리온
```

## 응답 코드

| return_code | 의미 |
|-------------|------|
| 0 | 정상 처리 |
| 2 | 입력 값 오류 |
| 3 | 인증 실패 |
| 5 | Rate Limit 초과 |

## Troubleshooting

### 인증 실패 (return_code: 3)
- `.env` 파일에 API Key/Secret 확인
- `TRADING_ENV` 설정 확인 (mock/prod)
- 토큰 만료 시 재발급

### Rate Limit 초과 (return_code: 5)
- 요청 간 delay 증가
- 배치 처리 사용
- 불필요한 요청 제거

### 잘못된 종목코드 (return_code: 2)
- 6자리 숫자 형식 확인
- KRX 거래소 코드 확인

### kt00005 체결잔고 모의투자 미지원 (return_code: 20)
- **원인**: kt00005는 모의투자에서 지원하지 않음
- **메시지**: `모의투자에서는 해당업무가 제공되지 않습니다`
- **대안**: kt00004 (계좌평가현황)로 보유종목/잔고 확인

### ka01690 주말/공휴일 빈 데이터
- **원인**: 주말·공휴일에는 시세 데이터 없음
- **메시지**: `서비스 TR을 확인 바랍니다` (return_code: 0이지만 데이터 비어있음)
- **대안**: 직전 영업일(금요일) 날짜로 조회

### find_project_root() .env 미발견
- **원인**: 스킬 하위 디렉토리의 `.env.example`이 프로젝트 루트의 `.env`보다 먼저 매칭됨
- **해결**: `.env`를 우선 탐색 후 `.env.example`을 fallback으로 탐색하도록 수정

## Resources

### references/
**api_endpoints.md** - 키움증권 REST API 엔드포인트 상세 스펙. OAuth, 주식정보, 계좌, 거래 API 포함.

**account.md** - 계좌 관련 API (ka01690 일별잔고수익률) 상세 스펙.

**environment_config.md** - 환경 설정 및 관리 가이드. 환경 변수 목록, Python에서 환경 확인 방법 포함.

**market_price.md** - 시세 API (호가, 일주월시분, 시분, 시세표성정보, 신주인수권) 상세 스펙.

**ranking.md** - 순위정보 API (호가잔량상위, 호가잔량급증, 잔량율급증, 거래량급증, 전일대비등락률상위) 상세 스펙.

**institution.md** - 기관/외국인 매매동향 API (외국인종목별, 기관) 상세 스펙.

**sector.md** - 업종 프로그램 매매 API 상세 스펙.

**short_selling.md** - 공매도 추이 API 상세 스펙.

**stock_info.md** - 종목정보 API (실시간순위, 기본정보, 거래원, 체결정보, 신용매매, 일별거래, 신고저가, 상하한가, 고저가근접, 가격급등락, 거래량갱신, 매물대집중, 고저PER) 상세 스펙.

**misc.md** - 기타 API (토큰 발급/폐기) 상세 스펙.

### assets/
**kiwoom_api_client_template.py** - 재사용 가능한 Kiwoom API 클라이언트 템플릿. OAuth 인증, 토큰 캐싱, 주식정보(ka10001), 계좌평가(kt00004), 일별잔고(ka01690), 체결잔고(kt00005) API 구현 포함.

## API 엔드포인트 요약

| API ID | 용도 | URL | 모의투자 |
|--------|------|-----|---------|
| au10001 | 토큰 발급 | `/oauth2/token` | 지원 |
| ka10001 | 주식기본정보 | `/api/dostk/stkinfo` | 지원 |
| kt00004 | 계좌평가현황 | `/api/dostk/acnt` | 지원 |
| ka01690 | 일별잔고수익률 | `/api/dostk/acnt` | 지원 |
| kt00005 | 체결잔고 | `/api/dostk/acnt` | **미지원** (실전투자 전용) |
| kt10000 | 매수주문 | `/api/dostk/ordr` | 지원 |
| kt10001 | 매도주문 | `/api/dostk/ordr` | 지원 |

## 주문 API 파라미터 규격

### 매수 (kt10000) / 매도 (kt10001) 공통

**엔드포인트**: `/api/dostk/ordr`

**모든 파라미터 값은 문자열(String)**이어야 합니다. 정수를 그대로 보내면 `타입 불일치` 에러 발생.

```python
body = {
    "dmst_stex_tp": "KRX",       # 거래소 구분 (필수)
    "stk_cd": "005930",          # 종목코드 (필수)
    "ord_qty": "4",              # 주문수량 (필수, 문자열!)
    "ord_uv": "0",               # 주문단가 (필수, 시장가="0")
    "trde_tp": "3",              # 매매구분 (필수)
}
```

### 파라미터 상세

| 파라미터 | 설명 | 값 | 비고 |
|----------|------|-----|------|
| `dmst_stex_tp` | 거래소 구분 | `"KRX"`, `"NXT"`, `"SOR"` | 누락 시 1511 에러 |
| `stk_cd` | 종목코드 | `"005930"` | 6자리 문자열 |
| `ord_qty` | 주문수량 | `"4"` | **반드시 문자열**, int 시 1517 에러 |
| `ord_uv` | 주문단가 | `"0"` (시장가), `"50000"` (지정가) | **반드시 문자열** |
| `trde_tp` | 매매구분 | `"0"`=지정가, `"3"`=시장가, `"5"`=조건부지정가 | |

### 주의: 잘못된 파라미터명

공식 API와 다른 이름을 사용하면 `필수입력 파라미터` 에러 발생:

| 잘못된 이름 | 올바른 이름 | 에러 |
|------------|-----------|------|
| `qty` | `ord_qty` | 1511: 필수입력 파라미터 |
| `ordr_prc` | `ord_uv` | 1511: 필수입력 파라미터 |
| `trd_dvsn` | `trde_tp` | 1511: 필수입력 파라미터 |

### 불필요한 파라미터

| 파라미터 | 불필요 이유 |
|----------|-----------|
| `acnt_no` | OAuth 토큰에 계좌 정보 포함 |

### 응답 예시

```json
{
    "ord_no": "0362917",
    "dmst_stex_tp": "KRX",
    "return_code": 0,
    "return_msg": "KRX 매수주문이 완료되었습니다."
}
```

## 실전투자 사전 요구사항

1. openapi.kiwoom.com에서 **지정단말기 IP 등록** 필수 (미등록 시 에러 8050)
2. `curl ifconfig.me`로 현재 IP 확인 후 등록

## Telegram / exec 명령 매핑

OpenClaw 제이(J)가 텔레그램에서 아래 패턴을 인식하면, 반드시 `exec` 도구로 해당 파이썬 스크립트를 실행한 뒤 결과를 SOUL.md에 정의된 투자/데이터 답변 스타일(마크다운 표 + 다음 단계 권장사항)로 요약해서 답변하게 해.

- **"현재가 [종목명]" 또는 "SK하이닉스"**
  - 예: `현재가 SK하이닉스`, `SK하이닉스` 등
  - 동작: exec 도구로 아래 명령 실행

    ```bash
    cd /home/node/.openclaw/workspace/skills/kiwoom-api && \
    python3 kiwoom_api.py get_stock_info 000660
    ```

  - 실행 결과 JSON에서 `stk_nm`, `stk_cd`, `cur_prc`, `flu_rt`를 뽑아서 아래 예시처럼 표로 보여줘:

    | 순위 | 종목명 | 현재가 | 등락률 |
    |------|--------|--------|--------|
    | 1 | SK하이닉스 | 234,500원 | +2.31% |

- **"잔고" 또는 "포트폴리오"**
  - 예: `잔고 보여줘`, `포트폴리오`, `계좌 평가`
  - 동작: exec 도구로 아래 명령 실행

    ```bash
    cd /home/node/.openclaw/workspace/skills/kiwoom-api && \
    python3 kiwoom_api.py get_account_evaluation
    ```

  - 응답 JSON에서 요약 정보(예수금, 추정자산, 오늘 손익 등)를 추려서 표로 정리하고, 보유 종목은 최대 N개까지만 요약해서 보여줘.

- **"데이터 수집"**
  - 예: `데이터 수집 시작`, `데이터 수집`
  - 동작: exec 도구로 아래 명령 실행

    ```bash
    cd /home/node/.openclaw/workspace && \
    python3 data_collector.py
    ```

  - 실행 후 생성된 파일이 있으면 `파일명 | 설명` 형식의 표로 보여주고, 다음 단계(예: 스케줄링, OpenDART 연동 등)를 번호 리스트로 2~3개 제안해.

이 매핑으로 나온 모든 답변은 **반말 + 한국어 + 마크다운 표 + 다음 단계 권장사항** 규칙을 반드시 지키게 해.

## 답변 포맷 강제 규칙

**절대 리스트(•) 형식으로 답변하지 마. 반드시 마크다운 표 형식으로 보여줘.**

- 종목명을 받으면 `normalize_stock_code()` 함수로 종목코드로 변환 후 API 호출
- 결과는 반드시 아래 형식의 표로 보여줘:

```
📊 관심 종목 현황

| 종목명 | 종목코드 | 현재가 | 등락률 |
|--------|----------|--------|--------|
| SK하이닉스 | 000660 | 234,500원 | +2.31% |
| 삼성전자 | 005930 | 78,200원 | -0.89% |

🚀 다음 단계 권장사항
1. 특정 종목 상세 분석: "분석 SK하이닉스"
2. 매수 주문: "매수 SK하이닉스 10주"
3. 전체 포트폴리오: "잔고"
```

리스트 형식(•)으로 답변하면 안 돼. 표 형식만 사용해.
