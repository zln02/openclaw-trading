---
name: portfolio-manager
description: 포트폴리오 현황 — 시장별 비중, 리밸런싱 상태, BTC/KR/US 배분
---

# Portfolio Manager 스킬

사용자가 "포트폴리오 현황", "시장별 비중", "리밸런싱 상태", "BTC/KR/US 배분 보여줘" 같이 물으면 이 스킬을 사용한다.

## 핵심 대상

- `/home/wlsdud5035/.openclaw/workspace/quant/portfolio/cross_market_manager.py`
- `/home/wlsdud5035/.openclaw/workspace/brain/portfolio/market_allocation.json`
- `/home/wlsdud5035/.openclaw/workspace/brain/portfolio/target_weights.json`
- `/home/wlsdud5035/.openclaw/workspace/common/equity_loader.py`

## 기본 확인 순서

1. 현재 배분 파일 확인
```bash
python3 - <<'PY'
import json, pathlib
path = pathlib.Path('/home/wlsdud5035/.openclaw/workspace/brain/portfolio/market_allocation.json')
print(json.loads(path.read_text()) if path.exists() else {'missing': True})
PY
```

2. 필요 시 배분 재계산
```bash
PYTHONPATH=/home/wlsdud5035/.openclaw/workspace python3 /home/wlsdud5035/.openclaw/workspace/quant/portfolio/cross_market_manager.py
```

3. 리밸런싱 목표 비중 재생성
```bash
bash /home/wlsdud5035/.openclaw/workspace/scripts/run_portfolio_rebalance.sh
```

## 응답 원칙

- 현재 `btc/kr/us/cash` 비중을 퍼센트로 먼저 요약한다.
- `updated_at`, `rebalance_due`, 레짐 상태를 같이 말한다.
- 파일이 없으면 재계산을 시도하고, 실패하면 누락 사실과 원인을 분리해서 말한다.
