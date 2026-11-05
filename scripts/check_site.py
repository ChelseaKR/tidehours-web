"""Checks a full build (`make build-site`): every catalog station has a page,
every page carries the disclaimers and the NOAA credit, nothing absent
renders as a value, every internal link and sitemap entry resolves, no page
is unreasonably large, and the sitemap lists exactly the pages that may be
indexed: subordinate station pages carry noindex and are left out
(docs/DECISIONS.md 0013). A station page shows a type of tide exactly when
its own constants give one, and it is the computed one (0014). The
king-tide pages' summary of the runs coming up, their titles, and the
king-tide links on station pages match the computed season for the day the
pages were built (0015). Amazon affiliate links appear only when a tag is
configured, only on the English king-tide page, after its method section,
tagged, with rel="sponsored nofollow noopener" and Amazon's disclosure right
before them; with no tag, "amazon" appears nowhere in the build (0016).

    uv run python scripts/check_site.py SITE_DIR [--amazon-tag TAG]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as htmllib
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tidehours import affiliate, kingtides, ktformat, site
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
AMAZON_A = re.compile(r'<a\b[^>]*\bhref="(https?://[^"]*amazon\.[^"]*)"[^>]*>', re.I)
REL_ATTR = re.compile(r'\brel="([^"]*)"')
JSON_LD = re.compile(r'<script type="application/ld\+json">.*?</script>', re.S)


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


def check_affiliate(root: Path, html: list[Path], tag: str) -> list[str]:
    """With no tag, "amazon" appears nowhere. With one, only the English
    king-tide page links to Amazon: at most MAX_LINKS links, each a plain
    tagged search with the configured tag and the required rel, after the
    method section, with the exact disclosure right before the first link
    (in the same section, no heading between). Never in JSON-LD, the sitemap,
    robots.txt or lastmod.json."""
    problems: list[str] = []
    for name in ("sitemap.xml", "robots.txt", "lastmod.json"):
        f = root / name
        if f.exists() and "amazon" in f.read_text(encoding="utf-8").lower():
            problems.append(f"{name}: mentions amazon")
    for f in html:
        rel = f.relative_to(root).as_posix()
        text = f.read_text(encoding="utf-8")
        if not tag:
            if "amazon" in text.lower():
                problems.append(f"{rel}: mentions amazon with no tag set")
            continue
        if any("amazon" in block.lower() for block in JSON_LD.findall(text)):
            problems.append(f"{rel}: amazon in JSON-LD")
        links = list(AMAZON_A.finditer(text))
        if rel != affiliate.PAGE + "index.html":
            if links or "amazon.com" in text.lower():
                problems.append(f"{rel}: amazon link outside {affiliate.PAGE}")
            continue
        problems += _check_affiliate_page(rel, text, links, tag)
    return problems


def _check_affiliate_page(rel: str, text: str, links: list[re.Match[str]], tag: str) -> list[str]:
    problems: list[str] = []
    if not links:
        return [f"{rel}: no amazon links with a tag set"]
    if len(links) > affiliate.MAX_LINKS:
        problems.append(f"{rel}: {len(links)} amazon links, at most {affiliate.MAX_LINKS}")
    for m in links:
        href = htmllib.unescape(m.group(1))
        parts = urlsplit(href)
        if f"{parts.scheme}://{parts.netloc}{parts.path}" != affiliate.SEARCH_URL:
            problems.append(f"{rel}: {href} is not a plain Amazon search")
        if parse_qs(parts.query).get("tag") != [tag]:
            problems.append(f"{rel}: {href} does not carry tag {tag}")
        rel_attr = REL_ATTR.search(m.group(0))
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if not {"sponsored", "nofollow", "noopener"} <= tokens:
            problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
    first = links[0].start()
    disclosure = text.rfind(affiliate.DISCLOSURE, 0, first)
    if disclosure < 0:
        problems.append(f"{rel}: no disclosure before the first amazon link")
    elif re.search(r"<h[1-6]\b|</section>", text[disclosure:first]):
        problems.append(f"{rel}: the disclosure is not next to the links")
    method = text.find('id="kt-method"')
    if method < 0 or text.find("</section>", method) > first:
        problems.append(f"{rel}: amazon links come before the end of the method section")
    return problems


def main(root: Path, amazon_tag: str = "") -> int:
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
    problems += check_affiliate(root, html, amazon_tag)
    for p in problems[:50]:
        print(p, file=sys.stderr)
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    print(f"check_site: {len(html)} pages, {len(locs)} sitemap URLs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="check_site")
    ap.add_argument("site_dir", type=Path)
    ap.add_argument("--amazon-tag", default="")
    args = ap.parse_args()
    sys.exit(main(args.site_dir, args.amazon_tag))
