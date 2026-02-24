"""
키움증권 REST API 클라이언트 템플릿

사용법:
    1. 프로젝트 루트에 .env 파일 생성 (cp .env.example .env)
    2. .env 파일에 API 인증 정보 입력
    3. 이 템플릿을 복사하여 사용

필수 환경 변수:
    TRADING_ENV=mock              # mock 또는 prod
    KIWOOM_REST_API_KEY=your_key
    KIWOOM_REST_API_SECRET=your_secret
    KIWOOM_ACCOUNT_NO=5012345678  # 계좌번호 (모의투자: 50으로 시작)
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Optional, List

try:
    from dotenv import load_dotenv
    _has_dotenv = True
except ImportError:
    _has_dotenv = False
    load_dotenv = None  # type: ignore[misc, assignment]

import httpx


def _load_env_from_file(env_path: Path) -> bool:
    """.env 파일에서 환경변수 로드. dotenv 미설치 시 False."""
    if not _has_dotenv or load_dotenv is None:
        return False
    if not env_path.exists():
        return False
    load_dotenv(env_path)
    return True


def find_project_root() -> Path:
    """프로젝트 루트 디렉토리 찾기 (.env 파일 위치)"""
    current = Path(__file__).resolve().parent

    # 1차: .env 파일을 우선 탐색 (최대 10레벨)
    search = current
    for _ in range(10):
        if (search / ".env").exists():
            return search
        parent = search.parent
        if parent == search:
            break
        search = parent

    # 2차: .env.example 파일을 탐색 (fallback)
    search = current
    for _ in range(10):
        if (search / ".env.example").exists():
            return search
        parent = search.parent
        if parent == search:
            break
        search = parent

    # 찾지 못하면 현재 작업 디렉토리 사용
    return Path.cwd()


class KiwoomAPIClient:
    """키움증권 REST API 클라이언트"""

    def __init__(self, use_mock: Optional[bool] = None):
        """
        Args:
            use_mock (bool, optional):
                - True: 모의투자 (mockapi.kiwoom.com)
                - False: 실전투자 (api.kiwoom.com)
                - None: .env의 TRADING_ENV 값 사용 (기본값)
        """
        # 프로젝트 루트의 .env 로드 (python-dotenv 설치 시). 미설치 시 os.environ만 사용(openclaw 등에서 주입 가능).
        project_root = find_project_root()
        env_path = project_root / ".env"
        loaded = _load_env_from_file(env_path)
        if not loaded and _has_dotenv:
            example_path = project_root / ".env.example"
            if example_path.exists():
                raise ValueError(
                    f".env 파일이 없습니다. 먼저 생성하세요:\n"
                    f"  cp {example_path} {env_path}"
                )
            raise ValueError(".env 파일을 찾을 수 없습니다.")

        # use_mock 결정: 인자 > 환경변수
        if use_mock is None:
            trading_env = os.getenv("TRADING_ENV", "mock").lower()
            use_mock = (trading_env == "mock")

        # openclaw.json env는 KIWOOM_MOCK_* 이름으로 주입될 수 있음
        self.api_key = (
            os.getenv("KIWOOM_REST_API_KEY")
            or os.getenv("KIWOOM_MOCK_REST_API_APP_KEY")
        )
        self.api_secret = (
            os.getenv("KIWOOM_REST_API_SECRET")
            or os.getenv("KIWOOM_MOCK_REST_API_SECRET_KEY")
        )
        self.account_no = (
            os.getenv("KIWOOM_ACCOUNT_NO")
            or os.getenv("KIWOOM_MOCK_ACCOUNT_NO")
        )

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "API Key/Secret이 설정되지 않았습니다.\n"
                ".env 파일에 KIWOOM_REST_API_KEY, KIWOOM_REST_API_SECRET을 설정하세요."
            )

        # Base URL 설정
        self.base_url = (
            "https://mockapi.kiwoom.com" if use_mock
            else "https://api.kiwoom.com"
        )
        self.use_mock = use_mock

        self.token = None
        self.token_expires = None

    def _get_token(self) -> str:
        """OAuth 토큰 발급 (캐시됨)"""
        if self.token and self.token_expires:
            if time.time() < self.token_expires:
                return self.token

        # 토큰 발급
        url = f"{self.base_url}/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "secretkey": self.api_secret
        }

        response = httpx.post(url, json=data, timeout=30.0)
        result = response.json()

        if result.get('return_code') != 0:
            raise Exception(f"토큰 발급 실패: {result.get('return_msg')}")

        self.token = result['token']
        self.token_expires = time.time() + 3600

        return self.token

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """
        주식 기본 정보 조회 (ka10001)

        Args:
            stock_code (str): 종목코드 6자리

        Returns:
            Dict: 주가 정보
        """
        token = self._get_token()

        url = f"{self.base_url}/api/dostk/stkinfo"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "ka10001",
            "authorization": f"Bearer {token}"
        }
        body = {"stk_cd": stock_code}

        response = httpx.post(url, headers=headers, json=body, timeout=30.0)
        result = response.json()

        if result.get('return_code') == 0:
            return result
        else:
            raise Exception(f"API 오류: {result.get('return_msg')}")

    def _call_api(self, api_id: str, endpoint: str, body: dict) -> Dict:
        """API 호출 공통 메서드.

        Args:
            api_id: TR 식별자 (예: "kt00004")
            endpoint: URL 경로 (예: "/api/dostk/acnt")
            body: 요청 본문

        Returns:
            API 응답 딕셔너리

        Raises:
            Exception: return_code != 0 인 경우
        """
        token = self._get_token()
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "authorization": f"Bearer {token}",
        }
        response = httpx.post(url, headers=headers, json=body, timeout=30.0)
        result = response.json()

        if result.get("return_code") != 0:
            raise Exception(
                f"[{api_id}] API 오류 (code={result.get('return_code')}): "
                f"{result.get('return_msg')}"
            )
        return result

    # ------------------------------------------------------------------
    # 계좌 조회
    # ------------------------------------------------------------------

    def get_account_evaluation(self) -> Dict:
        """계좌평가현황 조회 (kt00004).

        예수금, 총평가금액, 보유종목별 손익 등 계좌 전반의 평가 현황을 반환한다.

        Returns:
            {
                "summary": {
                    "deposit": int,             # 예수금
                    "d2_deposit": int,          # D+2 추정 예수금
                    "total_evaluation": int,    # 유가잔고 평가액
                    "total_asset": int,         # 예탁자산 평가액
                    "total_purchase": int,      # 총 매입금액
                    "estimated_asset": int,     # 추정 예탁자산
                    "today_pnl": int,           # 당일 투자손익
                    "monthly_pnl": int,         # 당월 투자손익
                    "cumulative_pnl": int,      # 누적 투자손익
                    "today_pnl_pct": float,     # 당일 손익률
                    "monthly_pnl_pct": float,   # 당월 손익률
                    "cumulative_pnl_pct": float, # 누적 손익률
                },
                "holdings": [
                    {
                        "code": str,           # 종목코드
                        "name": str,           # 종목명
                        "quantity": int,       # 보유수량
                        "avg_price": int,      # 평균단가
                        "current_price": int,  # 현재가
                        "evaluation": int,     # 평가금액
                        "pnl_amount": int,     # 손익금액
                        "pnl_pct": float,      # 손익률
                        "purchase_amount": int, # 매입금액
                    },
                    ...
                ],
                "raw": dict,  # 원본 응답 (디버깅용)
            }
        """
        result = self._call_api("kt00004", "/api/dostk/acnt", {
            "qry_tp": "0",
            "dmst_stex_tp": "KRX",
        })

        def _int(v: str) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        def _float(v: str) -> float:
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        summary = {
            "deposit": _int(result.get("entr")),
            "d2_deposit": _int(result.get("d2_entra")),
            "total_evaluation": _int(result.get("tot_est_amt")),
            "total_asset": _int(result.get("aset_evlt_amt")),
            "total_purchase": _int(result.get("tot_pur_amt")),
            "estimated_asset": _int(result.get("prsm_dpst_aset_amt")),
            "today_pnl": _int(result.get("tdy_lspft")),
            "monthly_pnl": _int(result.get("lspft2")),
            "cumulative_pnl": _int(result.get("lspft")),
            "today_pnl_pct": _float(result.get("tdy_lspft_rt")),
            "monthly_pnl_pct": _float(result.get("lspft_ratio")),
            "cumulative_pnl_pct": _float(result.get("lspft_rt")),
        }

        holdings = []
        for s in result.get("stk_acnt_evlt_prst", []):
            holdings.append({
                "code": s.get("stk_cd", ""),
                "name": s.get("stk_nm", ""),
                "quantity": _int(s.get("rmnd_qty")),
                "avg_price": _int(s.get("avg_prc")),
                "current_price": abs(_int(s.get("cur_prc"))),
                "evaluation": _int(s.get("evlt_amt")),
                "pnl_amount": _int(s.get("pl_amt")),
                "pnl_pct": _float(s.get("pl_rt")),
                "purchase_amount": _int(s.get("pur_amt")),
            })

        return {"summary": summary, "holdings": holdings, "raw": result}

    def get_daily_balance_pnl(self, query_date: Optional[str] = None) -> Dict:
        """일별잔고수익률 조회 (ka01690).

        특정 일자 기준 잔고 및 종목별 수익률을 반환한다.

        Args:
            query_date: 조회일자 (YYYYMMDD). None이면 오늘.

        Returns:
            {
                "date": str,
                "summary": {
                    "total_purchase": int,
                    "total_evaluation": int,
                    "total_pnl": int,
                    "total_pnl_pct": float,
                    "deposit": int,
                    "estimated_asset": int,
                    "cash_ratio": float,
                },
                "holdings": [
                    {
                        "code": str,
                        "name": str,
                        "current_price": int,
                        "quantity": int,
                        "avg_price": int,
                        "buy_ratio": float,
                        "evaluation": int,
                        "eval_ratio": float,
                        "pnl_amount": int,
                        "pnl_pct": float,
                    },
                    ...
                ],
                "raw": dict,
            }

        Note:
            모의투자 지원 (KRX만). 주말/공휴일에는 빈 데이터 반환.
        """
        from datetime import date as _date

        if query_date is None:
            query_date = _date.today().strftime("%Y%m%d")

        result = self._call_api("ka01690", "/api/dostk/acnt", {
            "qry_dt": query_date,
        })

        def _int(v: str) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        def _float(v: str) -> float:
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        summary = {
            "total_purchase": _int(result.get("tot_buy_amt")),
            "total_evaluation": _int(result.get("tot_evlt_amt")),
            "total_pnl": _int(result.get("tot_evltv_prft")),
            "total_pnl_pct": _float(result.get("tot_prft_rt")),
            "deposit": _int(result.get("dbst_bal")),
            "estimated_asset": _int(result.get("day_stk_asst")),
            "cash_ratio": _float(result.get("buy_wght")),
        }

        holdings = []
        for s in result.get("day_bal_rt", []):
            holdings.append({
                "code": s.get("stk_cd", ""),
                "name": s.get("stk_nm", ""),
                "current_price": abs(_int(s.get("cur_prc"))),
                "quantity": _int(s.get("rmnd_qty")),
                "avg_price": _int(s.get("buy_uv")),
                "buy_ratio": _float(s.get("buy_wght")),
                "evaluation": _int(s.get("evlt_amt")),
                "eval_ratio": _float(s.get("evlt_wght")),
                "pnl_amount": _int(s.get("evltv_prft")),
                "pnl_pct": _float(s.get("prft_rt")),
            })

        return {
            "date": result.get("dt", query_date),
            "summary": summary,
            "holdings": holdings,
            "raw": result,
        }

    def get_settlement_balance(self, exchange: str = "KRX") -> Dict:
        """체결잔고 조회 (kt00005) - 실전투자 전용.

        체결된 주문의 결제 잔고를 조회한다. 예수금, 주문가능금액, 신용/대출 현황,
        종목별 결제잔고 및 평가손익을 반환한다.

        ⚠️ 모의투자 환경에서는 지원하지 않습니다 (return_code: 20).
        모의투자에서는 kt00004 (get_account_evaluation)를 사용하세요.

        Args:
            exchange: 거래소 구분 ("KRX", "NXT", "SOR"). 기본값 "KRX".

        Returns:
            {
                "summary": {
                    "deposit": int,               # 예수금
                    "deposit_d1": int,             # D+1 예수금
                    "deposit_d2": int,             # D+2 예수금
                    "orderable_cash": int,         # 주문가능금액
                    "withdrawable": int,           # 출금가능금액
                    "unsettled_cash": int,         # 미결제금액
                    "total_buy_amount": int,       # 총 매입금액
                    "total_evaluation": int,       # 총 평가금액
                    "total_pnl": int,              # 총 평가손익
                    "total_pnl_pct": float,        # 총 손익률
                    "substitute_amount": int,      # 대용금액
                    "credit_collateral_rate": float, # 신용담보비율
                },
                "holdings": [
                    {
                        "code": str,               # 종목코드
                        "name": str,               # 종목명
                        "settlement_balance": int,  # 결제잔고
                        "current_quantity": int,    # 현재잔고
                        "current_price": int,       # 현재가
                        "avg_price": int,           # 매입단가
                        "purchase_amount": int,     # 매입금액
                        "evaluation": int,          # 평가금액
                        "pnl_amount": int,          # 평가손익
                        "pnl_pct": float,           # 손익률
                        "credit_type": str,         # 신용구분
                        "loan_date": str,           # 대출일
                        "expire_date": str,         # 만기일
                    },
                    ...
                ],
                "raw": dict,  # 원본 응답 (디버깅용)
            }

        Raises:
            Exception: 모의투자 환경에서 호출 시 return_code 20 에러
        """
        if self.use_mock:
            raise Exception(
                "[kt00005] 모의투자에서는 체결잔고를 지원하지 않습니다. "
                "kt00004 (get_account_evaluation)를 사용하세요."
            )

        result = self._call_api("kt00005", "/api/dostk/acnt", {
            "dmst_stex_tp": exchange,
        })

        def _int(v) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        def _float(v) -> float:
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        summary = {
            "deposit": _int(result.get("entr")),
            "deposit_d1": _int(result.get("entr_d1")),
            "deposit_d2": _int(result.get("entr_d2")),
            "orderable_cash": _int(result.get("ord_alowa")),
            "withdrawable": _int(result.get("pymn_alow_amt")),
            "unsettled_cash": _int(result.get("ch_uncla")),
            "total_buy_amount": _int(result.get("stk_buy_tot_amt")),
            "total_evaluation": _int(result.get("evlt_amt_tot")),
            "total_pnl": _int(result.get("tot_pl_tot")),
            "total_pnl_pct": _float(result.get("tot_pl_rt")),
            "substitute_amount": _int(result.get("repl_amt")),
            "credit_collateral_rate": _float(result.get("crd_grnt_rt")),
        }

        holdings = []
        for s in result.get("stk_cntr_remn", []):
            holdings.append({
                "code": s.get("stk_cd", ""),
                "name": s.get("stk_nm", ""),
                "settlement_balance": _int(s.get("setl_remn")),
                "current_quantity": _int(s.get("cur_qty")),
                "current_price": abs(_int(s.get("cur_prc"))),
                "avg_price": _int(s.get("buy_uv")),
                "purchase_amount": _int(s.get("pur_amt")),
                "evaluation": _int(s.get("evlt_amt")),
                "pnl_amount": _int(s.get("evltv_prft")),
                "pnl_pct": _float(s.get("pl_rt")),
                "credit_type": s.get("crd_tp", ""),
                "loan_date": s.get("loan_dt", ""),
                "expire_date": s.get("expr_dt", ""),
            })

        return {"summary": summary, "holdings": holdings, "raw": result}

    def get_asset_summary(self) -> Dict:
        """현재 자산 상태 요약 (kt00004 래핑).

        투자 시작 전 자산 현황을 한눈에 파악하기 위한 편의 메서드.

        Returns:
            {
                "environment": str,        # "모의투자" or "실전투자"
                "deposit": int,            # 예수금 (주문가능현금)
                "estimated_asset": int,    # 추정 예탁자산
                "total_purchase": int,     # 총 매입금액
                "total_evaluation": int,   # 유가잔고 평가액
                "cumulative_pnl": int,     # 누적 손익
                "cumulative_pnl_pct": float, # 누적 손익률
                "holdings_count": int,     # 보유종목 수
                "holdings": list,          # 보유종목 리스트
            }
        """
        data = self.get_account_evaluation()
        s = data["summary"]
        return {
            "environment": "모의투자" if self.use_mock else "실전투자",
            "deposit": s["deposit"],
            "estimated_asset": s["estimated_asset"],
            "total_purchase": s["total_purchase"],
            "total_evaluation": s["total_evaluation"],
            "cumulative_pnl": s["cumulative_pnl"],
            "cumulative_pnl_pct": s["cumulative_pnl_pct"],
            "holdings_count": len(data["holdings"]),
            "holdings": data["holdings"],
        }

    def get_environment_info(self) -> Dict:
        """현재 환경 정보 반환"""
        return {
            "use_mock": self.use_mock,
            "base_url": self.base_url,
            "env_label": "모의투자" if self.use_mock else "실전투자",
            "account_no": self.account_no,
        }

    def place_order(
        self,
        stock_code: str,
        order_type: str,
        quantity: int,
        price: int = 0,
    ) -> Dict:
        """주식 주문 (buy/sell). 시장가 시 price=0."""
        token = self._get_token()
        trde_tp = "2" if order_type == "buy" else "1"
        ord_prc_ptn_cd = "03" if price == 0 else "00"

        acnt_no = (self.account_no or "")[:8]
        acnt_prdt_cd = (self.account_no or "01")[8:] if len(self.account_no or "") > 8 else "01"

        tr_id = "TTTC0802U" if self.use_mock else "TTTC0801U"
        url = f"{self.base_url}/api/dostk/ordr"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "appkey": self.api_key,
            "secretkey": self.api_secret,
            "tr_id": tr_id,
        }
        body = {
            "acnt_no": acnt_no,
            "acnt_prdt_cd": acnt_prdt_cd,
            "stk_cd": stock_code,
            "ord_qty": str(quantity),
            "ord_uv": str(price),
            "trde_tp": trde_tp,
            "ord_prc_ptn_cd": ord_prc_ptn_cd,
        }
        response = httpx.post(url, headers=headers, json=body, timeout=10.0)
        return response.json()


# 별칭 (stock_premarket 등에서 사용)
KiwoomClient = KiwoomAPIClient

# 사용 예시
if __name__ == "__main__":
    client = KiwoomAPIClient()

    # 환경 정보
    env_info = client.get_environment_info()
    print(f"환경: {env_info['env_label']} ({env_info['base_url']})")
    print()

    # 자산 요약
    print("=" * 50)
    print("자산 현황")
    print("=" * 50)
    summary = client.get_asset_summary()
    print(f"  환경: {summary['environment']}")
    print(f"  예수금: {summary['deposit']:,}원")
    print(f"  추정예탁자산: {summary['estimated_asset']:,}원")
    print(f"  총매입금액: {summary['total_purchase']:,}원")
    print(f"  유가잔고평가: {summary['total_evaluation']:,}원")
    print(f"  누적손익: {summary['cumulative_pnl']:+,}원 ({summary['cumulative_pnl_pct']:+.2f}%)")
    print(f"  보유종목: {summary['holdings_count']}개")

    if summary["holdings"]:
        print()
        print("  보유종목 상세:")
        for h in summary["holdings"]:
            print(f"    {h['name']} ({h['code']})"
                  f" | {h['quantity']}주"
                  f" | 평가: {h['evaluation']:,}원"
                  f" | 손익: {h['pnl_pct']:+.2f}%")
