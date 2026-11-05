"""One station's tides for one local day, ready for a page: highs and lows,
the curve and an SVG of it. Nothing here invents a value: a day with no
high or low says so, and a missing curve draws nothing."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .catalog import Station
from .engine import HarmonicPredictor, Predictor, TideEvent

MINUS = "−"


def no_negative_zero(value: float, places: int) -> float:
    """-0.04 ft would print as "-0.0 ft"; a value that rounds to zero is 0
    (the app's HeightUnit.noNegativeZero)."""
    scale = 10**places
    rounded = round(value * scale) / scale
    return 0.0 if rounded == 0 else rounded


def feet(value: float) -> str:
    v = no_negative_zero(value, 1)
    return f"{v:.1f}".replace("-", MINUS) + " ft"


def meters(value_ft: float) -> str:
    v = no_negative_zero(value_ft * 0.3048, 2)
    return f"{v:.2f}".replace("-", MINUS) + " m"


def clock(t: dt.datetime) -> str:
    """ "1:40 PM", the app's "h:mm a"."""
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def long_date(d: dt.date) -> str:
    """ "Saturday, October 31, 2026"."""
    return f"{d.strftime('%A, %B')} {d.day}, {d.year}"


def short_date(d: dt.date) -> str:
    return f"{d.strftime('%b')} {d.day}"


@dataclass(frozen=True)
class Event:
    kind: str  # "High" or "Low"
    time: str  # local "1:40 PM"
    iso: str  # local ISO 8601 with offset, for <time datetime>
    height_ft: str
    height_m: str
    raw_height: float


@dataclass(frozen=True)
class Day:
    date: dt.date
    events: list[Event]
    svg: str | None  # None when there is no curve to draw
    approximate: bool

    @property
    def long_date(self) -> str:
        return long_date(self.date)

    def summary(self) -> str:
        """ "high 5.4 ft at 1:40 PM, low −0.4 ft at 7:12 PM"."""
        if not self.events:
            return "no high or low tide predicted"
        return ", ".join(f"{e.kind.lower()} {e.height_ft} at {e.time}" for e in self.events)


def local_midnight(d: dt.date, zone: ZoneInfo) -> float:
    return dt.datetime.combine(d, dt.time(), zone).timestamp()


def _event(e: TideEvent, zone: ZoneInfo) -> Event:
    t = dt.datetime.fromtimestamp(round(e.time / 60) * 60, zone)
    return Event(
        kind="High" if e.kind == "H" else "Low",
        time=clock(t),
        iso=t.isoformat(timespec="minutes"),
        height_ft=feet(e.height),
        height_m=meters(e.height),
        raw_height=e.height,
    )


W, H = 640.0, 220.0
PAD_L, PAD_R, PAD_T, PAD_B = 4.0, 16.0, 12.0, 6.0


def _svg(
    curve: list[tuple[float, float]],
    events: list[TideEvent],
    start: float,
    end: float,
    zone: ZoneInfo,
    d: dt.date,
    approximate: bool,
    title_id: str,
) -> str | None:
    if len(curve) < 2:
        return None
    heights = [h for _, h in curve] + [e.height for e in events]
    lo, hi = min(heights), max(heights)
    span = hi - lo
    pad = max(span * 0.12, 0.1)
    y0, y1 = lo - pad, hi + pad

    def x(t: float) -> float:
        return PAD_L + (t - start) / (end - start) * (W - PAD_L - PAD_R)

    def y(h: float) -> float:
        return PAD_T + (y1 - h) / (y1 - y0) * (H - PAD_T - PAD_B)

    path = "M" + " L".join(f"{x(t):.1f},{y(h):.1f}" for t, h in curve)
    parts: list[str] = []
    y_labels: list[str] = []
    x_labels: list[str] = []
    # Axis labels are HTML beside the SVG, not SVG text and not on top of it:
    # axe cannot measure the contrast of text inside or over a drawing.

    # Horizontal grid lines at whole feet (at most about six of them).
    step = max(1, math.ceil((y1 - y0) / 5))
    first = math.ceil(y0 / step) * step
    level = first
    while level <= y1:
        yy = y(level)
        text = f"{level}".replace("-", MINUS) + " ft"
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        y_labels.append(f'<span class="ax" style="top:{yy / H * 100:.2f}%">{text}</span>')
        level += step
    for hour, name in ((0, "12 AM"), (6, "6 AM"), (12, "Noon"), (18, "6 PM")):
        t = dt.datetime.combine(d, dt.time(hour), zone).timestamp()
        xx = x(t)
        parts.append(f'<line class="tick" x1="{xx:.1f}" x2="{xx:.1f}" y1="{PAD_T}" y2="{H - PAD_B}"/>')
        x_labels.append(f'<span class="ax" style="left:{xx / W * 100:.2f}%">{name}</span>')
    dash = ' stroke-dasharray="6 4"' if approximate else ""
    parts.append(f'<path class="curve" d="{path}"{dash}/>')
    for e in events:
        parts.append(f'<circle class="dot dot-{e.kind}" cx="{x(e.time):.1f}" cy="{y(e.height):.1f}" r="4.5"/>')
    # The chart is a picture of the table beside it, which carries every
    # number, and the figure's caption summarizes it; so the drawing is hidden
    # from assistive technology.
    return (
        f'<div class="chart-box" aria-hidden="true" data-caption="{title_id}">'
        f'<div class="ax-y">{"".join(y_labels)}</div>'
        f'<svg class="tide-chart" viewBox="0 0 {W:.0f} {H:.0f}" focusable="false">'
        + "".join(parts)
        + "</svg>"
        + f'<div class="ax-x">{"".join(x_labels)}</div>'
        + "</div>"
    )


def station_day(station: Station, predictor: Predictor, d: dt.date, curve_step: float = 600.0) -> Day:
    zone = ZoneInfo(station.tz)
    start = local_midnight(d, zone)
    end = local_midnight(d + dt.timedelta(days=1), zone)
    events = predictor.events(start, end)
    curve = predictor.curve(start, end, curve_step)
    approximate = not isinstance(predictor, HarmonicPredictor)
    svg = _svg(curve, events, start, end, zone, d, approximate, f"chart-title-{d.isoformat()}")
    return Day(d, [_event(e, zone) for e in events], svg, approximate)


def local_today(station: Station, now: dt.datetime) -> dt.date:
    return now.astimezone(ZoneInfo(station.tz)).date()
