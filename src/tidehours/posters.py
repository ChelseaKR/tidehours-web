"""A station page's link to that town's printable year-of-tides poster in the
Tide Hours shop on Etsy (docs/DECISIONS.md 0037, built as 0035 builds the
calendar links).

The posters are Tide Hours' own, sold as digital downloads in the shop 0029
links to, one per town and year. `copy/posters.json` lists the ones on
sale: a station id, the Etsy listing id, the year, and the title the link
shows. An entry is added by a pull request when a listing is live; there is
no repository variable.

A listed station's own page carries one sentence with one plain link,
`https://www.etsy.com/listing/ID` and nothing after it, with the same
attributes as the calendar's link (0035) and no click event. The sentence
comes after the calendar's when a station has both. The link shows while
the page's first day is in the poster's year or earlier, so a 2027 poster
leaves the page on January 1, 2028 without anyone editing a file.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .booklets import CLAIMS, STATION_ID
from .calendars import REL, URL_PREFIX, valid_listing

LIST = Path(__file__).parent / "copy" / "posters.json"
COPY = Path(__file__).parent / "copy" / "poster_link.json"
# The title every poster's link shares: the year, "Tide Poster:", and the
# place. Nothing else fits, so the link text cannot carry a price or a claim.
TITLE_PATTERN = re.compile(r"(20[0-9]{2}) Tide Poster: [A-Z][A-Za-z.' -]{0,38}[A-Za-z.]")
KEYS = {"listing", "year", "title"}


@dataclass(frozen=True)
class Poster:
    listing: str
    year: int
    title: str

    @property
    def url(self) -> str:
        """The listing's own page on Etsy, with nothing after the id."""
        return URL_PREFIX + self.listing


def _poster(station_id: str, entry: Any) -> Poster:
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
        raise ValueError(f"station {station_id}: {title!r} is not a title like '{year} Tide Poster: Place'")
    return Poster(listing, year, title)


def load(path: Path | None = None) -> dict[str, Poster]:
    """Station id -> its poster, from the committed list (or `path`, for
    tests). Anything that is not exactly a station id with a listing id, a
    year and a title is refused, and so is one listing listed for two
    stations."""
    source = path or LIST
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"posters"} or not isinstance(raw["posters"], dict):
        raise ValueError(f'{source.name}: expected {{"posters": {{...}}}}')
    out = {station_id: _poster(station_id, entry) for station_id, entry in raw["posters"].items()}
    listings = [p.listing for p in out.values()]
    if len(listings) != len(set(listings)):
        raise ValueError(f"{source.name}: one listing is listed for two stations")
    return out


def shown(poster: Poster, today: dt.date) -> bool:
    """Whether the link shows on a page whose first day is `today` (the
    station's own date): until the poster's year is over."""
    return poster.year >= today.year


def block(poster: Poster | None) -> dict[str, Any] | None:
    """What the station template needs for the sentence, or None for a page
    with no poster to show."""
    if poster is None:
        return None
    text: dict[str, str] = json.loads(COPY.read_text(encoding="utf-8"))
    return {
        "listing": poster.listing,
        "url": poster.url,
        "rel": REL,
        "title": poster.title,
        "before": text["before"].replace("{year}", str(poster.year)),
        "after": text["after"],
    }
