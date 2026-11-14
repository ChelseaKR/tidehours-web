"""A subordinate station's NOAA corrections, in words, and the rule for when
its page is a twin of its reference station's (docs/DECISIONS.md 0033).

NOAA predicts a subordinate station by moving each of its reference
station's highs and lows by a published number of minutes and scaling or
shifting its height. Almost every subordinate page therefore shows its own
times and heights. A twin is the exception: both time corrections round to
0 minutes and the high-tide height is unchanged (a ratio of 1.00, or 0.0 ft),
so every time on the page and every high tide is the reference's, every day.
"""

from __future__ import annotations

from .engine import Offsets


def is_twin(o: Offsets) -> bool:
    """Whether the corrections leave every time and every high-tide height
    as the reference station's."""
    same_times = round(o.high_time_minutes) == 0 and round(o.low_time_minutes) == 0
    same_highs = o.high_height == 1.0 if o.adjustment == "R" else o.high_height == 0.0
    return same_times and same_highs


def height_phrase(adjustment: str, value: float) -> str:
    """A published height correction in words: "multiplied by 0.96",
    "0.7 ft lower", "unchanged"."""
    if adjustment == "R":
        return "unchanged" if round(value, 2) == 1.0 else f"multiplied by {value:.2f}"
    if round(value, 1) == 0.0:
        return "unchanged"
    return f"{abs(value):.1f} ft {'higher' if value > 0 else 'lower'}"
