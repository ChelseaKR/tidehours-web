"""Repository hygiene, run by `make hygiene` (and so by `make verify`).

Text checks that are not a linter's job:

- American English in code, copy and docs (the portfolio rule): no
  "colour", "favourite", "behaviour" and the like. Quoted third-party names
  keep their spelling, so the list is only words this project writes itself.
- The word "official" never appears in the site's copy or templates. These
  are predictions computed from NOAA data, not NOAA's product.
- No merge-conflict markers.
- No wildcard `git add` in a workflow.
- The committed NOAA data matches the SHA-256 recorded in docs/DATA.md, so a
  data change is always a reviewed doc change too.

`--self-test` feeds each pattern a line it must reject and one it must
accept, so a check that has stopped matching cannot report a clean repo.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BRITISH = re.compile(
    r"\b(colours?|favourites?|behaviours?|licence|organis(e|ed|ing|ation)|"
    r"centre|metres?|analys(e|ed|ing)|catalogue|honour|travell(ed|ing)|programme|normalis(e|ed|ing)|"
    r"recognis(e|ed|ing)|neighbour(s|ing|hood)?|grey)\b",
    re.IGNORECASE,
)
OFFICIAL = re.compile(r"\bofficial\b", re.IGNORECASE)
CONFLICT = re.compile("^(?:" + "<" * 7 + "(?: |$)|" + ">" * 7 + "(?: |$)|" + "=" * 7 + "$)")
WILDCARD_ADD = re.compile(r"\bgit\s+add\s+(?:[^\n#]*\s)?(?:-A\b|--all\b|\.(?=\s|$))")
DATA_LINE = re.compile(r"`(?P<path>src/tidehours/data/[\w.-]+)`.*sha256 `(?P<sha>[0-9a-f]{64})`")

TEXT_SUFFIXES = {".py", ".jinja", ".css", ".json", ".md", ".yml", ".yaml", ".toml", ".sh", ".mjs", ".txt"}
SKIP_DIRS = {".git", ".venv", "node_modules", "fixtures", "__pycache__", ".mypy_cache", ".ruff_cache", "site"}
# Large NOAA data: names and regions are NOAA's own text.
SKIP_FILES = {"stations.json", "regions.json", "package-lock.json", "uv.lock"}


def files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        wanted = p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in SKIP_FILES
        if wanted and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
            out.append(p)
    return sorted(out)


def british(line: str) -> bool:
    return bool(BRITISH.search(line))


def check() -> list[str]:
    problems: list[str] = []
    for p in files():
        rel = p.relative_to(ROOT).as_posix()
        if rel == "scripts/check_hygiene.py":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if british(line):
                problems.append(f"{rel}:{n}: British spelling: {line.strip()[:80]}")
            if CONFLICT.match(line):
                problems.append(f"{rel}:{n}: merge-conflict marker")
            if rel.startswith(("src/tidehours/templates/", "src/tidehours/copy/")) and OFFICIAL.search(line):
                problems.append(f"{rel}:{n}: 'official' in site copy")
            if rel.startswith(".github/workflows/") and WILDCARD_ADD.search(line):
                problems.append(f"{rel}:{n}: wildcard git add")
    recorded = {m["path"]: m["sha"] for m in DATA_LINE.finditer((ROOT / "docs/DATA.md").read_text(encoding="utf-8"))}
    for data in sorted((ROOT / "src/tidehours/data").glob("*.json")):
        rel = data.relative_to(ROOT).as_posix()
        sha = hashlib.sha256(data.read_bytes()).hexdigest()
        if recorded.get(rel) != sha:
            problems.append(f"{rel}: sha256 {sha} is not the one recorded in docs/DATA.md")
    return problems


def self_test() -> list[str]:
    cases = [
        (british, "my favourite colour", "my favorite color"),
        (british, "a licence", "a license"),
        (lambda s: bool(OFFICIAL.search(s)), "the official tide", "NOAA's tides"),
        (lambda s: bool(CONFLICT.match(s)), "<" * 7 + " HEAD", "<<< not a marker"),
        (lambda s: bool(WILDCARD_ADD.search(s)), "git add -A", "git add site/index.html"),
    ]
    return [f"self-test: {bad!r} / {good!r}" for f, bad, good in cases if not f(bad) or f(good)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    problems = self_test() if ap.parse_args().self_test else check()
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
