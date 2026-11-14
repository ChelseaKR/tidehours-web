"""The tide gifts page, tide-gifts/ (docs/DECISIONS.md 0041): the committed
list is exactly the listings marked live; an entry without the date it was
marked live, or otherwise not a listing, stops the build; the page lists the
calendars and posters the station pages link to, the live gifts and the
custom print, by kind and by town, word for word; every English page's
footer links to it and the Spanish page's does not; the privacy and terms
pages name it; and a build with nothing to list has no page. A link from
the page to a listing that no list carries, which covers one not marked
live, fails check_site. Negative controls prove each check_site rule for
the page can fail, each asserting its sabotage changed the build.

The Guam listing ids and ASIN below are made up. They live only in lists a
test writes to a temporary directory; the committed lists hold the real
ones."""

from __future__ import annotations

import datetime as dt
import functools
import importlib.util
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tidehours import booklets, calendars, catalog, cli, gifts, posters

# The committed list. tests/conftest.py points gifts.load() with no path at
# an empty one for the other test modules; here the site as published names
# this file.
COMMITTED = Path(gifts.__file__).parent / "copy" / "gifts.json"

NOW = "2026-11-14T11:20:00Z"
SHOP = "https://www.etsy.com/shop/TideHours"
# The states of the committed lists' stations.
STATES = "ME,CA,OR,MA,GA,MD,WA,FL,NH,NC,AK,SC,NJ,DE"
PAGE = "tide-gifts/index.html"
FOOTER = ' · <a href="/tide-gifts/">Tide gifts</a>'
TITLE = "Tide chart gifts and tide art prints | Tide Hours"
HEADING = "Tide chart gifts and tide art prints"
DESCRIPTION = (
    "Gifts from Tide Hours, listed by kind and by town: custom tide chart prints, a winter solstice print, tide art "
    "prints, tide posters, 2027 tide calendars, tide blanket patterns, cross-stitch patterns and moon phase calendars."
)
INTRO = (
    "Each one is made by Tide Hours. The tide gifts are drawn from the same tide predictions as this site: art, "
    "not for navigation, and not a NOAA product."
)
HOW = (
    "They are listed by kind, and by town within each kind. A town's name links to its tide times on this site, "
    "and each gift links to where it is sold, on Etsy."
)
SECTIONS = [
    "Custom tide chart prints",
    "Winter solstice print",
    "Tide rings art prints",
    "Year-of-tides posters",
    "Printable 2027 tide calendars",
    "Tide blanket patterns",
    "Cross-stitch patterns",
    "Moon phase calendars",
]
# The made-to-order prints of the list and the cross-stitch patterns: each
# line's words after the link are the listing's own approved description.
YEAR_IN_TIDES = (
    '<li data-gift="4617340915"><a href="https://www.etsy.com/listing/4617340915" rel="noopener">Your Year In '
    "Tides</a>. A whole year of tides at your place, drawn as rings, like the rings of a tree: the year someone "
    "was born, the year you married, the year you moved to the coast, or a year still ahead.</li>"
)
WEDDING_SIGN = (
    '<li data-gift="4617341518"><a href="https://www.etsy.com/listing/4617341518" rel="noopener">Beach Wedding '
    "Welcome Sign</a>. A welcome sign for a wedding by the water: the predicted tide at your town or beach on your "
    "wedding day, with the time of your ceremony marked on the curve.</li>"
)
STITCH_TEXT = (
    "<p>Full cross stitches only, 2 strands: no backstitch, no half or quarter stitches. No fabric, thread or kit "
    "is shipped. There are no month marks, times or heights on it: it is a picture of the year, not a calendar or "
    "a tide table.</p>"
)
SF_STITCH = (
    '<li data-gift="4617334117"><a href="/stations/9414290/">San Francisco</a>, California: '
    '<a href="https://www.etsy.com/listing/4617334117" rel="noopener">2027 Tide Rings Cross Stitch Pattern: San '
    "Francisco</a>. A counted cross-stitch pattern of the whole 2027 tide year at San Francisco, California, drawn "
    "as a spiral of rings, from the shop&#39;s Tide Rings poster. Cream and amber on navy.</li>"
)
# The solstice print's sentence: the wording of its live Etsy listing,
# adapted only to join its first two sentences of the second paragraph.
SOLSTICE = (
    "<p>The winter solstice in your city, December 21, 2026: the shortest day of the year, and the first bar on "
    "the page. After it come the 364 days to December 20, 2027, one thin bar for each, from midnight at the top to "
    "midnight at the bottom, so you can watch the light come back through spring to the long days of June and out "
    "again. Made to order as a digital file, for any city in the 50 states, Puerto Rico or the U.S. Virgin Islands; "
    "not interior or northern Alaska, Guam, the Northern Mariana Islands or American Samoa.</p>\n  "
    '<ul class="printables">\n    <li data-gift="4616980007"><a href="https://www.etsy.com/listing/4616980007" '
    'rel="noopener">2026 Winter Solstice Print: The Light Returns</a></li>'
)
SAN_FRANCISCO = (
    '<li data-gift="4617280124"><a href="/stations/9414290/">San Francisco</a>, California: '
    '<a href="https://www.etsy.com/listing/4617280124" rel="noopener">2027 Tide Rings: San Francisco</a></li>'
)
CUSTOM = (
    '<p data-gift="custom">A made-to-order print of the predicted tide at one place on one day, such as a wedding, '
    "a birth or the day you met, with a line of your own words. It is a digital file that you print. Order it in "
    'the <a href="https://www.etsy.com/shop/TideHours" rel="noopener">Tide Hours shop on Etsy</a>.</p>'
)
RINGS = (
    '<li data-gift="4617246732"><a href="/stations/8413320/">Bar Harbor</a>, Maine: '
    '<a href="https://www.etsy.com/listing/4617246732" rel="noopener">2027 Tide Rings: Bar Harbor</a></li>'
)
# The book line the Guam test list gives (one town).
GU_BOOK = (
    '<li data-gift="B0TESTAAAA"><a href="https://www.amazon.com/dp/B0TESTAAAA" rel="noopener">2027 Tide Tables: '
    "Apra Harbor</a>, a paperback book of every predicted high and low tide of 2027 at "
    '<a href="/stations/1630000/">Apra Harbor</a>.</li>'
)
MOON = (
    '<li data-gift="4616923752"><a href="https://www.etsy.com/listing/4616923752" rel="noopener">2027 Moon Phase '
    "Poster: Southern Hemisphere</a></li>"
)
SHOP_PRIVACY = (
    "The About and king tides pages, the tide calendars and posters page, the tide gifts page, and the station "
    "pages of towns with a printable calendar or poster, link to the Tide Hours shop on Etsy. This site sends "
    "nothing to Etsy. The link takes you to Etsy, where Etsy's own privacy policy applies."
)
BOOK_PRIVACY = (
    "The tide gifts page links to printed tide tables that Tide Hours publishes and sells on Amazon. They are "
    "plain links, not affiliate links, and this site sends nothing to Amazon. A link takes you to Amazon, where "
    "Amazon's own privacy notice applies."
)
# The committed list: each listing id, as marked "LISTED" in the owner's
# product notes, with its kind, title and the day it was marked. The Maine
# Coast hardcover is left out until the owner has checked her author copy.
LIVE = {
    "4617340915": ("custom", "Your Year In Tides", "2026-11-14"),
    "4617341518": ("custom", "Beach Wedding Welcome Sign", "2026-11-14"),
    "4617334117": ("stitch", "2027 Tide Rings Cross Stitch Pattern: San Francisco", "2026-11-14"),
    "4617336719": ("stitch", "2027 Tide Rings Cross Stitch Pattern: Bar Harbor", "2026-11-14"),
    "4616980007": ("daylight", "2026 Winter Solstice Print: The Light Returns", "2026-11-13"),
    "4617246732": ("rings", "2027 Tide Rings: Bar Harbor", "2026-11-14"),
    "4617240419": ("rings", "2027 Tide Rings: Monterey", "2026-11-14"),
    "4617280124": ("rings", "2027 Tide Rings: San Francisco", "2026-11-14"),
    "4617279303": ("rings", "2027 Tide Rings: Half Moon Bay", "2026-11-14"),
    "4616975320": ("blanket", "2027 Tide Blanket Pattern: Bar Harbor", "2026-11-13"),
    "4616976698": ("blanket", "2027 Tide Blanket Pattern: Half Moon Bay", "2026-11-13"),
    "4616888829": ("moon", "2027 Moon Phase Poster: US Time Zones", "2026-11-13"),
    "4616911593": ("moon", "2027 Moon Phase Calendar: US Time Zones", "2026-11-13"),
    "4616923752": ("moon", "2027 Moon Phase Poster: Southern Hemisphere", "2026-11-13"),
}
# A Guam list for the small builds: one of each kind.
GU = "1630000"  # Apra Harbor
GU_OTHER = "1631428"
TEST_GIFTS: list[dict[str, Any]] = [
    {"kind": "rings", "listing": "1234567892", "year": 2027, "title": "2027 Tide Rings: Apra Harbor",
     "station": GU, "live": "2026-11-14"},
    {"kind": "blanket", "listing": "1234567893", "year": 2027, "title": "2027 Tide Blanket Pattern: Apra Harbor",
     "station": GU_OTHER, "live": "2026-11-14"},
    {"kind": "moon", "listing": "1234567894", "year": 2027, "title": "2027 Moon Phase Poster: Guam", "live": "2026-11-14"},
    {"kind": "book", "asin": "B0TESTAAAA", "year": 2027, "title": "2027 Tide Tables: Apra Harbor",
     "format": "paperback", "towns": [["Apra Harbor", GU]], "live": "2026-11-14"},
    {"kind": "daylight", "listing": "1234567895", "year": 2026, "title": "2026 Winter Solstice Print: The Light Returns",
     "live": "2026-11-13", "until": "2026-12-22"},
    {"kind": "custom", "listing": "1234567896", "title": "Your Guam Print",
     "about": "A print of the tide at Apra Harbor, made for you.", "live": "2026-11-14"},
    {"kind": "stitch", "listing": "1234567897", "year": 2027, "title": "2027 Tide Rings Cross Stitch Pattern: Apra Harbor",
     "station": GU, "about": "A counted cross-stitch pattern of the 2027 tide year at Apra Harbor.", "live": "2026-11-14"},
]  # fmt: skip
ETSY_OR_AMAZON = re.compile(r'<a\b[^>]*href="(https?://[^"]*(?:etsy|amazon)\.[^"]*)"', re.I)
H2 = re.compile(r"<h2 id=\"g-[^\"]*\">(.*?)</h2>")


def write_list(path: Path, entries: Any) -> Path:
    path.write_text(json.dumps({"gifts": entries}), encoding="utf-8")
    return path


def build(out: Path, *extra: str, now: str = NOW, states: str = "GU") -> Path:
    assert cli.main(["--out", str(out), "--now", now, "--states", states, *extra]) == 0
    return out


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


@functools.cache
def the_catalog() -> catalog.Catalog:
    return catalog.load()


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_gifts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lists(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("gift-lists")
    (d / "no-calendars.json").write_text('{"calendars": {}}', encoding="utf-8")
    (d / "no-posters.json").write_text('{"posters": {}}', encoding="utf-8")
    return {
        "test": write_list(d / "test.json", TEST_GIFTS),
        "none": write_list(d / "none.json", []),
        "no calendars": d / "no-calendars.json",
        "no posters": d / "no-posters.json",
    }


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Every committed list, in the states of their stations, with the
    print shop on: how the site is published."""
    return build(
        tmp_path_factory.mktemp("published"), "--print-shop-url", SHOP, "--gifts", str(COMMITTED), states=STATES
    )


@pytest.fixture(scope="module")
def guam(tmp_path_factory: pytest.TempPathFactory, lists: dict[str, Path]) -> Path:
    """The Guam test list, no calendars or posters, the shop on."""
    return build(
        tmp_path_factory.mktemp("guam"),
        "--print-shop-url", SHOP, "--gifts", str(lists["test"]),
        "--calendars", str(lists["no calendars"]), "--posters", str(lists["no posters"]),
    )  # fmt: skip


def problems(
    check: Any,
    root: Path,
    *,
    shop: str = "",
    gifts_file: Path = COMMITTED,
    tag: str = "",
    calendars_file: Path | None = None,
    posters_file: Path | None = None,
) -> list[str]:
    """check_site's rules that the gifts page touches, on a partial build."""
    cat, html = the_catalog(), pages(root)
    cal, undated = check.calendar_pages(root, calendars.load(calendars_file))
    pos, more = check.poster_pages(root, posters.load(posters_file))
    book, most = check.booklet_pages(root, booklets.load())
    listing, last = check.gift_listing(root, cat, gifts.load(gifts_file), shop, cal, pos)
    out: list[str] = [*undated, *more, *most, *last]
    out += check.check_gifts(root, html, listing)
    out += check.check_print_shop(root, html, shop, cal, pos, gifts.has_etsy(listing))
    out += check.check_affiliate(root, html, tag, book, gifts.has_books(listing))
    out += check._check_book_notice(root, book, gifts.has_books(listing))
    out += check.check_printables(root, html, cat, cal, pos)
    if (root / PAGE).is_file():
        out += check.check_page(root, root / PAGE)
    return list(out)


# The committed list


def test_the_committed_list_is_exactly_the_listings_marked_live() -> None:
    listed = gifts.load(COMMITTED)
    assert {g.ref: (g.kind, g.title, g.live.isoformat()) for g in listed} == LIVE
    by_ref = {g.ref: g for g in listed}
    assert all(g.year == 2027 for g in listed if g.kind not in ("daylight", "custom"))
    assert all(g.year is None and g.station is None and g.about for g in listed if g.kind == "custom")
    assert by_ref["4617334117"].station == "9414290" and by_ref["4617336719"].station == "8413320"
    assert by_ref["4617246732"].station == "8413320" and by_ref["4617240419"].station == "9413450"
    assert by_ref["4617280124"].station == "9414290" and by_ref["4617279303"].station == "9414131"
    assert by_ref["4616975320"].station == "8413320" and by_ref["4616976698"].station == "9414131"
    solstice = by_ref["4616980007"]
    assert (solstice.year, solstice.until) == (2026, dt.date(2026, 12, 22)) and solstice.station is None
    assert all(g.until is None for g in listed if g.kind != "daylight")
    # No book until the owner has checked her author copy.
    assert not [g for g in listed if g.kind == "book"]
    # None of them is a calendar or poster the station pages already link to.
    elsewhere = {c.listing for c in calendars.load().values()} | {p.listing for p in posters.load().values()}
    assert not set(LIVE) & elsewhere


def without(entry: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if k != key}


RINGS_ENTRY = TEST_GIFTS[0]
BAD = {
    "no live date": [without(RINGS_ENTRY, "live")],
    "live is empty": [{**RINGS_ENTRY, "live": ""}],
    "live is a draft": [{**RINGS_ENTRY, "live": "draft"}],
    "live is a word": [{**RINGS_ENTRY, "live": "LISTED"}],
    "live is not a date": [{**RINGS_ENTRY, "live": "2026-13-40"}],
    "live is true": [{**RINGS_ENTRY, "live": True}],
    "a slug": [{**RINGS_ENTRY, "listing": "1234567892/tide-rings"}],
    "a whole address": [{**RINGS_ENTRY, "listing": "https://www.etsy.com/listing/1234567892"}],
    "a claim": [{**RINGS_ENTRY, "title": "2027 Tide Rings: Best Apra"}],
    "a price": [{**RINGS_ENTRY, "title": "2027 Tide Rings: Apra $10"}],
    "another year": [{**RINGS_ENTRY, "title": "2028 Tide Rings: Apra Harbor"}],
    "unknown kind": [{**RINGS_ENTRY, "kind": "mug"}],
    "extra key": [{**RINGS_ENTRY, "price": 10}],
    "no station": [without(RINGS_ENTRY, "station")],
    "unknown station": [{**RINGS_ENTRY, "station": "9999999"}],
    "listed twice": [RINGS_ENTRY, {**TEST_GIFTS[1], "listing": RINGS_ENTRY["listing"]}],
    "a calendar's listing": [{**RINGS_ENTRY, "listing": "4614956632"}],
    "a bad ASIN": [{**TEST_GIFTS[3], "asin": "B0testaaaa"}],
    "a bad format": [{**TEST_GIFTS[3], "format": "ebook"}],
    "no towns": [{**TEST_GIFTS[3], "towns": []}],
    "a town twice": [{**TEST_GIFTS[3], "towns": [["Apra Harbor", GU], ["Apra", GU]]}],
    "until is not a date": [{**TEST_GIFTS[4], "until": "after the solstice"}],
    "until is a time": [{**TEST_GIFTS[4], "until": "2026-12-22T08:00"}],
    "until before live": [{**TEST_GIFTS[4], "until": "2026-11-01"}],
    "a solstice print without until": [without(TEST_GIFTS[4], "until")],
    "two solstice prints": [TEST_GIFTS[4], {**TEST_GIFTS[4], "listing": "1234567896"}],
    "a solstice print's other title": [{**TEST_GIFTS[4], "title": "2026 Winter Solstice Print: Best Gift"}],
    "a custom print with a year": [{**TEST_GIFTS[5], "year": 2027}],
    "a custom print without about": [without(TEST_GIFTS[5], "about")],
    "a custom print not marked live": [without(TEST_GIFTS[5], "live")],
    "about with a price": [{**TEST_GIFTS[5], "about": "A print of the tide at your place, only $22 today."}],
    "about with a claim": [{**TEST_GIFTS[5], "about": "The best print of the tide at your place on your day."}],
    "about with markup": [{**TEST_GIFTS[5], "about": "A print of the <b>tide</b> at your place on your day."}],
    "about that is not a sentence": [{**TEST_GIFTS[5], "about": "tide"}],
    "a custom title with a claim": [{**TEST_GIFTS[5], "title": "Best Tide Print"}],
    "a pattern without a station": [without(TEST_GIFTS[6], "station")],
    "a pattern without about": [without(TEST_GIFTS[6], "about")],
    "a pattern's other title": [{**TEST_GIFTS[6], "title": "2027 Tide Stitch: Apra Harbor"}],
}


@pytest.mark.parametrize("entries", BAD.values(), ids=BAD.keys())
def test_an_entry_not_marked_live_or_not_a_listing_stops_the_build(tmp_path: Path, entries: Any) -> None:
    path = write_list(tmp_path / "gifts.json", entries)
    with pytest.raises((SystemExit, ValueError)):
        cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--gifts", str(path)])
    assert not (tmp_path / "x" / PAGE).exists()


# The page as published


def test_the_published_page_word_for_word(published: Path, check_site: Any) -> None:
    text = read(published, PAGE)
    assert f"<title>{TITLE}</title>" in text
    assert f'<meta name="description" content="{DESCRIPTION}">' in text
    main = text[text.find("<main") : text.find("</main>")]
    assert f"<h1>{HEADING}</h1>" in main
    assert '<p class="lead">' + INTRO + "</p>" in main
    assert "<p>" + HOW.replace("'", "&#39;") + "</p>" in main
    assert H2.findall(main) == SECTIONS
    for line in (CUSTOM, SOLSTICE, RINGS, SAN_FRANCISCO, MOON, YEAR_IN_TIDES, WEDDING_SIGN, STITCH_TEXT, SF_STITCH):
        assert line in main
    # Every calendar and poster the station pages show, and every live gift,
    # once each: 40 + 6 + 14 listings and the shop.
    hrefs = ETSY_OR_AMAZON.findall(main)
    want = {c.url for c in calendars.load().values()} | {p.url for p in posters.load().values()}
    want |= {g.url for g in gifts.load(COMMITTED)} | {SHOP}
    assert sorted(hrefs) == sorted(want) and len(hrefs) == 40 + 6 + 14 + 1
    # Within a kind, by town.
    section = main[main.find('id="g-calendars"') : main.find('id="g-blanket"')]
    towns = re.findall(r'<a href="/stations/\d+/">([^<]*)</a>', section)
    assert towns == sorted(towns, key=str.lower) and len(towns) == 40
    assert problems(check_site, published, shop=SHOP) == []


def test_the_page_names_no_price_sale_or_rating_and_has_no_product_markup(published: Path) -> None:
    text = read(published, PAGE)
    main = text[text.find("<main") : text.find("</main>")]
    words = re.sub(r"<[^>]+>", " ", main)
    assert not re.search(r"[$%★]|\b(sale|discount|off|best|cheap|deal|rated|review)\b", words, re.I)
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
        assert "Product" not in block and "Offer" not in block and "etsy" not in block.lower()
        assert "amazon" not in block.lower() and "Review" not in block and "Rating" not in block
    assert "data-ga" not in main and "?" not in "".join(ETSY_OR_AMAZON.findall(main))


def test_every_english_footer_links_to_the_page_and_the_spanish_does_not(published: Path) -> None:
    for f in pages(published):
        text = f.read_text(encoding="utf-8")
        want = 1 if '<html lang="en">' in text else 0
        assert text.count('href="/tide-gifts/"') == want, f
    assert FOOTER in read(published, "index.html")
    assert FOOTER in read(published, "stations/8413320/index.html")
    assert FOOTER not in read(published, "es/king-tides/index.html")


def test_the_page_is_in_the_sitemap_and_not_in_llms_txt(published: Path) -> None:
    assert "<loc>https://tidehours.com/tide-gifts/</loc>" in read(published, "sitemap.xml")
    assert '"/tide-gifts/"' in read(published, "lastmod.json")
    assert "tide-gifts" not in read(published, "llms.txt")


def test_privacy_and_terms_name_the_page(published: Path) -> None:
    privacy = read(published, "privacy/index.html").replace("&#39;", "'")
    assert f'<h2 id="shop">Shop links</h2>\n<p>{SHOP_PRIVACY}</p>' in privacy
    assert 'id="booklets"' not in privacy and "Book links" not in privacy
    assert "no ads" in privacy
    terms = read(published, "terms/index.html")
    assert "Etsy" in terms and "Amazon" not in terms


def test_with_no_book_entry_nothing_links_to_or_names_amazon(published: Path, check_site: Any) -> None:
    """The committed list has no book: no page or file of the published
    build links to Amazon or names it, the gifts page has no "Printed tide
    tables" section, and check_site agrees."""
    assert not [g for g in gifts.load(COMMITTED) if g.kind == "book"]
    for f in published.rglob("*"):
        if f.is_file() and f.suffix in {".html", ".xml", ".txt", ".json"}:
            assert "amazon" not in f.read_text(encoding="utf-8").lower(), f
    assert "Printed tide tables" not in read(published, PAGE)
    assert problems(check_site, published, shop=SHOP) == []


# Other builds


def test_with_the_shop_off_there_is_no_custom_print(tmp_path: Path, lists: dict[str, Path], check_site: Any) -> None:
    root = build(tmp_path / "s", "--gifts", str(lists["test"]), "--calendars", str(lists["no calendars"]),
                 "--posters", str(lists["no posters"]))  # fmt: skip
    text = read(root, PAGE)
    assert 'data-gift="custom"' not in text and "etsy.com/shop" not in text
    privacy = read(root, "privacy/index.html").replace("&#39;", "'")
    assert (
        "<p>The tide gifts page links to listings in the Tide Hours shop on Etsy. This site sends nothing to Etsy."
    ) in privacy
    assert problems(check_site, root, gifts_file=lists["test"], calendars_file=lists["no calendars"],
                    posters_file=lists["no posters"]) == []  # fmt: skip


def test_a_one_town_book_and_the_guam_list(guam: Path, lists: dict[str, Path], check_site: Any) -> None:
    text = read(guam, PAGE)
    assert GU_BOOK in text
    assert H2.findall(text) == [
        "Custom tide chart prints", "Winter solstice print", "Tide rings art prints", "Tide blanket patterns",
        "Cross-stitch patterns", "Printed tide tables", "Moon phase calendars",
    ]  # fmt: skip
    assert "Amazon" in read(guam, "terms/index.html")
    privacy = read(guam, "privacy/index.html").replace("&#39;", "'")
    assert "<p>The About and king tides pages and the tide gifts page link to the Tide Hours shop on Etsy." in privacy
    assert f"<p>{BOOK_PRIVACY}</p>" in privacy
    assert problems(check_site, guam, shop=SHOP, gifts_file=lists["test"], calendars_file=lists["no calendars"],
                    posters_file=lists["no posters"]) == []  # fmt: skip


def test_only_a_moon_calendar_names_no_art_and_no_amazon(tmp_path: Path, lists: dict[str, Path]) -> None:
    path = write_list(tmp_path / "moon.json", [TEST_GIFTS[2]])
    root = build(tmp_path / "s", "--gifts", str(path), "--calendars", str(lists["no calendars"]),
                 "--posters", str(lists["no posters"]))  # fmt: skip
    text = read(root, PAGE)
    assert "<title>Tide chart gifts | Tide Hours</title>" in text
    assert "each gift links to where it is sold, on Etsy.</p>" in text
    assert "amazon" not in "".join(f.read_text(encoding="utf-8").lower() for f in pages(root))
    assert 'id="booklets"' not in read(root, "privacy/index.html")


def test_in_2028_the_page_lists_only_the_made_to_order_prints(tmp_path: Path, check_site: Any) -> None:
    """Every dated entry of the committed lists is of 2026 or 2027, so the
    build of January 1, 2028 lists only the custom prints, which have no
    year: the shop's own sentence and the two made-to-order listings."""
    root = build(tmp_path / "on", "--print-shop-url", SHOP, "--gifts", str(COMMITTED),
                 now="2028-01-01T11:20:00Z", states="ME")  # fmt: skip
    text = read(root, PAGE)
    assert H2.findall(text) == ["Custom tide chart prints"]
    assert sorted(ETSY_OR_AMAZON.findall(text)) == sorted(
        [SHOP, "https://www.etsy.com/listing/4617340915", "https://www.etsy.com/listing/4617341518"]
    )
    assert "amazon" not in "".join(f.read_text(encoding="utf-8").lower() for f in pages(root))
    assert problems(check_site, root, shop=SHOP) == []
    off = build(tmp_path / "off", "--gifts", str(COMMITTED), now="2028-01-01T11:20:00Z", states="ME")
    text = read(off, PAGE)
    assert 'data-gift="custom"' not in text and "etsy.com/shop" not in text
    assert YEAR_IN_TIDES in text and WEDDING_SIGN in text
    assert problems(check_site, off) == []


def test_calendars_posters_and_the_custom_print_alone_make_no_page(
    tmp_path: Path, lists: dict[str, Path], check_site: Any
) -> None:
    """tide-calendars/ and the print shop link already list them."""
    root = build(tmp_path / "s", "--print-shop-url", SHOP, "--gifts", str(lists["none"]), states="ME")
    assert (root / "tide-calendars/index.html").exists() and not (root / PAGE).exists()
    assert all("tide-gifts" not in f.read_text(encoding="utf-8") for f in pages(root))
    assert problems(check_site, root, shop=SHOP, gifts_file=lists["none"]) == []


def test_nothing_to_list_leaves_no_trace(tmp_path: Path, lists: dict[str, Path], check_site: Any) -> None:
    root = build(tmp_path / "s", "--gifts", str(lists["none"]), "--calendars", str(lists["no calendars"]),
                 "--posters", str(lists["no posters"]))  # fmt: skip
    assert not (root / PAGE).exists()
    assert all("tide-gifts" not in f.read_text(encoding="utf-8") for f in pages(root))
    assert problems(check_site, root, gifts_file=lists["none"], calendars_file=lists["no calendars"],
                    posters_file=lists["no posters"]) == []  # fmt: skip


SOLSTICE_ONLY = [TEST_GIFTS[0], TEST_GIFTS[4]]  # the Guam rings and the solstice print


@pytest.mark.parametrize(
    ("now", "shown"),
    [
        ("2026-12-21T11:20:00Z", True),  # the last daily build before the solstice print leaves
        ("2026-12-22T07:59:00Z", True),  # 23:59 on December 21 in Pacific time
        ("2026-12-22T08:00:00Z", False),  # midnight, December 22, Pacific
        ("2026-12-22T11:20:00Z", False),  # the daily build of December 22
    ],
)
def test_the_solstice_print_leaves_on_its_until_day_in_pacific_time(
    tmp_path: Path, check_site: Any, now: str, shown: bool
) -> None:
    path = write_list(tmp_path / "gifts.json", SOLSTICE_ONLY)
    root = build(tmp_path / "s", "--gifts", str(path), now=now, states="CA,GU")
    text = read(root, PAGE)
    assert ("listing/1234567895" in text) is shown
    assert ("Winter solstice print" in text) is shown
    assert "Tide rings art prints" in text
    assert problems(check_site, root, gifts_file=path) == []


def test_with_the_shop_off_the_custom_section_lists_its_prints_alone(
    tmp_path: Path, lists: dict[str, Path], check_site: Any
) -> None:
    root = build(tmp_path / "s", "--gifts", str(lists["test"]), "--calendars", str(lists["no calendars"]),
                 "--posters", str(lists["no posters"]))  # fmt: skip
    text = read(root, PAGE)
    section = text[text.find('id="g-custom"') : text.find("</section>", text.find('id="g-custom"'))]
    assert "<p" not in section and 'data-gift="1234567896"' in section
    assert "Your Guam Print</a>. A print of the tide at Apra Harbor, made for you.</li>" in section
    assert problems(check_site, root, gifts_file=lists["test"], calendars_file=lists["no calendars"],
                    posters_file=lists["no posters"]) == []  # fmt: skip


def test_check_site_catches_a_solstice_print_shown_past_its_until(tmp_path: Path, check_site: Any) -> None:
    """The December 21 page, checked against a list that says the print
    left that day: the page still lists it, so check_site fails."""
    path = write_list(tmp_path / "gifts.json", SOLSTICE_ONLY)
    root = build(tmp_path / "s", "--gifts", str(path), now="2026-12-21T11:20:00Z", states="CA,GU")
    assert problems(check_site, root, gifts_file=path) == []
    earlier = write_list(tmp_path / "earlier.json", [TEST_GIFTS[0], {**TEST_GIFTS[4], "until": "2026-12-21"}])
    found = problems(check_site, root, gifts_file=earlier)
    assert f"{PAGE}: https://www.etsy.com/listing/1234567895 is not a live listing this build lists" in found


def test_the_affiliate_switch_leaves_the_book_link_untagged(
    tmp_path: Path, lists: dict[str, Path], check_site: Any
) -> None:
    root = build(tmp_path / "s", "--amazon-tag", "tidehours-20", "--gifts", str(lists["test"]),
                 "--calendars", str(lists["no calendars"]), "--posters", str(lists["no posters"]))  # fmt: skip
    assert 'href="https://www.amazon.com/dp/B0TESTAAAA" rel="noopener"' in read(root, PAGE)
    assert "tag=" not in read(root, PAGE)
    assert problems(check_site, root, tag="tidehours-20", gifts_file=lists["test"],
                    calendars_file=lists["no calendars"], posters_file=lists["no posters"]) == []  # fmt: skip


def test_the_accessibility_sample_has_the_page(published: Path) -> None:
    path = Path(__file__).resolve().parent.parent / "scripts" / "site_sample.py"
    spec = importlib.util.spec_from_file_location("site_sample_for_gifts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "tide-gifts/" in module.sample(published)


# Negative controls: each sabotage changes the Guam build, and check_site
# then fails it. The first three are links to a listing that is not marked
# live: no list carries it, so the page may not link to it.

NOT_LIVE = "https://www.etsy.com/listing/4617999999"


def add_link(href: str) -> Callable[[Path], None]:
    def sabotage(root: Path) -> None:
        f = root / PAGE
        text = f.read_text(encoding="utf-8")
        f.write_text(text.replace("</ul>", f'<li><a href="{href}" rel="noopener">Draft</a></li></ul>', 1), "utf-8")

    return sabotage


def edit(rel: str, old: str, new: str, count: int = 1) -> Callable[[Path], None]:
    def sabotage(root: Path) -> None:
        f = root / rel
        f.write_text(f.read_text(encoding="utf-8").replace(old, new, count), encoding="utf-8")

    return sabotage


def remove_page(root: Path) -> None:
    (root / PAGE).unlink()


SABOTAGE: dict[str, Callable[[Path], None]] = {
    "a listing not marked live": add_link(NOT_LIVE),
    "a book not marked live": add_link("https://www.amazon.com/dp/B0NOTLIVE0"),
    "a live listing swapped for one that is not": edit(PAGE, "https://www.etsy.com/listing/1234567894", NOT_LIVE),
    "a gift left out": edit(PAGE, '<li data-gift="1234567894">', '<li data-gift="x">'),
    "a slug": edit(PAGE, "listing/1234567892", "listing/1234567892/tide-rings"),
    "a query string": edit(PAGE, "dp/B0TESTAAAA", "dp/B0TESTAAAA?tag=tidehours-20"),
    "sponsored rel": edit(PAGE, 'rel="noopener">2027 Tide Rings', 'rel="sponsored noopener">2027 Tide Rings'),
    "click event": edit(PAGE, 'rel="noopener">2027 Moon', 'rel="noopener" data-ga="x">2027 Moon'),
    "another title": edit(PAGE, "2027 Tide Rings: Apra Harbor", "2027 Tide Rings: Apra"),
    "a price": edit(PAGE, "A printable digital download.", "A printable digital download, $10."),
    "a sale": edit(PAGE, "A printable digital download.", "A printable digital download, on sale."),
    "a claim": edit(PAGE, "A printable digital download.", "The best printable digital download."),
    "the page title": edit(PAGE, "<title>Tide chart gifts", "<title>Tide gifts"),
    "the intro": edit(PAGE, "art, not for navigation", "art"),
    "a section heading": edit(PAGE, "Moon phase calendars</h2>", "Moon calendars</h2>"),
    "etsy in json-ld": edit(
        PAGE, "</head>", '<script type="application/ld+json">{"url": "https://www.etsy.com/x"}</script></head>'
    ),
    "the custom print's shop link": edit(
        PAGE, "https://www.etsy.com/shop/TideHours", "https://www.etsy.com/shop/Other"
    ),
    "a custom print's listing swapped for one not marked live": edit(
        PAGE, "https://www.etsy.com/listing/1234567896", NOT_LIVE
    ),
    "a pattern's listing swapped for one not marked live": edit(
        PAGE, "https://www.etsy.com/listing/1234567897", NOT_LIVE
    ),
    "a custom print's words changed": edit(PAGE, "made for you.", "made for you, fast."),
    "a pattern's words dropped": edit(
        PAGE, ". A counted cross-stitch pattern of the 2027 tide year at Apra Harbor.", ""
    ),
    "the pattern section's sentence": edit(PAGE, "No fabric, thread or kit is shipped. ", ""),
    "no page": remove_page,
    "no footer link": edit("index.html", FOOTER, ""),
    "two footer links": edit("about/index.html", FOOTER, FOOTER + FOOTER),
    "a footer link on the Spanish page": edit(
        "es/king-tides/index.html", "</footer>", '<a href="/tide-gifts/">Regalos</a></footer>'
    ),
    "privacy leaves out the page": edit("privacy/index.html", " and the tide gifts page", ""),
    "privacy leaves out the book": edit("privacy/index.html", '<h2 id="booklets">', '<h2 id="other">'),
    "about links a listing": edit(
        "about/index.html", "</main>", f'<p><a href="{NOT_LIVE}" rel="noopener">x</a></p></main>'
    ),
    "terms links the book": edit(
        "terms/index.html", "</main>", '<p><a href="https://www.amazon.com/dp/B0TESTAAAA">x</a></p></main>'
    ),
}


@pytest.mark.parametrize("sabotage", SABOTAGE.values(), ids=SABOTAGE.keys())
def test_check_site_catches_a_broken_gifts_page(
    guam: Path, lists: dict[str, Path], check_site: Any, tmp_path: Path, sabotage: Callable[[Path], None]
) -> None:
    root = tmp_path / "s"
    shutil.copytree(guam, root)
    before = {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}
    sabotage(root)
    after = {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}
    assert after != before, "the sabotage changed nothing"
    found = problems(check_site, root, shop=SHOP, gifts_file=lists["test"], calendars_file=lists["no calendars"],
                     posters_file=lists["no posters"])  # fmt: skip
    assert found


def test_a_link_to_a_listing_not_marked_live_is_named(
    guam: Path, lists: dict[str, Path], check_site: Any, tmp_path: Path
) -> None:
    root = tmp_path / "s"
    shutil.copytree(guam, root)
    add_link(NOT_LIVE)(root)
    found = problems(check_site, root, shop=SHOP, gifts_file=lists["test"], calendars_file=lists["no calendars"],
                     posters_file=lists["no posters"])  # fmt: skip
    assert f"{PAGE}: {NOT_LIVE} is not a live listing this build lists" in found


def test_a_page_in_a_build_with_nothing_to_list_fails(
    guam: Path, lists: dict[str, Path], check_site: Any, tmp_path: Path
) -> None:
    root = tmp_path / "s"
    shutil.copytree(guam, root)
    found = problems(check_site, root, gifts_file=lists["none"], calendars_file=lists["no calendars"],
                     posters_file=lists["no posters"])  # fmt: skip
    assert f"{PAGE}: a gifts page in a build with nothing to list" in found
