# Signal Query 스킬

사용자가 "BTC 신호 알려줘", "KR 추천 종목", "US 모멘텀", "현재 레짐 뭐야" 같이 신호 조회를 요청하면 이 스킬을 사용한다.

## 핵심 대상

- `/home/wlsdud5035/.openclaw/workspace/api/signal_api.py`
- `/home/wlsdud5035/.openclaw/workspace/api/ws_stream.py`
- `/home/wlsdud5035/.openclaw/workspace/brain/portfolio/market_allocation.json`

## 조회 방법

환경변수에 `PUBLIC_API_KEYS`가 설정돼 있으면 HTTP로 직접 확인한다.

```bash
curl -H "X-API-Key: $PUBLIC_API_KEY" http://localhost:8080/api/v1/signals/btc
curl -H "X-API-Key: $PUBLIC_API_KEY" http://localhost:8080/api/v1/signals/kr
curl -H "X-API-Key: $PUBLIC_API_KEY" http://localhost:8080/api/v1/signals/us
curl -H "X-API-Key: $PUBLIC_API_KEY" http://localhost:8080/api/v1/signals/regime
curl -H "X-API-Key: $PUBLIC_API_KEY" http://localhost:8080/api/v1/portfolio/allocation
```

API 키가 없으면 관련 소스 파일과 `brain/` 산출물을 직접 읽어 요약한다.

## 응답 원칙

- 먼저 추천/레짐/업데이트 시각을 짧게 요약한다.
- KR/US는 top picks 상위 3~5개만 보여준다.
- 신호가 stale이면 `updated_at` 기준으로 그 사실을 명시한다.
