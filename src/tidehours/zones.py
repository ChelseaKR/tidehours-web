"""A station's time zone in plain words ("Pacific Time (PT)"), for the page.

The IANA id ("America/Los_Angeles") stays in the data and in the page's
data-tz attribute, where the script needs it; readers see the name.
tests/test_site.py checks that every zone in the catalog has a name here, so
the fallback below is for a zone a future data refresh brings in. It never
shows an empty or raw value: it gives the UTC offset ("UTC-4", written with a
true minus sign), or, for an id it cannot read, "the station's local time".
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NAMES = {
    # The 50 states and DC.
    "America/New_York": "Eastern Time (ET)",
    "America/Detroit": "Eastern Time (ET)",
    "America/Indiana/Indianapolis": "Eastern Time (ET)",
    "America/Kentucky/Louisville": "Eastern Time (ET)",
    "America/Chicago": "Central Time (CT)",
    "America/Menominee": "Central Time (CT)",
    "America/Denver": "Mountain Time (MT)",
    "America/Boise": "Mountain Time (MT)",
    "America/Phoenix": "Mountain Standard Time (MST)",
    "America/Los_Angeles": "Pacific Time (PT)",
    "America/Anchorage": "Alaska Time (AKT)",
    "America/Juneau": "Alaska Time (AKT)",
    "America/Sitka": "Alaska Time (AKT)",
    "America/Yakutat": "Alaska Time (AKT)",
    "America/Nome": "Alaska Time (AKT)",
    "America/Metlakatla": "Alaska Time (AKT)",
    "America/Adak": "Hawaii–Aleutian Time (HST/HDT)",
    "Pacific/Honolulu": "Hawaii Standard Time (HST)",
    # Territories and the Pacific stations NOAA predicts.
    "America/Puerto_Rico": "Atlantic Standard Time (AST)",
    "America/St_Thomas": "Atlantic Standard Time (AST)",
    "Pacific/Guam": "Chamorro Standard Time (ChST)",
    "Pacific/Saipan": "Chamorro Standard Time (ChST)",
    "Pacific/Pago_Pago": "Samoa Standard Time (SST)",
    "Pacific/Midway": "Samoa Standard Time (SST)",
    "Pacific/Apia": "Samoa Time (Apia, UTC+13)",
    "Pacific/Majuro": "Marshall Islands Time (UTC+12)",
    "Pacific/Kwajalein": "Marshall Islands Time (UTC+12)",
    "Pacific/Wake": "Wake Island Time (UTC+12)",
}

UNKNOWN = "the station's local time"


def _offset(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "\u2212"  # U+2212, a true minus sign
    hours, rest = divmod(abs(minutes), 60)
    return f"{sign}{hours}" + (f":{rest:02d}" if rest else "")


def _minutes(when: dt.datetime) -> int:
    delta = when.utcoffset()
    return round(delta.total_seconds() / 60) if delta is not None else 0


def label(tz: str, year: int | None = None) -> str:
    """The zone's plain name; else its UTC offset, standard time first when
    it keeps daylight saving time ("UTC-5/-4", with true minus signs); else
    UNKNOWN."""
    if tz in NAMES:
        return NAMES[tz]
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return UNKNOWN
    y = year if year is not None else dt.datetime.now(dt.UTC).year
    # Standard time is the smaller offset, in either hemisphere.
    offsets = sorted({_minutes(dt.datetime(y, m, 15, 12, tzinfo=zone)) for m in (1, 7)})
    return "UTC" + "/".join(_offset(m) for m in offsets)
