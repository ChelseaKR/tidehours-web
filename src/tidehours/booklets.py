"""A station page's link to that station's printed tide-table booklet on
Amazon (docs/DECISIONS.md 0030).

The booklets are Tide Hours' own, published through Amazon KDP, one per
station and year. `copy/booklets.json` lists the ones that are on sale: a
station id, the booklet's ASIN, its year, and its title as printed on the
cover. The list ships empty, and empty leaves no trace in the build. An
entry is added by a pull request when a booklet goes live; there is no
repository variable.

A listed station's own page carries one sentence with one plain link,
`https://www.amazon.com/dp/ASIN` and nothing after it: no Associates tag,
even when the affiliate switch (0016) is on, no query string, no tracking
parameter and no click event. The link shows while the page's first day is
in the booklet's year or earlier, so a 2027 booklet leaves the page on
January 1, 2028 without anyone editing a file.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIST = Path(__file__).parent / "copy" / "booklets.json"
COPY = Path(__file__).parent / "copy" / "booklet_link.json"
# A paperback's ASIN: "B0" and eight capitals or digits, or the book's
# ISBN-10 (checked with its check digit). fullmatch, so a lowercase letter,
# a space, a newline or a whole address is refused.
ASIN_PATTERN = re.compile(r"B0[A-Z0-9]{8}|[0-9]{9}[0-9X]")
URL_PREFIX = "https://www.amazon.com/dp/"
REL = "noopener"
# The pages that may name Amazon in words, without a link, while a booklet
# link shows somewhere in the build.
MENTION_PAGES = ("privacy/", "terms/")
STATION_ID = re.compile(r"[0-9A-Z]{7}")
# The title on the cover, which every booklet shares: the year, "Tide
# Tables:", and the place. Nothing else fits, so the link text cannot carry
# a price or a claim.
TITLE_PATTERN = re.compile(r"(20[0-9]{2}) Tide Tables: [A-Z][A-Za-z.' -]{0,38}[A-Za-z.]")
CLAIMS = re.compile(r"\b(best|top|only|first|cheap|deals?|rated|official)\b", re.I)
KEYS = {"asin", "year", "title"}


def valid_asin(asin: str) -> bool:
    if ASIN_PATTERN.fullmatch(asin) is None:
        return False
    if asin.startswith("B0"):
        return True
    digits = [10 if c == "X" else int(c) for c in asin]
    return sum((10 - i) * d for i, d in enumerate(digits)) % 11 == 0


@dataclass(frozen=True)
class Booklet:
    asin: str
    year: int
    title: str

    @property
    def url(self) -> str:
        """The booklet's own page on Amazon, with nothing after the ASIN."""
        return URL_PREFIX + self.asin


def _booklet(station_id: str, entry: Any) -> Booklet:
    if STATION_ID.fullmatch(station_id) is None:
        raise ValueError(f"{station_id!r} is not a station id")
    if not isinstance(entry, dict) or set(entry) != KEYS:
        raise ValueError(f"station {station_id}: an entry has exactly asin, year and title")
    asin, year, title = entry["asin"], entry["year"], entry["title"]
    if not isinstance(asin, str) or not valid_asin(asin):
        raise ValueError(f"station {station_id}: {asin!r} is not an ASIN")
    if type(year) is not int or not 2000 <= year <= 2099:
        raise ValueError(f"station {station_id}: {year!r} is not a year")
    named = TITLE_PATTERN.fullmatch(title) if isinstance(title, str) else None
    if named is None or named.group(1) != str(year) or CLAIMS.search(title):
        raise ValueError(f"station {station_id}: {title!r} is not a title like '{year} Tide Tables: Place'")
    return Booklet(asin, year, title)


def load(path: Path | None = None) -> dict[str, Booklet]:
    """Station id -> its booklet, from the committed list (or `path`, for
    tests). Anything that is not exactly a station id with an ASIN, a year
    and a title is refused, and so is one ASIN listed for two stations."""
    source = path or LIST
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"booklets"} or not isinstance(raw["booklets"], dict):
        raise ValueError(f'{source.name}: expected {{"booklets": {{...}}}}')
    out = {station_id: _booklet(station_id, entry) for station_id, entry in raw["booklets"].items()}
    asins = [b.asin for b in out.values()]
    if len(asins) != len(set(asins)):
        raise ValueError(f"{source.name}: one ASIN is listed for two stations")
    return out


def shown(booklet: Booklet, today: dt.date) -> bool:
    """Whether the link shows on a page whose first day is `today` (the
    station's own date): until the booklet's year is over."""
    return booklet.year >= today.year


def block(booklet: Booklet | None) -> dict[str, Any] | None:
    """What the station template needs for the sentence, or None for a page
    with no booklet to show."""
    if booklet is None:
        return None
    text: dict[str, str] = json.loads(COPY.read_text(encoding="utf-8"))
    return {
        "asin": booklet.asin,
        "url": booklet.url,
        "rel": REL,
        "title": booklet.title,
        "before": text["before"].replace("{year}", str(booklet.year)),
        "after": text["after"],
    }


def notice(any_shown: bool) -> dict[str, str] | None:
    """The privacy page's words about the links, or None when no page in the
    build shows one."""
    if not any_shown:
        return None
    text: dict[str, str] = json.loads(COPY.read_text(encoding="utf-8"))
    return {"heading": text["privacyHeading"], "body": text["privacy"]}
