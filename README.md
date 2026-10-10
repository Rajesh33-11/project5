# E2E Automation – PR Validation + Jenkins

Python + pytest (Playwright) end-to-end suite. Every new feature is onboarded as a folder under `features/`, and every PR is gated by `scripts/validate_pr.sh` in Jenkins.

## Layout
```
Jenkinsfile                      Multibranch pipeline
scripts/
  validate_pr.sh                 PR gate (branch, title, secrets, lint, collect, onboarding)
  changed_features.py            Which features does this PR touch?
  check_feature_onboarding.py    README + tests + marker + page object present?
  new_feature.py                 Scaffold a new feature
features/<name>/                 README.md, test_<name>.py
pages/<name>_page.py             Page objects (extend BasePage)
```

## Onboard a new feature
```bash
git checkout -b feature/checkout
python scripts/new_feature.py checkout
# edit features/checkout/*, pages/checkout_page.py
git add . && git commit -m "QA-123: Add checkout tests"
git push -u origin feature/checkout     # open PR titled "QA-123: Add checkout tests"
```

## What Jenkins does
| Build | Stages |
|---|---|
| PR | Setup → **PR Validation** → run tests only for changed features (smoke if none) |
| main | Setup → full regression (`pytest -n 4`) |

Shared-code changes (`pages/`, `utils/`, `config/`, `conftest.py`, `requirements.txt`) trigger all features.

## Jenkins setup (one-time)
1. Create a **Multibranch Pipeline** job pointing at the git repo; enable PR discovery (GitHub/Bitbucket/GitLab branch source plugin).
2. Add Secret-text credential `e2e-base-url` (and `e2e-api-token` if needed).
3. Agent needs Python 3.10+, git; for Playwright run `playwright install --with-deps` (add to Setup stage).
4. Install plugins: Pipeline, Git, Timestamper, JUnit, Workspace Cleanup.
5. In the git host, make the Jenkins check **required** under branch protection so PRs can't merge when validation fails.

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && playwright install
export BASE_URL=https://your-app.example.com
TARGET_BRANCH=origin/main bash scripts/validate_pr.sh
pytest -m smoke
```

## Customising rules
- Branch/title regex: top of `scripts/validate_pr.sh`
- Onboarding requirements: `check()` in `scripts/check_feature_onboarding.py`
- Shared-code prefixes: `SHARED_PREFIXES` in `scripts/changed_features.py`

## PR flow (feature branch -> main)
1. Anyone creates `feature/<name>` from `main` and opens a PR.
2. Jenkins **PR Validation (whole repo)** runs `scripts/validate_pr.sh`:
   branch name, PR title, secrets, ruff, and `scripts/validate_repo.py`
   (folder structure, YAML, JSON, TOML, Dockerfile, shell, Python, Jenkinsfile syntax), test collection, onboarding.
3. Changed-feature tests run.
4. All OK -> Jenkins prints `PR #<n> ... ALL VALIDATIONS PASSED`, comments the result on the PR, then merges it into `main`
   (`scripts/github_pr.py`; squash, needs reviewer approval unless `REQUIRE_APPROVAL = 'false'`).
5. The `main` build runs full regression.

Any failure stops the pipeline: nothing is merged and the PR gets a comment listing the failed checks.
Jenkins credential needed: Secret text `github-token` (pull-requests:write + contents:write), plus `e2e-base-url`.
Set `AUTO_MERGE = 'false'` in the Jenkinsfile to validate only.

## Fully automatic flow (developer only runs 3 commands)
```bash
git checkout -b feature/payments
git add . && git commit -m "QA-1: payments"
git push -u origin feature/payments
```
Jenkins branch build -> **Auto-create PR** (title = last commit message) -> PR build validates + tests -> merges to `main` -> main build runs full regression.
Jenkins job: Branch Sources > Behaviours > *Discover branches: Exclude branches that are also filed as PRs* + *Discover pull requests from origin*.
Branch protection on `main` must not require human reviews (we set `REQUIRE_APPROVAL = 'false'`), or add Jenkins's token user to the bypass list.
