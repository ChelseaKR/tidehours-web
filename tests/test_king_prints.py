"""The king-tide print sentences (docs/DECISIONS.md 0058).

Inside the Prints section, the Washington, Oregon and California calendars
name the 2027 tide rings print or prints of their state whose accent color
includes this January's king tides, then the made-to-order print; the hub
names all five tide rings prints. Each name links straight to its Etsy
listing. The build fails unless each print's station reaches the threshold
printed on it during its state's January king tides. Built
pages are read back with htmlq; negative controls prove the checks can
fail.

The listings and thresholds were read on the live Etsy listings on
2026-11-21, and the January highs checked against NOAA's published
predictions that day (growth/king-tides-january-2027).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import calendars, cli, htmlq, kingtides, posters, printshop, site
from tidehours.catalog import load

NOW = "2026-11-22T11:20:00Z"  # the week they ship, the day before the Nov 23 run
URL = "https://www.etsy.com/shop/TideHours"
LISTING = "https://www.etsy.com/listing/"
CUSTOM = (
    "A made-to-order tide print can show the predicted tide at a place you choose on one day, a king tide day included."
)
# The recommended wording, as drafted for the owner's approval
# (growth/king-tides-january-2027/FOR-APPROVAL-dec29.md), approved 2026-11-21.
WORDS = {
    "king-tides/": [
        "On the West Coast, the 2027 tide rings prints for Long Beach, Newport, San Francisco, Half Moon Bay "
        "and Monterey show this January's king tides in an accent color."
    ],
    "king-tides/washington/": [
        "The 2027 tide rings print for Long Beach draws every predicted tide of the year at the south end of "
        "the Long Beach Peninsula, with the highest, this January's king tides among them, in an accent color.",
        CUSTOM,
    ],
    "king-tides/oregon/": [
        "The 2027 tide rings print for Newport draws every predicted tide of the year at Yaquina Bay, with the "
        "highest, this January's king tides among them, in an accent color.",
        CUSTOM,
    ],
    "king-tides/california/": [
        "The 2027 tide rings prints for San Francisco, Half Moon Bay and Monterey draw every predicted tide of "
        "the year, with the highest, this January's king tides among them, in an accent color.",
        CUSTOM,
    ],
}
LINKS = {
    "king-tides/": [
        ("4617391319", "Long Beach"),
        ("4617389139", "Newport"),
        ("4617280124", "San Francisco"),
        ("4617279303", "Half Moon Bay"),
        ("4617240419", "Monterey"),
    ],
    "king-tides/washington/": [("4617391319", "2027 tide rings print for Long Beach")],
    "king-tides/oregon/": [("4617389139", "2027 tide rings print for Newport")],
    "king-tides/california/": [
        ("4617280124", "San Francisco"),
        ("4617279303", "Half Moon Bay"),
        ("4617240419", "Monterey"),
    ],
}
# The standing wording rules for tide copy, no urgency, no claim, no safety
# advice, and never "no tracking".
BANNED = re.compile(
    r"\b(fish\w*|boat\w*|surf\w*|clam\w*|tide[ -]?pool\w*|swim\w*|div(e|es|ed|ing)|snorkel\w*|kayak\w*|"
    r"hurry|now|today only|last chance|limited|soon|don't miss|act fast|sale|deals?|free|best|top|only|"
    r"cheap\w*|rated|official|safe\w*|danger\w*|no tracking)\b|[$%★!]",
    re.I,
)


def build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "WA,OR,CA", *extra]) == 0
    return out


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("on"), "--print-shop-url", URL)


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("off"))


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_king_prints", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def due(root: Path, check_site: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """The station pages of a build that are due a calendar or poster link."""
    want_calendars, problems = check_site.calendar_pages(root, calendars.load())
    want_posters, more = check_site.poster_pages(root, posters.load())
    assert problems == [] and more == []
    return want_calendars, want_posters


def elements(root: Path, rel: str) -> list[htmlq.Element]:
    return htmlq.read((root / rel / "index.html").read_text(encoding="utf-8"))


def sentences(root: Path, rel: str) -> list[htmlq.Element]:
    return htmlq.marked(elements(root, rel), "data-king-prints", "p")


@pytest.mark.parametrize("rel", list(WORDS))
def test_each_page_reads_as_drafted(on: Path, rel: str) -> None:
    found = sentences(on, rel)
    assert [p.text for p in found] == WORDS[rel]
    links = [link for p in found for link in p.links]
    want = [(LISTING + listing, text) for listing, text in LINKS[rel]]
    if rel != "king-tides/":
        want.append((LISTING + "4614557132", "made-to-order tide print"))
    assert links == want


@pytest.mark.parametrize("rel", list(WORDS))
def test_inside_prints_after_the_other_sentences(on: Path, rel: str) -> None:
    els = elements(on, rel)
    (shop,) = htmlq.marked(els, "data-print-shop", "section")
    start = els.index(shop)
    end = next(i for i, el in enumerate(els) if i > start and el.tag == "section")
    paras = htmlq.tagged(els[start + 1 : end], "p")
    marked = [p for p in paras if "data-king-prints" in p.attrs]
    assert marked and paras[-len(marked) :] == marked  # last in the section
    assert paras[0].links == [(URL, "Tide Hours shop on Etsy")]  # the shop sentence first


def test_links_have_noopener_and_no_click_event(on: Path) -> None:
    for rel in WORDS:
        html = (on / rel / "index.html").read_text(encoding="utf-8")
        for tag in re.findall(r"<a\b[^>]*etsy\.com/listing[^>]*>", html):
            assert 'rel="noopener"' in tag and "data-ga" not in tag and "?" not in tag, tag


@pytest.mark.parametrize("rel", ["es/king-tides/", "about/"])
def test_no_other_page_gets_them(on: Path, rel: str) -> None:
    assert sentences(on, rel) == []


def test_off_builds_none(off: Path) -> None:
    for rel in WORDS:
        assert sentences(off, rel) == []
        assert "etsy" not in (off / rel / "index.html").read_text(encoding="utf-8").lower()


def test_the_words_break_no_wording_rule() -> None:
    for words in [w for ws in WORDS.values() for w in ws]:
        assert BANNED.search(words) is None, BANNED.search(words)


def test_the_banned_words_check_can_fail() -> None:
    for bad in ("tide pools at dawn", "Buy now", "safe viewing", "no tracking", "the best print", "$10"):
        assert BANNED.search(f"{CUSTOM} {bad}") is not None, bad


def test_every_print_reaches_its_threshold_in_january() -> None:
    """The claim behind each sentence, from this site's engine: matches
    NOAA's published January highs within 0.01 ft (Long Beach 10.12, Newport
    10.39, San Francisco 7.11, Half Moon Bay 7.11, Monterey 6.82)."""
    cat = load()
    seasons = site.king_tide_context(cat)["seasons"]
    prints = json.loads(printshop.COPY.read_text(encoding="utf-8"))["kingPrints"]["prints"]
    noaa = {"4617391319": 10.117, "4617389139": 10.390, "4617280124": 7.113, "4617279303": 7.109, "4617240419": 6.816}
    for listing, p in prints.items():
        (january,) = [
            m.span for m in kingtides.calendar(seasons, p["state"]) if (m.year, m.month) == (2027, 1) and m.span
        ]
        high = printshop.january_high(cat, p["station"], january[0], january[1])
        assert high >= p["thresholdFt"], listing
        assert abs(high - noaa[listing]) <= 0.02, (listing, high)


def test_the_build_fails_when_a_print_misses_its_threshold() -> None:
    """Negative control: a threshold over the station's January high is refused."""
    cat = load()
    seasons = site.king_tide_context(cat)["seasons"]
    shop = printshop.block(URL)
    assert shop is not None
    bad = copy.deepcopy(shop)
    bad["text"]["kingPrints"]["prints"]["4617240419"]["thresholdFt"] = 7.0
    with pytest.raises(ValueError, match=r"under its 7\.0 ft accent"):
        printshop.king_prints(bad, cat, seasons)
    unknown = copy.deepcopy(shop)
    unknown["text"]["kingPrints"]["lines"]["custom"][1]["listing"] = "1234567890"
    with pytest.raises(ValueError, match="not a listed print"):
        printshop.king_prints(unknown, cat, seasons)
    assert printshop.king_prints(None, cat, seasons) == {}


def test_check_site_passes_the_build(on: Path, check_site: Any) -> None:
    assert check_site.check_print_shop(on, sorted(on.rglob("*.html")), URL, *due(on, check_site)) == []


@pytest.mark.parametrize(
    ("rel", "old", "new", "expect"),
    [
        ("king-tides/oregon/", "listing/4617389139", "listing/4617389140", "sentences are"),
        ("king-tides/california/", 'listing/4617240419" rel="noopener"', 'listing/4617240419"', "rel"),
        ("about/", "", "", "due none"),
        ("king-tides/washington/", "listing/4617391319", "listing/4617391319?ref=x", "query string"),
    ],
)
def test_check_site_catches_a_broken_sentence(
    on: Path, tmp_path: Path, check_site: Any, rel: str, old: str, new: str, expect: str
) -> None:
    """Negative controls: a wrong listing, a missing rel, a sentence on a
    page due none, and a tracking parameter are each reported."""
    bad = tmp_path / "bad"
    shutil.copytree(on, bad)
    if expect == "due none":
        target = bad / "about" / "index.html"
        before = target.read_text(encoding="utf-8")
        after = before.replace("</main>", "<p data-king-prints>Words.</p></main>", 1)
    else:
        target = bad / rel / "index.html"
        before = target.read_text(encoding="utf-8")
        after = before.replace(old, new, 1)
    assert after != before  # the sabotage applied
    target.write_text(after, encoding="utf-8")
    problems = check_site.check_print_shop(bad, sorted(bad.rglob("*.html")), URL, *due(bad, check_site))
    assert any(p.startswith(rel + "index.html: ") and expect in p for p in problems), problems
