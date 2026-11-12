"""The accuracy gate: this site's engine against NOAA's own published
predictions, with the Tide Hours app's tolerances
(TideCore/Tests/TideCoreTests/GoldenAccuracyTests.swift):

- every NOAA high and low is matched by one of ours of the same kind within
  3 minutes and 0.05 ft, and hourly heights are within 0.05 ft;
- the stated "flat" exception: at a very flat high or low a 0.005 ft
  difference moves the peak by minutes, so an event more than 3 minutes off
  still passes only if our curve at NOAA's minute is within 0.01 ft of NOAA's
  height, and never beyond 15 minutes. For a subordinate station the
  question is asked of the reference station's curve at NOAA's minute less
  the published time offset, because a subordinate event is a reference
  event moved by fixed minutes (the app's test asks it of the interpolated
  curve, which is not the tide's shape near a peak);
- no invented events: inside NOAA's span we produce the same count.

Two fixtures: golden-app.json is the app's own (12 harmonic and 4
subordinate stations, a week in November 2026 plus three stations in June
2031), and golden-sample.json is one harmonic and one subordinate station per
state, chosen by hash (scripts/fetch_golden.py).

A third, golden-year-boundary.json, is December 31 and January 1 (GMT) at
18 stations with a high or low near 00:00 GMT on 2027-01-01 or 2028-01-01,
the one hour of the year when NOAA's highs and lows and its curve use
different years' constants (DECISIONS 0031).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from tidehours import engine
from tidehours.catalog import Catalog, load
from tidehours.engine import HarmonicPredictor, Predictor, TideEvent, year_start

FIXTURES = Path(__file__).parent / "fixtures"
TIME_TOL = 180.0
HEIGHT_TOL = 0.05


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load()


def golden(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


CASES = [
    (fixture, group, sid)
    for fixture in ("golden-app.json", "golden-sample.json")
    for group in ("harmonic", "subordinate")
    for sid in sorted(golden(fixture)[group])
]


def flatness(p: Predictor, ours: TideEvent, t: float) -> float:
    """How far the tide at NOAA's minute is from our event's height. For a
    subordinate station the curve is NOAA's shifted reference curve: its
    events are reference events moved by fixed minutes, so the question is
    whether the reference tide is flat there."""
    if isinstance(p, HarmonicPredictor):
        return abs(p.height(t) - ours.height)
    o = p.offsets
    high = ours.kind == "H"
    shift = (o.high_time_minutes if high else o.low_time_minutes) * 60
    adj = o.high_height if high else o.low_height
    ref_height = ours.height / adj if o.adjustment == "R" else ours.height - adj
    return abs(p.reference.height(t - shift) - ref_height)


def compare_hilo(rows: list[list[Any]], p: Predictor) -> dict[str, float]:
    noaa = [(ts(t), float(v), str(k)) for t, v, k in rows]
    assert noaa, "no golden events"
    first, last = noaa[0][0], noaa[-1][0]
    ours = p.events(first - 3 * 3600, last + 3 * 3600)
    stats = {"max_dt": 0.0, "max_dh": 0.0, "flat": 0.0, "events": float(len(noaa))}
    for t, v, k in noaa:
        same = [o for o in ours if o.kind == k]
        assert same, f"no {k} near {t}"
        m = min(same, key=lambda o: abs(o.time - t))
        dt_s, dh = abs(m.time - t), abs(m.height - v)
        stats["max_dt"] = max(stats["max_dt"], dt_s)
        stats["max_dh"] = max(stats["max_dh"], dh)
        if dt_s > TIME_TOL:
            at_noaa = flatness(p, m, t)
            assert at_noaa <= 0.01 and dt_s <= 15 * 60, (
                f"{k} {t}: {dt_s / 60:.1f} min off, {at_noaa:.3f} ft at NOAA's time"
            )
            stats["flat"] += 1
        assert dh <= HEIGHT_TOL, f"{k} {t}: height off by {dh:.3f} ft"
    # The span widens by the flat bound (15 minutes): a flat first or last
    # event may sit a few minutes outside NOAA's span.
    inside = [o for o in ours if first - 900 <= o.time <= last + 900]
    assert len(inside) == len(noaa), f"{len(inside)} events vs NOAA's {len(noaa)}"
    return stats


@pytest.mark.parametrize(("fixture", "group", "sid"), CASES)
def test_matches_noaa(catalog: Catalog, fixture: str, group: str, sid: str) -> None:
    entry = golden(fixture)[group][sid]
    station = catalog.station(sid)
    assert station is not None, f"{sid} missing from the catalog"
    assert station.is_subordinate == (group == "subordinate")
    p = catalog.predictor(sid)
    compare_hilo(entry["hilo"], p)
    if entry.get("hiloFar"):
        compare_hilo(entry["hiloFar"], p)
    for t, v in entry.get("hourly") or []:
        assert isinstance(p, HarmonicPredictor)
        assert abs(p.height(ts(t)) - v) <= HEIGHT_TOL, f"hourly {t}"


def test_sample_covers_every_state(catalog: Catalog) -> None:
    sample = golden("golden-sample.json")
    states = {s.state for s in catalog.stations}
    covered = {catalog.station(i).state for g in ("harmonic", "subordinate") for i in sample[g]}  # type: ignore[union-attr]
    assert covered == states
    assert len(sample["harmonic"]) >= 25
    assert len(sample["subordinate"]) >= 25


# The month fixture: every NOAA high and low in November 2026 at 81 stations
# (both fixtures above plus 14 small-range Gulf and Caribbean stations).
# Matching is one to one, nearest event of the same kind within 15 minutes.
# Each divergence that remains after drop_stands is listed here with what it
# is; anything else fails. Measured 2026-10-31; see DECISIONS 0004.
KNOWN_DIVERGENCES: dict[tuple[str, str], str] = {
    # NOAA omits a 0.015 ft pair 125 minutes apart (our times); the 120-minute
    # rule keeps it.
    ("9751639", "2026-11-21T17:53Z"): "stand NOAA omits (L)",
    ("9751639", "2026-11-21T19:58Z"): "stand NOAA omits (H)",
    # A flat double high (1.714 ft at 02:46, 1.709 ft at 06:13): drop_stands
    # keeps the earlier high, NOAA the later one.
    ("8771450", "2026-11-13T02:46Z"): "flat double high, other peak",
    # A 0.035 ft pair 121 minutes apart.
    ("8775870", "2026-11-22T02:19Z"): "stand NOAA omits (L)",
    ("8775870", "2026-11-22T04:19Z"): "stand NOAA omits (H)",
    # Subordinate: a 0.07 ft pair 99 minutes apart.
    ("9751540", "2026-11-06T18:37Z"): "stand NOAA omits (L)",
    ("9751540", "2026-11-06T20:16Z"): "stand NOAA omits (H)",
}
KNOWN_MISSING = {"8771450": 1}  # the other peak of the flat double high


def iso_minute(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


def test_month_against_noaa(catalog: Catalog) -> None:
    month = golden("golden-month.json")["stations"]
    assert len(month) >= 80
    total = matched = 0
    unexplained: list[str] = []
    used_known: set[tuple[str, str]] = set()
    for sid, rows in month.items():
        noaa = [(ts(t), float(v), str(k)) for t, v, k in rows]
        p = catalog.predictor(sid)
        ours = p.events(noaa[0][0] - 900, noaa[-1][0] + 901)
        free = list(ours)
        missing = 0
        for t, v, k in noaa:
            total += 1
            cands = [o for o in free if o.kind == k and abs(o.time - t) <= 900]
            if not cands:
                missing += 1
                continue
            m = min(cands, key=lambda o: abs(o.time - t))
            free.remove(m)
            matched += 1
            assert abs(m.height - v) <= HEIGHT_TOL, f"{sid} {iso_minute(t)}: {abs(m.height - v):.3f} ft"
            if abs(m.time - t) > TIME_TOL:
                assert flatness(p, m, t) <= 0.01, f"{sid} {iso_minute(t)} not flat"
                assert abs(m.time - t) <= 15 * 60
        for o in free:
            key = (sid, iso_minute(o.time))
            if key in KNOWN_DIVERGENCES:
                used_known.add(key)
            else:
                unexplained.append(f"{sid} extra {o.kind} {key[1]} {o.height:.3f}")
        if missing != KNOWN_MISSING.get(sid, 0):
            unexplained.append(f"{sid}: {missing} NOAA events unmatched")
    assert not unexplained, unexplained
    assert used_known == set(KNOWN_DIVERGENCES), "a listed divergence no longer happens; update the list"
    assert matched / total >= 0.998, f"{matched}/{total}"


# The year-boundary fixture (DECISIONS 0031, measured 2026-11-10). NOAA's
# published highs and lows keep the old year's constants for the first 30
# minutes of January 1 (GMT); its 6-minute heights do not.
BOUNDARY = golden("golden-year-boundary.json")
BOUNDARY_CASES = [(int(year), sid) for year, stations in BOUNDARY["boundaries"].items() for sid in sorted(stations)]
# Each fixture station's tide nearest 00:00 GMT differs by 0.046 ft or more
# between the two years' constants, and the engine is within 0.010 ft of
# NOAA at every one, so this tolerance tells the years apart.
BOUNDARY_HEIGHT_TOL = 0.02
BOUNDARY_TIME_TOL = 60.0


def boundary_miss(p: Predictor, year: int, rows: list[list[Any]]) -> tuple[float, float]:
    """(seconds, feet) between NOAA's tide nearest 00:00 GMT on January 1
    and ours of the same kind."""
    midnight = year_start(year)
    t, v, k = min(((ts(r[0]), float(r[1]), str(r[2])) for r in rows), key=lambda r: abs(r[0] - midnight))
    assert abs(t - midnight) <= 95 * 60, "no tide near midnight in the fixture"
    ours = [o for o in p.events(t - 3 * 3600, t + 3 * 3600) if o.kind == k]
    m = min(ours, key=lambda o: abs(o.time - t))
    return abs(m.time - t), abs(m.height - v)


def boundary_misses(catalog: Catalog) -> list[str]:
    out = []
    for year, sid in BOUNDARY_CASES:
        dt_s, dh = boundary_miss(catalog.predictor(sid), year, BOUNDARY["boundaries"][str(year)][sid])
        if dt_s > BOUNDARY_TIME_TOL or dh > BOUNDARY_HEIGHT_TOL:
            out.append(sid)
    return out


@pytest.mark.parametrize(("year", "sid"), BOUNDARY_CASES)
def test_year_boundary_matches_noaa(catalog: Catalog, year: int, sid: str) -> None:
    rows = BOUNDARY["boundaries"][str(year)][sid]
    p = catalog.predictor(sid)
    compare_hilo(rows, p)
    dt_s, dh = boundary_miss(p, year, rows)
    assert dt_s <= BOUNDARY_TIME_TOL and dh <= BOUNDARY_HEIGHT_TOL, f"{dt_s:.0f} s, {dh:.3f} ft"


def test_year_boundary_fixture_covers_both_sides(catalog: Catalog) -> None:
    assert len(BOUNDARY_CASES) == 18
    assert {year for year, _ in BOUNDARY_CASES} == {2027, 2028}
    subordinate = [sid for _, sid in BOUNDARY_CASES if not isinstance(catalog.predictor(sid), HarmonicPredictor)]
    assert subordinate == ["8410875"]  # Birch Islands, from Eastport
    assert boundary_misses(catalog) == []


@pytest.mark.parametrize(
    ("minutes", "missed"),
    [
        # No carry, the engine before 0031: the 10 tides after midnight that
        # NOAA publishes from the old year miss, among them Bar Harbor's
        # 00:09 low by 0.088 ft and Birch Islands' 01:33 low, which NOAA
        # derives from Eastport's 00:20 low. (Anchor Point's 00:02 low
        # misses by two minutes, not by height.)
        (0.0, {"8413320", "9466057", "8414249", "9455912", "8419317", "9457292", "8410875",
               "9444090", "9466328", "9455606"}),
        # Just under 30 minutes: Kodiak, Womens Bay (the old year's high is
        # at 00:29.96) goes to the new year. Just over: Ouzinkie (00:30.28)
        # and Milbridge (00:30.44) stay with the old.
        (29.9, {"9457292"}),
        (30.5, {"9457287", "8412581"}),
        # An hour: six of the seven tides NOAA publishes from the new year
        # miss (the old year puts Goodnews Bay's at 01:01.68).
        (60.0, {"9457287", "8412581", "8465705", "8410834", "9459758", "9465396"}),
    ],
)  # fmt: skip
def test_year_boundary_carry_is_thirty_minutes(
    catalog: Catalog, monkeypatch: pytest.MonkeyPatch, minutes: float, missed: set[str]
) -> None:
    """Negative controls: the fixture rejects any other carry."""
    monkeypatch.setattr(engine, "YEAR_CARRY", minutes * 60)
    assert set(boundary_misses(catalog)) == missed


def test_curve_changes_year_at_midnight(catalog: Catalog) -> None:
    """NOAA's 6-minute heights at Fire Island, AK follow the new year's
    constants from 00:00 GMT, as `heights` does, though its 00:26 low
    (5.634 ft) is the old year's: the curve reads 5.37 ft there."""
    rows = BOUNDARY["series"]["2028"]["9455912"]
    assert len(rows) == 41
    p = catalog.harmonic("9455912")
    for t, v in rows:
        assert abs(p.height(ts(t)) - v) <= 0.01, t
    low = next(r for r in BOUNDARY["boundaries"]["2028"]["9455912"] if r[0] == "2028-01-01T00:26Z")
    assert low[1] - min(v for _, v in rows) > 0.25


def test_noaa_answer_does_not_depend_on_request_start() -> None:
    """Bar Harbor asked for from January 1 on gives the same 00:09 low as
    asked for from December 31."""
    from_dec31 = BOUNDARY["boundaries"]["2028"]["8413320"]
    from_jan1 = BOUNDARY["fromJanuary1"]["2028"]["8413320"]
    assert from_jan1[0] == ["2028-01-01T00:09Z", 0.377, "L"]
    assert from_jan1[:4] == from_dec31[3:]
