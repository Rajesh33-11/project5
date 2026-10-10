#!/usr/bin/env python3
"""Check that every feature touched in the PR is fully onboarded.

Required per feature (features/<name>/):
  - README.md            what the feature covers, owner, test data notes
  - test_<name>.py       at least one test file
  - at least one test marked @pytest.mark.smoke or @pytest.mark.regression
and a page object at pages/<name>_page.py

Usage: python scripts/check_feature_onboarding.py --base origin/main
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER_RE = re.compile(r"@pytest\.mark\.(smoke|regression)")


def changed_features(base: str) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    ).stdout.splitlines()
    feats = set()
    for f in out:
        p = f.split("/")
        if p[0] == "features" and len(p) > 2 and (ROOT / "features" / p[1]).is_dir():
            feats.add(p[1])
    return feats


def check(feature: str) -> list[str]:
    errs = []
    d = ROOT / "features" / feature
    if not (d / "README.md").exists():
        errs.append("missing README.md")
    tests = list(d.glob("test_*.py"))
    if not tests:
        errs.append("no test_*.py file")
    elif not any(MARKER_RE.search(t.read_text()) for t in tests):
        errs.append("no test marked @pytest.mark.smoke or @pytest.mark.regression")
    if not (ROOT / "pages" / f"{feature}_page.py").exists():
        errs.append(f"missing page object pages/{feature}_page.py")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()

    feats = changed_features(args.base)
    if not feats:
        print("  no feature folders changed - nothing to check")
        return 0
    bad = False
    for f in sorted(feats):
        errs = check(f)
        if errs:
            bad = True
            for e in errs:
                print(f"  [{f}] {e}")
        else:
            print(f"  [{f}] OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
