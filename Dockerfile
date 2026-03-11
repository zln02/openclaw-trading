FROM node:20-bookworm-slim AS dashboard-builder

WORKDIR /dashboard

COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build


FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY common/ common/
COPY btc/ btc/
COPY stocks/ stocks/
COPY agents/ agents/
COPY quant/ quant/
COPY memory/ memory/
COPY scripts/ scripts/
COPY --from=dashboard-builder /dashboard/dist/ dashboard/dist/

# 환경변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 대시보드 포트
EXPOSE 8080

# 기본 진입점: 대시보드
CMD ["python", "btc/btc_dashboard.py"]
