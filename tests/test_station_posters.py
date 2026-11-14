"""A station page's link to its printable year-of-tides poster in the Tide
Hours shop on Etsy (docs/DECISIONS.md 0037, built as 0035 builds the calendar
links): the committed list is the six posters the owner listed on
2026-11-13; an empty list leaves no trace; one listed poster puts one plain
link on that station's page and on the page that lists them; a bad entry is
refused; the link leaves when the poster's year is over; and the sentence
sits after the calendar sentence when both show. Negative controls prove
each check_site rule for the sentence can fail, each asserting its sabotage
changed the build. tests/test_printables.py covers the page that lists them.

The Guam listing ids below are made up. They live only in lists a test
writes to a temporary directory; the committed lists hold the real ones."""

from __future__ import annotations

import datetime as dt
import functools
import html as htmllib
import importlib.util
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tidehours import calendars, catalog, cli, posters, printables

NOW = "2026-11-01T11:20:00Z"
STATION = "1630000"  # Apra Harbor, Guam
OTHER_STATION = "1631428"
LISTING = "1234567891"
TITLE = "2027 Tide Poster: Apra Harbor"
URL = "https://www.etsy.com/listing/1234567891"
CALENDAR_LISTING = "1234567890"
CALENDAR_TITLE = "2027 Tide Calendar: Apra Harbor"
CALENDAR_URL = "https://www.etsy.com/listing/1234567890"
PAGE = f"stations/{STATION}/index.html"
HUB = "tide-calendars/index.html"
FOOTER = ' · <a href="/tide-calendars/">Tide posters</a>'
SENTENCE = (
    "A printable 2027 year-of-tides poster for this station is in the Tide Hours shop on Etsy: "
    "2027 Tide Poster: Apra Harbor."
)
SHOP = "https://www.etsy.com/shop/TideHours"
# The committed list, as the owner gave it on 2026-11-13: station id ->
# (listing id, title).
COMMITTED = {
    "8413320": ("4616234122", "2027 Tide Poster: Bar Harbor"),
    "8410140": ("4616223885", "2027 Tide Poster: Eastport"),
    "9455558": ("4616235032", "2027 Tide Poster: Homer"),
    "8446121": ("4616224833", "2027 Tide Poster: Provincetown"),
    "9410230": ("4616225323", "2027 Tide Poster: La Jolla"),
    "9413450": ("4616225815", "2027 Tide Poster: Monterey"),
}
ETSY_A = re.compile(r'<a\b[^>]*href="(https?://[^"]*etsy\.[^"]*)"[^>]*>', re.I)
BLOCK = re.compile(r'<p class="poster"[^>]*>.*?</p>', re.S)
CALENDAR = re.compile(r'<p class="calendar"[^>]*>.*?</p>', re.S)
SUFFIXES = (".html", ".xml", ".txt", ".json", ".css")
# The words and signs test_print_shop.py refuses (no claim, price or rating).
FORBIDDEN = re.compile(r"\b(best|top|only|first|cheap|deals?|rated|official)\b|[$%★]", re.I)
SHOP_SECTION = re.compile(r'<h2 id="shop">(.*?)</h2>\s*<p>(.*?)</p>', re.S)
PRIVACY_POSTERS_ONLY = (
    "Shop links",
    "The tide posters page, and the station pages of towns with a printable poster, link to those posters in the "
    "Tide Hours shop on Etsy. This site sends nothing to Etsy. The link takes you to Etsy, where Etsy's own "
    "privacy policy applies.",
)
PRIVACY_EVERYTHING = (
    "Shop links",
    "The About and king tides pages, the tide calendars and posters page, and the station pages of towns with a "
    "printable calendar or poster, link to the Tide Hours shop on Etsy. This site sends nothing to Etsy. The link "
    "takes you to Etsy, where Etsy's own privacy policy applies.",
)


def entry(**changes: Any) -> dict[str, Any]:
    return {"listing": LISTING, "year": 2027, "title": TITLE} | changes


def write_list(path: Path, entries: Any, key: str = "posters") -> Path:
    path.write_text(json.dumps({key: entries}), encoding="utf-8")
    return path


def build(out: Path, list_file: Path | None, *extra: str, now: str = NOW) -> Path:
    args = ["--out", str(out), "--now", now, "--states", "GU", *extra]
    if list_file is not None:
        args += ["--posters", str(list_file)]
    assert cli.main(args) == 0
    return out


@pytest.fixture(scope="module")
def empty(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "empty.json", {})


@pytest.fixture(scope="module")
def listed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "one.json", {STATION: entry()})


@pytest.fixture(scope="module")
def calendar_list(tmp_path_factory: pytest.TempPathFactory) -> Path:
    entries = {STATION: {"listing": CALENDAR_LISTING, "year": 2027, "title": CALENDAR_TITLE}}
    return write_list(tmp_path_factory.mktemp("lists") / "calendars.json", entries, "calendars")


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory, empty: Path) -> Path:
    return build(tmp_path_factory.mktemp("off"), empty)


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory, listed: Path) -> Path:
    """A poster link with no calendar and the print shop off."""
    return build(tmp_path_factory.mktemp("on"), listed)


@pytest.fixture(scope="module")
def everything(tmp_path_factory: pytest.TempPathFactory, listed: Path, calendar_list: Path) -> Path:
    """A calendar and a poster on one page, with the print shop on."""
    return build(
        tmp_path_factory.mktemp("everything"), listed, "--calendars", str(calendar_list), "--print-shop-url", SHOP
    )


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_posters", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def the_catalog() -> catalog.Catalog:
    return catalog.load()


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def plain(html: str) -> str:
    """A sentence's words as they read, tags dropped in place."""
    return htmllib.unescape(re.sub(r"<[^>]+>", "", html)).strip()


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def traces(root: Path) -> list[str]:
    """Every file of a build that mentions Etsy, a poster link or the page
    that lists them."""
    found = []
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.suffix in SUFFIXES:
            body = f.read_text(encoding="utf-8").lower()
            if "etsy" in body or "data-poster" in body or "tide-calendars" in body:
                found.append(f.relative_to(root).as_posix())
    return found


def differing(a: Path, b: Path, ignoring: str = "") -> list[str]:
    """The files that are in only one of two builds, or differ in a byte
    once every `ignoring` is taken out of both."""
    names = {f.relative_to(root).as_posix() for root in (a, b) for f in root.rglob("*") if f.is_file()}
    cut = ignoring.encode("utf-8")

    def same(n: str) -> bool:
        if not ((a / n).is_file() and (b / n).is_file()):
            return False
        one, other = (a / n).read_bytes(), (b / n).read_bytes()
        return one == other or (bool(cut) and one.replace(cut, b"") == other.replace(cut, b""))

    return sorted(n for n in names if not same(n))


def problems(
    check_site: Any, root: Path, list_file: Path | None, url: str = "", calendar_file: Path | None = None
) -> list[str]:
    """What check_site's main does for Etsy: the pages due a calendar or
    poster link, from the lists and each page's own date, then the Etsy
    rules and the page that lists them."""
    want_calendars, undated_calendars = check_site.calendar_pages(root, calendars.load(calendar_file))
    want, undated = check_site.poster_pages(root, posters.load(list_file))
    found: list[str] = undated_calendars + undated
    found += check_site.check_print_shop(root, pages(root), url, want_calendars, want)
    found += check_site.check_printables(root, pages(root), the_catalog(), want_calendars, want)
    return found


def shop_section(root: Path) -> list[tuple[str, str]]:
    return [(htmllib.unescape(h), htmllib.unescape(p)) for h, p in SHOP_SECTION.findall(read(root, "privacy"))]


# The list


def test_the_committed_list_is_the_owners_posters() -> None:
    cat = the_catalog()
    listed = posters.load()
    assert {sid: (p.listing, p.title) for sid, p in listed.items()} == COMMITTED
    calendar_of = calendars.load()
    for station_id, poster in listed.items():
        assert cat.station(station_id) is not None, station_id
        assert poster.year == 2027
        assert poster.url == f"https://www.etsy.com/listing/{COMMITTED[station_id][0]}"
        # Each poster's town has a calendar, for the same station and place.
        assert printables.place(poster.title) == printables.place(calendar_of[station_id].title), station_id
    # No listing is both a calendar and a poster.
    assert not {p.listing for p in listed.values()} & {c.listing for c in calendar_of.values()}


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ({STATION: entry(listing="12345678x0")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=URL)}, "is not an Etsy listing id"),
        ({STATION: entry(listing=LISTING + "/2027-tide-poster-apra-harbor")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=LISTING + "?ref=shop_home")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=1234567891)}, "is not an Etsy listing id"),
        ({STATION: entry(year="2027")}, "is not a year"),
        ({STATION: entry(year=True)}, "is not a year"),
        ({STATION: entry(title="Apra Harbor Tide Poster 2027")}, "is not a title"),
        ({STATION: entry(title="2026 Tide Poster: Apra Harbor")}, "is not a title"),
        ({STATION: entry(title=CALENDAR_TITLE)}, "is not a title"),
        ({STATION: entry(title="2027 Tide Poster: Best Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Poster: Apra Harbor, $10")}, "is not a title"),
        ({STATION: entry(title=2027)}, "is not a title"),
        ({STATION: entry(url=URL)}, "exactly listing, year and title"),
        ({STATION: {"listing": LISTING, "year": 2027}}, "exactly listing, year and title"),
        ({STATION: LISTING}, "exactly listing, year and title"),
        ({"163000": entry()}, "is not a station id"),
        ({STATION: entry(), OTHER_STATION: entry()}, "one listing is listed for two stations"),
        ([entry()], "expected"),
    ],
)
def test_a_bad_list_is_refused(tmp_path: Path, entries: Any, message: str) -> None:
    bad = write_list(tmp_path / "bad.json", entries)
    with pytest.raises(ValueError, match=re.escape(message)):
        posters.load(bad)
    with pytest.raises(SystemExit, match="posters: "):
        cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--posters", str(bad)])
    assert not (tmp_path / "x").exists()  # refused before anything is built


def test_a_list_that_is_not_json_or_not_there_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"posters": ', encoding="utf-8")
    for path in (broken, tmp_path / "missing.json"):
        with pytest.raises(SystemExit, match="posters: "):
            cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--posters", str(path)])
    with pytest.raises(ValueError, match="expected"):
        posters.load(write_list(tmp_path / "wrong.json", {}, "calendars"))


def test_a_station_the_catalog_does_not_have_stops_the_build(tmp_path: Path) -> None:
    unknown = write_list(tmp_path / "unknown.json", {"9999999": entry()})
    with pytest.raises(ValueError, match="posters: no station 9999999 in the catalog"):
        build(tmp_path / "x", unknown)
    assert not (tmp_path / "x").exists()


def test_a_listing_that_is_a_calendar_too_stops_the_build(tmp_path: Path, calendar_list: Path) -> None:
    same = write_list(tmp_path / "same.json", {OTHER_STATION: entry(listing=CALENDAR_LISTING)})
    with pytest.raises(ValueError, match=f"posters: listing {CALENDAR_LISTING} is in the calendar list too"):
        build(tmp_path / "x", same, "--calendars", str(calendar_list))
    assert not (tmp_path / "x").exists()


# The empty list


def test_an_empty_list_leaves_no_trace(off: Path, empty: Path, tmp_path: Path, check_site: Any) -> None:
    assert traces(off) == []
    assert shop_section(off) == []
    assert problems(check_site, off, empty) == []
    # Guam has no poster in the committed list, so the default build is the
    # same build, file for file.
    assert not any(station_id in (STATION, OTHER_STATION) for station_id in posters.load())
    assert differing(off, build(tmp_path / "default", None)) == []


def test_the_empty_list_check_can_fail(off: Path, on: Path, empty: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: put the sentence into an empty-list build and the
    checks see it."""
    bad = tmp_path / "bad"
    shutil.copytree(off, bad)
    sentence = BLOCK.search(read(on, f"stations/{STATION}"))
    assert sentence is not None
    target = bad / PAGE
    before = target.read_text(encoding="utf-8")
    after = before.replace("</main>", sentence.group(0) + "</main>", 1)
    assert after != before  # the sabotage applied
    target.write_text(after, encoding="utf-8")
    assert traces(bad) == [PAGE]
    assert problems(check_site, bad, empty) == [
        f"{PAGE}: a poster link on a page that is due none",
        f"{PAGE}: mentions etsy with no shop address set",
    ]


# One listed poster


def test_one_poster_puts_one_link_on_its_page_and_on_the_list(
    off: Path, on: Path, listed: Path, check_site: Any
) -> None:
    # Every English page's footer gains the link to the list. Apart from
    # that, nothing but that station's page, the privacy and terms pages,
    # the list itself, the sitemap that names it and the record of
    # fingerprints differs from the empty-list build.
    assert differing(off, on, ignoring=FOOTER) == [
        "lastmod.json",
        "privacy/index.html",
        "sitemap.xml",
        PAGE,
        "terms/index.html",
        HUB,
    ]
    links = {
        f.relative_to(on).as_posix(): ETSY_A.findall(f.read_text(encoding="utf-8"))
        for f in on.rglob("*")
        if f.is_file() and f.suffix in SUFFIXES and ETSY_A.search(f.read_text(encoding="utf-8"))
    }
    assert links == {PAGE: [URL], HUB: [URL]}
    html = read(on, f"stations/{STATION}")
    blocks = BLOCK.findall(html)
    assert len(blocks) == 1
    assert plain(blocks[0]) == SENTENCE
    assert blocks[0] == (
        f'<p class="poster" data-poster="{LISTING}">A printable 2027 year-of-tides poster for this station is in '
        f'the Tide Hours shop on Etsy: <a href="{URL}" rel="noopener">{TITLE}</a>.</p>'
    )
    for unwanted in ("?", "&", "ref=shop", "utm_", "data-ga", "sponsored", "nofollow", "<img", "$"):
        assert unwanted not in blocks[0], unwanted
    # Take the sentence and the footer's link out and the page is the
    # empty-list page, byte for byte.
    assert html.replace(blocks[0], "").replace(FOOTER, "") == read(off, f"stations/{STATION}")
    # After the tide tables and the app line, before the closing notes.
    last_day = html.rindex('<section class="day"')
    assert (
        html.index("</section>", last_day) < html.index('id="week"') < html.index(blocks[0]) < html.index('id="what"')
    )
    assert shop_section(on) == [PRIVACY_POSTERS_ONLY]
    assert problems(check_site, on, listed) == []


def test_not_in_json_ld_or_the_files_beside_the_pages(on: Path) -> None:
    html = read(on, f"stations/{STATION}")
    for script in re.findall(r'<script type="application/ld\+json">.*?</script>', html, re.S):
        assert "etsy" not in script.lower() and LISTING not in script
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        body = (on / name).read_text(encoding="utf-8")
        assert "etsy" not in body.lower() and LISTING not in body, name
    for rel in ("", "states/gu", "states/gu/guam", "king-tides", "es/king-tides", "about", f"stations/{OTHER_STATION}"):
        assert "etsy" not in read(on, rel).lower(), rel


def test_the_sentence_makes_no_claim(on: Path) -> None:
    copy = json.loads(posters.COPY.read_text(encoding="utf-8"))
    built = BLOCK.search(read(on, f"stations/{STATION}"))
    assert built is not None
    for prose in (*copy.values(), plain(built.group(0))):
        assert FORBIDDEN.search(prose) is None, prose
    assert posters.block(None) is None


# Next to a calendar and the print shop


def test_with_a_calendar_the_calendar_line_comes_first(
    everything: Path, listed: Path, calendar_list: Path, check_site: Any
) -> None:
    html = read(everything, f"stations/{STATION}")
    calendar, poster = CALENDAR.search(html), BLOCK.search(html)
    assert calendar is not None and poster is not None
    assert calendar.end() <= poster.start()
    assert plain(poster.group(0)) == SENTENCE
    assert ETSY_A.findall(html) == [CALENDAR_URL, URL]
    assert shop_section(everything) == [PRIVACY_EVERYTHING]
    assert problems(check_site, everything, listed, SHOP, calendar_list) == []


# The year


def test_shown_until_the_year_is_over() -> None:
    poster = posters.Poster(LISTING, 2027, TITLE)
    assert posters.shown(poster, dt.date(2026, 11, 1))
    assert posters.shown(poster, dt.date(2027, 12, 31))
    assert not posters.shown(poster, dt.date(2028, 1, 1))


@pytest.mark.parametrize(
    ("now", "date", "shows"),
    [
        ("2027-12-31T11:20:00Z", "2027-12-31", True),
        # 15:00 UTC on December 31 is already January 1 in Guam: the page's
        # own first day decides, not the build's clock in UTC.
        ("2027-12-31T15:00:00Z", "2028-01-01", False),
        ("2028-01-01T11:20:00Z", "2028-01-01", False),
    ],
)
def test_the_link_leaves_when_the_year_is_over(
    tmp_path: Path, listed: Path, empty: Path, check_site: Any, now: str, date: str, shows: bool
) -> None:
    with_list = build(tmp_path / "listed", listed, now=now)
    assert f'data-station-date="{date}"' in read(with_list, f"stations/{STATION}")
    assert (ETSY_A.findall(read(with_list, f"stations/{STATION}")) == [URL]) == shows
    want, undated = check_site.poster_pages(with_list, posters.load(listed))
    assert undated == [] and list(want) == ([PAGE] if shows else [])
    assert problems(check_site, with_list, listed) == []
    if not shows:
        # Nobody edited the list, and the build is the empty-list build again.
        assert traces(with_list) == []
        assert differing(with_list, build(tmp_path / "empty", empty, now=now)) == []


def test_check_site_catches_a_link_left_up_after_its_year(on: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: the same build, checked against a list whose
    poster's year is over on the page's date."""
    past = write_list(tmp_path / "past.json", {STATION: entry(year=2025, title="2025 Tide Poster: Apra Harbor")})
    due_now, _ = check_site.poster_pages(on, posters.load(past))
    assert due_now == {}  # the sabotage applied: the list no longer calls for the link
    assert f"{PAGE}: a poster link on a page that is due none" in problems(check_site, on, past)


# Negative controls for check_site

LINK = f'href="{URL}"'
END_OF_LINK = 'rel="noopener">' + TITLE
NOT_THE_ADDRESS = f"is not the poster's address, {URL}"
MISPLACED = f"{PAGE}: the poster link is not between the tide tables and the closing notes"
OTHER_PAGE = f"stations/{OTHER_STATION}/index.html"
Sabotage = Callable[[str, str], str]  # (the file's text, the poster sentence) -> the file's text, broken


def swap(old: str, new: str) -> Sabotage:
    return lambda text, block: text.replace(old, new)


def before(marker: str, addition: str | None = None) -> Sabotage:
    """Put `addition` (the poster sentence, if None) in front of the first `marker`."""
    return lambda text, block: text.replace(marker, (addition or block) + marker, 1)


def move_before(marker: str) -> Sabotage:
    return lambda text, block: text.replace(block, "").replace(marker, block + marker, 1)


# name -> (the file to break, how, the problem check_site must report), on a
# build with a poster link, no calendar and the print shop off. The sabotage
# is applied to the station page's copy of the sentence only; the list's own
# link is tests/test_printables.py's.
BROKEN: dict[str, tuple[str, Sabotage, str]] = {
    "missing": (PAGE, lambda text, block: text.replace(block, ""), f"{PAGE}: 0 poster links, exactly 1 expected"),
    "repeated": (
        PAGE,
        lambda text, block: text.replace(block, block + block),
        f"{PAGE}: 2 poster links, exactly 1 expected",
    ),
    "slug": (
        PAGE,
        swap(LINK, f'href="{URL}/2027-tide-poster-apra-harbor"'),
        f"{PAGE}: {URL}/2027-tide-poster-apra-harbor {NOT_THE_ADDRESS}",
    ),
    "query string": (PAGE, swap(LINK, f'href="{URL}?ref=tidehours"'), f"{PAGE}: {URL}?ref=tidehours {NOT_THE_ADDRESS}"),
    "tracking parameter": (
        PAGE,
        swap(LINK, f'href="{URL}?utm_source=tidehours"'),
        f"{PAGE}: {URL}?utm_source=tidehours {NOT_THE_ADDRESS}",
    ),
    "another listing": (
        PAGE,
        swap(LINK, 'href="https://www.etsy.com/listing/9999999999"'),
        f"{PAGE}: https://www.etsy.com/listing/9999999999 {NOT_THE_ADDRESS}",
    ),
    "the shop instead": (PAGE, swap(LINK, f'href="{SHOP}"'), f"{PAGE}: {SHOP} {NOT_THE_ADDRESS}"),
    "sponsored rel": (
        PAGE,
        swap(END_OF_LINK, 'rel="sponsored nofollow noopener">' + TITLE),
        f"{PAGE}: {URL} rel is ['nofollow', 'noopener', 'sponsored']",
    ),
    "click event": (
        PAGE,
        swap(END_OF_LINK, 'rel="noopener" data-ga-event="poster_click">' + TITLE),
        f"{PAGE}: the poster link carries a click event",
    ),
    "second link": (
        PAGE,
        swap(f"{TITLE}</a>.</p>", f'{TITLE}</a>. <a href="/about/">About</a></p>'),
        f"{PAGE}: the poster sentence has 2 links, exactly 1 expected",
    ),
    "before the tables": (PAGE, move_before('<section class="day"'), MISPLACED),
    "after the notes": (PAGE, move_before("</main>"), MISPLACED),
    "another station": (OTHER_PAGE, before("</main>"), f"{OTHER_PAGE}: a poster link on a page that is due none"),
    "state page": (
        "states/gu/index.html",
        before("</main>"),
        "states/gu/index.html: a poster link on a page that is due none",
    ),
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}" rel="noopener">Buy</a></p>'),
        f"{PAGE}: mentions etsy with no shop address set",
    ),
    "undated": (
        PAGE,
        lambda text, block: re.sub(r' data-station-date="[^"]*"', "", text),
        f"{PAGE}: no date to tell whether its poster's year is over",
    ),
}

# Where the page has a calendar sentence too, and the print shop is on.
BROKEN_WITH_CALENDAR: dict[str, tuple[str, Sabotage, str]] = {
    "before the calendar": (
        PAGE,
        lambda text, block: text.replace(block, "").replace('<p class="calendar"', block + '<p class="calendar"', 1),
        f"{PAGE}: the poster link comes before the booklet or calendar link",
    ),
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}" rel="noopener">Buy</a></p>'),
        f"{PAGE}: etsy link outside about/, king-tides/",
    ),
    "on the about page": (
        "about/index.html",
        before("</main>"),
        "about/index.html: a poster link on a page that is due none",
    ),
}


def break_and_check(
    check_site: Any,
    good: Path,
    bad: Path,
    listed: Path,
    url: str,
    calendar_file: Path | None,
    broken: dict[str, tuple[str, Sabotage, str]],
    name: str,
) -> None:
    """Copy a good build, check it passes, apply one sabotage, assert that it
    changed a file, and assert check_site reports it."""
    rel, sabotage, expect = broken[name]
    shutil.copytree(good, bad)
    assert problems(check_site, bad, listed, url, calendar_file) == []
    block = BLOCK.search((bad / PAGE).read_text(encoding="utf-8"))
    assert block is not None
    target = bad / rel
    was = target.read_text(encoding="utf-8")
    now = sabotage(was, block.group(0))
    assert now != was  # the sabotage applied
    target.write_text(now, encoding="utf-8")
    found = problems(check_site, bad, listed, url, calendar_file)
    assert any(p.startswith(expect) or expect in p for p in found), found


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_check_site_catches_a_broken_poster_build(
    on: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    """Negative controls: each sabotage must change the build and be reported."""
    break_and_check(check_site, on, tmp_path / "bad", listed, "", None, BROKEN, name)


@pytest.mark.parametrize("name", sorted(BROKEN_WITH_CALENDAR))
def test_check_site_catches_a_broken_poster_build_with_a_calendar(
    everything: Path, listed: Path, calendar_list: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    break_and_check(check_site, everything, tmp_path / "bad", listed, SHOP, calendar_list, BROKEN_WITH_CALENDAR, name)
