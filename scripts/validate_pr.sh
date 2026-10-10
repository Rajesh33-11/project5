#!/usr/bin/env bash
# PR validation gate. Run locally or from Jenkins.
#   TARGET_BRANCH  (default origin/main)
#   PR_NUMBER / PR_ID  PR number (Jenkins CHANGE_ID)
#   PR_TITLE, PR_BRANCH, PR_URL  (optional; title/branch rules enforced if set)
# Writes reports/pr_validation.md (posted as the PR comment by scripts/github_pr.py).
set -uo pipefail

TARGET_BRANCH="${TARGET_BRANCH:-origin/main}"
PR_NUMBER="${PR_NUMBER:-${PR_ID:-local}}"
PR_TITLE="${PR_TITLE:-}"
PR_URL="${PR_URL:-}"
PR_BRANCH="${PR_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
FAILED=0
ROWS=""

mkdir -p reports

pass() { echo "  [PASS] $1"; ROWS+="| ✅ | $1 |"$'\n'; }
fail() { echo "  [FAIL] $1"; ROWS+="| ❌ | $1 |"$'\n'; FAILED=1; }
skip() { echo "  [SKIP] $1"; ROWS+="| ➖ | $1 |"$'\n'; }

echo "== 1. Branch name =="
if [[ "$PR_BRANCH" =~ ^(feature|bugfix|hotfix|chore)/[A-Za-z0-9._-]+$ ]]; then
  pass "Branch name \`$PR_BRANCH\` follows <type>/<name>"
else
  fail "Branch \`$PR_BRANCH\` must match feature|bugfix|hotfix|chore/<name>"
fi

echo "== 2. PR title =="
if [[ -z "$PR_TITLE" ]]; then
  skip "PR title not provided"
elif [[ "$PR_TITLE" =~ ^[A-Z]+-[0-9]+:\ .+ ]]; then
  pass "PR title has ticket id"
else
  fail "PR title must start with ticket id, e.g. \`QA-123: description\`"
fi

echo "== 3. Conflict markers / whitespace (PR diff) =="
if git diff --check "$TARGET_BRANCH"...HEAD; then pass "No whitespace errors / conflict markers"; else fail "Whitespace errors or conflict markers in diff"; fi

echo "== 4. Secrets scan (PR diff) =="
if git diff "$TARGET_BRANCH"...HEAD -U0 | grep -E '^\+' | grep -Eiq '(password|secret|api[_-]?key|token)\s*[:=]\s*["'\''][^"'\'' ]{6,}'; then
  fail "Possible hard-coded secret in diff (use Jenkins credentials / env vars)"
else
  pass "No hard-coded secrets found"
fi

echo "== 5. Lint =="
if ruff check . ; then pass "ruff lint"; else fail "ruff lint errors"; fi
if ruff format --check . ; then pass "ruff format"; else fail "Formatting - run \`ruff format .\`"; fi

echo "== 6. Whole-repo validation =="
if python scripts/validate_repo.py; then
  pass "Repo structure, YAML, JSON, TOML, Dockerfile, shell, Python, Jenkinsfile all valid"
else
  fail "Repo validation (structure / YAML / Dockerfile / syntax) - see Jenkins log"
fi

echo "== 7. Test collection (import check) =="
if pytest --collect-only -q >/dev/null; then pass "All tests collect"; else fail "pytest collection failed"; fi

echo "== 8. Feature onboarding checklist (changed features) =="
if python scripts/check_feature_onboarding.py --base "$TARGET_BRANCH"; then pass "Feature onboarding complete"; else fail "Feature onboarding incomplete"; fi

if [[ $FAILED -eq 0 ]]; then
  HEAD_LINE="### ✅ PR #${PR_NUMBER} validated - all checks passed"
else
  HEAD_LINE="### ❌ PR #${PR_NUMBER} validation FAILED"
fi
{
  echo "$HEAD_LINE"
  echo
  echo "**Branch:** \`${PR_BRANCH}\` → \`${TARGET_BRANCH#origin/}\`"
  [[ -n "$PR_TITLE" ]] && { echo; echo "**Title:** ${PR_TITLE}"; }
  echo
  echo "| Result | Check |"
  echo "|---|---|"
  printf '%s' "$ROWS"
  if [[ -n "${BUILD_URL:-}" ]]; then echo; echo "[Jenkins build](${BUILD_URL})"; fi
} > reports/pr_validation.md

echo
echo "=============================================================="
if [[ $FAILED -ne 0 ]]; then
  echo "❌ PR #${PR_NUMBER} VALIDATION FAILED - fix the [FAIL] items above"
  echo "=============================================================="
  exit 1
fi
echo "✅ PR #${PR_NUMBER} (${PR_BRANCH}) - ALL VALIDATIONS PASSED"
echo "   Title : ${PR_TITLE:-n/a}"
echo "   Target: ${TARGET_BRANCH}"
[[ -n "$PR_URL" ]] && echo "   URL   : ${PR_URL}"
echo "=============================================================="
