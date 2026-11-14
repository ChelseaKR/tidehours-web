"""The page that lists every printable calendar and poster a build links to,
tide-calendars/ (docs/DECISIONS.md 0037): it is built from the two lists the
station pages use; it lists each town by state and town with a link to its
station page and the station page's own plain link to each Etsy listing; it
is in the sitemap; every English page's footer links to it and the Spanish
page's does not; its words name what the build has (calendars and posters,
calendars alone, posters alone); and a build with nothing to list has no
page and no link. Negative controls prove each check_site rule for the page
can fail, each asserting its sabotage changed the build.

The Guam listing ids below are made up. They live only in lists a test
writes to a temporary directory; the committed lists hold the real ones."""

from __future__ import annotations

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
SHOP = "https://www.etsy.com/shop/TideHours"
# The states of the committed lists' stations.
STATES = "ME,CA,OR,MA,GA,MD,WA,FL,NH,NC,AK,SC,NJ,DE"
HUB = "tide-calendars/index.html"
FOOTER = ' · <a href="/tide-calendars/">Tide calendars and posters</a>'
TITLE = "Printable 2027 tide calendars and posters | Tide Hours"
DESCRIPTION = (
    "Printable 2027 tide calendars and posters from Tide Hours, one town each, listed by state, with links to each "
    "town's tide times and its Etsy listing."
)
HEADING = "Printable 2027 tide calendars and posters"
INTRO = (
    "Tide Hours sells printable 2027 tide calendars and year-of-tides posters, one town each, as digital downloads "
    "in the Tide Hours shop on Etsy."
)
HOW = (
    "They are listed here by state. Each town's name links to its tide times on this site, and each calendar or "
    "poster links to its listing on Etsy."
)
# The committed lists as the page shows them: state -> town -> station id.
LISTED = {
    "Alaska": {"Homer": "9455558", "Seward": "9455090"},
    "California": {
        "Eureka": "9418767",
        "Fort Bragg": "9417426",
        "Half Moon Bay": "9414131",
        "La Jolla": "9410230",
        "Monterey": "9413450",
    },
    "Delaware": {"Lewes": "8557380"},
    "Florida": {"Fernandina Beach": "8720030", "New Smyrna Beach": "8721164", "St. Augustine": "8720587"},
    "Georgia": {"St. Simons Island": "8677344", "Tybee Island": "8670870"},
    "Maine": {
        "Bar Harbor": "8413320",
        "Eastport": "8410140",
        "Kennebunkport": "8418911",
        "Ogunquit": "8419317",
        "Old Orchard Beach": "8418445",
        "Portland": "8418150",
    },
    "Maryland": {"Ocean City": "8570283"},
    "Massachusetts": {
        "Brewster Flats": "8447241",
        "Duxbury": "8446166",
        "Gloucester": "8441841",
        "Hull": "8444351",
        "Newburyport": "8440466",
        "Plymouth": "8446493",
        "Provincetown": "8446121",
    },
    "New Hampshire": {"Portsmouth": "8423898"},
    "New Jersey": {"Cape May": "8536110"},
    "North Carolina": {"Atlantic Beach": "8656590", "Hatteras Island": "8654400", "Wrightsville Beach": "8658163"},
    "Oregon": {"Garibaldi": "9437540", "Newport": "9435380"},
    "South Carolina": {"Myrtle Beach": "8661070"},
    "Washington": {
        "Hood Canal": "9445478",
        "La Push": "9442396",
        "Long Beach": "9440581",
        "Olympia": "9446807",
        "Westport": "9441102",
    },
}
WITH_POSTER = {"Bar Harbor", "Eastport", "Homer", "Provincetown", "La Jolla", "Monterey"}
BAR_HARBOR = (
    '<li data-printable="8413320"><a href="/stations/8413320/">Bar Harbor</a>: '
    '<a href="https://www.etsy.com/listing/4614956632" rel="noopener">2027 Tide Calendar: Bar Harbor</a>, '
    '<a href="https://www.etsy.com/listing/4616234122" rel="noopener">2027 Tide Poster: Bar Harbor</a></li>'
)
SEWARD = (
    '<li data-printable="9455090"><a href="/stations/9455090/">Seward</a>: '
    '<a href="https://www.etsy.com/listing/4616144439" rel="noopener">2027 Tide Calendar: Seward</a></li>'
)
# Guam, for the builds with one kind only.
STATION = "1630000"  # Apra Harbor
OTHER_STATION = "1631428"
CALENDAR = {"listing": "1234567890", "year": 2027, "title": "2027 Tide Calendar: Apra Harbor"}
POSTER = {"listing": "1234567891", "year": 2027, "title": "2027 Tide Poster: Apra Harbor"}

ETSY_A = re.compile(r'<a\b[^>]*href="(https?://[^"]*etsy\.[^"]*)"[^>]*>', re.I)
LI = re.compile(r'<li data-printable="[^"]*">.*?</li>', re.S)
H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
# The words and signs test_print_shop.py refuses (no claim, price or rating).
FORBIDDEN = re.compile(r"\b(best|top|only|first|cheap|deals?|rated|official)\b|[$%★]", re.I)


def write_list(path: Path, key: str, entries: Any) -> Path:
    path.write_text(json.dumps({key: entries}), encoding="utf-8")
    return path


def build(out: Path, *extra: str, now: str = NOW, states: str = "GU") -> Path:
    assert cli.main(["--out", str(out), "--now", now, "--states", states, *extra]) == 0
    return out


@pytest.fixture(scope="module")
def lists(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("lists")
    return {
        "no calendars": write_list(d / "no-calendars.json", "calendars", {}),
        "no posters": write_list(d / "no-posters.json", "posters", {}),
        "calendar": write_list(d / "calendar.json", "calendars", {STATION: CALENDAR}),
        "poster": write_list(d / "poster.json", "posters", {OTHER_STATION: POSTER}),
    }


@pytest.fixture(scope="module")
def committed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The committed lists, in the states of their stations, with the print
    shop on: how the site is published."""
    return build(tmp_path_factory.mktemp("committed"), "--print-shop-url", SHOP, states=STATES)


@pytest.fixture(scope="module")
def none(tmp_path_factory: pytest.TempPathFactory, lists: dict[str, Path]) -> Path:
    return build(
        tmp_path_factory.mktemp("none"),
        "--calendars",
        str(lists["no calendars"]),
        "--posters",
        str(lists["no posters"]),
    )


@pytest.fixture(scope="module")
def calendars_only(tmp_path_factory: pytest.TempPathFactory, lists: dict[str, Path]) -> Path:
    return build(
        tmp_path_factory.mktemp("calendars"),
        "--calendars",
        str(lists["calendar"]),
        "--posters",
        str(lists["no posters"]),
    )


@pytest.fixture(scope="module")
def posters_only(tmp_path_factory: pytest.TempPathFactory, lists: dict[str, Path]) -> Path:
    return build(
        tmp_path_factory.mktemp("posters"), "--calendars", str(lists["no calendars"]), "--posters", str(lists["poster"])
    )


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_printables", path)
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
    return htmllib.unescape(re.sub(r"<[^>]+>", "", html)).strip()


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def main_of(html: str) -> str:
    return html[html.index("<main") : html.index("</main>")]


def problems(
    check_site: Any, root: Path, url: str = "", calendar_file: Path | None = None, poster_file: Path | None = None
) -> list[str]:
    """What check_site's main does for Etsy and for the page that lists the
    calendars and posters."""
    want_calendars, undated_calendars = check_site.calendar_pages(root, calendars.load(calendar_file))
    want_posters, undated_posters = check_site.poster_pages(root, posters.load(poster_file))
    found: list[str] = undated_calendars + undated_posters
    found += check_site.check_print_shop(root, pages(root), url, want_calendars, want_posters)
    found += check_site.check_printables(root, pages(root), the_catalog(), want_calendars, want_posters)
    return found


# The words


def test_kind_names_what_the_build_has() -> None:
    assert printables.kind(True, True) == "both"
    assert printables.kind(True, False) == "calendars"
    assert printables.kind(False, True) == "posters"
    assert printables.kind(False, False) is None
    assert printables.link(None) is None
    assert printables.link("both") == {"path": "tide-calendars/", "label": "Tide calendars and posters"}
    assert printables.link("calendars") == {"path": "tide-calendars/", "label": "Tide calendars"}
    assert printables.link("posters") == {"path": "tide-calendars/", "label": "Tide posters"}
    assert printables.block({}, {}, {}) is None
    assert printables.notice(None, None) is None


def test_the_copy_makes_no_claim_and_names_no_price() -> None:
    copy = json.loads(printables.COPY.read_text(encoding="utf-8"))
    prose = [v for v in copy.values() if isinstance(v, str)]
    prose += [word for words in copy["kinds"].values() for word in words.values()]
    assert len(prose) > 10
    for text in prose:
        assert FORBIDDEN.search(text) is None, text
        assert "track" not in text.lower(), text


def test_calendars_and_posters_of_two_years_name_no_year() -> None:
    cat = the_catalog()
    station, other = cat.station(STATION), cat.station(OTHER_STATION)
    assert station is not None and other is not None
    calendar = calendars.Calendar("1234567890", 2027, "2027 Tide Calendar: Apra Harbor")
    poster = posters.Poster("1234567891", 2028, "2028 Tide Poster: Pago Bay")
    one = printables.block({STATION: calendar}, {}, {STATION: station})
    two = printables.block({STATION: calendar}, {OTHER_STATION: poster}, {STATION: station, OTHER_STATION: other})
    assert one is not None and two is not None
    assert one["title"] == "Printable 2027 tide calendars"
    assert two["title"] == "Printable tide calendars and posters"
    assert "20" not in two["intro"] and "  " not in two["intro"]
    # By town within the state; the calendar before the poster.
    (guam,) = two["states"]
    assert (guam.code, guam.name) == ("gu", "Guam")
    assert [t.name for t in guam.towns] == ["Apra Harbor", "Pago Bay"]
    both = printables.block({STATION: calendar}, {STATION: poster}, {STATION: station})
    assert both is not None
    assert [i.title for i in both["states"][0].towns[0].items] == [calendar.title, poster.title]


def test_a_station_without_a_state_is_listed_last() -> None:
    cat = the_catalog()
    stateless = next(s for s in cat.stations if not s.state)
    station = cat.station(STATION)
    assert station is not None
    calendar = calendars.Calendar("1234567890", 2027, "2027 Tide Calendar: Apra Harbor")
    poster = posters.Poster("1234567891", 2027, "2027 Tide Poster: Somewhere")
    found = printables.states({STATION: calendar}, {stateless.id: poster}, {STATION: station, stateless.id: stateless})
    assert [(s.code, s.name) for s in found] == [("gu", "Guam"), ("other", "Other places")]


# The page, as the site is published


def test_the_page_lists_the_committed_calendars_and_posters(committed: Path, check_site: Any) -> None:
    html = read(committed, "tide-calendars")
    assert f"<title>{TITLE}</title>" in html
    assert (
        f'<meta name="description" content="{htmllib.escape(DESCRIPTION, quote=True).replace("&#x27;", "&#39;")}">'
        in html
    )
    assert len(TITLE) <= 60 and len(DESCRIPTION) <= 155
    assert '<link rel="canonical" href="https://tidehours.com/tide-calendars/">' in html
    assert "noindex" not in html
    main = main_of(html)
    assert [plain(h) for h in re.findall(r"<h1>.*?</h1>", main, re.S)] == [HEADING]
    assert [plain(p) for p in re.findall(r"<p[ >].*?</p>", main, re.S)] == [INTRO, HOW]
    # By state, then by town: each town once, with its station page first.
    assert [plain(h) for h in H2.findall(main)] == list(LISTED)
    want = [
        (station_id, town, 3 if town in WITH_POSTER else 2)
        for towns in LISTED.values()
        for town, station_id in towns.items()
    ]
    items = LI.findall(main)
    found = [
        (m.group(1), plain(m.group(2)), item.count("<a "))
        for item in items
        if (m := re.match(r'<li data-printable="(\d+)"><a href="/stations/\1/">(.*?)</a>: ', item))
    ]
    assert found == want and len(found) == 40
    assert BAR_HARBOR in main and SEWARD in main
    # Exactly the 46 listings the station pages link to, each once, plain.
    listed = [c.url for c in calendars.load().values()] + [p.url for p in posters.load().values()]
    assert len(listed) == 46
    assert sorted(ETSY_A.findall(html)) == sorted(listed)
    for a in re.findall(r"<a\b[^>]*etsy[^>]*>", html):
        assert re.fullmatch(r'<a href="https://www\.etsy\.com/listing/[1-9][0-9]{9}" rel="noopener">', a), a
    for unwanted in ("?", "utm_", "ref=shop", "data-ga", "sponsored", "nofollow", "<img", "$", "<script", "<table"):
        assert unwanted not in main, unwanted
    assert FORBIDDEN.search(plain(main)) is None
    # Each town's poster is the one its own station page links to.
    for towns in LISTED.values():
        for station_id in towns.values():
            page = read(committed, f"stations/{station_id}")
            item = next(i for i in items if f'data-printable="{station_id}"' in i)
            assert ETSY_A.findall(item) == ETSY_A.findall(page), station_id
    assert problems(check_site, committed, SHOP) == []


def test_the_page_keeps_the_promises_and_the_gates(committed: Path, check_site: Any) -> None:
    html = read(committed, "tide-calendars")
    assert check_site.check_page(committed, committed / HUB) == []
    assert len(html.encode()) < check_site.MAX_PAGE_BYTES
    for promise in ("Predictions, not observations. Not for navigation.", "not a NOAA product", "NOAA CO-OPS"):
        assert promise in html, promise
    # No structured data: nothing here is a product or an offer to a crawler.
    assert "application/ld+json" not in html
    assert '<meta name="dateModified" content="2026-11-01">' in html
    assert html.count("<h1>") == 1 and '<nav class="crumbs"' not in html
    ids = re.findall(r'\bid="([^"]*)"', html)
    assert len(ids) == len(set(ids))
    for labelled in re.findall(r'aria-labelledby="([^"]*)"', html):
        assert labelled in ids, labelled


def test_the_page_is_in_the_sitemap_and_not_in_llms_txt(committed: Path) -> None:
    sitemap = (committed / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://tidehours.com/tide-calendars/</loc><lastmod>2026-11-01</lastmod>" in sitemap
    assert "/tide-calendars/" in json.loads((committed / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    for name in ("llms.txt", "robots.txt"):
        body = (committed / name).read_text(encoding="utf-8")
        assert "tide-calendars" not in body and "etsy" not in body.lower(), name


def test_every_english_footer_links_to_the_page(committed: Path) -> None:
    files = [*pages(committed)]
    assert committed / "404.html" in files and len(files) > 1_000
    for f in files:
        html = f.read_text(encoding="utf-8")
        rel = f.relative_to(committed).as_posix()
        if rel == "es/king-tides/index.html":
            assert "tide-calendars" not in html
            continue
        assert html.count('href="/tide-calendars/"') == 1, rel
        footer = html[html.index('<footer class="site-footer">') :]
        assert (
            '<p><a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/about/">About</a>'
            f"{FOOTER}</p>" in footer
        ), rel


def test_the_sample_for_the_accessibility_checks_has_the_page(committed: Path, none: Path) -> None:
    path = Path(__file__).resolve().parent.parent / "scripts" / "site_sample.py"
    spec = importlib.util.spec_from_file_location("site_sample_for_printables", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = module.sample(committed)
    assert sample.count("tide-calendars/") == 1
    for station_id in posters.load():
        assert f"stations/{station_id}/" in sample
    assert "tide-calendars/" not in module.sample(none)


# What the build has decides the words, and whether there is a page


def test_nothing_to_list_leaves_no_page_and_no_link(none: Path, lists: dict[str, Path], check_site: Any) -> None:
    assert not (none / "tide-calendars").exists()
    for f in sorted(none.rglob("*")):
        if f.is_file() and f.suffix in (".html", ".xml", ".txt", ".json"):
            assert "tide-calendars" not in f.read_text(encoding="utf-8"), f
    assert problems(check_site, none, "", lists["no calendars"], lists["no posters"]) == []


@pytest.mark.parametrize(
    ("fixture", "title", "footer", "intro", "how", "privacy"),
    [
        (
            "calendars_only",
            "Printable 2027 tide calendars",
            "Tide calendars",
            "Tide Hours sells printable 2027 tide calendars, one town each, as digital downloads in the Tide Hours "
            "shop on Etsy.",
            "They are listed here by state. Each town's name links to its tide times on this site, and each calendar "
            "links to its listing on Etsy.",
            "The tide calendars page, and the station pages of towns with a printable calendar, link to those "
            "calendars in the Tide Hours shop on Etsy.",
        ),
        (
            "posters_only",
            "Printable 2027 tide posters",
            "Tide posters",
            "Tide Hours sells printable 2027 year-of-tides posters, one town each, as digital downloads in the Tide "
            "Hours shop on Etsy.",
            "They are listed here by state. Each town's name links to its tide times on this site, and each poster "
            "links to its listing on Etsy.",
            "The tide posters page, and the station pages of towns with a printable poster, link to those posters "
            "in the Tide Hours shop on Etsy.",
        ),
    ],
)
def test_the_words_name_only_what_the_build_has(
    request: pytest.FixtureRequest,
    lists: dict[str, Path],
    check_site: Any,
    fixture: str,
    title: str,
    footer: str,
    intro: str,
    how: str,
    privacy: str,
) -> None:
    root: Path = request.getfixturevalue(fixture)
    html = read(root, "tide-calendars")
    main = main_of(html)
    assert f"<title>{title} | Tide Hours</title>" in html
    assert [plain(h) for h in re.findall(r"<h1>.*?</h1>", main, re.S)] == [title]
    assert [plain(p) for p in re.findall(r"<p[ >].*?</p>", main, re.S)] == [intro, how]
    assert [plain(h) for h in H2.findall(main)] == ["Guam"]
    assert len(LI.findall(main)) == 1 and len(ETSY_A.findall(html)) == 1
    assert f' · <a href="/tide-calendars/">{footer}</a></p>' in read(root, "")
    assert privacy in plain(read(root, "privacy"))
    other = "poster" if fixture == "calendars_only" else "calendar"
    assert other not in plain(main).lower() and other not in plain(read(root, "privacy")).lower()
    calendar_file = lists["calendar" if fixture == "calendars_only" else "no calendars"]
    poster_file = lists["poster" if fixture == "posters_only" else "no posters"]
    assert problems(check_site, root, "", calendar_file, poster_file) == []


def test_the_page_leaves_with_the_links_on_january_1_2028(tmp_path: Path, check_site: Any) -> None:
    after = build(tmp_path / "2028", "--print-shop-url", SHOP, now="2028-01-01T11:20:00Z", states="ME,NH")
    assert not (after / "tide-calendars").exists()
    assert not any("tide-calendars" in f.read_text(encoding="utf-8") for f in pages(after))
    assert "tide-calendars" not in (after / "sitemap.xml").read_text(encoding="utf-8")
    assert problems(check_site, after, SHOP) == []


# Negative controls for check_site

PAGE = f"stations/{STATION}/index.html"
URL = "https://www.etsy.com/listing/1234567890"
LINK = f'<a href="{URL}" rel="noopener">2027 Tide Calendar: Apra Harbor</a>'
ITEM = f'<li data-printable="{STATION}"><a href="/stations/{STATION}/">Apra Harbor</a>: {LINK}</li>'
DIFFER = f"{HUB}: the towns listed differ, or their order"
ONE_FOOTER = ' · <a href="/tide-calendars/">Tide calendars</a>'
Sabotage = Callable[[str], str]


def swap(old: str, new: str) -> Sabotage:
    return lambda text: text.replace(old, new)


# name -> (the file to break, how, the problem check_site must report), on a
# build with one calendar, no poster and the print shop off.
BROKEN: dict[str, tuple[str, Sabotage, str]] = {
    "town missing": (HUB, swap(ITEM, ""), DIFFER),
    "town twice": (HUB, swap(ITEM, ITEM + ITEM), DIFFER),
    "another station's page": (HUB, swap(f'href="/stations/{STATION}/"', f'href="/stations/{OTHER_STATION}/"'), DIFFER),
    "another town's name": (HUB, swap(">Apra Harbor</a>: ", ">Agana</a>: "), DIFFER),
    "another listing": (HUB, swap(URL, "https://www.etsy.com/listing/9999999999"), DIFFER),
    "slug": (HUB, swap(f'"{URL}"', f'"{URL}/2027-tide-calendar-apra-harbor"'), DIFFER),
    "query string": (HUB, swap(f'"{URL}"', f'"{URL}?ref=tidehours"'), DIFFER),
    "tracking parameter": (HUB, swap(f'"{URL}"', f'"{URL}?utm_source=tidehours"'), DIFFER),
    "another title": (HUB, swap(">2027 Tide Calendar: Apra Harbor<", ">Buy the calendar<"), DIFFER),
    "sponsored rel": (
        HUB,
        swap(f'href="{URL}" rel="noopener"', f'href="{URL}" rel="sponsored nofollow noopener"'),
        f"{HUB}: {URL} rel is ['nofollow', 'noopener', 'sponsored']",
    ),
    "click event": (
        HUB,
        swap(f'href="{URL}" rel="noopener"', f'href="{URL}" rel="noopener" data-ga-event="calendar_click"'),
        f"{HUB}: a listing link carries a click event",
    ),
    "the shop too": (
        HUB,
        swap("</main>", '<p><a href="https://www.etsy.com/shop/TideHours" rel="noopener">The shop</a></p></main>'),
        f"{HUB}: 2 etsy links, one for each listing expected",
    ),
    "json-ld": (
        HUB,
        swap("</head>", f'<script type="application/ld+json">{{"@type": "Product", "url": "{URL}"}}</script></head>'),
        f"{HUB}: etsy in JSON-LD",
    ),
    "another title tag": (
        HUB,
        swap("<title>Printable 2027 tide calendars |", "<title>Tide calendars from $8 |"),
        f"{HUB}: title ['Tide calendars from $8 | Tide Hours']",
    ),
    "a price in the words": (
        HUB,
        swap("one town each, as digital", "one town each, $8, as digital"),
        f"{HUB}: the heading and the two paragraphs are",
    ),
    "an extra paragraph": (
        HUB,
        swap("</main>", "<p>Rated five stars.</p></main>"),
        f"{HUB}: the heading and the two paragraphs are",
    ),
    "no page": (HUB, lambda text: "", f"{HUB}: no page, though station pages link to a calendar or poster"),
    "footer link missing": (
        "about/index.html",
        swap(ONE_FOOTER, ""),
        "about/index.html: 0 links to tide-calendars/, exactly 1 expected",
    ),
    "footer link twice": (
        PAGE,
        swap(ONE_FOOTER, ONE_FOOTER + ONE_FOOTER),
        f"{PAGE}: 2 links to tide-calendars/, exactly 1 expected",
    ),
    "on the spanish page": (
        "es/king-tides/index.html",
        swap("</footer>", '<p><a href="/tide-calendars/">Calendarios</a></p></footer>'),
        "es/king-tides/index.html: 1 links to tide-calendars/, exactly 0 expected",
    ),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_check_site_catches_a_broken_list_page(
    calendars_only: Path, lists: dict[str, Path], tmp_path: Path, check_site: Any, name: str
) -> None:
    """Negative controls: each sabotage must change the build and be reported."""
    rel, sabotage, expect = BROKEN[name]
    bad = tmp_path / "bad"
    shutil.copytree(calendars_only, bad)
    assert problems(check_site, bad, "", lists["calendar"], lists["no posters"]) == []
    target = bad / rel
    was = target.read_text(encoding="utf-8")
    now = sabotage(was)
    assert now != was  # the sabotage applied
    if now:
        target.write_text(now, encoding="utf-8")
    else:
        target.unlink()
    found = problems(check_site, bad, "", lists["calendar"], lists["no posters"])
    assert any(p.startswith(expect) for p in found), found


def test_check_site_catches_a_list_page_in_a_build_with_nothing_to_list(
    none: Path, calendars_only: Path, lists: dict[str, Path], tmp_path: Path, check_site: Any
) -> None:
    """Negative control: the page, copied into a build whose lists are empty."""
    bad = tmp_path / "bad"
    shutil.copytree(none, bad)
    assert problems(check_site, bad, "", lists["no calendars"], lists["no posters"]) == []
    shutil.copytree(calendars_only / "tide-calendars", bad / "tide-calendars")
    assert (bad / HUB).is_file()  # the sabotage applied
    found = problems(check_site, bad, "", lists["no calendars"], lists["no posters"])
    assert f"{HUB}: a list of calendars and posters in a build with none to list" in found
    assert f"{HUB}: mentions etsy with no shop address set" in found
    assert f"{HUB}: 1 links to tide-calendars/, exactly 0 expected" in found
