"""Engine details the golden tests do not reach: stands, edges, the year
boundary, and the catalog's refusals."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from tidehours import catalog as catalog_mod
from tidehours.catalog import CatalogError, load
from tidehours.engine import (
    YEAR_CARRY,
    Astro,
    HarmonicPredictor,
    Node,
    SubordinatePredictor,
    TideEvent,
    drop_stands,
    node_correction,
    tide_year,
    year_constants,
    year_start,
)


def ev(minutes: float, h: float, k: str) -> TideEvent:
    return TideEvent(minutes * 60, h, k)


def test_drop_stands_removes_flattest_pair_only() -> None:
    raw = [ev(0, 1.0, "H"), ev(300, 1.40, "L"), ev(360, 1.42, "H"), ev(700, 0.0, "L")]
    assert [e.time for e in drop_stands(raw)] == [0, 700 * 60]
    big = [ev(0, 1.0, "H"), ev(100, 0.5, "L"), ev(200, 1.0, "H")]  # 0.5 ft apart: real
    assert drop_stands(big) == big
    slow = [ev(0, 1.0, "L"), ev(121, 1.01, "H")]  # more than two hours apart
    assert drop_stands(slow) == slow
    assert drop_stands([]) == []


def test_drop_stands_removes_a_near_stand_that_stands_alone() -> None:
    """DECISIONS 0036: under 115 minutes and 0.095 ft, with no neighbor
    within NOAA's two hours and 0.10 ft of it."""
    alone = [ev(0, 0.0, "L"), ev(570, 7.65, "H"), ev(670, 7.56, "L"), ev(1000, 9.0, "H")]
    assert [e.time for e in drop_stands(alone)] == [0, 1000 * 60]
    wide = [ev(0, 0.0, "L"), ev(570, 7.65, "H"), ev(686, 7.56, "L"), ev(1000, 9.0, "H")]  # 116 minutes
    assert drop_stands(wide) == wide
    tall = [ev(0, 0.0, "L"), ev(570, 7.65, "H"), ev(670, 7.554, "L"), ev(1000, 9.0, "H")]  # 0.096 ft
    assert drop_stands(tall) == tall
    # Three tides in question: NOAA lists one of the two highs, and which
    # one is not known, so nothing is removed, before or after the pair.
    after = [ev(0, 0.0, "L"), ev(500, 1.275, "H"), ev(596, 1.19, "L"), ev(685, 1.268, "H"), ev(960, 0.3, "L")]
    assert drop_stands(after) == after
    before = [ev(0, 3.0, "H"), ev(300, 1.19, "L"), ev(389, 1.268, "H"), ev(485, 1.185, "L"), ev(800, 3.0, "H")]
    assert drop_stands(before) == before
    # A neighbor that is a real tide (0.24 ft away) does not protect it.
    real = [ev(0, 1.0, "L"), ev(300, 10.69, "H"), ev(372, 10.45, "L"), ev(430, 10.52, "H"), ev(700, 2.5, "L")]
    assert [e.time for e in drop_stands(real)] == [0, 300 * 60, 700 * 60]


def test_empty_and_reversed_windows() -> None:
    cat = load()
    p = cat.harmonic("9414290")
    assert p.events(100.0, 100.0) == []
    assert p.raw_events(200.0, 100.0) == []
    assert p.heights(np.array([])).size == 0


def test_year_boundary_step_is_small() -> None:
    """f and V0+u are held for each UTC year (as in the app and as NOAA
    does), so the curve steps slightly at New Year: 0.015 ft here."""
    p = load().harmonic("9414290")
    t = year_start(2027)
    assert abs(p.height(t - 1) - p.height(t)) < 0.03
    assert len(p.events(t - 86400, t + 86400)) >= 6


def test_new_year_hand_over_does_not_depend_on_the_window() -> None:
    """Highs and lows keep the old year's constants for YEAR_CARRY into the
    new year (DECISIONS 0031), and a window that starts or ends near the
    hand-over gets the same tides as a wide one."""
    cat = load()
    t = year_start(2028)
    first = t + YEAR_CARRY
    assert (tide_year(first - 1), tide_year(first)) == (2027, 2028)
    # Kodiak, Womens Bay: the old year's high is 2.3 seconds before the
    # hand-over and the new year's copy of it 43 seconds after.
    kodiak = cat.harmonic("9457292")
    wide = kodiak.raw_events(t - 86_400, t + 86_400)
    assert all(a.kind != b.kind for a, b in itertools.pairwise(wide))
    near = [e for e in wide if t <= e.time < t + 3_600]
    assert [e.kind for e in near] == ["H"] and 0 < first - near[0].time < 5
    assert kodiak.raw_events(first, first + 3_600) == []
    # The curve is the new year's from 00:00: still rising at the hand-over.
    assert kodiak.rates(np.array([first]))[0] > 0
    assert kodiak.raw_events(first + 30, first + 3_600) == []
    assert [e.kind for e in kodiak.raw_events(first - 60, first + 60)] == ["H"]
    pieces = kodiak.raw_events(t - 86_400, first) + kodiak.raw_events(first, t + 86_400)
    assert len(pieces) == len(wide)
    assert all(a.kind == b.kind and abs(a.time - b.time) < 1 for a, b in zip(pieces, wide, strict=True))
    # Milbridge: the new year's low is before the hand-over and the old
    # year's after it, so neither finds it; it is put at the hand-over.
    milbridge = cat.harmonic("8412581")
    low = milbridge.raw_events(t, t + 3_600)
    assert [(e.time, e.kind) for e in low] == [(first, "L")]
    assert low[0].height == pytest.approx(0.653, abs=0.001)
    assert milbridge.raw_events(first + 1, t + 3_600) == []
    # A window wholly inside a year never looks at another year.
    day = (t + 40 * 86_400, t + 41 * 86_400)
    assert kodiak.raw_events(*day) == kodiak._held_events(*day, 2028)


def test_subordinate_height_and_curve_edges() -> None:
    cat = load()
    p = cat.predictor("9413878")
    assert isinstance(p, SubordinatePredictor)
    t = year_start(2027)
    h = p.height(t)
    assert h is not None and -2 < h < 8
    assert SubordinatePredictor.interpolate([], t) is None
    same = [TideEvent(t - 60, 0.0, "L"), TideEvent(t, 1.0, "H"), TideEvent(t, 2.0, "L"), TideEvent(t + 60, 3.0, "H")]
    assert SubordinatePredictor.interpolate(same, t) == 2.0
    assert SubordinatePredictor.interpolate(same[:2], t) is None
    curve = p.curve(t, t + 3600, 600)
    assert len(curve) == 7


def test_node_corrections_cover_every_constituent() -> None:
    n = Node.of(Astro.at(year_start(2026)))
    for name in ("M2", "S2", "K1", "O1", "M4", "M6", "M8", "MK3", "2MK3", "OO1", "J1", "MM", "MF", "MSF",
                 "M3", "K2", "L2", "M1", "SIGMA1", "CHI1", "XX"):  # fmt: skip
        f, u = node_correction(name, n)
        assert 0.0 < f < 3.0 and np.isfinite(u)
    y = year_constants(2026, ["M2", "NOPE", "2MS6"], {"2MS6": [("M2", 2), ("S2", 1)]}, {})
    assert y.f[1] == 0.0 and y.vu[1] == 0.0
    assert y.f[2] == pytest.approx(y.f[0] ** 2)


def test_astro_before_1970() -> None:
    a = Astro.at(-3600.0)
    assert 0 <= a.T < 360


def test_catalog_refusals(tmp_path: Path) -> None:
    raw = json.loads((catalog_mod.DATA_DIR / "stations.json").read_text(encoding="utf-8"))
    regions = catalog_mod.DATA_DIR / "regions.json"
    bad = dict(raw, schema=2)
    (tmp_path / "s.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(CatalogError, match="schema"):
        load(tmp_path / "s.json", regions)
    broken = json.loads(json.dumps(raw))
    broken["harmonic"][0]["c"][0] = [9999, 1.0, 0.0]
    (tmp_path / "b.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(CatalogError, match="constituent term"):
        load(tmp_path / "b.json", regions)
    skip = json.loads(json.dumps(raw))
    skip["subordinate"][0]["hh"] = None
    (tmp_path / "k.json").write_text(json.dumps(skip), encoding="utf-8")
    cat = load(tmp_path / "k.json", regions)
    assert cat.skipped == [skip["subordinate"][0]["id"]]
    assert len(cat.stations) == 3255


def test_catalog_shape() -> None:
    cat = load()
    assert cat.skipped == []
    assert sum(1 for s in cat.stations if not s.is_subordinate) == 1232
    assert sum(1 for s in cat.stations if s.region is None) == 32
    assert cat.station("nope") is None
    assert isinstance(cat.predictor("9414290"), HarmonicPredictor)
    s = cat.station("9414290")
    assert s is not None and s.display_name.endswith(", CA")
