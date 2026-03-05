#!/usr/bin/env python3
"""
github_helper.py — OpenClaw GitHub 연동 (REST API)

필요: openclaw.json에 GITHUB_TOKEN 설정
  "env": { "GITHUB_TOKEN": "ghp_xxxx" }

사용법:
  prs [--repo OWNER/REPO] [--state open|closed|all]   # PR 목록
  pr --id N [--repo OWNER/REPO]                        # PR 상세
  commits [--repo OWNER/REPO] [--n 10]                 # 최근 커밋
  issues [--repo OWNER/REPO] [--state open|closed]     # 이슈 목록
  repos [--user USER]                                  # 레포 목록
  summary [--repo OWNER/REPO]                          # 레포 요약
  runs [--repo OWNER/REPO]                             # CI/CD 실행 상태
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ pip install requests")
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parent.parent


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    for p in [
        WORKSPACE.parent / "openclaw.json",
        Path("/home/wlsdud5035/.openclaw/openclaw.json"),
        Path("/home/node/.openclaw/openclaw.json"),
    ]:
        if p.exists():
            try:
                d = json.loads(p.read_text())
                return d.get("env", {})
            except Exception:
                pass
    return {}


def _get_token() -> str:
    import os
    cfg = _load_config()
    return cfg.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")


def _default_repo() -> str:
    """git remote origin URL에서 owner/repo 추출"""
    try:
        import subprocess
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(WORKSPACE), stderr=subprocess.DEVNULL
        ).decode().strip()
        # https://github.com/owner/repo.git or git@github.com:owner/repo.git
        if "github.com" in url:
            part = url.split("github.com")[-1].lstrip("/:").removesuffix(".git")
            return part
    except Exception:
        pass
    return ""


# ── API ───────────────────────────────────────────────────────────────────────

class GitHubAPI:
    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get(self, path: str, **params) -> dict | list:
        r = self.s.get(f"{self.BASE}{path}", params=params, timeout=15)
        if r.status_code == 401:
            print("❌ GITHUB_TOKEN 인증 실패 — 토큰 확인 필요")
            sys.exit(1)
        r.raise_for_status()
        return r.json()


def _relative_time(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        days = diff.days
        if days == 0:
            h = diff.seconds // 3600
            return f"{h}시간 전" if h else f"{diff.seconds // 60}분 전"
        if days < 30:
            return f"{days}일 전"
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_prs(api: GitHubAPI, args):
    repo  = args.repo or _default_repo()
    state = args.state or "open"
    prs   = api.get(f"/repos/{repo}/pulls", state=state, per_page=20)

    if not prs:
        print(f"PR 없음 ({state})")
        return

    print(f"\n📋 {repo} — PR 목록 ({state}) {len(prs)}개\n")
    print(f"{'#':>5}  {'상태':<8}  {'생성':<10}  제목")
    print("─" * 65)
    for pr in prs:
        status = "🟢 open" if pr["state"] == "open" else "🔴 closed"
        draft  = " [draft]" if pr.get("draft") else ""
        print(f"#{pr['number']:>4}  {status:<10}  {_relative_time(pr['created_at']):<10}  {pr['title']}{draft}")
        if pr.get("user"):
            print(f"       by @{pr['user']['login']}")


def cmd_pr(api: GitHubAPI, args):
    repo = args.repo or _default_repo()
    pr   = api.get(f"/repos/{repo}/pulls/{args.id}")

    reviews  = api.get(f"/repos/{repo}/pulls/{args.id}/reviews")
    comments = api.get(f"/repos/{repo}/pulls/{args.id}/comments")

    state_icon = "🟢" if pr["state"] == "open" else "🔴"
    print(f"\n{state_icon} PR #{pr['number']}: {pr['title']}")
    print(f"  by @{pr['user']['login']}  ·  {_relative_time(pr['created_at'])}")
    print(f"  {pr['head']['ref']} → {pr['base']['ref']}")
    if pr.get("body"):
        body = pr["body"][:300] + ("..." if len(pr["body"]) > 300 else "")
        print(f"\n  {body}")

    print(f"\n  변경: +{pr['additions']} -{pr['deletions']} 파일 {pr['changed_files']}개")

    review_states = [r["state"] for r in reviews]
    if review_states:
        print(f"  리뷰: {', '.join(set(review_states))}")
    print(f"  댓글: {len(comments)}개")
    print(f"\n  🔗 {pr['html_url']}")


def cmd_commits(api: GitHubAPI, args):
    repo = args.repo or _default_repo()
    n    = args.n or 10
    commits = api.get(f"/repos/{repo}/commits", per_page=n)

    print(f"\n📝 {repo} — 최근 커밋 {len(commits)}개\n")
    for c in commits:
        sha   = c["sha"][:7]
        msg   = c["commit"]["message"].split("\n")[0][:60]
        author = c["commit"]["author"]["name"]
        when  = _relative_time(c["commit"]["author"]["date"])
        print(f"  {sha}  {when:<10}  {author:<15}  {msg}")


def cmd_issues(api: GitHubAPI, args):
    repo  = args.repo or _default_repo()
    state = args.state or "open"
    # GitHub issues API also returns PRs; filter those out
    items = [i for i in api.get(f"/repos/{repo}/issues", state=state, per_page=20)
             if "pull_request" not in i]

    if not items:
        print(f"이슈 없음 ({state})")
        return

    print(f"\n🐛 {repo} — 이슈 ({state}) {len(items)}개\n")
    for i in items:
        labels = ", ".join(l["name"] for l in i.get("labels", []))
        print(f"  #{i['number']:>4}  {_relative_time(i['created_at']):<10}  {i['title']}")
        if labels:
            print(f"         [{labels}]")


def cmd_repos(api: GitHubAPI, args):
    user  = args.user or api.get("/user")["login"]
    repos = api.get(f"/users/{user}/repos", sort="updated", per_page=15)

    print(f"\n📦 {user} — 레포 {len(repos)}개\n")
    print(f"  {'이름':<30}  {'별':>5}  {'업데이트':<10}  언어")
    print("  " + "─" * 60)
    for r in repos:
        lang = r.get("language") or "-"
        print(f"  {r['name']:<30}  {r['stargazers_count']:>5}  {_relative_time(r['updated_at']):<10}  {lang}")


def cmd_summary(api: GitHubAPI, args):
    repo = args.repo or _default_repo()
    r    = api.get(f"/repos/{repo}")
    open_prs     = len(api.get(f"/repos/{repo}/pulls", state="open", per_page=100))
    open_issues  = len([i for i in api.get(f"/repos/{repo}/issues", state="open", per_page=100)
                        if "pull_request" not in i])
    recent = api.get(f"/repos/{repo}/commits", per_page=5)

    print(f"\n📊 {repo} 요약")
    print(f"  ⭐ {r['stargazers_count']}  🍴 {r['forks_count']}  👁 {r['watchers_count']}")
    print(f"  언어: {r.get('language', '-')}  기본 브랜치: {r['default_branch']}")
    print(f"  오픈 PR: {open_prs}  오픈 이슈: {open_issues}")
    print(f"  마지막 푸시: {_relative_time(r['pushed_at'])}")
    if recent:
        print(f"\n  최근 커밋:")
        for c in recent[:3]:
            msg = c["commit"]["message"].split("\n")[0][:50]
            print(f"    • {c['sha'][:7]}  {msg}")
    print(f"\n  🔗 {r['html_url']}")


def cmd_runs(api: GitHubAPI, args):
    repo = args.repo or _default_repo()
    try:
        runs = api.get(f"/repos/{repo}/actions/runs", per_page=10)["workflow_runs"]
    except Exception:
        print("Actions 없음 또는 권한 부족")
        return

    print(f"\n⚙️ {repo} — CI/CD 실행\n")
    icon = {"success": "✅", "failure": "❌", "in_progress": "🔄", "queued": "⏳"}
    for run in runs[:8]:
        i = icon.get(run["conclusion"] or run["status"], "❓")
        print(f"  {i} #{run['run_number']:>4}  {run['name']:<25}  "
              f"{_relative_time(run['created_at']):<10}  {run.get('conclusion') or run['status']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenClaw GitHub 연동")
    parser.add_argument("--repo", help="owner/repo (기본: 현재 git remote)")
    sub = parser.add_subparsers(dest="cmd")

    p_prs = sub.add_parser("prs",     help="PR 목록")
    p_prs.add_argument("--state", default="open", choices=["open", "closed", "all"])

    p_pr = sub.add_parser("pr",       help="PR 상세")
    p_pr.add_argument("--id", type=int, required=True)

    p_cm = sub.add_parser("commits",  help="최근 커밋")
    p_cm.add_argument("--n", type=int, default=10)

    p_is = sub.add_parser("issues",   help="이슈 목록")
    p_is.add_argument("--state", default="open", choices=["open", "closed", "all"])

    p_rp = sub.add_parser("repos",    help="레포 목록")
    p_rp.add_argument("--user")

    sub.add_parser("summary",         help="레포 요약")
    sub.add_parser("runs",            help="CI/CD 상태")

    args = parser.parse_args()

    token = _get_token()
    if not token:
        print("❌ GITHUB_TOKEN 없음\n"
              "   openclaw.json의 env 섹션에 추가:\n"
              '   "GITHUB_TOKEN": "ghp_xxxx..."')
        sys.exit(1)

    api = GitHubAPI(token)
    {
        "prs":     cmd_prs,
        "pr":      cmd_pr,
        "commits": cmd_commits,
        "issues":  cmd_issues,
        "repos":   cmd_repos,
        "summary": cmd_summary,
        "runs":    cmd_runs,
    }.get(args.cmd, lambda a, b: parser.print_help())(api, args)


if __name__ == "__main__":
    main()
