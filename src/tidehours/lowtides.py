"""The lowest daylight low tides: dated events for tide pooling, per region
(docs/DECISIONS.md 0021).

For each region, a fixed list of harmonic stations. Every predicted low at
those stations in the next `WINDOW_DAYS` local days (from the build day)
counts when it is

1. in daylight: at least `MARGIN_MINUTES` after sunrise and before sunset
   at that station on that day, and
2. below `THRESHOLD_FT` (0 ft MLLW) as the page prints it, to a tenth of a
   foot.

Each local day keeps only its lowest such low across the region's stations,
so a list never has two entries on one day (or two at one station on one
day). The region's list is the `LIST_SIZE` lowest of those days, shown in
date order. It is an event list, never a table of every tide: the free/paid
line in docs/DECISIONS.md 0001 stands.

A region with no qualifying low in the window gets no rows. The page says so
in words and names the first qualifying low after the window, searched up to
`SEARCH_DAYS` ahead, or says there is none in that time.

Every time and height is this site's engine's, from NOAA's harmonic
constants. Sunrise and sunset are computed here (`sun_times`), with no data
file and no network, from NOAA's Solar Calculator equations; they are only
used to decide what counts as daylight and to give the sun times beside each
event. When the site's sky module (feat/sky, docs/DECISIONS.md 0019) lands,
`sun_times` should call it instead, so the site has one sun computation.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .catalog import Catalog
from .engine import TideEvent

THRESHOLD_FT = 0.0
WINDOW_DAYS = 60
LIST_SIZE = 6
MARGIN_MINUTES = 30
SEARCH_DAYS = 365
# The sun's center at -0.833 degrees: 34' of refraction plus 16' of
# semidiameter, the U.S. Naval Observatory's definition of sunrise and sunset.
SUN_ALTITUDE = -0.833


@dataclass(frozen=True)
class RegionSpec:
    code: str  # state code; the page's anchor is lt-<code>
    name: str
    zone: str  # every station in the region is on this clock
    stations: tuple[tuple[str, str], ...]  # (NOAA id, place label)


# Harmonic stations only, on the open coast or close to it where there are
# tide pools. The WA, OR and CA places are the king-tide page's stations.
REGIONS: tuple[RegionSpec, ...] = (
    RegionSpec("WA", "Washington", "America/Los_Angeles", (
        ("9443090", "Neah Bay"),
        ("9444090", "Port Angeles"),
        ("9444900", "Port Townsend"),
        ("9449880", "Friday Harbor"),
        ("9447130", "Seattle"),
        ("9440910", "Toke Point (Willapa Bay)"),
    )),
    RegionSpec("OR", "Oregon", "America/Los_Angeles", (
        ("9439040", "Astoria"),
        ("9437540", "Garibaldi (Tillamook Bay)"),
        ("9435380", "South Beach (Newport)"),
        ("9432780", "Charleston (Coos Bay)"),
        ("9431647", "Port Orford"),
    )),
    RegionSpec("CA", "California", "America/Los_Angeles", (
        ("9419750", "Crescent City"),
        ("9418767", "Humboldt Bay (North Spit)"),
        ("9416841", "Arena Cove (Point Arena)"),
        ("9415020", "Point Reyes"),
        ("9414290", "San Francisco (Golden Gate)"),
        ("9414131", "Half Moon Bay (Pillar Point)"),
        ("9413450", "Monterey"),
        ("9412110", "Port San Luis"),
        ("9411340", "Santa Barbara"),
        ("9410840", "Santa Monica"),
        ("9410580", "Newport Beach (Corona del Mar)"),
        ("9410230", "La Jolla"),
        ("9410170", "San Diego"),
    )),
    RegionSpec("HI", "Hawaii", "Pacific/Honolulu", (
        ("1611400", "Nawiliwili (Kauai)"),
        ("1612340", "Honolulu (Oahu)"),
        ("1615680", "Kahului (Maui)"),
        ("1617433", "Kawaihae (Hawaii Island)"),
        ("1617760", "Hilo (Hawaii Island)"),
    )),
    RegionSpec("ME", "Maine", "America/New_York", (
        ("8410140", "Eastport"),
        ("8413320", "Bar Harbor"),
        ("8415490", "Rockland"),
        ("8418150", "Portland"),
        ("8419317", "Wells"),
    )),
)  # fmt: skip


def _julian_century(ts: float) -> float:
    return (ts / 86_400 + 2_440_587.5 - 2_451_545.0) / 36_525


def _sun_terms(ts: float) -> tuple[float, float]:
    """The sun's declination (degrees) and the equation of time (minutes) at
    an instant: NOAA's Solar Calculator spreadsheet, term for term."""
    c = _julian_century(ts)
    l0 = math.fmod(280.46646 + c * (36_000.76983 + c * 0.0003032), 360.0)
    m = 357.52911 + c * (35_999.05029 - 0.0001537 * c)
    e = 0.016708634 - c * (0.000042037 + 0.0000001267 * c)
    mr = math.radians(m)
    center = (
        math.sin(mr) * (1.914602 - c * (0.004817 + 0.000014 * c))
        + math.sin(2 * mr) * (0.019993 - 0.000101 * c)
        + math.sin(3 * mr) * 0.000289
    )
    omega = math.radians(125.04 - 1_934.136 * c)
    apparent = math.radians(l0 + center - 0.00569 - 0.00478 * math.sin(omega))
    mean_obliquity = 23 + (26 + (21.448 - c * (46.815 + c * (0.00059 - c * 0.001813))) / 60) / 60
    obliquity = math.radians(mean_obliquity + 0.00256 * math.cos(omega))
    decl = math.degrees(math.asin(math.sin(obliquity) * math.sin(apparent)))
    y = math.tan(obliquity / 2) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr)
    )
    return decl, eot


def _hour_angle(lat: float, decl: float) -> float | None:
    """Degrees from solar noon to the sun at SUN_ALTITUDE, or None when it
    never gets there that day (polar day or night)."""
    la, d = math.radians(lat), math.radians(decl)
    x = (math.sin(math.radians(SUN_ALTITUDE)) - math.sin(la) * math.sin(d)) / (math.cos(la) * math.cos(d))
    if not -1.0 <= x <= 1.0:
        return None
    return math.degrees(math.acos(x))


def sun_times(lat: float, lon: float, tz: str, d: dt.date) -> tuple[float, float] | None:
    """Sunrise and sunset (POSIX seconds) on the local date `d`, or None when
    the sun does not both rise and set that day. Each is refined twice with
    the sun's position at the time found, which puts it within about a
    minute of the Naval Observatory's times at the latitudes used here
    (tests/test_lowtides.py)."""
    zone = ZoneInfo(tz)
    noon_local = dt.datetime.combine(d, dt.time(12), zone).timestamp()
    out: list[float] = []
    for sign in (-1.0, 1.0):
        t = noon_local
        for _ in range(3):
            decl, eot = _sun_terms(t)
            ha = _hour_angle(lat, decl)
            if ha is None:
                return None
            utc_day = math.floor(t / 86_400) * 86_400
            noon = utc_day + (720 - 4 * lon - eot) * 60
            # The solar noon nearest the local noon of `d`.
            noon += round((noon_local - noon) / 86_400) * 86_400
            t = noon + sign * 4 * ha * 60
        out.append(t)
    rise, set_ = out
    if dt.datetime.fromtimestamp(rise, zone).date() != d or dt.datetime.fromtimestamp(set_, zone).date() != d:
        return None
    return rise, set_


def _hhmm(ts: float, zone: ZoneInfo) -> str:
    return dt.datetime.fromtimestamp(round(ts / 60) * 60, zone).strftime("%H:%M")


@dataclass(frozen=True)
class Low:
    station_id: str
    place: str
    date: str  # local YYYY-MM-DD
    time: str  # local HH:MM
    height: float  # feet above MLLW
    sunrise: str  # local HH:MM
    sunset: str  # local HH:MM

    def stamp(self) -> str:
        """What the page carries for scripts/check_site.py to compare."""
        return f"{self.station_id} {self.date} {self.time} {self.height:.1f}"


@dataclass(frozen=True)
class RegionLows:
    spec: RegionSpec
    first: str  # the window's first and last local dates
    last: str
    lows: list[Low]  # date order; empty when none qualifies
    next_after: Low | None  # the first one after the window, only when `lows` is empty

    @property
    def code(self) -> str:
        return self.spec.code


def qualifies(height: float) -> bool:
    """Below the threshold as printed: -0.04 ft prints as 0.0 ft, so it does
    not count."""
    return round(height, 1) < THRESHOLD_FT


def daylight_lows(cat: Catalog, spec: RegionSpec, first: dt.date, days: int) -> dict[str, Low]:
    """Local date -> the region's lowest qualifying daylight low that day."""
    zone = ZoneInfo(spec.zone)
    t0 = dt.datetime.combine(first, dt.time(), zone).timestamp()
    t1 = dt.datetime.combine(first + dt.timedelta(days=days), dt.time(), zone).timestamp()
    margin = MARGIN_MINUTES * 60
    best: dict[str, Low] = {}
    for sid, place in spec.stations:
        station = cat.station(sid)
        if station is None or station.is_subordinate:
            raise ValueError(f"low tides: {sid} is not a harmonic station in the catalog")
        if station.tz != spec.zone:
            raise ValueError(f"low tides: {sid} is in {station.tz}, not {spec.zone}")
        events: list[TideEvent] = cat.harmonic(sid).events(t0, t1)
        suns: dict[dt.date, tuple[float, float] | None] = {}
        for e in events:
            if e.kind != "L" or not qualifies(e.height):
                continue
            local = dt.datetime.fromtimestamp(e.time, zone)
            d = local.date()
            if d not in suns:
                suns[d] = sun_times(station.lat, station.lon, spec.zone, d)
            sun = suns[d]
            if sun is None or not sun[0] + margin <= e.time <= sun[1] - margin:
                continue
            low = Low(
                sid, place, d.isoformat(), _hhmm(e.time, zone), e.height, _hhmm(sun[0], zone), _hhmm(sun[1], zone)
            )
            have = best.get(low.date)
            if have is None or (low.height, low.time) < (have.height, have.time):
                best[low.date] = low
    return best


def region_lows(cat: Catalog, spec: RegionSpec, today: dt.date) -> RegionLows:
    last = today + dt.timedelta(days=WINDOW_DAYS - 1)
    by_day = daylight_lows(cat, spec, today, WINDOW_DAYS)
    chosen = sorted(by_day.values(), key=lambda lo: (lo.height, lo.date))[:LIST_SIZE]
    lows = sorted(chosen, key=lambda lo: lo.date)
    after: Low | None = None
    if not lows:
        later = daylight_lows(cat, spec, last + dt.timedelta(days=1), SEARCH_DAYS - WINDOW_DAYS)
        if later:
            after = later[min(later)]
    return RegionLows(spec, today.isoformat(), last.isoformat(), lows, after)


def today_in(spec: RegionSpec, now: dt.datetime) -> dt.date:
    return now.astimezone(ZoneInfo(spec.zone)).date()


def season(cat: Catalog, now: dt.datetime, states: set[str] | None = None) -> list[RegionLows]:
    """Each region's lows for the build instant, in REGIONS order; a build
    of only some states gets only their regions."""
    return [region_lows(cat, r, today_in(r, now)) for r in REGIONS if states is None or r.code in states]
