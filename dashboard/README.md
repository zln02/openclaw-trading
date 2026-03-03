# OpenClaw Dashboard

React + Vite 기반 실시간 대시보드. FastAPI 서버(포트 8080)에서 정적 파일로 서빙.

## 탭 구성

| 탭 | 경로 | 설명 |
|----|------|------|
| BTC | `/` | 캔들, 복합스코어, 포지션, F&G, 뉴스 |
| KR 주식 | `/kr` | 키움 실시간 포트폴리오, TOP 모멘텀 종목, 거래기록 |
| US 주식 | `/us` | 시장 지수, 모멘텀 랭킹, 포지션, 환율 |
| 에이전트 | `/agents` | AI 에이전트 결정 이력 |

## 개발

```bash
cd dashboard
npm install
npm run dev      # http://localhost:3000 (API 프록시 → :8080)
```

## 빌드 & 배포

```bash
npm run build    # dist/ 생성
# FastAPI가 dist/ 를 정적 파일로 서빙 (run_dashboard.sh)
```

## API 프록시

`vite.config.js` — 개발 시 `/api/*` → `http://localhost:8080` 프록시.
