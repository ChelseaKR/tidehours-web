"""The winter king-tide calendar pages, one per state (docs/DECISIONS.md
0024): each station's runs of the year's highest predicted tides that peak
from November 2026 through February 2027, by month, checked against
Washington Sea Grant's and the Coastal Commission's published dates, and the
gate's check of the built pages, with a negative control."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, site
from tidehours import kingtides as kt
from tidehours.catalog import DATA_DIR, load

NOW = "2026-11-01T11:20:00Z"
STATES = "CA,HI"


@pytest.fixture(scope="module")
def seasons() -> list[kt.StationSeason]:
    raw = json.loads((DATA_DIR / "datums.json").read_text(encoding="utf-8"))["datums"]
    return kt.season(load(), {k: v["mhhwAboveMllwFt"] for k, v in raw.items()})


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", STATES]) == 0
    return out


def test_every_month_in_order_and_runs_filed_by_peak(seasons: list[kt.StationSeason]) -> None:
    for code in ("WA", "OR", "CA"):
        months = kt.calendar(seasons, code)
        assert [(m.year, m.month) for m in months] == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]
        for m in months:
            for u in m.runs:
                peak = dt.date.fromisoformat(u.peak.date)
                assert (peak.year, peak.month) == (m.year, m.month)
                assert u.season.state == code
            assert [u.first for u in m.runs] == sorted(u.first for u in m.runs)
        # Every king-tide station has its first winter run in November.
        assert months[0].stations == sum(1 for s in seasons if s.state == code)


def test_matches_published_dates(seasons: list[kt.StationSeason]) -> None:
    wa = {(m.year, m.month): m for m in kt.calendar(seasons, "WA")}
    # Washington Sea Grant's Seattle table: Feb 20 to 24, 2027, highest
    # Feb 22 at 05:55, 12.62 ft.
    seattle = [u for u in wa[(2027, 2)].runs if u.season.id == "9447130"]
    assert [(u.first, u.last, u.peak.date, u.peak.time) for u in seattle] == [
        ("2027-02-20", "2027-02-24", "2027-02-22", "05:55")
    ]
    assert abs(seattle[0].peak.height - 12.62) <= 0.02
    # Some Washington stations have two runs in December; the page counts
    # stations, not runs.
    assert len(wa[(2026, 12)].runs) > wa[(2026, 12)].stations == 10
    # California: the Coastal Commission's peak days, and no run peaks in
    # February (the page says so in words).
    ca = kt.calendar(seasons, "CA")
    assert {u.peak.date for u in ca[0].runs} == {"2026-11-25"}
    assert {u.peak.date for u in ca[1].runs} == {"2026-12-24"}
    assert {u.peak.date for u in ca[2].runs} <= {"2027-01-21", "2027-01-22"}
    assert ca[3].runs == [] and ca[3].stations == 0


def test_calendar_refuses_bad_input(seasons: list[kt.StationSeason]) -> None:
    with pytest.raises(ValueError, match="no calendar for HI"):
        kt.calendar(seasons, "HI")
    with pytest.raises(ValueError, match="before it starts"):
        kt.calendar(seasons, "CA", "2027-02-28", "2026-11-01")
    with pytest.raises(ValueError, match="no datum epoch for"):
        kt.epochs(seasons, {}, "OR")
    assert kt.epochs(seasons, {s.id: "1983-2001" for s in seasons}, "OR") == ["1983-2001"]


def test_station_page_calendar_link(seasons: list[kt.StationSeason]) -> None:
    sf = next(s for s in seasons if s.id == "9414290")
    assert site.king_calendar(sf, None) == ("king-tides/california/", "California")
    up = kt.Upcoming(sf, sf.series[0])
    assert site.king_calendar(None, site.KingLink(up, 3.0)) == ("king-tides/california/", "California")
    assert site.king_calendar(None, None) is None


def test_built_pages(built: Path) -> None:
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    for code, (name, slug) in kt.CALENDAR_STATES.items():
        html = (built / "king-tides" / slug / "index.html").read_text(encoding="utf-8")
        assert f"<title>{name} king tides 2026–27: dates by month, Nov–Feb | Tide Hours</title>" in html
        assert "These are predictions, not observations or flood forecasts." in html
        assert "feet above mean lower low water (MLLW)" in html
        assert "mean higher high water (MHHW)" in html and "1983–2001 tidal datum epoch" in html
        assert "Times are Pacific time." in html
        assert f"https://tidehours.com/king-tides/{slug}/" in sitemap
        assert '"@type": "WebPage"' in html or '"@type":"WebPage"' in html
        assert f'href="/king-tides/#kt-{code}"' in html
    ca = (built / "king-tides/california/index.html").read_text(encoding="utf-8")
    assert "At none of the 16 stations does a run of the year's highest predicted tides peak in February 2027" in ca
    assert '<a href="/states/ca/">California tide times</a>' in ca
    wa = (built / "king-tides/washington/index.html").read_text(encoding="utf-8")
    assert "/states/wa/" not in wa  # not built here, so not linked
    assert "(some have two)" in wa
    # Links in: the king-tide pages, the state page, a king-tide station and
    # a station near one.
    en = (built / "king-tides/index.html").read_text(encoding="utf-8")
    es = (built / "es/king-tides/index.html").read_text(encoding="utf-8")
    for slug in ("washington", "oregon", "california"):
        assert f'href="/king-tides/{slug}/"' in en
        assert f'href="/king-tides/{slug}/" hreflang="en"' in es
    assert 'href="/king-tides/california/"' in (built / "states/ca/index.html").read_text(encoding="utf-8")
    assert "California king tides by month" in (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "King tides nearby" in (built / "stations/9410166/index.html").read_text(encoding="utf-8")
    assert "California king tides by month" in (built / "stations/9410166/index.html").read_text(encoding="utf-8")
    assert "king tides by month" not in (built / "stations/1612340/index.html").read_text(encoding="utf-8")


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_site_catches_a_wrong_calendar(tmp_path: Path, built: Path) -> None:
    """Negative control: the gate's calendar check passes on the build and
    fails on a changed run, a missing month, a month whose absence is no
    longer said, and a missing page."""
    check = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    cat = load()
    assert check.check_king_calendar(site_dir, cat) == []

    ca = site_dir / "king-tides/california/index.html"
    html = ca.read_text(encoding="utf-8")
    sabotaged = html.replace(
        "9414290 2026-11-24 2026-11-26 2026-11-25 10:49", "9414290 2026-11-24 2026-11-26 2026-11-25 11:49"
    )
    sabotaged = sabotaged.replace('data-kt-cal-month="2027-01"', "")
    sabotaged = sabotaged.replace("stations does a run of the year's highest predicted tides peak in", "stations: 0")
    assert sabotaged.count("11:49") == html.count("11:49") + 1  # the sabotage applied
    assert 'data-kt-cal-month="2027-01"' not in sabotaged and "stations: 0" in sabotaged
    ca.write_text(sabotaged, encoding="utf-8")
    shutil.rmtree(site_dir / "king-tides/oregon")

    found = check.check_king_calendar(site_dir, cat)
    assert "king-tides/oregon/: no page" in found
    assert any(p.startswith("king-tides/california/: runs differ") and "11:49" in p for p in found)
    assert any(p.startswith("king-tides/california/: months") for p in found)
    assert "king-tides/california/: 1 month(s) without a run, not each said in words" in found
    assert not any(p.startswith("king-tides/washington/") for p in found)
    assert len(found) == 4


def test_calendar_rows_show_the_computed_numbers(built: Path, seasons: list[kt.StationSeason]) -> None:
    html = (built / "king-tides/california/index.html").read_text(encoding="utf-8")
    row = re.search(r'<tr data-kt-cal="9414290 2026-11-24 2026-11-26 2026-11-25 10:49">(.*?)</tr>', html, re.S)
    assert row is not None
    cells = re.sub(r"<[^>]+>", "|", row.group(1))
    sf = next(s for s in seasons if s.id == "9414290")
    peak = kt.series_peak(sf.series[0])
    assert f"{round(peak.height, 1):.1f} ft" in cells
    assert "Nov 24–26, 2026" in cells and "Nov 25, 2026, 10:49 AM" in cells
    assert re.search(r"\+\d\.\d ft", cells)
