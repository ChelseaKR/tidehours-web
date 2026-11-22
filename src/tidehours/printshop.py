"""A link to the Tide Hours print shop on Etsy (docs/DECISIONS.md 0029).

Off unless a shop address is configured (`Config.print_shop_url`,
`--print-shop-url`, the repo variable PRINT_SHOP_URL). Off, the build has no
trace of it: no link, no section, and the privacy and terms pages unchanged.
On, the About page and the English king-tide page each carry one sentence
with one plain link to the shop, the privacy page says where the link goes,
and the terms page names Etsy among the trademarks.

The shop is Tide Hours' own, so this is not an affiliate link: no tag, no
tracking parameter, no click event, and no price or claim in the sentence.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import kingtides
from .catalog import Catalog

# An Etsy shop's own address, nothing else: no listing, search, query string
# or tracking parameter. fullmatch, so a trailing space or newline is refused.
URL_PATTERN = re.compile(r"https://www\.etsy\.com/shop/[A-Za-z0-9]{4,20}")
REL = "noopener"
# The pages that carry the link, as paths in the built site.
PAGES = ("about/", "king-tides/")
# The pages that may name Etsy in words without linking to it.
MENTION_PAGES = ("privacy/", "terms/")
# The state king-tide calendars that carry the same section, near the top,
# with a sentence naming the state's calendar towns (docs/DECISIONS.md 0051).
# Washington, Oregon and California only, as the owner approved; their paths
# are kingtides.calendar_path's (tests/test_king_shop_link.py holds them so).
CALENDAR_PAGES = ("king-tides/washington/", "king-tides/oregon/", "king-tides/california/")
COPY = Path(__file__).parent / "copy" / "print_shop.json"


def valid_url(url: str) -> bool:
    return URL_PATTERN.fullmatch(url) is not None


def block(url: str) -> dict[str, Any] | None:
    """What the templates need for the link, or None when the switch is off."""
    if not url:
        return None
    if not valid_url(url):
        raise ValueError(f"not an Etsy shop address: {url!r}")
    text: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))
    return {"url": url, "rel": REL, "text": text}


# The king-tide print sentences (docs/DECISIONS.md 0058): which page carries
# which of copy/print_shop.json's `kingPrints.lines`, in order, inside its
# Prints section. The hub names the five West Coast tide rings prints; each
# West Coast calendar names its own state's, then the made-to-order print.
KING_PRINT_PAGES = {
    "king-tides/": ("hub",),
    "king-tides/washington/": ("WA", "custom"),
    "king-tides/oregon/": ("OR", "custom"),
    "king-tides/california/": ("CA", "custom"),
}
LISTING_URL = "https://www.etsy.com/listing/{listing}"


def january_high(cat: Catalog, station: str, first: str, last: str) -> float:
    """The station's highest predicted high tide from `first` to `last`,
    local days, in feet above MLLW, from this site's engine."""
    st = cat.station(station)
    if st is None or st.is_subordinate:
        raise ValueError(f"king prints: {station} is not a harmonic station in the catalog")
    zone = ZoneInfo(st.tz)
    t0 = dt.datetime.combine(dt.date.fromisoformat(first), dt.time(), zone).timestamp()
    t1 = dt.datetime.combine(dt.date.fromisoformat(last) + dt.timedelta(days=1), dt.time(), zone).timestamp()
    highs = [e.height for e in cat.harmonic(station).events(t0, t1) if e.kind == "H"]
    if not highs:
        raise ValueError(f"king prints: no high tide at {station} from {first} to {last}")
    return max(highs)


def king_prints(
    shop: dict[str, Any] | None, cat: Catalog, seasons: list[kingtides.StationSeason]
) -> dict[str, list[list[tuple[str, str | None]]]]:
    """Each king-tide page's print sentences, as paragraphs of (words, link
    address or None), or {} with the shop off. A sentence says a print shows
    this January's king tides in its accent color, so the build fails unless
    each print's station has a predicted high tide at or above the
    threshold printed on it during its state's January king tides: the days
    the state's calendar gives for January (kingtides.calendar, the month
    line's span). The claim is checked, never assumed."""
    if shop is None:
        return {}
    text: dict[str, Any] = shop["text"]["kingPrints"]
    prints: dict[str, dict[str, Any]] = text["prints"]
    for listing, p in prints.items():
        january = [m.span for m in kingtides.calendar(seasons, p["state"]) if (m.year, m.month) == (2027, 1) and m.span]
        if len(january) != 1:
            raise ValueError(f"king prints: {p['state']} has no January king tides on its calendar")
        first, last = january[0][0], january[0][1]
        high = january_high(cat, p["station"], first, last)
        if high < p["thresholdFt"]:
            raise ValueError(
                f"king prints: {listing} ({p['place']}) reaches {high:.2f} ft in January, "
                f"under its {p['thresholdFt']} ft accent"
            )
    known = {*prints, text["custom"]}
    out: dict[str, list[list[tuple[str, str | None]]]] = {}
    for path, keys in KING_PRINT_PAGES.items():
        paragraphs: list[list[tuple[str, str | None]]] = []
        for key in keys:
            parts: list[tuple[str, str | None]] = []
            for part in text["lines"][key]:
                if isinstance(part, str):
                    parts.append((part, None))
                elif part["listing"] in known:
                    parts.append((part["text"], LISTING_URL.format(listing=part["listing"])))
                else:
                    raise ValueError(f"king prints: {part['listing']} is not a listed print")
            paragraphs.append(parts)
        out[path] = paragraphs
    return out


def king_print_urls(path: str) -> list[str]:
    """The listing addresses a page's print sentences link, in order, as
    the copy names them (empty for a page with none)."""
    text: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))["kingPrints"]
    return [
        LISTING_URL.format(listing=part["listing"])
        for key in KING_PRINT_PAGES.get(path, ())
        for part in text["lines"][key]
        if not isinstance(part, str)
    ]
