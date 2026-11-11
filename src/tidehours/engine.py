"""Tide prediction engine: a line-for-line port of the Tide Hours app's
TideCore (ChelseaKR/tide-hours, TideCore/Sources/TideCore: Astronomy.swift,
Constituents.swift, Prediction.swift), so the website and the app compute the
same numbers from the same NOAA constants.

Harmonic stations: h(t) = Z0 + sum f_i H_i cos(a_i t + (V0 + u)_i - kappa_i),
t in hours from 00:00 UTC on January 1, with V0 + u and f held for the
calendar year (Schureman, NOAA Special Publication 98; node factors at
July 2, 12:00 UTC, as the app does). Highs and lows keep a year's constants
for 30 minutes into the next year, as NOAA's published ones do (YEAR_CARRY).

Subordinate stations: NOAA's method. Take the reference station's highs and
lows, shift their times by the published minutes, and scale or offset their
heights. The curve between them is a cosine interpolation, an estimate, and is
labeled as one wherever it is drawn.

Times are POSIX seconds (UTC) as floats. Heights are feet above MLLW.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

_J2000 = 946_728_000.0  # 2000-01-01T12:00:00Z


def _norm(deg: float) -> float:
    r = math.fmod(deg, 360.0)
    return r + 360.0 if r < 0 else r


@dataclass(frozen=True)
class Astro:
    """Mean astronomical arguments (degrees) at an instant."""

    T: float
    s: float
    h: float
    p: float
    N: float
    p1: float

    @staticmethod
    def at(t: float) -> Astro:
        days = (t - _J2000) / 86_400
        c = days / 36_525
        c2, c3, c4 = c * c, c * c * c, c * c * c * c
        s = _norm(218.3164591 + 481_267.88134236 * c - 0.0013268 * c2 + c3 / 538_841 - c4 / 65_194_000)
        h = _norm(280.46645 + 36_000.7697489 * c + 0.00030322222 * c2 + c3 / 50_000_000)
        p = _norm(83.3532430 + 4_069.0137111 * c - 0.0103238 * c2 - c3 / 80_053 + c4 / 18_999_000)
        n = _norm(125.0445550 - 1_934.1361849 * c + 0.0020762 * c2 + c3 / 467_410 - c4 / 60_616_000)
        p1 = _norm(282.94 + 1.7192 * c)
        sod = math.fmod(t, 86_400)
        if sod < 0:
            sod += 86_400
        return Astro(T=_norm(180 + 15 * sod / 3_600), s=s, h=h, p=p, N=n, p1=p1)


@dataclass(frozen=True)
class Node:
    """Lunar-node quantities (radians)."""

    I: float  # noqa: E741 - Schureman's name
    xi: float
    nu: float
    nu_prime: float
    two_nu_double_prime: float
    P: float

    @staticmethod
    def of(a: Astro) -> Node:
        i = math.radians(5.145)
        w = math.radians(23.4393)
        n = math.radians(a.N)
        big_i = math.acos(math.cos(i) * math.cos(w) - math.sin(i) * math.sin(w) * math.cos(n))
        e1 = math.atan(math.cos(0.5 * (w - i)) / math.cos(0.5 * (w + i)) * math.tan(0.5 * n)) - 0.5 * n
        e2 = math.atan(math.sin(0.5 * (w - i)) / math.sin(0.5 * (w + i)) * math.tan(0.5 * n)) - 0.5 * n
        xi = -(e1 + e2)
        nu = e1 - e2
        nu_prime = math.atan2(math.sin(2 * big_i) * math.sin(nu), math.sin(2 * big_i) * math.cos(nu) + 0.3347)
        two_nupp = math.atan2(math.sin(big_i) ** 2 * math.sin(2 * nu), math.sin(big_i) ** 2 * math.cos(2 * nu) + 0.0727)
        return Node(I=big_i, xi=xi, nu=nu, nu_prime=nu_prime, two_nu_double_prime=two_nupp, P=math.radians(a.p) - xi)


# V = a*T + b*s + c*h + d*p + e*p1 + k (degrees), Schureman Table 2.
DOODSON: dict[str, tuple[int, int, int, int, int, int]] = {
    "M2": (2, -2, 2, 0, 0, 0), "S2": (2, 0, 0, 0, 0, 0), "N2": (2, -3, 2, 1, 0, 0),
    "K1": (1, 0, 1, 0, 0, -90), "M4": (4, -4, 4, 0, 0, 0), "O1": (1, -2, 1, 0, 0, 90),
    "M6": (6, -6, 6, 0, 0, 0), "MK3": (3, -2, 3, 0, 0, -90), "S4": (4, 0, 0, 0, 0, 0),
    "MN4": (4, -5, 4, 1, 0, 0), "NU2": (2, -3, 4, -1, 0, 0), "S6": (6, 0, 0, 0, 0, 0),
    "MU2": (2, -4, 4, 0, 0, 0), "2N2": (2, -4, 2, 2, 0, 0), "OO1": (1, 2, 1, 0, 0, -90),
    "LAM2": (2, -1, 0, 1, 0, 180), "S1": (1, 0, 0, 0, 0, 0), "M1": (1, -1, 1, 0, 0, -90),
    "J1": (1, 1, 1, -1, 0, -90), "MM": (0, 1, 0, -1, 0, 0), "SSA": (0, 0, 2, 0, 0, 0),
    "SA": (0, 0, 1, 0, 0, 0), "MSF": (0, 2, -2, 0, 0, 0), "MF": (0, 2, 0, 0, 0, 0),
    "RHO": (1, -3, 3, -1, 0, 90), "Q1": (1, -3, 1, 1, 0, 90), "T2": (2, 0, -1, 0, 1, 0),
    "R2": (2, 0, 1, 0, -1, 180), "2Q1": (1, -4, 1, 2, 0, 90), "P1": (1, 0, -1, 0, 0, 90),
    "2SM2": (2, 2, -2, 0, 0, 0), "M3": (3, -3, 3, 0, 0, 0), "L2": (2, -1, 2, -1, 0, 180),
    "2MK3": (3, -4, 3, 0, 0, 90), "K2": (2, 0, 2, 0, 0, 0), "M8": (8, -8, 8, 0, 0, 0),
    "MS4": (4, -2, 2, 0, 0, 0),
    "SIGMA1": (1, -4, 3, 0, 0, 90), "CHI1": (1, -1, 3, -1, 0, -90),
    "THETA1": (1, 1, -1, 1, 0, -90),
}  # fmt: skip


def equilibrium_argument(name: str, x: Astro) -> float:
    a, b, c, d, e, k = DOODSON[name]
    return _norm(a * x.T + b * x.s + c * x.h + d * x.p + e * x.p1 + k)


def node_correction(name: str, n: Node) -> tuple[float, float]:
    """Node factor f and node correction u (radians), as TideCore."""
    big_i, xi, nu, big_p = n.I, n.xi, n.nu, n.P
    f_m2 = math.cos(big_i / 2) ** 4 / 0.9154
    u_m2 = 2 * xi - 2 * nu
    f_o1 = math.sin(big_i) * math.cos(big_i / 2) ** 2 / 0.3800
    u_o1 = 2 * xi - nu
    f_k1 = math.sqrt(0.8965 * math.sin(2 * big_i) ** 2 + 0.6001 * math.sin(2 * big_i) * math.cos(nu) + 0.1006)
    u_k1 = -n.nu_prime
    if name in ("M2", "N2", "NU2", "MU2", "2N2", "LAM2", "MS4"):
        return f_m2, u_m2
    if name in ("S2", "S4", "S6", "SA", "SSA", "P1", "T2", "R2", "S1"):
        return 1.0, 0.0
    if name == "K1":
        return f_k1, u_k1
    if name in ("O1", "Q1", "RHO", "2Q1", "SIGMA1"):
        return f_o1, u_o1
    simple: dict[str, tuple[float, float]] = {
        "M4": (f_m2**2, 2 * u_m2),
        "MN4": (f_m2**2, 2 * u_m2),
        "M6": (f_m2**3, 3 * u_m2),
        "M8": (f_m2**4, 4 * u_m2),
        "MK3": (f_m2 * f_k1, u_m2 + u_k1),
        "2MK3": (f_m2 * f_m2 * f_k1, 2 * u_m2 - u_k1),
        "OO1": (math.sin(big_i) * math.sin(big_i / 2) ** 2 / 0.01640, -2 * xi - nu),
        "J1": (math.sin(2 * big_i) / 0.7214, -nu),
        "CHI1": (math.sin(2 * big_i) / 0.7214, -nu),
        "THETA1": (math.sin(2 * big_i) / 0.7214, -nu),
        "MM": ((2.0 / 3.0 - math.sin(big_i) ** 2) / 0.5021, 0.0),
        "MF": (math.sin(big_i) ** 2 / 0.1578, -2 * xi),
        "MSF": (f_m2, -u_m2),
        "2SM2": (f_m2, -u_m2),
        "M3": (math.cos(big_i / 2) ** 6 / 0.8758, 1.5 * u_m2),
    }
    if name in simple:
        return simple[name]
    if name == "K2":
        f = math.sqrt(19.0444 * math.sin(big_i) ** 4 + 2.7702 * math.sin(big_i) ** 2 * math.cos(2 * nu) + 0.0981)
        return f, -n.two_nu_double_prime
    if name == "L2":
        t2 = math.tan(big_i / 2) ** 2
        r = math.atan2(math.sin(2 * big_p), 1 / (6 * t2) - math.cos(2 * big_p))
        ra_inverse = math.sqrt(1 - 12 * t2 * math.cos(2 * big_p) + 36 * t2 * t2)
        return f_m2 * ra_inverse, u_m2 - r
    if name == "M1":
        ci = math.cos(big_i)
        q = math.atan2((5 * ci - 1) * math.sin(big_p), (7 * ci + 1) * math.cos(big_p))
        qa_inverse = math.sqrt(2.310 + 1.435 * math.cos(2 * big_p))
        return f_o1 * qa_inverse, xi - nu + q
    return 1.0, 0.0


def year_start(year: int) -> float:
    return datetime(year, 1, 1, tzinfo=UTC).timestamp()


def utc_year(t: float) -> int:
    return datetime.fromtimestamp(t, UTC).year


@dataclass(frozen=True)
class YearConstants:
    """f and V0 + u (degrees) for every catalog constituent, for one UTC year."""

    year: int
    start: float
    f: FloatArray
    vu: FloatArray


def year_constants(
    year: int,
    names: Sequence[str],
    compounds: dict[str, list[tuple[str, int]]],
    compound_phase: dict[str, float],
) -> YearConstants:
    start = year_start(year)
    a0 = Astro.at(start)
    node = Node.of(Astro.at(datetime(year, 7, 2, 12, tzinfo=UTC).timestamp()))

    def base(name: str) -> tuple[float, float] | None:
        if name not in DOODSON:
            return None
        f, u = node_correction(name, node)
        return f, equilibrium_argument(name, a0) + math.degrees(u)

    fs: list[float] = []
    vus: list[float] = []
    for name in names:
        b = base(name)
        parts = compounds.get(name, [])
        if b is not None:
            fs.append(b[0])
            vus.append(_norm(b[1]))
        elif parts and all(p in DOODSON for p, _ in parts):
            ff, v = 1.0, compound_phase.get(name, 0.0)
            for component, coef in parts:
                bc = base(component)
                assert bc is not None  # noqa: S101 - checked by all() above
                ff *= bc[0] ** abs(coef)
                v += coef * bc[1]
            fs.append(ff)
            vus.append(_norm(v))
        else:
            fs.append(0.0)  # Unknown constituent: contributes nothing, as in the app.
            vus.append(0.0)
    return YearConstants(year=year, start=start, f=np.array(fs), vu=np.array(vus))


@dataclass
class YearCache:
    names: list[str]
    compounds: dict[str, list[tuple[str, int]]]
    compound_phase: dict[str, float]
    _by_year: dict[int, YearConstants] = field(default_factory=dict)

    def get(self, year: int) -> YearConstants:
        y = self._by_year.get(year)
        if y is None:
            y = year_constants(year, self.names, self.compounds, self.compound_phase)
            self._by_year[year] = y
        return y


@dataclass(frozen=True)
class TideEvent:
    time: float
    height: float
    kind: str  # "H" or "L"


# A stand: a low and a high (or a high and a low) less than two hours apart
# that differ by less than 0.05 ft. NOAA's published high/low predictions
# leave these out; the app's engine (and `raw_events`) keeps them. Measured
# 2026-10-31 on a month of NOAA predictions at 14 small-range Gulf and
# Caribbean stations (docs/DECISIONS.md 0004): every pair NOAA omitted was
# 29 to 125 minutes apart and 0.0003 to 0.035 ft high, and the closest pairs
# NOAA kept were 125 minutes apart (0.020 ft) and 153 minutes (0.010 ft).
STAND_MINUTES = 120.0
STAND_FEET = 0.06
STAND_MARGIN = 3 * 3_600.0


def drop_stands(events: Sequence[TideEvent]) -> list[TideEvent]:
    """Remove each adjacent high/low pair that is a stand (see above), the
    flattest pair first, so a run of tiny wiggles collapses cleanly."""
    ev = list(events)
    while True:
        best: int | None = None
        best_dh = STAND_FEET
        for i in range(len(ev) - 1):
            a, b = ev[i], ev[i + 1]
            dh = abs(b.height - a.height)
            if a.kind != b.kind and b.time - a.time < STAND_MINUTES * 60 and dh < best_dh:
                best, best_dh = i, dh
        if best is None:
            return ev
        del ev[best : best + 2]


# NOAA's curve changes to the new year's constants at 00:00 GMT on January 1,
# as `heights` does, but its published highs and lows do not: a high or low
# that the old year's constants put before 00:30 GMT is published from the
# old year. Measured 2026-11-10 on NOAA's predictions around 2027-01-01 and
# 2028-01-01 at 18 stations (docs/DECISIONS.md 0031). The 10 tides the old
# constants put from 5 minutes before midnight to 29.96 minutes after
# (Kodiak, Womens Bay) are NOAA's to 0.007 ft with the old year's constants
# and 0.07 to 0.27 ft off with the new year's; the 7 they put from 30.28
# minutes after (Ouzinkie) to 62 are NOAA's to 0.009 ft with the new year's
# and 0.04 to 0.24 ft off with the old. A subordinate station follows its
# reference (Birch Islands, ME, 01:33, from Eastport's 00:20 low). NOAA's
# 6-minute heights at Fire Island, AK follow the new year from 00:00 on,
# 0.27 ft below its own 00:26 low.
YEAR_CARRY = 30 * 60.0


def tide_year(t: float) -> int:
    """The year whose constants find a high or low at `t`: the UTC year,
    kept for YEAR_CARRY into the next."""
    return utc_year(t - YEAR_CARRY)


class HarmonicPredictor:
    """The app's HarmonicPredictor, vectorized over time with numpy."""

    STEP = 360.0  # the app's 6-minute search grid

    def __init__(
        self,
        z0: float,
        index: Sequence[int],
        amplitude: Sequence[float],
        phase: Sequence[float],
        speeds: FloatArray,
        years: YearCache,
    ) -> None:
        self.z0 = z0
        self.index = np.asarray(index, dtype=np.int64)
        self.amplitude = np.asarray(amplitude, dtype=np.float64)
        self.phase = np.asarray(phase, dtype=np.float64)
        self.speed = speeds[self.index]
        self.years = years
        self._terms: dict[int, tuple[float, FloatArray, FloatArray]] = {}

    def _year_terms(self, year: int) -> tuple[float, FloatArray, FloatArray]:
        t = self._terms.get(year)
        if t is None:
            y = self.years.get(year)
            amp = y.f[self.index] * self.amplitude
            arg0 = y.vu[self.index] - self.phase
            t = (y.start, amp, arg0)
            self._terms[year] = t
        return t

    def _eval(self, times: FloatArray, derivative: bool, held: int | None = None) -> FloatArray:
        """Heights, or rates, with each instant's own UTC year's constants;
        with `held`, that one year's constants at every instant."""
        out = np.empty(times.shape, dtype=np.float64)
        if times.size == 0:
            return out
        if held is None:
            first, last = utc_year(float(times.min())), utc_year(float(times.max()))
        else:
            first = last = held
        for year in range(first, last + 1):
            if held is None:
                mask = (times >= year_start(year)) & (times < year_start(year + 1))
            else:
                mask = np.ones(times.shape, dtype=np.bool_)
            if not mask.any():
                continue
            start, amp, arg0 = self._year_terms(year)
            hours = (times[mask] - start) / 3_600
            # Chunks keep the (times x constituents) matrix small.
            vals = np.empty(hours.shape, dtype=np.float64)
            for i in range(0, hours.size, 4096):
                h = hours[i : i + 4096]
                arg = np.radians(np.outer(h, self.speed) + arg0)
                if derivative:
                    vals[i : i + 4096] = -(np.sin(arg) @ (amp * np.radians(self.speed)))
                else:
                    vals[i : i + 4096] = np.cos(arg) @ amp + self.z0
            out[mask] = vals
        return out

    def heights(self, times: FloatArray) -> FloatArray:
        return self._eval(np.asarray(times, dtype=np.float64), derivative=False)

    def height(self, t: float) -> float:
        return float(self.heights(np.array([t]))[0])

    def rates(self, times: FloatArray) -> FloatArray:
        """dh/dt in feet per hour."""
        return self._eval(np.asarray(times, dtype=np.float64), derivative=True)

    def events(self, start: float, end: float) -> list[TideEvent]:
        """Highs and lows in [start, end), with NOAA-style stands removed
        (`drop_stands`)."""
        if end <= start:
            return []
        raw = self.raw_events(start - STAND_MARGIN, end + STAND_MARGIN)
        return [e for e in drop_stands(raw) if start <= e.time < end]

    def raw_events(self, start: float, end: float) -> list[TideEvent]:
        """Every high and low in [start, end). Each year's constants find the
        highs and lows up to YEAR_CARRY after the year ends, as NOAA's do;
        everywhere else this is exactly the app's HarmonicPredictor.events."""
        if end <= start:
            return []
        out: list[TideEvent] = []
        for year in range(tide_year(start), tide_year(end) + 1):
            first = year_start(year) + YEAR_CARRY
            found = self._held_events(max(start, first), min(end, year_start(year + 1) + YEAR_CARRY), year)
            if start < first + STAND_MINUTES * 60:
                found = [e for e in self._hand_over(first, year, found) if start <= e.time < end]
            out += found
        return out

    def _hand_over(self, t: float, year: int, found: list[TideEvent]) -> list[TideEvent]:
        """`found`, highs and lows of `year`, as they follow the year
        before, which stops finding them at `t` (YEAR_CARRY into `year`).
        If the two years agree at `t` on whether the tide is rising, nothing
        changes. If they do not, one of them has passed a high or low that
        the other has not reached. Where the old year has passed it, the old
        year found it, and the new year's copy of the same tide, which
        follows `t` as a stand would, is left out (Kodiak, Womens Bay,
        2028-01-01: 00:29.96 and 00:30.71). Where the new year has passed
        it, neither found it, and it is put at `t` with the new year's
        height (NOAA's 00:30 low at Milbridge, ME, the same day)."""
        at = np.array([t])
        before = float(self._eval(at, derivative=True, held=year - 1)[0])
        after = float(self._eval(at, derivative=True, held=year)[0])
        if not (before < 0 < after or after < 0 < before):
            return found
        joint = TideEvent(t, float(self._eval(at, derivative=False, held=year)[0]), "H" if before > 0 else "L")
        copy = self._held_events(t, t + STAND_MINUTES * 60, year)[:1]
        if copy and abs(copy[0].height - joint.height) < STAND_FEET:
            return [e for e in found if e.time > copy[0].time + 1]  # a second: two searches' rounding
        return [joint, *found]

    def _held_events(self, start: float, end: float, year: int) -> list[TideEvent]:
        """The highs and lows in [start, end) with `year`'s constants: sign
        changes of dh/dt on a 6-minute grid, each refined by bisection to
        under one second."""
        if end <= start:
            return []
        grid = np.arange(start, end, self.STEP, dtype=np.float64)
        grid = np.append(grid, end) if grid[-1] < end else grid
        r = self._eval(grid, derivative=True, held=year)
        r0, r1 = r[:-1], r[1:]
        crossing = ((r0 > 0) & (r1 <= 0)) | ((r0 < 0) & (r1 >= 0))
        idx = np.nonzero(crossing)[0]
        if idx.size == 0:
            return []
        lo = grid[idx].copy()
        hi = grid[idx + 1].copy()
        rising = r0[idx] > 0
        while np.any(hi - lo > 0.5):
            active = hi - lo > 0.5
            mid = lo + (hi - lo) / 2
            rm = self._eval(mid, derivative=True, held=year)
            go_lo = active & ((rm > 0) == rising)
            go_hi = active & ~((rm > 0) == rising)
            lo = np.where(go_lo, mid, lo)
            hi = np.where(go_hi, mid, hi)
        t = lo + (hi - lo) / 2
        h = self._eval(t, derivative=False, held=year)
        return [
            TideEvent(float(tt), float(hh), "H" if up else "L")
            for tt, hh, up in zip(t, h, rising, strict=True)
            if start <= tt < end
        ]

    def curve(self, start: float, end: float, step: float = 600.0) -> list[tuple[float, float]]:
        """Evenly spaced samples in [start, end]."""
        times = np.arange(start, end + step / 2, step, dtype=np.float64)
        times = times[times <= end]
        return [(float(t), float(h)) for t, h in zip(times, self.heights(times), strict=True)]


@dataclass(frozen=True)
class Offsets:
    reference_id: str
    adjustment: str  # "R" ratio or "F" fixed feet
    high_time_minutes: float
    low_time_minutes: float
    high_height: float
    low_height: float


class SubordinatePredictor:
    def __init__(self, reference: HarmonicPredictor, offsets: Offsets) -> None:
        self.reference = reference
        self.offsets = offsets

    def events(self, start: float, end: float) -> list[TideEvent]:
        """NOAA derives a subordinate station from every reference high and
        low, stands included (measured at Christmas Bay, TX), so this shifts
        the reference's raw events, then removes the stands that result at
        the subordinate station itself (DECISIONS 0004)."""
        o = self.offsets
        margin = (max(abs(o.high_time_minutes), abs(o.low_time_minutes)) + 30) * 60 + STAND_MARGIN
        out: list[TideEvent] = []
        for e in self.reference.raw_events(start - margin, end + margin):
            high = e.kind == "H"
            t = e.time + (o.high_time_minutes if high else o.low_time_minutes) * 60
            adj = o.high_height if high else o.low_height
            h = e.height * adj if o.adjustment == "R" else e.height + adj
            out.append(TideEvent(t, h, e.kind))
        out.sort(key=lambda e: e.time)
        return [e for e in drop_stands(out) if start <= e.time < end]

    @staticmethod
    def interpolate(ev: Sequence[TideEvent], t: float) -> float | None:
        i = None
        for k, e in enumerate(ev):
            if e.time <= t:
                i = k
        if i is None or i + 1 >= len(ev):
            return None
        a, b = ev[i], ev[i + 1]
        span = b.time - a.time
        if span <= 0:
            return a.height
        x = (t - a.time) / span
        return a.height + (b.height - a.height) * (1 - math.cos(math.pi * x)) / 2

    def height(self, t: float) -> float | None:
        """Interpolated height, or None where no bracketing high and low exist."""
        return self.interpolate(self.events(t - 15 * 3_600, t + 15 * 3_600), t)

    def curve(self, start: float, end: float, step: float = 600.0) -> list[tuple[float, float]]:
        ev = self.events(start - 15 * 3_600, end + 15 * 3_600)
        out: list[tuple[float, float]] = []
        t = start
        while t <= end:
            h = self.interpolate(ev, t)
            if h is not None:
                out.append((t, h))
            t += step
        return out


Predictor = HarmonicPredictor | SubordinatePredictor
