#!/usr/bin/env python3
"""Scaffold a new feature so it passes PR validation from the start.

Usage: python scripts/new_feature.py checkout
Creates:
  features/checkout/{__init__.py, README.md, test_checkout.py}
  pages/checkout_page.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]*", sys.argv[1]):
        sys.exit("usage: new_feature.py <snake_case_name>")
    name = sys.argv[1]
    cls = "".join(w.capitalize() for w in name.split("_")) + "Page"

    fdir = ROOT / "features" / name
    if fdir.exists():
        sys.exit(f"feature '{name}' already exists")
    fdir.mkdir(parents=True)
    (fdir / "__init__.py").write_text("")
    (fdir / "README.md").write_text(
        f"# {name}\n\n**Owner:** <team/person>\n\n## Scope\n- What this feature's tests cover\n\n"
        f"## Test data\n- Accounts / fixtures needed\n\n## Run\n```\npytest features/{name}\n```\n"
    )
    (fdir / f"test_{name}.py").write_text(
        f"import pytest\n\nfrom pages.{name}_page import {cls}\n\n\n"
        f"@pytest.mark.smoke\ndef test_{name}_page_loads(page, base_url):\n"
        f"    p = {cls}(page, base_url)\n    p.open()\n    assert p.is_loaded()\n"
    )
    (ROOT / "pages" / f"{name}_page.py").write_text(
        f"from pages.base_page import BasePage\n\n\nclass {cls}(BasePage):\n"
        f'    PATH = "/{name}"\n\n    def is_loaded(self) -> bool:\n'
        f'        return self.page.url.rstrip("/").endswith(self.PATH)\n'
    )
    print(f"Created feature '{name}'. Next: edit tests, then open a PR from feature/{name}.")


if __name__ == "__main__":
    main()
