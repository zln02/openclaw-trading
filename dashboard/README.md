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

## HTTPS

운영 환경은 `Caddy`가 `opentrading.duckdns.org`에 대해 자동 HTTPS를 처리하고, 내부적으로 `dashboard:8080`으로 프록시해.

```bash
cd /home/wlsdud5035/openclaw
docker compose up -d --build
```

필수 조건:

- `opentrading.duckdns.org` DNS가 현재 서버 IP를 가리켜야 함
- 서버 방화벽에서 `80/tcp`, `443/tcp`가 열려 있어야 함
- `.env`에 `ACME_EMAIL=you@example.com`을 넣으면 인증서 발급 추적이 쉬워짐

개발 환경은 백엔드(FastAPI/uvicorn)와 Vite 개발 서버 둘 다 인증서 파일이 있으면 HTTPS로 실행할 수 있어.

```bash
mkdir -p ../certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout ../certs/localhost-key.pem \
  -out ../certs/localhost-cert.pem \
  -days 365 \
  -subj "/CN=localhost"
```

백엔드 HTTPS:

```bash
export SSL_KEYFILE=/home/wlsdud5035/openclaw/certs/localhost-key.pem
export SSL_CERTFILE=/home/wlsdud5035/openclaw/certs/localhost-cert.pem
../scripts/run_dashboard.sh
```

Vite 개발 서버 HTTPS:

```bash
export VITE_SSL_KEY=/home/wlsdud5035/openclaw/certs/localhost-key.pem
export VITE_SSL_CERT=/home/wlsdud5035/openclaw/certs/localhost-cert.pem
npm run dev
```

이 상태면 개발 URL은 `https://localhost:3000`, API 프록시는 `https://localhost:8080`을 사용해.

## 빌드 & 배포

```bash
npm run build    # dist/ 생성
# FastAPI가 dist/ 를 정적 파일로 서빙 (run_dashboard.sh)
```

## API 프록시

`vite.config.js` — 개발 시 `/api/*` → `http://localhost:8080` 프록시.
