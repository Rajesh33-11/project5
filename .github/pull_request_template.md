## What & why
<!-- Feature being onboarded / changed -->

## Checklist
- [ ] Branch is `feature/<name>` (or bugfix/hotfix/chore)
- [ ] PR title starts with ticket id: `QA-123: ...`
- [ ] Feature scaffolded with `python scripts/new_feature.py <name>`
- [ ] `features/<name>/README.md` filled in (owner, scope, test data)
- [ ] At least one `@pytest.mark.smoke` test
- [ ] Page object in `pages/<name>_page.py`
- [ ] No secrets committed (use Jenkins credentials)
- [ ] `ruff check . && ruff format .` clean locally
