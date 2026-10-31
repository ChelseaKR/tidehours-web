"""King tides: each station's highest predicted tides in a twelve-month window.

The ranking is a port of personal-site's scripts/king-tides-rank.mjs, itself
ported from Tide Hours (KingTideRanking), so the app, the old chelseakr.com
page and this site pick the same days. Unlike the old page, which copied
NOAA's published high/low predictions, the highs here are computed by this
site's engine from NOAA's harmonic constants; tests/test_kingtides.py checks
them against that NOAA-derived page and against the California Coastal
Commission's and Washington Sea Grant's published dates.

1. Every predicted high; each local day keeps its highest one.
2. The `seed_days` highest days, grouped into runs where consecutive seeds
   are at most `merge_gap_days` apart.
3. The `max_series` runs with the highest peaks.
4. Each run widened by neighboring days within `shoulder_fraction` of the
   window's tidal range (highest high minus lowest low) of the run's peak.
   Runs that then touch are merged.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .catalog import Catalog
from .engine import TideEvent

# (state, NOAA station id, place label). Harmonic stations only, all in the
# app's catalog; the same 31 stations as the chelseakr.com page.
STATIONS: list[tuple[str, str, str]] = [
    ("WA", "9449424", "Cherry Point (Bellingham area)"),
    ("WA", "9449880", "Friday Harbor"),
    ("WA", "9444090", "Port Angeles"),
    ("WA", "9444900", "Port Townsend"),
    ("WA", "9447659", "Everett"),
    ("WA", "9447130", "Seattle"),
    ("WA", "9446484", "Tacoma"),
    ("WA", "9446807", "Olympia (Budd Inlet)"),
    ("WA", "9443090", "Neah Bay"),
    ("WA", "9440910", "Toke Point (Willapa Bay)"),
    ("OR", "9439040", "Astoria"),
    ("OR", "9437540", "Garibaldi (Tillamook Bay)"),
    ("OR", "9435380", "South Beach (Newport)"),
    ("OR", "9432780", "Charleston (Coos Bay)"),
    ("OR", "9431647", "Port Orford"),
    ("CA", "9419750", "Crescent City"),
    ("CA", "9418767", "Humboldt Bay (North Spit)"),
    ("CA", "9416841", "Arena Cove (Point Arena)"),
    ("CA", "9415020", "Point Reyes"),
    ("CA", "9414290", "San Francisco (Golden Gate)"),
    ("CA", "9414750", "Alameda"),
    ("CA", "9414523", "Redwood City"),
    ("CA", "9414131", "Half Moon Bay (Pillar Point)"),
    ("CA", "9413450", "Monterey"),
    ("CA", "9412110", "Port San Luis"),
    ("CA", "9411340", "Santa Barbara"),
    ("CA", "9410840", "Santa Monica"),
    ("CA", "9410660", "Los Angeles (Outer Harbor)"),
    ("CA", "9410580", "Newport Beach (Corona del Mar)"),
    ("CA", "9410230", "La Jolla"),
    ("CA", "9410170", "San Diego"),
]

# The season this site's king-tide pages describe. The copy (the Coastal
# Commission's dates) is for this season, so a new season is an edit here
# and in the copy, once a year before November (docs/DECISIONS.md 0006).
SEASON_START = "2026-11-01"
SEASON_DAYS = 365


@dataclass(frozen=True)
class Ranking:
    seed_days: int = 20
    merge_gap_days: int = 2
    max_series: int = 5
    shoulder_fraction: float = 0.03


STANDARD = Ranking()


@dataclass(frozen=True)
class Day:
    date: str  # local YYYY-MM-DD
    time: str  # local HH:MM
    height: float


def _day_index(start: str, date: str) -> int:
    return (dt.date.fromisoformat(date) - dt.date.fromisoformat(start)).days


def rank(events: list[tuple[str, str, float, str]], start: str, params: Ranking = STANDARD) -> list[list[Day]]:  # noqa: C901
    """`events` are (local date, local HH:MM, feet, "H" or "L")."""
    daily: dict[int, Day] = {}
    highest = float("-inf")
    lowest = float("inf")
    for date, time, height, kind in events:
        if kind == "L":
            lowest = min(lowest, height)
            continue
        if kind != "H":
            raise ValueError(f"king tides: unknown event kind {kind} at {date} {time}")
        highest = max(highest, height)
        i = _day_index(start, date)
        have = daily.get(i)
        if have and have.height >= height:
            continue
        daily[i] = Day(date, time, height)
    if not daily or params.seed_days <= 0 or params.max_series <= 0:
        return []
    span = highest - lowest if lowest != float("inf") else 0.0
    tolerance = max(0.0, params.shoulder_fraction) * span

    ranked = sorted(daily.items(), key=lambda kv: (-kv[1].height, kv[0]))
    seeds = sorted(i for i, _ in ranked[: params.seed_days])
    groups: list[list[int]] = []
    for i in seeds:
        if groups and i - groups[-1][-1] <= params.merge_gap_days:
            groups[-1].append(i)
        else:
            groups.append([i])

    def peak(g: list[int]) -> float:
        return max(daily[i].height for i in g)

    kept = sorted(groups, key=lambda g: -peak(g))[: params.max_series]  # stable on ties
    spans: list[list[int]] = []
    for g in kept:
        p = peak(g)
        lo, hi = g[0], g[-1]
        while lo - 1 in daily and daily[lo - 1].height >= p - tolerance:
            lo -= 1
        while hi + 1 in daily and daily[hi + 1].height >= p - tolerance:
            hi += 1
        spans.append([lo, hi])
    spans.sort()
    merged: list[list[int]] = []
    for s in spans:
        if merged and s[0] <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], s[1])
        else:
            merged.append(list(s))
    return [[daily[i] for i in range(lo, hi + 1) if i in daily] for lo, hi in merged]


def series_peak(days: list[Day]) -> Day:
    best = days[0]
    for d in days:
        if d.height > best.height:
            best = d
    return best


def local_events(events: list[TideEvent], tz: str) -> list[tuple[str, str, float, str]]:
    """Events as NOAA prints them: local wall time to the nearest minute."""
    zone = ZoneInfo(tz)
    out = []
    for e in events:
        t = dt.datetime.fromtimestamp(round(e.time / 60) * 60, zone)
        out.append((t.date().isoformat(), t.strftime("%H:%M"), round(e.height, 3), e.kind))
    return out


@dataclass(frozen=True)
class StationSeason:
    state: str
    id: str
    place: str
    noaa_name: str
    mhhw_ft: float
    series: list[list[Day]]

    def above_mhhw(self, day: Day) -> float:
        return round(day.height, 2) - self.mhhw_ft


def window(start: str = SEASON_START, days: int = SEASON_DAYS) -> tuple[str, str]:
    end = dt.date.fromisoformat(start) + dt.timedelta(days=days - 1)
    return start, end.isoformat()


def season(catalog: Catalog, datums: dict[str, float], start: str = SEASON_START) -> list[StationSeason]:
    """Every king-tide station's ranked series. A station with no datum or no
    series is an error, never an empty row."""
    first, last = window(start)
    out: list[StationSeason] = []
    for state, sid, place in STATIONS:
        station = catalog.station(sid)
        if station is None or station.is_subordinate:
            raise ValueError(f"king tides: {sid} is not a harmonic station in the catalog")
        if sid not in datums:
            raise ValueError(f"king tides: no MHHW datum for {sid}")
        zone = ZoneInfo(station.tz)
        t0 = dt.datetime.combine(dt.date.fromisoformat(first), dt.time(), zone).timestamp()
        t1 = dt.datetime.combine(dt.date.fromisoformat(last) + dt.timedelta(days=1), dt.time(), zone).timestamp()
        events = local_events(catalog.harmonic(sid).events(t0, t1), station.tz)
        series = rank(events, first)
        if not series:
            raise ValueError(f"king tides: no series for {sid}")
        out.append(StationSeason(state, sid, place, station.name, datums[sid], series))
    return out
