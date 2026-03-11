# OpenClaw Trading System — Opus 컨설팅 분석 리포트

**분석일**: 2026-03-08
**분석 모델**: Claude Opus 4.6
**코드베이스**: 125 Python 파일, ~26,000 LOC

---

## 📊 Supabase 실거래 데이터 요약

| 시장 | 총 기록 | 청산 | 승률 | 평균 수익률 | 핵심 문제 |
|------|---------|------|------|-------------|-----------|
| BTC | 30건 | 0건 | N/A | N/A | 청산 기록 없음 — 진입만 반복, 손익 미실현 |
| KR | 20건 | 19건 | 0.0% | 0.00% | 전부 손절(-3%) 또는 0% 청산 |
| US | 16건 | 12건 | 0.0% | -3.01% | 12건 모두 stop-loss 청산 |

**진단**: 3개 시장 모두 수익을 내지 못하고 있음. BTC는 진입만 하고 청산 로직이 실질적으로 작동하지 않고, KR/US는 손절만 반복.

---

## 1. 🏗️ OpenClaw 아키텍처 재설계

### 현재 문제의 근본 원인
- `agents/`, `brain/`, `memory/`, `skills/` 폴더가 존재하지만 **실제 매매 루프와 완전히 단절**
- `memory/` 폴더는 빈 상태, `skills/`는 문서만 존재
- `secretary/`, `company/`는 실험적 코드 (production cron 미등록)
- `execution/` (TWAP/VWAP)는 import되지만 실제 사용 안 함
- `backtest/`는 orphaned 상태

### 실제 동작하는 코드 vs 데드 코드
```
[실제 동작] btc/ stocks/ common/ agents/(일부) quant/(일부) dashboard/
[미연결]    memory/ skills/ brain/ execution/ backtest/ company/ secretary/core/
```

### 개선 방향 (P1 — 이번 주)

**최단 경로: memory/ → 매매 루프 연결**

```python
# memory/trade_memory.py
class TradeMemory:
    """최근 거래 기억을 AI 프롬프트에 주입"""

    def __init__(self, supabase_client):
        self.sb = supabase_client

    def get_recent_context(self, market: str, limit: int = 10) -> str:
        """최근 N건 거래를 자연어 요약으로 반환"""
        table = {"btc": "btc_trades", "kr": "trade_executions", "us": "us_trade_executions"}[market]
        rows = self.sb.table(table).select("*").order("created_at", desc=True).limit(limit).execute().data
        return self._format_as_context(rows, market)

    def get_pattern_summary(self, market: str) -> str:
        """최근 30건의 패턴 분석 (승률, 평균 보유기간, 주요 손절 원인)"""
        ...

    def _format_as_context(self, rows, market) -> str:
        """GPT/Claude 프롬프트에 삽입할 형태로 포맷"""
        ...
```

**난이도**: 쉬움 | **임팩트**: 높음 (AI 판단 품질 직결)

**P2 — 이번 달: 불필요 폴더 정리**
- `backtest/` → `quant/backtest/`로 통합 또는 삭제
- `execution/` → 실사용 시까지 `_archive/`로 이동
- `company/` → 실험 레이블 명시 (`experimental/`)

**P3 — 나중에: 멀티에이전트 허브**
- `brain/` → 각 에이전트의 판단 결과 JSON 저장소로 활용
- 공유 Brain DB 테이블: `agent_decisions` (이미 스키마 존재)

---

## 2. 💰 BTC 매매 전략 최적화 (소자본 50만원 기준)

### 현재 파라미터 문제 진단

| 항목 | 현재값 | 문제 |
|------|--------|------|
| 진입 임계 | composite ≥ 43 | 너무 낮아 잡음 진입 발생 |
| 손절 | -3% | 50만원 기준 수수료(0.05%×2=0.1%) 대비 적정 |
| 익절 | +15% | **비현실적** — BTC 일간 변동성 2~5%에서 15%는 드물게 도달 |
| 트레일링 | 2% | 익절 15% 미도달 시 트레일링도 작동 안 함 |
| 타임컷 | 7일 | 적정하나 익절 미도달로 대부분 타임컷 종료 |
| 쿨다운 | 30분 | 과다 진입 방지에 적정 |
| 일일 최대 | 3회 | 50만원에서 3회는 과다 (수수료 3×0.1% = 자본의 0.3%/일) |

### 핵심 문제: 익절 +15%는 소자본 단기매매에서 거의 불가능

**수수료 분석**:
- Upbit 수수료: 매수 0.05% + 매도 0.05% = 왕복 0.1%
- 50만원 × 0.1% = 500원/거래
- 일 3회 × 30일 = 90회 × 500원 = **45,000원/월 수수료** (자본의 9%)

### 개선 방향 (P1 — 이번 주)

```python
# common/config.py 수정
BTC_RISK = {
    "stop_loss_pct": -2.5,        # -3% → -2.5% (수수료 감안)
    "take_profit_pct": 4.0,       # +15% → +4% (현실적 목표)
    "trailing_stop_pct": 1.5,     # 2% → 1.5% (더 타이트하게)
    "time_cut_hours": 72,         # 7일 → 3일 (빠른 회전)
    "cooldown_minutes": 60,       # 30분 → 60분 (진입 빈도 감소)
    "max_daily_trades": 2,        # 3 → 2 (수수료 절감)
    "buy_composite_min": 50,      # 43 → 50 (고확신 진입만)
}
```

**난이도**: 쉬움 | **임팩트**: 높음 (수수료 절감 + 승률 개선)

**P2: 복합스코어 가중치 재조정**
```python
# 현재: F&G + RSI + BB + 거래량 + 추세 + 7일수익률
# 제안: 추세 가중치 2배, F&G 극단값만 반영
COMPOSITE_WEIGHTS = {
    "fear_greed": 10,      # 극단(≤20, ≥80)에서만 ±10
    "rsi_daily": 15,       # RSI 과매도 가중 유지
    "bollinger": 10,       # BB 하단 터치 시
    "volume": 10,          # 평균 대비 급증 시
    "trend": 25,           # ★ 추세 가중치 대폭 상향
    "weekly_return": 10,   # 7일 수익률
    "funding_rate": 10,    # 펀딩비
    "open_interest": 10,   # OI 변화
}
```

---

## 3. 🧠 AI 판단 품질 개선

### 현재 문제의 근본 원인
1. **GPT-4o-mini가 매번 과거 기억 없이 판단** — 같은 실수 반복
2. **시장 국면(레짐) 인식이 판단에 약하게 반영** — DOWNTREND에서도 매수
3. **프롬프트에 최근 거래 결과가 없음** — 학습 피드백 루프 부재

### 개선 방향 (P1 — 이번 주)

**1. 과거 거래 기억 주입 (memory/ 연동)**

```python
# btc/btc_trading_agent.py의 GPT 호출 부분에 추가
from memory.trade_memory import TradeMemory

memory = TradeMemory(supabase)
recent_context = memory.get_recent_context("btc", limit=10)

prompt = f"""
{existing_prompt}

## 최근 10회 거래 기록 (반드시 참고)
{recent_context}

## 주의사항
- 최근 연속 손절이 {loss_streak}회 발생했습니다
- 최근 평균 보유시간: {avg_hold_hours}시간
- 가장 빈번한 손절 원인: {top_loss_reason}
"""
```

**2. 프롬프트에 즉시 추가해야 할 컨텍스트 3가지**
1. **최근 5회 거래 결과** (승/패, 수익률, 이유)
2. **현재 시장 레짐** (UPTREND/SIDEWAYS/DOWNTREND + 근거)
3. **당일 이미 실행한 거래 수** (일일 한도 대비 잔여)

**3. GPT-4o-mini → Claude 전환 시점**
- 현재 GPT-4o-mini 비용: ~$0.15/1M input, ~$0.60/1M output
- Claude Haiku 4.5: ~$0.80/1M input, ~$4.00/1M output (5배 비쌈)
- **권장**: GPT-4o-mini 유지하되, **주간 회고(reflection)**만 Claude Sonnet으로 실행
- 판단 품질 개선은 모델 교체보다 **프롬프트 개선 + 기억 주입**이 ROI 높음

**난이도**: 보통 | **임팩트**: 매우 높음

---

## 4. 🗄️ 메모리 시스템 설계

### 현재 상태
- `memory/` 폴더: 빈 상태
- 거래 데이터는 Supabase에 있지만 AI 판단 시 활용하지 않음

### 구현 스펙 (P1 — 이번 주)

```python
# memory/__init__.py
from memory.trade_memory import TradeMemory
from memory.reflection import WeeklyReflection

# memory/trade_memory.py
class TradeMemory:
    """단기 기억: 최근 N건 거래 컨텍스트"""

    def get_recent_context(self, market: str, limit: int = 10) -> str:
        """Supabase에서 최근 거래 조회 → 자연어 요약"""
        ...

    def get_loss_streak(self, market: str) -> int:
        """현재 연속 손절 횟수"""
        ...

    def get_avg_hold_duration(self, market: str) -> float:
        """평균 보유 시간 (시간 단위)"""
        ...

# memory/reflection.py
class WeeklyReflection:
    """장기 기억: 주간 회고 자동화"""

    def run_reflection(self, market: str) -> dict:
        """
        1. 주간 거래 데이터 수집
        2. GPT/Claude에게 자기 판단 평가 요청
        3. 패턴 분석 결과를 brain/reflections/ 에 JSON 저장
        4. 다음 주 판단 시 이 결과를 프롬프트에 포함
        """
        ...

    def get_latest_reflection(self, market: str) -> str:
        """가장 최근 회고 결과 반환 (프롬프트 주입용)"""
        ...
```

**저장 위치**:
- 단기 기억: Supabase 직접 조회 (추가 테이블 불필요)
- 장기 기억: `brain/reflections/{market}_weekly_{date}.json`

**난이도**: 보통 | **임팩트**: 높음

---

## 5. 🤖 Secretary(텔레그램 비서) 강화

### 현재 상태
- `secretary/` — 단순 알림 전송만 (`send_telegram()`)
- `secretary/core/` — 실험적 코드 (메모리, 승인, 리서치, Notion 연동) 존재하나 미연결
- `stocks/telegram_bot.py` — `/status`, `/balance`, `/sell_all` 등 명령어 존재

### 개선 방향 (P2 — 이번 달)

**1단계: 기존 telegram_bot.py에 명령어 추가**

```python
# stocks/telegram_bot.py에 추가할 핸들러
@bot.message_handler(commands=['report'])
def handle_report(message):
    """3개 시장 통합 일일 리포트"""
    from common.alert_system import AlertSystem
    alert = AlertSystem()
    stats = alert._get_today_statistics()
    # 마크다운 포맷 리포트 전송

@bot.message_handler(commands=['pause'])
def handle_pause(message):
    """특정 시장 매매 일시정지"""
    # brain/pause_flags.json에 플래그 설정
    # 각 에이전트가 시작 시 플래그 확인

@bot.message_handler(commands=['regime'])
def handle_regime(message):
    """현재 시장 레짐 조회"""
    # agents/regime_classifier.py 호출
```

**2단계 (P3): 자연어 대화형 비서**
- secretary/core/의 기존 코드를 telegram_bot.py에 통합
- LLM 기반 자연어 명령 해석 (`매매 멈춰`, `지금 어떤 상태야?`)

**난이도**: 1단계 쉬움, 2단계 어려움 | **임팩트**: 중간 (운영 편의성)

---

## 6. 📊 대시보드 개선

### 현재 상태
- FastAPI + React (Lightweight Charts) on port 8080
- 50+ API 엔드포인트 존재
- HTTP Basic Auth 적용 완료 (보안 패치 완료)
- GCP e2-small에서 운영 중

### 개선 방향 (P2 — 이번 달)

**1. 판단 근거 시각화 (왜 매수/매도했는지)**
```python
# btc/routes/btc_api.py에 추가
@router.get("/api/btc/decision-log")
async def get_decision_log():
    """최근 판단 로그 (AI reason + 지표 스냅샷)"""
    rows = supabase.table("btc_trades") \
        .select("timestamp, action, confidence, reason, indicator_snapshot") \
        .order("timestamp", desc=True).limit(20).execute().data
    return {"decisions": rows}
```

**2. 성과 분석 패널**
- `common/sheets_manager.py`에 이미 MDD/샤프/손익비 계산 구현되어 있음
- 이를 API로 노출하고 프론트엔드 차트에 연결

**3. GCP e2-small 최적화**
- 현재 메모리: ~4.2GB 사용 가능 (총 7.95GB)
- FastAPI + React SPA는 가벼움 (~100MB)
- **주의**: 모든 에이전트 + 대시보드 동시 실행 시 메모리 부족 가능
- 권장: `gunicorn` worker 1개 유지, WebSocket 대신 polling

**난이도**: 보통 | **임팩트**: 포트폴리오 가치 높음

---

## 7. 📁 파일/폴더 구조 정리

### 현재 문제
```
workspace/                      상태
├── agents/                     [부분 활성] 7개 에이전트, 일부만 cron 등록
├── backtest/                   [ORPHANED] 어디서도 import 안 됨
├── brain/                      [미활용] alpha/ 결과만 저장
├── btc/                        [활성] BTC 에이전트 + 대시보드
├── common/                     [활성] 공통 유틸
├── company/                    [실험] AI 소프트웨어 회사 (미등록)
├── dashboard/                  [미사용] btc/에 통합됨
├── docs/                       [활성] 문서
├── execution/                  [미사용] TWAP/VWAP (import만 됨)
├── memory/                     [빈 폴더]
├── prompts/                    [활성] AI 프롬프트
├── quant/                      [부분 활성] 팩터/평가기만 사용
├── schema/                     [활성] SQL 스키마
├── scripts/                    [활성] cron 래퍼
├── secretary/                  [미사용] 실험적 비서
├── skills/                     [문서만] 구현 없음
├── stocks/                     [활성] KR/US 에이전트
├── supabase/                   [활성] DB 관련
└── tests/                      [미활용] 수동 테스트만
```

### 정리 방안 (P2 — 이번 달)

```python
# 제안: 3단계 정리

# 1단계: 즉시 삭제/이동
# dashboard/ → 삭제 (btc/에 이미 통합)
# backtest/ → quant/backtest/ 로 이동 또는 삭제

# 2단계: 실험 폴더 명시
# company/ → _experimental/company/
# secretary/core/ → _experimental/secretary/
# execution/ → _experimental/execution/

# 3단계: 빈 폴더 구현 또는 삭제
# memory/ → 이번 주 구현 (Section 4)
# skills/ → 삭제 (문서만 있음)
```

**포트폴리오용 깔끔한 구조**:
```
workspace/
├── agents/          # AI 분석 에이전트 (뉴스, 레짐, 전략)
├── btc/             # BTC 자동매매 + 대시보드
├── stocks/          # KR/US 주식 자동매매
├── quant/           # 퀀트 엔진 (팩터, 백테스트, 최적화)
├── memory/          # AI 기억 시스템 (단기/장기)
├── common/          # 공통 유틸리티
├── brain/           # AI 판단 결과 저장소
├── scripts/         # 자동화 스크립트
├── schema/          # DB 스키마
├── docs/            # 시스템 문서
└── tests/           # 테스트 코드
```

**난이도**: 쉬움 | **임팩트**: 포트폴리오 가치 높음

---

## 8. 🔒 보안 및 운영 안정성

### 이미 완료된 보안 패치 (2026-03-08)
- [x] `company/tools.py`: shell injection 방지 (shell=True 제거, blocklist 확장)
- [x] `stocks/ml_model.py`: pickle → XGBoost native `.ubj`
- [x] `btc/btc_dashboard.py`: path traversal 방지 + auth 필수 + rate limiting
- [x] API routes: error info leakage 수정 (8곳)
- [x] `common/sheets_manager.py`: hardcoded Sheet ID → env var

### 추가 필요 사항 (P1)

**1. .env 파일 권한 확인**
```bash
# 현재 확인 필요
chmod 600 /home/wlsdud5035/.openclaw/.env
# .gitignore에 .env 포함 확인
```

**2. API 키 노출 위험 체크리스트**
- [ ] `.env`가 `.gitignore`에 포함되어 있는지 확인
- [ ] `openclaw.json` (대시보드 비밀번호)이 gitignore에 있는지 확인
- [ ] 로그 파일에 API 키가 출력되지 않는지 확인
- [ ] Telegram bot token이 에러 메시지에 노출되지 않는지 확인

**3. GCP e2-small 리소스 관리**
```
현재 상태:
- CPU: 2 cores
- RAM: 7.95GB (사용 가능 ~4.2GB)
- Disk: 49GB (사용 28GB)

위험 요소:
- 12개 cron job 동시 실행 시 메모리 스파이크
- ML retrain (XGBoost) + 대시보드 + 3개 에이전트 동시 → OOM 가능
```

**권장: 헬스체크 강화**
```bash
# scripts/check_health.sh에 추가
# 메모리 사용률 80% 초과 시 텔레그램 경고
MEM_PCT=$(free | awk '/Mem/{printf "%.0f", $3/$2*100}')
if [ "$MEM_PCT" -gt 80 ]; then
    curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
         -d "chat_id=${TG_CHAT}&text=⚠️ 메모리 ${MEM_PCT}% 사용 중"
fi
```

**4. 로그 관리**
- 현재: `common/logger.py`로 통합 로깅 중
- 개선: 로그 로테이션 설정 (logrotate 또는 `RotatingFileHandler`)
- 거래 감사 로그: Supabase에 이미 저장 중 (OK)

**난이도**: 쉬움~보통 | **임팩트**: 안정성 높음

---

## 9. 🚀 기술 스택 업그레이드 & 포트폴리오 전략

### 이력서 임팩트를 높이기 위한 TOP 3 기술 추가

| 순위 | 기술 | 이유 | 난이도 |
|------|------|------|--------|
| 1 | **LangChain/LangGraph** | 멀티에이전트 오케스트레이션 → 이미 agents/ 구조 있음 | 보통 |
| 2 | **Docker + GitHub Actions CI** | 배포 자동화 → 현재 CI/CD 없음, 채용시 필수 | 보통 |
| 3 | **MLflow** | ML 실험 추적 → XGBoost 모델 버전 관리 | 쉬움 |

### 포트폴리오 스토리 작성 방향

**제목**: "AI 에이전트 기반 멀티마켓 자동매매 시스템"

**핵심 키워드**:
- Multi-Agent Architecture (5 AI agents collaborating)
- Real-time Trading (BTC live + KR/US simulation)
- ML Pipeline (XGBoost + walk-forward validation + SHAP)
- Self-Improving System (weekly reflection + parameter auto-optimization)
- Full-Stack (FastAPI backend + React dashboard)

**차별화 포인트**:
1. 단순 백테스트가 아닌 **실거래 운영 경험** (Upbit 실자본)
2. AI가 스스로 학습하는 **자기개선 루프** (Signal Evaluator → Param Optimizer)
3. 125개 파일, 26,000 LOC의 **실제 프로덕션 시스템**

### 로드맵

**단기 (1달)**:
- [ ] Memory 시스템 구현 + 매매 루프 연결
- [ ] BTC 파라미터 현실화 (익절 4%, 일일 2회)
- [ ] Docker 컨테이너화
- [ ] README.md 작성 (아키텍처 다이어그램 포함)

**중기 (3달)**:
- [ ] GitHub Actions CI/CD 파이프라인
- [ ] LangGraph 기반 에이전트 오케스트레이션
- [ ] MLflow 실험 추적
- [ ] 테스트 커버리지 50% 이상

### 취업 관점에서 가장 먼저 완성해야 할 것

1. **README.md + 아키텍처 다이어그램** — 리크루터/면접관이 처음 보는 것
2. **Docker + CI** — 현대 개발 프로세스 이해 증명
3. **실거래 수익 기록** — "돈을 벌었다"는 사실이 가장 강력한 증명

---

## 🎯 이번 주 월요일부터 시작할 ACTION PLAN TOP 5

| 순위 | 작업 | 난이도 | 예상 임팩트 | 구현 파일 |
|------|------|--------|-------------|-----------|
| **1** | **BTC 파라미터 현실화** — 익절 15%→4%, 일일 3→2회, 임계 43→50 | 쉬움 | 수익화 직결 | `common/config.py`, `btc/btc_trading_agent.py` |
| **2** | **Memory 시스템 구현** — 최근 10건 거래를 GPT 프롬프트에 주입 | 보통 | AI 판단 품질 | `memory/trade_memory.py`, `btc/btc_trading_agent.py` |
| **3** | **폴더 구조 정리** — dashboard/ 삭제, backtest/ 이동, 실험폴더 분리 | 쉬움 | 포트폴리오 | 폴더 구조 변경 |
| **4** | **README.md 작성** — 아키텍처 다이어그램 + 기술 스택 + 실행 방법 | 쉬움 | 포트폴리오 필수 | `README.md` |
| **5** | **Dockerfile 작성** — 단일 컨테이너로 전체 시스템 실행 | 보통 | 기술 스택 증명 | `Dockerfile`, `docker-compose.yml` |

---

## 부록: 코드베이스 통계

- **총 파일**: 125 Python + 15 JS/JSX + 10 Shell
- **총 LOC**: ~26,000 (Python만)
- **활성 cron**: 12개 (10분~주간 주기)
- **API 엔드포인트**: 50+
- **DB 테이블**: btc_trades, btc_position, trade_executions, us_trade_executions, agent_decisions 등
- **외부 API**: Upbit, 키움증권, OpenAI, Anthropic, Telegram, yfinance, DART
