import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

try:
    from zoneinfo import ZoneInfo  # py>=3.9
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# ---------------------------------------------------------------------------
# 경로/파일 설정
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]  # workspace 루트
BRAIN_DIR = ROOT / "brain"
LOG_DIR = BRAIN_DIR / "logs"
LOG_PATH = LOG_DIR / "kiwoom-api.log"
TOKEN_CACHE_PATH = BRAIN_DIR / "kiwoom_token.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
BRAIN_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 설정/상태
# ---------------------------------------------------------------------------

MIN_CALL_INTERVAL_SEC = 0.5
RETRY_DELAY_SEC = 3.0
MAX_RETRIES = 3

# 장 시간 (KST 기준)
MARKET_START = (9, 0)   # 09:00
MARKET_END = (15, 30)   # 15:30

_last_call_ts: float = 0.0


@dataclass
class KiwoomConfig:
    api_key: str
    api_secret: str
    trading_env: str  # "mock" or "prod"

    @property
    def base_url(self) -> str:
        return "https://mockapi.kiwoom.com" if self.trading_env == "mock" else "https://api.kiwoom.com"


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------


def _now_kst() -> datetime:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Seoul"))
    # tzdata 없으면 UTC+9 근사치
    return datetime.utcnow() + timedelta(hours=9)


def _is_market_hours(now: Optional[datetime] = None) -> bool:
    if now is None:
        now = _now_kst()
    start = now.replace(hour=MARKET_START[0], minute=MARKET_START[1], second=0, microsecond=0)
    end = now.replace(hour=MARKET_END[0], minute=MARKET_END[1], second=0, microsecond=0)
    return start <= now <= end



def _load_stock_mapping() -> Dict[str, str]:
    """watchlist.md에서 종목명→종목코드 매핑 로드."""
    mapping = {}
    watchlist_path = BRAIN_DIR / "watchlist.md"
    
    if not watchlist_path.exists():
        return mapping
    
    try:
        with watchlist_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        
        in_table = False
        for line in lines:
            line = line.strip()
            if "| 종목명 | 종목코드 |" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    name, code = parts[0], parts[1]
                    mapping[name] = code
                    mapping[code] = code  # 코드→코드도 지원
            if in_table and (line.startswith("##") or not line):
                if in_table and line.startswith("##"):
                    break
    
    except Exception:
        pass
    
    return mapping


def normalize_stock_code(stock_input: str) -> str:
    """종목명 또는 종목코드를 받아서 6자리 종목코드로 변환."""
    stock_input = stock_input.strip()
    
    # 이미 6자리 숫자면 그대로 반환
    if stock_input.isdigit() and len(stock_input) == 6:
        return stock_input
    
    # 매핑 테이블에서 찾기
    mapping = _load_stock_mapping()
    code = mapping.get(stock_input)
    
    if code:
        return code
    
    # 매핑 없으면 원본 반환 (API가 알아서 처리하거나 에러 발생)
    return stock_input


def _load_config() -> KiwoomConfig:
    trading_env = os.getenv("TRADING_ENV", "mock").lower()

    api_key = os.getenv("KIWOOM_REST_API_KEY")
    api_secret = os.getenv("KIWOOM_REST_API_SECRET")

    if not api_key or not api_secret:
        # fallback: openclaw.json 의 env 사용
        candidates = [
            Path.home() / ".openclaw" / "openclaw.json",
            Path("/home/node/.openclaw/openclaw.json"),
        ]
        for p in candidates:
            try:
                with p.open("r", encoding="utf-8") as f:
                    cfg = json.load(f)
                env = cfg.get("env", {})
                api_key = api_key or env.get("KIWOOM_REST_API_KEY") or env.get("KIWOOM_MOCK_REST_API_APP_KEY")
                api_secret = api_secret or env.get("KIWOOM_REST_API_SECRET") or env.get("KIWOOM_MOCK_REST_API_SECRET_KEY")
                if api_key and api_secret:
                    break
            except Exception:
                continue

    if not api_key or not api_secret:
        raise RuntimeError("Kiwoom API 키가 설정되지 않았습니다. (KIWOOM_REST_API_KEY / KIWOOM_REST_API_SECRET 또는 openclaw.json env 확인)")

    return KiwoomConfig(api_key=api_key, api_secret=api_secret, trading_env=trading_env)


def _load_cached_token() -> Optional[Dict[str, Any]]:
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        with TOKEN_CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def _save_cached_token(token: str, expires_at: float) -> None:
    payload = {"token": token, "expires_at": expires_at}
    try:
        with TOKEN_CACHE_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        # 캐시 실패는 치명적이지 않으므로 무시
        pass


def _log_call(*, endpoint: str, api_id: Optional[str], success: bool, status: Optional[int], message: str) -> None:
    ts = _now_kst().isoformat()
    rec = {
        "time": ts,
        "endpoint": endpoint,
        "api_id": api_id,
        "success": success,
        "status": status,
        "message": message,
    }
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _notify_telegram_error(msg: str) -> None:
    """실제 텔레그램 연동은 OpenClaw 쪽에서 이 로그/출력을 훅으로 사용하도록 가정."""
    print(f"[KIWOOM_TELEGRAM_ALERT] {msg}")
    _log_call(endpoint="__telegram__", api_id=None, success=False, status=None, message=msg)


# ---------------------------------------------------------------------------
# 토큰 관리 (파일 캐시 + 30분 전에 자동 갱신)
# ---------------------------------------------------------------------------


def _get_or_refresh_token(cfg: KiwoomConfig) -> str:
    now = time.time()

    cached = _load_cached_token()
    if cached:
        token = cached.get("token")
        expires_at = float(cached.get("expires_at", 0))
        # 만료 30분 전까지는 재사용
        if token and now < (expires_at - 30 * 60):
            return token

    # 새 토큰 발급
    url = f"{cfg.base_url}/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "appkey": cfg.api_key,
        "secretkey": cfg.api_secret,
    }

    resp = httpx.post(url, json=data, timeout=30.0)
    result = resp.json()

    if result.get("return_code") != 0:
        msg = f"토큰 발급 실패: {result.get('return_msg')}"
        _log_call(endpoint="/oauth2/token", api_id=None, success=False, status=resp.status_code, message=msg)
        raise RuntimeError(msg)

    token = result["token"]
    # 키움 응답에 만료 시간이 따로 안 들어온다고 가정하고 1시간 유효
    expires_at = now + 3600
    _save_cached_token(token, expires_at)

    _log_call(endpoint="/oauth2/token", api_id=None, success=True, status=resp.status_code, message="token issued")
    return token


# ---------------------------------------------------------------------------
# 공통 호출 함수 (속도 제한 + 재시도 + 장시간 체크 + 로깅)
# ---------------------------------------------------------------------------


def _respect_rate_limit() -> None:
    global _last_call_ts
    now = time.time()
    delta = now - _last_call_ts
    if delta < MIN_CALL_INTERVAL_SEC:
        time.sleep(MIN_CALL_INTERVAL_SEC - delta)
    _last_call_ts = time.time()


def _call_kiwoom_api(*, api_id: str, endpoint: str, body: Dict[str, Any], is_trading: bool) -> Dict[str, Any]:
    cfg = _load_config()

    # 장 시간 체크: 시세(quote)는 항상 허용, 매매(trade)는 장 시간 내에서만
    if is_trading and not _is_market_hours():
        msg = "장 시간(09:00~15:30)이 아니라 매매 주문이 차단되었습니다."
        _log_call(endpoint=endpoint, api_id=api_id, success=False, status=None, message=msg)
        raise RuntimeError(msg)

    last_error: Optional[str] = None
    last_status: Optional[int] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _respect_rate_limit()
            token = _get_or_refresh_token(cfg)

            url = f"{cfg.base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "api-id": api_id,
                "authorization": f"Bearer {token}",
            }

            resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
            last_status = resp.status_code
            data = resp.json()

            if data.get('return_code') != 0:
                last_error = f"API 오류 (code={data.get('return_code')}): {data.get('return_msg')}"
                _log_call(endpoint=endpoint, api_id=api_id, success=False, status=resp.status_code, message=last_error)
                # 재시도 대상
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SEC)
                    continue
                else:
                    break

            # 성공
            _log_call(endpoint=endpoint, api_id=api_id, success=True, status=resp.status_code, message="OK")
            return data

        except Exception as e:  # 네트워크/파싱 등
            last_error = str(e)
            _log_call(endpoint=endpoint, api_id=api_id, success=False, status=last_status, message=last_error)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
                continue
            else:
                break

    # 여기까지 왔으면 실패
    alert_msg = f"[{api_id}] Kiwoom API 3회 연속 실패: status={last_status}, error={last_error}"
    _notify_telegram_error(alert_msg)
    raise RuntimeError(alert_msg)


# ---------------------------------------------------------------------------
# 공개 함수들
# ---------------------------------------------------------------------------


def get_stock_info(stock_code: str) -> Dict[str, Any]:
    """주식기본정보요청 (ka10001) - 시세 조회 (장시간 밖에서도 허용)."""
    normalized_code = normalize_stock_code(stock_code)
    body = {"stk_cd": normalized_code}
    return _call_kiwoom_api(api_id="ka10001", endpoint="/api/dostk/stkinfo", body=body, is_trading=False)


def get_account_evaluation() -> Dict[str, Any]:
    """계좌평가현황 (kt00004) - 매매 관련, 장 시간 내에서만 허용."""
    body = {"qry_tp": "0", "dmst_stex_tp": "KRX"}
    return _call_kiwoom_api(api_id="kt00004", endpoint="/api/dostk/acnt", body=body, is_trading=True)


def buy_order(stock_code: str, quantity: int, price: Optional[int] = None, order_type: str = "0") -> Dict[str, Any]:
    """매수주문 (kt10000).
    
    Args:
        stock_code: 종목코드 (6자리) 또는 종목명
        quantity: 주문 수량
        price: 주문 가격 (None이면 시장가, order_type="3"으로 처리)
        order_type: 주문 유형 ("0"=보통, "3"=시장가)
    
    Returns:
        주문 결과 딕셔너리
    """
    normalized_code = normalize_stock_code(stock_code)
    
    # 가격이 없으면 시장가로 처리
    if price is None:
        order_type = "3"
        price = 0
    
    body = {
        "dmst_stex_tp": "KRX",
        "stk_cd": normalized_code,
        "ord_qty": str(quantity),
        "ord_uv": str(price),
        "ord_tp": order_type,
    }
    
    return _call_kiwoom_api(api_id="kt10000", endpoint="/api/dostk/ordr", body=body, is_trading=True)


def sell_order(stock_code: str, quantity: int, price: Optional[int] = None, order_type: str = "0") -> Dict[str, Any]:
    """매도주문 (kt10001).
    
    Args:
        stock_code: 종목코드 (6자리) 또는 종목명
        quantity: 주문 수량
        price: 주문 가격 (None이면 시장가, order_type="3"으로 처리)
        order_type: 주문 유형 ("0"=보통, "3"=시장가)
    
    Returns:
        주문 결과 딕셔너리
    """
    normalized_code = normalize_stock_code(stock_code)
    
    # 가격이 없으면 시장가로 처리
    if price is None:
        order_type = "3"
        price = 0
    
    body = {
        "dmst_stex_tp": "KRX",
        "stk_cd": normalized_code,
        "ord_qty": str(quantity),
        "ord_uv": str(price),
        "ord_tp": order_type,
    }
    
    return _call_kiwoom_api(api_id="kt10001", endpoint="/api/dostk/ordr", body=body, is_trading=True)


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print(f"[INFO] 현재 KST 시각: {_now_kst().isoformat()} / 장시간 여부: {_is_market_hours()}")

    args = sys.argv[1:]
    if not args:
        # 기본 테스트: 005930
        code = os.getenv("KIWOOM_TEST_STOCK", "005930")
        try:
            info = get_stock_info(code)
            basic = {
                "stk_cd": info.get("stk_cd"),
                "stk_nm": info.get("stk_nm"),
                "cur_prc": info.get("cur_prc"),
                "flu_rt": info.get("flu_rt"),
            }
            print("[TEST] get_stock_info 성공:", json.dumps(basic, ensure_ascii=False))
        except Exception as e:
            print("[TEST] get_stock_info 실패:", e)
        sys.exit(0)

    cmd = args[0]
    if cmd == "get_stock_info":
        code = args[1] if len(args) > 1 else os.getenv("KIWOOM_TEST_STOCK", "005930")
        info = get_stock_info(code)
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == "get_account_evaluation":
        info = get_account_evaluation()
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == "buy_order":
        if len(args) < 3:
            print("사용법: buy_order <종목코드/종목명> <수량> [가격]")
            sys.exit(1)
        code = args[1]
        qty = int(args[2])
        price = int(args[3]) if len(args) > 3 else None
        info = buy_order(code, qty, price)
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == "sell_order":
        if len(args) < 3:
            print("사용법: sell_order <종목코드/종목명> <수량> [가격]")
            sys.exit(1)
        code = args[1]
        qty = int(args[2])
        price = int(args[3]) if len(args) > 3 else None
        info = sell_order(code, qty, price)
        print(json.dumps(info, ensure_ascii=False))
    else:
        print(f"알 수 없는 명령: {cmd}")
        sys.exit(1)

