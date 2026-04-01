---
name: auth-manager
description: OpenClaw 환경에서 외부 서비스 API 키와 인증 정보를 한 번에 관리하는 가이드
version: 2.0.0
author: Dante Labs (OpenClaw용)
tags:
  - auth
  - api-key
  - credentials
  - common
---

# Auth Manager (OpenClaw)

OpenClaw 에이전트들이 사용하는 **API 키 / 시크릿 / 토큰**을  
어디에, 어떤 이름으로 넣어야 하는지 정리한 레퍼런스 스킬입니다.

- 공통 키: `~/.openclaw/.env`
- Gateway 전용 키: `~/.openclaw/openclaw.json` 의 `env`
- 스킬 전용 키: 각 스킬 디렉터리의 `.env`

을 기준으로 봅니다.

---

## 1. OpenClaw에서 환경변수가 로드되는 순서

Gateway 프로세스는 다음 순서로 환경변수를 채웁니다 (위가 더 우선):

1. **프로세스 환경변수** (`docker-compose.yml` 의 `environment` 등)
2. **현재 작업 디렉터리의 `.env`** (일반 프로젝트용, Gateway에는 잘 안 씀)
3. **글로벌 `.env`**: `~/.openclaw/.env`
4. **`openclaw.json` 의 `env` 블록**

실제로 사람이 관리하기 좋은 포인트는:

- **전역 공통 키** → `~/.openclaw/.env`
- **Gateway 전용/민감 키** → `~/.openclaw/openclaw.json` 의 `env`

---

## 2. 서비스별 권장 환경변수 이름

| 서비스        | 용도               | 환경변수 예시                                     |
|--------------|--------------------|---------------------------------------------------|
| OpenAI       | GPT API            | `OPENAI_API_KEY`                                  |
| Anthropic    | Claude API         | `ANTHROPIC_API_KEY`                               |
| OpenRouter   | LLM 라우팅         | `OPENROUTER_API_KEY`                              |
| Brave        | 웹 검색            | `BRAVE_API_KEY`                                   |
| Supabase     | Postgres (DB)      | `SUPABASE_URL`, `SUPABASE_DB_URL`                |
| OpenDART     | 전자공시 API       | `DART_API_KEY`                                    |
| Kiwoom REST  | 증권 API           | `KIWOOM_REST_API_KEY`, `KIWOOM_REST_API_SECRET`   |
| Kie.ai       | 이미지/비디오 생성 | `KIEAI_API_KEY`, `KIE_AI_API_KEY`                 |

각 스킬의 `SKILL.md` 에도 어떤 키를 기대하는지 나와 있으니,  
**이 표 + 각 스킬 문서**를 같이 보면 됩니다.

---

## 3. 전역 `.env` (`~/.openclaw/.env`) 하나로 정리하기

### 위치

- 호스트: `~/.openclaw/.env`
- 컨테이너: `/home/wlsdud5035/.openclaw/.env` (호스트에서 마운트됨)

### 예시

```bash
# LLM / 검색
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
BRAVE_API_KEY=BSA0...

# Supabase (Postgres)
SUPABASE_URL="https://tgbwciiwxggvvnwbhrkx.supabase.co"
SUPABASE_DB_URL="postgresql://postgres.tgbwciiwxggvvnwbhrkx:비밀번호@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

# OpenDART
DART_API_KEY=your_dart_api_key_here

# Kiwoom REST
KIWOOM_REST_API_KEY=your_kiwoom_api_key
KIWOOM_REST_API_SECRET=your_kiwoom_secret
```

이렇게 해두면 대부분의 스킬/exec 가 `os.getenv(...)` / `$ENV_VAR` 로 바로 사용할 수 있습니다.

---

## 4. `openclaw.json` 의 `env` 블록 (Gateway 전용 설정)

더 세밀하게 Gateway 설정을 관리하고 싶으면 `openclaw.json` 의 `env` 를 씁니다.

### 위치

- 호스트: `~/.openclaw/openclaw.json`
- 컨테이너: `/home/wlsdud5035/.openclaw/openclaw.json`

### 예시 (일부)

```json5
{
  "env": {
    "shellEnv": {
      "enabled": true,
      "timeoutMs": 15000
    },
    "SUPABASE_URL": "https://tgbwciiwxggvvnwbhrkx.supabase.co",
    "SUPABASE_SECRET_KEY": "",
    "SUPABASE_DB_URL": "postgresql://postgres.tgbwciiwxggvvnwbhrkx:비밀번호@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
  }
}
```

여기에 있는 값들은 `process.env` 로 들어가서:

```ts
process.env.SUPABASE_DB_URL
```

처럼 바로 사용할 수 있습니다.

---

## 5. 스킬 전용 `.env` 가 필요한 경우

일부 스킬은 자기 디렉터리에 `.env` 를 둘 수 있습니다. 예:

```bash
~/.openclaw/workspace/skills/opendart-api/.env
DART_API_KEY=your_dart_api_key_here

~/.openclaw/workspace/skills/kiwoom-api/.env
KIWOOM_REST_API_KEY=your_kiwoom_api_key
KIWOOM_REST_API_SECRET=your_kiwoom_secret
```

이 패턴은:

- 프로젝트마다 다른 키를 쓰고 싶을 때
- 특정 스킬만 별도 키를 쓰고 싶을 때

에 유용하지만, **키가 여러 군데 흩어지면 관리가 어려워지므로**,  
가능하면 공통 키는 전부 `~/.openclaw/.env` 로 모으는 걸 추천합니다.

---

## 6. 코드/exec 쪽에서 키 읽는 패턴

대부분의 스킬/코드는 아래 형태를 씁니다.

```python
import os

openai_key = os.getenv("OPENAI_API_KEY")
dart_key = os.getenv("DART_API_KEY")
supabase_db_url = os.getenv("SUPABASE_DB_URL")
```

`exec` 도구도 마찬가지로:

```bash
psql "$SUPABASE_DB_URL" -c "SELECT version();"
```

처럼 **환경변수 이름만 맞으면 어디에 두었는지는 신경 쓰지 않습니다.**  
이 스킬은 “이름과 위치”를 통일하는 용도입니다.

---

## 7. 보안 가이드라인 (OpenClaw 기준)

1. **Git에 커밋 금지**
   ```bash
   # ~/.openclaw/.gitignore 에 추가 권장
   .env
   openclaw.json
   *.env
   ```
2. **파일 권한**
   ```bash
   chmod 600 ~/.openclaw/.env
   chmod 600 ~/.openclaw/openclaw.json
   ```
3. **공유 금지**
   - API 키/비밀번호를 채팅, 캡처, 메모 등에 그대로 붙여넣지 않기
4. **백업**
   ```bash
   cp -r ~/.openclaw ~/.openclaw.backup
   ```

---

## 8. 빠르게 상태 점검하는 명령어

```bash
# 호스트에서 전역 .env 확인
cat ~/.openclaw/.env

# 컨테이너 안에서 환경변수 확인
docker exec openclaw-openclaw-gateway-1 env | grep -E 'OPENAI|ANTHROPIC|OPENROUTER|BRAVE|SUPABASE|DART|KIWOOM'

# 컨테이너 안에서 openclaw.json env 블록 확인
docker exec openclaw-openclaw-gateway-1 \
  cat /home/wlsdud5035/.openclaw/openclaw.json | jq '.env'
```

이 스킬은 **“키를 어디에 어떻게 넣을지”에 대한 깔끔한 기준서**입니다.  
실제 값은 항상 `.env` / `openclaw.json` / CI 시크릿 등에만 넣고,  
스킬 파일에는 절대 넣지 마세요.

## Overview

DanteLabs Agentic School 플러그인들은 다양한 외부 서비스와 연동됩니다. 이 스킬은 API 키와 인증 정보를 안전하고 일관성 있게 관리하는 방법을 제공합니다.

## 지원 서비스

| 서비스 | 용도 | 환경변수 | 발급 URL |
| --- | --- | --- | --- |
| Kie.ai | 이미지/비디오 생성 | `KIEAI_API_KEY`, `KIE_AI_API_KEY` | https://kie.ai |
| OpenRouter | LLM API 라우팅 | `OPENROUTER_API_KEY` | https://openrouter.ai |
| OpenAI | GPT API | `OPENAI_API_KEY` | https://platform.openai.com |
| Anthropic | Claude API | `ANTHROPIC_API_KEY` | https://console.anthropic.com |

## 인증 관리 방법

### 방법 1: 중앙화된 인증 (권장)

`~/.claude/auth/` 디렉토리에 서비스별 환경 파일을 생성합니다.

```
~/.claude/auth/
├── kie-ai.env          # Kie.ai API 키
├── openrouter.env      # OpenRouter API 키
├── openai.env          # OpenAI API 키
└── anthropic.env       # Anthropic API 키
```

#### Kie.ai 설정

```bash
# ~/.claude/auth/kie-ai.env
KIEAI_API_KEY=your_api_key_here
KIE_AI_API_KEY=your_api_key_here
```

#### OpenRouter 설정

```bash
# ~/.claude/auth/openrouter.env
OPENROUTER_API_KEY=your_api_key_here
```

### 방법 2: 스킬 디렉토리별 .env

각 스킬 디렉토리에 개별 `.env` 파일을 생성합니다.

```bash
# ~/.claude/skills/kie-image-generator/.env
KIEAI_API_KEY=your_api_key_here

# ~/.claude/skills/kie-video-generator/.env
KIE_AI_API_KEY=your_api_key_here
```

### 방법 3: 시스템 환경변수

셸 프로파일에 직접 설정합니다.

```bash
# ~/.zshrc 또는 ~/.bashrc
export KIEAI_API_KEY=your_api_key_here
export KIE_AI_API_KEY=your_api_key_here
export OPENROUTER_API_KEY=your_api_key_here
```

## 환경 파일 로드

### 스크립트에서 로드

```python
from dotenv import load_dotenv
import os

# 중앙화된 인증 파일 로드
load_dotenv(os.path.expanduser("~/.claude/auth/kie-ai.env"))

# 또는 스킬 디렉토리의 .env 로드
load_dotenv()

api_key = os.getenv("KIEAI_API_KEY")
```

### 셸에서 로드

```bash
# 단일 서비스
source ~/.claude/auth/kie-ai.env

# 모든 인증 파일 로드
for f in ~/.claude/auth/*.env; do source "$f"; done
```

## 보안 가이드라인

### 권장 사항

1. **Git 제외**: `.env` 파일을 `.gitignore`에 추가
   ```
   # .gitignore
   .env
   *.env
   ```

2. **파일 권한**: 인증 파일은 본인만 읽을 수 있도록 설정
   ```bash
   chmod 600 ~/.claude/auth/*.env
   ```

3. **백업**: 인증 파일은 안전한 곳에 백업
   ```bash
   cp -r ~/.claude/auth ~/.claude/auth.backup
   ```

### 금지 사항

- API 키를 코드에 하드코딩하지 마세요
- API 키를 Git에 커밋하지 마세요
- API 키를 공개 채널에 공유하지 마세요
- 스크린샷에 API 키가 노출되지 않도록 주의하세요

## 크레딧/사용량 확인

### Kie.ai 크레딧 확인

```bash
# 이미지 생성 크레딧
python ~/.claude/skills/kie-image-generator/scripts/generate_image.py --credits

# 비디오 생성 크레딧
python ~/.claude/skills/kie-video-generator/scripts/generate_video.py --credits
```

### 사용량 모니터링

```bash
# 생성 후 출력 예시
💰 Credits used: 45.0 ($0.23)
   Remaining: 837.5 credits ($4.19)
```

## 문제 해결

### API 키 오류

| 오류 코드 | 원인 | 해결 방법 |
| --- | --- | --- |
| 401 | 잘못된 API 키 | API 키 재확인 |
| 402 | 크레딧 부족 | 크레딧 충전 |
| 403 | 권한 없음 | API 키 권한 확인 |

### 환경변수 로드 확인

```bash
# 환경변수 설정 확인
echo $KIEAI_API_KEY

# .env 파일 내용 확인 (주의: 터미널 기록에 남음)
cat ~/.claude/auth/kie-ai.env
```

## auth-loader 스킬 연동

`auth-loader` 스킬이 설치되어 있다면, 대화형으로 인증 정보를 관리할 수 있습니다.

```bash
# 서비스 목록 확인
/auth-loader list

# 새 서비스 추가
/auth-loader add kie-ai

# 인증 정보 검증
/auth-loader validate kie-ai
```

## 프로젝트 디렉토리 구조

모든 에이전트와 스킬은 산출물을 아래 표준 디렉토리 구조에 저장합니다.

```
{project}/
├── assets/           # 이미지, 비디오 등 정적 에셋
│   ├── images/       # AI 생성 이미지
│   └── videos/       # AI 생성 비디오
├── reports/          # 마케팅 문서 및 분석 리포트
│   ├── brand/        # 브랜드 분석 문서
│   ├── persona/      # 페르소나 카드
│   ├── strategy/     # 전략 문서
│   └── content/      # 카피, 스크립트
├── scripts/          # 실행 스크립트
│   └── automation/   # 자동화 스크립트
└── tmp/              # 임시 파일 (작업 완료 후 삭제 가능)
```

### 디렉토리 설명

| 디렉토리 | 용도 | 예시 |
| --- | --- | --- |
| `assets/` | 이미지, 비디오 등 정적 에셋 | `product-hero.png`, `brand-video.mp4` |
| `reports/` | 마케팅 문서 및 분석 결과 | `brand-strategy-brief.md`, `persona-card.md` |
| `scripts/` | 자동화 및 유틸리티 스크립트 | `generate_thumbnails.py` |
| `tmp/` | 임시 파일 (중간 결과물) | `draft-v1.md`, `temp-image.png` |

### 디렉토리 자동 생성

에이전트가 파일 생성 시, 해당 디렉토리가 없으면 자동으로 생성합니다.

```bash
# 필요 시 디렉토리 생성
mkdir -p assets/images assets/videos
mkdir -p reports/brand reports/persona reports/strategy reports/content
mkdir -p scripts/automation
mkdir -p tmp
```

## 관련 스킬

- `kie-image-generator`: AI 이미지 생성 (Kie.ai API 사용)
- `kie-video-generator`: AI 비디오 생성 (Kie.ai API 사용)
- `auth-loader`: 대화형 인증 관리 도구
