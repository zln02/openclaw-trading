# Sonnet 구현 명세 #3 — 대시보드 + API 개선 (P1)

> 모든 경로는 `/home/wlsdud5035/.openclaw/workspace/` 기준.

---

## Task 1: stock_api.py N+1 쿼리 수정

**파일**: `btc/routes/stock_api.py`

**문제 (line 54)**: `_stock_name(code)` — 매 호출마다 Supabase 쿼리.

**수정**:
```python
_name_cache: dict[str, str] = {}
_name_cache_ts: float = 0.0

def _stock_name(code: str) -> str:
    """종목 코드 → 종목명 (캐시)."""
    global _name_cache, _name_cache_ts
    # 5분마다 캐시 갱신
    if time.time() - _name_cache_ts > 300 or not _name_cache:
        try:
            rows = supabase.table("top50_stocks") \
                .select("code, name").execute().data or []
            _name_cache = {r["code"]: r["name"] for r in rows}
            _name_cache_ts = time.time()
        except Exception:
            pass
    return _name_cache.get(code, code)
```

---

## Task 2: us_api.py yfinance 배치 호출

**파일**: `btc/routes/us_api.py`

**문제 (lines 87-105)**: 포지션마다 개별 yfinance 호출 (N번).

**수정**:
```python
import yfinance as yf

def _batch_fetch_prices(symbols: list[str]) -> dict[str, float]:
    """여러 심볼의 현재가를 한 번에 조회."""
    if not symbols:
        return {}
    try:
        data = yf.download(
            symbols, period="2d", progress=False, threads=True
        )
        prices = {}
        if len(symbols) == 1:
            # yfinance는 단일 심볼 시 MultiIndex 없음
            close = data.get("Close")
            if close is not None and len(close) > 0:
                prices[symbols[0]] = float(close.iloc[-1])
        else:
            close = data.get("Close")
            if close is not None:
                for sym in symbols:
                    if sym in close.columns and len(close[sym].dropna()) > 0:
                        prices[sym] = float(close[sym].dropna().iloc[-1])
        return prices
    except Exception as e:
        log.warning(f"yfinance 배치 실패: {e}")
        return {}

# get_us_portfolio() 내부에서 활용
@router.get("/api/us/portfolio")
async def get_us_portfolio():
    positions = supabase.table("us_trade_executions") \
        .select("*").eq("result", "OPEN").execute().data or []

    symbols = list({p.get("symbol", "") for p in positions if p.get("symbol")})
    prices = _batch_fetch_prices(symbols)

    for p in positions:
        sym = p.get("symbol", "")
        if sym in prices:
            p["current_price"] = prices[sym]
            entry = float(p.get("entry_price") or 0)
            if entry > 0:
                p["pnl_pct"] = round((prices[sym] - entry) / entry * 100, 2)

    return {"positions": positions}
```

---

## Task 3: btc_api.py 캐시 로직 간소화

**파일**: `btc/routes/btc_api.py`

**문제 (lines 38-88)**: 캐시 유효성 검사 조건이 복잡하고 혼란.

**수정**: 단순한 TTL 기반 캐시 패턴:
```python
_upbit_cache = {"ts": 0.0, "data": None}
_UPBIT_CACHE_TTL = 60  # seconds

def _get_upbit_balance() -> dict:
    """Upbit 잔고 조회 (60초 캐시)."""
    now = time.time()
    if _upbit_cache["data"] and now - _upbit_cache["ts"] < _UPBIT_CACHE_TTL:
        return _upbit_cache["data"]

    try:
        balances = upbit.get_balances() or []
        krw_entry = next((b for b in balances if b.get("currency") == "KRW"), {})
        btc_entry = next((b for b in balances if b.get("currency") == "BTC"), {})

        result = {
            "krw": float(krw_entry.get("balance", 0)),
            "krw_locked": float(krw_entry.get("locked", 0)),
            "krw_total": float(krw_entry.get("balance", 0)) + float(krw_entry.get("locked", 0)),
            "btc": float(btc_entry.get("balance", 0)),
            "btc_locked": float(btc_entry.get("locked", 0)),
        }
        _upbit_cache["data"] = result
        _upbit_cache["ts"] = now
        return result
    except Exception as e:
        log.warning(f"Upbit 잔고 조회 실패: {e}")
        return _upbit_cache.get("data") or {
            "krw": 0, "krw_locked": 0, "krw_total": 0,
            "btc": 0, "btc_locked": 0,
        }
```

---

## Task 4: API 호출 타임아웃 추가

**파일**: `btc/routes/btc_api.py`, `stock_api.py`, `us_api.py`

모든 외부 API 호출에 타임아웃:
```python
# pyupbit 호출 래퍼
import signal as _signal
from contextlib import contextmanager

@contextmanager
def timeout(seconds: int = 10):
    """함수 실행 타임아웃 (Linux only)."""
    def _handler(signum, frame):
        raise TimeoutError(f"타임아웃 ({seconds}s)")
    old = _signal.signal(_signal.SIGALRM, _handler)
    _signal.alarm(seconds)
    try:
        yield
    finally:
        _signal.alarm(0)
        _signal.signal(_signal.SIGALRM, old)

# 사용 예시
with timeout(10):
    balance = upbit.get_balance("KRW")
```

또는 더 안전한 방법 (스레드 기반):
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

_executor = ThreadPoolExecutor(max_workers=2)

def _with_timeout(fn, *args, timeout_sec=10, default=None):
    """함수 호출에 타임아웃 적용."""
    future = _executor.submit(fn, *args)
    try:
        return future.result(timeout=timeout_sec)
    except FuturesTimeout:
        log.warning(f"{fn.__name__} 타임아웃 ({timeout_sec}s)")
        return default
```

---

## Task 5: 대시보드 CORS 환경변수화

**파일**: `btc/btc_dashboard.py`

**문제 (line 88)**: CORS가 `localhost:3000`으로 하드코딩.

**수정**:
```python
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Task 6: 프론트엔드 — KR/US 페이지 기능 보강

### 6-1. KrStockPage.jsx 개선

**파일**: `dashboard/src/pages/KrStockPage.jsx`

**추가할 섹션**:
1. **섹터별 포지션 분포** — 원형 차트 (Recharts PieChart)
2. **종목 검색/필터** — 입력 필드로 top50 필터링
3. **최근 거래 이력** — TradeTable 컴포넌트 활용
4. **마지막 cron 실행 시간** — 상단에 타임스탬프 표시

```jsx
// 섹터 분포 예시
import { PieChart, Pie, Cell, Tooltip } from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

function SectorChart({ positions }) {
  const sectors = {};
  positions.forEach(p => {
    const s = p.sector || '기타';
    sectors[s] = (sectors[s] || 0) + (p.eval_amount || 0);
  });
  const data = Object.entries(sectors).map(([name, value]) => ({ name, value }));

  return (
    <PieChart width={300} height={200}>
      <Pie data={data} cx={150} cy={100} outerRadius={80} dataKey="value">
        {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
      </Pie>
      <Tooltip />
    </PieChart>
  );
}
```

### 6-2. UsStockPage.jsx 개선

**파일**: `dashboard/src/pages/UsStockPage.jsx`

**추가할 섹션**:
1. **포트폴리오 PnL 요약** — 총 평가액, 미실현 손익
2. **VIX 게이지** — ScoreGauge 컴포넌트 재사용
3. **환율 표시** — USD/KRW 실시간
4. **거래 이력 테이블** — 최근 20건

---

## Task 7: 프론트엔드 — 마지막 업데이트 시간 표시

**파일**: `dashboard/src/hooks/usePolling.js`

**추가**: 각 폴링 결과에 lastUpdated 타임스탬프:
```javascript
export function usePolling(fetchFn, intervalMs = 30000) {
  const [data, setData] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const result = await fetchFn();
        if (active && result != null) {
          setData(result);
          setLastUpdated(new Date());
          setError(null);
        }
      } catch (e) {
        if (active) setError(e);
      }
    };
    poll();
    const id = setInterval(poll, intervalMs);
    return () => { active = false; clearInterval(id); };
  }, [fetchFn, intervalMs]);

  return { data, lastUpdated, error };
}
```

각 페이지 상단에 표시:
```jsx
<span className="text-xs text-gray-500">
  마지막 업데이트: {lastUpdated?.toLocaleTimeString('ko-KR') || '로딩 중...'}
</span>
```

---

## Task 8: API 에러 응답 표준화

**파일**: `btc/routes/btc_api.py`, `stock_api.py`, `us_api.py`

**문제**: 에러 시 `[]`, `{}`, `null`, `{"error": "..."}` 등 불일치.

**표준 에러 응답 헬퍼**:
```python
# btc/routes/__init__.py 또는 common/api_utils.py
from fastapi.responses import JSONResponse

def api_error(message: str, status_code: int = 500, detail: str = None) -> JSONResponse:
    body = {"error": True, "message": message}
    if detail:
        body["detail"] = detail
    return JSONResponse(content=body, status_code=status_code)

def api_success(data, message: str = "ok") -> dict:
    return {"error": False, "message": message, "data": data}
```

기존 엔드포인트에서:
```python
# 변경 전
except Exception as e:
    return {"error": str(e)}

# 변경 후
except Exception as e:
    log.error(f"포트폴리오 조회 실패: {e}")
    return api_error("포트폴리오 조회 실패")
```

---

## Task 9: 판단 근거 API 추가

**파일**: `btc/routes/btc_api.py`

**Opus 분석에서 제안한 decision-log 엔드포인트**:
```python
@router.get("/api/btc/decision-log")
async def get_decision_log(limit: int = 20):
    """BTC 매매 판단 로그 (AI reason + 지표 스냅샷)."""
    try:
        rows = supabase.table("btc_trades") \
            .select("created_at, action, confidence, reason, composite_score, fear_greed, rsi") \
            .order("created_at", desc=True) \
            .limit(limit).execute().data or []
        return {"decisions": rows}
    except Exception as e:
        log.error(f"decision-log 조회 실패: {e}")
        return api_error("판단 로그 조회 실패")
```

프론트엔드 (BtcPage.jsx)에 판단 근거 카드 추가:
```jsx
function DecisionLog({ decisions }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h3 className="text-lg font-bold mb-2">최근 판단 근거</h3>
      {decisions.map((d, i) => (
        <div key={i} className="border-b border-gray-800 py-2">
          <div className="flex justify-between">
            <span className={d.action === 'BUY' ? 'text-green-400' : 'text-red-400'}>
              {d.action}
            </span>
            <span className="text-gray-500 text-sm">
              {new Date(d.created_at).toLocaleString('ko-KR')}
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">{d.reason}</p>
          <div className="flex gap-2 mt-1 text-xs text-gray-500">
            <span>신뢰도: {d.confidence}%</span>
            <span>스코어: {d.composite_score}</span>
            <span>F&G: {d.fear_greed}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## Task 10: 프론트엔드 빌드 및 배포

대시보드 변경 후:
```bash
cd /home/wlsdud5035/.openclaw/workspace/dashboard
npm run build
# dist/ 폴더를 btc/dist/로 복사
cp -r dist/ ../btc/dist/
```

**주의**: `btc/dist/`가 실제 서빙 경로. `dashboard/dist/`는 빌드 결과물.

---

## 실행 순서

1. Task 1 (stock_api 캐시) — 빠른 수정
2. Task 2 (us_api 배치) — 빠른 수정
3. Task 3 (btc_api 캐시 간소화) — 리팩터링
4. Task 4 (타임아웃) — 안정성
5. Task 5 (CORS) — 빠른 수정
6. Task 8 (에러 표준화) — 백엔드 완료 후
7. Task 9 (판단 근거 API) — 새 기능
8. Task 6-7 (프론트엔드) — 마지막
9. Task 10 (빌드) — 최종

**각 태스크 완료 후 개별 커밋.**
