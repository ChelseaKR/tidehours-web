"""The king-tide dates late in a run (docs/DECISIONS.md 0060).

Once a station's run ends, `kingtides.coming_up` gives it the next month's
run. The king-tide page's heading, description and state lines, the home
page's king-tide line and the WA, OR and CA state pages' took the first and
last day over every station, so late in a run they reached into the next
month: on Nov 28, "Washington: Nov 24–Dec 26, 2026" for a run that ends
Dec 1. While king tides are under way, they now use only the runs under way;
a state with none keeps its next run's line, and the station rows are every
run coming up, as before. No words change.

Builds are pinned with `--now` at the daily build's time, 11:20 UTC. Each
date is also built with the span as it was before this change (every run
coming up), so the tests can say what changed: on the dates between runs,
nothing; on the dates late in a run, only those lines, on the English and
Spanish king-tide pages, the home page and the state pages."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tidehours import cli, htmlq, site
from tidehours import kingtides as kt
from tidehours.catalog import DATA_DIR, load

STATES = "CA,OR,WA"
PAGES = ("king-tides/index.html", "es/king-tides/index.html")

EN_DESCRIPTION = (
    "The next West Coast king tides are {}: peak day, time and height at 31 NOAA stations,"
    " from Puget Sound to Oregon and San Diego."
)
ES_DESCRIPTION = (
    "Mareas reales en la costa oeste, {}: las mareas previstas más altas de la temporada en 31 estaciones"
    " de NOAA, de Bellingham a San Diego, con el día, la hora local y la altura del pico en cada lugar."
)

# date: (English range, heading, state lines), (Spanish range, heading, state lines)
EXPECTED: dict[str, tuple[tuple[str, str, list[str]], tuple[str, str, list[str]]]] = {
    "2026-11-22": (
        (
            "Nov 23–Dec 1, 2026",
            "The next king tides: Nov 23–Dec 1, 2026",
            [
                "Washington: Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026.",
                "Oregon: Nov 23–27, 2026, peaking Nov 25, 2026.",
                "California: Nov 23–27, 2026, peaking Nov 25, 2026.",
            ],
        ),
        (
            "23 nov–1 dic 2026",
            "Las próximas mareas reales: 23 nov–1 dic 2026",
            [
                "Washington: 23 nov–1 dic 2026; pico: 25–27 nov 2026.",
                "Oregón: 23–27 nov 2026; pico: 25 nov 2026.",
                "California: 23–27 nov 2026; pico: 25 nov 2026.",
            ],
        ),
    ),
    "2026-11-27": (
        (
            "Nov 23–Dec 1, 2026",
            "King tides now: Nov 23–Dec 1, 2026",
            [
                "Washington: Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026.",
                "Oregon: Nov 23–27, 2026, peaking Nov 25, 2026.",
                "California: Nov 23–27, 2026, peaking Nov 25, 2026.",
            ],
        ),
        (
            "23 nov–1 dic 2026",
            "Mareas reales ahora: 23 nov–1 dic 2026",
            [
                "Washington: 23 nov–1 dic 2026; pico: 25–27 nov 2026.",
                "Oregón: 23–27 nov 2026; pico: 25 nov 2026.",
                "California: 23–27 nov 2026; pico: 25 nov 2026.",
            ],
        ),
    ),
    "2026-11-28": (
        (
            "Nov 24–Dec 1, 2026",
            "King tides now: Nov 24–Dec 1, 2026",
            [
                "Washington: Nov 24–Dec 1, 2026, peaking Nov 26–27, 2026.",
                "Oregon: Dec 21–26, 2026, peaking Dec 24, 2026.",
                "California: Dec 21–26, 2026, peaking Dec 24, 2026.",
            ],
        ),
        (
            "24 nov–1 dic 2026",
            "Mareas reales ahora: 24 nov–1 dic 2026",
            [
                "Washington: 24 nov–1 dic 2026; pico: 26–27 nov 2026.",
                "Oregón: 21–26 dic 2026; pico: 24 dic 2026.",
                "California: 21–26 dic 2026; pico: 24 dic 2026.",
            ],
        ),
    ),
    "2026-12-01": (
        (
            "Nov 25–Dec 1, 2026",
            "King tides now: Nov 25–Dec 1, 2026",
            [
                "Washington: Nov 25–Dec 1, 2026, peaking Nov 27, 2026.",
                "Oregon: Dec 21–26, 2026, peaking Dec 24, 2026.",
                "California: Dec 21–26, 2026, peaking Dec 24, 2026.",
            ],
        ),
        (
            "25 nov–1 dic 2026",
            "Mareas reales ahora: 25 nov–1 dic 2026",
            [
                "Washington: 25 nov–1 dic 2026; pico: 27 nov 2026.",
                "Oregón: 21–26 dic 2026; pico: 24 dic 2026.",
                "California: 21–26 dic 2026; pico: 24 dic 2026.",
            ],
        ),
    ),
    "2026-12-02": (
        (
            "Dec 8–30, 2026",
            "The next king tides: Dec 8–30, 2026",
            [
                "Washington: Dec 8–30, 2026, peaking Dec 9–26, 2026.",
                "Oregon: Dec 21–26, 2026, peaking Dec 24, 2026.",
                "California: Dec 21–26, 2026, peaking Dec 24, 2026.",
            ],
        ),
        (
            "8–30 dic 2026",
            "Las próximas mareas reales: 8–30 dic 2026",
            [
                "Washington: 8–30 dic 2026; pico: 9–26 dic 2026.",
                "Oregón: 21–26 dic 2026; pico: 24 dic 2026.",
                "California: 21–26 dic 2026; pico: 24 dic 2026.",
            ],
        ),
    ),
    "2026-12-17": (
        (
            "Dec 20–30, 2026",
            "The next king tides: Dec 20–30, 2026",
            [
                "Washington: Dec 20–30, 2026, peaking Dec 23–26, 2026.",
                "Oregon: Dec 21–26, 2026, peaking Dec 24, 2026.",
                "California: Dec 21–26, 2026, peaking Dec 24, 2026.",
            ],
        ),
        (
            "20–30 dic 2026",
            "Las próximas mareas reales: 20–30 dic 2026",
            [
                "Washington: 20–30 dic 2026; pico: 23–26 dic 2026.",
                "Oregón: 21–26 dic 2026; pico: 24 dic 2026.",
                "California: 21–26 dic 2026; pico: 24 dic 2026.",
            ],
        ),
    ),
    "2026-12-27": (
        (
            "Dec 22–30, 2026",
            "King tides now: Dec 22–30, 2026",
            [
                "Washington: Dec 22–30, 2026, peaking Dec 25–26, 2026.",
                "Oregon: Jan 19–24, 2027, peaking Jan 22, 2027.",
                "California: Jan 19–23, 2027, peaking Jan 21–22, 2027.",
            ],
        ),
        (
            "22–30 dic 2026",
            "Mareas reales ahora: 22–30 dic 2026",
            [
                "Washington: 22–30 dic 2026; pico: 25–26 dic 2026.",
                "Oregón: 19–24 ene 2027; pico: 22 ene 2027.",
                "California: 19–23 ene 2027; pico: 21–22 ene 2027.",
            ],
        ),
    ),
    "2026-12-30": (
        (
            "Dec 24–30, 2026",
            "King tides now: Dec 24–30, 2026",
            [
                "Washington: Dec 24–30, 2026, peaking Dec 26, 2026.",
                "Oregon: Jan 19–24, 2027, peaking Jan 22, 2027.",
                "California: Jan 19–23, 2027, peaking Jan 21–22, 2027.",
            ],
        ),
        (
            "24–30 dic 2026",
            "Mareas reales ahora: 24–30 dic 2026",
            [
                "Washington: 24–30 dic 2026; pico: 26 dic 2026.",
                "Oregón: 19–24 ene 2027; pico: 22 ene 2027.",
                "California: 19–23 ene 2027; pico: 21–22 ene 2027.",
            ],
        ),
    ),
    "2027-01-05": (
        (
            "Jan 18–27, 2027",
            "The next king tides: Jan 18–27, 2027",
            [
                "Washington: Jan 18–27, 2027, peaking Jan 20–25, 2027.",
                "Oregon: Jan 19–24, 2027, peaking Jan 22, 2027.",
                "California: Jan 19–23, 2027, peaking Jan 21–22, 2027.",
            ],
        ),
        (
            "18–27 ene 2027",
            "Las próximas mareas reales: 18–27 ene 2027",
            [
                "Washington: 18–27 ene 2027; pico: 20–25 ene 2027.",
                "Oregón: 19–24 ene 2027; pico: 22 ene 2027.",
                "California: 19–23 ene 2027; pico: 21–22 ene 2027.",
            ],
        ),
    ),
}
# The home page's king-tide sentence and the WA, OR and CA state pages'.
SUMMARIES: dict[str, tuple[str, str, str, str]] = {
    "2026-11-22": (
        "The next West Coast king tides are Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026 depending on the place.",
        "Washington's next king tides are Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026 depending on the place.",
        "Oregon's next king tides are Nov 23–27, 2026, highest on Nov 25, 2026.",
        "California's next king tides are Nov 23–27, 2026, highest on Nov 25, 2026.",
    ),
    "2026-11-27": (
        "The next West Coast king tides are Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026 depending on the place.",
        "Washington's next king tides are Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026 depending on the place.",
        "Oregon's next king tides are Nov 23–27, 2026, highest on Nov 25, 2026.",
        "California's next king tides are Nov 23–27, 2026, highest on Nov 25, 2026.",
    ),
    "2026-11-28": (
        "The next West Coast king tides are Nov 24–Dec 1, 2026, peaking Nov 26–27, 2026 depending on the place.",
        "Washington's next king tides are Nov 24–Dec 1, 2026, peaking Nov 26–27, 2026 depending on the place.",
        "Oregon's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
        "California's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
    ),
    "2026-12-01": (
        "The next West Coast king tides are Nov 25–Dec 1, 2026, highest on Nov 27, 2026.",
        "Washington's next king tides are Nov 25–Dec 1, 2026, highest on Nov 27, 2026.",
        "Oregon's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
        "California's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
    ),
    "2026-12-02": (
        "The next West Coast king tides are Dec 8–30, 2026, peaking Dec 9–26, 2026 depending on the place.",
        "Washington's next king tides are Dec 8–30, 2026, peaking Dec 9–26, 2026 depending on the place.",
        "Oregon's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
        "California's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
    ),
    "2026-12-17": (
        "The next West Coast king tides are Dec 20–30, 2026, peaking Dec 23–26, 2026 depending on the place.",
        "Washington's next king tides are Dec 20–30, 2026, peaking Dec 23–26, 2026 depending on the place.",
        "Oregon's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
        "California's next king tides are Dec 21–26, 2026, highest on Dec 24, 2026.",
    ),
    "2026-12-27": (
        "The next West Coast king tides are Dec 22–30, 2026, peaking Dec 25–26, 2026 depending on the place.",
        "Washington's next king tides are Dec 22–30, 2026, peaking Dec 25–26, 2026 depending on the place.",
        "Oregon's next king tides are Jan 19–24, 2027, highest on Jan 22, 2027.",
        "California's next king tides are Jan 19–23, 2027, peaking Jan 21–22, 2027 depending on the place.",
    ),
    "2026-12-30": (
        "The next West Coast king tides are Dec 24–30, 2026, highest on Dec 26, 2026.",
        "Washington's next king tides are Dec 24–30, 2026, highest on Dec 26, 2026.",
        "Oregon's next king tides are Jan 19–24, 2027, highest on Jan 22, 2027.",
        "California's next king tides are Jan 19–23, 2027, peaking Jan 21–22, 2027 depending on the place.",
    ),
    "2027-01-05": (
        "The next West Coast king tides are Jan 18–27, 2027, peaking Jan 20–25, 2027 depending on the place.",
        "Washington's next king tides are Jan 18–27, 2027, peaking Jan 20–25, 2027 depending on the place.",
        "Oregon's next king tides are Jan 19–24, 2027, highest on Jan 22, 2027.",
        "California's next king tides are Jan 19–23, 2027, peaking Jan 21–22, 2027 depending on the place.",
    ),
}
SUMMARY_PAGES = ("index.html", "states/wa/index.html", "states/or/index.html", "states/ca/index.html")
# Late in a run: the dates the old merge got wrong, and the state page that
# was wrong on each, besides the home page and the two king-tide pages.
LATE = {
    "2026-11-27": "states/ca/index.html",
    "2026-11-28": "states/wa/index.html",
    "2026-12-01": "states/wa/index.html",
    "2026-12-27": "states/wa/index.html",
    "2026-12-30": "states/wa/index.html",
}
# What the page said on those dates before this change, for the record.
BEFORE = {
    "2026-11-27": (
        "King tides now: Nov 23–Dec 26, 2026",
        "California: Nov 23–Dec 26, 2026, peaking Nov 25–Dec 24, 2026.",
    ),
    "2026-11-28": (
        "King tides now: Nov 24–Dec 26, 2026",
        "Washington: Nov 24–Dec 26, 2026, peaking Nov 26–Dec 24, 2026.",
    ),
    "2026-12-01": (
        "King tides now: Nov 25–Dec 30, 2026",
        "Washington: Nov 25–Dec 30, 2026, peaking Nov 27–Dec 26, 2026.",
    ),
    "2026-12-27": (
        "King tides now: Dec 22, 2026–Jan 24, 2027",
        "Washington: Dec 22, 2026–Jan 24, 2027, peaking Dec 25, 2026–Jan 22, 2027.",
    ),
    "2026-12-30": (
        "King tides now: Dec 24, 2026–Jan 26, 2027",
        "Washington: Dec 24, 2026–Jan 26, 2027, peaking Dec 26, 2026–Jan 24, 2027.",
    ),
}


def old_spans(runs: list[kt.Upcoming], today: dt.date) -> tuple[site.KingSpan | None, dict[str, site.KingSpan | None]]:
    """The spans as they were before 0060: every run coming up."""
    return site.king_span(runs), {
        code: site.king_span([u for u in runs if u.season.state == code]) for code in ("WA", "OR", "CA")
    }


_built: dict[tuple[str, bool], Path] = {}


def built(tmp_path_factory: pytest.TempPathFactory, day: str, fixed: bool = True) -> Path:
    key = (day, fixed)
    if key not in _built:
        out = tmp_path_factory.mktemp(f"hub-{day}-{'fixed' if fixed else 'before'}")
        with pytest.MonkeyPatch.context() as mp:
            if not fixed:
                mp.setattr(site, "king_spans", old_spans)
            assert cli.main(["--out", str(out), "--now", f"{day}T11:20:00Z", "--states", STATES]) == 0
        _built[key] = out
    return _built[key]


def hub_lines(page: Path) -> tuple[str, str | None, str, list[str]]:
    """The description, the og:description, the heading and the state lines."""
    els = htmlq.read(page.read_text(encoding="utf-8"))
    description = htmlq.meta(els, "description")
    assert description is not None
    og = next((el.attrs.get("content") for el in els if el.attrs.get("property") == "og:description"), None)
    heading = next(el.text for el in els if el.tag == "h2" and el.attrs.get("id") == "kt-next")
    lines = [el.text for el in els if el.tag == "a" and el.attrs.get("href", "").startswith("#kt-")]
    return description, og, heading, lines


@pytest.mark.parametrize("day", sorted(EXPECTED))
def test_hub_dates(tmp_path_factory: pytest.TempPathFactory, day: str) -> None:
    out = built(tmp_path_factory, day)
    for (dates, heading, lines), rel, frame in zip(EXPECTED[day], PAGES, (EN_DESCRIPTION, ES_DESCRIPTION), strict=True):
        description, og, h2, found = hub_lines(out / rel)
        assert description == frame.format(dates), (day, rel)
        assert og == description, (day, rel)
        assert h2 == heading, (day, rel)
        assert found == lines, (day, rel)


def summary(page: Path) -> str:
    """The home or state page's king-tide sentence: the start of the one
    paragraph that names the next king tides."""
    found = [
        el.text for el in htmlq.read(page.read_text(encoding="utf-8")) if el.tag == "p" and "king tides are " in el.text
    ]
    assert len(found) == 1, (page, found)
    return found[0]


@pytest.mark.parametrize("day", sorted(SUMMARIES))
def test_home_and_state_dates(tmp_path_factory: pytest.TempPathFactory, day: str) -> None:
    out = built(tmp_path_factory, day)
    for rel, sentence in zip(SUMMARY_PAGES, SUMMARIES[day], strict=True):
        assert summary(out / rel).startswith(sentence + " "), (day, rel)


@pytest.mark.parametrize("day", sorted(EXPECTED))
def test_only_the_summaries_change(tmp_path_factory: pytest.TempPathFactory, day: str) -> None:
    """The control: built the old way, every file but the two king-tide
    pages, the home page, one state page (and lastmod.json, which
    fingerprints them) is byte for byte the same, and so are the station
    rows. On the king-tide pages only the heading, the two descriptions and
    the state lines differ; on the home and state page only the king-tide
    sentence; and only late in a run."""
    fixed, before = built(tmp_path_factory, day), built(tmp_path_factory, day, fixed=False)
    files = sorted(p.relative_to(before) for p in before.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(fixed) for p in fixed.rglob("*") if p.is_file())
    changed = [str(p) for p in files if (fixed / p).read_bytes() != (before / p).read_bytes()]
    if day not in LATE:
        assert changed == [], day
        return
    assert changed == sorted(
        ["es/king-tides/index.html", "index.html", "king-tides/index.html", "lastmod.json", LATE[day]]
    )
    for rel in ("index.html", LATE[day]):
        new = (fixed / rel).read_text(encoding="utf-8").splitlines()
        old = (before / rel).read_text(encoding="utf-8").splitlines()
        assert len(new) == len(old), (day, rel)
        diff = [(a, b) for a, b in zip(old, new, strict=True) if a != b]
        assert len(diff) == 1 and "king tides are " in diff[0][0], (day, rel, diff)
        assert summary(before / rel) != summary(fixed / rel)
    allowed = (
        '<meta name="description" ',
        '<meta property="og:description" ',
        '<h2 id="kt-next">',
        '<li><a href="#kt-',
    )
    for rel in PAGES:
        new = (fixed / rel).read_text(encoding="utf-8").splitlines()
        old = (before / rel).read_text(encoding="utf-8").splitlines()
        assert len(new) == len(old), (day, rel)
        diff = [(a, b) for a, b in zip(old, new, strict=True) if a != b]
        assert diff and all(a.lstrip().startswith(allowed) for a, _ in diff), (day, rel, diff)
        rows = [line for line in old if line.startswith("<tr data-kt-next=")]
        assert len(rows) == 31 and rows == [line for line in new if line.startswith("<tr data-kt-next=")]
        start, end = old.index("    <tbody>"), old.index("    </tbody>")
        assert new[start : end + 1] == old[start : end + 1], (day, rel)
    _, _, heading, lines = hub_lines(before / PAGES[0])
    assert heading == BEFORE[day][0] and BEFORE[day][1] in lines, day


@pytest.fixture(scope="module")
def seasons() -> list[kt.StationSeason]:
    raw = json.loads((DATA_DIR / "datums.json").read_text(encoding="utf-8"))["datums"]
    return kt.season(load(), {k: v["mhhwAboveMllwFt"] for k, v in raw.items()})


def test_spans_every_day_of_the_season(seasons: list[kt.StationSeason]) -> None:
    """Every day from Oct 2026 to Mar 2027. Before any run has begun, the
    spans are as they were. While runs are under way: every run that has
    begun is inside the heading's span and its state's line, the span starts
    no later than today and ends no earlier, and it has no day that no run in
    it covers, so the next month's run is never merged in."""
    day = dt.date(2026, 10, 1)
    while day <= dt.date(2027, 3, 31):
        up = kt.coming_up(seasons, day)
        span, states = site.king_spans(up, day)
        iso = day.isoformat()
        begun = [u for u in up if u.first <= iso]
        if not begun:
            assert (span, states) == old_spans(up, day), day
        else:
            assert span is not None and span.first <= iso <= span.last, day
            inside = [u for u in up if span.first <= u.first and u.last <= span.last]
            assert all(u in inside for u in begun), day
            covered = {
                (dt.date.fromisoformat(u.first) + dt.timedelta(days=i)).isoformat()
                for u in inside
                for i in range((dt.date.fromisoformat(u.last) - dt.date.fromisoformat(u.first)).days + 1)
            }
            first, last = dt.date.fromisoformat(span.first), dt.date.fromisoformat(span.last)
            assert all((first + dt.timedelta(days=i)).isoformat() in covered for i in range((last - first).days + 1)), (
                day
            )
            for code, line in states.items():
                mine = [u for u in begun if u.season.state == code]
                assert line is not None or not mine, (day, code)
                if mine and line is not None:
                    assert all(line.first <= u.first and u.last <= line.last for u in mine), (day, code)
        day += dt.timedelta(days=1)


def test_a_run_that_starts_a_day_later_is_part_of_it(seasons: list[kt.StationSeason]) -> None:
    """The stations' runs start on different days. On a run's first days the
    runs that have not begun yet are still part of it, so the page reads as it
    did: on Nov 23 Washington's line is Nov 23–Dec 1, not just the runs that
    began that day. Late in January, February's run is left out."""
    for day, wa in (
        ("2026-11-23", ("2026-11-23", "2026-12-01")),
        ("2026-11-24", ("2026-11-23", "2026-12-01")),
        ("2026-12-20", ("2026-12-20", "2026-12-30")),
        ("2027-01-18", ("2027-01-18", "2027-01-27")),
        ("2027-01-25", ("2027-01-18", "2027-01-27")),
    ):
        today = dt.date.fromisoformat(day)
        up = kt.coming_up(seasons, today)
        span, states = site.king_spans(up, today)
        line = states["WA"]
        assert line is not None and (line.first, line.last) == wa, day
        if day != "2027-01-25":
            assert (span, states) == old_spans(up, today), day
    assert site.king_under_way([], dt.date(2026, 11, 28)) == []
