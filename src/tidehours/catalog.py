"""The station catalog: the Tide Hours app's bundled `stations.json`
(NOAA CO-OPS harmonic constants, datums and subordinate offsets), decoded the
way TideCore's StationCatalog decodes it, plus NOAA's region names.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
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


# NOAA's region names for the three U.S. Virgin Islands. NOAA codes some of
# their stations PR (state "PR" in its station metadata, and so in the app's
# bundle), which put Cruz Bay or Magens Bay on the Puerto Rico page. A station
# in one of these regions is listed under VI, in the islands' own time zone
# (the same clock as Puerto Rico's, UTC-4 all year), docs/DECISIONS.md 0017.
USVI_REGIONS = frozenset(["St. Croix Island", "St. Johns Island", "St. Thomas Island"])
USVI_TZ = "America/St_Thomas"


def territory(state: str, tz: str, region: str | None) -> tuple[str, str]:
    """The (state, time zone) a station is listed under: NOAA's, except that
    a U.S. Virgin Islands station is VI in America/St_Thomas."""
    if region in USVI_REGIONS or state == "VI":
        return "VI", USVI_TZ
    return state, tz


# The six harmonic stations NOAA lists without a state, all on U.S. islands
# its station names identify (DECISIONS 0018). UM is the U.S. Minor Outlying
# Islands.
TERRITORY_STATES = {
    "1619000": "UM",  # JOHNSTON ATOLL
    "1619910": "UM",  # SAND ISLAND, MIDWAY ISLANDS
    "1630000": "GU",  # APRA HARBOR, GUAM
    "1631428": "GU",  # Pago Bay, Guam
    "1770000": "AS",  # PAGO PAGO Harbor, Tutuila Island
    "1890000": "UM",  # WAKE ISLAND (U.S.)
}

# Where a station's coordinates rule out a state it would take from its
# reference station: the reference can be across a border (DECISIONS 0018).
# Each line is the state, what is across the border, and the test on
# (latitude, longitude). They are deliberately coarse, and every station NOAA
# itself codes with the state passes them, except NOAA's one Saipan station
# coded GU (tests/test_site.py).
Border = tuple[str, str, Callable[[float, float], bool]]
BORDERS: tuple[Border, ...] = (
    ("WA", "British Columbia (49th parallel)", lambda la, lo: la >= 49.0),
    ("WA", "Vancouver Island (Strait of Juan de Fuca)", lambda la, lo: la >= 48.42 and lo <= -123.3),
    ("AK", "British Columbia (south of Dixon Entrance)", lambda la, lo: la < 54.6 and -141 < lo < -129),
    ("AK", "British Columbia (east of Pearse Canal)", lambda la, lo: la < 54.85 and -130.65 < lo < -129),
    ("CA", "Oregon (42nd parallel)", lambda la, lo: la > 42.0),
    ("OR", "California (42nd parallel)", lambda la, lo: la < 42.0),
    ("OR", "Washington (north of the Columbia River)", lambda la, lo: la > 46.26),
    ("FL", "Georgia or Alabama (31st parallel)", lambda la, lo: la > 31.0),
    ("FL", "Georgia (St. Marys River)", lambda la, lo: lo > -82.5 and la > 30.85),
    ("GA", "South Carolina (Savannah River)", lambda la, lo: la > 32.09 and lo > -81.1),
    ("GA", "Florida (St. Marys River)", lambda la, lo: la < 30.7),
    ("SC", "North Carolina (Little River Inlet)", lambda la, lo: la > 33.8 and lo > -78.55),
    ("SC", "Georgia (Savannah River)", lambda la, lo: la < 32.0),
    ("NC", "South Carolina (Little River Inlet)", lambda la, lo: la < 33.85 and lo < -78.5),
    ("NC", "Virginia (36.55 degrees north)", lambda la, lo: la > 36.56),
    ("LA", "Mississippi (Pearl River)", lambda la, lo: la > 30.15 and lo > -89.55),
    ("LA", "Texas (Sabine River)", lambda la, lo: lo < -93.9),
    ("MS", "Louisiana (Pearl River)", lambda la, lo: lo < -89.65),
    ("MS", "Alabama", lambda la, lo: lo > -88.39),
    ("VA", "Maryland (Eastern Shore line)", lambda la, lo: lo > -76.25 and la > 38.03),
    ("VA", "North Carolina (36.55 degrees north)", lambda la, lo: la < 36.54),
    ("DC", "Maryland or Virginia", lambda la, lo: not (38.79 <= la <= 39.0 and -77.13 <= lo <= -76.9)),
    ("GU", "the Northern Mariana Islands", lambda la, lo: la > 13.8),
)


def across_border(state: str, lat: float, lon: float) -> str | None:
    """What is across the border when (lat, lon) cannot be in `state`, or
    None when nothing in BORDERS rules it out."""
    for code, across, outside in BORDERS:
        if code == state and outside(lat, lon):
            return across
    return None


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    state: str  # two-letter code; "" when NOAA lists none and none is filed (0018)
    lat: float
    lon: float
    tz: str
    reference_id: str | None  # set for subordinate stations
    region: str | None  # NOAA's region name; None when NOAA's list has none
    # Where `state` comes from when NOAA lists none (DECISIONS 0018):
    # "territory" (TERRITORY_STATES) or "reference" (the reference station's).
    filed_by: str | None = None

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
        filed_state = h["st"] or TERRITORY_STATES.get(h["id"], "")
        code, tz = territory(filed_state, h["tz"], regions.get(h["id"]))
        filed = "territory" if filed_state and not h["st"] else None
        stations.append(
            Station(h["id"], tidy_name(h["n"]), code, h["la"], h["lo"], tz, None, regions.get(h["id"]), filed)
        )
    ref_state = {st.id: st.state for st in stations}
    for s in raw["subordinate"]:
        # TideCore skips a subordinate station whose reference or heights are
        # missing; so does the site, and it reports the count.
        if s["ref"] not in harmonic or s["k"] not in ("R", "F") or s.get("hh") is None or s.get("hl") is None:
            skipped.append(s["id"])
            continue
        offsets[s["id"]] = Offsets(s["ref"], s["k"], float(s["th"]), float(s["tl"]), float(s["hh"]), float(s["hl"]))
        # A station NOAA lists without a state takes its reference station's,
        # unless its coordinates are across a border from it (0018).
        filed_state, filed = s["st"], None
        if not filed_state and ref_state[s["ref"]] and across_border(ref_state[s["ref"]], s["la"], s["lo"]) is None:
            filed_state, filed = ref_state[s["ref"]], "reference"
        code, tz = territory(filed_state, s["tz"], regions.get(s["id"]))
        stations.append(
            Station(s["id"], tidy_name(s["n"]), code, s["la"], s["lo"], tz, s["ref"], regions.get(s["id"]), filed)
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
