"""Checks a full build (`make build-site`): every catalog station has a page,
every page carries the disclaimers and the NOAA credit, nothing absent
renders as a value, every internal link and sitemap entry resolves, no page
is unreasonably large, and the sitemap lists exactly the pages that may be
indexed: subordinate station pages carry noindex and are left out
(docs/DECISIONS.md 0013). A station page shows a type of tide exactly when
its own constants give one, and it is the computed one (0014). The
king-tide pages' summary of the runs coming up, their titles, and the
king-tide links on station pages match the computed season for the day the
pages were built (0015).

    uv run python scripts/check_site.py SITE_DIR
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

from tidehours import kingtides, ktformat, site
from tidehours.catalog import Catalog, Station, load

HREF = re.compile(r'(?:href|src)="(/[^"#?]*)')
LOC = re.compile(r"<loc>https://tidehours\.com/([^<]*)</loc>")
SCRIPT = re.compile(r"<script.*?</script>", re.S)
BAD = ("None", "NaN", "nan ft", "undefined", "{{", "{place}", "{id}", "{date}")
MAX_PAGE_BYTES = 120_000
NOINDEX = '<meta name="robots" content="noindex,follow">'
TIDE_TYPE = re.compile(r'data-tide-type="([^"]*)"')
STATION_DATE = re.compile(r'data-station-date="(\d{4}-\d{2}-\d{2})"')
KT_NEXT = re.compile(r'data-kt-next="([^"]*)"')
KT_RUN = re.compile(r'data-kt-run="([^"]*)"')
TITLE = re.compile(r"<title>([^<]*)</title>")


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


def check_tide_types(root: Path, cat: Catalog) -> list[str]:
    """Each station page shows the type of tide its constants give, and none
    when they give none (subordinate stations, or a constituent missing)."""
    problems: list[str] = []
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if not f.exists():
            continue
        shown = TIDE_TYPE.findall(f.read_text(encoding="utf-8"))
        tt = cat.tide_type(s.id)
        want = [tt.kind.key] if tt else []
        if shown != want:
            problems.append(f"stations/{s.id}: type of tide {shown or 'none'}, expected {want or 'none'}")
    return problems


def check_king_tides(root: Path, cat: Catalog) -> list[str]:
    """The king-tide pages list exactly the runs coming up on the day they
    were built, and name their months in the title; each station page links
    to the king-tide run computed for it, and none links where none is."""
    problems: list[str] = []
    ctx = site.king_tide_context(cat)
    seasons: list[kingtides.StationSeason] = ctx["seasons"]
    # The day the pages were built for, on the coast: a king-tide station
    # page's date. The king-tide pages don't carry it, so that they stay
    # byte-identical (and are not re-announced, 0011) until what they say changes.
    dated = [root / "stations" / k.id / "index.html" for k in seasons]
    found = [STATION_DATE.findall(f.read_text(encoding="utf-8")) for f in dated if f.exists()]
    if not found or len(found[0]) != 1:
        return ["king-tides: no king-tide station page to date the build"]
    today = dt.date.fromisoformat(found[0][0])
    up = kingtides.coming_up(seasons, today)
    want = [u.stamp() for u in up]
    for lang, rel in (("en", "king-tides"), ("es", "es/king-tides")):
        text = (root / rel / "index.html").read_text(encoding="utf-8")
        shown = KT_NEXT.findall(text)
        if shown != want:
            extra = [x for x in shown if x not in want]
            missing = [w for w in want if w not in shown]
            problems.append(
                f"{rel}: runs coming up differ: shown but not computed {extra}, computed but not shown {missing}"
            )
        title = TITLE.findall(text)
        if up and not (title and ktformat.fmt_months(kingtides.months(up, today), lang, ctx["copy"][lang]) in title[0]):
            problems.append(f"{rel}: title {title[:1]} does not name the months of the runs coming up")
    links = site.king_links(cat.stations, seasons, today, cat)
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if not f.exists():
            continue
        shown = KT_RUN.findall(f.read_text(encoding="utf-8"))
        link = links.get(s.id)
        expect = [link.up.stamp()] if link else []
        if shown != expect:
            problems.append(f"stations/{s.id}: king-tide link {shown or 'none'}, expected {expect or 'none'}")
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
    problems += check_tide_types(root, cat)
    problems += check_king_tides(root, cat)
    for p in problems[:50]:
        print(p, file=sys.stderr)
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    print(f"check_site: {len(html)} pages, {len(locs)} sitemap URLs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
