"""Checks a full build (`make build-site`): every catalog station has a page,
every page carries the disclaimers and the NOAA credit, nothing absent
renders as a value, every internal link and sitemap entry resolves, no page
is unreasonably large, and the sitemap lists exactly the pages that may be
indexed: subordinate station pages carry noindex and are left out
(docs/DECISIONS.md 0013).

    uv run python scripts/check_site.py SITE_DIR
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from tidehours.catalog import Station, load

HREF = re.compile(r'(?:href|src)="(/[^"#?]*)')
LOC = re.compile(r"<loc>https://tidehours\.com/([^<]*)</loc>")
SCRIPT = re.compile(r"<script.*?</script>", re.S)
BAD = ("None", "NaN", "nan ft", "undefined", "{{", "{place}", "{id}", "{date}")
MAX_PAGE_BYTES = 120_000
NOINDEX = '<meta name="robots" content="noindex,follow">'


def check_page(root: Path, f: Path) -> list[str]:
    problems: list[str] = []
    rel = f.relative_to(root).as_posix()
    text = f.read_text(encoding="utf-8")
    if len(text.encode()) > MAX_PAGE_BYTES:
        problems.append(f"{rel}: {len(text.encode())} bytes")
    if "Not for navigation" not in text and "No sirven para la navegación" not in text:
        problems.append(f"{rel}: no navigation disclaimer")
    if "not a NOAA product" not in text and "no es un producto de NOAA" not in text:
        problems.append(f"{rel}: no 'not a NOAA product'")
    if "NOAA CO-OPS" not in text:
        problems.append(f"{rel}: no NOAA credit")
    body = SCRIPT.sub("", text)
    problems += [f"{rel}: contains {b!r}" for b in BAD if b in body]
    for link in HREF.findall(text):
        target = root / link.lstrip("/")
        if not (target.is_file() or (target / "index.html").is_file()):
            problems.append(f"{rel}: broken link {link}")
    return problems


def check_indexing(root: Path, html: list[Path], stations: list[Station]) -> list[str]:
    """Subordinate station pages carry noindex and harmonic ones do not; the
    sitemap and lastmod.json list exactly the pages without noindex."""
    problems: list[str] = []
    for s in stations:
        f = root / "stations" / s.id / "index.html"
        if f.exists() and (NOINDEX in f.read_text(encoding="utf-8")) != s.is_subordinate:
            kind, want = ("subordinate", "noindex") if s.is_subordinate else ("harmonic", "no noindex")
            problems.append(f"stations/{s.id}: a {kind} station needs {want}")
    indexable: set[str] = set()
    for f in html:
        if f.name == "index.html" and NOINDEX not in f.read_text(encoding="utf-8"):
            indexable.add("" if f.parent == root else f.parent.relative_to(root).as_posix() + "/")
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    if set(locs) != indexable or len(locs) != len(indexable):
        problems.append(f"sitemap lists {len(locs)} URLs for {len(indexable)} indexable pages")
    problems += [f"sitemap: {loc} has no page" for loc in locs if not (root / loc / "index.html").is_file()]
    manifest = json.loads((root / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    if set(manifest) != {"/" + p for p in indexable}:
        problems.append(f"lastmod.json lists {len(manifest)} pages for {len(indexable)} indexable pages")
    return problems


def main(root: Path) -> int:
    problems: list[str] = []
    cat = load()
    html = sorted(root.rglob("*.html"))
    if len(html) < 3_700:
        problems.append(f"only {len(html)} pages; a full build has more than 3,700")
    for s in cat.stations:
        if not (root / "stations" / s.id / "index.html").exists():
            problems.append(f"no page for station {s.id}")
    for f in html:
        problems += check_page(root, f)
    problems += check_indexing(root, html, cat.stations)
    for p in problems[:50]:
        print(p, file=sys.stderr)
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    print(f"check_site: {len(html)} pages, {len(locs)} sitemap URLs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
