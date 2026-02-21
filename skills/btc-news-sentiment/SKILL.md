# BTC 뉴스·감정 스킬

## 역할
- 비트코인/가상자산 관련 뉴스 수집
- 호재/악재 키워드 감지 후 요약 문자열로 전달 → `btc_trading_agent`의 `analyze_with_ai` 입력

## 연동
- `workspace/btc_news_collector.py`: 뉴스 수집(파일/DB 저장)
- 에이전트는 수집 결과를 읽어 `get_news_sentiment()` 또는 직접 파일 내용을 `news_summary`로 전달

## 활용
- AI 매매 신호 시 뉴스 요약을 프롬프트에 포함해 감정 반영
- RAM 절약: 뉴스 수집은 별도 Cron/프로세스로 돌리고, 에이전트는 요약만 읽기
