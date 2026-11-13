"""A station page's link to that town's printable tide calendar in the Tide
Hours shop on Etsy (docs/DECISIONS.md 0035, built as 0030 builds the
booklet links).

The calendars are Tide Hours' own, sold as digital downloads in the shop
0029 links to, one per town and year. `copy/calendars.json` lists the ones
on sale: a station id, the Etsy listing id, the year, and the calendar's
title as the listing names it. An entry is added by a pull request when a
listing is live; there is no repository variable.

A listed station's own page carries one sentence with one plain link,
`https://www.etsy.com/listing/ID` and nothing after it: no slug, no query
string, no tracking parameter and no click event. The link shows while the
page's first day is in the calendar's year or earlier, so a 2027 calendar
leaves the page on January 1, 2028 without anyone editing a file.

The privacy page names the Etsy links by what the build shows: the print
shop's sentence alone (0029), the print shop's and the calendars' together,
or the calendars' alone (`notice`).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .booklets import CLAIMS, STATION_ID

LIST = Path(__file__).parent / "copy" / "calendars.json"
COPY = Path(__file__).parent / "copy" / "calendar_link.json"
# An Etsy listing id: digits only, no leading zero. fullmatch, so a slug, a
# whole address, a query string, a space or a newline is refused.
LISTING_PATTERN = re.compile(r"[1-9][0-9]{5,14}")
URL_PREFIX = "https://www.etsy.com/listing/"
REL = "noopener"
# The title every calendar shares: the year, "Tide Calendar:", and the
# place. Nothing else fits, so the link text cannot carry a price or a claim.
TITLE_PATTERN = re.compile(r"(20[0-9]{2}) Tide Calendar: [A-Z][A-Za-z.' -]{0,38}[A-Za-z.]")
KEYS = {"listing", "year", "title"}


def valid_listing(listing: str) -> bool:
    return LISTING_PATTERN.fullmatch(listing) is not None


@dataclass(frozen=True)
class Calendar:
    listing: str
    year: int
    title: str

    @property
    def url(self) -> str:
        """The listing's own page on Etsy, with nothing after the id."""
        return URL_PREFIX + self.listing


def _calendar(station_id: str, entry: Any) -> Calendar:
    if STATION_ID.fullmatch(station_id) is None:
        raise ValueError(f"{station_id!r} is not a station id")
    if not isinstance(entry, dict) or set(entry) != KEYS:
        raise ValueError(f"station {station_id}: an entry has exactly listing, year and title")
    listing, year, title = entry["listing"], entry["year"], entry["title"]
    if not isinstance(listing, str) or not valid_listing(listing):
        raise ValueError(f"station {station_id}: {listing!r} is not an Etsy listing id")
    if type(year) is not int or not 2000 <= year <= 2099:
        raise ValueError(f"station {station_id}: {year!r} is not a year")
    named = TITLE_PATTERN.fullmatch(title) if isinstance(title, str) else None
    if named is None or named.group(1) != str(year) or CLAIMS.search(title):
        raise ValueError(f"station {station_id}: {title!r} is not a title like '{year} Tide Calendar: Place'")
    return Calendar(listing, year, title)


def load(path: Path | None = None) -> dict[str, Calendar]:
    """Station id -> its calendar, from the committed list (or `path`, for
    tests). Anything that is not exactly a station id with a listing id, a
    year and a title is refused, and so is one listing listed for two
    stations."""
    source = path or LIST
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"calendars"} or not isinstance(raw["calendars"], dict):
        raise ValueError(f'{source.name}: expected {{"calendars": {{...}}}}')
    out = {station_id: _calendar(station_id, entry) for station_id, entry in raw["calendars"].items()}
    listings = [c.listing for c in out.values()]
    if len(listings) != len(set(listings)):
        raise ValueError(f"{source.name}: one listing is listed for two stations")
    return out


def shown(calendar: Calendar, today: dt.date) -> bool:
    """Whether the link shows on a page whose first day is `today` (the
    station's own date): until the calendar's year is over."""
    return calendar.year >= today.year


def block(calendar: Calendar | None) -> dict[str, Any] | None:
    """What the station template needs for the sentence, or None for a page
    with no calendar to show."""
    if calendar is None:
        return None
    text: dict[str, str] = json.loads(COPY.read_text(encoding="utf-8"))
    return {
        "listing": calendar.listing,
        "url": calendar.url,
        "rel": REL,
        "title": calendar.title,
        "before": text["before"].replace("{year}", str(calendar.year)),
        "after": text["after"],
    }


def notice(any_shown: bool, print_shop: dict[str, Any] | None) -> dict[str, str] | None:
    """The privacy page's words about the links to Etsy, or None when the
    build has none. `print_shop` is printshop.block's value. With no
    calendar link shown, the print shop's own sentence (0029), unchanged;
    with one, a sentence that names the station pages too, and the print
    shop's pages only when its link is on."""
    if not any_shown:
        if print_shop is None:
            return None
        return {"heading": print_shop["text"]["privacyHeading"], "body": print_shop["text"]["privacy"]}
    text: dict[str, str] = json.loads(COPY.read_text(encoding="utf-8"))
    return {"heading": text["privacyHeading"], "body": text["privacyWithShop" if print_shop else "privacy"]}
