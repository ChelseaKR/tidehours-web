"""The station catalog: the Tide Hours app's bundled `stations.json`
(NOAA CO-OPS harmonic constants, datums and subordinate offsets), decoded the
way TideCore's StationCatalog decodes it, plus NOAA's region names.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .engine import HarmonicPredictor, Offsets, Predictor, SubordinatePredictor, YearCache
from .tidetype import TideType, tide_type

DATA_DIR = Path(__file__).resolve().parent / "data"


class CatalogError(ValueError):
    pass


# Abbreviations in NOAA's station names that stay in capitals. Everything else
# NOAA writes in capitals (its convention for the long-running reference
# stations, "SAN FRANCISCO (Golden Gate)", "BOSTON") is a place name.
ACRONYMS = frozenset(
    [
        "AFB",
        "AK",
        "ANVSA",
        "CBBT",
        "GNSS",
        "GPS",
        "ICW",
        "ICWW",
        "LAWMA",
        "MA",
        "MARAD",
        "MSF",
        "NAB",
        "NAS",
        "NC",
        "NE",
        "NERR",
        "NOAA",
        "NW",
        "NY",
        "PGA",
        "RR",
        "SE",
        "SW",
        "US",
        "USCG",
        "USS",
    ]
)
_CAPS_WORD = re.compile(r"\b[A-Z][A-Z']+\b(?![&-])")


def tidy_name(name: str) -> str:
    """NOAA's name with words in capitals written as place names
    ("SAN FRANCISCO (Golden Gate)" -> "San Francisco (Golden Gate)").
    Abbreviations (ICWW, USCG, and dotted ones like N.J. or D.C.) are kept.
    Display only: ids, URLs and the data file keep NOAA's name (DECISIONS 0013)."""

    def fix(m: re.Match[str]) -> str:
        w = m.group(0)
        if w in ACRONYMS:
            return w
        return "'".join(part[:1] + part[1:].lower() for part in w.split("'"))

    return _CAPS_WORD.sub(fix, name)


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
    _amplitudes: dict[str, dict[str, float]]

    def station(self, station_id: str) -> Station | None:
        return self._by_id.get(station_id)

    def predictor(self, station_id: str) -> Predictor:
        station = self._by_id[station_id]
        if station.reference_id is None:
            return self._harmonic[station_id]
        return SubordinatePredictor(self._harmonic[station.reference_id], self._offsets[station_id])

    def offsets(self, station_id: str) -> Offsets:
        return self._offsets[station_id]

    def harmonic(self, station_id: str) -> HarmonicPredictor:
        return self._harmonic[station_id]

    def tide_type(self, station_id: str) -> TideType | None:
        """A harmonic station's type of tide from its own constants; None for a
        subordinate station or one missing K1, O1, M2 or S2 (DECISIONS 0014)."""
        amplitudes = self._amplitudes.get(station_id)
        return tide_type(amplitudes) if amplitudes is not None else None


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
    amplitudes: dict[str, dict[str, float]] = {}
    skipped: list[str] = []
    for h in raw["harmonic"]:
        idx, amp, ph = [], [], []
        for term in h["c"]:
            if len(term) != 3 or not 0 <= int(term[0]) < len(names):
                raise CatalogError(f"constituent term for {h['id']}")
            idx.append(int(term[0]))
            amp.append(float(term[1]))
            ph.append(float(term[2]))
        amplitudes[h["id"]] = {names[i]: a for i, a in zip(idx, amp, strict=True)}
        harmonic[h["id"]] = HarmonicPredictor(float(h["z0"]), idx, amp, ph, speeds, years)
        stations.append(
            Station(h["id"], tidy_name(h["n"]), h["st"], h["la"], h["lo"], h["tz"], None, regions.get(h["id"]))
        )
    for s in raw["subordinate"]:
        # TideCore skips a subordinate station whose reference or heights are
        # missing; so does the site, and it reports the count.
        if s["ref"] not in harmonic or s["k"] not in ("R", "F") or s.get("hh") is None or s.get("hl") is None:
            skipped.append(s["id"])
            continue
        offsets[s["id"]] = Offsets(s["ref"], s["k"], float(s["th"]), float(s["tl"]), float(s["hh"]), float(s["hl"]))
        stations.append(
            Station(s["id"], tidy_name(s["n"]), s["st"], s["la"], s["lo"], s["tz"], s["ref"], regions.get(s["id"]))
        )
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
        _amplitudes=amplitudes,
    )
