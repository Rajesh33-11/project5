#!/usr/bin/env python3
"""GitHub PR helper used by Jenkins (stdlib only).

  github_pr.py comment            post reports/pr_validation.md (or --body) as a PR comment
  github_pr.py merge              merge the PR into its base branch
  github_pr.py create-pr          open a PR for --head into --base (no-op if one is already open)

Env:
  GITHUB_TOKEN    token with pull-requests:write + contents:write   (required)
  PR_ID           PR number (Jenkins CHANGE_ID)                      (required)
  REPO            "owner/repo"  (default: parsed from git remote origin)
  GITHUB_API      default https://api.github.com  (set for GitHub Enterprise)
  MERGE_METHOD    merge | squash | rebase          (default squash)
  REQUIRE_APPROVAL  true|false                     (default true)

Exit codes: 0 ok, 10 merge skipped (waiting for approval), 1 error.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/")


def repo_slug() -> str:
    if os.environ.get("REPO"):
        return os.environ["REPO"]
    url = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True
    ).stdout.strip()
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        sys.exit(f"cannot derive owner/repo from '{url}' - set REPO")
    return m.group(1)


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API {method} {path} -> {e.code}: {e.read().decode()[:400]}")


def comment(repo: str, pr: str, body: str):
    call("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": body})
    print(f"commented on PR #{pr}")


def approved(repo: str, pr: str) -> tuple[bool, str]:
    latest: dict[str, str] = {}
    for r in call("GET", f"/repos/{repo}/pulls/{pr}/reviews?per_page=100"):
        if r["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[r["user"]["login"]] = r["state"]
    if "CHANGES_REQUESTED" in latest.values():
        return False, "changes requested by a reviewer"
    if "APPROVED" not in latest.values():
        return False, "no approving review yet"
    return True, "approved"


def merge(repo: str, pr: str) -> int:
    info = call("GET", f"/repos/{repo}/pulls/{pr}")
    if info["state"] != "open":
        print(f"PR #{pr} is {info['state']} - nothing to merge")
        return 0
    if info.get("draft"):
        print("PR is a draft - not merging")
        return 10
    if os.environ.get("REQUIRE_APPROVAL", "true").lower() == "true":
        ok, why = approved(repo, pr)
        if not ok:
            comment(
                repo,
                pr,
                f"⏳ Validation passed but **not merged**: {why}. "
                "Approve the PR, then re-run the Jenkins build to merge.",
            )
            print(f"not merging: {why}")
            return 10
    res = call(
        "PUT",
        f"/repos/{repo}/pulls/{pr}/merge",
        {
            "merge_method": os.environ.get("MERGE_METHOD", "squash"),
            "sha": info["head"]["sha"],  # refuse if branch moved since validation
            "commit_title": f"{info['title']} (#{pr})",
        },
    )
    print(f"merged PR #{pr} into {info['base']['ref']}: {res.get('sha')}")
    comment(repo, pr, f"🚀 Merged into `{info['base']['ref']}` by Jenkins (`{res.get('sha', '')[:7]}`).")
    return 0


def create_pr(repo: str, head: str, base: str, title: str, body: str) -> int:
    owner = repo.split("/")[0]
    q = urllib.parse.quote(f"{owner}:{head}", safe="")
    existing = call(
        "GET", f"/repos/{repo}/pulls?state=open&head={q}&base={urllib.parse.quote(base, safe='')}"
    )
    if existing:
        print(f"PR #{existing[0]['number']} already open for {head}: {existing[0]['html_url']}")
        return 0
    res = call(
        "POST",
        f"/repos/{repo}/pulls",
        {"title": title, "head": head, "base": base, "body": body},
    )
    print(f"created PR #{res['number']} {head} -> {base}: {res['html_url']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["comment", "merge", "create-pr"])
    ap.add_argument("--body", default=None)
    ap.add_argument("--head")
    ap.add_argument("--base", default="main")
    ap.add_argument("--title")
    ap.add_argument("--file", default="reports/pr_validation.md")
    a = ap.parse_args()
    needed = ("GITHUB_TOKEN",) if a.action == "create-pr" else ("GITHUB_TOKEN", "PR_ID")
    for v in needed:
        if not os.environ.get(v):
            sys.exit(f"{v} is required")
    if a.action == "create-pr":
        if not (a.head and a.title):
            sys.exit("create-pr needs --head and --title")
        return create_pr(repo_slug(), a.head, a.base, a.title, a.body or "Auto-created by Jenkins.")
    repo, pr = repo_slug(), os.environ["PR_ID"]
    if a.action == "comment":
        body = a.body or (open(a.file).read() if os.path.exists(a.file) else "Validation finished.")
        comment(repo, pr, body)
        return 0
    return merge(repo, pr)


if __name__ == "__main__":
    sys.exit(main())
