"""King tides, computed by this site's engine, against three outside lists:
NOAA's own published high/low predictions (the data behind the old
chelseakr.com page), the California Coastal Commission's 2026-27 dates and
Washington Sea Grant's Seattle table. Ported from personal-site's
src/test/kingTides.test.ts, plus the NOAA comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tidehours import kingtides as kt
from tidehours.catalog import DATA_DIR, Catalog, load
from tidehours.ktformat import fmt_feet

NOAA_PAGE = json.loads((Path(__file__).parent / "fixtures/king-tides-noaa-2026-27.json").read_text(encoding="utf-8"))

# California Coastal Commission King Tides Project, 2026-27 statewide dates
# (https://www.coastal.ca.gov/kingtides/, read 2026-10-31).
CCC_STATEWIDE = [
    "2026-11-24", "2026-11-25", "2026-11-26", "2026-12-23", "2026-12-24", "2026-12-25",
    "2027-01-21", "2027-01-22",
]  # fmt: skip
CCC_NORCAL_EXTRA = ["2026-12-22", "2027-01-20", "2027-01-23"]

# Washington Sea Grant king tides calendar, Seattle, 2026-27 (read
# 2026-10-31): date, local time, feet above MLLW, feet above MHHW.
WSG_SEATTLE = [
    ("2026-11-25", "05:57", 12.44, 1.07), ("2026-11-26", "06:48", 12.67, 1.31),
    ("2026-11-27", "07:39", 12.7, 1.33), ("2026-11-28", "08:31", 12.59, 1.23),
    ("2026-11-29", "09:22", 12.45, 1.09), ("2026-12-25", "06:40", 12.93, 1.57),
    ("2026-12-26", "07:22", 13.01, 1.65), ("2026-12-27", "08:02", 13.0, 1.64),
    ("2026-12-28", "08:42", 12.92, 1.55), ("2026-12-29", "09:20", 12.75, 1.39),
    ("2027-01-23", "06:11", 12.89, 1.53), ("2027-01-24", "06:43", 13.04, 1.68),
    ("2027-01-25", "07:16", 13.09, 1.73), ("2027-01-26", "07:48", 13.0, 1.64),
    ("2027-01-27", "08:21", 12.72, 1.36), ("2027-02-20", "04:59", 12.27, 0.91),
    ("2027-02-21", "05:27", 12.5, 1.14), ("2027-02-22", "05:55", 12.62, 1.26),
    ("2027-02-23", "06:24", 12.59, 1.23), ("2027-02-24", "06:55", 12.37, 1.01),
]  # fmt: skip


def minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


@pytest.fixture(scope="module")
def seasons() -> list[kt.StationSeason]:
    cat: Catalog = load()
    raw = json.loads((DATA_DIR / "datums.json").read_text(encoding="utf-8"))["datums"]
    return kt.season(cat, {k: v["mhhwAboveMllwFt"] for k, v in raw.items()})


def days_of(s: kt.StationSeason) -> dict[str, kt.Day]:
    return {d.date: d for series in s.series for d in series}


def by_id(seasons: list[kt.StationSeason], sid: str) -> kt.StationSeason:
    return next(s for s in seasons if s.id == sid)


def test_window_and_stations(seasons: list[kt.StationSeason]) -> None:
    assert kt.window() == ("2026-11-01", "2027-10-31")
    assert len(seasons) == 31
    for s in seasons:
        assert s.mhhw_ft > 0
        assert s.series
        assert all(series for series in s.series)


def test_matches_noaa_published_predictions(seasons: list[kt.StationSeason]) -> None:
    """Same days at every station; times within a minute, heights within
    0.02 ft, MHHW identical."""
    noaa = {s["id"]: s for s in NOAA_PAGE["stations"]}
    assert NOAA_PAGE["window"] == {"start": "2026-11-01", "end": "2027-10-31"}
    for s in seasons:
        ref = noaa[s.id]
        assert s.mhhw_ft == ref["mhhwFt"], s.id
        theirs = {d["date"]: d for series in ref["series"] for d in series["days"]}
        ours = days_of(s)
        assert set(ours) == set(theirs), s.id
        for date, d in ours.items():
            assert abs(minutes(d.time) - minutes(theirs[date]["time"])) <= 1, (s.id, date)
            assert abs(d.height - theirs[date]["ft"]) <= 0.02, (s.id, date)


def test_coastal_commission_statewide_days(seasons: list[kt.StationSeason]) -> None:
    for s in seasons:
        if s.state == "CA":
            days = days_of(s)
            for date in CCC_STATEWIDE:
                assert date in days, (s.place, date)


def test_coastal_commission_winter_at_san_francisco(seasons: list[kt.StationSeason]) -> None:
    winter = sorted(d for d in days_of(by_id(seasons, "9414290")) if d < "2027-03-01")
    assert winter == sorted(CCC_STATEWIDE + CCC_NORCAL_EXTRA)


def test_washington_sea_grant_seattle(seasons: list[kt.StationSeason]) -> None:
    seattle = by_id(seasons, "9447130")
    days = days_of(seattle)
    for date, time, ft, above in WSG_SEATTLE:
        d = days[date]
        assert abs(minutes(d.time) - minutes(time)) <= 1, date
        assert abs(d.height - ft) <= 0.02, date
        assert abs(d.height - seattle.mhhw_ft - above) <= 0.03, date


def test_rank_edge_cases() -> None:
    assert kt.rank([], "2026-11-01") == []
    ev = [("2026-11-01", "01:00", 1.0, "H"), ("2026-11-01", "13:00", 2.0, "H"), ("2026-11-02", "02:00", 0.0, "L")]
    out = kt.rank(ev, "2026-11-01")
    assert [[d.date for d in s] for s in out] == [["2026-11-01"]]
    assert out[0][0].height == 2.0
    with pytest.raises(ValueError, match="unknown event kind"):
        kt.rank([("2026-11-01", "01:00", 1.0, "X")], "2026-11-01")
    assert kt.rank(ev, "2026-11-01", kt.Ranking(seed_days=0)) == []
    assert kt.series_peak([kt.Day("a", "1", 1.0), kt.Day("b", "2", 3.0), kt.Day("c", "3", 3.0)]).date == "b"


def test_season_refuses_missing_datum() -> None:
    with pytest.raises(ValueError, match="no MHHW"):
        kt.season(load(), {})


def test_upcoming_runs_and_their_months(seasons: list[kt.StationSeason]) -> None:
    """The runs "coming up" (docs/DECISIONS.md 0015): a station's next run that
    has not ended and starts within LEAD_DAYS. The dates are the computed
    season's, checked above against NOAA and the published lists."""
    import datetime as dt

    from tidehours import ktformat

    sf = by_id(seasons, "9414290")
    nov4 = dt.date(2026, 11, 4)
    up = kt.upcoming(sf, nov4)
    assert up is not None and up.stamp() == "9414290 2026-11-24 2026-11-26 2026-11-25 10:49"
    # 30 days ahead is in; 31 is not.
    assert kt.upcoming(sf, dt.date(2026, 10, 25)) is not None
    assert kt.upcoming(sf, dt.date(2026, 10, 24)) is None
    # Under way, and on its last day, it is still the run coming up.
    assert kt.upcoming(sf, dt.date(2026, 11, 26)) == up
    after = kt.upcoming(sf, dt.date(2026, 11, 27))
    assert after is not None and after.first == "2026-12-22"
    # Past the season's last run: nothing, not an empty run.
    assert kt.next_run(sf, dt.date(2027, 11, 1)) is None
    assert kt.upcoming(sf, dt.date(2027, 11, 1)) is None

    runs = kt.coming_up(seasons, nov4)
    assert len(runs) == 31
    assert min(u.first for u in runs) == "2026-11-23" and max(u.last for u in runs) == "2026-12-01"
    assert kt.months(runs, nov4) == [(2026, 11)]
    # On Nov 28 Seattle's run (peak Nov 27) is still under way; California's next is December's.
    assert kt.months(kt.coming_up(seasons, dt.date(2026, 11, 28)), dt.date(2026, 11, 28)) == [(2026, 11), (2026, 12)]
    assert kt.coming_up(seasons, dt.date(2027, 3, 15)) == []

    c = json.loads((Path(kt.__file__).parent / "copy/king_tides.json").read_text(encoding="utf-8"))
    assert ktformat.fmt_months([(2026, 11)], "en", c["en"]) == "November 2026"
    assert ktformat.fmt_months([(2026, 11), (2026, 12)], "en", c["en"]) == "November and December 2026"
    assert ktformat.fmt_months([(2026, 12), (2027, 1)], "en", c["en"]) == "December 2026 and January 2027"
    assert ktformat.fmt_months([(2026, 11)], "es", c["es"]) == "noviembre de 2026"
    assert ktformat.fmt_months([(2026, 11), (2026, 12)], "es", c["es"]) == "noviembre y diciembre de 2026"
    assert ktformat.fmt_months([(2026, 12), (2027, 1)], "es", c["es"]) == "diciembre de 2026 y enero de 2027"
    with pytest.raises(ValueError, match="no months"):
        ktformat.fmt_months([], "en", c["en"])


GARIBALDI_MHHW = 8.32  # 9437540, NOAA 1983-2001 epoch


@pytest.mark.parametrize(
    ("height", "above", "shown"),
    [
        # Garibaldi, Dec 24, 2026: NOAA's 10.379 is 2.059 above MHHW, +2.1.
        (10.379, 2.059, "+2.1 ft"),
        # This site's engine gives 10.369 that day: 2.049, +2.0. The 0.01 ft
        # between the two is inside DECISIONS 0006's tolerance.
        (10.369, 2.049, "+2.0 ft"),
        # Rounding the height to 10.37 first made this 2.05 (2.0499... as a
        # float) and showed +2.0; the true 2.054 is +2.1.
        (10.374, 2.054, "+2.1 ft"),
        (10.32, 2.0, "+2.0 ft"),
        (8.32, 0.0, "+0.0 ft"),
    ],
)
def test_above_mhhw_rounds_once(height: float, above: float, shown: str) -> None:
    """Above MHHW is the unrounded height minus MHHW, rounded once for
    display like every other height on the page."""
    season = kt.StationSeason("OR", "9437540", "Garibaldi (Tillamook Bay)", "Garibaldi", GARIBALDI_MHHW, [])
    value = season.above_mhhw(kt.Day("2026-12-24", "12:11", height))
    assert value == above
    assert fmt_feet(value, "en", {"ft": "ft"}, True) == shown
