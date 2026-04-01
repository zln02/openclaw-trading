---
name: risk-report
description: 리스크 리포트 — VaR, MDD, 드로우다운 상태, 매수 차단 여부
---

# Risk Report 스킬

사용자가 "리스크 리포트", "VaR 보여줘", "드로우다운 상태", "매수 차단 걸렸나" 같이 물으면 이 스킬을 사용한다.

## 핵심 대상

- `/home/wlsdud5035/.openclaw/workspace/common/risk_snapshot.py`
- `/home/wlsdud5035/.openclaw/workspace/agents/alert_manager.py`
- `/home/wlsdud5035/.openclaw/workspace/brain/risk/latest_snapshot.json`
- `/home/wlsdud5035/.openclaw/workspace/brain/ml/drift_report.json`
- `/home/wlsdud5035/.openclaw/workspace/brain/ml/us/drift_report.json`

## 기본 실행 순서

1. 최신 리스크 스냅샷 생성
```bash
PYTHONPATH=/home/wlsdud5035/.openclaw/workspace python3 /home/wlsdud5035/.openclaw/workspace/common/risk_snapshot.py
```

2. 결과 확인
```bash
python3 - <<'PY'
import json, pathlib
path = pathlib.Path('/home/wlsdud5035/.openclaw/workspace/brain/risk/latest_snapshot.json')
print(json.loads(path.read_text()) if path.exists() else {'missing': True})
PY
```

3. 드리프트 상태 같이 확인
```bash
python3 - <<'PY'
import json, pathlib
for name in ['brain/ml/drift_report.json', 'brain/ml/us/drift_report.json']:
    path = pathlib.Path('/home/wlsdud5035/.openclaw/workspace') / name
    print(name, json.loads(path.read_text()) if path.exists() else {'missing': True})
PY
```

## 응답 원칙

- `VaR`, `CVaR`, `drawdown`, 포지션 수를 먼저 요약한다.
- KR/US 드리프트가 `WARNING` 또는 `DANGER`면 그 영향을 별도로 적는다.
- 리스크 게이트가 신규 BUY를 막는 상태면 그 사실을 명확히 말한다.
