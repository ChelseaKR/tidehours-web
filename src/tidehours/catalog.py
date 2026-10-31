"""The station catalog: the Tide Hours app's bundled `stations.json`
(NOAA CO-OPS harmonic constants, datums and subordinate offsets), decoded the
way TideCore's StationCatalog decodes it, plus NOAA's region names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .engine import HarmonicPredictor, Offsets, Predictor, SubordinatePredictor, YearCache

DATA_DIR = Path(__file__).resolve().parent / "data"


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    state: str  # two-letter code; "" when NOAA lists none
    lat: float
    lon: float
    tz: str
    reference_id: str | None  # set for subordinate stations
    region: str | None  # NOAA's region name; None when NOAA's list has none

    @property
    def is_subordinate(self) -> bool:
        return self.reference_id is not None

    @property
    def display_name(self) -> str:
        return f"{self.name}, {self.state}" if self.state else self.name


@dataclass
class Catalog:
    stations: list[Station]
    retrieved: str
    attribution: str
    skipped: list[str]
    _by_id: dict[str, Station]
    _harmonic: dict[str, HarmonicPredictor]
    _offsets: dict[str, Offsets]

    def station(self, station_id: str) -> Station | None:
        return self._by_id.get(station_id)

    def predictor(self, station_id: str) -> Predictor:
        station = self._by_id[station_id]
        if station.reference_id is None:
            return self._harmonic[station_id]
        return SubordinatePredictor(self._harmonic[station.reference_id], self._offsets[station_id])

    def harmonic(self, station_id: str) -> HarmonicPredictor:
        return self._harmonic[station_id]


def _compounds(raw: dict[str, Any]) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    for name, parts in (raw.get("compound") or {}).items():
        out[name] = [(str(p[0]), int(p[1])) for p in parts]
    return out


def load(
    stations_path: Path | None = None,
    regions_path: Path | None = None,
) -> Catalog:
    stations_path = stations_path or DATA_DIR / "stations.json"
    regions_path = regions_path or DATA_DIR / "regions.json"
    raw = json.loads(stations_path.read_text(encoding="utf-8"))
    if raw.get("schema") != 1:
        raise CatalogError(f"unsupported stations.json schema {raw.get('schema')!r}")
    regions_raw = json.loads(regions_path.read_text(encoding="utf-8"))
    regions: dict[str, str] = regions_raw["regions"]

    names = [str(row[0]) for row in raw["constituents"]]
    speeds = np.array([float(row[1]) for row in raw["constituents"]], dtype=np.float64)
    years = YearCache(names, _compounds(raw), {k: float(v) for k, v in (raw.get("compoundPhase") or {}).items()})

    stations: list[Station] = []
    harmonic: dict[str, HarmonicPredictor] = {}
    offsets: dict[str, Offsets] = {}
    skipped: list[str] = []
    for h in raw["harmonic"]:
        idx, amp, ph = [], [], []
        for term in h["c"]:
            if len(term) != 3 or not 0 <= int(term[0]) < len(names):
                raise CatalogError(f"constituent term for {h['id']}")
            idx.append(int(term[0]))
            amp.append(float(term[1]))
            ph.append(float(term[2]))
        harmonic[h["id"]] = HarmonicPredictor(float(h["z0"]), idx, amp, ph, speeds, years)
        stations.append(Station(h["id"], h["n"], h["st"], h["la"], h["lo"], h["tz"], None, regions.get(h["id"])))
    for s in raw["subordinate"]:
        # TideCore skips a subordinate station whose reference or heights are
        # missing; so does the site, and it reports the count.
        if s["ref"] not in harmonic or s["k"] not in ("R", "F") or s.get("hh") is None or s.get("hl") is None:
            skipped.append(s["id"])
            continue
        offsets[s["id"]] = Offsets(s["ref"], s["k"], float(s["th"]), float(s["tl"]), float(s["hh"]), float(s["hl"]))
        stations.append(Station(s["id"], s["n"], s["st"], s["la"], s["lo"], s["tz"], s["ref"], regions.get(s["id"])))
    by_id: dict[str, Station] = {}
    for st in stations:
        by_id.setdefault(st.id, st)
    return Catalog(
        stations=list(by_id.values()),
        retrieved=str(raw["retrieved"]),
        attribution=str(raw["attribution"]),
        skipped=skipped,
        _by_id=by_id,
        _harmonic=harmonic,
        _offsets=offsets,
    )
