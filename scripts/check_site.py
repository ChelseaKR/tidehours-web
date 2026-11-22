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
station whose printed tide tables are listed (src/tidehours/copy/booklets.json)
and whose year is not over links to each book once, on its own page, in the
list's order, with exactly https://www.amazon.com/dp/ASIN; those sentences
are the one exception to the Amazon rules above, and with no book listed
they are unchanged (0030).
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
While a live entry of src/tidehours/copy/gifts.json shows (its year not
over), tide-gifts/ lists exactly those entries, the calendars and posters
above, and the custom print when the shop address is set, by kind and
town, each with the same plain link; a link to any listing it does not list, which covers one not marked
live, fails the build. Every English page's footer links to it once, and
the privacy page names it among the pages that link to Etsy and Amazon
(0041).
Every station page has a sun and moon line for each of its two days, and it
is the one sky.py computes for that station and date: a day without a
sunrise, sunset, civil twilight, moonrise or moonset says so in words, and
no line shows "00:00" (0019). Every station page has one next-tide line, in
its answer box, and it is the first day's highs and lows as that day's table
lists them, in order, by date, or says in words that the day has none (0038).
Each state page lists its regions once each, in coast order, and each region
page's row for a station shows that station page's first-day highs and lows,
for the date its heading names (0039). /places.json, the home page's find
list, names every station page of the build once, by its display name, and
the home page lists every state under its coast groups (0040).
Every page carries the share card (its own title and description, the
one 1200 x 630 share image, a large-image Twitter card) and links
favicon.ico, the apple-touch-icon and manifest.json, and those files are
at the root at their exact sizes, each under 200 KB (0042).
robots.txt lets Bingbot, OAI-SearchBot, ChatGPT-User, GPTBot, PerplexityBot
and ClaudeBot fetch every page in the sitemap, read the way those crawlers
read it (the group that names the crawler, else "*"; the longest matching
rule wins), and no sitemap page tells a crawler not to keep or quote it
(noarchive, nocache, nosnippet, max-snippet:0) (0048).

    uv run python scripts/check_site.py SITE_DIR [--amazon-tag TAG] [--print-shop-url URL] [--booklets FILE]
                                       [--calendars FILE] [--posters FILE] [--gifts FILE]
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

from tidehours import affiliate, booklets, calendars, gifts, kingtides, ktformat, posters, printables, printshop, site
from tidehours.catalog import Catalog, Station, load
from tidehours.days import sky_text
from tidehours.sky import moon_day, moon_times, sun_day

HREF = re.compile(r'(?:href|src)="(/[^"#?]*)')
LOC = re.compile(r"<loc>https://tidehours\.com/([^<]*)</loc>")
SCRIPT = re.compile(r"<script.*?</script>", re.S)
BAD = ("None", "NaN", "nan ft", "undefined", "{{", "{place}", "{id}", "{date}")
MAX_PAGE_BYTES = 120_000
NOINDEX = '<meta name="robots" content="noindex,follow">'
# Search and AI-answer crawlers that must be able to fetch every sitemap page
# (0048), by the names their owners publish: Bing's crawler; OpenAI's search
# crawler, its fetcher for a user's question and its training crawler;
# Perplexity's and Anthropic's crawlers. Changing this list is an owner
# decision.
CRAWLERS = ("bingbot", "OAI-SearchBot", "ChatGPT-User", "GPTBot", "PerplexityBot", "ClaudeBot")
# A robots meta value that stops a crawler keeping or quoting a page. Bing
# documents nocache and noarchive as limits on its chat answers.
QUOTE_LIMITS = ("noarchive", "nocache", "nosnippet", "max-snippet:0")
META = re.compile(r"<meta\b[^>]*>", re.I)
META_NAME = re.compile(r'\bname="([^"]*)"', re.I)
META_CONTENT = re.compile(r'\bcontent="([^"]*)"', re.I)
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
GIFT_ITEM = re.compile(r'<(li|p) data-gift="([^"]*)">(.*?)</\1>', re.S)
H2_TEXT = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
BUILT = re.compile(r"page built (\d{4}-\d{2}-\d{2}) \(UTC\)")
# What no word on the gifts page may be: a price, a discount, a rating or a
# claim (0029, 0030, 0041).
GIFT_FORBIDDEN = re.compile(r"[$%\u2605]|\b(sale|discount|free shipping|best|cheap|deals?|rated|official)\b", re.I)
# The share and icon tags every page carries, and the files they name, at
# their exact pixel sizes and each under MAX_IMAGE_BYTES (0042).
SHARE_TAGS = (
    '<meta property="og:image:type" content="image/png">',
    '<meta property="og:image:width" content="1200">',
    '<meta property="og:image:height" content="630">',
    '<meta property="og:image:alt" content="',
    '<meta name="twitter:card" content="summary_large_image">',
    '<link rel="icon" href="/favicon.ico" sizes="32x32">',
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
    '<link rel="manifest" href="/manifest.json">',
)
OG_IMAGE = re.compile(r'<meta property="og:image" content="https://[^/"]+/share\.png">')
OG_TITLE = re.compile(r'<meta property="og:title" content="([^"]*)">')
OG_DESCRIPTION = re.compile(r'<meta property="og:description" content="([^"]*)">')
OG_URL = re.compile(r'<meta property="og:url" content="https://[^/"]+/([^"]*)">')
DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)">')
SHARE_IMAGES = {
    "share.png": (1200, 630),
    "apple-touch-icon.png": (180, 180),
    "icon-192.png": (192, 192),
    "icon-512.png": (512, 512),
}
FAVICON_ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
MAX_IMAGE_BYTES = 200_000


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
    problems += check_share_tags(rel, text)
    for link in HREF.findall(text):
        target = root / link.lstrip("/")
        if not (target.is_file() or (target / "index.html").is_file()):
            problems.append(f"{rel}: broken link {link}")
    return problems


def check_share_tags(rel: str, text: str) -> list[str]:
    """The page's share card is its own title and description with the one
    share image, its og:url is its canonical URL (none on the 404 page), and
    it links the icons and the manifest (0042)."""
    problems = [f"{rel}: no {tag!r}" for tag in SHARE_TAGS if text.count(tag) != 1]
    if len(OG_IMAGE.findall(text)) != 1:
        problems.append(f"{rel}: no og:image of the share image")
    title, description = TITLE.findall(text), DESCRIPTION.findall(text)
    if OG_TITLE.findall(text) != title[:1] or len(title) != 1:
        problems.append(f"{rel}: og:title is not the page's title")
    if OG_DESCRIPTION.findall(text) != description[:1] or len(description) != 1:
        problems.append(f"{rel}: og:description is not the page's description")
    if OG_URL.findall(text) != CANONICAL.findall(text):
        problems.append(f"{rel}: og:url is not the canonical URL")
    return problems


def png_size(data: bytes) -> tuple[int, int] | None:
    """A PNG's width and height from its header, or None if it is not a PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def ico_sizes(data: bytes) -> list[tuple[int, int]]:
    """The sizes in an .ico file's directory (0 means 256), or [] if it is
    not one."""
    if data[:4] != b"\x00\x00\x01\x00":
        return []
    count = int.from_bytes(data[4:6], "little")
    entries = [data[6 + 16 * i : 8 + 16 * i] for i in range(count)]
    return [(e[0] or 256, e[1] or 256) for e in entries if len(e) == 2]


def check_share_files(root: Path) -> list[str]:
    """The share image and the icons are at the root at their exact sizes,
    each under MAX_IMAGE_BYTES, and the manifest names the two home-screen
    icons by their real sizes (0042)."""
    problems: list[str] = []
    for name, size in SHARE_IMAGES.items():
        f = root / name
        if not f.is_file():
            problems.append(f"no /{name}")
            continue
        data = f.read_bytes()
        if png_size(data) != size:
            problems.append(f"/{name} is {png_size(data)}, not {size}")
        if len(data) > MAX_IMAGE_BYTES:
            problems.append(f"/{name} is {len(data)} bytes")
    ico = root / "favicon.ico"
    if not ico.is_file() or ico_sizes(ico.read_bytes()) != FAVICON_ICO_SIZES:
        problems.append(f"/favicon.ico does not hold {FAVICON_ICO_SIZES}")
    elif ico.stat().st_size > MAX_IMAGE_BYTES:
        problems.append(f"/favicon.ico is {ico.stat().st_size} bytes")
    manifest = root / "manifest.json"
    icons = json.loads(manifest.read_text(encoding="utf-8")).get("icons", []) if manifest.is_file() else []
    for icon in icons:
        f = root / str(icon.get("src", "")).lstrip("/")
        named = tuple(int(n) for n in re.findall(r"\d+", str(icon.get("sizes", ""))))
        if not f.is_file() or png_size(f.read_bytes()) != named:
            problems.append(f"manifest.json: icon {icon} does not match its file")
    if sorted(str(i.get("src")) for i in icons) != ["/icon-192.png", "/icon-512.png"]:
        problems.append("manifest.json does not name /icon-192.png and /icon-512.png")
    return problems


def robots_rules(robots: str, crawler: str) -> list[tuple[str, str]]:
    """The Allow and Disallow rules of robots.txt that apply to one crawler
    (RFC 9309): those of every group that names it, else those of "*"."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    in_agents = False
    for raw in robots.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not in_agents:
                groups.append(([], []))
            groups[-1][0].append(value.lower())
            in_agents = True
            continue
        in_agents = False
        if key in ("allow", "disallow") and groups and value:
            groups[-1][1].append((key, value))
    name = crawler.lower()
    named = [g for g in groups if any(agent != "*" and agent in name for agent in g[0])]
    chosen = named or [g for g in groups if "*" in g[0]]
    return [rule for g in chosen for rule in g[1]]


def may_fetch(rules: list[tuple[str, str]], path: str) -> bool:
    """Whether the rules let a crawler fetch a path: the longest matching
    rule wins, Allow wins a tie, and no matching rule means yes. "*" matches
    any run of characters and a final "$" the end of the path.
    urllib.robotparser takes the first matching rule instead, which is not
    how Bing, Google or OpenAI read the file."""
    allowed, longest = True, -1
    for kind, pattern in rules:
        regex = re.escape(pattern).replace(r"\*", ".*")
        if regex.endswith(r"\$"):
            regex = regex[:-2] + "$"
        if re.match(regex, path) is None:
            continue
        if len(pattern) > longest or (len(pattern) == longest and kind == "allow"):
            allowed, longest = kind == "allow", len(pattern)
    return allowed


def quote_limits(page: str) -> list[str]:
    """The keep-or-quote limits a page's robots meta tags set for a search or
    AI-answer crawler, as "name: limit". A tag for Google alone (googlebot)
    is not one of them: it leaves the page open to every other crawler."""
    names = {"robots", *(c.lower() for c in CRAWLERS)}
    found = []
    for tag in META.findall(page):
        name, content = META_NAME.search(tag), META_CONTENT.search(tag)
        if name is None or content is None or name.group(1).lower() not in names:
            continue
        values = content.group(1).lower().replace(" ", "").split(",")
        found += [f"{name.group(1).lower()}: {limit}" for limit in QUOTE_LIMITS if limit in values]
    return found


def check_crawlers(root: Path) -> list[str]:
    """robots.txt lets each of CRAWLERS fetch every page the sitemap lists,
    and no sitemap page limits keeping or quoting it (0048). Bing, Yahoo and
    DuckDuckGo sent 12 of the site's first 14 search visits, and until this
    check the only crawler anything named was Bingbot, at the site root
    (indexnow.check_robots)."""
    problems: list[str] = []
    robots = (root / "robots.txt").read_text(encoding="utf-8")
    locs = LOC.findall((root / "sitemap.xml").read_text(encoding="utf-8"))
    for crawler in CRAWLERS:
        rules = robots_rules(robots, crawler)
        shut = [loc for loc in locs if not may_fetch(rules, "/" + loc)]
        if shut:
            problems.append(f"robots.txt: {crawler} may not fetch {len(shut)} sitemap page(s), such as /{shut[0]}")
    for loc in locs:
        f = root / loc / "index.html"
        if f.is_file():
            problems += [f"{loc or 'index.html'}: {limit}" for limit in quote_limits(f.read_text(encoding="utf-8"))]
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


def _king_build_day(root: Path, seasons: list[kingtides.StationSeason]) -> dt.date | None:
    """The day the pages were built for, on the coast: a king-tide station
    page's date. The king-tide pages don't carry it, so that they stay
    byte-identical (and are not re-announced, 0011) until what they say changes."""
    dated = [root / "stations" / k.id / "index.html" for k in seasons]
    found = [STATION_DATE.findall(f.read_text(encoding="utf-8")) for f in dated if f.exists()]
    if not found or len(found[0]) != 1:
        return None
    return dt.date.fromisoformat(found[0][0])


def check_king_tides(root: Path, cat: Catalog) -> list[str]:
    """The king-tide pages list exactly the runs coming up on the day they
    were built, and name their months in the title; each station page links
    to the king-tide run computed for it, and none links where none is."""
    problems: list[str] = []
    ctx = site.king_tide_context(cat)
    seasons: list[kingtides.StationSeason] = ctx["seasons"]
    today = _king_build_day(root, seasons)
    if today is None:
        return ["king-tides: no king-tide station page to date the build"]
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


HOME_GROUP = re.compile(r'<h3 class="coast" id="c-\d+">([^<]*)</h3>\s*<ul class="states"[^>]*>(.*?)</ul>', re.S)


def check_places(root: Path, cat: Catalog) -> list[str]:
    """/places.json has one row for each station page of the build, in id
    order: [id, display name], plus the station's searched name from
    copy/place_names.json when it has one, and no other row. The home page
    shows site.coast_groups for the states of the build, each state linked
    under its groups (docs/DECISIONS.md 0040)."""
    problems: list[str] = []
    f = root / "places.json"
    if not f.is_file():
        return ["places.json: missing"]
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"places.json: not JSON ({e})"]
    searched = site.place_names()
    built = [s for s in cat.stations if (root / "stations" / s.id / "index.html").is_file()]
    want = [
        [s.id, s.display_name] + ([n] if (n := site.place_name(s, searched)) != s.display_name else [])
        for s in sorted(built, key=lambda s: s.id)
    ]
    if rows != want:
        extra = [r for r in rows if r not in want][:5]
        missing = [w for w in want if w not in rows][:5]
        problems.append(f"places.json: {len(rows)} rows for {len(want)} station pages; not due {extra}, due {missing}")
    states = [st for st in site.group(cat.stations) if (root / st.path / "index.html").is_file()]
    home = (root / "index.html").read_text(encoding="utf-8")
    shown = [(name, re.findall(r'<a href="/(states/[^"]+/)">', inner)) for name, inner in HOME_GROUP.findall(home)]
    expect = [(name, [st.path for st in sts]) for name, sts in site.coast_groups(states)]
    if shown != expect:
        problems.append(f"index.html: state groups {shown}, expected {expect}")
    return problems


COAST_SECTION = re.compile(
    r'<section class="coast-states" aria-labelledby="coast-\d+">\s*<h2 id="coast-\d+">([^<]*)</h2>\s*<ul class="states">(.*?)</ul>',
    re.S,
)
REGION_JUMP = re.compile(r'<details class="regions-jump">.*?</details>', re.S)
ENTRY = re.compile(r'<a href="/([^"]+)">[^<]*</a>|<span aria-current="page">[^<]*</span>')


def _entries(html: str, here: str) -> list[str]:
    """The paths a list links, in order, with `here` where it names the
    page itself without a link; a link to the page itself is marked."""
    return [
        here if m.group(1) is None else m.group(1) + (" (linked)" if m.group(1) == here else "")
        for m in ENTRY.finditer(html)
    ]


def check_links(root: Path, cat: Catalog) -> list[str]:
    """Each state page ends with the home page's coast groups that hold it
    and another state of the build, every state in the group's order, itself
    unlinked; each region page ends with its state's regions in the state
    page's order, itself unlinked, unless its state has one region or no
    state (docs/DECISIONS.md 0043)."""
    problems: list[str] = []
    order = site.region_order()
    states = [st for st in site.group(cat.stations) if (root / st.path / "index.html").is_file()]
    groups = site.coast_groups(states)
    for st in states:
        page = (root / st.path / "index.html").read_text(encoding="utf-8")
        shown = [(name, _entries(inner, st.path)) for name, inner in COAST_SECTION.findall(page)]
        expect = [(name, [s.path for s in sts]) for name, sts in site.coast_neighbors(st, groups)]
        if shown != expect:
            problems.append(f"{st.path}: coast groups {shown}, expected {expect}")
        regions = site.coast_order(st, order)
        want = [r.path for r in site.sibling_regions(st, regions)]
        for r in st.regions:
            f = root / r.path / "index.html"
            if not f.is_file():
                continue
            jumps = REGION_JUMP.findall(f.read_text(encoding="utf-8"))
            if not want:
                if jumps:
                    problems.append(f"{r.path}: a list of regions where its state has none to list")
                continue
            got = _entries(jumps[0], r.path) if len(jumps) == 1 else [f"({len(jumps)} lists)"]
            if got != want:
                problems.append(f"{r.path}: regions {got}, expected {want}")
    return problems


def check_king_calendar(root: Path, cat: Catalog) -> list[str]:
    """Each state's winter king-tide calendar lists every month of the
    window, in order, and in each exactly the runs computed for it; a month
    with none says so in words (docs/DECISIONS.md 0024). Its title and
    description name the dates in season on the build day (0045)."""
    problems: list[str] = []
    ctx = site.king_tide_context(cat)
    seasons: list[kingtides.StationSeason] = ctx["seasons"]
    today = _king_build_day(root, seasons)
    if today is None:
        problems.append("king-tides: no king-tide station page to date the calendars' titles")
    for code in kingtides.CALENDAR_STATES:
        rel = kingtides.calendar_path(code)
        f = root / rel / "index.html"
        if not f.is_file():
            problems.append(f"{rel}: no page")
            continue
        text = f.read_text(encoding="utf-8")
        months = kingtides.calendar(seasons, code)
        # The title and description name the dates of the month in season on
        # the build day, or the season's (docs/DECISIONS.md 0045).
        if today is not None:
            title, description = site.king_calendar_head(code, months, today, ctx["copy"]["en"])
            if [htmllib.unescape(t) for t in TITLE.findall(text)] != [title]:
                problems.append(f"{rel}: title {TITLE.findall(text)[:1]}, expected {title!r}")
            if [htmllib.unescape(d) for d in DESCRIPTION.findall(text)] != [description]:
                problems.append(f"{rel}: description {DESCRIPTION.findall(text)[:1]}, expected {description!r}")
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


Books = tuple[booklets.Booklet, ...]


def booklet_pages(root: Path, listed: dict[str, Books]) -> tuple[dict[str, Books], list[str]]:
    """The station pages of this build that must link to a book, as page
    path -> its books, in order: each listed station that has a page, with
    the books whose year is not past the page's own date
    (docs/DECISIONS.md 0030)."""
    want: dict[str, Books] = {}
    problems: list[str] = []
    for station_id, books in listed.items():
        rel = f"stations/{station_id}/index.html"
        if not (root / rel).is_file():
            continue
        dates = STATION_DATE.findall((root / rel).read_text(encoding="utf-8"))
        if len(dates) != 1:
            problems.append(f"{rel}: no date to tell whether its booklet's year is over")
            continue
        due = tuple(b for b in books if booklets.shown(b, dt.date.fromisoformat(dates[0])))
        if due:
            want[rel] = due
    return want, problems


def _check_booklet(rel: str, text: str, want: Books | None) -> tuple[str, list[str]]:
    """One page's book sentences. Returns the page without them, for the
    Amazon rules that apply to everything else, and the problems: a
    sentence on a page that is due none; or, on a page that is due some, a
    number of sentences other than its number of books, more than one link
    in a sentence, an address that is not exactly its book's (which covers
    books out of order), a rel other than noopener, a click event, or a
    place before the tide tables or after the page's closing notes."""
    blocks = list(BOOKLET_P.finditer(text))
    if not want:
        return text, ([f"{rel}: a booklet link on a page that is due none"] if blocks else [])
    if len(blocks) != len(want):
        return BOOKLET_P.sub("", text), [f"{rel}: {len(blocks)} booklet links, exactly {len(want)} expected"]
    problems: list[str] = []
    last_day = text.rfind('<section class="day"')
    for found, book in zip(blocks, want, strict=True):
        anchors = ANY_A.findall(found.group(0))
        if len(anchors) != 1 or found.group(0).count("http") != 1:
            problems.append(f"{rel}: the booklet sentence has {len(anchors)} links, exactly 1 expected")
        for a in anchors:
            href_attr = HREF_ATTR.search(a)
            href = htmllib.unescape(href_attr.group(1)) if href_attr else ""
            if href != book.url:
                problems.append(f"{rel}: {href} is not the booklet's address, {book.url}")
            rel_attr = REL_ATTR.search(a)
            tokens = set(rel_attr.group(1).split()) if rel_attr else set()
            if tokens != set(booklets.REL.split()):
                problems.append(f"{rel}: {href} rel is {sorted(tokens)}")
            if "data-ga" in a:
                problems.append(f"{rel}: the booklet link carries a click event")
        if not 0 <= last_day < text.find("</section>", last_day) < found.start() < text.find('id="what"'):
            problems.append(f"{rel}: the booklet link is not between the tide tables and the closing notes")
    return BOOKLET_P.sub("", text), problems


def check_affiliate(
    root: Path,
    html: list[Path],
    tag: str,
    booklet_links: dict[str, Books] | None = None,
    gift_books: bool = False,
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
    and terms pages may name Amazon in words, never with a link.

    The same holds while the tide gifts page lists a book (`gift_books`,
    docs/DECISIONS.md 0041): that page is left to check_gifts."""
    want = booklet_links or {}
    named = {p + "index.html" for p in booklets.MENTION_PAGES} if want or gift_books else set()
    problems: list[str] = []
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        f = root / name
        if f.exists() and "amazon" in f.read_text(encoding="utf-8").lower():
            problems.append(f"{name}: mentions amazon")
    for f in html:
        rel = f.relative_to(root).as_posix()
        if gift_books and rel == gifts.PATH + "index.html":
            continue
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
    if any(m.start() > found.start() for m in BOOKLET_P.finditer(text)):
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
    earlier = [*BOOKLET_P.finditer(text), *CALENDAR_P.finditer(text)]
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


def build_date(root: Path, cat: Catalog) -> dt.date | None:
    """The day the build was made (UTC), as its station pages say it."""
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if f.is_file():
            found = BUILT.findall(f.read_text(encoding="utf-8"))
            return dt.date.fromisoformat(found[0]) if found else None
    return None


def until_day(root: Path, cat: Catalog, built: dt.date) -> dt.date:
    """The build's date in gifts.UNTIL_ZONE, which an entry's `until` is
    read in: the date a station page in that zone shows, or the build's
    UTC date when the build has none (the daily build runs at 11:20 UTC,
    when the two are the same day)."""
    zone = str(gifts.UNTIL_ZONE)
    for s in cat.stations:
        f = root / "stations" / s.id / "index.html"
        if s.tz == zone and f.is_file():
            found = STATION_DATE.findall(f.read_text(encoding="utf-8"))
            if len(found) == 1:
                return dt.date.fromisoformat(found[0])
    return built


def gift_listing(
    root: Path,
    cat: Catalog,
    listed: list[gifts.Gift],
    url: str,
    calendar_links: dict[str, calendars.Calendar] | None = None,
    poster_links: dict[str, posters.Poster] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """What tide-gifts/ must show for this build, worked out from the
    build itself: the calendars and posters its station pages are due, the
    entries of `listed` whose year is not over on the build's date, whose
    `until`, if any, has not come, and whose station, if any, has a page,
    and the custom print when the shop address is set (docs/DECISIONS.md
    0041)."""
    stations = {s.id: s for s in cat.stations if (root / "stations" / s.id / "index.html").is_file()}
    built = build_date(root, cat)
    if built is None:
        return None, ["no station page says when the build was made"]
    today = until_day(root, cat, built)
    shown = [g for g in listed if gifts.shown(g, built, today) and (g.station is None or g.station in stations)]
    listing = gifts.block(
        _station_ids(calendar_links), _station_ids(poster_links), shown, stations, printshop.block(url)
    )
    return listing, []


def check_gifts(root: Path, html: list[Path], listing: dict[str, Any] | None) -> list[str]:
    """While an entry of copy/gifts.json shows (`listing`, from
    gift_listing), tide-gifts/ exists and is exactly the page gifts.py
    gives: its title, heading, two paragraphs, sections and their words,
    and each line's links in order. Every link from it to Etsy or Amazon is
    one it lists, once, with rel="noopener" and no click event, so a link to
    a listing that no list carries, or that is not marked live, fails. No
    price, discount or rating, and Etsy and Amazon are not in its JSON-LD.
    Every English page links to it once, in the footer, and the Spanish
    page does not. With nothing to list, there is no such page and no link
    to one (docs/DECISIONS.md 0041)."""
    rel = gifts.PATH + "index.html"
    f = root / rel
    problems: list[str] = []
    if listing is None:
        if f.is_file():
            problems.append(f"{rel}: a gifts page in a build with nothing to list")
    elif not f.is_file():
        problems.append(f"{rel}: no page, though the build has gifts to list")
    else:
        problems += _check_gifts_page(rel, f.read_text(encoding="utf-8"), listing)
    href = f'href="/{gifts.PATH}"'
    for page in html:
        text = page.read_text(encoding="utf-8")
        want = 1 if listing is not None and '<html lang="en">' in text else 0
        if text.count(href) != want:
            where = page.relative_to(root).as_posix()
            problems.append(f"{where}: {text.count(href)} links to {gifts.PATH}, exactly {want} expected")
    return problems


def _gift_lines(listing: dict[str, Any]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Each line the page must show, as (data-gift, its links in order)."""
    out: list[tuple[str, list[tuple[str, str]]]] = []
    for sec in listing["sections"]:
        if sec.link:
            out.append(("custom", [(sec.link["url"], sec.link["text"])]))
        out += [(e.key, gifts.links_of(e)) for e in sec.entries]
    return out


def _check_gift_words(rel: str, main: str, listing: dict[str, Any]) -> list[str]:
    """Each line's words, as gifts.line_text gives them: the town, the
    title, and for a custom print or a pattern the listing's own words."""
    shown = [
        " ".join(htmllib.unescape(TAG.sub("", inner)).split())
        for tag, _, inner in GIFT_ITEM.findall(main)
        if tag == "li"
    ]
    want = [gifts.line_text(e) for sec in listing["sections"] for e in sec.entries]
    return [] if shown == want else [f"{rel}: the gift lines read {shown}, expected {want}"]


def _check_gifts_page(rel: str, text: str, listing: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    main = text[text.find("<main") : text.find("</main>")]
    shown = [
        (key, [(htmllib.unescape(h), htmllib.unescape(TAG.sub("", t))) for h, t in LINK_TEXT.findall(inner)])
        for _, key, inner in GIFT_ITEM.findall(main)
    ]
    want = _gift_lines(listing)
    if shown != want:
        extra = [x for x in shown if x not in want]
        missing = [w for w in want if w not in shown]
        problems.append(
            f"{rel}: the gifts listed differ, or their order: shown but not due {extra}, due but not shown {missing}"
        )
    problems += _check_gift_words(rel, main, listing)
    allowed = [h for _, links in want for h, _ in links if h.startswith("http")]
    outbound = [*ETSY_A.finditer(text), *AMAZON_A.finditer(text)]
    hrefs = [htmllib.unescape(m.group(1)) for m in outbound]
    problems += [f"{rel}: {h} is not a live listing this build lists" for h in hrefs if h not in allowed]
    if sorted(hrefs) != sorted(allowed):
        problems.append(f"{rel}: {len(hrefs)} links to Etsy or Amazon, one for each of the {len(allowed)} listed")
    for m in outbound:
        rel_attr = REL_ATTR.search(m.group(0))
        tokens = set(rel_attr.group(1).split()) if rel_attr else set()
        if tokens != set(listing["rel"].split()):
            problems.append(f"{rel}: {htmllib.unescape(m.group(1))} rel is {sorted(tokens)}")
        if "data-ga" in m.group(0):
            problems.append(f"{rel}: a gift link carries a click event")
    if any(w in block.lower() for block in JSON_LD.findall(text) for w in ("etsy", "amazon")):
        problems.append(f"{rel}: etsy or amazon in JSON-LD")
    title = [htmllib.unescape(t) for t in TITLE.findall(text)]
    if title != [f"{listing['title']} | Tide Hours"]:
        problems.append(f"{rel}: title {title}")
    words = [htmllib.unescape(x) for x in (*H1.findall(main), *MAIN_P.findall(main)[:2])]
    if words != [listing["heading"], listing["intro"], listing["how"]]:
        problems.append(f"{rel}: the heading and the two paragraphs are {words}")
    headings = [htmllib.unescape(h) for h in H2_TEXT.findall(main)]
    if headings != [sec.heading for sec in listing["sections"]]:
        problems.append(f"{rel}: the section headings are {headings}")
    plain = [" ".join(htmllib.unescape(TAG.sub("", p)).split()) for p in MAIN_P.findall(main)[2:]]
    want_p = [
        f"{sec.text} {sec.link['text']}{sec.link['after']}" if sec.link else sec.text
        for sec in listing["sections"]
        if sec.link or sec.text
    ]
    if plain != want_p:
        problems.append(f"{rel}: the section paragraphs are {plain}")
    bad = GIFT_FORBIDDEN.findall(htmllib.unescape(TAG.sub(" ", main)))
    if bad:
        problems.append(f"{rel}: a price, sale or claim word: {bad}")
    return problems


def _check_book_notice(root: Path, booklet_links: dict[str, Books], gift_books: bool) -> list[str]:
    """The privacy page's section on the Amazon book links is exactly the one
    gifts.book_notice gives for this build (docs/DECISIONS.md 0030, 0041)."""
    f = root / "privacy" / "index.html"
    if not f.is_file():
        return []
    expect = gifts.book_notice(booklets.notice(bool(booklet_links)), gift_books)
    pattern = re.compile(r'<h2 id="booklets">(.*?)</h2>\s*<p>(.*?)</p>', re.S)
    found = [(htmllib.unescape(h), htmllib.unescape(p)) for h, p in pattern.findall(f.read_text(encoding="utf-8"))]
    want = [(expect["heading"], expect["body"])] if expect else []
    if found != want:
        return [f"privacy/index.html: the book section is {found or 'missing'}, expected {want or 'none'}"]
    return []


def check_print_shop(
    root: Path,
    html: list[Path],
    url: str,
    calendar_links: dict[str, calendars.Calendar] | None = None,
    poster_links: dict[str, posters.Poster] | None = None,
    gift_etsy: bool = False,
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
    and is not held to the rules above (docs/DECISIONS.md 0037). So is the
    tide gifts page while it links to Etsy (`gift_etsy`), which is left to
    check_gifts (0041)."""
    want = calendar_links or {}
    want_poster = poster_links or {}
    which = printables.kind(bool(want), bool(want_poster))
    named = {p + "index.html" for p in printshop.MENTION_PAGES} if which or gift_etsy else set()
    problems: list[str] = []
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        f = root / name
        if f.exists() and "etsy" in f.read_text(encoding="utf-8").lower():
            problems.append(f"{name}: mentions etsy")
    # Since 0051 the state king-tide calendars of printshop.CALENDAR_PAGES
    # carry the link too, under the same rules.
    link_pages = {p + "index.html" for p in (*printshop.PAGES, *printshop.CALENDAR_PAGES)}
    for f in html:
        rel = f.relative_to(root).as_posix()
        text, found = _without_shop_click(rel, f.read_text(encoding="utf-8"))
        problems += found
        text, found = _check_poster(rel, text, want_poster.get(rel))
        problems += found
        text, found = _check_calendar(rel, text, want.get(rel))
        problems += found
        if which and rel == printables.PATH + "index.html":
            continue
        if gift_etsy and rel == gifts.PATH + "index.html":
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
    problems += _check_shop_notice(root, url, which, gift_etsy)
    return problems


# The GA4 shop_click handler (_ga4.html.jinja, docs/DECISIONS.md 0057), as
# rendered. It names www.etsy.com in code, not as a link or in words, so the
# Etsy checks look at a page without it; it may sit only on a page that links
# to Etsy, and it never reads a data-ga attribute.
SHOP_CLICK = re.compile(r"\n\n  // Shop link clicks:.*?\n  \}\);\n", re.S)


def _without_shop_click(rel: str, text: str) -> tuple[str, list[str]]:
    blocks = SHOP_CLICK.findall(text)
    if not blocks:
        return text, []
    problems: list[str] = []
    if len(blocks) > 1:
        problems.append(f"{rel}: {len(blocks)} shop_click handlers")
    if not ETSY_A.search(text):
        problems.append(f"{rel}: a shop_click handler with no Etsy link")
    if any("data-ga" in b or ".href" in b for b in blocks):
        problems.append(f"{rel}: the shop_click handler reads an attribute or the address")
    return SHOP_CLICK.sub("\n", text), problems


SHOP_NOTICE = re.compile(r'<h2 id="shop">(.*?)</h2>\s*<p>(.*?)</p>', re.S)


def _check_shop_notice(root: Path, url: str, which: str | None, gift_etsy: bool = False) -> list[str]:
    """The privacy page's section on the Etsy links is exactly the one
    printables.notice gives for this build: none with no Etsy link, the print
    shop's own sentence with only the shop link, and the sentence that names
    the list of calendars and posters and the station pages while a calendar
    or poster link shows (docs/DECISIONS.md 0035, 0037), and the tide gifts
    page while it links to Etsy (0041). `which` is printables.kind's value."""
    f = root / "privacy" / "index.html"
    if not f.is_file():
        return []
    expect = gifts.shop_notice(which, printshop.block(url), gift_etsy)
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
            problems.append(f"{rel}: etsy link outside {', '.join((*printshop.PAGES, *printshop.CALENDAR_PAGES))}")
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
    gifts_file: Path | None = None,
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
    problems += check_crawlers(root)
    problems += check_tide_types(root, cat)
    problems += check_king_tides(root, cat)
    problems += check_king_calendar(root, cat)
    booklet_links, undated = booklet_pages(root, booklets.load(booklets_file))
    problems += undated
    calendar_links, undated = calendar_pages(root, calendars.load(calendars_file))
    problems += undated
    poster_links, undated = poster_pages(root, posters.load(posters_file))
    problems += undated
    gift_page, undated = gift_listing(root, cat, gifts.load(gifts_file), print_shop_url, calendar_links, poster_links)
    problems += undated
    problems += check_affiliate(root, html, amazon_tag, booklet_links, gifts.has_books(gift_page))
    problems += _check_book_notice(root, booklet_links, gifts.has_books(gift_page))
    problems += check_print_shop(root, html, print_shop_url, calendar_links, poster_links, gifts.has_etsy(gift_page))
    problems += check_printables(root, html, cat, calendar_links, poster_links)
    problems += check_gifts(root, html, gift_page)
    problems += check_sky(root, cat)
    problems += check_next(root, cat)
    problems += check_hubs(root, cat)
    problems += check_places(root, cat)
    problems += check_links(root, cat)
    problems += check_share_files(root)
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
    ap.add_argument("--gifts", type=Path, help="the gift list the site was built with, if not the committed one")
    args = ap.parse_args()
    sys.exit(
        main(
            args.site_dir,
            args.amazon_tag,
            args.print_shop_url,
            args.booklets,
            args.calendars,
            args.posters,
            args.gifts,
        )
    )
