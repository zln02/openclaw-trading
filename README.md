# OpenClaw Trading System

## 구성
- btc/       — BTC 자동매매 (Upbit + gpt-4o-mini)
- kiwoom/    — 주식 자동매매 (개발 중)
- secretary/ — 비서(제이) 텔레그램 관리
- skills/    — AI 스킬 모음
- schema/    — DB 스키마 (Supabase)
- scripts/   — 실행 스크립트

## 빠른 실행
```bash
# BTC 매매
python3 btc/btc_trading_agent.py

# 1시간 리포트
python3 btc/btc_trading_agent.py report

# 대시보드
python3 btc/btc_dashboard.py
```
