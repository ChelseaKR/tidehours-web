"""The Prints section on the king-tide pages (docs/DECISIONS.md 0051): on the
English king-tide page it comes right after the next run, before "What is a
king tide?"; on the Washington, Oregon and California calendars it comes
after the safety box and before the months, with one more sentence naming
that state's calendar towns and linking to its section of tide-calendars/.
Built pages are read back with htmlq, never with a regular expression over
HTML. Station, state and region pages are unchanged (test_print_shop.py and
check_site.check_print_shop hold that); negative controls prove the checks
can fail."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import calendars, cli, htmlq, kingtides, posters, printables, printshop
from tidehours.catalog import load

NOW = "2026-11-20T11:20:00Z"  # three days before the Nov 23 run: the hub's "next" section is built
URL = "https://www.etsy.com/shop/TideHours"
STATES = {"WA": "washington", "OR": "oregon", "CA": "california"}
LABEL = "Tide calendars and posters"
SHOP_SENTENCE = (
    "Tide Hours also sells a made-to-order print of the tide at one place on one day, and printable 2027 "
    "tide calendars for a few towns, all drawn from the same predictions as this site. They are in the "
    "Tide Hours shop on Etsy."
)
# The owner's wording for Washington, 2026-11-19, word for word.
WASHINGTON = (
    "Printable 2027 tide calendars for Hood Canal, La Push, Long Beach, Olympia and Westport are listed "
    "under Washington on Tide calendars and posters."
)
# The standing wording rules for tide copy, and the claims and urgency
# test_print_shop.py and test_printables.py refuse.
BANNED = re.compile(
    r"\b(fish\w*|boat\w*|surf\w*|clam\w*|tide[ -]?pool\w*|swim\w*|div(e|es|ed|ing)|snorkel\w*|kayak\w*|"
    r"hurry|now|today only|last chance|limited|soon|don't miss|act fast|sale|deals?|free|best|top|only|"
    r"first|cheap\w*|rated|official)\b|[$%★!]",
    re.I,
)


def build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", ",".join(STATES), *extra]) == 0
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
    spec = importlib.util.spec_from_file_location("check_site_for_king_shop_link", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elements(root: Path, rel: str) -> list[htmlq.Element]:
    return htmlq.read((root / rel / "index.html").read_text(encoding="utf-8"))


def position(els: list[htmlq.Element], test: Any) -> int:
    found = [i for i, el in enumerate(els) if test(el)]
    assert len(found) == 1, found
    return found[0]


def section(labelled_by: str) -> Any:
    return lambda el: el.tag == "section" and el.attrs.get("aria-labelledby") == labelled_by


def shop_section(els: list[htmlq.Element]) -> htmlq.Element:
    found = htmlq.marked(els, "data-print-shop", "section")
    assert len(found) == 1
    return found[0]


def paragraphs(els: list[htmlq.Element], within: htmlq.Element) -> list[htmlq.Element]:
    """The <p> elements of a section, in order: those between it and the
    next section (sections on these pages do not nest)."""
    start = els.index(within)
    end = next((i for i, el in enumerate(els) if i > start and el.tag == "section"), len(els))
    return htmlq.tagged(els[start + 1 : end], "p")


def towns_listed(root: Path, code: str) -> list[str]:
    """The towns tide-calendars/ lists under one state, in its order."""
    els = elements(root, printables.PATH)
    start = position(els, section(f"p-{code.lower()}"))
    end = next((i for i, el in enumerate(els) if i > start and el.tag == "section"), len(els))
    return [el.links[0][1] for el in els[start:end] if el.tag == "li" and "data-printable" in el.attrs]


def due(root: Path, check_site: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """The station pages of a build that are due a calendar or poster link."""
    want_calendars, problems = check_site.calendar_pages(root, calendars.load())
    want_posters, more = check_site.poster_pages(root, posters.load())
    assert problems == [] and more == []
    return want_calendars, want_posters


def committed_towns(code: str) -> list[str]:
    """The committed calendars' and posters' towns in one state, by name."""
    by_id = {s.id: s for s in load().stations}
    titles = [c.title for sid, c in calendars.load().items() if by_id[sid].state == code]
    titles += [p.title for sid, p in posters.load().items() if by_id[sid].state == code]
    return sorted({printables.place(t) for t in titles}, key=str.lower)


def test_the_calendar_pages_are_the_three_west_coast_calendars() -> None:
    assert tuple(kingtides.calendar_path(code) for code in STATES) == printshop.CALENDAR_PAGES
    assert set(printshop.CALENDAR_PAGES).isdisjoint(printshop.PAGES)


def test_hub_prints_come_right_after_the_next_run(on: Path) -> None:
    els = elements(on, "king-tides")
    shop = els.index(shop_section(els))
    assert position(els, section("kt-next")) < shop < position(els, section("kt-definition"))
    assert shop < position(els, section("kt-method"))
    # Nothing but the next-run section's own elements lies between them.
    between = [el for el in els[position(els, section("kt-next")) + 1 : shop] if el.tag in ("section", "h2")]
    assert [el.attrs.get("id") for el in between if el.tag == "h2"] == ["kt-next"]
    assert shop_section(els).text == "Prints " + SHOP_SENTENCE
    assert shop_section(els).links == [(URL, "Tide Hours shop on Etsy")]
    assert htmlq.marked(els, "data-shop-towns") == []


def test_the_spanish_page_still_has_no_prints(on: Path) -> None:
    els = elements(on, "es/king-tides")
    assert htmlq.marked(els, "data-print-shop") == []
    assert all("etsy" not in href for el in els for href, _ in el.links)


@pytest.mark.parametrize("code", list(STATES))
def test_state_prints_come_after_the_safety_box_with_the_towns(on: Path, code: str) -> None:
    rel = kingtides.calendar_path(code)
    els = elements(on, rel)
    box = shop_section(els)
    shop = els.index(box)
    months = [i for i, el in enumerate(els) if el.tag == "section" and "data-kt-cal-month" in el.attrs]
    assert months and position(els, section("kt-safety")) < shop < months[0]
    first, towns = paragraphs(els, box)
    assert first.text == SHOP_SENTENCE and first.links == [(URL, "Tide Hours shop on Etsy")]
    assert "data-shop-towns" in towns.attrs
    assert towns.links == [(f"/{printables.PATH}#p-{code.lower()}", LABEL)]
    assert box.links == [(URL, "Tide Hours shop on Etsy"), (f"/{printables.PATH}#p-{code.lower()}", LABEL)]


def test_washington_reads_as_the_owner_approved(on: Path) -> None:
    (towns,) = htmlq.marked(elements(on, "king-tides/washington"), "data-shop-towns")
    assert towns.text == WASHINGTON


@pytest.mark.parametrize("code", list(STATES))
def test_the_towns_are_the_calendars_of_that_state(on: Path, code: str) -> None:
    """The sentence names exactly the towns tide-calendars/ lists under the
    state, in its order, and those are the committed calendars and posters
    of stations in that state."""
    (towns,) = htmlq.marked(elements(on, kingtides.calendar_path(code)), "data-shop-towns")
    listed = towns_listed(on, code)
    assert listed == committed_towns(code)
    name = {"WA": "Washington", "OR": "Oregon", "CA": "California"}[code]
    lead = f"Printable 2027 tide {'calendars and posters' if code == 'CA' else 'calendars'} for "
    joined = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + " and " + listed[-1]
    assert towns.text == f"{lead}{joined} are listed under {name} on {LABEL}."


def test_the_anchor_each_sentence_links_exists(on: Path) -> None:
    ids = {el.attrs["id"] for el in elements(on, printables.PATH) if "id" in el.attrs}
    for code in STATES:
        assert f"p-{code.lower()}" in ids


@pytest.mark.parametrize("rel", ["king-tides", *(kingtides.calendar_path(c).rstrip("/") for c in STATES)])
def test_the_prints_words_break_no_wording_rule(on: Path, rel: str) -> None:
    prose = shop_section(elements(on, rel)).text
    assert BANNED.search(prose) is None, BANNED.search(prose)


def test_the_banned_words_check_can_fail() -> None:
    """Negative control: each kind of word the rule refuses is caught."""
    for bad in ("tide-pool walks", "swimming", "Hurry, last chance", "on sale", "$8", "the best calendar"):
        assert BANNED.search(f"{WASHINGTON} {bad}") is not None, bad


def test_off_builds_no_prints_and_no_towns(off: Path) -> None:
    for rel in ("king-tides", *printshop.CALENDAR_PAGES):
        els = elements(off, rel)
        assert htmlq.marked(els, "data-print-shop") == [], rel
        assert htmlq.marked(els, "data-shop-towns") == [], rel


def test_no_other_page_gets_the_towns(on: Path) -> None:
    named = sorted(
        f.parent.relative_to(on).as_posix() + "/"
        for f in on.rglob("index.html")
        if htmlq.marked(htmlq.read(f.read_text(encoding="utf-8")), "data-shop-towns")
    )
    assert named == sorted(printshop.CALENDAR_PAGES)


def test_check_site_passes_the_build(on: Path, check_site: Any) -> None:
    assert check_site.check_print_shop(on, sorted(on.rglob("*.html")), URL, *due(on, check_site)) == []


@pytest.mark.parametrize(("name", "expect"), [("missing", "no shop link"), ("repeated", "2 etsy links")])
def test_check_site_catches_a_broken_state_page(
    on: Path, tmp_path: Path, check_site: Any, name: str, expect: str
) -> None:
    """Negative controls: a state calendar with no link, or two, is reported."""
    bad = tmp_path / "bad"
    shutil.copytree(on, bad)
    target = bad / "king-tides" / "oregon" / "index.html"
    before = target.read_text(encoding="utf-8")
    start = before.index('<section class="print-shop"')
    end = before.index("</section>", start) + len("</section>")
    block = before[start:end]
    after = before.replace(block, "" if name == "missing" else block + block.replace('id="print-shop"', 'id="ps2"'))
    assert after != before  # the sabotage applied
    target.write_text(after, encoding="utf-8")
    problems = check_site.check_print_shop(bad, sorted(bad.rglob("*.html")), URL, *due(bad, check_site))
    assert any(p.startswith("king-tides/oregon/index.html: ") and expect in p for p in problems), problems


def test_state_lines_read_in_the_singular_and_drop_a_mixed_year() -> None:
    by_id = {s.id: s for s in load().stations}
    one = printables.state_lines(
        {"9437540": calendars.Calendar("4614965438", 2027, "2027 Tide Calendar: Garibaldi")}, {}, by_id
    )
    assert one == {
        "or": {
            "before": "A printable 2027 tide calendar for Garibaldi is listed under Oregon on",
            "path": "tide-calendars/#p-or",
            "label": "Tide calendars",
            "after": ".",
        }
    }
    mixed = printables.state_lines(
        {
            "9437540": calendars.Calendar("4614965438", 2027, "2027 Tide Calendar: Garibaldi"),
            "9435380": calendars.Calendar("4616000000", 2028, "2028 Tide Calendar: Newport"),
        },
        {},
        by_id,
    )
    assert mixed["or"]["before"] == "Printable tide calendars for Garibaldi and Newport are listed under Oregon on"
    assert printables.state_lines({}, {}, by_id) == {}


def test_the_copy_has_both_frames() -> None:
    text = json.loads(printables.COPY.read_text(encoding="utf-8"))
    for key in ("stateLine", "stateLineOne"):
        assert "{towns}" in text[key] and "{state}" in text[key] and BANNED.search(text[key]) is None
