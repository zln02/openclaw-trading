#!/bin/bash
# workspace 스택 → openclaw 스택 마이그레이션
set -e

echo "=== 1. Grafana 볼륨 데이터 백업 ==="
docker cp workspace-grafana-1:/var/lib/grafana /tmp/grafana_backup 2>/dev/null || echo "백업 스킵"

echo "=== 2. workspace 스택 중지 ==="
cd /home/wlsdud5035/.openclaw/workspace
docker compose down

echo "=== 3. openclaw 통합 스택 시작 ==="
cd /home/wlsdud5035/quant-agent
docker compose up -d

echo "=== 4. 상태 확인 ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

echo "=== 5. 디스크 정리 ==="
docker system prune -f

echo "마이그레이션 완료!"
