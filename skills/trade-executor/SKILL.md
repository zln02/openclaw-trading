---
name: trade-executor
description: 매매 실행 관련 명령을 다루는 스킬. 매수, 매도, 중지, 재개는 반드시 확인 절차를 둔다
---

⚠️ 이 스킬은 실제 돈이 움직이는 명령을 포함한다. 모든 매매 명령은 반드시 사용자 확인을 받은 뒤 실행한다.

모든 `exec` 경로는 `/home/wlsdud5035/.openclaw/workspace`, 로그 경로는 `/home/wlsdud5035/.openclaw/logs`, 가상환경은 `/home/wlsdud5035/.openclaw/workspace/.venv`를 사용한다.

## 매매 중지 `/stop`

사용자가 "매매 중지", "거래 멈춰", `/stop`을 요청하면:

```bash
touch /home/wlsdud5035/.openclaw/workspace/stocks/STOP_TRADING && echo "매매 중지 플래그 설정됨"
```

## 매매 재개 `/resume`

사용자가 "매매 재개", "거래 시작", `/resume`을 요청하면:

```bash
rm -f /home/wlsdud5035/.openclaw/workspace/stocks/STOP_TRADING && echo "매매 재개됨"
```

## 전체 매도 `/sell_all`

반드시 "정말 전체 매도하시겠습니까?"를 먼저 확인한 뒤 진행한다.

```bash
cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python3 -c "
from stocks.telegram_bot import handle_sell_all_confirm
handle_sell_all_confirm('')
"
```

실행 전에 현재 포지션과 시장 상태를 먼저 보여주는 편이 안전하다.

## 에이전트 재시작

사용자가 "BTC 에이전트 재시작", "KR 재시작" 등을 요청하면:

- 해당 Docker 컨테이너 이름과 재시작 명령을 안내한다.
- 직접 재시작은 하지 않는다.
- 포지션이 열려 있으면 재시작 전에 위험을 한 줄로 경고한다.
