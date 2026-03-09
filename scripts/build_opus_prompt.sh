#!/bin/bash
# build_opus_prompt.sh
# Opus 컨설팅 프롬프트 최종 조립 + 실행
# 사용법: bash build_opus_prompt.sh

set -e

echo "📦 Supabase 데이터 추출 중..."
python3 export_for_opus.py > /tmp/supabase_snapshot.md

echo "📝 프롬프트 조립 중..."
cat openclaw_opus_master_prompt.md \
    /tmp/supabase_snapshot.md \
    >> /tmp/opus_final_prompt.md

# 일일 자동 개선 플랜도 포함
cat >> /tmp/opus_final_prompt.md << 'EOF'

---

### 10. 🤖 Claude 자동 개선 시스템 설계

아래 구조로 "매일 새벽 Claude Sonnet이 자동으로 시스템을 개선하는 파이프라인"을 설계해줘:

```
cron (매일 새벽 1시)
  → export_for_opus.py (Supabase 성과 데이터 추출)
  → tasks_today.md 자동 생성 (어제 성과 기반)
  → claude --dangerously-skip-permissions 실행
  → git add + commit (자동 버전 관리)
  → Telegram 알림 (개선 완료 or 실패)
```

요청사항:
1. tasks_today.md 자동 생성 로직 (어떤 성과 지표를 보고 어떤 작업을 만들지)
2. Claude가 절대 건드리면 안 되는 파일 목록 (실거래 보호)
3. Pro 플랜 한도 안에서 효율적으로 작업하는 프롬프트 구조
4. 실패 시 롤백 전략 (git revert 자동화)
5. 이 구조 전체 bash 스크립트 스펙

EOF

echo "🚀 Opus 실행 중... (시간이 걸릴 수 있어요)"
claude --model claude-opus-4-5-20251101 \
  --dangerously-skip-permissions \
  -p "$(cat /tmp/opus_final_prompt.md)" \
  > opus_analysis_$(date +%Y%m%d).md

echo "✅ 완료! opus_analysis_$(date +%Y%m%d).md 확인하세요"
echo ""
echo "📌 다음 단계:"
echo "  cat opus_analysis_$(date +%Y%m%d).md"
echo "  → P1 항목을 Sonnet에게 구현 요청"
