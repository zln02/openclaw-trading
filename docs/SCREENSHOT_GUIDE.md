# 📸 Screenshot Guide

README에 들어갈 스크린샷 촬영 가이드입니다.

## 필요한 스크린샷 목록

### 1. 배너 이미지

- **파일**: `docs/images/banner.png`
- **크기**: 1200x400
- **내용**: 프로젝트 로고 + "OpenClaw Trading System v6.0" + 보라/블루 그라디언트 배경
- **도구**: Figma 또는 Canva

### 2. 대시보드 — BTC 탭

- **파일**: `docs/images/dashboard-btc.png`
- **크기**: 1280x720
- **캡처 방법**: 브라우저에서 http://localhost:8080 접속 → BTC 탭 선택 → 캔들차트 + 복합스코어 게이지 + 포지션 카드 + F&G 인디케이터가 모두 보이는 상태에서 캡처
- **주의**: 브라우저 주소창 제거 (F11 전체화면 또는 크롭)

### 3. 대시보드 — KR 주식 탭

- **파일**: `docs/images/dashboard-kr.png`
- **크기**: 1280x720
- **캡처 내용**: 포트폴리오 원형차트 + 보유종목 테이블 + TOP 모멘텀 랭킹

### 4. 대시보드 — US 주식 탭

- **파일**: `docs/images/dashboard-us.png`
- **크기**: 1280x720
- **캡처 내용**: 시장지수 카드 3개(S&P/NASDAQ/DJI) + 모멘텀 랭킹 테이블 + 포지션

### 5. 대시보드 — Agents 탭

- **파일**: `docs/images/dashboard-agents.png`
- **크기**: 1280x720
- **캡처 내용**: AI 에이전트 결정 이력 타임라인

### 6. 텔레그램 알림

- **파일**: `docs/images/telegram-alerts.png`
- **크기**: 360x640 (모바일 비율)
- **캡처 내용**: 매수 알림, 매도 알림, 일일 리포트, Level 5 파라미터 변경 알림 (3~4개)
- **주의**: 채팅 ID 등 개인정보 모자이크

### 7. Equity Curve

- **파일**: `docs/images/equity-curve.png`
- **생성**: `python scripts/generate_performance_report.py`
- **내용**: BTC/KR/US 3개 시장 누적 수익률 라인 차트
