"""Sunrise, sunset, civil twilight, moonrise, moonset and the moon's phase
for one station's local day, computed at build time with no data file and no
network (docs/DECISIONS.md 0019).

The sun: NOAA's Solar Calculator equations (NOAA Global Monitoring
Laboratory, after Meeus, *Astronomical Algorithms*), the sun's center at an
apparent altitude of -0.833 degrees (34' of refraction plus 16' of
semidiameter), as the U.S. Naval Observatory defines sunrise and sunset. The
altitude is evaluated every minute of the station's local day, midnight to
midnight in its own IANA zone (so a daylight saving day has 23 or 25 hours),
and each horizon crossing is placed between the two minutes either side of it.
Civil twilight begins and ends with the sun's center 6 degrees below the
horizon, with no refraction, as USNO defines it.

The moon: Meeus chapter 47's main periodic terms for the moon's longitude,
latitude and distance, and chapter 48 for the phase angle and the fraction
of the disk lit. A primary phase (new moon, first quarter, full moon, last
quarter) is the instant the moon's longitude minus the sun's is a multiple of
90 degrees. Moonrise and moonset: the same series turned into right ascension
and declination, the station's local sidereal time (Meeus 12.4), and the
moon's center at a geocentric altitude of 0.7275 times its horizontal
parallax less 0.5667 degrees (Meeus 15), which puts the upper limb on the
horizon after refraction, as USNO defines moonrise and moonset. Like the sun,
the altitude is sampled every minute of the local day.

Nothing here makes up a value. A day the sun does not rise or does not set
has no time for it: `rise` or `set` is None, and the page says so in words
(polar night and midnight sun at Prudhoe Bay and the other Arctic stations).
The same holds for civil twilight, and for a day without a moonrise or a
moonset, which comes about once a month everywhere.
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np

# The sun's center at sunrise and sunset (USNO's definition).
HORIZON_DEG = -0.833
# The sun's center at the start and end of civil twilight.
CIVIL_DEG = -6.0
EARTH_RADIUS_KM = 6378.14
# TT - UT, seconds, for 2026-27 (IERS: about 69 s). Meeus's lunar series are
# in TT; a minute's error here moves a primary phase by under a minute.
DELTA_T = 69.0
J2000 = 2451545.0
STEP = 60.0  # seconds between altitude samples


def julian_day(ts: float | np.ndarray) -> float | np.ndarray:
    """Julian day (UT) of a Unix time."""
    return ts / 86400.0 + 2440587.5


def _sun_terms(t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """NOAA Solar Calculator: the sun's declination (degrees), the equation
    of time (minutes) and its apparent longitude (degrees), for Julian
    centuries t since J2000."""
    l0 = np.mod(280.46646 + t * (36000.76983 + t * 0.0003032), 360.0)
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = np.radians(m)
    c = (
        np.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + np.sin(2 * mr) * (0.019993 - 0.000101 * t)
        + np.sin(3 * mr) * 0.000289
    )
    omega = np.radians(125.04 - 1934.136 * t)
    app_long = l0 + c - 0.00569 - 0.00478 * np.sin(omega)
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = np.radians(eps0 + 0.00256 * np.cos(omega))
    decl = np.degrees(np.arcsin(np.sin(eps) * np.sin(np.radians(app_long))))
    y = np.tan(eps / 2) ** 2
    l0r = np.radians(l0)
    eot = 4.0 * np.degrees(
        y * np.sin(2 * l0r)
        - 2 * e * np.sin(mr)
        + 4 * e * y * np.sin(mr) * np.cos(2 * l0r)
        - 0.5 * y * y * np.sin(4 * l0r)
        - 1.25 * e * e * np.sin(2 * mr)
    )
    return decl, eot, app_long


@lru_cache(maxsize=256)
def _sun_grid(start: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample times from `start`, every STEP seconds, with the sun's
    declination and equation of time at each. Shared by every station whose
    local day starts at the same instant (the same date and zone)."""
    ts = start + np.arange(n) * STEP
    t = np.asarray((julian_day(ts) - J2000) / 36525.0, dtype=np.float64)
    decl, eot, _ = _sun_terms(t)
    return ts, decl, eot


def sun_altitude(ts: np.ndarray, decl: np.ndarray, eot: np.ndarray, lat: float, lon: float) -> np.ndarray:
    """The sun's geometric altitude (degrees) at Unix times `ts`."""
    utc_minutes = np.mod(ts, 86400.0) / 60.0
    hour_angle = np.radians(np.mod(utc_minutes + eot + 4.0 * lon, 1440.0) / 4.0 - 180.0)
    la, dr = math.radians(lat), np.radians(decl)
    cos_zenith = np.clip(math.sin(la) * np.sin(dr) + math.cos(la) * np.cos(dr) * np.cos(hour_angle), -1.0, 1.0)
    altitude: np.ndarray = 90.0 - np.degrees(np.arccos(cos_zenith))
    return altitude


@dataclass(frozen=True)
class SunEvent:
    kind: str  # "rise" or "set"
    time: dt.datetime  # local, rounded to the minute
    ts: float  # the instant, POSIX seconds, not rounded


@dataclass(frozen=True)
class SunDay:
    """The sun on one local day. `events` are the sunrises and sunsets in
    time order; with none, `up_all_day` says which kind of day it is."""

    date: dt.date
    events: list[SunEvent]
    up_all_day: bool
    # Unix-time spans of the day with the sun below the horizon, for the
    # curve's night shading.
    dark: list[tuple[float, float]]
    # Civil dawn and dusk ("dawn", "dusk"), in time order; with none,
    # `civil_light_all_day` says whether the sun stayed above -6 degrees
    # all day or below it all day.
    civil: list[SunEvent]
    civil_light_all_day: bool

    @property
    def rise(self) -> dt.datetime | None:
        return next((e.time for e in self.events if e.kind == "rise"), None)

    @property
    def set(self) -> dt.datetime | None:
        return next((e.time for e in self.events if e.kind == "set"), None)


def _minute(ts: float, zone: ZoneInfo) -> dt.datetime:
    return dt.datetime.fromtimestamp(round(ts / 60.0) * 60.0, zone)


def _crossings(ts: np.ndarray, h: np.ndarray) -> list[tuple[bool, float]]:
    """Where h (sampled at ts, STEP apart) changes sign: (rising, instant),
    linear between the two samples, since altitude is smooth over a minute."""
    up = h >= 0
    out: list[tuple[bool, float]] = []
    for i in np.nonzero(up[1:] != up[:-1])[0]:
        frac = float(h[i] / (h[i] - h[i + 1]))
        out.append((bool(up[i + 1]), float(ts[i]) + frac * STEP))
    return out


def _local_day(tz: str, d: dt.date) -> tuple[ZoneInfo, float, float]:
    zone = ZoneInfo(tz)
    start = dt.datetime.combine(d, dt.time(), zone).timestamp()
    end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), zone).timestamp()
    return zone, start, end


def sun_day(lat: float, lon: float, tz: str, d: dt.date) -> SunDay:
    zone, start, end = _local_day(tz, d)
    ts, decl, eot = _sun_grid(start, round((end - start) / STEP) + 1)
    alt = sun_altitude(ts, decl, eot, lat, lon)
    h = alt - HORIZON_DEG
    crossings = _crossings(ts, h)
    events = [SunEvent("rise" if rising else "set", _minute(when, zone), when) for rising, when in crossings]
    dark: list[tuple[float, float]] = []
    edges = [start, *(when for _, when in crossings), end]
    below = not bool(h[0] >= 0)
    for a, b in itertools.pairwise(edges):
        if below:
            dark.append((a, b))
        below = not below
    c = alt - CIVIL_DEG
    civil = [SunEvent("dawn" if rising else "dusk", _minute(when, zone), when) for rising, when in _crossings(ts, c)]
    return SunDay(d, events, bool((h >= 0).all()), dark, civil, bool((c >= 0).all()))


def sun_times(lat: float, lon: float, tz: str, d: dt.date) -> tuple[float, float] | None:
    """Sunrise and the sunset after it (POSIX seconds, not rounded) on the
    local date `d` in zone `tz`, or None when the day has no sunrise followed
    by a sunset (polar night, midnight sun, or an Arctic day whose sunset
    comes before its sunrise). The same contract as lowtides.sun_times on
    feat/low-tides, which can call this once both are merged."""
    day = sun_day(lat, lon, tz, d)
    rise = next((e.ts for e in day.events if e.kind == "rise"), None)
    if rise is None:
        return None
    sunset = next((e.ts for e in day.events if e.kind == "set" and e.ts > rise), None)
    return None if sunset is None else (rise, sunset)


# Moon (Meeus chapter 47, main terms). Each row: D, M, M', F multipliers and
# the coefficient (degrees for longitude and latitude, km for distance).
_MOON_LON = (
    (0, 0, 1, 0, 6.288774), (2, 0, -1, 0, 1.274027), (2, 0, 0, 0, 0.658314), (0, 0, 2, 0, 0.213618),
    (0, 1, 0, 0, -0.185116), (0, 0, 0, 2, -0.114332), (2, 0, -2, 0, 0.058793), (2, -1, -1, 0, 0.057066),
    (2, 0, 1, 0, 0.053322), (2, -1, 0, 0, 0.045758), (0, 1, -1, 0, -0.040923), (1, 0, 0, 0, -0.034720),
    (0, 1, 1, 0, -0.030383), (2, 0, 0, -2, 0.015327), (0, 0, 1, 2, -0.012528), (0, 0, 1, -2, 0.010980),
    (4, 0, -1, 0, 0.010675), (0, 0, 3, 0, 0.010034), (4, 0, -2, 0, 0.008548), (2, 1, -1, 0, -0.007888),
    (2, 1, 0, 0, -0.006766), (1, 0, -1, 0, -0.005163), (1, 1, 0, 0, 0.004987), (2, -1, 1, 0, 0.004036),
    (2, 0, 2, 0, 0.003994), (4, 0, 0, 0, 0.003861), (2, 0, -3, 0, 0.003665), (0, 1, -2, 0, -0.002689),
)  # fmt: skip
_MOON_LAT = (
    (0, 0, 0, 1, 5.128122), (0, 0, 1, 1, 0.280602), (0, 0, 1, -1, 0.277693), (2, 0, 0, -1, 0.173237),
    (2, 0, -1, 1, 0.055413), (2, 0, -1, -1, 0.046271), (2, 0, 0, 1, 0.032573), (0, 0, 2, 1, 0.017198),
)  # fmt: skip
_MOON_DIST = (
    (0, 0, 1, 0, -20905.355), (2, 0, -1, 0, -3699.111), (2, 0, 0, 0, -2955.968), (0, 0, 2, 0, -569.925),
    (0, 1, 0, 0, 48.888), (2, 0, -2, 0, 246.158), (2, -1, -1, 0, -152.138), (2, 0, 1, 0, -170.733),
    (2, -1, 0, 0, -204.586), (0, 1, -1, 0, -129.620), (1, 0, 0, 0, 108.743), (0, 1, 1, 0, 104.755),
)  # fmt: skip
AU_KM = 149_597_870.7


def _series(
    rows: tuple[tuple[int, int, int, int, float], ...], args: tuple[np.ndarray, ...], e: np.ndarray, cos: bool
) -> np.ndarray:
    d, m, mp, f = args
    total = np.zeros_like(d)
    for cd, cm, cmp, cf, coeff in rows:
        x = cd * d + cm * m + cmp * mp + cf * f
        total = total + coeff * e ** abs(cm) * (np.cos(x) if cos else np.sin(x))
    return total


def _moon_ecliptic(t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The moon's apparent ecliptic longitude and latitude (degrees) and its
    distance (km), for Julian centuries t (TT) since J2000."""
    lp = 218.3164477 + 481267.88123421 * t - 0.0015786 * t * t
    d = np.radians(297.8501921 + 445267.1114034 * t - 0.0018819 * t * t)
    m = np.radians(357.5291092 + 35999.0502909 * t - 0.0001536 * t * t)
    mp = np.radians(134.9633964 + 477198.8675055 * t + 0.0087414 * t * t)
    f = np.radians(93.2720950 + 483202.0175233 * t - 0.0036539 * t * t)
    e = 1 - 0.002516 * t - 0.0000074 * t * t
    args = (d, m, mp, f)
    moon_lon = lp + _series(_MOON_LON, args, e, cos=False)
    moon_lat = _series(_MOON_LAT, args, e, cos=False)
    moon_dist = 385000.56 + _series(_MOON_DIST, args, e, cos=True)
    # The same nutation in longitude as the sun's apparent longitude.
    moon_app = moon_lon - 0.00478 * np.sin(np.radians(125.04 - 1934.136 * t))
    return moon_app, moon_lat, moon_dist


def _moon_sun(ts: float) -> tuple[float, float, float]:
    """(elongation in longitude, degrees 0-360; moon's latitude, degrees;
    moon's distance, km) at Unix time ts."""
    t = np.array([(float(julian_day(ts + DELTA_T)) - J2000) / 36525.0])
    moon_app, moon_lat, moon_dist = _moon_ecliptic(t)
    # sun_lon is apparent (nutation and aberration), like moon_app.
    _, _, sun_lon = _sun_terms(t)
    return float(moon_app[0] - sun_lon[0]) % 360.0, float(moon_lat[0]), float(moon_dist[0])


@lru_cache(maxsize=256)
def _moon_grid(start: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample times from `start`, every STEP seconds, with the moon's right
    ascension and declination (radians), the Greenwich mean sidereal time
    (degrees) and the moonrise altitude (degrees) at each. Shared by every
    station whose local day starts at the same instant."""
    ts = start + np.arange(n) * STEP
    jd_ut = np.asarray(julian_day(ts), dtype=np.float64)
    t = np.asarray((julian_day(ts + DELTA_T) - J2000) / 36525.0, dtype=np.float64)
    lam, beta, dist = _moon_ecliptic(t)
    omega = np.radians(125.04 - 1934.136 * t)
    eps = np.radians(23.4392911 - 0.0130042 * t + 0.00256 * np.cos(omega))
    lr, br = np.radians(lam), np.radians(beta)
    ra = np.arctan2(np.sin(lr) * np.cos(eps) - np.tan(br) * np.sin(eps), np.cos(lr))
    dec = np.arcsin(np.sin(br) * np.cos(eps) + np.cos(br) * np.sin(eps) * np.sin(lr))
    tu = (jd_ut - J2000) / 36525.0
    gmst = 280.46061837 + 360.98564736629 * (jd_ut - J2000) + 0.000387933 * tu * tu - tu**3 / 38710000.0
    gmst = np.asarray(gmst, dtype=np.float64)
    h0 = np.asarray(0.7275 * np.degrees(np.arcsin(EARTH_RADIUS_KM / dist)) - 0.5667, dtype=np.float64)
    return ts, np.asarray(ra, dtype=np.float64), np.asarray(dec, dtype=np.float64), gmst, h0


@dataclass(frozen=True)
class MoonTimes:
    """Moonrise and moonset on one local day at one place, in time order;
    with none, `up_all_day` says whether the moon stayed up or down."""

    date: dt.date
    events: list[SunEvent]  # kind "rise" or "set"
    up_all_day: bool

    @property
    def rise(self) -> dt.datetime | None:
        return next((e.time for e in self.events if e.kind == "rise"), None)

    @property
    def set(self) -> dt.datetime | None:
        return next((e.time for e in self.events if e.kind == "set"), None)


def moon_times(lat: float, lon: float, tz: str, d: dt.date) -> MoonTimes:
    """Moonrise and moonset at the station's position on its local day."""
    zone, start, end = _local_day(tz, d)
    ts, ra, dec, gmst, h0 = _moon_grid(start, round((end - start) / STEP) + 1)
    hour_angle = np.radians(gmst + lon) - ra
    la = math.radians(lat)
    sin_alt = np.clip(math.sin(la) * np.sin(dec) + math.cos(la) * np.cos(dec) * np.cos(hour_angle), -1.0, 1.0)
    h = np.degrees(np.arcsin(sin_alt)) - h0
    events = [SunEvent("rise" if rising else "set", _minute(when, zone), when) for rising, when in _crossings(ts, h)]
    return MoonTimes(d, events, bool((h >= 0).all()))


def illuminated(ts: float) -> float:
    """The fraction of the moon's disk lit (0 to 1), Meeus 48.2 and 48.3."""
    elong, lat, moon_km = _moon_sun(ts)
    psi = math.acos(math.cos(math.radians(lat)) * math.cos(math.radians(elong)))
    # The sun's distance at a constant 1 au: its yearly change moves the
    # phase angle by under 0.003 degrees.
    i = math.atan2(AU_KM * math.sin(psi), moon_km - AU_KM * math.cos(psi))
    return (1 + math.cos(i)) / 2


def elongation(ts: float) -> float:
    return _moon_sun(ts)[0]


PRIMARY = ("New moon", "First quarter", "Full moon", "Last quarter")


@dataclass(frozen=True)
class MoonDay:
    """The moon on one local day. `phase` and `fraction` are at local noon,
    named as the U.S. Naval Observatory names them: new or full moon when the
    lit share rounds to 0% or 100%, a quarter when it rounds to 50%, and
    otherwise waxing or waning, crescent or gibbous. `primary` is the primary
    phase whose instant falls on this day, if one does, with its local time."""

    date: dt.date
    phase: str
    fraction: float  # lit at local noon, 0 to 1
    primary: tuple[str, dt.datetime] | None

    @property
    def percent(self) -> int:
        return round(self.fraction * 100)


def phase_name(percent: int, waxing: bool) -> str:
    if percent == 0:
        return "New moon"
    if percent == 100:
        return "Full moon"
    if percent == 50:
        return "First quarter" if waxing else "Last quarter"
    return f"{'Waxing' if waxing else 'Waning'} {'crescent' if percent < 50 else 'gibbous'}"


def _primary_between(a: float, b: float) -> tuple[int, float] | None:
    """The primary phase (0-3) whose instant falls in [a, b), and that
    instant. The elongation grows about 12 degrees a day, so a day holds at
    most one."""
    ea = elongation(a)
    span = (elongation(b) - ea) % 360.0
    k = math.floor(ea / 90.0) + 1
    gap = (k * 90.0 - ea) % 360.0
    if gap >= span:
        return None
    lo, hi = a, b
    for _ in range(40):  # bisect to well under a second
        mid = (lo + hi) / 2
        if (elongation(mid) - ea) % 360.0 >= gap:
            hi = mid
        else:
            lo = mid
    return k % 4, hi


@lru_cache(maxsize=512)
def moon_day(tz: str, d: dt.date) -> MoonDay:
    """The moon on one local day in zone tz. It depends only on the date and
    the zone, not on where in the zone the station is (the moon's parallax
    moves the lit share by well under one percent)."""
    zone = ZoneInfo(tz)
    start = dt.datetime.combine(d, dt.time(), zone).timestamp()
    end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), zone).timestamp()
    noon = dt.datetime.combine(d, dt.time(12), zone).timestamp()
    frac = illuminated(noon)
    name = phase_name(round(frac * 100), elongation(noon) < 180.0)
    hit = _primary_between(start, end)
    primary = (PRIMARY[hit[0]], _minute(hit[1], zone)) if hit else None
    return MoonDay(d, name, frac, primary)
