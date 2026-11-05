"""A harmonic station's type of tide, from its own NOAA constants.

The form factor F = (K1 + O1) / (M2 + S2) is the ratio of the amplitudes of
the two main daily constituents to the two main twice-daily ones. NOAA's Tide
and Current Glossary ("type of tide", after Dietrich) classifies a tide as
semidiurnal under 0.25, mixed, mainly semidiurnal from 0.25 to 1.5, mixed,
mainly diurnal from 1.5 to 3.0, and diurnal above 3.0 (docs/DECISIONS.md 0014).

A station gets a type only when all four constituents are in its constants
and M2 + S2 is positive. Nothing is estimated for the others, and subordinate
stations get none: their constants are not in NOAA's data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DIURNAL = ("K1", "O1")
SEMIDIURNAL = ("M2", "S2")


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    meaning: str  # one plain sentence for a visitor


SEMI = Kind(
    "semidiurnal",
    "Semidiurnal",
    "Two high tides and two low tides a day, with the two highs about the same height and the two lows about the same height.",
)
MIXED_SEMI = Kind(
    "mixed-semidiurnal",
    "Mixed, mainly semidiurnal",
    "Usually two high tides and two low tides a day, but of different heights: one high is often higher than the other, and one low lower.",
)
MIXED_DIURNAL = Kind(
    "mixed-diurnal",
    "Mixed, mainly diurnal",
    "Often only one high tide and one low tide a day; on other days there are two of each, with one pair much smaller.",
)
DIURNAL_KIND = Kind(
    "diurnal",
    "Diurnal",
    "Usually one high tide and one low tide a day. For a few days about every two weeks the tide is small, and two highs and two lows can appear.",
)
KINDS = (SEMI, MIXED_SEMI, MIXED_DIURNAL, DIURNAL_KIND)


@dataclass(frozen=True)
class TideType:
    form_factor: float  # rounded to 2 decimals, as shown on the page
    kind: Kind


def classify(form_factor: float) -> Kind:
    """NOAA's thresholds, applied to the form factor as shown (2 decimals)."""
    if form_factor < 0.25:
        return SEMI
    if form_factor < 1.5:
        return MIXED_SEMI
    if form_factor <= 3.0:
        return MIXED_DIURNAL
    return DIURNAL_KIND


def tide_type(amplitudes: Mapping[str, float]) -> TideType | None:
    """The type of tide from a station's constituent amplitudes by name, or
    None when K1, O1, M2 or S2 is missing or M2 + S2 is not positive."""
    if any(name not in amplitudes for name in DIURNAL + SEMIDIURNAL):
        return None
    semi = amplitudes["M2"] + amplitudes["S2"]
    if semi <= 0:
        return None
    f = round((amplitudes["K1"] + amplitudes["O1"]) / semi, 2)
    return TideType(f, classify(f))
