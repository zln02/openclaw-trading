# Sonnet 구현 명세 #2 — 에이전트 + 퀀트 개선 (P1)

> 모든 경로는 `/home/wlsdud5035/.openclaw/workspace/` 기준.
> `01_critical_bugfixes.md` 완료 후 진행.

---

## Task 1: 에이전트 팀 안정성 강화

**파일**: `agents/trading_agent_team.py`

### 1-1. 에이전트 타임아웃 추가 (line 269-298)
```python
import asyncio

async def _run_sub_agent_with_timeout(self, agent, prompt, tools, timeout_sec=60):
    """타임아웃 포함 서브 에이전트 실행."""
    try:
        return await asyncio.wait_for(
            self._run_sub_agent(agent, prompt, tools),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        log.warning(f"{agent.name} 타임아웃 ({timeout_sec}s)")
        return f"[{agent.name}] 응답 시간 초과 - 기본 분석 사용"
```

### 1-2. 오케스트레이터 결정 검증 (line 432-458)
```python
VALID_DECISIONS = {"BUY", "SELL", "HOLD", "NO_POSITION"}

def _validate_decision(self, decision: str, confidence: float) -> bool:
    """오케스트레이터 결정 유효성 검증."""
    if decision not in VALID_DECISIONS:
        log.warning(f"잘못된 결정: {decision}")
        return False
    if confidence < 20:
        log.warning(f"신뢰도 너무 낮음: {confidence}%")
        return False
    return True
```

### 1-3. 도구 결과 캐싱
- `get_btc_indicators()`, `get_fear_greed()` 등은 여러 에이전트가 호출
- 사이클 내 결과를 dict에 캐싱:
```python
_tool_cache: dict = {}

def _cached_tool_call(self, name: str, fn, *args):
    if name not in _tool_cache:
        _tool_cache[name] = fn(*args)
    return _tool_cache[name]
```

---

## Task 2: 뉴스 분석 안정성 개선

**파일**: `agents/news_analyst.py`

### 2-1. Claude API 재시도 + 백오프 (line 216-232)
```python
from common.retry import retry

@retry(max_attempts=3, base_delay=2.0, backoff_factor=2.0)
def _call_claude(self, prompt: str, model: str) -> str:
    """Claude API 호출 (재시도 포함)."""
    # 기존 코드 유지, @retry 데코레이터 추가
```

### 2-2. 예산 검사 선행 (line 284-285)
```python
# 변경 전: 추정 후 검사
estimated_cost = self._estimate_cost_usd(prompt, model)
if not self._within_budget(estimated_cost):
    return None

# 변경 후: 호출 전 검사
estimated_cost = self._estimate_cost_usd(prompt, model)
if not self._within_budget(estimated_cost):
    log.info(f"일일 예산 초과 예상 (${estimated_cost:.4f}). 휴리스틱 사용.")
    return None
```

### 2-3. 모델 맵 완성 (line 37-50)
```python
_CLAUDE_MODEL_MAP = {
    "claude-haiku": "claude-haiku-4-5-20251001",
    "claude-haiku-4": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-sonnet-4": "claude-sonnet-4-6",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-6",
    "claude-opus-4": "claude-opus-4-6",
    "claude-opus-4-6": "claude-opus-4-6",
}
```

---

## Task 3: 레짐 분류기 개선

**파일**: `agents/regime_classifier.py`

### 3-1. XGBoost 피처 순서 명시 (line 314)
```python
# 피처 이름을 명시적으로 저장/검증
FEATURE_NAMES = [
    "spy_20d_return", "spy_60d_return", "vix_level", "vix_change_20d",
    "qqq_spy_corr_60d", "hyg_lqd_spread", "spy_vol_20d",
    "spy_skew_20d", "qqq_20d_return", "spy_drawdown_60d",
]

def _features_to_array(self, features: dict) -> np.ndarray:
    """피처 딕셔너리 → 정렬된 배열 (피처 순서 보장)."""
    return np.array([[features.get(name, 0.0) for name in FEATURE_NAMES]])
```

### 3-2. 모델 학습 최소 데이터 증가
```python
# 변경 전 (line 393-394)
if len(X) < 24:  # 24개월

# 변경 후
if len(X) < 36:  # 최소 3년 (36개월)
    log.warning(f"학습 데이터 부족: {len(X)}개 (최소 36개 필요)")
```

### 3-3. 교차 검증 추가
```python
from sklearn.model_selection import TimeSeriesSplit, cross_val_score

def train_from_rule_labels(self, ...) -> dict:
    # ... 기존 코드 ...
    # 학습 후 CV 평가 추가
    cv = TimeSeriesSplit(n_splits=3)
    scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
    log.info(f"레짐 모델 CV 정확도: {scores.mean():.3f} ± {scores.std():.3f}")
    return {"accuracy_cv": float(scores.mean()), ...}
```

---

## Task 4: 전략 리뷰어 코드 중복 제거

**파일**: `agents/strategy_reviewer.py`

### 4-1. collect_weekly_metrics()와 collect_daily_metrics() 통합

**문제**: 두 함수가 80% 동일한 코드 (3개 시장별 Supabase 쿼리 + PnL 계산).

**수정**: 공통 함수 추출
```python
def _collect_market_trades(self, market: str, since: str) -> dict:
    """특정 시장의 거래 데이터를 수집.

    Args:
        market: 'btc' | 'kr' | 'us'
        since: ISO 날짜 문자열 (예: '2026-03-02')

    Returns:
        dict: {total, wins, losses, avg_pnl, total_pnl, trades: [...]}
    """
    from common.metrics import calc_trade_pnl  # Task 1에서 생성

    table_map = {
        "btc": "btc_position",
        "kr": "trade_executions",
        "us": "us_trade_executions",
    }
    table = table_map[market]

    rows = supabase.table(table) \
        .select("*") \
        .gte("created_at", since) \
        .execute().data or []

    closed = [r for r in rows if r.get("result") == "CLOSED"
              or (market == "kr" and r.get("trade_type") == "SELL")
              or (market == "us" and r.get("trade_type") == "SELL")]

    pnls = [calc_trade_pnl(t, market=market) for t in closed]
    valid = [p for p in pnls if p is not None]

    return {
        "total": len(closed),
        "wins": sum(1 for p in valid if p > 0),
        "losses": sum(1 for p in valid if p <= 0),
        "avg_pnl": sum(valid) / max(len(valid), 1),
        "total_pnl": sum(valid),
        "trades": closed,
    }


def collect_weekly_metrics(self) -> dict:
    since = (date.today() - timedelta(days=7)).isoformat()
    return {m: self._collect_market_trades(m, since) for m in ["btc", "kr", "us"]}


def collect_daily_metrics(self) -> dict:
    since = date.today().isoformat()
    return {m: self._collect_market_trades(m, since) for m in ["btc", "kr", "us"]}
```

---

## Task 5: 시그널 평가기 강화

**파일**: `quant/signal_evaluator.py`

### 5-1. 통계적 유의성 테스트
```python
def _permutation_test(self, signals: list, returns: list, n_perms: int = 1000) -> float:
    """순열 검정으로 IC 유의성 p-value 계산."""
    import numpy as np
    from scipy.stats import spearmanr

    observed_ic = spearmanr(signals, returns).correlation
    count = 0
    returns_arr = np.array(returns)
    for _ in range(n_perms):
        shuffled = np.random.permutation(returns_arr)
        perm_ic = spearmanr(signals, shuffled).correlation
        if abs(perm_ic) >= abs(observed_ic):
            count += 1
    return count / n_perms  # p-value
```

`evaluate_signal()` 결과에 p-value 추가:
```python
result["p_value"] = self._permutation_test(signals, returns)
result["significant"] = result["p_value"] < 0.05
```

### 5-2. IC 유의하지 않은 시그널 경고
```python
if not result["significant"]:
    log.warning(f"시그널 {name}: IC={ic:.4f} (p={result['p_value']:.3f}) — 통계적으로 유의하지 않음")
```

---

## Task 6: 파라미터 최적화 롤백 기능

**파일**: `quant/param_optimizer.py`

### 6-1. 변경 전 파라미터 백업
```python
import shutil

def _backup_params(self):
    """현재 파라미터를 백업."""
    src = BRAIN_PATH / "agent_params.json"
    if src.exists():
        dst = BRAIN_PATH / f"agent_params_backup_{date.today().isoformat()}.json"
        shutil.copy2(src, dst)
        log.info(f"파라미터 백업: {dst}")
```

### 6-2. run()에 백업 단계 추가
```python
def run(self):
    self._backup_params()  # 먼저 백업
    # ... 기존 최적화 로직 ...
```

### 6-3. 롤백 명령어 (텔레그램 연동 가능)
```python
def rollback_params(self, backup_date: str = None):
    """가장 최근 또는 지정 날짜의 백업으로 롤백."""
    if backup_date:
        src = BRAIN_PATH / f"agent_params_backup_{backup_date}.json"
    else:
        backups = sorted(BRAIN_PATH.glob("agent_params_backup_*.json"), reverse=True)
        if not backups:
            log.warning("백업 없음")
            return
        src = backups[0]
    shutil.copy2(src, BRAIN_PATH / "agent_params.json")
    log.info(f"파라미터 롤백 완료: {src.name}")
```

---

## Task 7: 알파 연구자 조기 종료

**파일**: `quant/alpha_researcher.py`

### 7-1. 그리드 서치 조기 종료 (line 267-303)
```python
def _grid_search(self, param_space, ...) -> dict:
    combos = list(itertools.product(*param_space.values()))
    log.info(f"그리드 서치: {len(combos)} 조합")

    best_ir = -999
    no_improve_count = 0
    MAX_NO_IMPROVE = 20  # 20회 연속 개선 없으면 중단

    for i, combo in enumerate(combos):
        params = dict(zip(param_space.keys(), combo))
        ic, ir = self._walk_forward_ic(params, ...)

        if ir > best_ir:
            best_ir = ir
            best_params = params
            no_improve_count = 0
        else:
            no_improve_count += 1

        if no_improve_count >= MAX_NO_IMPROVE:
            log.info(f"조기 종료: {i+1}/{len(combos)} (연속 {MAX_NO_IMPROVE}회 미개선)")
            break

    return {"params": best_params, "ir": best_ir}
```

---

## Task 8: 팩터 귀속 개선

**파일**: `quant/portfolio/attribution.py`

### 8-1. SELL뿐 아니라 OPEN 포지션도 포함
```python
def _load_closed_trades(self, since: str) -> list:
    """SELL(청산) + OPEN(미청산) 포지션 모두 로드."""
    closed = supabase.table("trade_executions") \
        .select("*") \
        .eq("trade_type", "SELL") \
        .gte("created_at", since).execute().data or []

    # 미청산 포지션: 현재가 기준 미실현 PnL
    open_pos = supabase.table("trade_executions") \
        .select("*") \
        .eq("result", "OPEN") \
        .execute().data or []

    return closed + open_pos
```

### 8-2. 다운웨이팅 임계값 config로 이동
```python
# common/config.py에 추가
ATTRIBUTION_DOWNWEIGHT_THRESHOLD = -0.005  # -0.5%
ATTRIBUTION_DECAY_FACTOR = 0.5
```

---

## Task 9: Whale Tracker를 BTC 복합스코어에 연결

**파일**: `btc/btc_trading_agent.py`

### 9-1. calc_btc_composite()에 whale 시그널 추가
```python
# whale_tracker import 추가 (상단)
try:
    from btc.signals.whale_tracker import WhaleTracker, WhaleSignal
    _whale_tracker = WhaleTracker()
except ImportError:
    _whale_tracker = None

# calc_btc_composite() 내부에 whale 점수 추가
def calc_btc_composite(...):
    # ... 기존 8개 컴포넌트 ...

    # Whale 시그널 (±3점)
    whale_score = 0
    if _whale_tracker:
        try:
            ws = _whale_tracker.get_signal()
            if ws and ws.classification == "HODL_SIGNAL":
                whale_score = 3
            elif ws and ws.classification == "SELL_PRESSURE":
                whale_score = -3
        except Exception:
            pass

    components["whale"] = whale_score
    # total에 반영
```

---

## 실행 순서

1. Task 4 (전략 리뷰어 중복 제거) — Task 1 (PnL 중앙화) 의존
2. Task 1 (에이전트 팀) — 독립적
3. Task 2 (뉴스 분석) — 독립적
4. Task 3 (레짐 분류기) — 독립적
5. Task 5 (시그널 평가기) — 독립적
6. Task 6 (파라미터 최적화) — 독립적
7. Task 7 (알파 연구자) — 독립적
8. Task 8 (팩터 귀속) — 독립적
9. Task 9 (Whale 연결) — 독립적

**각 태스크 완료 후 개별 커밋.**
