# 키움증권 API 환경 설정 레퍼런스

## 환경 구분

| 환경 | Base URL | 용도 |
|------|----------|------|
| 모의투자 (MOCK) | https://mockapi.kiwoom.com | 개발/테스트 |
| 실전투자 (PRODUCTION) | https://api.kiwoom.com | 운영 |

## 인증 정보 설정

모든 인증 정보는 **프로젝트 루트의 `.env` 파일**에서 관리합니다.

```bash
# 프로젝트 루트에서
cp .env.example .env
# .env 파일 편집
```

## 환경 변수

```bash
# 거래 환경 (mock 또는 prod)
TRADING_ENV=mock

# API 인증
KIWOOM_REST_API_KEY=your_api_key_here
KIWOOM_REST_API_SECRET=your_api_secret_here

# 계좌번호 (모의투자 계좌는 50으로 시작)
KIWOOM_ACCOUNT_NO=5012345678
```

## 환경 전환 방법

`.env` 파일에서 `TRADING_ENV` 값을 변경합니다:

```bash
# 모의투자 (개발/테스트)
TRADING_ENV=mock

# 실전투자 (운영)
TRADING_ENV=prod
```

## Python에서 환경 확인

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
project_root = Path(__file__).parent
while not (project_root / ".env").exists():
    project_root = project_root.parent

load_dotenv(project_root / ".env")

# 환경 확인
trading_env = os.getenv("TRADING_ENV", "mock")

if trading_env == "mock":
    base_url = "https://mockapi.kiwoom.com"
    print("✅ 모의투자 환경")
else:
    base_url = "https://api.kiwoom.com"
    print("⚠️ 실전투자 환경")
```

## 환경별 API Key

### 모의투자
- `.env` 파일에 모의투자용 API Key/Secret 설정
- `TRADING_ENV=mock`

### 실전투자
- `.env` 파일에 실전투자용 API Key/Secret 설정
- `TRADING_ENV=prod`

## 안전 수칙

### 모의투자 (권장)
- ✅ 개발 및 테스트
- ✅ 전략 검증
- ✅ 백테스팅
- ✅ 무제한 실험

### 실전투자 (신중히)
- ⚠️ 검증 완료 후에만
- ⚠️ 소액으로 시작
- ⚠️ 조회 API 위주
- 🚨 거래 API 극도로 신중
