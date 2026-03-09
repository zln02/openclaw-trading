# OpenClaw System Master Review Prompt (Opus CLI용)
# 사용법: claude -p "$(cat openclaw_opus_master_prompt.md)"

---

You are a senior software architect and quantitative trading systems expert.
Think step-by-step and reason deeply before answering each section.
For every recommendation, include: WHY it matters, difficulty level (쉬움/보통/어려움), and a concrete code spec or pseudocode that Claude Sonnet can immediately implement.

---

## 🧠 내 정보

- 컴퓨터공학과 학생 + AI 엔지니어 목표
- 포트폴리오/이력서 기술 스택 업그레이드 중
- GCP e2-small 서버에서 24시간 운영 중

---

## 📦 시스템 개요: OpenClaw Trading System v5.0

### 현재 실행 상태
- BTC: Upbit 실거래 중 (자본 50만원 미만)
- KR 주식: 키움증권 모의투자
- US 주식: DRY-RUN ($10,000 가상)

### 기술 스택
| 항목 | 현재 |
|------|------|
| 서버 | GCP e2-small (24시간) |
| AI 판단 | GPT-4o-mini |
| DB | Supabase (PostgreSQL) |
| 알림 | Telegram Bot |
| 대시보드 | FastAPI + Lightweight Charts (포트 8080) |
| ML | XGBoost (KR 주식 매수 예측, 승률 78%+) |
| 바이브코딩 | Claude Sonnet (CLI) |

### 폴더 구조
```
workspace/
├── agents/       ← 에이전트 정의 (현재 미연결)
├── brain/        ← 판단 로직 (현재 미연결)
├── memory/       ← 기억 시스템 (현재 미연결)
├── skills/       ← 스킬 모듈 (현재 미연결)
├── secretary/    ← 텔레그램 비서 (단순 알림만)
├── btc/          ← BTC 매매 에이전트 (실제 동작 중)
├── stocks/       ← KR/US 주식 에이전트 (동작 중)
├── common/       ← 공통 유틸 (config, supabase, telegram, indicators)
├── dashboard/    ← (미사용, btc/에 통합됨)
├── quant/        ← (내용 불명확)
├── execution/    ← (내용 불명확)
├── schema/       ← Supabase SQL 스키마
├── prompts/      ← AI 프롬프트/대화 기록
├── scripts/      ← cron 실행 스크립트
├── supabase/     ← DB 관련
├── docs/         ← 시스템 문서
└── tests/        ← 테스트 (내용 불명확)
```

### 현재 BTC 전략
- 복합스코어 ≥ 45 (F&G + 일봉RSI + BB + 거래량 + 추세 + 7일수익률)
- 손절 -3% / 익절 +15% / 트레일링 2%
- 타임컷 7일 / 쿨다운 30분 / 일일 최대 3회
- GPT-4o-mini가 매번 과거 기억 없이 판단

### 현재 KR 주식 전략
- 모멘텀 + RSI/BB/거래량 + DART 재무제표
- XGBoost 예측 (승률 78%+ 기준)
- 분할매수 3단계 / 손절 -3% / 익절 +8%
- 08:00 AI 브리핑 → 09:00~15:30 자동매매

### 현재 US 주식 전략
- S&P500 + NASDAQ100 모멘텀 랭킹
- A/B/C/D 등급 → DRY-RUN

---

## ❌ 현재 문제점 (내가 인식하는 것)

1. agents/brain/memory/skills 폴더가 있지만 실제 매매 루프와 완전히 단절됨
2. GPT 판단에 과거 거래 기억이 없음 (매번 새로 판단)
3. BTC 실거래 수익이 안 나고 있음 (수수료 누적 의심)
4. secretary/가 단순 알림만 하고 진짜 비서 역할 없음
5. 폴더 구조가 중복되거나 불명확한 것들 존재 (dashboard/, quant/, execution/)
6. 보안: .env 관리, API 키 노출 위험 여부 불명확
7. GCP e2-small이 모든 에이전트 동시 실행 시 메모리 한계 의심
8. 테스트 코드 부재 가능성
9. CI/CD 없음
10. 이력서/포트폴리오에 내세울 수 있는 명확한 아키텍처 스토리 부재

---

## 📋 분석 요청 항목

아래 9개 영역을 순서대로 깊이 분석하고, 각 항목마다:
- 현재 문제의 근본 원인
- 구체적 개선 방향 (우선순위 포함)
- Sonnet이 바로 구현할 수 있는 코드 스펙/함수 시그니처
- 구현 난이도 (쉬움/보통/어려움)
- 예상 임팩트 (수익화 / 안정성 / 포트폴리오 가치)

### 1. 🏗️ OpenClaw 아키텍처 재설계
- agents/brain/memory/skills를 실제 매매 루프에 연결하는 최단 경로
- 각 폴더의 명확한 역할 재정의
- 멀티에이전트 협업 구조 (BTC/KR/US 에이전트 + 공유 Brain)
- OpenClaw를 "AI 에이전트 프레임워크"로 포지셔닝하는 설계 원칙

### 2. 💰 BTC 매매 전략 최적화 (소자본 50만원 기준)
- 현재 파라미터의 문제점 진단
- 수수료 최적화 (Upbit 0.05% × 양방향 × 빈도)
- 소자본에 맞는 손익비, 진입 임계값, 쿨다운 재조정
- 복합스코어 구성 요소 가중치 최적화 방향

### 3. 🧠 AI 판단 품질 개선
- GPT-4o-mini → 어떤 상황에서 Claude로 전환해야 하나
- 과거 거래 기억을 프롬프트에 주입하는 구조 설계
- 시장 국면(상승장/하락장/횡보) 인식을 판단에 반영하는 방법
- 프롬프트 최적화: 지금 당장 추가해야 할 컨텍스트 3가지

### 4. 🗄️ 메모리 시스템 설계
- Supabase 기존 데이터를 활용한 거래 기억 구조
- 단기 기억 (최근 10회 거래) vs 장기 기억 (패턴 학습) 분리
- 주간 회고(reflection) 자동화: GPT가 자기 판단을 평가하는 루프
- memory/ 폴더 구현 스펙

### 5. 🤖 Secretary(텔레그램 비서) 강화
- 현재: 단순 알림 → 목표: 양방향 대화형 비서
- 명령어 체계 설계 (예: /status, /pause, /resume, /report)
- Brain과 연동해서 자연어로 시스템 상태 조회
- 구현 난이도와 우선순위

### 6. 📊 대시보드 개선
- 현재 FastAPI + Lightweight Charts 구조의 한계
- 실시간 판단 근거 시각화 (왜 매수/매도했는지)
- 성과 분석 패널 (샤프비율, MDD, 승률 등)
- GCP e2-small에서 무겁지 않게 운영하는 최적화 방법

### 7. 📁 파일/폴더 구조 정리
- 현재 중복/불명확한 폴더 정리 방안 (dashboard/, quant/, execution/ 등)
- 명확한 모듈 경계 설계
- 포트폴리오로 보여줄 때 깔끔한 구조 제안
- __init__.py, imports 정리 방향

### 8. 🔒 보안 및 운영 안정성
- GCP e2-small에서 .env / secrets 관리 베스트 프랙티스
- API 키 노출 위험 체크리스트
- 메모리/CPU 한계에서 다중 에이전트 안정 운영 방법
- 헬스체크 및 자동 재시작 구조 (현재 check_health.sh 보완)
- 로그 관리 (에러 추적, 거래 감사 로그)

### 9. 🚀 기술 스택 업그레이드 & 포트폴리오 전략
- 현재 스택에서 이력서 임팩트를 높이기 위해 추가할 기술 TOP 3
- "AI 에이전트 기반 자동매매 시스템" 포트폴리오 스토리 작성 방향
- 단기(1달) / 중기(3달) 기술 로드맵
- 취업/포트폴리오 관점에서 가장 먼저 완성해야 할 것

---

## 📤 출력 형식 요구사항

- 각 섹션 제목을 명확히 구분
- 우선순위는 항상 P1(이번 주) / P2(이번 달) / P3(나중에)로 표시
- 코드 스펙은 Python 기준, 함수 시그니처 + 핵심 로직 주석 포함
- 마지막에 "이번 주 월요일부터 시작할 ACTION PLAN TOP 5" 요약 제공
- Sonnet이 바로 코딩 작업에 들어갈 수 있도록 구체적으로 작성
