# 워크스페이스 정리·리팩토링 검사 요약

## 1. 삭제 권장 (중복·불필요)

### 1-1. 백업 파일 (즉시 삭제 가능)
| 경로 | 비고 |
|------|------|
| `stocks/stock_trading_agent.py.v1.bak` | .gitignore에 `*.v1.*` 있음, 버전관리는 Git으로 |
| `stocks/kiwoom_client.py.v1.bak` | 동일 |
| `stocks/stock_premarket.py.v1.bak` | 동일 |
| `stocks/stock_data_collector.py.v1.bak` | 동일 |

### 1-2. 스크립트·경로 문제
| 항목 | 문제 | 조치 |
|------|------|------|
| `scripts/copy_to_workspace.sh` | `SETUP=/home/wlsdud5035_gmail_com/btc_trading_setup` — 현재 워크스페이스와 사용자 경로 불일치, 루트에 `*.py`/`*.sql` 복사 가정(현재는 `btc/`, `stocks/` 등으로 분리됨) | 사용 안 하면 삭제, 또는 경로·대상 폴더 수정 |
| `scripts/run_dry_test.sh` | `python3 btc_trading_agent.py` 실행 — 루트에 실행 파일 없음(실제는 `btc/btc_trading_agent.py`) | `python3 btc/btc_trading_agent.py` 또는 `.venv/bin/python btc/btc_trading_agent.py`로 수정 |

### 1-3. 스키마 마이그레이션 중복
| 경로 | 비고 |
|------|------|
| `schema/supabase/migrations/20260218103246_create_test_table.sql` | **빈 파일** |
| `schema/supabase/migrations/20260218103257_create_test_table.sql` | 동일 |
| `schema/supabase/migrations/20260218103733_create_test_table.sql` | 동일 |

→ 테스트용이면 하나만 남기거나, 실제 스키마(daily_ohlcv, intraday_ohlcv, trade_executions 등)용 마이그레이션으로 교체 권장.

---

## 2. 로그·캐시 정리

| 항목 | 상태 | 제안 |
|------|------|------|
| `brain/logs/` | **비어 있음** (파일 0개) | 유지해도 됨. 로그 수집할 계획이 없으면 폴더 삭제 가능 |
| `*.log` | .gitignore에 있음, 워크스페이스 내 로그 파일 미발견 | 유지 |
| `__pycache__` | 이미 정리됨 | — |

---

## 3. 폴더·파일 재구조화 제안

### 3-1. 현재 구조 요약
```
.
├── .venv/          # 메인 Python (stocks, btc, 대시보드)
├── brain/          # 뉴스·마켓·일일요약·todos (md + kiwoom_token.json)
├── btc/            # BTC 대시보드·트레이딩·뉴스·백테스트 (5개 py)
├── kiwoom/         # 키움 데이터 수집 (collect_top50, data_collector, opendart 등) — stocks와 역할 겹침
├── memory/         # 날짜별 메모리 md
├── prompts/        # AI 프롬프트 + 대화요약 md
├── schema/         # Supabase 마이그레이션 (현재 빈 테스트 3개)
├── scripts/        # run_dashboard, run_dry_test, run_btc_cron, copy_to_workspace
├── secretary/      # 별도 .venv + 자율 에이전트(Notion 등)
├── skills/         # kiwoom-api, opendart-api, supabase 등 참조용 스킬
├── stocks/         # 주식 트레이딩 에이전트·수집기·키움클라이언트
└── 루트 .md        # README, AGENTS, BOOTSTRAP, IDENTITY, USER, SOUL, TOOLS, MEMORY, HEARTBEAT
```

### 3-2. 역할 중복 (정리 권장)
| 기능 | kiwoom/ | stocks/ | 비고 |
|------|---------|---------|------|
| TOP50 종목 정보 | `kiwoom/collect_top50_stocks.py` (yfinance만, Supabase 저장 없음, 하이닉스 중복 키) | `stocks/stock_data_collector.py` → `collect_top50()` (Supabase upsert) | **실제 사용은 stocks** — kiwoom 쪽은 구버전/미완성 |
| OHLCV·DART 수집 | `kiwoom/data_collector.py`, `data_to_supabase.py`, `opendart_collector.py` | `stocks/stock_data_collector.py` (ohlcv, intraday, financials) | stocks가 단일 진입점으로 사용 중 |

**제안**: `kiwoom/`은 키움 OpenAPI 연동(로그인·주문·잔고)만 두고, **데이터 수집·TOP50은 stocks/ 로 통일**.  
- `kiwoom/collect_top50_stocks.py` → 삭제 또는 `scripts/legacy/` 등으로 이동 후 “deprecated, stock_data_collector.py top50 사용” 주석.

### 3-3. 스크립트 위치 통일
- `scripts/run_dashboard.sh` → 이미 `btc/btc_dashboard.py` 기준으로 동작 (OK).
- `scripts/run_dry_test.sh` → **수정**: 실행 경로를 `btc/btc_trading_agent.py` + `.venv/bin/python` 으로 변경.
- `scripts/run_btc_cron.sh` → 내용 확인 후 btc/stocks 크론과 경로 일치하는지 점검.

### 3-4. 루트 .md 정리
- **유지 권장**: `README.md`, `MEMORY.md`, `USER.md` (프로젝트·사용자 맥락)
- **선택**: `AGENTS.md`, `BOOTSTRAP.md`, `TOOLS.md`, `HEARTBEAT.md`, `IDENTITY.md`, `SOUL.md` — 에이전트/시스템 설정용이면 `docs/` 로 묶어도 됨.

### 3-5. 문서 일원화 제안
- `btc/DASHBOARD_LOADING_REPORT.md`, `stocks/DEPLOY_V2.md`, `stocks/STOCK_TRADING_AGENT_V2_CHANGELOG.md`  
  → `docs/` (예: `docs/btc-dashboard.md`, `docs/stocks-deploy-v2.md`, `docs/stocks-changelog.md`) 로 옮기면 루트가 정리됨.

---

## 4. 리팩토링·품질 검사 요약

### 4-1. Python 문법·import
- `stocks/*.py`, `btc/*.py` — `py_compile` 및 핵심 4개 import 테스트 **통과**.

### 4-2. 의존성·경로
- `stocks/stock_trading_agent.py`, `stock_data_collector.py`, `stock_premarket.py`  
  → `skills/kiwoom-api/.env` 하드코딩 경로 사용.  
  **리팩토링**: `OPENCLAW_WORKSPACE` 또는 공통 env에서 workspace 루트 읽고 `Path(workspace)/"skills/kiwoom-api/.env"` 로 통일 권장.

### 4-3. 대형 파일
- `btc/btc_dashboard.py` — **약 2784줄** (Flask/HTML/JS/CSS 포함).  
  **리팩토링**:  
  - 정적 HTML/JS는 `btc/static/` 또는 `btc/templates/` 로 분리하거나,  
  - 최소한 라우트/API 블록과 프론트 블록을 별도 파일로 나누면 유지보수에 유리.

### 4-4. kiwoom/ vs stocks/
- `stocks/kiwoom_client.py` — 실제 키움 API 호출 (주문·잔고 등).
- `kiwoom/` — 데이터 수집·진단 스크립트.  
  **정리**: “키움 API 클라이언트”는 stocks에 두고, “키움 관련 스크립트/레거시”만 kiwoom에 두거나 scripts 하위로 이동.

### 4-5. secretary/
- 별도 `.venv` (15MB).  
  - 워크스페이스 메인 플로우(stocks/btc)와 독립이면 유지.  
  - 사용하지 않으면 폴더 전체를 아카이브하거나 제외해도 됨.

---

## 5. 실행 순서 제안 (정리 시)

1. **즉시**:  
   - `stocks/*.py.v1.bak` 4개 삭제.  
   - `scripts/run_dry_test.sh` 실행 경로를 `btc/btc_trading_agent.py` + `.venv` 기준으로 수정.
2. **스키마**:  
   - `schema/supabase/migrations/` 빈 3개 파일 삭제 또는 실제 사용 스키마 마이그레이션 1개로 교체.
3. **선택**:  
   - `scripts/copy_to_workspace.sh` 사용 안 하면 삭제.  
   - `kiwoom/collect_top50_stocks.py` deprecated 표시 또는 삭제.  
   - 루트 .md 중 에이전트용은 `docs/` 로 이동.  
   - `btc_dashboard.py` 템플릿/정적 리소스 분리.

이 요약본을 기준으로 단계별로 적용하면 됩니다.
