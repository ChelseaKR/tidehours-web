"""The page that lists every printable calendar and poster a build links to
(docs/DECISIONS.md 0037), at `tide-calendars/`.

The page is built from the two lists the station pages use
(`copy/calendars.json`, 0035, and `copy/posters.json`, 0037) and nothing
else: each town whose station page shows a calendar or poster link in this
build, by state and then by town, with a link to that station's page and
the same plain link to each Etsy listing that the station page carries.
A build that shows no such link has no page, no footer link and no trace of
either. The words follow what the build has: calendars and posters,
calendars alone, or posters alone (`kind`).

The page's link in the footer of every English page, and the privacy
page's words about the Etsy links (`notice`), come from here too. The copy
is `copy/printables.json`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .calendars import REL, Calendar
from .catalog import STATE_NAMES, Station
from .posters import Poster

PATH = "tide-calendars/"
COPY = Path(__file__).parent / "copy" / "printables.json"
# The heading for a listed station that has no state on this site (0005).
NO_STATE = "Other places"


@dataclass(frozen=True)
class Item:
    """One calendar or poster: its title and its listing's address."""

    title: str
    url: str


@dataclass(frozen=True)
class Town:
    station_id: str
    name: str  # the place, as the calendar's or the poster's title names it
    items: tuple[Item, ...]  # the calendar first, then the poster


@dataclass(frozen=True)
class StateList:
    code: str  # "other" for a station without a state
    name: str
    towns: tuple[Town, ...]


def kind(any_calendar: bool, any_poster: bool) -> str | None:
    """Which words the build needs: "both", "calendars", "posters", or None
    when no station page shows a calendar or poster link."""
    if any_calendar and any_poster:
        return "both"
    return "calendars" if any_calendar else "posters" if any_poster else None


def place(title: str) -> str:
    """The place a title names: what follows "YEAR Tide Calendar: "."""
    return title.split(": ", 1)[1]


def states(
    calendar_of: Mapping[str, Calendar], poster_of: Mapping[str, Poster], stations: Mapping[str, Station]
) -> list[StateList]:
    """The towns to list, by state name and then by town name. `calendar_of`
    and `poster_of` are the links the station pages of this build show
    (station id -> calendar or poster); `stations` holds each of those
    stations."""
    by_state: dict[str, list[Town]] = {}
    for station_id in sorted({*calendar_of, *poster_of}):
        calendar, poster = calendar_of.get(station_id), poster_of.get(station_id)
        items = tuple(Item(x.title, x.url) for x in (calendar, poster) if x is not None)
        town = Town(station_id, place(items[0].title), items)
        by_state.setdefault(stations[station_id].state, []).append(town)
    out = [
        StateList(code.lower() or "other", STATE_NAMES.get(code, NO_STATE), tuple(sorted(towns, key=_town_order)))
        for code, towns in by_state.items()
    ]
    return sorted(out, key=lambda s: (s.code == "other", s.name))


def _town_order(town: Town) -> tuple[str, str]:
    return town.name.lower(), town.station_id


def _fill(text: str, words: dict[str, str], year: int | None) -> str:
    """The copy with this build's words in it. A build whose calendars and
    posters are not all of one year names no year."""
    for key, value in words.items():
        text = text.replace("{" + key + "}", value)
    return text.replace("{year} ", f"{year} " if year is not None else "")


def _copy(which: str) -> tuple[dict[str, Any], dict[str, str]]:
    text: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))
    words: dict[str, str] = text["kinds"][which]
    return text, words


def block(
    calendar_of: Mapping[str, Calendar], poster_of: Mapping[str, Poster], stations: Mapping[str, Station]
) -> dict[str, Any] | None:
    """What the page's template needs, or None for a build with nothing to
    list."""
    which = kind(bool(calendar_of), bool(poster_of))
    if which is None:
        return None
    text, words = _copy(which)
    years = {c.year for c in calendar_of.values()} | {p.year for p in poster_of.values()}
    year = years.pop() if len(years) == 1 else None
    return {
        "rel": REL,
        "states": states(calendar_of, poster_of, stations),
        **{key: _fill(text[key], words, year) for key in ("title", "description", "heading", "intro", "how")},
    }


def link(which: str | None) -> dict[str, str] | None:
    """The footer's link to the page, or None when the build has no page."""
    if which is None:
        return None
    text, words = _copy(which)
    return {"path": PATH, "label": _fill(text["footer"], words, None)}


def notice(which: str | None, print_shop: dict[str, Any] | None) -> dict[str, str] | None:
    """The privacy page's words about the links to Etsy, or None when the
    build has none. `which` is `kind`'s value and `print_shop` is
    printshop.block's. With no calendar or poster link shown, the print
    shop's own sentence (0029), unchanged; with one, a sentence that names
    this page and the station pages too, and the print shop's pages only
    when its link is on."""
    if which is None:
        if print_shop is None:
            return None
        return {"heading": print_shop["text"]["privacyHeading"], "body": print_shop["text"]["privacy"]}
    text, words = _copy(which)
    body = _fill(text["privacyWithShop" if print_shop else "privacy"], words, None)
    return {"heading": text["privacyHeading"], "body": body}
