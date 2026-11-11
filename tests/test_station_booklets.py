"""A station page's link to its printed booklet on Amazon (docs/DECISIONS.md
0030): an empty list leaves no trace; one listed booklet puts one plain link
on that station's page and nowhere else, with the privacy and terms lines;
a bad entry is refused; the link leaves when the booklet's year is over; and
it stays untagged next to the affiliate switch. Negative controls prove each
new check_site rule can fail, each asserting its sabotage changed the build.

The ASIN below is made up. It lives only in a list a test writes to a
temporary directory; the committed list holds real ones or none."""

from __future__ import annotations

import datetime as dt
import html as htmllib
import importlib.util
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tidehours import booklets, catalog, cli

NOW = "2026-11-01T11:20:00Z"
STATION = "1630000"  # Apra Harbor, Guam
OTHER_STATION = "1631428"
ASIN = "B0TESTTEST"
TITLE = "2027 Tide Tables: Apra Harbor"
URL = "https://www.amazon.com/dp/B0TESTTEST"
PAGE = f"stations/{STATION}/index.html"
SENTENCE = "A printed 2027 tide table for this station is sold on Amazon as 2027 Tide Tables: Apra Harbor."
TAG = "tidehours-20"
SHOP = "https://www.etsy.com/shop/TideHours"
AMAZON_A = re.compile(r'<a\b[^>]*href="(https?://[^"]*amazon\.[^"]*)"[^>]*>', re.I)
BLOCK = re.compile(r'<p class="booklet"[^>]*>.*?</p>', re.S)
SUFFIXES = (".html", ".xml", ".txt", ".json", ".css")
# The words and signs test_print_shop.py refuses (no claim, price or rating).
FORBIDDEN = re.compile(r"\b(best|top|only|first|cheap|deals?|rated|official)\b|[$%★]", re.I)
TERMS_OFF = "NOAA, other agency names, Apple and App Store are the names and trademarks of their owners."
TERMS_ON = "NOAA, other agency names, Apple, App Store and Amazon are the names and trademarks of their owners."
TERMS_ALL = "NOAA, other agency names, Apple, App Store, Amazon and Etsy are the names and trademarks of their owners."


def entry(**changes: Any) -> dict[str, Any]:
    return {"asin": ASIN, "year": 2027, "title": TITLE} | changes


def write_list(path: Path, entries: Any) -> Path:
    path.write_text(json.dumps({"booklets": entries}), encoding="utf-8")
    return path


def build(out: Path, list_file: Path | None, *extra: str, now: str = NOW) -> Path:
    args = ["--out", str(out), "--now", now, "--states", "GU", *extra]
    if list_file is not None:
        args += ["--booklets", str(list_file)]
    assert cli.main(args) == 0
    return out


@pytest.fixture(scope="module")
def empty(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "empty.json", {})


@pytest.fixture(scope="module")
def listed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_list(tmp_path_factory.mktemp("lists") / "one.json", {STATION: entry()})


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory, empty: Path) -> Path:
    return build(tmp_path_factory.mktemp("off"), empty, "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory, listed: Path) -> Path:
    return build(tmp_path_factory.mktemp("on"), listed, "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory, listed: Path) -> Path:
    """The affiliate switch, the print shop and a booklet, all at once."""
    return build(
        tmp_path_factory.mktemp("both"), listed, "--ga4-id", "G-TEST123", "--amazon-tag", TAG, "--print-shop-url", SHOP
    )


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_booklets", path)
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
    """Every file of a build that mentions Amazon or a booklet at all.
    Shared by the empty-list test and its negative control."""
    found = []
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.suffix in SUFFIXES:
            body = f.read_text(encoding="utf-8").lower()
            if "amazon" in body or "booklet" in body:
                found.append(f.relative_to(root).as_posix())
    return found


def differing(a: Path, b: Path) -> list[str]:
    """The files that are in only one of two builds, or differ in a byte."""
    names = {f.relative_to(root).as_posix() for root in (a, b) for f in root.rglob("*") if f.is_file()}
    return sorted(
        n
        for n in names
        if not ((a / n).is_file() and (b / n).is_file() and (a / n).read_bytes() == (b / n).read_bytes())
    )


def problems(check_site: Any, root: Path, list_file: Path, tag: str = "") -> list[str]:
    """What check_site's main does for Amazon: the pages due a booklet link,
    from the list and each page's own date, then the Amazon rules."""
    want, undated = check_site.booklet_pages(root, booklets.load(list_file))
    found: list[str] = undated + check_site.check_affiliate(root, pages(root), tag, want)
    return found


def statement_problems(check_site: Any, root: Path) -> list[str]:
    """check_site's page check on every page: the disclaimers, the NOAA
    credit, nothing absent rendered as a value. Its link check is left out:
    a Guam-only build has no pages for the West Coast stations the king-tide
    pages link to."""
    return [p for f in pages(root) for p in check_site.check_page(root, f) if "broken link" not in p]


# The list


def test_the_committed_list_loads_and_names_real_stations() -> None:
    cat = catalog.load()
    for station_id, booklet in booklets.load().items():
        assert cat.station(station_id) is not None, station_id
        assert booklet.url == f"https://www.amazon.com/dp/{booklet.asin}"


def test_valid_asin() -> None:
    for good in (ASIN, "B0D1ABCDE2", "0306406152", "080442957X"):
        assert booklets.valid_asin(good), good
    for bad in (
        "",
        "b0testtest",
        "B0TESTTES",
        "B0TESTTEST1",
        "B0TESTTEST ",
        "B0TESTTEST\n",
        "B0TEST-EST",
        "A0TESTTEST",
        "0306406153",  # an ISBN-10 with the wrong check digit
        "030640615x",
        URL,
        ASIN + "?tag=" + TAG,
    ):
        assert not booklets.valid_asin(bad), bad


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ({STATION: entry(asin="b0testtest")}, "is not an ASIN"),
        ({STATION: entry(asin=URL)}, "is not an ASIN"),
        ({STATION: entry(asin=ASIN + "?tag=" + TAG)}, "is not an ASIN"),
        ({STATION: entry(asin=1630000000)}, "is not an ASIN"),
        ({STATION: entry(year="2027")}, "is not a year"),
        ({STATION: entry(year=True)}, "is not a year"),
        ({STATION: entry(year=27)}, "is not a year"),
        ({STATION: entry(title="Apra Harbor Tide Tables 2027")}, "is not a title"),
        ({STATION: entry(title="2026 Tide Tables: Apra Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Tables: Best Harbor")}, "is not a title"),
        ({STATION: entry(title="2027 Tide Tables: Apra Harbor, $9.99")}, "is not a title"),
        ({STATION: entry(title=2027)}, "is not a title"),
        ({STATION: entry(tag=TAG)}, "exactly asin, year and title"),
        ({STATION: {"asin": ASIN, "year": 2027}}, "exactly asin, year and title"),
        ({STATION: ASIN}, "exactly asin, year and title"),
        ({"163000": entry()}, "is not a station id"),
        ({STATION: entry(), OTHER_STATION: entry()}, "one ASIN is listed for two stations"),
        ([entry()], "expected"),
    ],
)
def test_a_bad_list_is_refused(tmp_path: Path, entries: Any, message: str) -> None:
    bad = write_list(tmp_path / "bad.json", entries)
    with pytest.raises(ValueError, match=re.escape(message)):
        booklets.load(bad)
    with pytest.raises(SystemExit, match="booklets: "):
        cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--booklets", str(bad)])
    assert not (tmp_path / "x").exists()  # refused before anything is built


def test_a_list_that_is_not_json_or_not_there_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"booklets": ', encoding="utf-8")
    for path in (broken, tmp_path / "missing.json"):
        with pytest.raises(SystemExit, match="booklets: "):
            cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--booklets", str(path)])
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"booklets": {}, "tag": TAG}), encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        booklets.load(extra)


def test_a_station_the_catalog_does_not_have_stops_the_build(tmp_path: Path) -> None:
    unknown = write_list(tmp_path / "unknown.json", {"9999999": entry()})
    with pytest.raises(ValueError, match="no station 9999999 in the catalog"):
        build(tmp_path / "x", unknown)


# The empty list


def test_an_empty_list_leaves_no_trace(off: Path, empty: Path, tmp_path: Path, check_site: Any) -> None:
    assert traces(off) == []
    assert TERMS_OFF in text_of(read(off, "terms"))
    assert problems(check_site, off, empty) == []
    # Guam has no booklet in the committed list, so the default build is the
    # same build, file for file.
    assert not any(station_id in (STATION, OTHER_STATION) for station_id in booklets.load())
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
        f"{PAGE}: a booklet link on a page that is due none",
        f"{PAGE}: mentions amazon with no tag set",
    ]


# One listed booklet


def test_one_booklet_puts_one_link_on_one_page(off: Path, on: Path, listed: Path, check_site: Any) -> None:
    # Nothing but that station's page, the privacy and terms pages, and the
    # record of their fingerprints differs from the empty-list build.
    assert differing(off, on) == ["lastmod.json", "privacy/index.html", PAGE, "terms/index.html"]
    links = {
        f.relative_to(on).as_posix(): AMAZON_A.findall(f.read_text(encoding="utf-8"))
        for f in on.rglob("*")
        if f.is_file() and f.suffix in SUFFIXES and AMAZON_A.search(f.read_text(encoding="utf-8"))
    }
    assert links == {PAGE: [URL]}
    html = read(on, f"stations/{STATION}")
    blocks = BLOCK.findall(html)
    assert len(blocks) == 1
    assert plain(blocks[0]) == SENTENCE
    assert blocks[0].count("<a ") == 1
    assert f'<a href="{URL}" rel="noopener">{TITLE}</a>' in blocks[0]
    for unwanted in ("?", "&", "tag=", "/ref", "data-ga", "sponsored", "<img"):
        assert unwanted not in blocks[0], unwanted
    # Take the sentence out and the page is the empty-list page, byte for byte.
    assert html.replace(blocks[0], "") == read(off, f"stations/{STATION}")
    # After the tide tables and the app line, before the closing notes.
    last_day = html.rindex('<section class="day"')
    assert (
        html.index("</section>", last_day) < html.index('id="week"') < html.index(blocks[0]) < html.index('id="what"')
    )
    assert sorted(traces(on)) == sorted(["privacy/index.html", PAGE, "terms/index.html"])
    assert problems(check_site, on, listed) == []


def test_not_in_json_ld_or_the_files_beside_the_pages(on: Path) -> None:
    html = read(on, f"stations/{STATION}")
    for script in re.findall(r'<script type="application/ld\+json">.*?</script>', html, re.S):
        assert "amazon" not in script.lower() and ASIN not in script
    for name in ("sitemap.xml", "robots.txt", "lastmod.json", "llms.txt"):
        body = (on / name).read_text(encoding="utf-8")
        assert "amazon" not in body.lower() and ASIN not in body, name
    for rel in ("", "states/gu", "states/gu/guam", "king-tides", "es/king-tides", "about", f"stations/{OTHER_STATION}"):
        assert "amazon" not in read(on, rel).lower(), rel


def test_privacy_and_terms_say_so(on: Path, off: Path) -> None:
    privacy = read(on, "privacy")
    assert 'id="booklets"' in privacy and 'id="booklets"' not in read(off, "privacy")
    said = text_of(privacy)
    assert "sells on Amazon" in said
    assert "this site sends nothing to Amazon." in said
    assert "The link takes you to Amazon" in said
    assert AMAZON_A.findall(privacy) == []
    assert "no accounts, no forms and no ads." in said  # the link is the site's own book, not an ad
    terms = text_of(read(on, "terms"))
    assert TERMS_ON in terms and terms.count("Amazon") == 1


def test_every_page_keeps_the_required_statements(on: Path, check_site: Any) -> None:
    assert statement_problems(check_site, on) == []
    html = read(on, f"stations/{STATION}")
    assert "They are predictions, not observed water levels, and not for navigation." in html
    assert "Tide Hours is not a NOAA product" in html and "NOAA CO-OPS" in html


def test_the_sentence_makes_no_claim(on: Path) -> None:
    copy = json.loads(booklets.COPY.read_text(encoding="utf-8"))
    built = BLOCK.search(read(on, f"stations/{STATION}"))
    assert built is not None
    for prose in (*copy.values(), plain(built.group(0))):
        assert FORBIDDEN.search(prose) is None, prose
    assert booklets.block(None) is None
    assert booklets.notice(False) is None


# The year


def test_shown_until_the_year_is_over() -> None:
    booklet = booklets.Booklet(ASIN, 2027, TITLE)
    assert booklets.shown(booklet, dt.date(2026, 11, 1))
    assert booklets.shown(booklet, dt.date(2027, 12, 31))
    assert not booklets.shown(booklet, dt.date(2028, 1, 1))


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
    assert (AMAZON_A.findall(read(with_list, f"stations/{STATION}")) == [URL]) == shows
    want, undated = check_site.booklet_pages(with_list, booklets.load(listed))
    assert undated == [] and list(want) == ([PAGE] if shows else [])
    assert problems(check_site, with_list, listed) == []
    if not shows:
        # Nobody edited the list, and the build is the empty-list build again.
        assert traces(with_list) == []
        assert differing(with_list, build(tmp_path / "empty", empty, now=now)) == []


def test_check_site_catches_a_link_left_up_after_its_year(on: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: the same build, checked against a list whose
    booklet's year is over on the page's date."""
    past = write_list(tmp_path / "past.json", {STATION: entry(year=2025, title="2025 Tide Tables: Apra Harbor")})
    due_now, _ = check_site.booklet_pages(on, booklets.load(past))
    assert due_now == {}  # the sabotage applied: the list no longer calls for the link
    assert f"{PAGE}: a booklet link on a page that is due none" in problems(check_site, on, past)


# Next to the affiliate switch


def test_with_the_affiliate_switch_on_too(both: Path, listed: Path, check_site: Any) -> None:
    assert problems(check_site, both, listed, TAG) == []
    assert check_site.check_print_shop(both, pages(both), SHOP) == []
    assert statement_problems(check_site, both) == []
    station = read(both, f"stations/{STATION}")
    assert AMAZON_A.findall(station) == [URL]  # still untagged
    assert TAG not in station and "gear_click" not in station and "As an Amazon Associate" not in station
    searches = [htmllib.unescape(href) for href in AMAZON_A.findall(read(both, "king-tides"))]
    assert len(searches) == 4 and all(href.endswith(f"&tag={TAG}") for href in searches)
    terms = text_of(read(both, "terms"))
    assert TERMS_ALL in terms and terms.count("Amazon") == 1
    privacy = read(both, "privacy")
    assert 'id="affiliate"' in privacy and 'id="booklets"' in privacy and 'id="shop"' in privacy


def test_the_affiliate_switch_alone_is_unchanged(tmp_path: Path, empty: Path, check_site: Any) -> None:
    tagged = build(tmp_path / "tagged", empty, "--amazon-tag", TAG)
    assert TERMS_ON in text_of(read(tagged, "terms"))
    assert 'id="booklets"' not in read(tagged, "privacy")
    assert problems(check_site, tagged, empty, TAG) == []


# Negative controls for check_site

LINK = f'href="{URL}"'
END_OF_LINK = 'rel="noopener">' + TITLE
NOT_THE_ADDRESS = f"is not the booklet's address, {URL}"
MISPLACED = f"{PAGE}: the booklet link is not between the tide tables and the closing notes"
OTHER_PAGE = f"stations/{OTHER_STATION}/index.html"
JSON_LD_TYPE = '"@type": "WebPage"'
Sabotage = Callable[[str, str], str]  # (the file's text, the booklet sentence) -> the file's text, broken


def swap(old: str, new: str) -> Sabotage:
    return lambda text, block: text.replace(old, new)


def before(marker: str, addition: str | None = None) -> Sabotage:
    """Put `addition` (the booklet sentence, if None) in front of the first `marker`."""
    return lambda text, block: text.replace(marker, (addition or block) + marker, 1)


def move_before(marker: str) -> Sabotage:
    return lambda text, block: text.replace(block, "").replace(marker, block + marker, 1)


# name -> (the file to break, how, the problem check_site must report)
BROKEN: dict[str, tuple[str, Sabotage, str]] = {
    "missing": (PAGE, lambda text, block: text.replace(block, ""), f"{PAGE}: 0 booklet links, exactly 1 expected"),
    "repeated": (
        PAGE,
        lambda text, block: text.replace(block, block + block),
        f"{PAGE}: 2 booklet links, exactly 1 expected",
    ),
    "tagged": (PAGE, swap(LINK, f'href="{URL}?tag={TAG}"'), f"{PAGE}: {URL}?tag={TAG} {NOT_THE_ADDRESS}"),
    "tracking path": (PAGE, swap(LINK, f'href="{URL}/ref=sr_1_1"'), f"{PAGE}: {URL}/ref=sr_1_1 {NOT_THE_ADDRESS}"),
    "another book": (
        PAGE,
        swap(LINK, 'href="https://www.amazon.com/dp/B0OTHERONE"'),
        f"{PAGE}: https://www.amazon.com/dp/B0OTHERONE {NOT_THE_ADDRESS}",
    ),
    "sponsored rel": (
        PAGE,
        swap(END_OF_LINK, 'rel="sponsored nofollow noopener">' + TITLE),
        f"{PAGE}: {URL} rel is ['nofollow', 'noopener', 'sponsored']",
    ),
    "click event": (
        PAGE,
        swap(END_OF_LINK, 'rel="noopener" data-ga-event="gear_click">' + TITLE),
        f"{PAGE}: the booklet link carries a click event",
    ),
    "second link": (
        PAGE,
        swap(f"{TITLE}</a>.</p>", f'{TITLE}</a>. <a href="/about/">About</a></p>'),
        f"{PAGE}: the booklet sentence has 2 links, exactly 1 expected",
    ),
    "before the tables": (PAGE, move_before('<section class="day"'), MISPLACED),
    "after the notes": (PAGE, move_before("</main>"), MISPLACED),
    "another station": (OTHER_PAGE, before("</main>"), f"{OTHER_PAGE}: a booklet link on a page that is due none"),
    "state page": (
        "states/gu/index.html",
        before("</main>"),
        "states/gu/index.html: a booklet link on a page that is due none",
    ),
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}" rel="noopener">Buy</a></p>'),
        f"{PAGE}: mentions amazon with no tag set",
    ),
    "json-ld": (
        PAGE,
        swap(JSON_LD_TYPE, f'{JSON_LD_TYPE}, "sameAs": "{URL}"'),
        f"{PAGE}: mentions amazon with no tag set",
    ),
    "privacy links": (
        "privacy/index.html",
        before("</main>", f'<p><a href="{URL}" rel="noopener">{TITLE}</a></p>'),
        "privacy/index.html: mentions amazon with no tag set",
    ),
    "about names it": (
        "about/index.html",
        before("</main>", "<p>Our booklets are sold on Amazon.</p>"),
        "about/index.html: mentions amazon with no tag set",
    ),
    "sitemap": (
        "sitemap.xml",
        before("</urlset>", f"<url><loc>{URL}</loc></url>"),
        "sitemap.xml: mentions amazon",
    ),
    "llms.txt": ("llms.txt", lambda text, block: f"{text}\n- [{TITLE}]({URL})\n", "llms.txt: mentions amazon"),
    "undated": (
        PAGE,
        lambda text, block: re.sub(r' data-station-date="[^"]*"', "", text),
        f"{PAGE}: no date to tell whether its booklet's year is over",
    ),
}

# The same where the affiliate switch is on, which is where a tag is most
# likely to be added to the booklet link by mistake.
BROKEN_TAGGED: dict[str, tuple[str, Sabotage, str]] = {
    "tagged": BROKEN["tagged"],
    "extra link": (
        PAGE,
        before("</main>", f'<p><a href="{URL}?tag={TAG}" rel="sponsored">Buy</a></p>'),
        f"{PAGE}: amazon link outside king-tides/",
    ),
    "json-ld": (PAGE, BROKEN["json-ld"][1], f"{PAGE}: amazon in JSON-LD"),
    "on the king-tide page": (
        "king-tides/index.html",
        before("</main>"),
        "king-tides/index.html: a booklet link on a page that is due none",
    ),
    "privacy links": (
        "privacy/index.html",
        before("</main>", f'<p><a href="{URL}" rel="noopener">{TITLE}</a></p>'),
        "privacy/index.html: amazon link outside king-tides/",
    ),
}


def break_and_check(check_site: Any, good: Path, bad: Path, listed: Path, tag: str, name: str) -> None:
    """Copy a good build, check it passes, apply one sabotage, assert that it
    changed a file, and assert check_site reports it."""
    rel, sabotage, expect = (BROKEN_TAGGED if tag else BROKEN)[name]
    shutil.copytree(good, bad)
    assert problems(check_site, bad, listed, tag) == []
    block = BLOCK.search((bad / PAGE).read_text(encoding="utf-8"))
    assert block is not None
    target = bad / rel
    was = target.read_text(encoding="utf-8")
    now = sabotage(was, block.group(0))
    assert now != was  # the sabotage applied
    target.write_text(now, encoding="utf-8")
    assert expect in problems(check_site, bad, listed, tag)


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_check_site_catches_a_broken_booklet_build(
    on: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    """Negative controls: each sabotage must change the build and be reported."""
    break_and_check(check_site, on, tmp_path / "bad", listed, "", name)


@pytest.mark.parametrize("name", sorted(BROKEN_TAGGED))
def test_check_site_catches_a_broken_booklet_build_with_the_affiliate_switch_on(
    both: Path, listed: Path, tmp_path: Path, check_site: Any, name: str
) -> None:
    break_and_check(check_site, both, tmp_path / "bad", listed, TAG, name)
