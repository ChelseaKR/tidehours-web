"""Checks a full build (`make build-site`): every catalog station has a page,
every page carries the disclaimers and the NOAA credit, nothing absent
renders as a value, every internal link and sitemap entry resolves, no page
is unreasonably large, and the sitemap lists exactly the pages that may be
indexed: a subordinate station whose corrections leave its times and high
tides as its reference's (a twin) carries noindex and a canonical link to
the reference's page and is left out (docs/DECISIONS.md 0033, superseding
0013), and so do region pages of fewer than three stations (0022). A station page shows a type of tide exactly when
its own constants give one, and it is the computed one (0014). The
king-tide pages' summary of the runs coming up, their titles, and the
king-tide links on station pages match the computed season for the day the
pages were built (0015), and each state's winter calendar lists exactly
the computed runs by month (0024). Amazon affiliate links appear only when a tag is
configured, only on the English king-tide page, after its method section,
tagged, with rel="sponsored nofollow noopener" and Amazon's disclosure right
before them; with no tag, "amazon" appears nowhere in the build (0016). The
link to the Tide Hours shop on Etsy appears only when a shop address is
configured, once on the About page and once on the English king-tide page,
with that exact address; with none, "etsy" appears nowhere (0029). A
station whose printed booklet is listed (src/tidehours/copy/booklets.json)
and whose year is not over links to it once, on its own page, with exactly
https://www.amazon.com/dp/ASIN; that sentence is the one exception to the
Amazon rules above, and with no booklet listed they are unchanged (0030).
In the same way, a station whose printable calendar is listed
(src/tidehours/copy/calendars.json) and whose year is not over links to it
once, on its own page, with exactly https://www.etsy.com/listing/ID, after
the booklet sentence when there is one; that sentence is the one exception
to the Etsy rules above, and the privacy page names the Etsy links by what
the build shows (0035). A station whose printable poster is listed
(src/tidehours/copy/posters.json) links to it in the same way, after the
calendar sentence when there is one. While any station page shows a
calendar or poster link, tide-calendars/ lists exactly those towns, by
state and town, each with a link to its station page and the same plain
link to each listing, and every English page's footer links to it once;
otherwise there is no such page and no link to one (0037).
Every station page has a sun and moon line for each of its two days, and it
is the one sky.py computes for that station and date: a day without a
sunrise, sunset, civil twilight, moonrise or moonset says so in words, and
no line shows "00:00" (0019). Every station page has one next-tide line, in
its answer box, and it is the first day's highs and lows as that day's table
lists them, in order, by date, or says in words that the day has none (0038).
Each state page lists its regions once each, in coast order, and each region
page's row for a station shows that station page's first-day highs and lows,
for the date its heading names (0039).

    uv run python scripts/check_site.py SITE_DIR [--amazon-tag TAG] [--print-shop-url URL] [--booklets FILE]
                                       [--calendars FILE] [--posters FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as htmllib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tidehours import affiliate, booklets, calendars, kingtides, ktformat, posters, printables, printshop, site
from tidehours.catalog import Catalog, Station, load
from tidehours.days import sky_text
from tidehours.sky import moon_day, moon_times, sun_day

HREF = re.compile(r'(?:href|src)="(/[^"#?]*)')
LOC = re.compile(r"<loc>https://tidehours\.com/([^<]*)</loc>")
SCRIPT = re.compile(r"<script.*?</script>", re.S)
BAD = ("None", "NaN", "nan ft", "undefined", "{{", "{place}", "{id}", "{date}")
MAX_PAGE_BYTES = 120_000
NOINDEX = '<meta name="robots" content="noindex,follow">'
CANONICAL = re.compile(r'<link rel="canonical" href="https://[^/"]+/([^"]*)">')
TIDE_TYPE = re.compile(r'data-tide-type="([^"]*)"')
STATION_DATE = re.compile(r'data-station-date="(\d{4}-\d{2}-\d{2})"')
KT_NEXT = re.compile(r'data-kt-next="([^"]*)"')
KT_RUN = re.compile(r'data-kt-run="([^"]*)"')
KT_CAL = re.compile(r'data-kt-cal="([^"]*)"')
KT_CAL_MONTH = re.compile(r'data-kt-cal-month="(\d{4}-\d{2})"')
TITLE = re.compile(r"<title>([^<]*)</title>")
AMAZON_A = re.compile(r'<a\b[^>]*\bhref="(https?://[^"]*amazon\.[^"]*)"[^>]*>', re.I)
REL_ATTR = re.compile(r'\brel="([^"]*)"')
JSON_LD = re.compile(r'<script type="application/ld\+json">.*?</script>', re.S)
SKY = re.compile(r'<p class="sky" data-sky="([^"]*)">(.*?)</p>', re.S)
TAG = re.compile(r"<[^>]+>")
BOOKLET_P = re.compile(r'<p class="booklet"[^>]*>.*?</p>', re.S)
CALENDAR_P = re.compile(r'<p class="calendar"[^>]*>.*?</p>', re.S)
POSTER_P = re.compile(r'<p class="poster"[^>]*>.*?</p>', re.S)
PRINTABLE_LI = re.compile(r'<li data-printable="([^"]*)">(.*?)</li>', re.S)
LINK_TEXT = re.compile(r'<a\b[^>]*\bhref="([^"]*)"[^>]*>(.*?)</a>', re.S)
H1 = re.compile(r"<h1>(.*?)</h1>", re.S)
MAIN_P = re.compile(r"<p(?: [^>]*)?>(.*?)</p>", re.S)
ANY_A = re.compile(r"<a\b[^>]*>", re.I)
HREF_ATTR = re.compile(r'\bhref="([^"]*)"')
NEXT_P = re.compile(r'<p class="next" id="next">(.*?)</p>', re.S)
DAY_SECTION = re.compile(r'<section class="day"[^>]*\bdata-date="(\d{4}-\d{2}-\d{2})">(.*?)</section>', re.S)
EVENT_ROW = re.compile(
    r'<tr class="ev-(high|low)"><th scope="row">(High|Low)</th><td><time datetime="([^"]*)">([^<]*)</time></td>'
)


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
    """A twin station's page (site.indexable) carries noindex and a
    canonical link to its reference station's page, and every other station
    page carries neither; region pages of fewer than
    site.REGION_MIN_STATIONS stations carry noindex and the rest do not; the
    sitemap and lastmod.json list exactly the pages without noindex."""
    problems: list[str] = []
    for s in stations:
        f = root / "stations" / s.id / "index.html"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        twin = not site.indexable(s)
        if (NOINDEX in text) != twin:
            kind = "twin" if twin else "subordinate" if s.is_subordinate else "harmonic"
            problems.append(f"stations/{s.id}: a {kind} station needs {'noindex' if twin else 'no noindex'}")
        canonical = CANONICAL.search(text)
        want_path = f"stations/{s.twin_of}/" if twin else f"stations/{s.id}/"
        if canonical is None or canonical.group(1) != want_path:
            got = canonical.group(1) if canonical else "none"
            problems.append(f"stations/{s.id}: canonical {got}, expected {want_path}")
    for st in site.group(stations):
        for r in st.regions:
            f = root / r.path / "index.html"
            if f.exists() and (NOINDEX in f.read_text(encoding="utf-8")) == site.region_indexable(r):
                want = "no noindex" if site.region_indexable(r) else "noindex"
                problems.append(f"{r.path}: a region of {len(r.stations)} station(s) needs {want}")
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


def check_sky(root: Path, cat: Catalog) -> list[str]:
    """Each station page's two days each carry the sun and moon line that
    sky.py computes for the station's position, zone and date, in that
    order, and nothing else in a sky line: no placeholder time."""
    problems: list[str] = []
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        dated = STATION_DATE.findall(text)
        if len(dated) != 1:
            problems.append(f"stations/{s.id}: no station date")
            continue
        first = dt.date.fromisoformat(dated[0])
        days = [first, first + dt.timedelta(days=1)]
        shown = [(d, " ".join(htmllib.unescape(TAG.sub(" ", inner)).split())) for d, inner in SKY.findall(text)]
        want = [
            (
                d.isoformat(),
                sky_text(sun_day(s.lat, s.lon, s.tz, d), moon_day(s.tz, d), moon_times(s.lat, s.lon, s.tz, d)),
            )
            for d in days
        ]
        if shown != want:
            problems.append(f"stations/{s.id}: sun and moon {shown or 'missing'}, expected {want}")
        problems += [f"stations/{s.id}: {d}: a sky line shows 00:00" for d, line in shown if "00:00" in line]
    return problems


def next_sentence(date: dt.date, events: list[tuple[str, str]]) -> str:
    """The next-tide line a station page is built with, from its first
    day's (kind, time) rows: "Friday, Nov 13, in order: high 2:25 AM, low
    5:30 AM." or "Friday, Nov 13: no high or low tide predicted." Written
    out here, not taken from days.py, so the check does not trust the code
    it checks."""
    when = f"{date.strftime('%A')}, {date.strftime('%b')} {date.day}"
    if not events:
        return f"{when}: no high or low tide predicted."
    return f"{when}, in order: " + ", ".join(f"{kind.lower()} {time}" for kind, time in events) + "."


def check_next(root: Path, cat: Catalog) -> list[str]:
    """Each station page has exactly one next-tide line (p#next), inside its
    answer box, and it says the first day's highs and lows exactly as that
    day's table lists them, in order, with no placeholder (docs/DECISIONS.md
    0038). The page's script may replace it in the browser; the build's
    words are what crawlers and readers without the script get."""
    problems: list[str] = []
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if not f.exists():
            continue
        body = SCRIPT.sub("", f.read_text(encoding="utf-8"))
        where = f"stations/{s.id}"
        lines = list(NEXT_P.finditer(body))
        if len(lines) != 1:
            problems.append(f"{where}: {len(lines)} next-tide lines, exactly 1 expected")
            continue
        line = lines[0]
        answer = body.find('<div class="answer">')
        if not 0 <= answer < line.start() < line.end() <= body.find("</div>", answer):
            problems.append(f"{where}: the next-tide line is not in the answer box")
        dated = STATION_DATE.findall(body)
        first = DAY_SECTION.search(body)
        if len(dated) != 1 or first is None or first.group(1) != dated[0]:
            problems.append(f"{where}: no first day to check the next-tide line against")
            continue
        date = dt.date.fromisoformat(first.group(1))
        rows = EVENT_ROW.findall(first.group(2))
        bad_rows = [r for r in rows if r[0] != r[1].lower()]
        if bad_rows or len(rows) != first.group(2).count('<tr class="ev-'):
            problems.append(f"{where}: the first day's table has rows the check cannot read: {bad_rows}")
        shown = " ".join(htmllib.unescape(TAG.sub("", line.group(1))).split())
        want = next_sentence(date, [(kind, time) for _, kind, _, time in rows])
        if shown != want:
            problems.append(f"{where}: next-tide line {shown!r}, expected {want!r}")
        problems += [f"{where}: the next-tide line contains {b!r}" for b in BAD if b in shown]
    return problems


HUB_DAY = re.compile(r'<h2 class="hub-day" data-date="(\d{4}-\d{2}-\d{2})">')
HUB_ROW = re.compile(r'<li data-station="([^"]+)">(.*?)</li>', re.S)
REGION_SECTION = re.compile(r'<section aria-labelledby="(r-[^"]+)">')


def hub_times(events: list[tuple[str, str]]) -> str:
    """A region page row's times, as its text reads, from a station page's
    first-day (kind, time) rows: "High 2:25 AM, 11:34 AM Low 5:30 AM",
    "High 2:25 AM no low tide", or "no high or low tide predicted". Written
    out here, not taken from the template."""
    if not events:
        return "no high or low tide predicted"
    parts = []
    for kind in ("High", "Low"):
        times = [t for k, t in events if k == kind]
        parts.append(f"{kind} {', '.join(times)}" if times else f"no {kind.lower()} tide")
    return " ".join(parts)


def check_hubs(root: Path, cat: Catalog) -> list[str]:
    """Each state page lists every one of its regions once, in the order
    site.coast_order gives (copy/region_order.json, else north to south),
    with the stations without a region last. Each region page lists exactly
    its stations; when it has a dated heading, every station page's date is
    that date, and each row's times are that station page's first-day
    highs and lows, in order; without one, no row shows times
    (docs/DECISIONS.md 0039)."""
    problems: list[str] = []
    order = site.region_order()
    for st in site.group(cat.stations):
        f = root / st.path / "index.html"
        if not f.is_file():
            continue
        want = ["r-" + r.slug for r in site.coast_order(st, order)] + (["r-none"] if st.unregioned else [])
        shown = REGION_SECTION.findall(f.read_text(encoding="utf-8"))
        if shown != want:
            problems.append(f"{st.path}: regions {shown}, expected {want}")
        for r in st.regions:
            g = root / r.path / "index.html"
            if g.is_file():
                problems += _check_hub(r, g.read_text(encoding="utf-8"), root)
    return problems


def _check_hub(r: site.Region, text: str, root: Path) -> list[str]:
    problems: list[str] = []
    rows = HUB_ROW.findall(text)
    if sorted(sid for sid, _ in rows) != sorted(s.id for s in r.stations) or len(rows) != len(r.stations):
        problems.append(f"{r.path}: rows {[sid for sid, _ in rows]}, expected the region's {len(r.stations)} stations")
    dated = HUB_DAY.findall(text)
    if len(dated) > 1:
        problems.append(f"{r.path}: {len(dated)} dated headings")
    for sid, row in rows:
        times = row.split('<span class="hub-times">', 1)
        if not dated:
            if len(times) > 1:
                problems.append(f"{r.path}: {sid}: times under no dated heading")
            continue
        station = root / "stations" / sid / "index.html"
        if not station.is_file():
            continue
        page = SCRIPT.sub("", station.read_text(encoding="utf-8"))
        first = DAY_SECTION.search(page)
        if first is None or first.group(1) != dated[0]:
            problems.append(f"{r.path}: {sid}: its page's first day is not {dated[0]}")
            continue
        want = hub_times([(kind, time) for _, kind, _, time in EVENT_ROW.findall(first.group(2))])
        got = " ".join(htmllib.unescape(TAG.sub(" ", times[1])).split()) if len(times) > 1 else "none"
        if got != want:
            problems.append(f"{r.path}: {sid}: times {got!r}, expected {want!r}")
        problems += [f"{r.path}: {sid}: contains {b!r}" for b in BAD if b in got]
    return problems


def check_king_calendar(root: Path, cat: Catalog) -> list[str]:
    """Each state's winter king-tide calendar lists every month of the
    window, in order, and in each exactly the runs computed for it; a month
    with none says so in words (docs/DECISIONS.md 0024)."""
    problems: list[str] = []
    seasons = site.king_tide_context(cat)["seasons"]
    for code in kingtides.CALENDAR_STATES:
        rel = kingtides.calendar_path(code)
        f = root / rel / "index.html"
        if not f.is_file():
            problems.append(f"{rel}: no page")
            continue
        text = f.read_text(encoding="utf-8")
        months = kingtides.calendar(seasons, code)
        want_months = [f"{m.year}-{m.month:02d}" for m in months]
        if KT_CAL_MONTH.findall(text) != want_months:
            problems.append(f"{rel}: months {KT_CAL_MONTH.findall(text)}, expected {want_months}")
        want = [u.stamp() for m in months for u in m.runs]
        shown = KT_CAL.findall(text)
        if shown != want:
            extra = [x for x in shown if x not in want]
            missing = [w for w in want if w not in shown]
            problems.append(f"{rel}: runs differ: shown but not computed {extra}, computed but not shown {missing}")
        empty = sum(1 for m in months if not m.runs)
        if text.count("stations does a run of the year's highest predicted tides peak in") != empty:
            problems.append(f"{rel}: {empty} month(s) without a run, not each said in words")
    return problems


def booklet_pages(root: Path, listed: dict[str, booklets.Booklet]) -> tuple[dict[str, booklets.Booklet], list[str]]:
    """The station pages of this build that must link to a booklet, as page
    path -> booklet: each listed station that has a page, unless the page's
    own date is past the booklet's year (docs/DECISIONS.md 0030)."""
    want: dict[str, booklets.Booklet] = {}
    problems: list[str] = []
    for station_id, booklet in listed.items():
        rel = f"stations/{station_id}/index.html"
        if not (root / rel).is_file():
            continue
        dates = STATION_DATE.findall((root / rel).read_text(encoding="utf-8"))
        if len(dates) != 1:
            problems.append(f"{rel}: no date to tell whether its booklet's year is over")
        elif booklets.shown(booklet, dt.date.fromisoformat(dates[0])):
            want[rel] = booklet
    return want, problems


def _check_booklet(rel: str, text: str, want: booklets.Booklet | None) -> tuple[str, list[str]]:
    """One page's booklet sentence. Returns the page without the sentence,
    for the Amazon rules that apply to everything else, and the problems:
    a sentence on a page that is due none; or, on a page that is due one,
    none or more than one, more than one link in it, an address that is not
    exactly the booklet's, a rel other than noopener, a click event, or a
    place before the tide tables or after the page's closing notes."""
    blocks = list(BOOKLET_P.finditer(text))
    if want is None:
        return text, ([f"{rel}: a booklet link on a page that is due none"] if blocks else [])
    if len(blocks) != 1:
        return BOOKLET_P.sub("", text), [f"{rel}: {len(blocks)} booklet links, exactly 1 expected"]
    problems: list[str] = []
    found = blocks[0]
    anchors = ANY_A.findall(found.group(0))
    if len(anchors) != 1 or found.group(0).count("http") != 1:
        problems.append(f"{rel}: the booklet sentence has {len(anchors)} links, exactly 1 expected")
    for a in anchors:
        href_attr = HREF_ATTR.search(a)
        href = htmllib.unescape(href_attr.group(1)) if href_attr else ""
        if href != want.url:
            problems.append(f"{rel}: {href} is not the booklet's address, {want.url}")
        rel_attr = REL_ATTR.search(a)
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if tokens != set(booklets.REL.split()):
            problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
        if "data-ga" in a:
            problems.append(f"{rel}: the booklet link carries a click event")
    last_day = text.rfind('<section class="day"')
    if not 0 <= last_day < text.find("</section>", last_day) < found.start() < text.find('id="what"'):
        problems.append(f"{rel}: the booklet link is not between the tide tables and the closing notes")
    return text[: found.start()] + text[found.end() :], problems


def check_affiliate(
    root: Path, html: list[Path], tag: str, booklet_links: dict[str, booklets.Booklet] | None = None
) -> list[str]:
    """With no tag, "amazon" appears nowhere. With one, only the English
    king-tide page links to Amazon: at most MAX_LINKS links, each a plain
    tagged search with the configured tag and the required rel, after the
    method section, with the exact disclosure right before the first link
    (in the same section, no heading between). Never in JSON-LD, the sitemap,
    robots.txt, lastmod.json or llms.txt.

    The one exception (docs/DECISIONS.md 0030): `booklet_links`, from
    booklet_pages, names the station pages that are due a booklet sentence.
    That sentence is checked on its own (_check_booklet) and taken out of
    the page before the rules above run on the rest, so they hold for
    everything else, tag or no tag. While any page is due one, the privacy
    and terms pages may name Amazon in words, never with a link."""
    want = booklet_links or {}
    named = {p + "index.html" for p in booklets.MENTION_PAGES} if want else set()
    problems: list[str] = []
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        f = root / name
        if f.exists() and "amazon" in f.read_text(encoding="utf-8").lower():
            problems.append(f"{name}: mentions amazon")
    for f in html:
        rel = f.relative_to(root).as_posix()
        page = f.read_text(encoding="utf-8")
        text, found = _check_booklet(rel, page, want.get(rel))
        problems += found
        if not tag:
            low = text.lower()
            in_words_only = rel in named and not AMAZON_A.search(text) and "amazon.com" not in low
            if "amazon" in low and not in_words_only:
                problems.append(f"{rel}: mentions amazon with no tag set")
            continue
        if any("amazon" in block.lower() for block in JSON_LD.findall(page)):
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


ETSY_A = re.compile(r'<a\b[^>]*\bhref="(https?://[^"]*etsy\.com[^"]*)"[^>]*>', re.I)


def calendar_pages(
    root: Path, listed: dict[str, calendars.Calendar]
) -> tuple[dict[str, calendars.Calendar], list[str]]:
    """The station pages of this build that must link to a calendar, as page
    path -> calendar: each listed station that has a page, unless the page's
    own date is past the calendar's year (docs/DECISIONS.md 0035)."""
    want: dict[str, calendars.Calendar] = {}
    problems: list[str] = []
    for station_id, calendar in listed.items():
        rel = f"stations/{station_id}/index.html"
        if not (root / rel).is_file():
            continue
        dates = STATION_DATE.findall((root / rel).read_text(encoding="utf-8"))
        if len(dates) != 1:
            problems.append(f"{rel}: no date to tell whether its calendar's year is over")
        elif calendars.shown(calendar, dt.date.fromisoformat(dates[0])):
            want[rel] = calendar
    return want, problems


def _check_calendar(rel: str, text: str, want: calendars.Calendar | None) -> tuple[str, list[str]]:
    """One page's calendar sentence. Returns the page without the sentence,
    for the Etsy rules that apply to everything else, and the problems: a
    sentence on a page that is due none; or, on a page that is due one, none
    or more than one, more than one link in it, an address that is not
    exactly the listing's, a rel other than noopener, a click event, a place
    before the tide tables or after the page's closing notes, or a place
    before the booklet sentence."""
    blocks = list(CALENDAR_P.finditer(text))
    if want is None:
        return text, ([f"{rel}: a calendar link on a page that is due none"] if blocks else [])
    if len(blocks) != 1:
        return CALENDAR_P.sub("", text), [f"{rel}: {len(blocks)} calendar links, exactly 1 expected"]
    problems: list[str] = []
    found = blocks[0]
    anchors = ANY_A.findall(found.group(0))
    if len(anchors) != 1 or found.group(0).count("http") != 1:
        problems.append(f"{rel}: the calendar sentence has {len(anchors)} links, exactly 1 expected")
    for a in anchors:
        href_attr = HREF_ATTR.search(a)
        href = htmllib.unescape(href_attr.group(1)) if href_attr else ""
        if href != want.url:
            problems.append(f"{rel}: {href} is not the calendar's address, {want.url}")
        rel_attr = REL_ATTR.search(a)
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if tokens != set(calendars.REL.split()):
            problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
        if "data-ga" in a:
            problems.append(f"{rel}: the calendar link carries a click event")
    last_day = text.rfind('<section class="day"')
    if not 0 <= last_day < text.find("</section>", last_day) < found.start() < text.find('id="what"'):
        problems.append(f"{rel}: the calendar link is not between the tide tables and the closing notes")
    booklet = BOOKLET_P.search(text)
    if booklet and booklet.start() > found.start():
        problems.append(f"{rel}: the calendar link comes before the booklet link")
    return text[: found.start()] + text[found.end() :], problems


def poster_pages(root: Path, listed: dict[str, posters.Poster]) -> tuple[dict[str, posters.Poster], list[str]]:
    """The station pages of this build that must link to a poster, as page
    path -> poster: each listed station that has a page, unless the page's
    own date is past the poster's year (docs/DECISIONS.md 0037)."""
    want: dict[str, posters.Poster] = {}
    problems: list[str] = []
    for station_id, poster in listed.items():
        rel = f"stations/{station_id}/index.html"
        if not (root / rel).is_file():
            continue
        dates = STATION_DATE.findall((root / rel).read_text(encoding="utf-8"))
        if len(dates) != 1:
            problems.append(f"{rel}: no date to tell whether its poster's year is over")
        elif posters.shown(poster, dt.date.fromisoformat(dates[0])):
            want[rel] = poster
    return want, problems


def _check_poster(rel: str, text: str, want: posters.Poster | None) -> tuple[str, list[str]]:
    """One page's poster sentence, held to the calendar sentence's rules
    (_check_calendar). Returns the page without the sentence, and the
    problems: a sentence on a page that is due none; or, on a page that is
    due one, none or more than one, more than one link in it, an address
    that is not exactly the listing's, a rel other than noopener, a click
    event, a place before the tide tables or after the page's closing
    notes, or a place before the booklet or calendar sentence. It runs
    before _check_calendar, on the page that still has the calendar
    sentence."""
    blocks = list(POSTER_P.finditer(text))
    if want is None:
        return text, ([f"{rel}: a poster link on a page that is due none"] if blocks else [])
    if len(blocks) != 1:
        return POSTER_P.sub("", text), [f"{rel}: {len(blocks)} poster links, exactly 1 expected"]
    problems: list[str] = []
    found = blocks[0]
    anchors = ANY_A.findall(found.group(0))
    if len(anchors) != 1 or found.group(0).count("http") != 1:
        problems.append(f"{rel}: the poster sentence has {len(anchors)} links, exactly 1 expected")
    for a in anchors:
        href_attr = HREF_ATTR.search(a)
        href = htmllib.unescape(href_attr.group(1)) if href_attr else ""
        if href != want.url:
            problems.append(f"{rel}: {href} is not the poster's address, {want.url}")
        rel_attr = REL_ATTR.search(a)
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if tokens != set(calendars.REL.split()):
            problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
        if "data-ga" in a:
            problems.append(f"{rel}: the poster link carries a click event")
    last_day = text.rfind('<section class="day"')
    if not 0 <= last_day < text.find("</section>", last_day) < found.start() < text.find('id="what"'):
        problems.append(f"{rel}: the poster link is not between the tide tables and the closing notes")
    earlier = [m for m in (BOOKLET_P.search(text), CALENDAR_P.search(text)) if m is not None]
    if any(m.start() > found.start() for m in earlier):
        problems.append(f"{rel}: the poster link comes before the booklet or calendar link")
    return text[: found.start()] + text[found.end() :], problems


def _station_ids(pages: dict[str, Any] | None) -> dict[str, Any]:
    """calendar_pages' or poster_pages' value, keyed by station id."""
    return {rel.split("/")[1]: item for rel, item in (pages or {}).items()}


def check_printables(
    root: Path,
    html: list[Path],
    cat: Catalog,
    calendar_links: dict[str, calendars.Calendar] | None = None,
    poster_links: dict[str, posters.Poster] | None = None,
) -> list[str]:
    """While a station page of this build is due a calendar or poster
    sentence, tide-calendars/ exists and is exactly the page printables.py
    gives for those sentences: its title, heading and two paragraphs, and
    each town in order with a link to its station page and one link to each
    of its listings, `https://www.etsy.com/listing/ID` with rel="noopener"
    and no click event. Etsy is linked nowhere else on it and is not in its
    JSON-LD. Every English page links to it once, in the footer, and the
    Spanish page does not. With no sentence due, there is no such page and
    no link to one (docs/DECISIONS.md 0037)."""
    calendar_of, poster_of = _station_ids(calendar_links), _station_ids(poster_links)
    stations = {sid: s for sid in {*calendar_of, *poster_of} if (s := cat.station(sid)) is not None}
    listing = printables.block(calendar_of, poster_of, stations)
    rel = printables.PATH + "index.html"
    f = root / rel
    problems: list[str] = []
    if listing is None:
        if f.is_file():
            problems.append(f"{rel}: a list of calendars and posters in a build with none to list")
    elif not f.is_file():
        problems.append(f"{rel}: no page, though station pages link to a calendar or poster")
    else:
        problems += _check_printables_page(rel, f.read_text(encoding="utf-8"), listing)
    href = f'href="/{printables.PATH}"'
    for page in html:
        text = page.read_text(encoding="utf-8")
        want = 1 if listing is not None and '<html lang="en">' in text else 0
        if text.count(href) != want:
            where = page.relative_to(root).as_posix()
            problems.append(f"{where}: {text.count(href)} links to {printables.PATH}, exactly {want} expected")
    return problems


def _check_printables_page(rel: str, text: str, listing: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    main = text[text.find("<main") : text.find("</main>")]
    shown = [
        (station_id, [(htmllib.unescape(href), htmllib.unescape(name)) for href, name in LINK_TEXT.findall(inner)])
        for station_id, inner in PRINTABLE_LI.findall(main)
    ]
    want = [
        (town.station_id, [(f"/stations/{town.station_id}/", town.name), *((i.url, i.title) for i in town.items)])
        for state in listing["states"]
        for town in state.towns
    ]
    if shown != want:
        extra = [x for x in shown if x not in want]
        missing = [w for w in want if w not in shown]
        problems.append(
            f"{rel}: the towns listed differ, or their order: shown but not due {extra}, due but not shown {missing}"
        )
    links = list(ETSY_A.finditer(text))
    if len(links) != sum(len(town.items) for state in listing["states"] for town in state.towns):
        problems.append(f"{rel}: {len(links)} etsy links, one for each listing expected")
    for m in links:
        rel_attr = REL_ATTR.search(m.group(0))
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if tokens != set(listing["rel"].split()):
            problems.append(f"{rel}: {htmllib.unescape(m.group(1))} rel is {sorted(tokens)}")
        if "data-ga" in m.group(0):
            problems.append(f"{rel}: a listing link carries a click event")
    if any("etsy" in block.lower() for block in JSON_LD.findall(text)):
        problems.append(f"{rel}: etsy in JSON-LD")
    title = [htmllib.unescape(t) for t in TITLE.findall(text)]
    if title != [f"{listing['title']} | Tide Hours"]:
        problems.append(f"{rel}: title {title}")
    words = [htmllib.unescape(x) for x in (*H1.findall(main), *MAIN_P.findall(main))]
    if words != [listing["heading"], listing["intro"], listing["how"]]:
        problems.append(f"{rel}: the heading and the two paragraphs are {words}")
    return problems


def check_print_shop(
    root: Path,
    html: list[Path],
    url: str,
    calendar_links: dict[str, calendars.Calendar] | None = None,
    poster_links: dict[str, posters.Poster] | None = None,
) -> list[str]:
    """With no shop address, "etsy" appears nowhere. With one, the About page
    and the English king-tide page each link to it exactly once, with that
    exact address and rel="noopener"; the privacy and terms pages may name
    Etsy without linking; no other page mentions it. Never in JSON-LD, the
    sitemap, robots.txt, lastmod.json or llms.txt (docs/DECISIONS.md 0029).

    The one exception (docs/DECISIONS.md 0035): `calendar_links`, from
    calendar_pages, names the station pages that are due a calendar
    sentence. That sentence is checked on its own (_check_calendar) and
    taken out of the page before the rules above run on the rest, so they
    hold for everything else, shop address or none. While any page is due
    one, the privacy and terms pages may name Etsy in words, never with a
    link. The privacy page says exactly what printables.notice says for this
    build, and nothing about Etsy when the build has no Etsy link.

    The same holds for `poster_links`, from poster_pages, and the poster
    sentence (_check_poster). While any page is due either sentence, the
    page that lists them all, tide-calendars/, is left to check_printables
    and is not held to the rules above (docs/DECISIONS.md 0037)."""
    want = calendar_links or {}
    want_poster = poster_links or {}
    which = printables.kind(bool(want), bool(want_poster))
    named = {p + "index.html" for p in printshop.MENTION_PAGES} if which else set()
    problems: list[str] = []
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        f = root / name
        if f.exists() and "etsy" in f.read_text(encoding="utf-8").lower():
            problems.append(f"{name}: mentions etsy")
    link_pages = {p + "index.html" for p in printshop.PAGES}
    for f in html:
        rel = f.relative_to(root).as_posix()
        text, found = _check_poster(rel, f.read_text(encoding="utf-8"), want_poster.get(rel))
        problems += found
        text, found = _check_calendar(rel, text, want.get(rel))
        problems += found
        if which and rel == printables.PATH + "index.html":
            continue
        if "etsy" not in text.lower():
            if url and rel in link_pages:
                problems.append(f"{rel}: no shop link with a shop address set")
        elif not url:
            in_words_only = rel in named and not ETSY_A.search(text) and "etsy.com" not in text.lower()
            if not in_words_only:
                problems.append(f"{rel}: mentions etsy with no shop address set")
        else:
            problems += _check_print_shop_page(rel, text, url, rel in link_pages)
    problems += _check_shop_notice(root, url, which)
    return problems


SHOP_NOTICE = re.compile(r'<h2 id="shop">(.*?)</h2>\s*<p>(.*?)</p>', re.S)


def _check_shop_notice(root: Path, url: str, which: str | None) -> list[str]:
    """The privacy page's section on the Etsy links is exactly the one
    printables.notice gives for this build: none with no Etsy link, the print
    shop's own sentence with only the shop link, and the sentence that names
    the list of calendars and posters and the station pages while a calendar
    or poster link shows (docs/DECISIONS.md 0035, 0037). `which` is
    printables.kind's value."""
    f = root / "privacy" / "index.html"
    if not f.is_file():
        return []
    expect = printables.notice(which, printshop.block(url))
    found = [(htmllib.unescape(h), htmllib.unescape(p)) for h, p in SHOP_NOTICE.findall(f.read_text(encoding="utf-8"))]
    want = [(expect["heading"], expect["body"])] if expect else []
    if found != want:
        return [f"privacy/index.html: the shop section is {found or 'missing'}, expected {want or 'none'}"]
    return []


def _check_print_shop_page(rel: str, text: str, url: str, link_page: bool) -> list[str]:
    """One page that mentions Etsy, in a build with a shop address set."""
    problems: list[str] = []
    if any("etsy" in block.lower() for block in JSON_LD.findall(text)):
        problems.append(f"{rel}: etsy in JSON-LD")
    links = list(ETSY_A.finditer(text))
    if not link_page:
        if links:
            problems.append(f"{rel}: etsy link outside {', '.join(printshop.PAGES)}")
        elif rel not in {p + "index.html" for p in printshop.MENTION_PAGES}:
            problems.append(f"{rel}: mentions etsy")
        return problems
    if len(links) != 1:
        problems.append(f"{rel}: {len(links)} etsy links, exactly 1 expected")
    for m in links:
        href = htmllib.unescape(m.group(1))
        if href != url:
            problems.append(f"{rel}: {href} is not the configured shop address")
        found = re.search(r'\brel="([^"]*)"', m.group(0))
        tokens = set(found.group(1).split()) if found else set()
        if tokens != set(printshop.REL.split()):
            problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
    return problems


def main(
    root: Path,
    amazon_tag: str = "",
    print_shop_url: str = "",
    booklets_file: Path | None = None,
    calendars_file: Path | None = None,
    posters_file: Path | None = None,
) -> int:
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
    problems += check_king_calendar(root, cat)
    booklet_links, undated = booklet_pages(root, booklets.load(booklets_file))
    problems += undated
    problems += check_affiliate(root, html, amazon_tag, booklet_links)
    calendar_links, undated = calendar_pages(root, calendars.load(calendars_file))
    problems += undated
    poster_links, undated = poster_pages(root, posters.load(posters_file))
    problems += undated
    problems += check_print_shop(root, html, print_shop_url, calendar_links, poster_links)
    problems += check_printables(root, html, cat, calendar_links, poster_links)
    problems += check_sky(root, cat)
    problems += check_next(root, cat)
    problems += check_hubs(root, cat)
    for p in problems[:50]:
        print(p, file=sys.stderr)
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    print(f"check_site: {len(html)} pages, {len(locs)} sitemap URLs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="check_site")
    ap.add_argument("site_dir", type=Path)
    ap.add_argument("--amazon-tag", default="")
    ap.add_argument("--print-shop-url", default="")
    ap.add_argument("--booklets", type=Path, help="the booklet list the site was built with, if not the committed one")
    ap.add_argument(
        "--calendars", type=Path, help="the calendar list the site was built with, if not the committed one"
    )
    ap.add_argument("--posters", type=Path, help="the poster list the site was built with, if not the committed one")
    args = ap.parse_args()
    sys.exit(main(args.site_dir, args.amazon_tag, args.print_shop_url, args.booklets, args.calendars, args.posters))
