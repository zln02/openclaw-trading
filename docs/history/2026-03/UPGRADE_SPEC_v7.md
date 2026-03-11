# OpenClaw Trading System — Upgrade Specification v7.0

> **목적**: Codex 5.4가 이 문서를 읽고 코드를 구현할 수 있도록 작성된 전략 스펙.
> 각 섹션은 독립적으로 구현 가능하며, 우선순위 순서로 정렬됨.
> **작성일**: 2026-03-11

---

## 목차

1. [Phase A] 기존 미연결 모듈 와이어링 (즉시 효과)
2. [Phase B] ML 모델 고도화 (XGBoost → 앙상블)
3. [Phase C] Level 6 — Multi-Strategy Portfolio
4. [Phase D] Level 7 — On-chain DEX Arbitrage
5. [Phase E] Public API for External Traders
6. [Phase F] Mobile Dashboard (React Native)
7. [Phase G] OpenClaw 플랫폼 통합 강화

---

## Phase A: 기존 미연결 모듈 와이어링

### 문제

코드는 존재하지만 실제 매매 루프에 연결되지 않은 모듈이 6개 있음.
이것만 연결해도 즉시 리스크 관리 수준이 올라감.

### A-1. DrawdownGuard → 에이전트 매매 루프 연결

**현재**: `quant/risk/drawdown_guard.py`에 3단계 캐스케이드(일간 -2% 매수차단, 주간 -5% 50%청산, 월간 -10% 전량청산+7일 쿨다운) 구현 완료. 하지만 `btc_trading_agent.py`, `stock_trading_agent.py`, `us_stock_trading_agent.py` 어디에서도 호출하지 않음.

**구현 방향**:
```
# 각 에이전트의 매매 사이클 시작부에 추가
from quant.risk.drawdown_guard import DrawdownGuard

guard = DrawdownGuard()
equity_curve = _load_equity_curve_from_supabase(market="btc")  # 새 헬퍼
result = guard.check(equity_curve)

if result.action == "BLOCK_BUY":
    log.warning(f"DrawdownGuard: 매수 차단 (일간 수익률 {result.daily_return:.1%})")
    return  # 매수 로직 스킵, 기존 포지션 유지
elif result.action == "DELEVERAGE":
    log.warning(f"DrawdownGuard: 50% 청산 (주간 수익률 {result.weekly_return:.1%})")
    _deleverage_50pct()
elif result.action == "FULL_STOP":
    log.critical(f"DrawdownGuard: 전량 청산 + 7일 쿨다운")
    _liquidate_all()
    _set_cooldown(days=7)
```

**수정 파일**:
- `btc/btc_trading_agent.py` — `run_cycle()` 최상단
- `stocks/stock_trading_agent.py` — `run()` 최상단
- `stocks/us_stock_trading_agent.py` — `run()` 최상단
- 신규 헬퍼: `common/equity_loader.py` — Supabase에서 equity curve 로드

**주의**: drawdown_guard.py 자체는 수정하지 말 것. 호출부만 추가.

---

### A-2. KellyPositionSizer → 에이전트 포지션 크기 결정

**현재**: `quant/risk/position_sizer.py`에 Half-Kelly + 변동성 스케일링 + 5% 상한 구현 완료. 하지만 에이전트들은 `config.py`의 고정 `INVEST_RATIO`(25~30%) 사용 중.

**구현 방향**:
```
# execute_buy() 내부에서 고정 비율 대신 Kelly 사용
from quant.risk.position_sizer import KellyPositionSizer

sizer = KellyPositionSizer()
trades = _load_recent_trades(market, limit=100)
win_rate = calc_win_rate(trades)
avg_win = mean([t.pnl_pct for t in trades if t.pnl_pct > 0]) or 0.02
avg_loss = abs(mean([t.pnl_pct for t in trades if t.pnl_pct < 0])) or 0.03

kelly_fraction = sizer.calculate(
    win_prob=win_rate,
    win_loss_ratio=avg_win / max(avg_loss, 0.001),
    atr_pct=current_atr_pct,
    conviction=composite_score / 100  # 0~1 스케일
)
invest_amount = total_equity * kelly_fraction
```

**수정 파일**:
- `btc/btc_trading_agent.py` — `execute_buy()`
- `stocks/stock_trading_agent.py` — `execute_buy()`
- `stocks/us_stock_trading_agent.py` — `execute_buy()`

**폴백**: 거래 이력 50건 미만이면 기존 고정 비율 유지.

---

### A-3. SmartRouter → 에이전트 주문 실행

**현재**: `execution/smart_router.py`에 금액 기반 라우팅(≤1M→MARKET, ≤5M→TWAP, >5M→VWAP) + 스프레드 오버라이드 구현 완료. 하지만 에이전트들은 `kiwoom_client.place_order()` 직접 호출.

**구현 방향**:
```
# 기존: kiwoom.place_order(ticker, qty, price)
# 변경: SmartRouter가 주문 방식 결정
from execution.smart_router import SmartRouter

router = SmartRouter(broker=kiwoom_client)
fill = await router.execute(
    ticker=ticker,
    side="BUY",
    quantity=qty,
    notional_krw=qty * price,
    spread_bps=current_spread_bps
)
log.info(f"SmartRouter: {fill.route_type}, slippage={fill.slippage_bps:.1f}bps")
```

**수정 파일**:
- `stocks/stock_trading_agent.py` — `execute_buy()`, `execute_sell()`
- BTC/US는 거래소 API 특성상 MARKET 주문만 유효하므로 KR만 적용

**주의**: SmartRouter 내부 TWAP/VWAP는 비동기. `asyncio` 래퍼 필요할 수 있음.

---

### A-4. PortfolioOptimizer → 주간 리밸런싱

**현재**: `quant/portfolio/optimizer.py`에 Mean-Variance/Risk-Parity/Black-Litterman 3가지 방법 구현. 호출하는 곳 없음.

**구현 방향**: 주간 리서치 루프에 추가 (일요일 param_optimizer 직후)
```
# scripts/run_portfolio_rebalance.sh (신규)
# crontab: 일요일 23:45

from quant.portfolio.optimizer import PortfolioOptimizer

optimizer = PortfolioOptimizer(method="risk_parity")
current_positions = load_all_positions()  # BTC + KR + US
target_weights = optimizer.optimize(
    assets=current_positions,
    covariance=calc_rolling_cov(lookback=60),
    expected_returns=load_signal_scores()
)

# brain/portfolio/target_weights.json에 저장
# 월요일 에이전트 시작 시 로드하여 과대/과소 포지션 조절
```

**신규 파일**:
- `scripts/run_portfolio_rebalance.sh`
- `brain/portfolio/target_weights.json` (출력)

**수정 파일**:
- 각 에이전트의 `run()` — 시작 시 target_weights 로드, 과대 포지션이면 매수 스킵

---

### A-5. VaR → 실시간 리스크 모니터링

**현재**: `quant/risk/var_model.py`에 Historical/Parametric VaR + CVaR 구현. 독립 실행만 가능.

**구현 방향**: `agents/alert_manager.py`에 VaR 체크 추가
```
from quant.risk.var_model import VaRModel

var_model = VaRModel(confidence=0.99)
portfolio_var = var_model.calculate(positions, returns_252d)

if portfolio_var > MAX_PORTFOLIO_VAR:  # config.py에 추가: 0.05 (5%)
    send_telegram(f"⚠️ Portfolio VaR {portfolio_var:.1%} > 한도 {MAX_PORTFOLIO_VAR:.1%}")
    # DrawdownGuard BLOCK_BUY와 연계
```

---

### A-6. 에이전트 팀 결정 → ML 피드백 루프

**현재**: `agents/trading_agent_team.py`가 Supabase `agent_decisions`에 결정 저장. 이 데이터를 ML이나 signal_evaluator가 사용하지 않음.

**구현 방향**: `quant/signal_evaluator.py`에 agent_team 신호 추가
```
# signal_evaluator.py의 SIGNAL_SOURCES에 추가
"agent_team_confidence": {
    "table": "agent_decisions",
    "column": "confidence",
    "join_key": "created_at"  # trade_executions.created_at과 시간 매칭 (±30분)
}
```

---

## Phase B: ML 모델 고도화

### 현재 상태

| 항목 | 현재 | 문제 |
|------|------|------|
| 모델 | XGBClassifier 1개 | 단일 모델 과적합 리스크 |
| 피처 | 기술적 지표 20개 | quant/factors/ 20개 팩터 미사용 |
| 예측 | 3일 수익률 ≥ 2% → BUY | 단일 기간, 단일 임계값 |
| 검증 | TimeSeriesSplit 5-fold | 충분하나 앙상블 시 조정 필요 |
| 재학습 | 수동 트리거 (50건 이상) | 드리프트 감지 없음 |

### B-1. 앙상블 스태킹 (XGBoost + LightGBM + CatBoost)

**구현 위치**: `stocks/ml_model.py` 확장

**아키텍처**:
```
Layer 1 (Base Models):
  ├── XGBClassifier (기존, n_estimators=200, max_depth=5)
  ├── LGBMClassifier (신규, n_estimators=300, num_leaves=31, learning_rate=0.03)
  └── CatBoostClassifier (신규, iterations=300, depth=6, learning_rate=0.03)

Layer 2 (Meta-Learner):
  └── LogisticRegression(C=1.0)  # base model 출력 3개 → 최종 확률

학습 방식:
  - Layer 1: TimeSeriesSplit 5-fold, 각 fold의 OOS 예측값 수집
  - Layer 2: Layer 1의 OOS 예측값으로 학습 (data leakage 방지)
  - 최종 테스트: 마지막 20% 기간에서 Layer1→Layer2 파이프라인 평가
```

**requirements.txt 추가**:
```
lightgbm>=4.0.0
catboost>=1.2.0
```

**저장 형식**:
```
brain/ml/
├── xgb_model.ubj          # XGBoost (기존 경로 유지)
├── lgbm_model.txt          # LightGBM native
├── catboost_model.cbm      # CatBoost native
├── meta_model.pkl          # LogisticRegression (sklearn)
└── ensemble_meta.json      # feature names, thresholds, 학습일, AUC
```

**블렌딩 공식 변경**:
```
# 기존: confidence = rule * 0.6 + xgb * 0.4
# 변경: confidence = rule * 0.5 + ensemble * 0.5
# 앙상블 자체가 3모델 가중 평균이므로 ML 비중 상향
```

**폴백**: LightGBM/CatBoost 학습 실패 시 XGBoost 단독 사용 (기존 로직 유지).

---

### B-2. 피처 엔지니어링 확장 (20 → 45개)

**현재 20개**: 순수 기술적 (RSI, MACD, BB, volume, returns, ATR)

**추가 25개** (3개 카테고리):

#### 팩터 피처 (quant/factors/에서 가져옴, 10개)
```python
FACTOR_FEATURES = [
    "momentum_12m",      # 12개월 수익률
    "momentum_1m",       # 1개월 수익률
    "pe_ratio",          # PER (반전)
    "pb_ratio",          # PBR (반전)
    "roe",               # ROE
    "debt_ratio",        # 부채비율 (반전)
    "revenue_growth",    # 매출성장률
    "earnings_surprise", # 어닝 서프라이즈
    "volume_ratio_20d",  # 20일 거래량비 (이미 기술적에 유사한 것 있으나 팩터 버전)
    "orderbook_imbalance" # 호가 불균형
]
```

**수집 방법**: `quant/factors/registry.py`의 `FactorRegistry.compute(factor_name, context)` 호출.
`FactorContext`에 종목코드 + 날짜 전달하면 Supabase/yfinance에서 자동 조회.

#### 시장 컨텍스트 피처 (5개)
```python
MARKET_FEATURES = [
    "kospi_rsi_14",       # KOSPI RSI (시장 전체 과열도)
    "kospi_return_5d",    # KOSPI 5일 수익률
    "vix_level",          # VIX (yfinance ^VIX)
    "fg_index",           # Fear & Greed Index
    "regime_encoded"      # RISK_ON=3, TRANSITION=2, RISK_OFF=1, CRISIS=0
]
```

#### 수급/이벤트 피처 (10개)
```python
SUPPLY_FEATURES = [
    "foreign_net_buy_5d",    # 외국인 5일 순매수 (KRX)
    "inst_net_buy_5d",       # 기관 5일 순매수
    "short_interest_ratio",  # 공매도 비율
    "days_to_earnings",      # 실적발표까지 남은 일수 (0~30, 없으면 30)
    "sector_momentum_rank",  # 섹터 내 모멘텀 순위 (0~1 percentile)
    "relative_strength_vs_kospi",  # KOSPI 대비 상대강도
    "avg_spread_bps",        # 평균 스프레드 (유동성 프록시)
    "turnover_ratio",        # 회전율 (거래량/시가총액)
    "52w_high_proximity",    # 52주 신고가 근접도 (0~1)
    "market_cap_log"         # 시가총액 log (사이즈 팩터)
]
```

**구현 위치**: `stocks/ml_model.py`의 `_compute_features()` 확장

**결측치 처리**: 팩터/수급 피처는 결측 가능. `XGBoost`는 결측 자체 처리 가능, `LightGBM`도 동일. `CatBoost`도 결측 네이티브 지원. 별도 imputation 불필요.

---

### B-3. 멀티 호라이즌 예측

**현재**: 3일 수익률 ≥ 2% → BUY (단일)

**변경**: 3개 기간 동시 예측
```
Label definitions:
  - short_win:  1일 수익률 ≥ +1%
  - mid_win:    3일 수익률 ≥ +2%  (기존)
  - swing_win: 10일 수익률 ≥ +5%

각 기간별 앙상블 모델 독립 학습 (총 3 × 3 = 9개 base 모델 + 3 meta)

최종 신호 결합:
  if short_prob >= 0.7 and mid_prob >= 0.6:
      action = "STRONG_BUY"  # 단기+중기 동시 확신
  elif mid_prob >= 0.65:
      action = "BUY"         # 기존과 동일
  elif swing_prob >= 0.7 and mid_prob >= 0.5:
      action = "SWING_BUY"   # 장기 관점 진입 (포지션 크기 축소)
```

**저장 구조**:
```
brain/ml/
├── horizon_1d/   # short
├── horizon_3d/   # mid (기존 호환)
└── horizon_10d/  # swing
```

---

### B-4. 피처 드리프트 감지

**신규 파일**: `stocks/ml_drift_monitor.py`

```
매일 08:25 (ML 재학습 전) 실행:

1. 최근 20일 피처 분포 vs 학습 시 피처 분포 비교
2. PSI (Population Stability Index) 계산
   - PSI < 0.1: 안정 → 재학습 불필요
   - 0.1 ≤ PSI < 0.25: 주의 → 텔레그램 알림
   - PSI ≥ 0.25: 위험 → 자동 재학습 트리거 + 텔레그램
3. 개별 피처별 KS-test (p < 0.01 → 해당 피처 드리프트 경보)
4. 결과 저장: brain/ml/drift_report.json
```

**crontab 추가**: 평일 08:25 (기존 08:30 재학습 직전)

---

### B-5. US 주식 ML 도입

**현재**: US 에이전트는 모멘텀 스코어링만 사용 (ML 없음)

**구현**: KR ML 파이프라인을 US에 복제하되 피처 조정
```
US 전용 피처 (KR과 다른 부분):
  - sector_etf_momentum: 섹터 ETF(XLK,XLF...) 대비 상대 모멘텀
  - spy_beta: SPY 대비 60일 베타
  - earnings_revision: 어닝 추정치 변화율 (yfinance .info)
  - options_iv_rank: 옵션 IV percentile (가능 시)

블렌딩: us_confidence = rule * 0.6 + ensemble * 0.4 (KR과 동일 비율)
학습 데이터: yfinance S&P500 일봉 (최근 3년)
라벨: 5일 수익률 ≥ 3% → BUY (US는 변동성 낮으므로 기간/임계값 상향)
```

**저장**: `brain/ml/us/` (KR과 분리)

---

## Phase C: Level 6 — Multi-Strategy Portfolio

### 개요

Level 5까지는 시장별 독립 에이전트(BTC/KR/US). Level 6은 **교차 시장 포트폴리오 관리** + **롱숏 전략** 도입.

### C-1. Cross-Market Portfolio Manager

**신규 파일**: `quant/portfolio/cross_market_manager.py`

```
역할:
  1. BTC + KR + US 전체 포지션을 하나의 포트폴리오로 관리
  2. 시장 간 상관관계 모니터링 (correlation.py 활용)
  3. 시장별 자본 배분 동적 조절

자본 배분 로직:
  base_allocation = {"btc": 0.30, "kr": 0.40, "us": 0.30}

  # 레짐별 조절
  if regime == "CRISIS":
      allocation = {"btc": 0.15, "kr": 0.25, "us": 0.25, "cash": 0.35}
  elif regime == "RISK_OFF":
      allocation = {"btc": 0.20, "kr": 0.35, "us": 0.25, "cash": 0.20}
  elif regime == "RISK_ON":
      allocation = {"btc": 0.35, "kr": 0.40, "us": 0.25, "cash": 0.00}

  # IC 성과 기반 동적 조절: 최근 30일 IC 높은 시장에 +5%p 재배분
  # VaR 기반 제한: 시장별 VaR > 3% 시 해당 시장 배분 축소

출력: brain/portfolio/market_allocation.json
실행: 매일 07:00 (각 시장 에이전트 시작 전)
```

---

### C-2. KR 주식 롱숏 전략

**신규 파일**: `stocks/long_short_agent.py`

```
전제조건: 키움증권 신용/대주 가능 계좌 (현재 모의투자이므로 시뮬레이션 모드로 시작)

전략 개요:
  - Long leg: 기존 KR 에이전트의 매수 신호 (상위 5종목)
  - Short leg: 팩터 모델 최하위 5종목 (momentum_12m 하위 + quality 하위)
  - Market neutral 목표: Long notional ≈ Short notional (β ≈ 0)

팩터 기반 숏 선정:
  1. quant/factors/ 에서 momentum_12m, roe, revenue_growth 계산
  2. 종합 팩터 스코어 하위 10% 종목 중
  3. RSI > 70 (과열) + volume_ratio < 0.5 (관심 저하) 필터
  4. 최대 5종목, 각 포지션 포트폴리오의 4%

리스크 제한:
  - 총 숏 노출 ≤ 총 롱 노출 * 1.1
  - 개별 숏 손절: +5% (숏이므로 가격 상승이 손실)
  - 섹터 집중 제한: 동일 섹터 롱+숏 합계 30% 이하
  - CRISIS 레짐 시 숏 전면 청산 (숏 스퀴즈 리스크)

모드:
  - DRY_RUN=1: 시뮬레이션 (Supabase에 가상 거래 기록)
  - DRY_RUN=0: 실거래 (키움 신용매도 API 연동)

Supabase 테이블 (신규):
  CREATE TABLE short_positions (
      id UUID DEFAULT gen_random_uuid(),
      ticker TEXT NOT NULL,
      ticker_name TEXT,
      entry_price NUMERIC,
      current_price NUMERIC,
      quantity INTEGER,
      side TEXT DEFAULT 'SHORT',
      pnl_pct NUMERIC,
      factor_snapshot JSONB,
      created_at TIMESTAMPTZ DEFAULT now(),
      closed_at TIMESTAMPTZ
  );
```

---

### C-3. 시장 중립 모니터

**신규 파일**: `quant/portfolio/neutrality_monitor.py`

```
역할: 롱숏 포트폴리오의 시장 중립성 실시간 감시

메트릭:
  - Net beta: Σ(long_β * weight) - Σ(short_β * weight), 목표 |β| < 0.15
  - Sector exposure: 섹터별 넷 포지션
  - Factor exposure: 팩터별 넷 틸트

이탈 시 행동:
  |β| > 0.15 → 텔레그램 경고
  |β| > 0.30 → 자동 리밸런싱 (최대 노출 포지션 축소)

실행: KR 장중 매 30분 (crontab)
```

---

## Phase D: Level 7 — On-chain DEX Arbitrage

### 개요

CEX(Upbit) 가격과 DEX(Uniswap/SushiSwap) 가격 차이를 이용한 차익거래.
BTC는 WBTC 형태로 DEX에서 거래됨.

### D-1. DEX 가격 모니터

**신규 파일**: `btc/signals/dex_price_monitor.py`

```
데이터 소스:
  - Uniswap V3 (Ethereum): WBTC/USDC 풀 (The Graph API 또는 직접 RPC)
  - SushiSwap: WBTC/WETH 풀
  - Upbit: KRW-BTC (기존 pyupbit)
  - Binance: BTC-USDT (기존)

모니터링:
  1. 10초 간격으로 CEX/DEX 가격 수집
  2. 스프레드 계산:
     - upbit_premium = (upbit_krw / fx_rate - binance_usdt) / binance_usdt
     - dex_premium = (dex_wbtc_usdc - binance_usdt) / binance_usdt
     - cross_arb = dex_wbtc_usdc - upbit_btc_usd (환율 보정)
  3. 가스비 포함 수익성 계산:
     - estimated_gas_eth = gas_price * gas_limit (≈ 200K gas for swap)
     - net_profit = spread * notional - gas_fee_usd - slippage_estimate

의존성 추가 (requirements.txt):
  web3>=7.0.0
  gql>=3.5.0  # The Graph 쿼리
```

---

### D-2. Arbitrage Executor

**신규 파일**: `btc/arb_executor.py`

```
실행 조건:
  - net_profit > MIN_ARB_PROFIT (config.py: $50)
  - gas_price < MAX_GAS_GWEI (config.py: 30 gwei)
  - 슬리피지 추정 < 0.3%

실행 플로우 (CEX→DEX 방향):
  1. Upbit에서 BTC 매도 → KRW 확보
  2. KRW→USDC 환전 (또는 USDT 경유)
  3. DEX에서 USDC→WBTC 스왑
  4. WBTC→BTC unwrap → CEX로 입금

실행 플로우 (DEX→CEX 방향):
  1. DEX에서 WBTC 매도 → USDC 확보
  2. USDC→KRW 환전
  3. Upbit에서 BTC 매수

주의사항:
  - Phase D는 전체 DRY_RUN 모드로 시작 (시뮬레이션만)
  - 실거래 전환 전 최소 30일 시뮬레이션 + 수익성 검증 필수
  - 온체인 트랜잭션은 되돌릴 수 없으므로 gas 추정 정확성이 핵심
  - MEV(Maximal Extractable Value) 리스크: Flashbots Protect RPC 사용 권장

Supabase 테이블 (신규):
  CREATE TABLE arb_opportunities (
      id UUID DEFAULT gen_random_uuid(),
      direction TEXT,  -- 'cex_to_dex' or 'dex_to_cex'
      cex_price NUMERIC,
      dex_price NUMERIC,
      spread_pct NUMERIC,
      gas_cost_usd NUMERIC,
      net_profit_usd NUMERIC,
      executed BOOLEAN DEFAULT false,
      tx_hash TEXT,
      created_at TIMESTAMPTZ DEFAULT now()
  );
```

---

### D-3. Flashloan Arbitrage (고급)

**신규 파일**: `btc/flashloan_arb.py`

```
개념: 자본 없이 단일 트랜잭션 내에서 차익 실현
  1. Aave V3에서 USDC 플래시론
  2. DEX A에서 USDC→WBTC 스왑
  3. DEX B에서 WBTC→USDC 스왑 (더 비싼 곳)
  4. 플래시론 상환 + 수수료 (0.05%)
  5. 이익 확보

구현:
  - Solidity 스마트 컨트랙트 (FlashLoanArbitrage.sol)
  - Python은 모니터링 + 트리거만 담당
  - 컨트랙트 배포 후 Python에서 web3.py로 호출

우선순위: 낮음 (D-1, D-2 완료 후)
리스크: 실패 시 가스비만 손실 (원금 리스크 없음이 플래시론 장점)
```

---

## Phase E: Public API for External Traders

### 개요

외부 트레이더가 OpenClaw의 시그널을 구독할 수 있는 공개 API.

### E-1. Signal API

**신규 파일**: `api/signal_api.py` (FastAPI Router)

```
엔드포인트:

GET /api/v1/signals/btc
  → { composite_score, regime, trend, fg_index, recommendation, updated_at }

GET /api/v1/signals/kr
  → { top_picks: [{ticker, score, ml_confidence, factors}], regime, updated_at }

GET /api/v1/signals/us
  → { top_picks: [{ticker, momentum_score, grade}], regime, updated_at }

GET /api/v1/signals/regime
  → { current_regime, confidence, factors, history_7d }

GET /api/v1/portfolio/allocation
  → { btc_pct, kr_pct, us_pct, cash_pct, rebalance_due }

인증: API Key (헤더 X-API-Key)
Rate Limit: 60 req/min per key
CORS: 설정 가능 (config)

Supabase 테이블 (신규):
  CREATE TABLE api_keys (
      id UUID DEFAULT gen_random_uuid(),
      key_hash TEXT NOT NULL,  -- bcrypt 해시 저장 (평문 절대 저장 금지)
      user_email TEXT,
      tier TEXT DEFAULT 'free',  -- free: 60/min, pro: 600/min
      created_at TIMESTAMPTZ DEFAULT now(),
      last_used_at TIMESTAMPTZ
  );
```

---

### E-2. WebSocket 실시간 스트림

**신규 파일**: `api/ws_stream.py`

```
ws://host:8080/api/v1/ws/signals

메시지 형식:
  {
    "type": "btc_signal",
    "data": { composite_score, trend, ... },
    "timestamp": "2026-03-11T09:00:00+09:00"
  }

이벤트 종류:
  - btc_signal: BTC 스코어 변경 (10분 간격)
  - kr_trade: KR 매매 실행 시
  - us_trade: US 매매 실행 시
  - regime_change: 레짐 전환 시
  - alert: 리스크 경보 시

인증: 연결 시 query param ?api_key=xxx
```

---

### E-3. Webhook 알림

**신규 파일**: `api/webhook_manager.py`

```
사용자가 webhook URL 등록 → 이벤트 발생 시 POST 전송

POST /api/v1/webhooks
  body: { url, events: ["btc_signal", "regime_change"], secret }

이벤트 발생 시:
  POST {user_url}
  Headers: X-Webhook-Signature: HMAC-SHA256(body, secret)
  Body: { event, data, timestamp }
```

---

## Phase F: Mobile Dashboard (React Native)

### F-1. 앱 구조

**신규 디렉토리**: `mobile/`

```
기술 스택:
  - React Native (Expo) — 크로스 플랫폼 (iOS + Android)
  - React Navigation — 탭/스택 네비게이션
  - TanStack Query (React Query) — 서버 상태 관리
  - Victory Native — 차트
  - Expo Notifications — 푸시 알림

mobile/
├── app/
│   ├── (tabs)/
│   │   ├── btc.tsx        # BTC 대시보드
│   │   ├── kr.tsx         # KR 주식
│   │   ├── us.tsx         # US 주식
│   │   └── settings.tsx   # 설정
│   ├── _layout.tsx
│   └── login.tsx          # API Key 로그인
├── components/
│   ├── PriceCard.tsx
│   ├── SignalBadge.tsx
│   ├── MiniChart.tsx
│   └── TradeList.tsx
├── hooks/
│   ├── useSignals.ts      # Phase E API 호출
│   └── useWebSocket.ts    # 실시간 스트림
├── app.json
└── package.json
```

### F-2. 핵심 화면

```
[BTC 탭]
  ┌─────────────────────────┐
  │ BTC ₩112,500,000  +2.3% │
  │ ████████████░░░░ 스코어 67│
  │ 레짐: RISK_ON  F&G: 42  │
  ├─────────────────────────┤
  │ [24h 미니 캔들차트]       │
  ├─────────────────────────┤
  │ 현재 포지션: 0.05 BTC    │
  │ 수익: +125,000원 (+2.2%) │
  │ 손절: ₩110,125,000       │
  ├─────────────────────────┤
  │ 최근 매매 기록 (5건)      │
  └─────────────────────────┘

[KR 탭]
  ┌─────────────────────────┐
  │ 총 자산: 5,230,000원     │
  │ 일간 PnL: +45,000 (+0.9%)│
  ├─────────────────────────┤
  │ 보유 종목 (카드 리스트)   │
  │ ┌ SK하이닉스  +3.2%     │
  │ │ ML: 82%  팩터: A      │
  │ └───────────────────────│
  ├─────────────────────────┤
  │ TOP 매수 후보 (3종목)     │
  └─────────────────────────┘

[US 탭]
  모멘텀 랭킹 + 포지션 + 환율

[설정]
  API Key 입력, 알림 설정, 테마
```

### F-3. 푸시 알림

```
Expo Push Notification 연동:
  - 매매 실행 시 → "SK하이닉스 10주 매수 (ML 82%)"
  - 레짐 전환 시 → "⚠️ RISK_OFF 전환 — 모멘텀 가중치 축소"
  - 드로우다운 경보 → "🚨 일간 -2.5% — 매수 차단 활성화"
  - 주간 리포트 → "📊 주간 수익률 +3.2%, 승률 65%"

서버 측: api/push_notifier.py → Expo Push API 호출
```

---

## Phase G: OpenClaw 플랫폼 통합 강화

### G-1. openclaw 레포 동기화

**현재**: `/home/wlsdud5035/openclaw/`(GitHub 레포)와 `/home/wlsdud5035/.openclaw/workspace/`(운영)가 별도 관리.

**개선**:
```bash
# workspace가 openclaw 레포의 심볼릭 링크 또는 git worktree가 되도록 통합
# 방안 1: workspace를 openclaw 레포의 worktree로 설정
cd /home/wlsdud5035/openclaw
git worktree add /home/wlsdud5035/.openclaw/workspace main

# 방안 2: 단방향 rsync 동기화 스크립트
# scripts/sync_to_repo.sh
rsync -av --exclude='.env' --exclude='brain/' --exclude='logs/' \
  /home/wlsdud5035/.openclaw/workspace/ /home/wlsdud5035/openclaw/
```

---

### G-2. OpenClaw 스킬 확장

**현재 스킬**: `kiwoom-api/`, `opendart-api/`, `trading-ops/`

**신규 스킬**:

```
skills/
├── portfolio-manager/   # "포트폴리오 현황" → cross_market_manager 호출
│   └── SKILL.md
├── signal-query/        # "BTC 신호 알려줘" → signal_api 호출
│   └── SKILL.md
├── backtest-runner/     # "SK하이닉스 백테스트 돌려줘" → quant/backtest 호출
│   └── SKILL.md
└── risk-report/         # "리스크 리포트" → VaR + DrawdownGuard + Exposure 종합
    └── SKILL.md
```

---

### G-3. 텔레그램 봇 명령어 확장

**현재**: `/status`, `/sell_all`, `/portfolio`, `/report`

**추가 명령어**:
```
/regime         → 현재 시장 레짐 + 팩터 가중치
/allocation     → BTC/KR/US/현금 배분 비율 + 리밸런싱 일정
/var            → 포트폴리오 VaR + CVaR
/ml_status      → ML 모델 상태 (마지막 학습일, AUC, 드리프트 PSI)
/arb            → DEX 차익거래 기회 현황 (Phase D)
/longshort      → 롱숏 포지션 + 넷 베타 (Phase C)
/api_usage      → Public API 사용량 (Phase E)
```

---

## 구현 우선순위 및 의존성

```
Phase A (와이어링)     ← 즉시 착수 가능, 의존성 없음
  ↓
Phase B (ML 고도화)    ← A 완료 후 (Kelly/DrawdownGuard 연결 상태에서 학습)
  ↓
Phase C (Level 6)     ← B 완료 후 (앙상블 ML이 롱숏 신호 제공)
  │
  ├── Phase E (Public API) ← C와 병렬 가능
  └── Phase F (Mobile)     ← E 완료 후 (API 의존)
  │
Phase D (Level 7 Arb)  ← 독립적, 언제든 착수 가능 (단, DRY_RUN 우선)
  │
Phase G (플랫폼)       ← 각 Phase 완료 시 점진적 추가
```

---

## 구현 시 공통 규칙

1. 모든 신규 모듈은 `from common.env_loader import load_env; load_env()` 필수
2. 로깅은 `from common.logger import get_logger; log = get_logger("module")` 사용
3. 설정값은 `common/config.py`에 추가 (하드코딩 금지)
4. 외부 API 호출은 `try/except` + `common/retry.py:retry_call()` 사용
5. Public 함수에 타입 힌트 필수
6. Supabase 접근은 `common/supabase_client.get_supabase()` 사용
7. 테스트: 각 Phase별 `tests/test_phase_{a~g}.py` 작성
8. **리스크 코드 수정 시**: CLAUDE.md의 "Critical Files" 섹션 참조
9. DRY_RUN 모드 지원 필수: 실거래 로직은 반드시 `DRY_RUN` 환경변수 체크

---

## 예상 의존성 추가 (requirements.txt)

```
# Phase B: ML 앙상블
lightgbm>=4.0.0
catboost>=1.2.0

# Phase D: DEX/온체인
web3>=7.0.0
gql>=3.5.0

# Phase E: API
pydantic>=2.0.0    # 이미 있을 수 있음 (FastAPI 의존)

# Phase F: Mobile (별도 package.json)
# expo, react-native, victory-native, @tanstack/react-query
```
