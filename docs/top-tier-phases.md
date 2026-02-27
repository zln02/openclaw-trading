# OpenClaw Top-tier Quant 로드맵 (Phase 9~18)

> Phase 1~8은 완료 (코드 정리, 대시보드, 로거, 리트라이 등)
> 아래 각 Phase는 Codex에 독립적으로 지시할 수 있도록 **파일, 입출력, 의존성** 명시

---

## Phase 9: 데이터 파이프라인 강화

**목표:** 현재 yfinance/RSS 기반 → 실시간 + 대안데이터로 업그레이드

### 태스크
1. **`common/data/news_stream.py`** — WebSocket 기반 실시간 뉴스 수집기
   - CryptoPanic WebSocket (BTC) + Benzinga/Polygon.io (US)
   - 입력: API key (env)
   - 출력: `{ headline, source, timestamp, symbols[], sentiment_raw }`
   - 콜백 패턴: `on_news(callback)` 등록식

2. **`common/data/orderbook.py`** — Level 2 호가 데이터 수집
   - 바이낸스 WebSocket (`depth@100ms`) → BTC 오더북 스냅샷
   - 키움 실시간 호가 (REST polling fallback)
   - 출력: `{ bids: [{price, qty}], asks: [{price, qty}], spread, imbalance }`
   - `imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)` — 핵심 시그널

3. **`common/data/alt_data.py`** — 대안데이터 수집
   - Google Trends (`pytrends`): 종목명/티커 검색량 7일 추세
   - Reddit/Twitter 멘션 수 (간단 API or scraping)
   - 출력: `{ symbol, search_trend_7d, social_mentions_24h, sentiment_score }`

4. **`common/data/realtime_price.py`** — 통합 실시간 가격
   - BTC: pyupbit WebSocket (`ticker`)
   - US: Polygon.io WebSocket or Alpaca
   - KR: 키움 실시간 체결가
   - 출력: `{ symbol, price, volume, timestamp }` 스트림

### 의존성
- `websockets`, `pytrends` → requirements.txt에 추가
- Polygon.io API key (무료 티어 가능)
- 환경변수: `POLYGON_API_KEY`, `BENZINGA_API_KEY` (선택)

### 완료 기준
- 각 모듈 독립 실행 가능 (`python -m common.data.news_stream`)
- 10초 내 데이터 수신 확인
- 기존 에이전트에서 `from common.data import ...` 임포트 가능

---

## Phase 10: 알파 팩터 엔진

**목표:** 팩터 발굴 → 백테스트 → 검증/기각을 자동화

### 태스크
1. **`quant/backtest/engine.py`** — Walk-forward 백테스트 엔진
   - 입력: `strategy_fn(date, universe, data) → signals[]`
   - 설정: `{ train_window: 252, test_window: 63, step: 21 }` (1년 학습 / 3개월 테스트 / 1개월 슬라이딩)
   - 출력: `{ sharpe, sortino, max_drawdown, calmar, win_rate, avg_hold_days, trades[] }`
   - 반드시 **미래 데이터 참조(look-ahead bias) 차단** — 데이터는 `as_of(date)` 메서드로만 접근

2. **`quant/backtest/universe.py`** — 생존편향 제거 유니버스
   - Supabase `top50_stocks` 테이블의 **날짜별** 스냅샷 사용
   - 상폐/합병 종목 포함 (survivorship-bias free)
   - US: S&P 500 히스토리컬 구성종목 (Wikipedia 스크래핑 or 파일)

3. **`quant/factors/registry.py`** — 팩터 레지스트리
   - 팩터 정의: `@register_factor(name, category, universe)`
   - 자동 계산: `calc(date, symbol) → float`
   - 카테고리: momentum, value, quality, sentiment, technical, alternative
   - 기본 내장 팩터 최소 20개:
     ```
     momentum_12m, momentum_1m, rsi_14d, macd_signal,
     pe_ratio, pb_ratio, ev_ebitda, roe, roa, debt_ratio,
     earnings_surprise, revenue_growth, accruals,
     volume_ratio_20d, atr_pct, bb_position,
     fg_index, search_trend, social_sentiment,
     orderbook_imbalance
     ```

4. **`quant/factors/analyzer.py`** — 팩터 성과 분석
   - IC (Information Coefficient): 팩터값 vs 다음달 수익률 상관계수
   - IC 평균, IC IR (IC / IC_std), 단조성 테스트
   - Quantile spread: 상위 20% - 하위 20% 수익률 차이
   - 출력: `{ factor_name, ic_mean, ic_ir, quantile_spread, is_valid: bool }`

5. **`quant/factors/combiner.py`** — 팩터 결합 최적화
   - 현재: 수동 가중치 (`F&G:22, RSI:20, ...`)
   - 개선: IC-weighted 결합 또는 Ridge/Lasso 기반
   - 과적합 방지: L2 정규화 + 가중치 상한 (max 30%)

### 완료 기준
- `python -m quant.backtest.engine --strategy momentum --years 3` 실행 시 리포트 출력
- IC > 0.03, IC IR > 0.5인 팩터만 자동 채택
- Walk-forward Sharpe > 1.0이면 전략 승인

---

## Phase 11: 리스크 모델 고도화

**목표:** 포지션별 → 포트폴리오 전체 리스크 관리

### 태스크
1. **`quant/risk/var_model.py`** — VaR/CVaR 계산
   - Historical VaR (95%, 99%) — 과거 252일 기반
   - Parametric VaR — 정규분포 가정
   - CVaR (Expected Shortfall) — 꼬리 리스크
   - 입력: 현재 포지션 리스트 + 과거 수익률 매트릭스
   - 출력: `{ var_95, var_99, cvar_95, portfolio_vol, diversification_ratio }`

2. **`quant/risk/correlation.py`** — 상관관계 모니터링
   - 60일 롤링 상관 매트릭스 (BTC, KR종목들, US종목들)
   - 상관관계 급등 감지 → 텔레그램 경보
   - 포지션 간 상관 > 0.7이면 경고

3. **`quant/risk/exposure.py`** — 팩터/섹터 노출 관리
   - 섹터 노출 상한: 단일 섹터 < 30%
   - 팩터 노출: 모멘텀/가치/품질 편향도 계산
   - 국가 노출: KR/US/BTC 비중 모니터링

4. **`quant/risk/position_sizer.py`** — Kelly 기반 동적 사이징
   - 현재: ATR 기반 고정 비율
   - 개선: Kelly Criterion → `f* = (bp - q) / b`
   - Half-Kelly (보수적) 적용
   - 최대 단일 포지션: 전체 자산의 5%
   - 최대 총 노출: 전체 자산의 80%

5. **`quant/risk/drawdown_guard.py`** — 드로다운 방어
   - 일간 손실 > 2% → 신규 매수 중단
   - 주간 손실 > 5% → 포지션 50% 축소
   - 월간 손실 > 10% → 전체 청산 + 쿨다운 7일
   - 하드 리밋: AI 판단 불가, 룰 기반만

### 완료 기준
- 매 사이클마다 VaR 계산 (< 100ms)
- 드로다운 가드 백테스트: 2022년 하락장에서 MDD 50% 이상 축소 확인

---

## Phase 12: AI 전략 레이어

**목표:** 3-tier AI 구조 구축 (전략/판단/분석)

### 태스크
1. **`agents/strategy_reviewer.py`** — 주간 전략 리뷰 (Opus/o3)
   - 매주 일요일 자동 실행
   - 입력: 주간 거래 로그, PnL, 팩터 성과, 시장 레짐
   - 프롬프트: "지난주 성과 분석 → 팩터 가중치 조정 → 다음주 전략 방향"
   - 출력: `today_strategy.json` 자동 업데이트
   - 변경 이력: `brain/strategy-history/YYYY-MM-DD.json` 저장

2. **`agents/news_analyst.py`** — 뉴스 심층분석 (Haiku/4o-mini)
   - Phase 9의 `news_stream`에서 실시간 수신
   - 각 뉴스 → "이 뉴스가 {symbol} 단기(1~3일) 가격에 미칠 영향: POSITIVE/NEGATIVE/NEUTRAL, 강도 1~5"
   - 배치 처리: 5분마다 누적 뉴스 요약 → `news_sentiment_score` 생성
   - 비용 제어: 하루 최대 $2 (API 호출 카운터)

3. **`agents/regime_classifier.py`** — 시장 레짐 ML 분류
   - 현재: SPY 200MA + VIX (단순 룰)
   - 개선: HMM (Hidden Markov Model) 또는 XGBoost
   - 피처: VIX, VIX term structure, 수익률 분포(skew/kurtosis), 신용 스프레드, 상관관계 변화
   - 레짐: RISK_ON, RISK_OFF, TRANSITION, CRISIS
   - 각 레짐별 전략 파라미터 프리셋 자동 적용

### 완료 기준
- 주간 리뷰 → JSON 생성 자동화
- 뉴스 심층분석 정확도: 수동 라벨 50건 대비 > 70%
- 레짐 분류: 과거 5년 데이터 기준 전환점 80% 이상 포착

---

## Phase 13: 실행 최적화

**목표:** 주문 실행 품질을 기관급으로

### 태스크
1. **`execution/twap.py`** — TWAP 알고리즘
   - 대량 주문을 N분할 × 시간 균등 배분
   - 입력: `{ symbol, side, total_qty, duration_minutes }`
   - 키움/업비트 API 호출 간격 자동 조절

2. **`execution/vwap.py`** — VWAP 알고리즘
   - 과거 거래량 프로파일 기반 분할
   - 거래량 많은 시간대에 더 많이 체결

3. **`execution/slippage_tracker.py`** — 슬리피지 추적
   - 매 거래: `expected_price vs actual_price` 기록
   - Supabase 테이블: `execution_quality`
   - 월간 리포트: 평균 슬리피지, 최악 사례, 개선 추세

4. **`execution/smart_router.py`** — 스마트 주문 라우터
   - 주문 크기 기반: 소액 → 시장가, 중액 → TWAP, 대액 → VWAP
   - 스프레드 기반: 좁으면 시장가, 넓으면 지정가

### 완료 기준
- 평균 슬리피지 < 0.1% (KR 주식 기준)
- TWAP/VWAP 실행 시 시장가 대비 0.05% 이상 절감

---

## Phase 14: BTC 에이전트 Top-tier

**목표:** 현재 70/100 → 90/100

### 태스크
1. **오더플로우 분석** — `btc/signals/orderflow.py`
   - 바이낸스 WebSocket `trade` 스트림
   - CVD (Cumulative Volume Delta) 계산
   - 대량 체결 감지 (> 10 BTC 단일 주문)
   - 출력: `{ cvd, large_buy_count, large_sell_count, net_flow }`

2. **펀딩비 캐리 전략** — `btc/strategies/funding_carry.py`
   - 펀딩비 > 0.05% → 현물 매수 + 선물 숏 (델타 뉴트럴)
   - 펀딩비 < -0.03% → 현물 매도 + 선물 롱
   - 예상 연 수익률: 15~30% (시장 방향 무관)

3. **거래소간 아비트라지 감지** — `btc/signals/arb_detector.py`
   - 업비트 vs 바이낸스 가격 실시간 비교
   - 김치프리미엄 > 5% → 경고
   - 역프리미엄 → 매수 시그널 강화

4. **온체인 고래 추적 고도화** — `btc/signals/whale_tracker.py`
   - Glassnode/CryptoQuant API (또는 무료 대안)
   - 거래소 입금량 급증 → 매도 압력 예측
   - 거래소 출금량 급증 → HODLing 시그널
   - 장기보유자(LTH) 이동 감지

### 완료 기준
- CVD 시그널 단독 백테스트 Sharpe > 0.5
- 펀딩비 캐리: 백테스트 연 15%+ (MDD < 5%)
- 고래 추적: 대규모 이동 후 72시간 가격 변화 방향 적중률 > 60%

---

## Phase 15: KR 주식 에이전트 Top-tier

**목표:** 현재 55/100 → 85/100

### 태스크
1. **실시간 호가잔량 분석** — `stocks/signals/orderbook_kr.py`
   - 키움 실시간 호가 (10호가)
   - 매수/매도 잔량 비율 → 단기 방향 예측
   - 호가 벽(wall) 감지: 특정 가격에 비정상 대량 잔량

2. **수급 팩터** — `stocks/signals/flow_kr.py`
   - KRX 일별 투자자별 매매동향 (외국인, 기관, 개인)
   - 외국인 5일 연속 순매수 → 강력 매수 시그널
   - 기관+외국인 동시 매수 → 최강 시그널
   - 데이터: KRX Open API 또는 pykrx

3. **DART 실시간 공시 필터** — `stocks/signals/dart_realtime.py`
   - DART 공시 RSS/API 실시간 모니터링
   - 핵심 공시 분류: 실적발표, 자사주매입, 유상증자, 대규모계약
   - 자사주매입 공시 → 즉시 매수 시그널
   - 유상증자 공시 → 즉시 매도 시그널

4. **섹터 로테이션 모델** — `stocks/strategies/sector_rotation.py`
   - 11개 GICS 섹터 상대강도 순위
   - 상위 3개 섹터에 집중, 하위 3개 회피
   - 로테이션 주기: 월간

### 완료 기준
- 수급 팩터 IC > 0.05
- DART 공시 이벤트 반응: 공시 후 3일 수익률 > 시장 대비 1%
- 섹터 로테이션: 벤치마크(KOSPI) 대비 연 5%+ 초과수익

---

## Phase 16: US 주식 에이전트 Top-tier

**목표:** 현재 65/100 → 90/100 + 실거래 전환

### 태스크
1. **실거래 전환** — `stocks/us_broker.py`
   - Alpaca API (수수료 0, 소수점 주식 거래 가능)
   - Paper trading → Live trading 전환 스위치
   - 주문 실행: `execution/smart_router.py` 연동

2. **SEC 13F 분석** — `stocks/signals/sec_13f.py`
   - 분기별 기관 포지션 변화 추적
   - 버크셔/브릿지워터 등 탑 펀드 신규 매수 종목 감지
   - 출력: `{ symbol, fund_name, change_type: NEW/ADD/REDUCE/EXIT, shares }`

3. **옵션 플로우 데이터** — `stocks/signals/options_flow.py`
   - 비정상 옵션 거래량 감지 (unusual options activity)
   - 콜/풋 비율(PCR) 변화
   - 스마트머니 추적: 대량 콜 매수 → 강세 시그널
   - 데이터: Polygon.io Options API or CBOE

4. **어닝 서프라이즈 모델** — `stocks/signals/earnings_model.py`
   - 과거 어닝 서프라이즈 패턴 학습
   - 컨센서스 추정치 vs 실제 발표 → SUE(Standardized Unexpected Earnings)
   - PEAD(Post-Earnings Announcement Drift) 포착
   - 어닝 후 3일 드리프트 방향 예측

5. **숏 인터레스트 팩터** — `stocks/signals/short_interest.py`
   - 공매도 비중(SI%) 모니터링
   - 숏 스퀴즈 후보: SI% > 20% + 주가 상승 시작
   - Days to cover > 5 → 스퀴즈 위험

### 완료 기준
- Alpaca paper trading 1개월 안정 운영
- 어닝 서프라이즈 모델: 방향 적중률 > 60%
- 옵션 플로우 시그널: 비정상 거래 후 5일 수익률 > 2%

---

## Phase 17: 통합 포트폴리오 매니저

**목표:** BTC + KR + US를 하나의 포트폴리오로 최적 관리

### 태스크
1. **`quant/portfolio/optimizer.py`** — 자산배분 최적화
   - Mean-Variance (Markowitz) 기본
   - Risk Parity (리스크 균등 배분) 옵션
   - Black-Litterman (AI 전망 반영) 옵션
   - 제약: 각 자산군 10~50%, 단일 종목 < 5%

2. **`quant/portfolio/rebalancer.py`** — 자동 리밸런싱
   - 목표 비중 대비 5% 이상 이탈 시 리밸런싱
   - 세금/수수료 고려한 최소 거래 리밸런싱
   - 주간 체크, 월간 강제 리밸런싱

3. **`quant/portfolio/attribution.py`** — 성과 어트리뷰션
   - Brinson 모델: 자산배분 효과 vs 종목선택 효과
   - 팩터 기여도: 어떤 팩터가 수익/손실에 기여했는가
   - 월간 자동 리포트 생성

### 완료 기준
- 통합 포트폴리오 Sharpe > 1.5 (백테스트 3년)
- MDD < 15%
- 리밸런싱 비용 < 연 0.5%

---

## Phase 18: 모니터링/알림 고도화

**목표:** 실시간 상황 인지 + 자동 리포트

### 태스크
1. **대시보드 v2** — `dashboard/` 확장
   - 실시간 PnL 커브 (WebSocket → 차트 업데이트)
   - VaR 게이지, 드로다운 히트맵
   - 팩터 노출 레이더 차트
   - 섹터/국가 파이 차트

2. **`agents/alert_manager.py`** — 지능형 경보
   - 드로다운 > 3% → 텔레그램 + 대시보드
   - VaR 초과 → 즉시 경보 + 포지션 축소 제안
   - 팩터 이상 감지: 상관관계 급변, 볼륨 스파이크
   - 경보 우선순위: CRITICAL / WARNING / INFO
   - 경보 중복 방지 (같은 경보 10분 쿨다운)

3. **`agents/daily_report.py`** — 일간 자동 리포트
   - 매일 21:00(KST) 텔레그램 발송
   - 내용: 오늘 PnL, 거래 요약, 내일 전략, 리스크 상태
   - 마크다운 포맷

4. **`agents/weekly_report.py`** — 주간 자동 리포트
   - 매주 일요일 발송
   - 주간 성과, 팩터 기여도, 레짐 변화, 다음주 전략
   - Phase 12의 `strategy_reviewer` 결과 포함

### 완료 기준
- 대시보드 < 1초 로딩
- 크리티컬 경보: 발생 후 10초 내 텔레그램 수신
- 일간/주간 리포트 자동 발송 4주 안정 운영

---

## 실행 순서 권장

```
Phase 9 (데이터) → Phase 10 (팩터엔진) → Phase 11 (리스크)
    ↓                                         ↓
Phase 12 (AI 전략) ← ← ← ← ← ← ← ← ← ← ←┘
    ↓
Phase 13 (실행최적화)
    ↓
Phase 14/15/16 (에이전트 고도화) — 병렬 가능
    ↓
Phase 17 (통합 포트폴리오)
    ↓
Phase 18 (모니터링)
```

**Phase 9 → 10 → 11이 기반 인프라이므로 반드시 먼저.**
Phase 14/15/16은 서로 독립적이라 Codex에 병렬로 시킬 수 있음.

---

## Codex 지시 시 주의사항

1. **모든 새 파일은 `common/`, `quant/`, `execution/`, `agents/` 패키지 구조 사용**
2. **기존 `common/logger.py`, `common/retry.py`, `common/cache.py` 반드시 활용**
3. **환경변수는 `common/env_loader.py`로 로드, 하드코딩 금지**
4. **각 모듈은 독립 실행 가능해야 함 (`if __name__ == "__main__":` 포함)**
5. **타입 힌트 필수, docstring 한국어 OK**
6. **테스트: 각 모듈별 `tests/test_*.py` 작성**
