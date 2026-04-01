---
name: signal-query
description: BTC/KR/US 매매 신호 조회 — 복합 스코어, 레짐, 추천 종목
---

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

## 대시보드 복합 스코어 조회

대시보드가 로컬에서 떠 있으면 아래 엔드포인트를 우선 사용한다. 내부 대시보드 접근은 예외적으로 `X-Dashboard-Password` 헤더를 붙여도 된다.

```bash
curl -s -H "X-Dashboard-Password: rldyal" http://localhost:8080/api/btc/composite
curl -s -H "X-Dashboard-Password: rldyal" http://localhost:8080/api/kr/composite
curl -s -H "X-Dashboard-Password: rldyal" http://localhost:8080/api/us/composite
```

응답은 필요한 필드만 뽑아서 마크다운 테이블로 정리한다. 기본 컬럼은 `market`, `composite_score`, `regime`, `signal`, `updated_at` 우선이다.

예시:

```markdown
| 시장 | 복합스코어 | 레짐 | 신호 | 갱신시각 |
|---|---:|---|---|---|
| BTC | 0.71 | RISK_ON | BUY | 2026-03-27T12:00:00+09:00 |
```
