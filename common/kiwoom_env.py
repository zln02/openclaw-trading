"""키움 API 환경변수 로딩 단일 진입점.

이 모듈은 키움 자격증명을 로딩하는 유일한 진입점이다(Single Source of Truth).

설계 원칙:
- mock 모드: KIWOOM_MOCK_* 변수만 사용
- 실전 모드: KIWOOM_* 변수만 사용
- or-fallback 없음 (silent wrong-key injection 방지)
- 키 누락 시 ValueError로 즉시 실패
- TRADING_ENV 환경변수로 모드 결정 (기본 'mock')
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KiwoomCredentials:
    api_key: str
    api_secret: str
    account_no: Optional[str]
    use_mock: bool
    base_url: str


_MOCK_BASE_URL = "https://mockapi.kiwoom.com"
_PROD_BASE_URL = "https://api.kiwoom.com"


def resolve_use_mock(use_mock: Optional[bool] = None) -> bool:
    """모드 결정 헬퍼.

    명시 인자(use_mock)가 주어지면 그것을 우선 사용하고,
    없으면 TRADING_ENV 환경변수(기본 'mock')로 결정한다.
    """
    if use_mock is not None:
        return use_mock
    trading_env = os.getenv("TRADING_ENV", "mock").lower()
    return trading_env == "mock"


def get_kiwoom_credentials(use_mock: Optional[bool] = None) -> KiwoomCredentials:
    """키움 자격증명 로딩.

    Args:
        use_mock: None이면 TRADING_ENV로 결정. True/False 명시 가능.

    Returns:
        KiwoomCredentials: api_key, api_secret, account_no, use_mock, base_url

    Raises:
        ValueError: 선택된 모드의 키가 누락된 경우 (or-fallback 없음)
    """
    use_mock = resolve_use_mock(use_mock)

    if use_mock:
        api_key = os.getenv("KIWOOM_MOCK_REST_API_APP_KEY", "")
        api_secret = os.getenv("KIWOOM_MOCK_REST_API_SECRET_KEY", "")
        account_no = os.getenv("KIWOOM_MOCK_ACCOUNT_NO")
        base_url = _MOCK_BASE_URL
        required = "KIWOOM_MOCK_REST_API_APP_KEY / KIWOOM_MOCK_REST_API_SECRET_KEY"
    else:
        api_key = os.getenv("KIWOOM_REST_API_KEY", "")
        api_secret = os.getenv("KIWOOM_REST_API_SECRET", "")
        account_no = os.getenv("KIWOOM_ACCOUNT_NO")
        base_url = _PROD_BASE_URL
        required = "KIWOOM_REST_API_KEY / KIWOOM_REST_API_SECRET"

    if not api_key or not api_secret:
        env_name = "모의투자" if use_mock else "실전투자"
        raise ValueError(
            f"키움 {env_name} API 키가 설정되지 않았습니다. 필요: {required}"
        )

    return KiwoomCredentials(
        api_key=api_key,
        api_secret=api_secret,
        account_no=account_no,
        use_mock=use_mock,
        base_url=base_url,
    )
