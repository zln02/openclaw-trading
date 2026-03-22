# OpenClaw Trading System v6.0 업그레이드 종합 스펙

> 작성일: 2026-03-15 | 작성: Claude Opus 4.6 → GPT-5.4 실행용
> 대상: `/home/wlsdud5035/.openclaw/workspace/`

---

## 목차

1. [현재 시스템 진단 요약](#1-현재-시스템-진단-요약)
2. [크리티컬 버그 & 에러 수정](#2-크리티컬-버그--에러-수정)
3. [매매 전략 업그레이드](#3-매매-전략-업그레이드)
4. [에이전트 시스템 개선](#4-에이전트-시스템-개선)
5. [대시보드 개선](#5-대시보드-개선)
6. [OpenClaw 스킬 업데이트](#6-openclaw-스킬-업데이트)
7. [폴더/파일 재구조화](#7-폴더파일-재구조화)
8. [Google Sheets 보고 체계](#8-google-sheets-보고-체계)
9. [커밋 & 배포 체크리스트](#9-커밋--배포-체크리스트)

---

## 1. 현재 시스템 진단 요약

### 포지션 현황 (2026-03-15)
| 마켓 | 종목 | 수량 | 현재가 | 평가액 |
|------|------|------|--------|--------|
| BTC | BTC/KRW | 0.00074491 | 103,004,000 | 76,729 KRW |
| KR | A042700 (한미반도체) | 2주 | 318,000 | 636,000 KRW |
| US | NFLX | 31.15 | $96.30 | $3,000 |
| US | PFE | 74.43 | $26.87 | $2,000 |
| US | CVX | 10.57 | $189.28 | $2,000 |
| US | XLE | 36.05 | $55.47 | $2,000 |

### ML 모델 성능
- **모드**: Stacking (XGB + LGBM + CatBoost)
- **학습 샘플**: 9,583 (train: 7,666 / test: 1,917)
- **Walk-forward AUC**: 0.6291 (std=0.0375) — **개선 필요 (목표: 0.70+)**
- **Precision**: 0.5305 — **동전 던지기 수준, 개선 필수**
- **치명적 문제**: 13개 피처 importance=0.0 (pe_ratio, roe, debt_ratio 등 펀더멘털 전부 0)

### 신호 품질 (Signal IC/IR)
- **모든 신호 INSUFFICIENT_DATA** — 관측값 0~1개
- Alpha parameters는 우수: IC=0.35, IR=1.95
- **핵심 병목**: 매매 데이터가 DB에 충분히 쌓이지 않음 (BTC 1건만 IC 평가)

### 포트폴리오 상태
- 레짐: TRANSITION
- **market_scores 전부 0.0** — 성과 평가가 실행되지 않고 있음
- 넷 베타: 1.0 (Long-only), 숏 포지션 없음
- 섹터 편중: 반도체(60%) — 재조정 필요

---

## 2. 크리티컬 버그 & 에러 수정

### P0 — 즉시 수정 (서비스 영향)

#### 2.1 Signal IC 데이터 파이프라인 단절
**문제**: `signal_evaluator.py`가 KR 매매 데이터에서 신호값을 찾지 못함 (n=0)
**원인**: `execute_buy()` 에서 `ml_score`, `composite_score` 등을 저장하지만, signal_evaluator가 조회하는 컬럼명/테이블이 다를 수 있음
**파일**: `quant/signal_evaluator.py` + `stocks/stock_trading_agent.py`
**수정**:
```python
# signal_evaluator.py에서 trade_executions 테이블 조회 시
# 실제 저장된 컬럼명과 매칭 확인
# ml_score, composite_score, rsi 컬럼이 실제 INSERT 되는지 검증
# Supabase에서 SELECT COUNT(*) WHERE ml_score IS NOT NULL 실행하여 확인
```

#### 2.2 ML 피처 13개 importance=0.0 (Dead Features)
**문제**: pe_ratio, pb_ratio, roe, debt_ratio, revenue_growth, earnings_surprise, orderbook_imbalance, fg_index, regime_encoded, foreign_net_buy_5d, inst_net_buy_5d, short_interest_ratio, momentum_12m 전부 0
**원인**: 피처 추출 시 해당 데이터가 NULL/0으로 채워지고 있음
**파일**: `stocks/ml_model.py` — `_extract_features()` 또는 `_build_feature_matrix()`
**수정**:
1. OpenDART API로 pe_ratio, pb_ratio, roe, debt_ratio 실제 수집 구현
2. KRX API로 foreign_net_buy_5d, inst_net_buy_5d 수집
3. 데이터 없는 피처는 제거하여 노이즈 방지 (importance=0인 피처가 있으면 모델이 오히려 약해짐)
4. 당장은 importance=0 피처 13개 drop → 재학습

```python
# ml_model.py 수정
DEAD_FEATURES = [
    "momentum_12m", "pe_ratio", "pb_ratio", "roe", "debt_ratio",
    "revenue_growth", "earnings_surprise", "orderbook_imbalance",
    "fg_index", "regime_encoded", "foreign_net_buy_5d",
    "inst_net_buy_5d", "short_interest_ratio"
]
# _build_feature_matrix()에서 DEAD_FEATURES 제외
# 또는 실제 데이터 수집 파이프라인 구축 후 재활성화
```

#### 2.3 Market Scores 전부 0.0
**문제**: `brain/portfolio/market_allocation.json`에서 btc/kr/us score 모두 0
**원인**: `quant/portfolio/cross_market_manager.py`에서 성과 계산이 실행되지 않거나 데이터 부족
**파일**: `quant/portfolio/cross_market_manager.py`
**수정**: 최근 90일 매매 데이터에서 시장별 mean_pnl, win_rate 계산 로직 검증

#### 2.4 대시보드 fetchJSON 무한 대기
**문제**: `dashboard/src/api.js`의 `fetchJSON()`에 timeout 없음 — API 장애 시 영구 hang
**파일**: `dashboard/src/api.js`
**수정**:
```javascript
async function fetchJSON(path) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}
```

### P1 — 높은 우선순위

#### 2.5 KR/US 페이지 에러 핸들링 없음
**문제**: BtcPage만 ErrorState 표시, KrStockPage/UsStockPage는 API 실패 시 빈 화면
**파일**: `dashboard/src/pages/KrStockPage.jsx`, `UsStockPage.jsx`
**수정**: compositeError/portfolioError 체크 + ErrorState 컴포넌트 추가

#### 2.6 Layout.jsx 중복 API 호출
**문제**: Layout에서 getBtcPortfolio(30s) 호출 + BtcPage에서 동일 호출 = 2x 요청
**파일**: `dashboard/src/components/Layout.jsx`
**수정**: React Context로 데이터 공유하거나, Layout에서 제거하고 각 페이지에서만 호출

#### 2.7 US Portfolio 데이터 구조 불일치
**문제**: Layout.jsx는 `getUsPositions()` → `us?.summary?.total_current`, 페이지는 `getUsPortfolio()` 사용
**파일**: `dashboard/src/components/Layout.jsx`, `pages/UsStockPage.jsx`
**수정**: 하나의 엔드포인트로 통일 (getUsPortfolio 사용 권장)

#### 2.8 BB/RSI 계산 캐싱 없음
**문제**: `/api/stocks/chart/{code}` 매 요청마다 O(n) BB+RSI 계산
**파일**: `btc/routes/stock_api.py:299-391`
**수정**: 5분 캐시 적용 (`common/cache.py` 활용)

#### 2.9 Hardcoded Fallback 값이 에러를 숨김
**문제**: BtcPage.jsx `trend_score || 42` — API 실패 시 42가 표시되어 사용자가 문제 인지 불가
**파일**: `dashboard/src/pages/BtcPage.jsx:31`
**수정**: fallback 제거, null이면 "N/A" 표시

### P2 — 중간 우선순위

#### 2.10 API 응답 형식 불일치
- BTC: `{ rows: [...] }` / KR/US: `[...]` (raw list)
- 에러: `{ "error": "..." }` (일부) vs `{ "detail": "..." }` (FastAPI 기본)
**수정**: 모든 응답을 `api_success(data)` / `api_error(msg)` 표준화

#### 2.11 `/api/kr/top` 페이지네이션 없음
**수정**: `?limit=20&offset=0` 파라미터 추가

#### 2.12 차트 빈 데이터 처리
**문제**: LightweightPriceChart에 data=[] 전달 시 빈 차트 렌더링
**수정**: data.length === 0 → "데이터 없음" 메시지

---

## 3. 매매 전략 업그레이드

### 3.1 ML 모델 대폭 개선 (AUC 0.63 → 0.70+ 목표)

#### A. Dead Feature 정리 & 피처 엔지니어링
```
현재: 44개 피처 중 13개 = 0.0 importance (30% dead)
목표: 살아있는 31개 + 신규 실데이터 피처 10개 = 41개
```

**즉시 제거할 피처** (데이터 미수집):
- momentum_12m, pe_ratio, pb_ratio, roe, debt_ratio
- revenue_growth, earnings_surprise, orderbook_imbalance
- fg_index, regime_encoded
- foreign_net_buy_5d, inst_net_buy_5d, short_interest_ratio

**신규 추가 피처** (실데이터 기반):
```python
NEW_FEATURES = {
    # 가격 구조
    "price_vs_vwap": "현재가/VWAP 비율",
    "gap_pct": "시가 갭 비율",
    "intraday_range_pct": "(고가-저가)/전일종가",

    # 수급 (KRX API 활용)
    "foreign_net_ratio_5d": "5일 외국인 순매수/거래량",
    "inst_net_ratio_5d": "5일 기관 순매수/거래량",

    # 시장 컨텍스트
    "kospi_bb_pos": "KOSPI의 BB 위치",
    "krx_advance_decline": "등락비율 (HTS 지표)",
    "us_futures_return": "전일 미국선물 수익률",

    # 섹터
    "sector_rs_rank": "섹터 상대강도 순위 (0-1)",
    "sector_flow_5d": "섹터 5일 자금흐름",
}
```

#### B. Walk-Forward 검증 강화
```python
# 현재: 5-fold, fold AUC 편차 큼 (0.577~0.679)
# 개선:
# 1. Purged K-Fold (6개월 학습, 1개월 테스트, 1주일 gap)
# 2. 클래스 불균형 처리 (scale_pos_weight 또는 SMOTE)
# 3. Bayesian HPO (Optuna) — learning_rate, max_depth, n_estimators
# 4. Feature selection: Recursive Feature Elimination (RFECV)
```

#### C. 앙상블 개선
```python
# 현재: Stacking (base AUC: XGB=0.62, LGBM=0.63, CatBoost=0.62)
# 개선:
# 1. Diversity 확보: 각 base model에 다른 피처 서브셋 사용
# 2. Meta-learner: LogisticRegression → Calibrated CatBoost
# 3. Threshold 동적 조정: precision-recall curve에서 최적점 자동 계산
# 4. 캘리브레이션: Platt scaling으로 확률 보정
```

### 3.2 BTC 전략 업그레이드

#### A. 현재 상태
- 소자본 (76,729 KRW ≈ 약 5만원 어치)
- 10분 사이클, composite score 기반
- Fear & Greed Index + RSI + MACD + Bollinger

#### B. 개선사항
```
1. 멀티타임프레임 강화
   - 1분봉 모멘텀 + 5분봉 트렌드 + 1시간봉 지지/저항 통합
   - 상위 TF confirmation 필터 추가

2. 온체인 데이터 통합
   - MVRV Z-Score (현재가 vs 실현가)
   - Exchange Net Flow (거래소 입출금)
   - Active Addresses 변화율
   → btc/signals/ 폴더 활용

3. 펀딩비 캐리 전략 활성화
   - btc/strategies/funding_carry.py 존재하지만 미사용
   - 펀딩비 > 0.01% 시 숏 포지션 고려 (현물 + 무기한 선물 역방향)

4. 김치프리미엄 재정거래
   - btc/signals/arb_detector.py + btc/arb_executor.py 존재
   - 프리미엄 > 3% 시 매도 신호, < -1% 시 매수 신호
   - 현재 비활성 → 활성화 조건 확인 후 가동

5. 스톱로스 개선
   - 현재: 고정 % 기반
   - 개선: ATR 기반 동적 스톱 + 트레일링 스톱 (highest_price 활용)
```

### 3.3 KR 주식 전략 업그레이드

#### A. 현재 상태
- 한미반도체(A042700) 2주 보유
- 반도체 섹터 60% 편중
- 넷 베타 1.0 (풀 롱)

#### B. 개선사항
```
1. 섹터 분산 강제
   - 동일 섹터 최대 30% 제한 (현재 60%)
   - quant/portfolio/optimizer.py에 섹터 제약 추가
   - common/config.py에 MAX_SECTOR_WEIGHT = 0.30 추가

2. 진입 필터 강화
   - ML confidence > 0.65일 때만 매수 (현재 threshold)
   - + 거래량 조건: vol_ratio_5 > 1.5 (5일 평균 대비 1.5배)
   - + 수급 조건: 외국인/기관 순매수 양수

3. 포지션 사이징 개선
   - 현재: 균등 배분
   - 개선: Kelly Criterion 기반 + ATR 조정
   - max_position = 투자금 × Kelly_fraction × (1/ATR_normalized)

4. 매도 전략 개선
   - 부분 익절: +5% → 50% 매도, +10% → 나머지 매도
   - 트레일링 스톱: highest_price × (1 - ATR×2)
   - 시간 기반 손절: 20일 경과 + 수익률 < 0% → 손절

5. 레짐 기반 포지션 크기 조절
   - RISK_ON: 투자비율 80%
   - TRANSITION: 투자비율 50%
   - RISK_OFF: 투자비율 30%
   - CRISIS: 투자비율 10% (현금 90%)
```

### 3.4 US 주식 전략 업그레이드

#### A. 현재 상태
- NFLX($3K), PFE($2K), CVX($2K), XLE($2K) 보유
- 에너지 섹터 과다 (CVX+XLE = $4K = 44%)
- dry-run 모드

#### B. 개선사항
```
1. 팩터 기반 종목 선정
   - Value: P/E, P/B, FCF Yield
   - Quality: ROE, Debt/Equity, Revenue Growth
   - Momentum: 6M/12M 수익률 상위
   - 각 팩터 점수 합산 → Top N 매수

2. 섹터 로테이션
   - XLK/XLF/XLV/XLE/XLY 등 섹터 ETF 모멘텀 비교
   - Top 3 섹터에서만 개별 종목 선정
   - 월 1회 리밸런싱

3. VIX 기반 리스크 관리
   - VIX < 20: 정상 투자
   - VIX 20-30: 신규 매수 중단, 기존 보유만
   - VIX > 30: 50% 포지션 축소
   - common/config.py의 US_RISK_DEFAULTS 활용

4. 환율 헷지
   - USD/KRW > 1,400: 환 노출 주의 알림
   - 환율 변동률 > 2%/주: 포지션 축소 경고

5. 실거래 전환 준비
   - dry-run → paper trading → live 3단계
   - Alpaca API 또는 IBKR API 연동 설계
```

### 3.5 주간 자동 최적화 루프 강화

```
현재:
  Sat 22:00 alpha_researcher → best_params.json
  Sun 23:00 signal_evaluator → weights.json
  Sun 23:30 param_optimizer → agent_params.json

추가 (v6.0):
  Mon 00:00 attribution_runner  → brain/portfolio/weekly_attribution.json
  Mon 00:30 factor_correlator   → brain/factors/correlation_matrix.json
  Mon 08:00 regime_reporter     → brain/regime/weekly_report.json
  Daily 06:00 equity_analyzer   → brain/equity/daily_metrics.json
```

**신규 스크립트**:
```bash
# scripts/run_attribution.sh
# scripts/run_factor_correlator.sh
# scripts/run_regime_reporter.sh
# scripts/run_equity_analyzer.sh
```

**crontab 추가**:
```cron
0 0 * * 1 /path/scripts/run_attribution.sh
30 0 * * 1 /path/scripts/run_factor_correlator.sh
0 8 * * 1 /path/scripts/run_regime_reporter.sh
0 6 * * * /path/scripts/run_equity_analyzer.sh
```

---

## 4. 에이전트 시스템 개선

### 4.1 독립 에이전트 → 중앙 보고 체계

현재 BTC/KR/US 에이전트가 독립 실행되지만 **중앙 총괄 보고가 없음**.

**신규: Central Report Aggregator**
```python
# agents/central_reporter.py (신규)

class CentralReporter:
    """
    모든 에이전트의 실행 결과를 수집하여
    1. 텔레그램 종합 보고
    2. Google Sheets 업데이트
    3. brain/daily-summary/ 일일 리포트 생성
    """

    def collect_all_markets(self):
        """BTC, KR, US 포지션 + 매매 이력 + 수익률 수집"""
        btc = self._get_btc_status()
        kr = self._get_kr_status()
        us = self._get_us_status()
        return {"btc": btc, "kr": kr, "us": us}

    def generate_daily_report(self):
        """
        일일 종합 보고서:
        - 총 자산 (KRW 환산)
        - 시장별 수익률
        - 오늘 매매 내역
        - 리스크 지표 (MDD, Sharpe, 섹터 편중도)
        - 내일 전략 (레짐 기반)
        """
        pass

    def send_to_telegram(self, report):
        """텔레그램 종합 보고 전송"""
        pass

    def update_google_sheets(self, report):
        """J 계정 Google Sheets 업데이트"""
        pass
```

**실행 스케줄**: 매일 22:00 (KR장 마감 후)
```cron
0 22 * * 1-5 /path/scripts/run_central_reporter.sh
```

### 4.2 5-에이전트 팀 개선

**현재**: `agents/trading_agent_team.py`
- Orchestrator (Opus) → MarketAnalyst + NewsAnalyst + RiskManager + Reporter

**개선사항**:
```
1. Agent Memory 강화
   - 각 에이전트가 이전 판단 이력 참조 (brain/agent-memory/)
   - "지난주 SELL 판단했는데 가격 5% 상승" → 반성 & 보정

2. Agent Confidence Calibration
   - 과거 판단 vs 실제 결과 비교표 유지
   - 과신/과소신 에이전트 자동 가중치 조절
   - brain/agent-calibration.json에 저장

3. Risk Manager 강화
   - 포트폴리오 전체 VaR 계산
   - 상관관계 기반 분산 효과 반영
   - 최대 드로우다운 시나리오 시뮬레이션

4. Orchestrator 결정 근거 투명화
   - 각 하위 에이전트 입력 → 최종 결정까지 chain-of-thought 저장
   - brain/agent-decisions/ 폴더에 일자별 저장
   - 대시보드 AgentsPage에서 시각화
```

### 4.3 News Analyst 개선

**파일**: `agents/news_analyst.py`

```
1. 비용 효율화
   - 현재: 뉴스당 1 API 호출 or batch (batch 구현됨)
   - 개선: 중복 뉴스 필터링 (제목 유사도 > 0.8 → skip)
   - dedup 해시 캐시: brain/news-analysis/_state/seen_hashes.json

2. Claude → OpenAI 폴백 전략
   - Claude 할당 초과 시 자동 OpenAI 폴백 (현재 구현됨)
   - 개선: 비용 대비 품질 모니터링
   - 주간 보고: Claude vs OpenAI 판단 정확도 비교

3. 뉴스 영향도 피드백 루프
   - 뉴스 분석 → 매매 → 결과 수집 → 뉴스 분석 정확도 추적
   - 정확도 높은 뉴스 소스 가중치 상향
```

### 4.4 Regime Classifier 개선

**파일**: `agents/regime_classifier.py`

```
1. 피처 추가
   - 현재: VIX, KOSPI, DXY 기반
   - 추가: 크레딧 스프레드 (HY-IG), 채권 수익률 커브 (10Y-2Y), 원달러 환율

2. 앙상블 레짐 판정
   - Rule-based + ML-based 결합
   - 두 방법이 일치 시 confidence 상향
   - 불일치 시 TRANSITION으로 분류

3. 레짐 전환 지연 (debounce)
   - 현재: 즉시 전환
   - 개선: 3일 연속 같은 레짐 → 전환 확정
   - 빈번한 전환으로 인한 whipsaw 방지
```

---

## 5. 대시보드 개선

### 5.1 API 레이어 수정

**파일**: `dashboard/src/api.js`

```javascript
// 1. 타임아웃 추가
// 2. 재시도 로직 (1회)
// 3. 429 Rate Limit 처리

async function fetchJSON(path, retries = 1) {
  for (let i = 0; i <= retries; i++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.status === 429) {
        await new Promise(r => setTimeout(r, 2000));
        continue;
      }
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (i === retries) throw e;
    }
  }
}
```

### 5.2 페이지별 개선

#### BtcPage.jsx
```
- [ ] trend_score || 42 같은 하드코딩 제거 → null이면 "N/A"
- [ ] 캔들차트에 거래량 오버레이 추가
- [ ] Fear & Greed 히스토리 차트 (7일)
- [ ] 최근 매매 결과 + PnL 표시
- [ ] 레짐 상태 배지 (RISK_ON=초록, TRANSITION=노랑, RISK_OFF=빨강)
```

#### KrStockPage.jsx
```
- [ ] ErrorState 컴포넌트 추가 (API 실패 시)
- [ ] 일일 손실 경고 배너 추가 (is_daily_loss_exceeded 활용)
- [ ] 섹터 분포 도넛차트 추가 (SvgDonutChart 활용)
- [ ] 종목별 ML 신호 표시 (ml_score, ml_confidence)
- [ ] 팩터 가중치 레이더 차트 (SvgRadarChart 활용)
- [ ] 수익률 히트맵 (일별 × 종목)
```

#### UsStockPage.jsx
```
- [ ] ErrorState 컴포넌트 추가
- [ ] factorData 하드코딩 제거 → API에서 실제 팩터 점수 로드
- [ ] 환율 변동 차트 추가
- [ ] 섹터 로테이션 현황 표시
- [ ] 포지션별 수익률 바 차트
```

#### AgentsPage.jsx
```
- [ ] 에이전트 판단 이력 타임라인
- [ ] 판단 정확도 누적 차트
- [ ] Orchestrator chain-of-thought 펼치기/접기
- [ ] 에이전트별 신뢰도 게이지
```

### 5.3 신규 페이지

#### OverviewPage.jsx (총괄 대시보드)
```
- 전체 자산 (BTC+KR+US, KRW 환산)
- 시장별 수익률 비교 바 차트
- 일일/주간/월간 PnL 곡선
- 포트폴리오 파이차트 (시장별 배분)
- 레짐 상태 + 최근 전환 이력
- 리스크 지표: 전체 MDD, Sharpe, 최대 포지션 비중
```

#### PerformancePage.jsx (성과 분석)
```
- Equity Curve (brain/equity/*.jsonl 활용)
- 승률/수익률 히스토그램
- 드로우다운 차트
- 팩터 Attribution 테이블
- 월별 수익률 히트맵
```

### 5.4 백엔드 API 추가

**파일**: `btc/routes/` 에 추가

```python
# btc_api.py에 추가
@router.get("/api/overview")
async def get_overview():
    """전체 포트폴리오 종합 (BTC+KR+US)"""
    # brain/risk/latest_snapshot.json 로드
    # 시장별 수익률 계산
    # 레짐 정보 포함
    pass

@router.get("/api/performance")
async def get_performance(days: int = 30):
    """성과 분석 데이터"""
    # brain/equity/*.jsonl에서 equity curve 로드
    # Supabase에서 매매 이력 → 승률, MDD, Sharpe 계산
    pass

@router.get("/api/regime/history")
async def get_regime_history(days: int = 30):
    """레짐 전환 이력"""
    pass

# stock_api.py에 추가
@router.get("/api/kr/sectors")
async def get_kr_sectors():
    """KR 섹터 분포"""
    pass

@router.get("/api/kr/factor-weights")
async def get_kr_factor_weights():
    """현재 팩터 가중치 (brain/signal-ic/weights.json)"""
    pass
```

### 5.5 공통 UI 개선

```
- [ ] 다크모드 토글 (현재 다크모드만)
- [ ] 모바일 반응형 개선 (현재 부분적)
- [ ] 자동 새로고침 상태 표시 (마지막 업데이트: 30초 전)
- [ ] 데이터 Stale 경고 (2분 이상 갱신 안됨 → 노란 배지)
- [ ] 토스트 알림 (매매 발생 시 실시간 알림)
```

---

## 6. OpenClaw 스킬 업데이트

### 6.1 기존 스킬 업데이트

| 스킬 | 현재 상태 | 업데이트 내용 |
|------|-----------|---------------|
| `signal-query` | brain/ JSON 읽기 | Supabase 실시간 쿼리 추가, 최근 N일 필터 |
| `portfolio-manager` | 기본 리밸런싱 | 레짐 기반 동적 배분 + 섹터 제약 반영 |
| `backtest-runner` | 기본 백테스트 | Walk-forward + Monte Carlo 시뮬레이션 추가 |
| `risk-report` | 기본 리스크 | VaR/CVaR 계산 + 상관관계 매트릭스 포함 |
| `trading-ops` | 기본 매매 | ML 신호 + 레짐 필터 통합 |
| `kiwoom-api` | OAuth2 + REST | 429 재시도 + 배치 조회 최적화 |
| `opendart-api` | 기본 DART | 재무제표 피처 자동 추출 (PE/PB/ROE) |
| `auth-manager` | 가이드 문서 | Anthropic API 키 관리 추가 |
| `todo-manager` | 기본 TODO | brain/todos.md ↔ Telegram 연동 |

### 6.2 신규 스킬

```
skills/
├── performance-analyzer/   # 성과 분석 (승률, MDD, Sharpe, Attribution)
│   └── SKILL.md
├── regime-query/           # 레짐 조회 + 전환 이력
│   └── SKILL.md
├── ml-monitor/             # ML 모델 성능 모니터링 + drift 감지
│   └── SKILL.md
└── sheets-reporter/        # Google Sheets 자동 보고
    └── SKILL.md
```

### 6.3 OpenClaw JS 프로젝트 연동

**위치**: `/home/wlsdud5035/openclaw/`

이 프로젝트가 OpenAI를 사용하여 스킬을 실행하는 부분:
```
1. OpenAI API 호출 부분 → 최신 openai 패키지 (>=1.6.0) 호환 확인
2. 스킬 실행 시 workspace/ 경로 참조 → 경로 동기화 확인
3. 스킬 결과를 brain/ 에 저장하는 로직 검증
4. 에러 핸들링: API 실패 시 fallback 로직 추가
```

---

## 7. 폴더/파일 재구조화

### 7.1 현재 문제점
- `btc/` 폴더가 대시보드 서버 + BTC 에이전트 + 모든 API 라우트를 포함 (혼재)
- `stock_api.py`, `us_api.py`가 `btc/routes/`에 있음 (논리적 불일치)
- `brain/` 내 일부 파일이 git-tracked (kiwoom_token.json은 위험)
- 스크립트 37개 — 정리 필요

### 7.2 재구조화 계획

```
변경 전:                          변경 후:
btc/                              btc/
  btc_dashboard.py (서버)           btc_trading_agent.py
  btc_trading_agent.py              btc_news_collector.py
  routes/                           signals/
    btc_api.py                      strategies/
    stock_api.py  ← 여기 왜?
    us_api.py     ← 여기 왜?      server/  (신규: 대시보드 서버 분리)
  dist/                               app.py (기존 btc_dashboard.py)
  signals/                            routes/
  strategies/                           btc_api.py
                                        kr_api.py  (← stock_api.py 리네임)
                                        us_api.py
                                      dist/
```

**단, 이 변경은 cron 스크립트, import 경로, 대시보드 빌드 프로세스에 영향을 주므로 신중하게 실행해야 함.**

> **권장**: 당장은 파일 이동 대신 `stock_api.py` → `kr_api.py` 리네임만 진행. 서버 분리는 Phase 7에서 진행.

### 7.3 .gitignore 보강

```gitignore
# 추가할 항목
brain/kiwoom_token.json
brain/ml/**/*.ubj
brain/ml/**/*.cbm
brain/ml/**/*.txt
brain/ml/**/*.pkl
*.pyc
__pycache__/
.DS_Store
```

### 7.4 정리 대상 파일

```
삭제 후보:
- scripts/export_for_opus.py (일회성)
- scripts/build_opus_prompt.sh (일회성)
- docs/history/2026-03/ (아카이브 → 별도 branch)
- prompts/00_system_diagnosis.md ~ 04_infra_cicd.md (실행 완료)

통합 후보:
- scripts/run_btc_cron.sh + run_stock_cron.sh + run_us_cron.sh
  → 하나의 scripts/run_agent.sh --market btc|kr|us 로 통합 가능
```

---

## 8. Google Sheets 보고 체계

### 8.1 J 계정 시트 구조

**기존**: `common/sheets_logger.py` + `common/sheets_manager.py`

**시트 구성**:
```
OpenClaw Dashboard (Google Sheet)
├── [Overview] — 총 자산, 시장별 배분, 일일 수익률
├── [BTC] — BTC 포지션, 매매 이력, composite score
├── [KR] — KR 포지션, 매매 이력, ML 신호
├── [US] — US 포지션, 매매 이력
├── [Performance] — 일별 수익률, MDD, Sharpe, 승률
├── [Signals] — 최근 신호 IC/IR 현황
└── [Regime] — 레짐 변화 이력
```

### 8.2 자동 업데이트 구현

```python
# common/sheets_reporter.py (신규 또는 sheets_manager.py 확장)

class SheetsReporter:
    """Google Sheets J 계정에 일일 보고 자동화"""

    def update_overview(self):
        """전체 자산 현황 업데이트"""

    def update_market_sheet(self, market: str):
        """시장별 시트 업데이트 (BTC/KR/US)"""

    def update_performance(self):
        """성과 지표 업데이트"""

    def update_signals(self):
        """신호 품질 현황"""
```

**실행**: 매일 22:30 (central_reporter 직후)
```cron
30 22 * * 1-5 /path/scripts/run_sheets_reporter.sh
```

---

## 9. 커밋 & 배포 체크리스트

### 9.1 작업 순서 (우선순위)

```
Phase 1 — 크리티컬 버그 수정 (1일)
  □ P0: Signal IC 데이터 파이프라인 수정
  □ P0: ML dead features 제거 + 재학습
  □ P0: Market scores 계산 로직 수정
  □ P0: 대시보드 fetchJSON 타임아웃 추가
  □ P1: KR/US 페이지 에러 핸들링
  □ P1: Layout 중복 API 호출 제거
  □ P1: BB/RSI 캐싱

Phase 2 — 매매 전략 개선 (2-3일)
  □ ML 피처 정리 + 재학습
  □ BTC 멀티타임프레임 + ATR 스톱
  □ KR 섹터 분산 제약
  □ US 팩터 기반 종목 선정
  □ 주간 루프 강화 (attribution, correlation, regime)

Phase 3 — 에이전트 개선 (2일)
  □ Central Reporter 구현
  □ 에이전트 메모리 & 캘리브레이션
  □ Regime Classifier 피처 추가 + debounce
  □ News Analyst dedup + 피드백 루프

Phase 4 — 대시보드 개선 (2-3일)
  □ API 레이어 개선 (타임아웃, 재시도)
  □ KR/US 페이지 에러/차트/배너
  □ OverviewPage 신규
  □ PerformancePage 신규
  □ AgentsPage 이력 시각화

Phase 5 — 스킬 & 보고 체계 (1일)
  □ 기존 스킬 업데이트
  □ 신규 스킬 4개 추가
  □ Google Sheets 자동 보고

Phase 6 — 정리 & 배포 (1일)
  □ .gitignore 보강
  □ 불필요 파일 정리
  □ kr_api.py 리네임
  □ 테스트 추가 (coverage 50%+)
  □ git commit & push
```

### 9.2 커밋 컨벤션

```
feat(btc): 멀티타임프레임 트렌드 필터 추가
fix(ml): dead features 13개 제거 + 재학습
fix(dashboard): fetchJSON 타임아웃 및 에러 핸들링
feat(agents): CentralReporter 종합 보고 시스템
feat(dashboard): OverviewPage 전체 포트폴리오 뷰
refactor(routes): stock_api.py → kr_api.py 리네임
chore: .gitignore 보강 + 불필요 파일 정리
```

### 9.3 테스트 필수 항목

```python
# tests/test_signal_pipeline.py (신규)
- test_signal_values_stored_on_buy()  # ml_score, composite_score 실제 저장 확인
- test_signal_evaluator_reads_stored_values()  # evaluator가 읽는지 확인

# tests/test_ml_features.py (신규)
- test_no_dead_features()  # importance=0 피처 없는지 확인
- test_feature_extraction_completeness()  # 모든 피처 non-null 비율 > 80%

# tests/test_dashboard_api.py (신규)
- test_all_endpoints_return_200()  # 모든 API 정상 응답
- test_response_format_consistency()  # 응답 형식 통일 확인

# tests/test_central_reporter.py (신규)
- test_all_markets_collected()
- test_telegram_report_format()
```

---

## 부록: 핵심 수치 목표 (v6.0)

| 지표 | 현재 | 목표 | 방법 |
|------|------|------|------|
| ML AUC | 0.6291 | 0.70+ | 피처 정리 + HPO + 캘리브레이션 |
| ML Precision | 0.5305 | 0.65+ | 임계값 최적화 + 피처 엔지니어링 |
| Signal IC | N/A (데이터 부족) | 0.03+ | 파이프라인 수정 후 측정 |
| 섹터 집중도 | 60% | ≤30% | 섹터 제약 추가 |
| 대시보드 에러율 | ~30% (에러 미표시) | 0% | 에러 핸들링 + 타임아웃 |
| 테스트 커버리지 | ~30% | 50%+ | 신규 테스트 추가 |
| 일일 보고 자동화 | 부분적 | 100% | CentralReporter + Sheets |

---

> 이 문서는 GPT-5.4가 단계별로 실행할 수 있도록 작성되었습니다.
> 각 Phase의 파일 경로, 수정 내용, 테스트 항목이 명시되어 있으므로
> 순서대로 실행하면 됩니다.
>
> **주의**: 리스크 파일 수정 시 반드시 DRY_RUN=1 테스트 후 적용
