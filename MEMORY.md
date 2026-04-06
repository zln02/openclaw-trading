# 🧠 제이(J)의 장기 기억

## 사용자 프로필
- **이름:** 광주 거주 개발자
- **관심사:** AI/반도체, 1인 AI 회사 준비
- **투자 종목:** SK하이닉스, 삼성전자, NVIDIA, TSMC, 애플, BTC
- **언어:** 한국어 반말, 핵심만 짧게, 이모지 OK
- **시간대:** KST (Asia/Seoul, UTC+9)

## 시스템 현황
- **OpenClaw:** v2026.3.31, Gateway 포트 18789, systemd 서비스
- **자동매매 (OpenClaw Trading System v6.1):**
  - BTC: Upbit 실거래 (24/7)
  - KR 주식: 키움증권 모의투자
  - US 주식: yfinance DRY-RUN
  - 대시보드: http://localhost:8080
  - 워크스페이스: /home/wlsdud5035/.openclaw/workspace/
- **서버:** GCP e2-small (2 vCPU, 2GB RAM)
- **DB:** Supabase (trade_executions, agent_decisions 등)
- **AI:** Claude (Anthropic), GPT-4o-mini (OpenAI)

## 배운 교훈
- Gateway 프로세스가 1GB 이상 먹을 수 있음 → NODE_OPTIONS --max-old-space-size=512 필수
- systemd 서비스 파일 경로가 npx 캐시 경로면 업데이트 후 깨짐 → 전역 설치 경로 사용
- 크론 잡 delivery.to에 "last"는 불안정 → 숫자 chat ID(8583323855) 직접 지정
- AGENTS.md 경로 버그: gateway가 docs/reference/templates/AGENTS.md 요구 → 심볼릭 링크로 우회

## OpenClaw Notify 연동 (Phase 5~6 완료, 2026-04-02)
- `common/openclaw_notify.py` → OpenClaw Gateway에 이벤트 전달
- BTC: 매수/매도/손절 5곳 연동
- KR: 매수/매도 2곳 연동
- Drawdown Guard: 가드 활성화 시 urgent 알림
- `scripts/cleanup_sessions.sh`: 세션/brain/로그 자동 정리 스크립트
- Gateway hooks: wake hook 설정 완료 (openclaw.json)

## 결정 기록
- [2026-04-02] OpenClaw v2026.3.31 전역 설치, systemd 서비스 업데이트
- [2026-04-02] 모든 크론 잡 에러 리셋, delivery.to 통일
- [2026-04-02] Phase 5~6 완료: notify 연동 (BTC/KR/Drawdown), cleanup 스크립트, hooks, 에러 리셋

## 요청 패턴
- 아침: 브리핑 (일정/메일/뉴스/주식/날씨)
- 낮: 뉴스 수집, 시장 모니터링
- 저녁: 투자 리포트
- 밤: 하루 정리
- 주간: 종합 리포트 (일요일)
- 수시: 시스템 헬스체크, 매매 상태 확인
