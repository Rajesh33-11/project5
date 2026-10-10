#!/usr/bin/env python3
"""Whole-repo validation (not just the PR diff).

Checks
  1. Repo structure   : required files/folders, every feature has README + tests + page object
  2. YAML  (*.yml/*.yaml)      : syntax
  3. JSON  (*.json)            : syntax
  4. TOML  (*.toml)            : syntax
  5. Dockerfile (Dockerfile*)  : valid instructions, FROM present, no ':latest', uses hadolint if installed
  6. Shell (*.sh)              : bash -n (and shellcheck if installed)
  7. Python (*.py)             : compiles
  8. Jenkinsfile               : basic structure + balanced braces

Exit code 0 = everything OK, 1 = at least one failure.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "reports",
}

REQUIRED_FILES = ["Jenkinsfile", "README.md", "requirements.txt", "pytest.ini", "conftest.py"]
REQUIRED_DIRS = ["features", "pages", "scripts"]

DOCKER_INSTRUCTIONS = {
    "FROM",
    "RUN",
    "CMD",
    "LABEL",
    "MAINTAINER",
    "EXPOSE",
    "ENV",
    "ADD",
    "COPY",
    "ENTRYPOINT",
    "VOLUME",
    "USER",
    "WORKDIR",
    "ARG",
    "ONBUILD",
    "STOPSIGNAL",
    "HEALTHCHECK",
    "SHELL",
}

errors: list[str] = []
warnings: list[str] = []


def files(*patterns: str):
    seen = set()
    for pat in patterns:
        for p in ROOT.rglob(pat):
            if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p not in seen:
                seen.add(p)
                yield p


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def section(title: str) -> int:
    print(f"\n== {title} ==")
    return len(errors)


def done(start: int, ok_msg: str) -> None:
    print(f"  [PASS] {ok_msg}" if len(errors) == start else f"  [FAIL] {len(errors) - start} problem(s)")


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  - {msg}")


# ---------------------------------------------------------------- 1. structure
def check_structure() -> None:
    s = section("1. Repo structure")
    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            err(f"missing required file: {f}")
    for d in REQUIRED_DIRS:
        if not (ROOT / d).is_dir():
            err(f"missing required folder: {d}/")
    fdir = ROOT / "features"
    if fdir.is_dir():
        for feat in sorted(p for p in fdir.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
            if not (feat / "README.md").is_file():
                err(f"features/{feat.name}: missing README.md")
            if not list(feat.glob("test_*.py")):
                err(f"features/{feat.name}: no test_*.py file")
            if not (ROOT / "pages" / f"{feat.name}_page.py").is_file():
                err(f"features/{feat.name}: missing page object pages/{feat.name}_page.py")
    done(s, "folders and files are correct")


# ---------------------------------------------------------------- 2-4. data files
def check_yaml() -> None:
    s = section("2. YAML syntax")
    n = 0
    for p in files("*.yml", "*.yaml"):
        n += 1
        try:
            list(yaml.safe_load_all(p.read_text()))
        except yaml.YAMLError as e:
            err(f"{rel(p)}: {str(e).splitlines()[0]} {getattr(e, 'problem_mark', '') or ''}".strip())
    done(s, f"{n} YAML file(s) valid")


def check_json() -> None:
    s = section("3. JSON syntax")
    n = 0
    for p in files("*.json"):
        n += 1
        try:
            json.loads(p.read_text())
        except ValueError as e:
            err(f"{rel(p)}: {e}")
    done(s, f"{n} JSON file(s) valid")


def check_toml() -> None:
    s = section("4. TOML syntax")
    n = 0
    for p in files("*.toml"):
        n += 1
        try:
            tomllib.loads(p.read_text())
        except tomllib.TOMLDecodeError as e:
            err(f"{rel(p)}: {e}")
    done(s, f"{n} TOML file(s) valid")


# ---------------------------------------------------------------- 5. Dockerfile
def logical_lines(text: str):
    """Yield (line_no, logical line) joining backslash continuations, skipping comments/blank."""
    buf, start = "", 0
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not buf and (not line.strip() or line.lstrip().startswith("#")):
            continue
        if line.lstrip().startswith("#"):  # comment inside continuation
            continue
        if not buf:
            start = i
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        yield start, (buf + line).strip()
        buf = ""
    if buf:
        yield start, buf.strip()


def check_dockerfiles() -> None:
    s = section("5. Dockerfile")
    docker = sorted(set(files("Dockerfile", "Dockerfile.*", "*.Dockerfile")))
    hadolint = shutil.which("hadolint")
    for p in docker:
        seen_from = False
        for no, line in logical_lines(p.read_text()):
            instr = line.split(None, 1)[0].upper()
            if instr not in DOCKER_INSTRUCTIONS:
                err(f"{rel(p)}:{no}: unknown instruction '{instr}'")
                continue
            if instr == "FROM":
                seen_from = True
                image = line.split()[1] if len(line.split()) > 1 else ""
                if not image:
                    err(f"{rel(p)}:{no}: FROM without image")
                elif image.endswith(":latest") or (
                    ":" not in image and "@" not in image and image != "scratch" and "$" not in image
                ):
                    err(f"{rel(p)}:{no}: pin the base image version (no ':latest' / untagged): {image}")
            elif instr != "ARG" and not seen_from:
                err(f"{rel(p)}:{no}: '{instr}' before FROM")
        if not seen_from:
            err(f"{rel(p)}: no FROM instruction")
        if hadolint:
            r = subprocess.run([hadolint, "--no-fail", "-t", "error", str(p)], capture_output=True, text=True)
            if r.stdout.strip():
                err(f"{rel(p)}: hadolint: {r.stdout.strip()}")
    if not hadolint and docker:
        warnings.append("hadolint not installed - used built-in Dockerfile checks only")
    done(s, f"{len(docker)} Dockerfile(s) valid")


# ---------------------------------------------------------------- 6. shell
def check_shell() -> None:
    s = section("6. Shell scripts")
    n = 0
    shellcheck = shutil.which("shellcheck")
    for p in files("*.sh"):
        n += 1
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        if r.returncode:
            err(f"{rel(p)}: {r.stderr.strip()}")
        elif shellcheck:
            r = subprocess.run([shellcheck, "-S", "error", str(p)], capture_output=True, text=True)
            if r.returncode:
                err(f"{rel(p)}: shellcheck: {r.stdout.strip()}")
    done(s, f"{n} shell script(s) valid")


# ---------------------------------------------------------------- 7. python
def check_python() -> None:
    s = section("7. Python syntax")
    n = 0
    for p in files("*.py"):
        n += 1
        try:
            compile(p.read_text(), str(p), "exec")
        except (SyntaxError, ValueError) as e:
            err(f"{rel(p)}: {e}")
    done(s, f"{n} Python file(s) compile")


# ---------------------------------------------------------------- 8. Jenkinsfile
def check_jenkinsfile() -> None:
    s = section("8. Jenkinsfile")
    jf = ROOT / "Jenkinsfile"
    if jf.is_file():
        text = jf.read_text()
        if not re.search(r"\bpipeline\s*\{", text) and not re.search(r"\bnode\b", text):
            err("Jenkinsfile: no 'pipeline {' block found")
        # strip strings/comments crudely before counting braces
        stripped = re.sub(r"'''.*?'''|\"\"\".*?\"\"\"", "", text, flags=re.S)
        stripped = re.sub(r"//.*", "", stripped)
        stripped = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", "", stripped)
        for o, c in ("{}", "()"):
            if stripped.count(o) != stripped.count(c):
                err(f"Jenkinsfile: unbalanced '{o}{c}' ({stripped.count(o)} vs {stripped.count(c)})")
    done(s, "Jenkinsfile structure OK")


def main() -> int:
    print(f"Validating repository: {ROOT}")
    for fn in (
        check_structure,
        check_yaml,
        check_json,
        check_toml,
        check_dockerfiles,
        check_shell,
        check_python,
        check_jenkinsfile,
    ):
        fn()
    for w in warnings:
        print(f"\n[WARN] {w}")
    print()
    if errors:
        print(f"REPO VALIDATION FAILED: {len(errors)} problem(s)")
        return 1
    print("REPO VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
