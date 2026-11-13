"""/llms.txt in the format llmstxt.org specifies: an H1 with the site's name,
a blockquote summary, plain text, then H2 sections that are lists of
``[name](url): note`` links. The same pattern as Trout Truck's and Next Home
Game's files.

Station counts, the NOAA retrieval date and the king-tide calendars come from
the catalog this build reads; nothing is listed from memory. The promises
every page makes (predictions, not observations; not for navigation; not a
NOAA product; NOAA CO-OPS credited) are made here too.
"""

from __future__ import annotations

from .catalog import Catalog
from .kingtides import CALENDAR_STATES, calendar_path

SPEC_URL = "https://llmstxt.org/"


def render(cat: Catalog, base: str, *, app_store_url: str = "") -> str:
    base = base.rstrip("/")
    total = len(cat.stations)
    subordinate = sum(1 for s in cat.stations if s.is_subordinate)
    harmonic = total - subordinate
    app = (
        f"- [Tide Hours for iPhone]({app_store_url}): seven days, widgets and offline use"
        if app_store_url
        else "- The Tide Hours iPhone app (seven days, widgets, offline) is coming soon; it computes the same numbers on the phone."
    )
    lines = [
        "# Tide Hours",
        "",
        "> Tide Hours is a free website of predicted high and low tides for today "
        f"and tomorrow at {total:,} NOAA tide stations in the United States and its "
        "territories, with king-tide dates for Washington, Oregon and California. "
        "Every number is computed from NOAA CO-OPS harmonic constants and offsets "
        "when the site is built. These are predictions, not observations or "
        "forecasts, and not for navigation. Tide Hours is not a NOAA product and "
        "is not endorsed by NOAA.",
        "",
        "What the numbers mean: heights are in feet above mean lower low water "
        "(MLLW), the datum on NOAA charts, with meters alongside. Times are local "
        "to each station, with daylight saving time where it applies. "
        f"{harmonic:,} stations are harmonic stations, predicted from NOAA's "
        f"constituents; {subordinate:,} are subordinate stations, predicted from a "
        "reference station with NOAA's published time and height corrections, and "
        "their curve between highs and lows is an estimate. Wind, storms, river "
        "flow and air pressure can move the real water well above or below a "
        "prediction; the National Weather Service issues warnings.",
        "",
        "King tides: the year's highest predicted tides at West Coast stations. "
        '"Above a normal high tide" is the height above mean higher high water '
        "(MHHW) at that station. King-tide dates are predictions, not flood "
        "forecasts.",
        "",
        "Update cadence: the site is rebuilt once a day (11:20 UTC). The NOAA "
        f"station data in this build was retrieved on {cat.retrieved}.",
        "",
        "How to cite: name this site and credit NOAA CO-OPS as the source of the "
        'constants. Example: "Tide Hours (' + base + "/), predicted from NOAA CO-OPS "
        'data; predictions, not observations, and not for navigation."',
        "",
        f"This file follows the llms.txt format described at {SPEC_URL}.",
        "",
        "## Pages",
        "",
        f"- [Home]({base}/): every state and territory, and the king tides coming up",
        f"- [States and territories]({base}/#states): the index of state and territory pages, with station counts",
        f"- Station pages: {base}/stations/<NOAA station id>/, today's and tomorrow's highs and lows at one station",
        f"- State pages: {base}/states/<two-letter code>/, with region pages under /states/<code>/<region>/",
        f"- [King tides]({base}/king-tides/): the coming king tides on the West Coast",
    ]
    for code, (name, _slug) in CALENDAR_STATES.items():
        lines.append(
            f"- [{name} king tides]({base}/{calendar_path(code)}): the season's calendar, month by month ({code})"
        )
    lines += [
        f"- [Mareas reales (Spanish)]({base}/es/king-tides/): the king-tide page in Spanish",
        f"- [How the predictions are made]({base}/about/): the method, how it is checked against NOAA, and what the numbers are not",
        f"- [Sitemap]({base}/sitemap.xml)",
        app,
        "",
        "## Sources",
        "",
        "- [NOAA CO-OPS Metadata API](https://api.tidesandcurrents.noaa.gov/mdapi/prod/): "
        "harmonic constants, datums, subordinate offsets and region names; U.S. "
        "Government work in the public domain",
        "- [NOAA CO-OPS tide predictions](https://tidesandcurrents.noaa.gov/tide_predictions.html): the "
        "official predictions; check them for anything that matters",
        "- [NOAA CO-OPS disclaimers](https://tidesandcurrents.noaa.gov/disclaimers.html)",
        "",
    ]
    return "\n".join(lines)
