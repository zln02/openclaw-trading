"""
사용자가 '학습해줘' 등으로 승인했을 때 호출.
pending_approvals의 최신 항목을 learned_content로 이동.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agency_memory import apply_pending_to_learned

if __name__ == "__main__":
    pending_id = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    result = apply_pending_to_learned(pending_id)
    print(result.get("message", result.get("error", result)))
