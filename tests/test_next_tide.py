"""The next-tide line on station pages (docs/DECISIONS.md 0038), as built:
the first day's highs and lows in order, by date, in the answer box, and a
day without either says so. Negative controls prove check_site's
check_next fails a page whose line is missing, doubled, out of the answer
box, out of order, wrong, a placeholder, or no longer the table's. What the
page's script does with the line is in tests/test_today.py."""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, sky
from tidehours.catalog import load
from tidehours.days import Day, Event

NOW = "2026-11-13T11:20:00Z"
MONTEREY = "9413450"
LINE = '<p class="next" id="next">Friday, Nov 13, in order: high 2:25 AM, low 5:30 AM, high 11:34 AM, low 7:35 PM.</p>'


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ca(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("next-site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA"]) == 0
    return out


def _day(d: dt.date, events: list[Event]) -> Day:
    # The sky fields do not enter the sentence; any valid values do.
    sun = sky.SunDay(d, [], False, [], [], False)
    return Day(d, events, None, False, sun, sky.MoonDay(d, "New moon", 0.0, None), sky.MoonTimes(d, [], False))


def test_the_sentence_names_the_date_and_says_absence() -> None:
    check = _check_site()
    friday = dt.date(2026, 11, 13)
    one = _day(
        friday, [Event("High", "2:25 AM", "", "3.7 ft", "", 3.7), Event("Low", "5:30 AM", "", "3.4 ft", "", 3.4)]
    )
    assert one.in_order() == "Friday, Nov 13, in order: high 2:25 AM, low 5:30 AM."
    assert _day(friday, []).in_order() == "Friday, Nov 13: no high or low tide predicted."
    # check_site writes the sentence out on its own; the two agree.
    assert check.next_sentence(friday, [("High", "2:25 AM"), ("Low", "5:30 AM")]) == one.in_order()
    assert check.next_sentence(friday, []) == _day(friday, []).in_order()


def test_built_page_has_the_line_in_the_answer_box(ca: Path) -> None:
    html = (ca / f"stations/{MONTEREY}/index.html").read_text(encoding="utf-8")
    assert html.count('id="next"') == 1 and LINE in html
    answer = html.index('<div class="answer">')
    assert answer < html.index(LINE) < html.index('id="q-high"') < html.index("</div>", answer)
    # The chart comes before the table in each day's card, and the sun and
    # moon line after it.
    for section in re.findall(r'<section class="day".*?</section>', html, re.S):
        assert section.index('<figure class="chart">') < section.index('<table class="events">')
        assert section.index('<table class="events">') < section.index('<p class="sky"')


def test_check_next_passes_the_build(ca: Path) -> None:
    assert _check_site().check_next(ca, load()) == []


def _sabotage(page: Path, old: str, new: str) -> None:
    html = page.read_text(encoding="utf-8")
    assert old in html
    page.write_text(html.replace(old, new, 1), encoding="utf-8")
    assert page.read_text(encoding="utf-8") != html  # the sabotage applied


CASES = {
    "removed": (LINE, "", "0 next-tide lines"),
    "doubled": (LINE, LINE + LINE, "2 next-tide lines"),
    "outside": (
        '<div class="answer">\n  ' + LINE,
        LINE + '\n<div class="answer">',
        "the next-tide line is not in the answer box",
    ),
    "wrong-time": (LINE, LINE.replace("7:35 PM", "7:53 PM"), "next-tide line"),
    "order": (LINE, LINE.replace("high 2:25 AM, low 5:30 AM", "low 5:30 AM, high 2:25 AM"), "next-tide line"),
    "tomorrow": (LINE, LINE.replace("Friday, Nov 13", "Saturday, Nov 14"), "next-tide line"),
    "placeholder": (LINE, '<p class="next" id="next">Friday, Nov 13, in order: high None.</p>', "contains 'None'"),
    "says-today": (LINE, LINE.replace("Friday, Nov 13", "Today"), "next-tide line"),
    "table-changed": (
        '<time datetime="2026-11-13T19:35-08:00">7:35 PM</time></td>',
        '<time datetime="2026-11-13T19:35-08:00">7:36 PM</time></td>',
        "next-tide line",
    ),
}


@pytest.mark.parametrize("how", sorted(CASES))
def test_check_next_catches_a_bad_line(tmp_path: Path, ca: Path, how: str) -> None:
    """Negative controls: check_next passes a copy of the build, then fails
    each sabotage of one page's next-tide line, naming that page."""
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(ca / "stations" / MONTEREY, root / "stations" / MONTEREY)
    cat = load()
    assert check.check_next(root, cat) == []
    old, new, expect = CASES[how]
    _sabotage(root / f"stations/{MONTEREY}/index.html", old, new)
    problems = check.check_next(root, cat)
    assert problems and all(p.startswith(f"stations/{MONTEREY}: ") for p in problems), problems
    assert any(expect in p for p in problems), problems
