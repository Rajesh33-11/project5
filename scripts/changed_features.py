#!/usr/bin/env python3
"""Print the feature folders changed in this PR (space separated).

A "feature" is a directory under features/. Changes to shared code
(pages/, utils/, conftest.py, requirements.txt, config/) touch every
feature, so ALL features are returned.

Usage: python scripts/changed_features.py --base origin/main
"""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_PREFIXES = ("pages/", "utils/", "config/", "conftest.py", "requirements.txt", "pytest.ini")


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def all_features() -> list[str]:
    return sorted(p.name for p in (ROOT / "features").iterdir() if p.is_dir() and not p.name.startswith("_"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()

    files = changed_files(args.base)
    features: set[str] = set()
    for f in files:
        if f.startswith(SHARED_PREFIXES):
            print(" ".join(all_features()))
            return
        parts = f.split("/")
        if parts[0] == "features" and len(parts) > 2:
            features.add(parts[1])
    # only keep features that still exist (not deleted)
    existing = set(all_features())
    print(" ".join(sorted(features & existing)))


if __name__ == "__main__":
    main()
