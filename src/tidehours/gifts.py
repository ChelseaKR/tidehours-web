"""The tide gifts page (docs/DECISIONS.md 0041), at `tide-gifts/`: every Tide
Hours product this build links to, by kind and, within a kind, by town.

Two kinds come from the lists the station pages already use: the printable
calendars (`copy/calendars.json`, 0035) and posters (`copy/posters.json`,
0037), exactly as the station pages of this build show them. The rest come
from `copy/gifts.json`: tide rings art prints and tide blanket patterns (one
town each), moon phase calendars (no town) and printed tide tables on Amazon
(one or more towns). Every entry there carries `live`, the date its listing
was marked live; an entry without one stops the build, so a draft cannot be
linked. The custom tide chart print is the print shop's own (0029): its
section shows only when the shop address is set, and links to the shop.

Every link to Etsy or Amazon is plain, as on the station pages: exactly
`https://www.etsy.com/listing/ID` or `https://www.amazon.com/dp/ASIN`,
`rel="noopener"`, no slug, query string, tag or click event. No price,
image, rating or claim, and no JSON-LD: nothing on this site is marked up
as a product or an offer (0034). An entry leaves the page when its year is
over by the build's date (UTC), as the calendars leave theirs; a town-bound
entry shows only when its station has a page in the build. A build in which
no entry of copy/gifts.json shows has no page and no footer link: the
calendars, posters and custom print are listed elsewhere already.

The privacy page's words about the Etsy and Amazon links are composed here
when the page links to them (`shop_notice`, `book_notice`).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import printables
from .booklets import CLAIMS, STATION_ID, valid_asin
from .booklets import TITLE_PATTERN as BOOK_TITLE
from .booklets import URL_PREFIX as AMAZON_PREFIX
from .calendars import REL, Calendar, valid_listing
from .calendars import URL_PREFIX as ETSY_PREFIX
from .catalog import STATE_NAMES, Station
from .posters import Poster

PATH = "tide-gifts/"
LIST = Path(__file__).parent / "copy" / "gifts.json"
COPY = Path(__file__).parent / "copy" / "gifts_page.json"
# The order of the sections on the page.
ORDER = ("custom", "daylight", "rings", "posters", "calendars", "blanket", "book", "moon")
# The zone an entry's `until` date is read in: the shop's own.
UNTIL_ZONE = ZoneInfo("America/Los_Angeles")
# The kinds copy/gifts.json may list, with the keys an entry has and the
# shape of its title. A title cannot carry a price or a claim.
_PLACE = r"[A-Z][A-Za-z.' -]{0,38}[A-Za-z.]"
TITLES = {
    "rings": re.compile(rf"(20[0-9]{{2}}) Tide Rings: {_PLACE}"),
    "blanket": re.compile(rf"(20[0-9]{{2}}) Tide Blanket Pattern: {_PLACE}"),
    "moon": re.compile(r"(20[0-9]{2}) Moon Phase (?:Poster|Calendar): [A-Z][A-Za-z ]{0,38}[a-z]"),
    "book": BOOK_TITLE,
    "daylight": re.compile(r"(20[0-9]{2}) Winter Solstice Print: The Light Returns"),
}
KEYS = {
    "rings": {"kind", "listing", "year", "title", "station", "live"},
    "blanket": {"kind", "listing", "year", "title", "station", "live"},
    "moon": {"kind", "listing", "year", "title", "live"},
    "book": {"kind", "asin", "year", "title", "format", "towns", "live"},
    "daylight": {"kind", "listing", "year", "title", "live", "until"},
}
# Every kind may carry `until`: the first day, in UNTIL_ZONE, on which the
# entry no longer shows. A made-to-order seasonal print must carry one.
OPTIONAL = {"until"}
FORMATS = ("hardcover", "paperback")
TOWN_NAME = re.compile(_PLACE)
LIVE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")
COUNTS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


@dataclass(frozen=True)
class Gift:
    """One entry of copy/gifts.json."""

    kind: str
    ref: str  # the Etsy listing id, or the book's ASIN
    year: int
    title: str
    live: dt.date  # the day its listing was marked live
    station: str | None = None  # rings and blanket: the town's station
    towns: tuple[tuple[str, str], ...] = ()  # book: (name, station id), in the book's order
    format: str | None = None  # book: hardcover or paperback
    until: dt.date | None = None  # the first day (UNTIL_ZONE) it no longer shows

    @property
    def url(self) -> str:
        """The listing's or the book's own page, with nothing after the id."""
        return (AMAZON_PREFIX if self.kind == "book" else ETSY_PREFIX) + self.ref

    @property
    def store(self) -> str:
        return "Amazon" if self.kind == "book" else "Etsy"


def _gift(n: int, entry: Any) -> Gift:
    where = f"entry {n + 1}"
    if not isinstance(entry, dict) or entry.get("kind") not in KEYS:
        raise ValueError(f"{where}: kind is one of {', '.join(sorted(KEYS))}")
    kind = entry["kind"]
    if not KEYS[kind] <= set(entry) <= KEYS[kind] | OPTIONAL:
        raise ValueError(f"{where}: a {kind} entry has exactly {', '.join(sorted(KEYS[kind]))}")
    live_on = _date(where, "live", entry["live"])
    until = _date(where, "until", entry["until"]) if "until" in entry else None
    if until is not None and until <= live_on:
        raise ValueError(f"{where}: until {until} is not after live {live_on}")
    year, title = entry["year"], entry["title"]
    if type(year) is not int or not 2000 <= year <= 2099:
        raise ValueError(f"{where}: {year!r} is not a year")
    named = TITLES[kind].fullmatch(title) if isinstance(title, str) else None
    if named is None or named.group(1) != str(year) or CLAIMS.search(title):
        raise ValueError(f"{where}: {title!r} is not a {kind} title for {year}")
    if kind == "book":
        return _book(where, entry, year, title, live_on, until)
    listing = entry["listing"]
    if not isinstance(listing, str) or not valid_listing(listing):
        raise ValueError(f"{where}: {listing!r} is not an Etsy listing id")
    station = entry.get("station")
    if kind in ("rings", "blanket") and (not isinstance(station, str) or STATION_ID.fullmatch(station) is None):
        raise ValueError(f"{where}: {station!r} is not a station id")
    return Gift(kind, listing, year, title, live_on, station, until=until)


def _date(where: str, key: str, value: Any) -> dt.date:
    """`live`, the date the listing was marked live, or `until`: a date
    written YYYY-MM-DD and nothing else."""
    if not isinstance(value, str) or LIVE.fullmatch(value) is None:
        raise ValueError(f"{where}: {key} is a date like 2026-11-14, not {value!r}")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as err:
        raise ValueError(f"{where}: {key} is not a date: {value!r}") from err


def _book(where: str, entry: dict[str, Any], year: int, title: str, live: dt.date, until: dt.date | None) -> Gift:
    asin, fmt, towns = entry["asin"], entry["format"], entry["towns"]
    if not isinstance(asin, str) or not valid_asin(asin):
        raise ValueError(f"{where}: {asin!r} is not an ASIN")
    if fmt not in FORMATS:
        raise ValueError(f"{where}: format is {' or '.join(FORMATS)}, not {fmt!r}")
    ok = isinstance(towns, list) and 1 <= len(towns) <= len(COUNTS)
    pairs: list[tuple[str, str]] = []
    for town in towns if ok else []:
        if not (isinstance(town, list) and len(town) == 2 and all(isinstance(x, str) for x in town)):
            ok = False
            break
        name, station = town
        if TOWN_NAME.fullmatch(name) is None or STATION_ID.fullmatch(station) is None:
            ok = False
            break
        pairs.append((name, station))
    if not ok or len({s for _, s in pairs}) != len(pairs):
        raise ValueError(f"{where}: towns is a list of one to twelve [name, station id] pairs, each station once")
    return Gift("book", asin, year, title, live, None, tuple(pairs), fmt, until)


def load(path: Path | None = None) -> list[Gift]:
    """The entries of the committed list (or `path`, for tests). An entry
    that is not exactly one of the kinds above, with its listing id or
    ASIN, year, title and the date it was marked live, is refused, and so
    is one listing or ASIN listed twice."""
    source = path or LIST
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"gifts"} or not isinstance(raw["gifts"], list):
        raise ValueError(f'{source.name}: expected {{"gifts": [...]}}')
    out = [_gift(n, entry) for n, entry in enumerate(raw["gifts"])]
    refs = [g.ref for g in out]
    if len(refs) != len(set(refs)):
        raise ValueError(f"{source.name}: one listing is listed twice")
    if sum(g.kind == "daylight" for g in out) > 1:
        raise ValueError(f"{source.name}: at most one solstice print, whose dates the section names")
    return out


def until_day(now: dt.datetime) -> dt.date:
    """The day an entry's `until` is compared with: the build's date in
    UNTIL_ZONE."""
    return now.astimezone(UNTIL_ZONE).date()


def shown(gift: Gift, built: dt.date, today: dt.date | None = None) -> bool:
    """Whether the entry shows in a build of `built` (UTC): until its year
    is over, and, for an entry with `until`, while `today` (the build's
    date in UNTIL_ZONE; `built` when not given) is before it."""
    if gift.year < built.year:
        return False
    return gift.until is None or (today or built) < gift.until


@dataclass(frozen=True)
class Entry:
    """One line of a section: an optional town (its name, its station
    page and its state), the link to the gift, and, for a book, the towns
    it covers."""

    key: str  # data-gift: the listing id or ASIN
    title: str
    url: str
    town: str | None = None
    town_path: str | None = None
    state: str | None = None
    tail: str = ""
    towns: tuple[tuple[str, str | None, str], ...] = ()  # (name, station page or None, text after it)


@dataclass(frozen=True)
class Section:
    key: str
    heading: str
    text: str
    entries: tuple[Entry, ...] = ()
    link: dict[str, str] | None = None  # the custom print's shop link


def links_of(entry: Entry) -> list[tuple[str, str]]:
    """Every link of an entry's line, in order, as (address, text)."""
    out = [(f"/{entry.town_path}", entry.town)] if entry.town and entry.town_path else []
    out.append((entry.url, entry.title))
    out += [(f"/{path}", name) for name, path, _ in entry.towns if path]
    return out


def _copy() -> dict[str, Any]:
    text: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))
    return text


def _one_year(years: set[int], text: str) -> str:
    """The copy with its year, or no year when the entries are of more than
    one year."""
    return text.replace("{year} ", f"{years.pop()} " if len(years) == 1 else "")


def _join(parts: list[str]) -> str:
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _town_entry(key: str, title: str, url: str, station: Station) -> Entry:
    return Entry(
        key,
        title,
        url,
        printables.place(title),
        f"stations/{station.id}/",
        STATE_NAMES.get(station.state) if station.state else None,
    )


def _by_town(entries: list[Entry]) -> tuple[Entry, ...]:
    return tuple(sorted(entries, key=lambda e: ((e.town or "").lower(), e.key)))


def _book_entry(gift: Gift, stations: Mapping[str, Station], copy: dict[str, str]) -> Entry:
    item = copy["item" if len(gift.towns) > 1 else "itemOne"]
    names = [name for name, _ in gift.towns]
    towns: list[tuple[str, str | None, str]] = []
    for n, (name, station) in enumerate(gift.towns):
        after = "." if n == len(names) - 1 else " and " if n == len(names) - 2 else ", "
        towns.append((name, f"stations/{station}/" if station in stations else None, after))
    tail = (
        item.replace("{format}", gift.format or "")
        .replace("{year}", str(gift.year))
        .replace("{count}", COUNTS[len(names) - 1])
    )
    return Entry(gift.ref, gift.title, gift.url, tail=tail, towns=tuple(towns))


def _daylight_years(text: str, years: set[int]) -> str:
    """The solstice print's sentence with its solstice's year and the next
    (load refuses a second solstice print, so there is one year)."""
    year = min(years)
    return text.replace("{year}", str(year)).replace("{next}", str(year + 1))


def sections(
    calendar_of: Mapping[str, Calendar],
    poster_of: Mapping[str, Poster],
    listed: list[Gift],
    stations: Mapping[str, Station],
    print_shop: dict[str, Any] | None,
) -> list[Section]:
    """The page's sections, in ORDER, each with at least one entry.
    `calendar_of` and `poster_of` are the links this build's station pages
    show (station id -> calendar or poster); `listed` is the entries of
    copy/gifts.json that show in this build (`shown`, and a town-bound one
    only with its station in `stations`, the build's stations by id)."""
    text = _copy()["sections"]
    found: dict[str, tuple[set[int], list[Entry]]] = {}

    def add(kind: str, year: int, entry: Entry) -> None:
        years, entries = found.setdefault(kind, (set(), []))
        years.add(year)
        entries.append(entry)

    for sid, c in calendar_of.items():
        add("calendars", c.year, _town_entry(c.listing, c.title, c.url, stations[sid]))
    for sid, p in poster_of.items():
        add("posters", p.year, _town_entry(p.listing, p.title, p.url, stations[sid]))
    for g in listed:
        if g.kind == "book":
            add("book", g.year, _book_entry(g, stations, text["book"]))
        elif g.kind in ("moon", "daylight"):
            add(g.kind, g.year, Entry(g.ref, g.title, g.url))
        elif g.station is not None and g.station in stations:
            add(g.kind, g.year, _town_entry(g.ref, g.title, g.url, stations[g.station]))
    out: list[Section] = []
    for key in ORDER:
        copy = text[key]
        if key == "custom":
            if print_shop is not None:
                link = {
                    "url": print_shop["url"],
                    "rel": print_shop["rel"],
                    "text": copy["link"],
                    "after": copy["after"],
                }
                out.append(Section(key, copy["heading"], copy["text"], link=link))
            continue
        if key not in found:
            continue
        years, entries = found[key]
        ordered = _by_town(entries) if key not in ("moon", "book", "daylight") else tuple(entries)
        text_ = _daylight_years(copy["text"], years) if key == "daylight" else copy["text"]
        out.append(Section(key, _one_year(set(years), copy["heading"]), _one_year(set(years), text_), ordered))
    return out


def stores(secs: list[Section]) -> list[str]:
    """The stores the page links to: Etsy, Amazon, or both."""
    keys = {s.key for s in secs}
    return [name for name, has in (("Etsy", bool(keys - {"book"})), ("Amazon", "book" in keys)) if has]


def block(
    calendar_of: Mapping[str, Calendar],
    poster_of: Mapping[str, Poster],
    listed: list[Gift],
    stations: Mapping[str, Station],
    print_shop: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """What the page's template needs, or None when no entry of
    copy/gifts.json shows in this build. The calendars, posters and custom
    print alone do not make a page: tide-calendars/ (0037) and the print
    shop's own link (0029) already list them."""
    secs = sections(calendar_of, poster_of, listed, stations, print_shop)
    if not any(s.key in {g.kind for g in listed} for s in secs):
        return None
    text = _copy()
    years: set[int] = {c.year for c in calendar_of.values()}
    kinds = [_one_year(set(years), text["sections"][s.key]["short"]) for s in secs]
    art = any(s.key in ("custom", "daylight", "rings", "posters") for s in secs)
    title = text["titleArt" if art else "title"]
    return {
        "rel": REL,
        "sections": secs,
        "title": title,
        "heading": title,
        "description": text["description"].replace("{kinds}", _join(kinds)),
        "intro": text["intro"],
        "how": text["how"].replace("{stores}", " or ".join(stores(secs))),
    }


def link(listing: dict[str, Any] | None) -> dict[str, str] | None:
    """The footer's link to the page, or None when the build has no page."""
    if listing is None:
        return None
    return {"path": PATH, "label": _copy()["footer"]}


def has_etsy(listing: dict[str, Any] | None) -> bool:
    return listing is not None and "Etsy" in stores(listing["sections"])


def has_books(listing: dict[str, Any] | None) -> bool:
    return listing is not None and "Amazon" in stores(listing["sections"])


def shop_notice(which: str | None, print_shop: dict[str, Any] | None, gift_etsy: bool) -> dict[str, str] | None:
    """The privacy page's words about the links to Etsy. Without an Etsy
    link on this page, printables.notice's, unchanged (0029, 0035, 0037);
    with one, a sentence that names this page among the pages that link to
    Etsy. `which` is printables.kind's value."""
    if not gift_etsy:
        return printables.notice(which, print_shop)
    text = _copy()
    plural = one = ""
    if which is not None:
        words = json.loads(printables.COPY.read_text(encoding="utf-8"))["kinds"][which]
        plural, one = words["plural"], words["one"]
    places = [
        *(["the About and king tides pages"] if print_shop else []),
        *([f"the tide {plural} page"] if which else []),
        "the tide gifts page",
        *([f"the station pages of towns with a printable {one}"] if which else []),
    ]
    joined = places[0] if len(places) == 1 else _join(places) if len(places) == 2 else ", ".join(places[:-1])
    if len(places) > 2:
        joined += ", and " + places[-1] + ","
    body = (
        text["privacyShop"]
        .replace("{places}", joined[0].upper() + joined[1:])
        .replace("{verb}", "links to" if len(places) == 1 else "link to")
        .replace("{target}", "the Tide Hours shop on Etsy" if print_shop else "listings in the Tide Hours shop on Etsy")
    )
    heading = json.loads(printables.COPY.read_text(encoding="utf-8"))["privacyHeading"]
    return {"heading": heading, "body": body}


def book_notice(booklet_links: dict[str, str] | None, gift_books: bool) -> dict[str, str] | None:
    """The privacy page's words about the links to Amazon books: the
    booklet sentence (0030) unchanged when only station pages link to one;
    otherwise one that names this page."""
    if not gift_books:
        return booklet_links
    text = _copy()
    body = text["privacyBooksAndBooklets" if booklet_links else "privacyBooks"]
    return {"heading": text["privacyBooksHeading"], "body": body}
