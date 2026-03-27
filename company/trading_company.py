"""company/trading_company.py — OpenClaw AI 소프트웨어 회사.

CEO가 사용자 요청을 받아 각 전문가 에이전트(CTO, Backend, Frontend,
Quant, DevOps, QA)에게 위임하고, 실제 코드베이스를 수정·개선합니다.

실행:
  python -m company --task "대시보드에 BTC 수익률 차트 추가해줘"
  python -m company --task "stock_api.py 버그 찾아서 고쳐줘" --dry-run
  python -m company --role backend --task "새 API 엔드포인트 추가"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_WS = str(Path(__file__).resolve().parents[1])
if _WS not in sys.path:
    sys.path.insert(0, _WS)

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("company")

import anthropic
from anthropic import beta_tool

from company.tools import (
    CODE_TOOLS, FILE_TOOLS, READ_ONLY_TOOLS,
    read_file, list_files, get_codebase_overview, get_directory_tree,
)
from company import prompts

# ── 모델 ──────────────────────────────────────────────────────────────────
MODEL_CEO   = "claude-opus-4-6"
MODEL_CTO   = "claude-opus-4-6"
MODEL_SR    = "claude-sonnet-4-6"   # 시니어 엔지니어
MODEL_JR    = "claude-haiku-4-5-20251001"  # DevOps, QA

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


# ══════════════════════════════════════════════════════════════════════════
# 전문가 에이전트 실행기
# ══════════════════════════════════════════════════════════════════════════

def _run_specialist(
    role: str,
    system_prompt: str,
    task: str,
    tools: list,
    model: str,
    max_tokens: int = 8192,
    stream_output: bool = True,
) -> str:
    """전문가 에이전트를 tool_runner로 실행하고 최종 텍스트를 반환."""
    log.info(f"[{role}] 작업 시작: {task[:80]}...")
    start = time.time()

    try:
        runner = _client.beta.messages.tool_runner(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=[{"role": "user", "content": task}],
        )
        result_text = ""
        tool_calls: list[str] = []

        for message in runner:
            for block in message.content:
                if block.type == "text":
                    result_text = block.text
                    if stream_output:
                        # 실시간 출력 (prefix 없이)
                        pass
                elif block.type == "tool_use":
                    tool_calls.append(block.name)
                    if stream_output:
                        log.info(f"  ⚙ [{role}] {block.name}({str(block.input)[:60]}...)")

        elapsed = time.time() - start
        log.info(f"[{role}] 완료: {len(result_text)}자, 도구 {len(tool_calls)}회, {elapsed:.1f}s")
        return result_text or "(결과 없음)"

    except Exception as exc:
        log.error(f"[{role}] 오류: {exc}")
        return f"[{role} 오류] {exc}"


# ── 각 전문가 @beta_tool 래퍼 (CEO가 도구로 호출) ─────────────────────────

@beta_tool
def assign_to_cto(task: str) -> str:
    """기술 아키텍처 설계·검토를 CTO에게 위임합니다.

    Args:
        task: CTO에게 전달할 구체적인 기술 과제
    """
    log.info(f"\n📐 [CTO] {task[:100]}")
    return _run_specialist("CTO", prompts.CTO, task, READ_ONLY_TOOLS + [get_codebase_overview], MODEL_CTO)


@beta_tool
def assign_to_backend(task: str) -> str:
    """Python/FastAPI 백엔드 개발을 Backend Engineer에게 위임합니다.

    Args:
        task: 백엔드 개발·수정 태스크 (구체적인 파일명, 함수명 포함 권장)
    """
    log.info(f"\n⚙️  [Backend] {task[:100]}")
    return _run_specialist("Backend", prompts.BACKEND, task, CODE_TOOLS, MODEL_SR)


@beta_tool
def assign_to_frontend(task: str) -> str:
    """React 대시보드 개발을 Frontend Engineer에게 위임합니다.

    Args:
        task: 프론트엔드 개발·수정 태스크
    """
    log.info(f"\n🎨 [Frontend] {task[:100]}")
    return _run_specialist("Frontend", prompts.FRONTEND, task, FILE_TOOLS, MODEL_SR)


@beta_tool
def assign_to_quant(task: str) -> str:
    """트레이딩 전략·ML 모델 개발을 Quant Engineer에게 위임합니다.

    Args:
        task: 퀀트 전략, 지표, 백테스트 관련 태스크
    """
    log.info(f"\n📊 [Quant] {task[:100]}")
    return _run_specialist("Quant", prompts.QUANT, task, CODE_TOOLS, MODEL_SR)


@beta_tool
def assign_to_devops(task: str) -> str:
    """인프라·배포·모니터링을 DevOps Engineer에게 위임합니다.

    Args:
        task: cron, 배포, 환경설정, 모니터링 관련 태스크
    """
    log.info(f"\n🔧 [DevOps] {task[:100]}")
    return _run_specialist("DevOps", prompts.DEVOPS, task, CODE_TOOLS, MODEL_JR)


@beta_tool
def assign_to_qa(task: str) -> str:
    """코드 품질 검토·버그 탐지를 QA Engineer에게 위임합니다.

    Args:
        task: 코드 리뷰, 버그 탐색, 테스트 작성 태스크
    """
    log.info(f"\n🔍 [QA] {task[:100]}")
    return _run_specialist("QA", prompts.QA, task, CODE_TOOLS, MODEL_JR)


@beta_tool
def request_user_approval(question: str) -> str:
    """리스크가 높은 작업 전 사용자에게 확인을 요청합니다.

    Args:
        question: 사용자에게 물어볼 내용 (실거래 영향, 파괴적 변경 등)
    """
    log.info(f"\n⚠️  [CEO→사용자 확인 필요]\n{question}\n")
    try:
        answer = input("계속 진행하시겠습니까? (y/N): ").strip().lower()
        return "approved" if answer in ("y", "yes", "예", "네") else "rejected"
    except EOFError:
        return "rejected"


# ── CEO 전용 컨텍스트 도구 ─────────────────────────────────────────────────

@beta_tool
def read_project_overview() -> str:
    """프로젝트 구조와 핵심 파일 목록을 반환합니다. CEO가 태스크 계획 수립에 사용."""
    return get_codebase_overview()


# ══════════════════════════════════════════════════════════════════════════
# CEO 에이전트 (회사 최상위 오케스트레이터)
# ══════════════════════════════════════════════════════════════════════════

_CEO_TOOLS = [
    assign_to_cto,
    assign_to_backend,
    assign_to_frontend,
    assign_to_quant,
    assign_to_devops,
    assign_to_qa,
    request_user_approval,
    read_project_overview,
    read_file,          # CEO가 직접 파일 확인 가능
    get_directory_tree,
]


def run_ceo(user_request: str, dry_run: bool = False) -> Dict[str, Any]:
    """CEO 에이전트 실행.

    Args:
        user_request: 사용자 요청 (자연어)
        dry_run:      True면 실제 파일 수정 없이 계획만 수립

    Returns:
        {result, plan, delegations, elapsed_sec}
    """
    log.info(f"[CEO] 요청 수신: {user_request[:100]}")
    start = time.time()

    dry_notice = "\n\n[DRY-RUN 모드] 파일 수정 없이 계획만 수립하세요. assign_to_* 도구 호출 시 실제 코드 변경은 하지 않도록 지시하세요." if dry_run else ""

    system = prompts.CEO + dry_notice
    user_msg = (
        f"# 사용자 요청\n{user_request}\n\n"
        f"# 지시\n"
        f"1. read_project_overview()로 프로젝트 구조 파악\n"
        f"2. 요청에 맞는 전문가에게 assign_to_*() 도구로 위임\n"
        f"3. 실거래 코드 수정 시 request_user_approval() 먼저 호출\n"
        f"4. 모든 작업 완료 후 최종 보고서 작성"
    )

    log.info(f"\n{'='*60}")
    log.info("  🏢 OpenClaw AI Company")
    log.info(f"  요청: {user_request[:80]}")
    log.info(f"{'='*60}\n")

    result_text = ""
    plan_extracted = ""

    try:
        # CEO: adaptive thinking + tool_runner (전문가 호출 포함)
        # thinking은 tool_runner와 함께 쓸 수 없으므로 stream 방식 사용
        runner = _client.beta.messages.tool_runner(
            model=MODEL_CEO,
            max_tokens=16384,
            system=system,
            tools=_CEO_TOOLS,
            messages=[{"role": "user", "content": user_msg}],
        )

        delegation_log: list[str] = []
        for message in runner:
            for block in message.content:
                if block.type == "text":
                    result_text = block.text
                    # 실시간 출력
                    if block.text.strip():
                        log.info(f"\n{'─'*60}")
                        log.info(f"📋 [CEO 보고]\n{block.text}")
                elif block.type == "tool_use":
                    delegation_log.append(f"{block.name}: {str(block.input)[:80]}")

        elapsed = time.time() - start
        log.info(f"\n{'='*60}")
        log.info(f"  ✅ 완료 | 소요: {elapsed:.1f}초")
        log.info(f"{'='*60}\n")

        return {
            "result":      result_text,
            "delegations": delegation_log,
            "elapsed_sec": round(elapsed, 1),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        log.error(f"[CEO] 오류: {exc}")
        return {
            "result":      f"CEO 오류: {exc}",
            "delegations": [],
            "elapsed_sec": round(time.time() - start, 1),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════
# TradingCompany — 공개 인터페이스
# ══════════════════════════════════════════════════════════════════════════

class TradingCompany:
    """OpenClaw AI 소프트웨어 회사 메인 클래스.

    사용법:
        company = TradingCompany()
        company.request("대시보드에 BTC 수익률 히트맵 추가해줘")
    """

    ROLES = {
        "ceo":      (run_ceo,        "CEO — 전체 위임"),
        "backend":  (lambda t, **kw: _run_specialist("Backend", prompts.BACKEND, t, CODE_TOOLS, MODEL_SR), "Backend Engineer"),
        "frontend": (lambda t, **kw: _run_specialist("Frontend", prompts.FRONTEND, t, FILE_TOOLS, MODEL_SR), "Frontend Engineer"),
        "quant":    (lambda t, **kw: _run_specialist("Quant", prompts.QUANT, t, CODE_TOOLS, MODEL_SR), "Quant Engineer"),
        "devops":   (lambda t, **kw: _run_specialist("DevOps", prompts.DEVOPS, t, CODE_TOOLS, MODEL_JR), "DevOps Engineer"),
        "qa":       (lambda t, **kw: _run_specialist("QA", prompts.QA, t, CODE_TOOLS, MODEL_JR), "QA Engineer"),
        "cto":      (lambda t, **kw: _run_specialist("CTO", prompts.CTO, t, READ_ONLY_TOOLS, MODEL_CTO), "CTO"),
    }

    def request(self, task: str, role: str = "ceo", dry_run: bool = False) -> Dict[str, Any]:
        """회사에 태스크를 요청합니다.

        Args:
            task:    요청 내용 (자연어)
            role:    담당자 ('ceo' | 'backend' | 'frontend' | 'quant' | 'devops' | 'qa' | 'cto')
            dry_run: True면 계획만 수립, 실제 파일 수정 없음
        """
        role = role.lower()
        if role not in self.ROLES:
            return {"error": f"알 수 없는 역할: {role}. 사용 가능: {list(self.ROLES.keys())}"}

        fn, role_name = self.ROLES[role]
        log.info(f"[TradingCompany] {role_name}에게 요청: {task[:80]}")

        if role == "ceo":
            return run_ceo(task, dry_run=dry_run)
        else:
            result = fn(task)
            return {
                "role":   role_name,
                "result": result,
                "task":   task,
            }

    def list_roles(self) -> None:
        """사용 가능한 역할 목록 출력."""
        log.info("\n📋 OpenClaw AI Company — 팀 구성\n")
        roles_info = {
            "ceo":      f"CEO        ({MODEL_CEO})  — 전체 조율, 위임, 최종 보고",
            "cto":      f"CTO        ({MODEL_CTO})  — 기술 아키텍처 설계·검토",
            "backend":  f"Backend    ({MODEL_SR}) — Python/FastAPI/Supabase 개발",
            "frontend": f"Frontend   ({MODEL_SR}) — React/Vite/Tailwind 대시보드",
            "quant":    f"Quant      ({MODEL_SR}) — 전략/ML/백테스트",
            "devops":   f"DevOps     ({MODEL_JR})    — cron/배포/모니터링",
            "qa":       f"QA         ({MODEL_JR})    — 코드 리뷰/버그 탐지",
        }
        for role, desc in roles_info.items():
            log.info(f"  --role {role:<10} {desc}")
        log.info("")


# ══════════════════════════════════════════════════════════════════════════
# CLI 진입점
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenClaw AI Software Company — Claude 다중 에이전트 팀",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m company --task "대시보드에 BTC 수익률 차트 추가해줘"
  python -m company --task "stock_api.py 버그 찾아서 고쳐줘" --role qa
  python -m company --task "새 리스크 지표 추가해줘" --role quant
  python -m company --task "cron 스케줄 최적화해줘" --role devops --dry-run
  python -m company --list-roles
        """,
    )
    parser.add_argument("--task",       type=str, help="요청할 태스크 (자연어)")
    parser.add_argument("--role",       type=str, default="ceo",
                        choices=["ceo", "cto", "backend", "frontend", "quant", "devops", "qa"],
                        help="담당 역할 (기본: ceo)")
    parser.add_argument("--dry-run",    action="store_true", help="계획만 수립, 실제 파일 수정 없음")
    parser.add_argument("--json",       action="store_true", help="결과를 JSON으로 출력")
    parser.add_argument("--list-roles", action="store_true", help="팀 구성 보기")
    args = parser.parse_args()

    company = TradingCompany()

    if args.list_roles:
        company.list_roles()
        return

    if not args.task:
        parser.print_help()
        return

    result = company.request(args.task, role=args.role, dry_run=args.dry_run)

    if args.json:
        log.info(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
