"""Engine details the golden tests do not reach: stands, edges, the year
boundary, and the catalog's refusals."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tidehours import catalog as catalog_mod
from tidehours.catalog import CatalogError, load
from tidehours.engine import (
    Astro,
    HarmonicPredictor,
    Node,
    SubordinatePredictor,
    TideEvent,
    drop_stands,
    node_correction,
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
