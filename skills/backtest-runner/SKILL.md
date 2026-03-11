# Backtest Runner 스킬

사용자가 "백테스트 돌려줘", "이 종목 전략 검증해줘", "성과 확인해줘"라고 하면 이 스킬을 사용한다.

## 핵심 대상

- `/home/wlsdud5035/.openclaw/workspace/quant/backtest/`
- `/home/wlsdud5035/.openclaw/workspace/backtest/backtest_engine.py`
- `/home/wlsdud5035/.openclaw/workspace/stocks/ml_model.py`

## 기본 실행 예시

```bash
PYTHONPATH=/home/wlsdud5035/.openclaw/workspace python3 /home/wlsdud5035/.openclaw/workspace/backtest/backtest_engine.py
```

전략/유니버스/기간 옵션이 있으면 코드에서 CLI 인자를 먼저 확인한 뒤 그 형식에 맞춰 실행한다.

## 검증 포인트

- 총수익률
- MDD
- 승률
- 거래 수
- 벤치마크 대비 초과수익

## 응답 원칙

- 결과 숫자를 먼저 보고한다.
- 샘플 수가 적거나 데이터 소스가 제한되면 그 한계를 바로 적는다.
- 가능하면 생성된 결과 파일 경로를 같이 남긴다.
