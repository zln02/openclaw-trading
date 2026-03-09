# Sonnet 구현 명세 #4 — CI/CD + Docker + 테스트 (P2)

> 모든 경로는 `/home/wlsdud5035/.openclaw/workspace/` 기준.
> `01`, `02`, `03` 완료 후 진행.

---

## Task 1: GitHub Actions CI 파이프라인

**신규 파일**: `.github/workflows/ci.yml`

```yaml
name: OpenClaw CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install flake8 isort
          pip install -r requirements.txt
      - name: Lint (flake8)
        run: |
          flake8 --max-line-length=120 --ignore=E501,W503,E402 \
            common/ btc/ stocks/ agents/ quant/ memory/ scripts/*.py
      - name: Import sort check
        run: isort --check-only --diff common/ btc/ stocks/ agents/ quant/

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        env:
          DRY_RUN: "1"
          SUPABASE_URL: "https://mock.supabase.co"
          SUPABASE_SECRET_KEY: "mock-key"
        run: |
          pytest tests/ -v --tb=short --cov=common --cov=quant \
            --cov-report=term-missing --cov-fail-under=30

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check for secrets
        run: |
          # .env 파일이 커밋에 포함되지 않았는지 확인
          if git ls-files | grep -E '\.env$' | grep -v '\.example'; then
            echo "ERROR: .env file tracked in git!"
            exit 1
          fi
      - name: Check for hardcoded keys
        run: |
          # API 키 패턴 검사
          if grep -rn 'sk-[a-zA-Z0-9]\{20,\}' --include='*.py' .; then
            echo "ERROR: Possible hardcoded API key found!"
            exit 1
          fi
```

---

## Task 2: Dockerfile 작성

**신규 파일**: `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY common/ common/
COPY btc/ btc/
COPY stocks/ stocks/
COPY agents/ agents/
COPY quant/ quant/
COPY memory/ memory/
COPY scripts/ scripts/
COPY prompts/ prompts/

# 환경변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 대시보드 포트
EXPOSE 8080

# 기본 진입점: 대시보드
CMD ["python", "-m", "uvicorn", "btc.btc_dashboard:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Task 3: docker-compose.yml 작성

**신규 파일**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "8080:8080"
    env_file: .env
    environment:
      - PYTHONPATH=/app
    volumes:
      - ./brain:/app/brain
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/system"]
      interval: 60s
      timeout: 10s
      retries: 3

  btc-agent:
    build: .
    command: ["python", "btc/btc_trading_agent.py"]
    env_file: .env
    environment:
      - PYTHONPATH=/app
    volumes:
      - ./brain:/app/brain
      - ./logs:/app/logs
    restart: unless-stopped
    depends_on:
      - dashboard

  kr-agent:
    build: .
    command: ["python", "stocks/stock_trading_agent.py"]
    env_file: .env
    environment:
      - PYTHONPATH=/app
    volumes:
      - ./brain:/app/brain
      - ./logs:/app/logs
    restart: unless-stopped

  us-agent:
    build: .
    command: ["python", "stocks/us_stock_trading_agent.py"]
    env_file: .env
    environment:
      - PYTHONPATH=/app
    volumes:
      - ./brain:/app/brain
      - ./logs:/app/logs
    restart: unless-stopped
```

---

## Task 4: 핵심 유닛 테스트 작성

**신규 디렉토리**: `tests/`

### 4-1. 테스트 설정

**`tests/conftest.py`**:
```python
import pytest
import os
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 테스트 환경변수
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "mock-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("UPBIT_ACCESS_KEY", "test-key")
os.environ.setdefault("UPBIT_SECRET_KEY", "test-key")


@pytest.fixture
def sample_kr_trade():
    return {
        "trade_id": "test-001",
        "symbol": "005930",
        "trade_type": "SELL",
        "entry_price": 70000,
        "price": 72100,
        "quantity": 10,
        "pnl_pct": 3.0,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }


@pytest.fixture
def sample_us_trade():
    return {
        "trade_id": "test-002",
        "symbol": "AAPL",
        "trade_type": "SELL",
        "entry_price": 180.0,
        "exit_price": 185.4,
        "quantity": 5,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }


@pytest.fixture
def sample_btc_trade():
    return {
        "id": "test-003",
        "action": "SELL",
        "entry_price": 95000000,
        "price": 97850000,
        "pnl": 2850000,
        "result": "CLOSED",
        "created_at": "2026-03-09T10:00:00Z",
    }
```

### 4-2. common/metrics.py 테스트

**`tests/test_metrics.py`**:
```python
from common.metrics import calc_trade_pnl, calc_win_rate, calc_sharpe


class TestCalcTradePnl:
    def test_from_pnl_pct(self, sample_kr_trade):
        assert calc_trade_pnl(sample_kr_trade) == 3.0

    def test_from_exit_entry_price(self, sample_us_trade):
        del sample_us_trade["pnl_pct"]  # pnl_pct 없는 경우
        pnl = calc_trade_pnl(sample_us_trade, market="us")
        assert pnl is not None
        assert abs(pnl - 3.0) < 0.1

    def test_from_pnl_absolute(self, sample_btc_trade):
        pnl = calc_trade_pnl(sample_btc_trade, market="btc")
        assert pnl is not None
        assert pnl > 0

    def test_missing_data(self):
        assert calc_trade_pnl({}) is None
        assert calc_trade_pnl({"pnl_pct": None}) is None

    def test_zero_entry_price(self):
        trade = {"entry_price": 0, "price": 100, "pnl": 100}
        # pnl 있고 entry_price 0이면 % 변환 불가 → exit/entry 폴백
        result = calc_trade_pnl(trade)
        assert result is None or result == 0  # 둘 다 합리적


class TestCalcWinRate:
    def test_all_wins(self):
        trades = [{"pnl_pct": 1.0}, {"pnl_pct": 2.0}, {"pnl_pct": 0.5}]
        assert calc_win_rate(trades) == 1.0

    def test_mixed(self):
        trades = [{"pnl_pct": 1.0}, {"pnl_pct": -2.0}]
        assert calc_win_rate(trades) == 0.5

    def test_empty(self):
        assert calc_win_rate([]) == 0.0


class TestCalcSharpe:
    def test_basic(self):
        pnls = [0.01, 0.02, -0.01, 0.03, 0.01]
        sharpe = calc_sharpe(pnls)
        assert sharpe > 0

    def test_zero_std(self):
        assert calc_sharpe([0.01, 0.01, 0.01]) == 0.0

    def test_insufficient_data(self):
        assert calc_sharpe([0.01]) == 0.0
```

### 4-3. 리스크 관리 테스트

**`tests/test_risk.py`**:
```python
from quant.risk.position_sizer import kelly_fraction


class TestKellyFraction:
    def test_positive_edge(self):
        # 승률 60%, 보상비 2:1
        k = kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        assert 0 < k < 1

    def test_no_edge(self):
        # 승률 50%, 보상비 1:1 → Kelly = 0
        k = kelly_fraction(win_rate=0.5, avg_win=1.0, avg_loss=1.0)
        assert k == 0.0

    def test_negative_edge(self):
        k = kelly_fraction(win_rate=0.3, avg_win=1.0, avg_loss=1.0)
        assert k <= 0
```

### 4-4. 캐시 테스트

**`tests/test_cache.py`**:
```python
import time
from common.cache import get_cached, set_cached, ttl_cache, clear_cache


class TestTTLCache:
    def setup_method(self):
        clear_cache()

    def test_set_and_get(self):
        set_cached("test_key", "test_value", ttl=60)
        assert get_cached("test_key") == "test_value"

    def test_expired(self):
        set_cached("test_key", "test_value", ttl=0.1)
        time.sleep(0.2)
        assert get_cached("test_key") is None

    def test_decorator(self):
        call_count = 0

        @ttl_cache(ttl=60)
        def expensive_fn(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive_fn(5) == 10
        assert expensive_fn(5) == 10  # 캐시 히트
        assert call_count == 1
```

### 4-5. 유틸 테스트

**`tests/test_utils.py`**:
```python
from common.utils import safe_float, parse_json_from_text


class TestSafeFloat:
    def test_valid(self):
        assert safe_float("3.14") == 3.14
        assert safe_float(42) == 42.0

    def test_invalid(self):
        assert safe_float("abc", default=0.0) == 0.0
        assert safe_float(None, default=-1.0) == -1.0


class TestParseJsonFromText:
    def test_plain_json(self):
        result = parse_json_from_text('{"action": "BUY"}')
        assert result == {"action": "BUY"}

    def test_markdown_wrapped(self):
        text = 'Here is the result:\n```json\n{"action": "SELL"}\n```'
        result = parse_json_from_text(text)
        assert result == {"action": "SELL"}

    def test_invalid(self):
        assert parse_json_from_text("no json here") is None
```

---

## Task 5: pytest 설정

**신규 파일**: `pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**requirements.txt에 추가** (개발 의존성):
```
# 마지막에 추가
pytest>=7.0.0
pytest-cov>=4.0.0
```

---

## Task 6: .dockerignore 작성

**신규 파일**: `.dockerignore`
```
.git
.venv
venv
__pycache__
*.pyc
.env
.env.local
*.log
brain/
logs/
node_modules/
dashboard/node_modules/
.claude/
secretary/.venv/
*.bak
*.backup
```

---

## Task 7: 폴더 구조 정리

### 7-1. 삭제 대상
```bash
# dashboard/ 폴더는 유지 (소스코드). btc/dist/가 빌드 결과물.
# 이미 btc/에 통합된 중복 파일만 제거.
```

### 7-2. 실험 폴더 명시
```bash
# 현재 미사용 폴더에 README 추가
echo "# Experimental — 프로덕션 미등록" > execution/README.md
echo "# Experimental — 프로덕션 미등록" > company/README.md
```

### 7-3. tests/ 위치
```
workspace/
├── tests/
│   ├── conftest.py
│   ├── test_metrics.py
│   ├── test_risk.py
│   ├── test_cache.py
│   └── test_utils.py
```

---

## Task 8: pre-commit 설정 (선택)

**신규 파일**: `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120', '--ignore=E501,W503,E402']

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

---

## 실행 순서

1. Task 4 (테스트 작성) — 가장 먼저 (다른 태스크 검증에 사용)
2. Task 5 (pytest 설정) — 테스트 실행 환경
3. Task 1 (GitHub Actions) — CI 파이프라인
4. Task 2 (Dockerfile) — 컨테이너화
5. Task 3 (docker-compose) — 서비스 오케스트레이션
6. Task 6 (.dockerignore) — 빌드 최적화
7. Task 7 (폴더 정리) — 구조 개선
8. Task 8 (pre-commit) — 선택적

**각 태스크 완료 후 개별 커밋.**
