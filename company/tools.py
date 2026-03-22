"""company/tools.py — 에이전트 공용 파일/코드/시스템 도구 (@beta_tool).

보안:
  - 모든 파일 접근은 WORKSPACE 루트 이하로 제한
  - bash 명령은 위험 명령 차단 리스트 적용
"""
from __future__ import annotations

import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_WS = Path("/home/wlsdud5035/.openclaw/workspace").resolve()

try:
    _WS_STR = str(_WS)
    if _WS_STR not in sys.path:
        sys.path.insert(0, _WS_STR)
    from anthropic import beta_tool
    from common.logger import get_logger as _get_logger
    log = _get_logger("company.tools")
except ImportError:
    import logging
    log = logging.getLogger("company.tools")

    def beta_tool(fn):
        return fn


# ── 보안 헬퍼 ──────────────────────────────────────────────────────────────
def _safe_path(path: str) -> Path:
    """경로를 WORKSPACE 내부로 제한. 외부 경로면 ValueError."""
    p = (_WS / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    # startswith(str(_WS)) 만으로는 "/workspace_evil" 같은 경로가 통과됨 → "/" 추가
    if p != _WS and not str(p).startswith(str(_WS) + "/"):
        raise ValueError(f"보안: WORKSPACE 외부 경로 접근 차단 ({p})")
    return p


_BASH_BLOCKLIST = re.compile(
    r"(rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r"          # rm -rf 및 변형
    r"|\bsudo\b|\bsu\b"                                       # 권한 상승
    r"|\bchmod\s+[0-7]{3,4}\s+/"                             # 루트 권한 변경
    r"|\bchown\s+root"                                        # root 소유권 변경
    r"|\bdd\s+if="                                            # 디스크 덮어쓰기
    r"|\bmkfs\b|\bfdisk\b|\bparted\b"                        # 파티션/포맷
    r"|\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b"        # 시스템 종료
    r"|\bcurl\s+.+\|\s*(ba)?sh|\bwget\s+.+\|\s*(ba)?sh"     # 원격 실행
    r"|\beval\b"                                              # eval 실행 (강화)
    r"|\$\([^)]*rm\b|\`[^`]*rm\b"                            # 명령치환으로 rm
    r"|\b/bin/rm\b|\b/usr/bin/rm\b"                          # 전체 경로 rm
    r"|\b:\s*\(\s*\)\s*\{.*:\|:&\}"                          # 포크 폭탄
    r"|\bkill\s+-9\s+1\b|\bkillall\b"                        # 프로세스 강제 종료
    r"|\b(python|python3|bash|sh)\s+-c\s+[\"'].*rm\b"        # 인터프리터 경유 rm
    r"|/etc/passwd|/etc/shadow|/etc/crontab|/etc/sudoers"    # 시스템 파일 접근
    r"|\biptables\b|\bnftables\b|\bufw\b"                    # 방화벽 변경
    # ── 우회 기법 차단 ────────────────────────────────────────────────────
    r"|base64\s+-d\s*\|"                                      # base64 디코드→파이프
    r"|\$\{IFS\}"                                             # IFS 치환 공격
    r"|\$'\\x[0-9a-f]{2}"                                    # 헥스 인코딩
    r"|\bexec\s+[0-9]*>"                                      # fd 리다이렉트
    r"|\bsource\b|\b\.\s+/"                                   # 외부 스크립트 로드
    r"|\bnc\s+.*-e\b|\bncat\b.*-e\b"                         # 리버스쉘
    r"|\bcrontab\s+-"                                          # crontab 수정
    r"|\bat\s+now\b|\bbatch\b"                               # 지연 실행
    r"|>\s*/etc/|>\s*/bin/|>\s*/usr/"                          # 시스템 디렉토리 쓰기
    r"|\benv\b|\bprintenv\b|\bset\b"                           # 환경변수 노출
    r"|\bperl\b|\bruby\b"                                      # 대체 인터프리터
    r"|/proc/self/environ",                                    # 프로세스 환경변수 접근
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════
# 파일 도구
# ══════════════════════════════════════════════════════════════════════════

@beta_tool
def read_file(path: str) -> str:
    """파일 내용을 읽어 반환합니다.

    Args:
        path: WORKSPACE 기준 상대 경로 또는 절대 경로 (예: 'btc/btc_trading_agent.py')
    """
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"[오류] 파일 없음: {path}"
        size = p.stat().st_size
        if size > 300_000:
            return f"[경고] 파일이 너무 큼 ({size//1024}KB). list_files 또는 grep_files 사용 권장."
        return p.read_text(encoding="utf-8", errors="replace")
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def write_file(path: str, content: str) -> str:
    """파일을 생성하거나 전체 내용을 덮어씁니다.

    Args:
        path:    WORKSPACE 기준 경로 (예: 'dashboard/src/components/NewWidget.jsx')
        content: 파일에 쓸 내용
    """
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        log.info(f"write_file: {path} ({len(content)}자)")
        return f"✓ 파일 저장 완료: {path} ({len(content.splitlines())}줄)"
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def edit_file(path: str, old_string: str, new_string: str) -> str:
    """파일에서 특정 문자열을 정확히 찾아 교체합니다.

    Args:
        path:       WORKSPACE 기준 경로
        old_string: 교체할 기존 문자열 (정확히 일치해야 함)
        new_string: 교체 후 새 문자열
    """
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"[오류] 파일 없음: {path}"
        original = p.read_text(encoding="utf-8")
        if old_string not in original:
            return f"[오류] 문자열을 찾을 수 없습니다:\n{old_string[:200]}..."
        count = original.count(old_string)
        if count > 1:
            return f"[오류] '{old_string[:50]}...' 이 {count}곳에 있습니다. 더 구체적인 old_string을 사용하세요."
        updated = original.replace(old_string, new_string, 1)
        p.write_text(updated, encoding="utf-8")
        log.info(f"edit_file: {path}")
        return f"✓ 수정 완료: {path}"
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def list_files(directory: str = ".", pattern: str = "**/*.py") -> str:
    """디렉토리에서 파일 목록을 반환합니다.

    Args:
        directory: WORKSPACE 기준 디렉토리 (기본: 워크스페이스 루트)
        pattern:   glob 패턴 (기본: '**/*.py')
    """
    try:
        base = _safe_path(directory)
        matches = sorted(base.glob(pattern))
        # .venv, __pycache__, .git 제외
        filtered = [
            str(m.relative_to(_WS))
            for m in matches
            if not any(x in m.parts for x in (".venv", "__pycache__", ".git", "node_modules"))
        ]
        if not filtered:
            return f"(파일 없음: {directory}/{pattern})"
        return "\n".join(filtered[:200])
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def grep_files(pattern: str, path: str = ".", file_glob: str = "*.py") -> str:
    """파일 내용에서 패턴을 검색합니다.

    Args:
        pattern:   검색할 정규식 또는 문자열
        path:      검색 시작 디렉토리 (WORKSPACE 기준)
        file_glob: 검색 대상 파일 확장자 (예: '*.py', '*.jsx', '*.ts')
    """
    try:
        base = _safe_path(path)
        result = subprocess.run(
            ["grep", "-rn", "--include", file_glob, pattern, str(base)],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        if not output:
            return f"(결과 없음: '{pattern}' in {path}/{file_glob})"
        # WORKSPACE 경로 단축 + 최대 50줄
        lines = output.split("\n")[:50]
        shortened = [l.replace(str(_WS) + "/", "") for l in lines]
        suffix = f"\n... (+{len(output.split(chr(10))) - 50}줄)" if len(output.split("\n")) > 50 else ""
        return "\n".join(shortened) + suffix
    except ValueError as e:
        return f"[보안 오류] {e}"
    except subprocess.TimeoutExpired:
        return "[오류] grep 타임아웃"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def get_directory_tree(directory: str = ".", max_depth: int = 3) -> str:
    """디렉토리 구조를 트리 형태로 반환합니다.

    Args:
        directory: WORKSPACE 기준 경로
        max_depth: 표시할 최대 깊이 (기본 3)
    """
    try:
        base = _safe_path(directory)
        skip = {".venv", "__pycache__", ".git", "node_modules", ".next", "dist", "build"}
        lines = [str(base.relative_to(_WS)) + "/"]

        def _tree(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                children = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            children = [c for c in children if c.name not in skip]
            for i, child in enumerate(children):
                connector = "└── " if i == len(children) - 1 else "├── "
                lines.append(prefix + connector + child.name + ("/" if child.is_dir() else ""))
                if child.is_dir():
                    ext = "    " if i == len(children) - 1 else "│   "
                    _tree(child, prefix + ext, depth + 1)

        _tree(base, "", 1)
        return "\n".join(lines[:300])
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


# ══════════════════════════════════════════════════════════════════════════
# 실행 도구
# ══════════════════════════════════════════════════════════════════════════

@beta_tool
def run_bash(command: str, cwd: str = ".") -> str:
    """WORKSPACE 내에서 bash 명령을 실행합니다 (읽기 전용 권장).

    Args:
        command: 실행할 bash 명령 (위험 명령 자동 차단)
        cwd:     작업 디렉토리 (WORKSPACE 기준, 기본: 루트)
    """
    try:
        if _BASH_BLOCKLIST.search(command):
            return f"[보안 차단] 위험 명령어가 포함되어 있습니다: {command[:100]}"
        work_dir = _safe_path(cwd)
        # shell=True 대신 bash 명시 호출로 injection surface 최소화
        # --norc/--noprofile: 사용자 프로파일 로드 차단
        # 시크릿 키(API key/token/secret 패턴)는 자식 프로세스에 전달하지 않음
        _SECRET_PAT = re.compile(r"(key|token|secret|password|passwd|pwd|credential)", re.IGNORECASE)
        env = {
            k: v for k, v in os.environ.items() if not _SECRET_PAT.search(k)
        }
        env.update({
            "PYTHONPATH": str(_WS),
            "BASH_ENV": "/dev/null",   # non-interactive bash env 파일 로드 차단
        })
        result = subprocess.run(
            ["bash", "--norc", "--noprofile", "-c", command],
            capture_output=True, text=True,
            timeout=60, cwd=str(work_dir), env=env
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(out[:3000])
        if err:
            parts.append(f"[stderr]\n{err[:1000]}")
        if result.returncode != 0:
            parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts) if parts else "(출력 없음)"
    except ValueError as e:
        return f"[보안 오류] {e}"
    except subprocess.TimeoutExpired:
        return "[오류] 명령 타임아웃 (60초)"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def run_python_check(path: str) -> str:
    """Python 파일의 문법을 검사합니다.

    Args:
        path: 검사할 .py 파일 경로 (WORKSPACE 기준)
    """
    try:
        p = _safe_path(path)
        result = subprocess.run(
            [str(_WS / ".venv/bin/python3"), "-m", "py_compile", str(p)],
            capture_output=True, text=True, timeout=30, cwd=str(_WS)
        )
        if result.returncode == 0:
            return f"✓ 문법 OK: {path}"
        return f"✗ 문법 오류:\n{result.stderr.strip()}"
    except ValueError as e:
        return f"[보안 오류] {e}"
    except Exception as e:
        return f"[오류] {e}"


@beta_tool
def get_git_diff(path: str = ".") -> str:
    """현재 git 변경사항(staged + unstaged)을 반환합니다.

    Args:
        path: 비교 범위 (기본: 전체 워크스페이스)
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--stat"],
            capture_output=True, text=True, timeout=15, cwd=str(_WS)
        )
        return result.stdout.strip() or "(변경사항 없음)"
    except Exception as e:
        return f"[오류] {e}"


# ══════════════════════════════════════════════════════════════════════════
# 코드베이스 컨텍스트 도구
# ══════════════════════════════════════════════════════════════════════════

@beta_tool
def get_codebase_overview() -> str:
    """OpenClaw 프로젝트 구조와 핵심 모듈 요약을 반환합니다."""
    overview = {
        "project": "OpenClaw Trading System v5.0",
        "workspace": str(_WS),
        "markets": ["BTC (Upbit)", "KR Stocks (Kiwoom)", "US Stocks (Alpaca/yfinance)"],
        "stack": {
            "backend": "Python 3.11, FastAPI, uvicorn",
            "database": "Supabase (PostgreSQL)",
            "ai": "OpenAI GPT-4o-mini, Anthropic Claude (haiku/sonnet/opus)",
            "frontend": "React + Vite + Tailwind + Recharts",
            "infra": "cron + shell scripts",
        },
        "key_dirs": {
            "btc/":       "BTC 트레이딩 에이전트, 라우터, 시그널",
            "stocks/":    "KR/US 주식 에이전트, 키움 클라이언트, ML 모델",
            "common/":    "공통 유틸 (config, logger, telegram, sheets)",
            "agents/":    "AI 전략 에이전트 (뉴스분석, 레짐분류, 에이전트팀)",
            "quant/":     "백테스트, 팩터, 포트폴리오, 리스크",
            "execution/": "주문 실행 (TWAP, VWAP, 스마트라우팅)",
            "dashboard/": "React 대시보드 (src/pages, src/components, src/api.js)",
            "company/":   "AI 소프트웨어 회사 에이전트",
            "brain/":     "AI 분석 결과 저장",
        },
        "entry_points": {
            "btc":      "python btc/btc_trading_agent.py",
            "kr":       "python stocks/kr_trading_agent.py",
            "us":       "python stocks/us_trading_agent.py",
            "dashboard":"python scripts/dashboard_runner.py",
            "agent_team":"python -m agents.trading_agent_team --market btc",
            "company":  "python -m company --task '요청 내용'",
        },
    }
    return json.dumps(overview, ensure_ascii=False, indent=2)


# ── 도구 그룹 (전문가별 도구 세트) ────────────────────────────────────────
FILE_TOOLS = [read_file, write_file, edit_file, list_files, grep_files,
              get_directory_tree, run_python_check, get_codebase_overview]

CODE_TOOLS = FILE_TOOLS + [run_bash, get_git_diff]

READ_ONLY_TOOLS = [read_file, list_files, grep_files, get_directory_tree,
                   get_codebase_overview, run_python_check]
