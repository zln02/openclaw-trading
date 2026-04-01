---
name: market-briefing
description: 시장 브리핑 - BTC, KR, US 종합 현황을 한눈에 정리할 때 사용하는 스킬
---

사용자가 "브리핑", "시장", "마켓", "현황"을 요청하면 이 스킬을 사용한다.

모든 `exec` 경로는 `/home/wlsdud5035/.openclaw/workspace` 기준으로 잡고, 로그 경로는 `/home/wlsdud5035/.openclaw/logs`를 사용한다.

## 실행 순서

1. BTC 현재가 조회

```bash
curl -s "https://api.upbit.com/v1/ticker?markets=KRW-BTC" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'BTC: {d[0][\"trade_price\"]:,.0f}원 ({d[0][\"signed_change_rate\"]*100:+.2f}%)')"
```

2. BTC 복합 스코어 조회

```bash
curl -s -H "X-Dashboard-Password: rldyal" http://localhost:8080/api/btc/composite | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'복합스코어: {d.get(\"composite_score\",\"N/A\")}, 레짐: {d.get(\"regime\",\"N/A\")}')"
```

3. BTC 포지션 조회

```bash
cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python3 -c "
from common.supabase_client import get_supabase
sb = get_supabase()
pos = sb.table('btc_position').select('*').eq('status','OPEN').execute().data if sb else []
if pos:
    row = pos[0]
    print(f'BTC 포지션: {row.get(\"quantity\", 0)} BTC @ {float(row.get(\"entry_price\") or 0):,.0f}원')
else:
    print('BTC 포지션: 없음')
"
```

4. Fear & Greed 조회

```bash
curl -s "https://api.alternative.me/fng/?limit=1" | python3 -c "import json,sys; d=json.load(sys.stdin); v=d['data'][0]; print(f'공포탐욕: {v[\"value\"]} ({v[\"value_classification\"]})')"
```

5. KR/US 상태는 필요하면 `signal-query`, `portfolio-manager`와 연동해서 추가 조회한다.

## 응답 형식

결과는 이모지를 포함한 깔끔한 마크다운으로 정리한다.

```markdown
📊 시장 브리핑 (KST)
- BTC: 가격, 등락률, 포지션, 복합스코어, 레짐
- 공포탐욕 지수
- KR/US 시장 상태
```

짧게 요약하고, stale 데이터면 갱신 시각과 함께 그 사실을 밝힌다.
