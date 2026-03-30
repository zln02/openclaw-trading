# Agents Module

AI 전략 에이전트 계층. 시장 분석, 레짐 분류, 뉴스 분석, 알림을 담당한다.

## 파일 구조

| 파일 | 역할 | 사용 빈도 |
|------|------|----------|
| regime_classifier.py | 시장 레짐 분류 (BULL/BEAR/TRANSITION/CRISIS) | 매 사이클 |
| news_analyst.py | 뉴스 감성 분석 (Claude/GPT 배치) | 매 사이클 |
| alert_manager.py | 리스크 알림 (드로우다운, 손실 한도) | 2분마다 |
| strategy_reviewer.py | 일간/주간 전략 리뷰 | 일 1회 |
| daily_loss_analyzer.py | 일일 손익 분석 | 일 1회 |
| gateway_agent.py | 텔레그램 자연어 처리 보조 | 텔레그램 요청 시 |
| trading_agent_team.py | 5-에이전트 Claude 팀 | 수동 실행 |
| self_healer.py | 시스템 헬스체크 (5분마다) | 크론 |

## 의존성

- `common/logger.py` — 로깅
- `common/supabase_client.py` — DB 접근
- `common/telegram.py` — 알림 발송
- `common/config.py` — 설정값

## 실행 예시

```bash
# 레짐 분류 단독 실행
PYTHONPATH=/home/wlsdud5035/openclaw python agents/regime_classifier.py

# 5-에이전트 팀 실행
python -m agents.trading_agent_team --market btc

# 헬스체크
python agents/self_healer.py
```
