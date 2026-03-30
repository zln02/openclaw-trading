# Cron 타이밍 매트릭스

## 실시간 (1~10분)

| 주기 | 작업 | 스크립트 |
|------|------|----------|
| 2분 | 알림 체크 | alert_manager.py |
| 5분 | 헬스체크 | self_healer.py |
| 10분 | BTC 매매 사이클 | btc_trading_agent.py |
| 10분 | KR 매매 사이클 | stock_trading_agent.py |
| 15분 | US 매매 사이클 | us_stock_trading_agent.py |

## 일간

| 시간(KST) | 작업 | 스크립트 |
|-----------|------|----------|
| 07:00 | 크로스마켓 배분 | cross_market_manager.py |
| 08:25 | KR ML 드리프트 | ml_drift_monitor.py |
| 08:30 | KR ML 재학습 | ml_model.py |
| 09:00 | 프리마켓 셋업 | stock_premarket.py |
| 18:00 | 일간 전략 리뷰 | strategy_reviewer.py |
| 22:20 | US ML 드리프트 | us_ml_drift_monitor.py |

## 주간

| 요일/시간 | 작업 | 스크립트 |
|-----------|------|----------|
| 토 22:00 | 알파 리서치 | alpha_researcher.py |
| 일 23:00 | 시그널 평가 | signal_evaluator.py |
| 일 23:30 | 파라미터 최적화 | param_optimizer.py |
| 일 04:00 | 세션 정리 | cleanup_sessions.sh |
