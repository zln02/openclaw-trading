# Sonnet 구현 명세 #1 — 크리티컬 버그 수정 (P0)

> 이 파일을 Sonnet에게 전달하면 각 태스크를 순서대로 구현합니다.
> 모든 경로는 `/home/wlsdud5035/.openclaw/workspace/` 기준.

---

## Task 1: PnL 계산 함수 중앙화

**문제**: PnL 계산 로직이 5개 이상 파일에 중복. 스키마 변경 시 불일치 위험.

**구현**:
1. `common/metrics.py` 신규 생성
2. 아래 함수 구현:

```python
# common/metrics.py
from typing import Optional

def calc_trade_pnl(trade: dict, *, market: str = "kr") -> Optional[float]:
    """거래 PnL% 계산 (통합).

    지원 스키마:
    - pnl_pct (직접 저장된 경우)
    - pnl (KRW/USD 절대값 → entry_price로 나눠 % 변환)
    - price + entry_price (수동 계산)
    - exit_price + entry_price (US 스키마)

    Returns:
        float: PnL 퍼센트 (예: 2.5 = +2.5%), None if 계산 불가
    """
    # 1. pnl_pct 직접 사용
    if trade.get("pnl_pct") is not None:
        return float(trade["pnl_pct"])

    # 2. pnl 절대값 → % 변환
    if trade.get("pnl") is not None:
        entry = float(trade.get("entry_price") or trade.get("buy_price") or 0)
        if entry > 0:
            return float(trade["pnl"]) / entry * 100

    # 3. exit_price / entry_price
    exit_p = float(trade.get("exit_price") or trade.get("price") or 0)
    entry_p = float(trade.get("entry_price") or trade.get("buy_price") or 0)
    if exit_p > 0 and entry_p > 0:
        return (exit_p - entry_p) / entry_p * 100

    return None


def calc_win_rate(trades: list[dict], *, market: str = "kr") -> float:
    """승률 계산. 거래 리스트 → 승률 (0.0~1.0)."""
    pnls = [calc_trade_pnl(t, market=market) for t in trades]
    valid = [p for p in pnls if p is not None]
    if not valid:
        return 0.0
    wins = sum(1 for p in valid if p > 0)
    return wins / len(valid)


def calc_sharpe(pnl_series: list[float], *, annualize: int = 252) -> float:
    """샤프 비율 계산."""
    import numpy as np
    arr = np.array(pnl_series)
    if len(arr) < 2 or arr.std() == 0:
        return 0.0
    return float(arr.mean() / arr.std() * (annualize ** 0.5))
```

3. 기존 파일들의 중복 PnL 계산을 `calc_trade_pnl()` 호출로 교체:
   - `agents/strategy_reviewer.py` lines 139-147, 152-171
   - `agents/daily_loss_analyzer.py` lines 85-116
   - `agents/daily_report.py` lines 145-206
   - `quant/param_optimizer.py` lines 58-108
   - `quant/portfolio/attribution.py` lines 231-237

**검증**: 각 파일에서 기존과 동일한 PnL 값이 나오는지 확인.

---

## Task 2: ML 데이터 누출 수정

**파일**: `stocks/ml_model.py`

**문제 (line 248)**:
```python
for i in range(60, len(rows) - target_days):
    # ...
    label = 1 if closes[i + target_days] > closes[i] * (1 + target_pct) else 0
```
경계 검사 없음 → IndexError 가능 + 미래 데이터 참조.

**수정**:
```python
for i in range(60, len(rows)):
    if i + target_days >= len(closes):
        break  # 미래 데이터 부족 시 중단
    label = 1 if closes[i + target_days] > closes[i] * (1 + target_pct) else 0
```

**추가 수정**:
- line 162: `(h[-1] - l[-1]) / price` → `/ max(price, 1)` (0 나누기 방지)
- line 176: `avg_vol_20` 폴백 → `max(avg_vol_20, 1)`
- line 380-381: SHAP 값 차원 검사 추가:
```python
if isinstance(shap_vals, list):
    sv = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
else:
    sv = shap_vals  # 1D array for binary classifier
```

---

## Task 3: Kiwoom 주문 재시도 추가

**파일**: `stocks/kiwoom_client.py`

**문제 (line 479)**: `place_order()` 내부에서 `retries=0`으로 API 호출.

**수정**:
- `place_order()` 메서드의 `_request()` 호출에 `retries=1` (최소 1회 재시도)
- 429 (Rate Limit) 시 2초 대기 후 재시도
- 주문 실패 시 `log.error()` + Telegram 알림

추가:
- line 323: `int(s.get("rmnd_qty"))` → `int(s.get("rmnd_qty") or 0)` (None 방지)

---

## Task 4: BTC 포지션 롤백 안전화

**파일**: `btc/btc_trading_agent.py`

**문제 (lines 956-983)**: 매수 성공 → DB 저장 실패 → 즉시 패닉 매도.

**수정**:
```python
result = upbit.buy_market_order("KRW-BTC", invest_krw)
qty = float(result.get("executed_volume", 0)) or (invest_krw / price)

# DB 저장 시도 (3회 재시도)
ok = False
for attempt in range(3):
    ok = open_position_with_context(...)
    if ok:
        break
    log.warning(f"포지션 DB 저장 재시도 {attempt+1}/3")
    time.sleep(2)

if not ok:
    log.error(f"포지션 DB 저장 실패 (3회). 수동 확인 필요. qty={qty}")
    send_telegram(f"⚠️ BTC 매수 성공했으나 DB 저장 실패.\n수량: {qty}\n수동 확인 필요!")
    # 패닉 매도 대신 수동 확인 요청
    # 이전: upbit.sell_market_order(...) ← 즉시 매도 제거
```

---

## Task 5: 쿨다운 적용 확인

**파일**: `btc/btc_trading_agent.py`

**문제**: `RISK["cooldown_minutes"]`가 60으로 설정되어 있지만 실제 매매 루프에서 적용되는지 확인 필요.

**확인할 곳**: `run_main_cycle()` 또는 매수 결정 직전 로직에서 마지막 매수 시간 확인.

**구현 (누락된 경우)**:
```python
def _check_cooldown() -> bool:
    """마지막 매수 후 cooldown_minutes 경과 여부 확인."""
    try:
        rows = supabase.table("btc_trades") \
            .select("created_at") \
            .eq("action", "BUY") \
            .order("created_at", desc=True) \
            .limit(1).execute().data
        if not rows:
            return True
        last_buy = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - last_buy).total_seconds() / 60
        return elapsed >= RISK["cooldown_minutes"]
    except Exception as e:
        log.warning(f"쿨다운 확인 실패: {e}")
        return True  # 실패 시 매매 허용 (보수적이지 않지만 기존 동작 유지)
```

---

## Task 6: 로그 로테이션 추가

**파일**: `common/logger.py`

**문제**: `FileHandler` 사용 → 파일 무한 증가.

**수정**: `RotatingFileHandler` 교체.
```python
from logging.handlers import RotatingFileHandler

# 기존 FileHandler를 교체
fh = RotatingFileHandler(
    log_path,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
```

---

## Task 7: alert_system.py Supabase count 쿼리 수정

**파일**: `common/alert_system.py`

**문제 (line 308)**: `.select("count")` → Supabase에서 유효하지 않음.

**수정**:
```python
# 변경 전
supabase.table("btc_trades").select("count").limit(1)

# 변경 후
supabase.table("btc_trades").select("id", count="exact").limit(1)
# result.count로 접근
```

---

## Task 8: 뉴스 배치 파싱 안전화

**파일**: `agents/news_analyst.py`

**문제 (line 323)**: `text.find("[")` — 이스케이프된 브래킷 미처리.

**수정**:
```python
def _parse_batch_response(self, text: str, count: int) -> list[dict]:
    """배치 응답에서 JSON 배열 추출 (안전)."""
    import re
    # 마크다운 코드블록 안의 JSON 우선 추출
    m = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 직접 JSON 배열 추출
    try:
        # 가장 바깥쪽 [] 찾기
        start = text.index('[')
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '[': depth += 1
            elif ch == ']': depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
    except (ValueError, json.JSONDecodeError):
        pass

    return []  # 파싱 실패 시 빈 리스트
```

**추가**: 배치 실패 시 개별 처리 폴백:
```python
results = self._parse_batch_response(response_text, len(items))
if not results and len(items) > 1:
    log.warning("배치 파싱 실패, 개별 처리로 전환")
    results = [self._analyze_single_item(item) for item in items]
```

---

## Task 9: 파일 기반 상태 원자적 쓰기

**파일**: `common/telegram.py` (buffer), `agents/alert_manager.py` (cooldown)

**공통 유틸 추가** (`common/utils.py`):
```python
import tempfile, os

def atomic_write_json(path: str, data: dict) -> None:
    """원자적 JSON 파일 쓰기 (temp → rename)."""
    dir_name = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(
        mode='w', dir=dir_name, suffix='.tmp', delete=False
    ) as f:
        json.dump(data, f, ensure_ascii=False)
        tmp_path = f.name
    os.replace(tmp_path, path)  # 원자적 교체
```

기존 `json.dump(data, open(path, 'w'))` 패턴을 `atomic_write_json()` 호출로 교체.

---

## 실행 순서

1. Task 1 (PnL 중앙화) — 가장 넓은 영향, 먼저 작업
2. Task 2 (ML 누출) — 독립적, 빠르게 수정 가능
3. Task 3 (Kiwoom 재시도) — 실거래 안전성
4. Task 4 (BTC 롤백) — 실거래 안전성
5. Task 5 (쿨다운) — 확인 + 필요 시 구현
6. Task 6 (로그 로테이션) — 운영 안정성
7. Task 7 (alert count) — 빠른 수정
8. Task 8 (뉴스 파싱) — AI 품질
9. Task 9 (원자적 쓰기) — 데이터 안정성

**각 태스크 완료 후 `git add` + `git commit` 개별 수행.**
