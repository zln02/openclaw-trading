FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 비root 사용자 생성
RUN useradd -m -u 1000 openclaw && chown -R openclaw:openclaw /app
USER openclaw

# 소스 코드 복사
COPY --chown=openclaw:openclaw common/ common/
COPY --chown=openclaw:openclaw api/ api/
COPY --chown=openclaw:openclaw btc/ btc/
COPY --chown=openclaw:openclaw stocks/ stocks/
COPY --chown=openclaw:openclaw agents/ agents/
COPY --chown=openclaw:openclaw quant/ quant/
COPY --chown=openclaw:openclaw execution/ execution/
COPY --chown=openclaw:openclaw scripts/ scripts/
COPY --chown=openclaw:openclaw dashboard/dist/ dashboard/dist/

# 환경변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 대시보드 포트
EXPOSE 8080

# 기본 진입점: 대시보드
CMD ["python", "-m", "uvicorn", "btc.btc_dashboard:app", "--host", "0.0.0.0", "--port", "8080"]
