---
name: deploy-check
description: >
  Docker 서비스 배포 전 사전 점검. '배포 전 체크', 'deploy check' 요청 시 트리거.
  7개 Docker 서비스 상태와 환경변수를 확인한다.
---

## 실행 순서

1. docker compose ps 로 7개 서비스 상태 확인
2. .env 필수 키 존재 여부 확인 (UPBIT, SUPABASE, TELEGRAM, ANTHROPIC)
3. pytest -v --tb=short 실행
4. flake8 린트 통과 여부 확인
5. 모두 통과 시 '✅ 배포 준비 완료' 보고, 실패 시 항목별 정리

## 점검 대상 서비스 (7개)

| 서비스 | 포트 | 헬스체크 |
|--------|------|----------|
| dashboard | 8080 | /health |
| btc-agent | — | 로그 확인 |
| kr-agent | — | 로그 확인 |
| us-agent | — | 로그 확인 |
| telegram-bot | — | 로그 확인 |
| prometheus | 9090 | /-/healthy |
| grafana | 3000 | /api/health |

## 필수 환경변수 점검 목록

```
UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY
SUPABASE_URL, SUPABASE_KEY
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
ANTHROPIC_API_KEY
```

## 실행 명령어 참조

```bash
cd ~/quant-agent

# 1. 서비스 상태
docker compose ps

# 2. 환경변수 확인
grep -E "UPBIT_|SUPABASE_|TELEGRAM_|ANTHROPIC_" .env | cut -d= -f1

# 3. 테스트
pytest -v --tb=short

# 4. 린트
flake8 --max-line-length=120 --ignore=E501,W503,E402 common/ btc/ stocks/ agents/ quant/
```

## 출력 형식

```
## 배포 전 체크 — YYYY-MM-DD HH:MM

| 항목 | 결과 |
|------|------|
| Docker 서비스 (7개) | ✅ 전체 실행 중 / 🚨 N개 중단 |
| 필수 환경변수 | ✅ 전체 존재 / 🚨 [누락 키] 없음 |
| pytest | ✅ XX passed / 🚨 XX failed |
| flake8 | ✅ 통과 / 🚨 XX 오류 |

[✅ 배포 준비 완료 / 🚨 수정 필요 항목 목록]
```
