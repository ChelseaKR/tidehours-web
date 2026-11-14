"""A station page's link to its printable tide calendar in the Tide Hours shop
on Etsy (docs/DECISIONS.md 0035, built as 0030 builds the booklet links): the
committed list is the calendars the owner listed (three on 2026-11-11, twelve from 2026-11-12, twenty-eight from 2026-11-13); an empty list leaves
no trace; one listed calendar puts one plain link on that station's page, and
since 0037 the same link on the page that lists the calendars, which every
English page's footer then links to; a bad entry is refused; the link leaves
when the calendar's year is over; the privacy page names the Etsy links by
what the build shows; and the link sits after the booklet sentence when both
show. Negative controls prove each new check_site rule can fail, each
asserting its sabotage changed the build. tests/test_station_posters.py and
tests/test_printables.py cover the posters and the list (0037).

The Guam listing id below is made up. It lives only in a list a test writes
to a temporary directory; the committed list holds the real ones."""

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
from markupsafe import escape

from tidehours import booklets, calendars, catalog, cli, posters

NOW = "2026-11-01T11:20:00Z"
STATION = "1630000"  # Apra Harbor, Guam
OTHER_STATION = "1631428"
LISTING = "1234567890"
TITLE = "2027 Tide Calendar: Apra Harbor"
URL = "https://www.etsy.com/listing/1234567890"
PAGE = f"stations/{STATION}/index.html"
# The page that lists the calendars (0037), and its link in the footer of a
# build that has calendars and no posters.
HUB = "tide-calendars/index.html"
FOOTER = ' · <a href="/tide-calendars/">Tide calendars</a>'
SENTENCE = "A printable 2027 tide calendar for this station is in the Tide Hours shop on Etsy: 2027 Tide Calendar: Apra Harbor."
SHOP = "https://www.etsy.com/shop/TideHours"
TAG = "tidehours-20"
ASIN = "B0TESTTEST"
# The committed list, as the owner gave it on 2026-11-12 and 2026-11-13.
COMMITTED = {
    "8413320": ("4614956632", "2027 Tide Calendar: Bar Harbor"),
    "9414131": ("4614960826", "2027 Tide Calendar: Half Moon Bay"),
    "9437540": ("4614965438", "2027 Tide Calendar: Garibaldi"),
    "9410230": ("4616040586", "2027 Tide Calendar: La Jolla"),
    "9413450": ("4616029561", "2027 Tide Calendar: Monterey"),
    "8444351": ("4616042968", "2027 Tide Calendar: Hull"),
    "8677344": ("4616031807", "2027 Tide Calendar: St. Simons Island"),
    "8570283": ("4616045426", "2027 Tide Calendar: Ocean City"),
    "9441102": ("4616046346", "2027 Tide Calendar: Westport"),
    "8410140": ("4616051522", "2027 Tide Calendar: Eastport"),
    "8447241": ("4616040791", "2027 Tide Calendar: Brewster Flats"),
    "8721164": ("4616053676", "2027 Tide Calendar: New Smyrna Beach"),
    "8446493": ("4616148066", "2027 Tide Calendar: Plymouth"),
    "8423898": ("4616137561", "2027 Tide Calendar: Portsmouth"),
    "8418911": ("4616138071", "2027 Tide Calendar: Kennebunkport"),
    "8418150": ("4616149760", "2027 Tide Calendar: Portland"),
    "9417426": ("4616150142", "2027 Tide Calendar: Fort Bragg"),
    "9446807": ("4616150530", "2027 Tide Calendar: Olympia"),
    "8440466": ("4616156716", "2027 Tide Calendar: Newburyport"),
    "8446166": ("4616154046", "2027 Tide Calendar: Duxbury"),
    "8446121": ("4616143255", "2027 Tide Calendar: Provincetown"),
    "8720587": ("4616143649", "2027 Tide Calendar: St. Augustine"),
    "8654400": ("4616144049", "2027 Tide Calendar: Hatteras Island"),
    "9455090": ("4616144439", "2027 Tide Calendar: Seward"),
    "8441841": ("4616144799", "2027 Tide Calendar: Gloucester"),
    "9442396": ("4616156330", "2027 Tide Calendar: La Push"),
    "9445478": ("4616157186", "2027 Tide Calendar: Hood Canal"),
    "9455558": ("4616157552", "2027 Tide Calendar: Homer"),
}
ETSY_A = re.compile(r'<a\b[^>]*href="(https?://[^"]*etsy\.[^"]*)"[^>]*>', re.I)
BLOCK = re.compile(r'<p class="calendar"[^>]*>.*?</p>', re.S)
BOOKLET = re.compile(r'<p class="booklet"[^>]*>.*?</p>', re.S)
SUFFIXES = (".html", ".xml", ".txt", ".json", ".css")
# The words and signs test_print_shop.py refuses (no claim, price or rating).
FORBIDDEN = re.compile(r"\b(best|top|only|first|cheap|deals?|rated|official)\b|[$%★]", re.I)
TERMS_OFF = "NOAA, other agency names, Apple and App Store are the names and trademarks of their owners."
TERMS_ON = "NOAA, other agency names, Apple, App Store and Etsy are the names and trademarks of their owners."
TERMS_ALL = "NOAA, other agency names, Apple, App Store, Amazon and Etsy are the names and trademarks of their owners."
# The privacy page's section on the Etsy links, in each case.
PRIVACY_SHOP_ONLY = (
    "Shop link",
    "The About and king tides pages link to the Tide Hours shop on Etsy, where the print is sold. "
    "This site sends nothing to Etsy. The link takes you to Etsy, where Etsy's own privacy policy applies.",
)
PRIVACY_BOTH = (
    "Shop links",
    "The About and king tides pages, the tide calendars page, and the station pages of towns with a printable "
    "calendar, link to the Tide Hours shop on Etsy. This site sends nothing to Etsy. The link takes you to Etsy, "
    "where Etsy's own privacy policy applies.",
)
PRIVACY_CALENDARS_ONLY = (
    "Shop links",
    "The tide calendars page, and the station pages of towns with a printable calendar, link to those calendars "
    "in the Tide Hours shop on Etsy. This site sends nothing to Etsy. The link takes you to Etsy, where Etsy's "
    "own privacy policy applies.",
)
# As the site is published: the print shop, the calendars and the posters.
PRIVACY_COMMITTED = (
    "Shop links",
    "The About and king tides pages, the tide calendars and posters page, and the station pages of towns with a "
    "printable calendar or poster, link to the Tide Hours shop on Etsy. This site sends nothing to Etsy. The link "
    "takes you to Etsy, where Etsy's own privacy policy applies.",
)
SHOP_SENTENCE = (
    "Tide Hours also sells a made-to-order print of the tide at one place on one day, and printable 2027 tide "
    "calendars for a few towns, all drawn from the same predictions as this site. They are in the Tide Hours "
    "shop on Etsy."
)
SHOP_SECTION = re.compile(r'<h2 id="shop">(.*?)</h2>\s*<p>(.*?)</p>', re.S)


def entry(**changes: Any) -> dict[str, Any]:
    return {"listing": LISTING, "year": 2027, "title": TITLE} | changes


def write_list(path: Path, entries: Any) -> Path:
    path.write_text(json.dumps({"calendars": entries}), encoding="utf-8")
    return path


def build(out: Path, list_file: Path | None, *extra: str, now: str = NOW, states: str = "GU") -> Path:
    args = ["--out", str(out), "--now", now, "--states", states, *extra]
    if list_file is not None:
        args += ["--calendars", str(list_file)]
    assert cli.main(args) == 0
    return out


@pytest.fixture(scope="module")
def empty(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "empty.json", {})


@pytest.fixture(scope="module")
def listed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "one.json", {STATION: entry()})


@pytest.fixture(scope="module")
def booklet_list(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("lists") / "booklets.json"
    entries = {STATION: {"asin": ASIN, "year": 2027, "title": "2027 Tide Tables: Apra Harbor"}}
    path.write_text(json.dumps({"booklets": entries}), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory, empty: Path) -> Path:
    return build(tmp_path_factory.mktemp("off"), empty, "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory, listed: Path) -> Path:
    """A calendar link with the print shop off."""
    return build(tmp_path_factory.mktemp("on"), listed, "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def shop_only(tmp_path_factory: pytest.TempPathFactory, empty: Path) -> Path:
    return build(tmp_path_factory.mktemp("shop"), empty, "--ga4-id", "G-TEST123", "--print-shop-url", SHOP)


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory, listed: Path) -> Path:
    """A calendar link with the print shop on: how the site is published."""
    return build(tmp_path_factory.mktemp("both"), listed, "--ga4-id", "G-TEST123", "--print-shop-url", SHOP)


@pytest.fixture(scope="module")
def everything(tmp_path_factory: pytest.TempPathFactory, listed: Path, booklet_list: Path) -> Path:
    """A booklet and a calendar on one page, with the affiliate switch and
    the print shop on."""
    return build(
        tmp_path_factory.mktemp("everything"),
        listed,
        "--booklets",
        str(booklet_list),
        "--amazon-tag",
        TAG,
        "--print-shop-url",
        SHOP,
    )


@pytest.fixture(scope="module")
def committed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The committed list, in the states of its stations, with the
    print shop on."""
    return build(
        tmp_path_factory.mktemp("committed"), None, "--print-shop-url", SHOP, states="ME,CA,OR,MA,GA,MD,WA,FL,NH,NC,AK"
    )


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_calendars", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def text_of(html: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def plain(html: str) -> str:
    """A sentence's words as they read, tags dropped in place."""
    return htmllib.unescape(re.sub(r"<[^>]+>", "", html)).strip()


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def traces(root: Path) -> list[str]:
    """Every file of a build that mentions Etsy or a calendar link at all.
    Shared by the empty-list test and its negative control."""
    found = []
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.suffix in SUFFIXES:
            body = f.read_text(encoding="utf-8").lower()
            if "etsy" in body or "data-calendar" in body:
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


@functools.cache
def the_catalog() -> catalog.Catalog:
    return catalog.load()


def problems(check_site: Any, root: Path, list_file: Path | None, url: str = "") -> list[str]:
    """What check_site's main does for Etsy: the pages due a calendar or
    poster link, from the lists and each page's own date, then the Etsy
    rules and the page that lists them (0037). The poster list is the
    committed one, which has no station in Guam."""
    want, undated = check_site.calendar_pages(root, calendars.load(list_file))
    want_posters, undated_posters = check_site.poster_pages(root, posters.load())
    found: list[str] = undated + undated_posters
    found += check_site.check_print_shop(root, pages(root), url, want, want_posters)
    found += check_site.check_printables(root, pages(root), the_catalog(), want, want_posters)
    return found


def shop_section(root: Path) -> list[tuple[str, str]]:
    return [(htmllib.unescape(h), htmllib.unescape(p)) for h, p in SHOP_SECTION.findall(read(root, "privacy"))]


# The list


def test_the_committed_list_is_the_owners_calendars() -> None:
    cat = catalog.load()
    listed = calendars.load()
    assert {sid: (c.listing, c.title) for sid, c in listed.items()} == COMMITTED
    for station_id, calendar in listed.items():
        assert cat.station(station_id) is not None, station_id
        assert calendar.year == 2027
        assert calendar.url == f"https://www.etsy.com/listing/{COMMITTED[station_id][0]}"


def test_valid_listing() -> None:
    for good in (LISTING, "4614956632", "123456"):
        assert calendars.valid_listing(good), good
    for bad in (
        "",
        "12345",  # too short to be a listing
        "0614956632",
        "4614956632 ",
        " 4614956632",
        "4614956632\n",
        "4614956632/2027-tide-calendar-bar-harbor",
        "4614956632?ref=shop_home",
        "461495663a",
        "４６１４９５６６３２",  # full-width digits are digits to str.isdigit, not to the pattern
        "https://www.etsy.com/listing/4614956632",
    ):
        assert not calendars.valid_listing(bad), bad


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ({STATION: entry(listing="12345678x0")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=URL)}, "is not an Etsy listing id"),
        ({STATION: entry(listing=LISTING + "/2027-tide-calendar-apra-harbor")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=LISTING + "?ref=shop_home")}, "is not an Etsy listing id"),
        ({STATION: entry(listing=1234567890)}, "is not an Etsy listing id"),
        ({STATION: entry(year="2027")}, "is not a year"),
        ({STATION: entry(year=True)}, "is not a year"),
        ({STATION: entry(year=27)}, "is not a year"),
        ({STATION: entry(title="Apra Harbor Tide Calendar 2027")}, "is not a title"),
        ({STATION: entry(title="2026 Tide Calendar: Apra Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Tables: Apra Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Calendar: Best Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Calendar: Official Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Calendar: Apra Harbor, $4.50")}, "is not a title"),
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
        calendars.load(bad)
    with pytest.raises(SystemExit, match="calendars: "):
        cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--calendars", str(bad)])
    assert not (tmp_path / "x").exists()  # refused before anything is built


def test_a_list_that_is_not_json_or_not_there_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"calendars": ', encoding="utf-8")
    for path in (broken, tmp_path / "missing.json"):
        with pytest.raises(SystemExit, match="calendars: "):
            cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--calendars", str(path)])
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"calendars": {}, "ref": "site"}), encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        calendars.load(extra)


def test_a_station_the_catalog_does_not_have_stops_the_build(tmp_path: Path) -> None:
    unknown = write_list(tmp_path / "unknown.json", {"9999999": entry()})
    with pytest.raises(ValueError, match="calendars: no station 9999999 in the catalog"):
        build(tmp_path / "x", unknown)


# The empty list


def test_an_empty_list_leaves_no_trace(off: Path, empty: Path, tmp_path: Path, check_site: Any) -> None:
    assert traces(off) == []
    assert not (off / HUB).exists()
    assert not any("tide-calendars" in f.read_text(encoding="utf-8") for f in off.rglob("*") if f.suffix in SUFFIXES)
    assert TERMS_OFF in text_of(read(off, "terms"))
    assert shop_section(off) == []
    assert problems(check_site, off, empty) == []
    # Guam has no calendar in the committed list, so the default build is the
    # same build, file for file.
    assert not any(station_id in (STATION, OTHER_STATION) for station_id in calendars.load())
    assert differing(off, build(tmp_path / "default", None, "--ga4-id", "G-TEST123")) == []


def test_the_empty_list_check_can_fail(off: Path, on: Path, empty: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: put the sentence into an empty-list build and both
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
        f"{PAGE}: a calendar link on a page that is due none",
        f"{PAGE}: mentions etsy with no shop address set",
    ]


# One listed calendar


def test_one_calendar_puts_one_link_on_one_page(off: Path, on: Path, listed: Path, check_site: Any) -> None:
    # Every English page's footer gains the link to the list (0037). Apart
    # from that, nothing but that station's page, the privacy and terms
    # pages, the list itself, the sitemap that now names it and the record
    # of fingerprints differs from the empty-list build.
    linking = {f.relative_to(on).as_posix() for f in pages(on) if FOOTER in f.read_text(encoding="utf-8")}
    assert linking == {f.relative_to(on).as_posix() for f in pages(on)} - {"es/king-tides/index.html"}
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
    assert blocks[0].count("<a ") == 1
    assert f'<a href="{URL}" rel="noopener">{TITLE}</a>' in blocks[0]
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
    assert sorted(traces(on)) == sorted(["privacy/index.html", PAGE, "terms/index.html", HUB])
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


def test_every_page_keeps_the_required_statements(both: Path, check_site: Any) -> None:
    found = [p for f in pages(both) for p in check_site.check_page(both, f) if "broken link" not in p]
    assert found == []


def test_the_sentence_makes_no_claim(on: Path) -> None:
    copy = json.loads(calendars.COPY.read_text(encoding="utf-8"))
    built = BLOCK.search(read(on, f"stations/{STATION}"))
    assert built is not None
    for prose in (*copy.values(), plain(built.group(0)), SHOP_SENTENCE):
        assert FORBIDDEN.search(prose) is None, prose
    assert calendars.block(None) is None


# The committed calendars


def test_the_committed_calendars_show_on_their_own_stations_only(committed: Path, check_site: Any) -> None:
    links: dict[str, list[str]] = {}
    for f in committed.rglob("*"):
        if f.is_file() and f.suffix in SUFFIXES:
            found = ETSY_A.findall(f.read_text(encoding="utf-8"))
            if found:
                links[f.relative_to(committed).as_posix()] = found
    # The six towns with a poster (0037) link to it after the calendar, and
    # the page that lists them all carries every listing once.
    poster_of = {sid: poster.url for sid, poster in posters.load().items()}
    assert len(poster_of) == 6 and set(poster_of) <= set(COMMITTED)
    want = {
        f"stations/{sid}/index.html": [
            f"https://www.etsy.com/listing/{listing}",
            *([poster_of[sid]] if sid in poster_of else []),
        ]
        for sid, (listing, _) in COMMITTED.items()
    }
    every = sorted(url for urls in want.values() for url in urls)
    assert len(every) == 34 and sorted(links.pop(HUB)) == every
    assert links == want | {"about/index.html": [SHOP], "king-tides/index.html": [SHOP]}
    for sid, (listing, title) in COMMITTED.items():
        html = read(committed, f"stations/{sid}")
        blocks = BLOCK.findall(html)
        assert len(blocks) == 1, sid
        assert plain(blocks[0]) == (
            f"A printable 2027 tide calendar for this station is in the Tide Hours shop on Etsy: {title}."
        )
        assert blocks[0] == (
            f'<p class="calendar" data-calendar="{listing}">A printable 2027 tide calendar for this station is in '
            f'the Tide Hours shop on Etsy: <a href="https://www.etsy.com/listing/{listing}" rel="noopener">'
            f"{title}</a>.</p>"
        )
    assert shop_section(committed) == [PRIVACY_COMMITTED]
    assert problems(check_site, committed, None, SHOP) == []


def test_the_committed_calendars_leave_on_january_1_2028(tmp_path: Path, check_site: Any) -> None:
    after = build(
        tmp_path / "2028",
        None,
        "--print-shop-url",
        SHOP,
        now="2028-01-01T11:20:00Z",
        states="ME,CA,OR,MA,GA,MD,WA,FL,NH,NC,AK",
    )
    for sid in COMMITTED:
        assert 'data-station-date="2028-01-01"' in read(after, f"stations/{sid}")
        assert "etsy" not in read(after, f"stations/{sid}").lower(), sid
    assert {f.relative_to(after).as_posix() for f in pages(after) if ETSY_A.search(f.read_text(encoding="utf-8"))} == {
        "about/index.html",
        "king-tides/index.html",
    }
    assert shop_section(after) == [PRIVACY_SHOP_ONLY]
    assert not (after / HUB).exists()
    assert problems(check_site, after, None, SHOP) == []


# The print shop's sentence and the privacy page, in each case


def test_the_print_shop_sentence_names_the_calendars(shop_only: Path, both: Path) -> None:
    for root in (shop_only, both):
        section = re.search(r'<section class="print-shop".*?</section>', read(root, "about"), re.S)
        assert section is not None
        sentence = re.search(r"<p>.*?</p>", section.group(0), re.S)
        assert sentence is not None
        assert plain(sentence.group(0)) == SHOP_SENTENCE
        assert ETSY_A.findall(section.group(0)) == [SHOP]


@pytest.mark.parametrize(
    ("fixture", "section", "terms"),
    [
        ("off", [], TERMS_OFF),
        ("shop_only", [PRIVACY_SHOP_ONLY], TERMS_ON),
        ("on", [PRIVACY_CALENDARS_ONLY], TERMS_ON),
        ("both", [PRIVACY_BOTH], TERMS_ON),
    ],
)
def test_privacy_names_the_etsy_links_the_build_has(
    request: pytest.FixtureRequest, fixture: str, section: list[tuple[str, str]], terms: str
) -> None:
    root: Path = request.getfixturevalue(fixture)
    assert shop_section(root) == section
    privacy = read(root, "privacy")
    assert ETSY_A.findall(privacy) == []
    said = text_of(privacy)
    assert ("station pages" in said) == (fixture in ("on", "both"))
    assert ("The About and king tides pages" in said) == (fixture in ("shop_only", "both"))
    assert "no accounts, no forms and no ads." in said  # the link is the site's own calendar, not an ad
    terms_text = text_of(read(root, "terms"))
    assert terms in terms_text and terms_text.count("Etsy") == (0 if fixture == "off" else 1)


def test_the_privacy_section_for_each_case_is_checked(
    off: Path, shop_only: Path, on: Path, both: Path, empty: Path, listed: Path, check_site: Any
) -> None:
    assert problems(check_site, off, empty) == []
    assert problems(check_site, shop_only, empty, SHOP) == []
    assert problems(check_site, on, listed) == []
    assert problems(check_site, both, listed, SHOP) == []


# The year


def test_shown_until_the_year_is_over() -> None:
    calendar = calendars.Calendar(LISTING, 2027, TITLE)
    assert calendars.shown(calendar, dt.date(2026, 11, 1))
    assert calendars.shown(calendar, dt.date(2027, 12, 31))
    assert not calendars.shown(calendar, dt.date(2028, 1, 1))


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
    want, undated = check_site.calendar_pages(with_list, calendars.load(listed))
    assert undated == [] and list(want) == ([PAGE] if shows else [])
    assert problems(check_site, with_list, listed) == []
    if not shows:
        # Nobody edited the list, and the build is the empty-list build again.
        assert traces(with_list) == []
        assert differing(with_list, build(tmp_path / "empty", empty, now=now)) == []


def test_check_site_catches_a_link_left_up_after_its_year(on: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: the same build, checked against a list whose
    calendar's year is over on the page's date."""
    past = write_list(tmp_path / "past.json", {STATION: entry(year=2025, title="2025 Tide Calendar: Apra Harbor")})
    due_now, _ = check_site.calendar_pages(on, calendars.load(past))
    assert due_now == {}  # the sabotage applied: the list no longer calls for the link
    assert f"{PAGE}: a calendar link on a page that is due none" in problems(check_site, on, past)


# Next to a booklet, the affiliate switch and the print shop


def test_with_a_booklet_the_booklet_line_comes_first(
    everything: Path, listed: Path, booklet_list: Path, check_site: Any
) -> None:
    html = read(everything, f"stations/{STATION}")
    booklet, calendar = BOOKLET.search(html), BLOCK.search(html)
    assert booklet is not None and calendar is not None
    assert booklet.end() <= calendar.start()
    assert plain(calendar.group(0)) == SENTENCE
    assert problems(check_site, everything, listed, SHOP) == []
    want, _ = check_site.booklet_pages(everything, booklets.load(booklet_list))
    assert check_site.check_affiliate(everything, pages(everything), TAG, want) == []
    assert TERMS_ALL in text_of(read(everything, "terms"))
    privacy = read(everything, "privacy")
    assert 'id="affiliate"' in privacy and 'id="booklets"' in privacy and 'id="shop"' in privacy
    assert shop_section(everything) == [PRIVACY_BOTH]


# Negative controls for check_site

LINK = f'href="{URL}"'
END_OF_LINK = 'rel="noopener">' + TITLE
NOT_THE_ADDRESS = f"is not the calendar's address, {URL}"
MISPLACED = f"{PAGE}: the calendar link is not between the tide tables and the closing notes"
OTHER_PAGE = f"stations/{OTHER_STATION}/index.html"
JSON_LD_TYPE = '"@type": "WebPage"'
PRIVACY = "privacy/index.html"
WRONG_SECTION = f"{PRIVACY}: the shop section is"
Sabotage = Callable[[str, str], str]  # (the file's text, the calendar sentence) -> the file's text, broken


def swap(old: str, new: str) -> Sabotage:
    return lambda text, block: text.replace(old, new)


def before(marker: str, addition: str | None = None) -> Sabotage:
    """Put `addition` (the calendar sentence, if None) in front of the first `marker`."""
    return lambda text, block: text.replace(marker, (addition or block) + marker, 1)


def move_before(marker: str) -> Sabotage:
    return lambda text, block: text.replace(block, "").replace(marker, block + marker, 1)


def esc(text: str) -> str:
    """As the templates escape it."""
    return str(escape(text))


def drop_section(text: str, block: str) -> str:
    return SHOP_SECTION.sub("", text)


# name -> (the file to break, how, the problem check_site must report), on
# a build with a calendar link and the print shop off.
BROKEN: dict[str, tuple[str, Sabotage, str]] = {
    "missing": (PAGE, lambda text, block: text.replace(block, ""), f"{PAGE}: 0 calendar links, exactly 1 expected"),
    "repeated": (
        PAGE,
        lambda text, block: text.replace(block, block + block),
        f"{PAGE}: 2 calendar links, exactly 1 expected",
    ),
    "slug": (
        PAGE,
        swap(LINK, f'href="{URL}/2027-tide-calendar-apra-harbor"'),
        f"{PAGE}: {URL}/2027-tide-calendar-apra-harbor {NOT_THE_ADDRESS}",
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
        swap(END_OF_LINK, 'rel="noopener" data-ga-event="calendar_click">' + TITLE),
        f"{PAGE}: the calendar link carries a click event",
    ),
    "second link": (
        PAGE,
        swap(f"{TITLE}</a>.</p>", f'{TITLE}</a>. <a href="/about/">About</a></p>'),
        f"{PAGE}: the calendar sentence has 2 links, exactly 1 expected",
    ),
    "before the tables": (PAGE, move_before('<section class="day"'), MISPLACED),
    "after the notes": (PAGE, move_before("</main>"), MISPLACED),
    "another station": (OTHER_PAGE, before("</main>"), f"{OTHER_PAGE}: a calendar link on a page that is due none"),
    "state page": (
        "states/gu/index.html",
        before("</main>"),
        "states/gu/index.html: a calendar link on a page that is due none",
    ),
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}" rel="noopener">Buy</a></p>'),
        f"{PAGE}: mentions etsy with no shop address set",
    ),
    "json-ld": (
        PAGE,
        swap(JSON_LD_TYPE, f'{JSON_LD_TYPE}, "sameAs": "{URL}"'),
        f"{PAGE}: mentions etsy with no shop address set",
    ),
    "privacy links": (
        PRIVACY,
        before("</main>", f'<p><a href="{URL}" rel="noopener">{TITLE}</a></p>'),
        f"{PRIVACY}: mentions etsy with no shop address set",
    ),
    "about names it": (
        "about/index.html",
        before("</main>", "<p>Our calendars are sold on Etsy.</p>"),
        "about/index.html: mentions etsy with no shop address set",
    ),
    "sitemap": ("sitemap.xml", before("</urlset>", f"<url><loc>{URL}</loc></url>"), "sitemap.xml: mentions etsy"),
    "llms.txt": ("llms.txt", lambda text, block: f"{text}\n- [{TITLE}]({URL})\n", "llms.txt: mentions etsy"),
    "undated": (
        PAGE,
        lambda text, block: re.sub(r' data-station-date="[^"]*"', "", text),
        f"{PAGE}: no date to tell whether its calendar's year is over",
    ),
    "privacy claims the shop link": (
        PRIVACY,
        swap(esc(PRIVACY_CALENDARS_ONLY[1]), esc(PRIVACY_BOTH[1])),
        WRONG_SECTION,
    ),
    "privacy says nothing": (PRIVACY, drop_section, WRONG_SECTION),
}

# The same where the print shop is on, as it is when the site is published.
BROKEN_SHOP: dict[str, tuple[str, Sabotage, str]] = {
    "query string": BROKEN["query string"],
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}" rel="noopener">Buy</a></p>'),
        f"{PAGE}: etsy link outside about/, king-tides/",
    ),
    "on the about page": (
        "about/index.html",
        before("</main>"),
        "about/index.html: a calendar link on a page that is due none",
    ),
    "privacy links": (
        PRIVACY,
        before("</main>", f'<p><a href="{URL}" rel="noopener">{TITLE}</a></p>'),
        f"{PRIVACY}: etsy link outside about/, king-tides/",
    ),
    "privacy leaves out the station pages": (
        PRIVACY,
        swap(esc(PRIVACY_BOTH[1]), esc(PRIVACY_SHOP_ONLY[1])),
        WRONG_SECTION,
    ),
}

# Where the build has a booklet sentence too.
BROKEN_WITH_BOOKLET: dict[str, tuple[str, Sabotage, str]] = {
    "before the booklet": (
        PAGE,
        lambda text, block: text.replace(block, "").replace('<p class="booklet"', block + '<p class="booklet"', 1),
        f"{PAGE}: the calendar link comes before the booklet link",
    ),
}


def break_and_check(
    check_site: Any,
    good: Path,
    bad: Path,
    listed: Path,
    url: str,
    broken: dict[str, tuple[str, Sabotage, str]],
    name: str,
) -> None:
    """Copy a good build, check it passes, apply one sabotage, assert that it
    changed a file, and assert check_site reports it."""
    rel, sabotage, expect = broken[name]
    shutil.copytree(good, bad)
    assert problems(check_site, bad, listed, url) == []
    block = BLOCK.search((bad / PAGE).read_text(encoding="utf-8"))
    assert block is not None
    target = bad / rel
    was = target.read_text(encoding="utf-8")
    now = sabotage(was, block.group(0))
    assert now != was  # the sabotage applied
    target.write_text(now, encoding="utf-8")
    found = problems(check_site, bad, listed, url)
    assert any(p.startswith(expect) or expect in p for p in found), found


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_check_site_catches_a_broken_calendar_build(
    on: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    """Negative controls: each sabotage must change the build and be reported."""
    break_and_check(check_site, on, tmp_path / "bad", listed, "", BROKEN, name)


@pytest.mark.parametrize("name", sorted(BROKEN_SHOP))
def test_check_site_catches_a_broken_calendar_build_with_the_print_shop_on(
    both: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    break_and_check(check_site, both, tmp_path / "bad", listed, SHOP, BROKEN_SHOP, name)


@pytest.mark.parametrize("name", sorted(BROKEN_WITH_BOOKLET))
def test_check_site_catches_a_broken_calendar_build_with_a_booklet(
    everything: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    break_and_check(check_site, everything, tmp_path / "bad", listed, SHOP, BROKEN_WITH_BOOKLET, name)


def test_check_site_catches_a_shop_section_with_no_etsy_link(
    off: Path, empty: Path, tmp_path: Path, check_site: Any
) -> None:
    """Negative control: a privacy section about Etsy links in a build that
    has none."""
    bad = tmp_path / "bad"
    shutil.copytree(off, bad)
    target = bad / PRIVACY
    was = target.read_text(encoding="utf-8")
    heading, body = PRIVACY_CALENDARS_ONLY
    now = was.replace("</main>", f'<h2 id="shop">{heading}</h2>\n<p>{esc(body)}</p></main>', 1)
    assert now != was  # the sabotage applied
    target.write_text(now, encoding="utf-8")
    found = problems(check_site, bad, empty)
    assert any(p.startswith(WRONG_SECTION) for p in found), found
