"""OpenClaw AI Software Company — Claude 다중 에이전트 팀 (Phase 14).

팀 구성:
  CEO        (claude-opus-4-6)        — 전체 조율, 위임, 최종 보고
  CTO        (claude-opus-4-6)        — 기술 아키텍처 설계·검토
  Backend    (claude-sonnet-4-6)      — Python/FastAPI/Supabase
  Frontend   (claude-sonnet-4-6)      — React/Vite/Tailwind 대시보드
  Quant      (claude-sonnet-4-6)      — 전략/ML/백테스트
  DevOps     (claude-haiku-4-5)       — cron/배포/모니터링
  QA         (claude-haiku-4-5)       — 코드 리뷰/버그 탐지

사용법:
    from company import TradingCompany
    company = TradingCompany()
    company.request("대시보드에 BTC 차트 추가해줘")
"""

from company.trading_company import TradingCompany

__all__ = ["TradingCompany"]
