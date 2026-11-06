"""Renders the static site: a page per station (today and tomorrow), state
and region indexes, the king-tide pages, about, privacy, terms, 404, sitemap and
robots.txt. Every number on a page is computed at build time from NOAA's
constants (docs/DECISIONS.md 0002); nothing is fetched while building."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import shutil
import string
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import numpy as np
from jinja2 import Environment, PackageLoader, StrictUndefined, Template, select_autoescape

from . import affiliate, indexnow, kingtides, ktformat
from .catalog import DATA_DIR, STATE_NAMES, Catalog, Station, tidy_name
from .days import Day, feet, local_today, long_date, short_date, station_day
from .engine import Offsets
from .zones import UNKNOWN as ZONE_UNKNOWN
from .zones import label as zone_label

DEFAULT_BASE_URL = "https://tidehours.com/"
# Analytics regions where analytics_storage defaults to denied (EEA, UK, CH),
# as on the portfolio's other sites.
GA4_DENIED_REGIONS = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "LV",
    "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH",
]  # fmt: skip

OTHER = "other"
# Region pages that moved (docs/DECISIONS.md 0017): the old path is built as a
# noindex stub, out of the sitemap, that sends visitors to the new page. The
# site is static files on S3 behind CloudFront, with no redirect rules.
MOVED_REGIONS = {
    "states/pr/st-croix-island/": "states/vi/st-croix-island/",
    "states/pr/st-johns-island/": "states/vi/st-johns-island/",
    "states/pr/st-thomas-island/": "states/vi/st-thomas-island/",
}
OTHER_NAME = "Stations without a state"


def indexable(station: Station) -> bool:
    """Whether a station's page asks search engines to index it.

    Harmonic stations are indexed. A subordinate station's highs and lows are
    its reference station's, moved by fixed minutes and scaled, so its page is
    a near-copy of another page on this site; it is served, linked and
    followed, but carries ``noindex`` and is left out of the sitemap (and so of
    IndexNow) until the site has earned some trust (docs/DECISIONS.md 0013)."""
    return not station.is_subordinate


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "region"


# A station page's <title> (and og:title): the longest of these that fits in
# TITLE_MAX characters, else the shortest (docs/DECISIONS.md 0020).
TITLE_MAX = 60
TITLE_TIERS = ("{} tide times today | Tide Hours", "{} tide times today", "{} tide times")


def station_title(name: str) -> str:
    for tier in TITLE_TIERS:
        title = tier.format(name)
        if len(title) <= TITLE_MAX:
            return title
    return title


# NOAA's region names with typos or case slips, written right
# (docs/DECISIONS.md 0020). The region's URL keeps NOAA's name.
REGION_FIXES = {
    "Hawaiin Islands": "Hawaiian Islands",
    "St. Johns Island": "St. John Island",
    "Chesapeake Bay, western shore": "Chesapeake Bay, Western Shore",
}
REGION_SUFFIXES = ("-cont.", ", etc.")


def region_label(region: str, state_name: str | None) -> str:
    """How a region's name reads on the site: NOAA's typos fixed, out of
    capitals ("MAINE and NEW HAMPSHIRE" -> "Maine and New Hampshire"),
    without NOAA's page-break "-cont." or ", etc.", and without a leading
    "STATE, " part on that state's own pages ("FLORIDA, East Coast" -> "East
    Coast"). The region's page and URL are NOAA's region, unchanged."""
    label = tidy_name(REGION_FIXES.get(region, region))
    for suffix in REGION_SUFFIXES:
        label = label.removesuffix(suffix)
    head, sep, rest = label.partition(",")
    if sep and state_name and head.strip().lower() == state_name.lower():
        rest = rest.strip()
        label = string.capwords(rest) if rest == rest.lower() else rest[:1].upper() + rest[1:]
    return label


def tell_apart(code: str, regions: list[Region]) -> None:
    """Give two regions of one state that `region_label` names alike their
    own labels (docs/DECISIONS.md 0023). NOAA splits a region across a page
    break ("MAINE, outer coast" and "MAINE, outer coast-cont."), so its own
    detail is only "continued"; the parts are told apart by where NOAA puts
    their stations, "(north)" and "(south)", as NOAA writes "(inside)" and
    "(outside)". That holds only when every station of one part is north of
    every station of the other; anything else stops the build."""
    by_label: dict[str, list[Region]] = defaultdict(list)
    for r in regions:
        by_label[r.name].append(r)
    for label, same in by_label.items():
        if len(same) == 1:
            continue
        if len(same) > 2:
            raise ValueError(f"{code}: {len(same)} regions are labeled {label!r}")
        south, north = sorted(same, key=lambda r: min(s.lat for s in r.stations))
        if max(s.lat for s in south.stations) >= min(s.lat for s in north.stations):
            raise ValueError(f"{code}: the two {label!r} regions overlap north to south")
        south.name, north.name = f"{label} (south)", f"{label} (north)"


@dataclass
class Config:
    base_url: str = DEFAULT_BASE_URL
    ga4_measurement_id: str = ""
    app_store_url: str = ""
    states: set[str] | None = None  # None builds every state
    # Amazon Associates tracking ID. Empty (the default) means off: no
    # affiliate link anywhere (docs/DECISIONS.md 0016).
    amazon_tag: str = ""


@dataclass
class Region:
    state: str
    name: str
    slug: str
    stations: list[Station] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"states/{self.state.lower()}/{self.slug}/"


@dataclass
class State:
    code: str
    name: str
    regions: list[Region]
    unregioned: list[Station]

    @property
    def path(self) -> str:
        return f"states/{self.code.lower()}/"

    @property
    def count(self) -> int:
        return sum(len(r.stations) for r in self.regions) + len(self.unregioned)


def group(stations: list[Station]) -> list[State]:
    by_state: dict[str, list[Station]] = defaultdict(list)
    for s in stations:
        by_state[s.state or OTHER].append(s)
    out: list[State] = []
    for code in sorted(by_state, key=lambda c: (c == OTHER, STATE_NAMES.get(c, c))):
        regions: dict[str, Region] = {}
        unregioned: list[Station] = []
        for s in sorted(by_state[code], key=lambda s: s.name.lower()):
            if s.region is None:
                unregioned.append(s)
                continue
            r = regions.get(s.region)
            if r is None:
                r = regions[s.region] = Region(code, region_label(s.region, STATE_NAMES.get(code)), slug(s.region))
            r.stations.append(s)
        tell_apart(code, list(regions.values()))
        slugs = [r.slug for r in regions.values()]
        if len(slugs) != len(set(slugs)):
            raise ValueError(f"{code}: two regions share a URL slug")
        name = OTHER_NAME if code == OTHER else STATE_NAMES.get(code)
        if name is None:
            raise ValueError(f"no name for state code {code!r}")
        out.append(State(code, name, sorted(regions.values(), key=lambda r: r.name.lower()), unregioned))
    return out


def distance_km(a: Station, b: Station) -> float:
    la1, la2 = math.radians(a.lat), math.radians(b.lat)
    dla, dlo = la2 - la1, math.radians(b.lon - a.lon)
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, h)))


def nearby(station: Station, pool: list[Station], n: int = 6) -> list[tuple[Station, float]]:
    near = sorted(((s, distance_km(station, s)) for s in pool if s.id != station.id), key=lambda x: (x[1], x[0].id))
    return near[:n]


class Nearby:
    """nearby() for every station at once, vectorized: the same haversine."""

    def __init__(self, pool: list[Station]) -> None:
        self.pool = pool
        self.lat = np.radians(np.array([s.lat for s in pool]))
        self.lon = np.radians(np.array([s.lon for s in pool]))

    def __call__(self, station: Station, n: int = 6) -> list[tuple[Station, float]]:
        la1, lo1 = math.radians(station.lat), math.radians(station.lon)
        h = np.sin((self.lat - la1) / 2) ** 2 + math.cos(la1) * np.cos(self.lat) * np.sin((self.lon - lo1) / 2) ** 2
        km = 6371.0 * 2 * np.arcsin(np.sqrt(np.minimum(1.0, h)))
        order = np.lexsort((np.array([s.id for s in self.pool]), km))
        out: list[tuple[Station, float]] = []
        for i in order:
            if self.pool[i].id != station.id:
                out.append((self.pool[i], float(km[i])))
            if len(out) == n:
                break
        return out


def offset_phrase(minutes: float) -> str:
    """A subordinate station's published time correction, in words."""
    m = round(minutes)
    if m == 0:
        return "at the same time"
    h, rest = divmod(abs(m), 60)
    span = f"{h} h {rest} min" if h and rest else f"{h} h" if h else f"{rest} min"
    return f"{span} {'later' if m > 0 else 'earlier'}"


def env() -> Environment:
    e = Environment(
        loader=PackageLoader("tidehours", "templates"),
        autoescape=select_autoescape(["html", "xml", "jinja"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    e.filters["feet"] = feet
    e.filters["short_date"] = short_date
    e.filters["long_date"] = long_date
    e.filters["short_date_iso"] = lambda iso: short_date(dt.date.fromisoformat(iso))
    e.globals.update(
        minutes=offset_phrase,
        station_title=station_title,
        fill=ktformat.fill,
        fmt_date=ktformat.fmt_date,
        fmt_long_date=ktformat.fmt_long_date,
        fmt_range=ktformat.fmt_range,
        fmt_time=ktformat.fmt_time,
        fmt_feet=ktformat.fmt_feet,
        fmt_months=ktformat.fmt_months,
        calendar_path=kingtides.calendar_path,
        zone_label=zone_label,
        zone_unknown=ZONE_UNKNOWN,
    )
    return e


@dataclass
class Page:
    path: str  # "" for home, "stations/9414290/" etc.
    html: str
    index: bool = True  # False: served with noindex, not in the sitemap or lastmod.json


@dataclass(frozen=True)
class Derived:
    """A subordinate station predicted from the page's station."""

    station: Station
    offsets: Offsets
    km: float


def king_tide_context(cat: Catalog) -> dict[str, Any]:
    datums_raw = json.loads((DATA_DIR / "datums.json").read_text(encoding="utf-8"))
    datums = {k: float(v["mhhwAboveMllwFt"]) for k, v in datums_raw["datums"].items()}
    seasons = kingtides.season(cat, datums)
    first, last = kingtides.window()
    copy = json.loads((Path(__file__).parent / "copy" / "king_tides.json").read_text(encoding="utf-8"))
    return {
        "seasons": seasons,
        "window_start": first,
        "window_end": last,
        "datums_retrieved": datums_raw["retrieved"],
        "datum_epochs": {k: str(v.get("epoch", "")) for k, v in datums_raw["datums"].items()},
        "copy": copy,
    }


@dataclass(frozen=True)
class KingSpan:
    """The runs coming up in one state (or all three): first and last day,
    and the first and last day a station peaks."""

    first: str
    last: str
    peak_first: str
    peak_last: str


def king_span(runs: list[kingtides.Upcoming]) -> KingSpan | None:
    if not runs:
        return None
    peaks = [u.peak.date for u in runs]
    return KingSpan(min(u.first for u in runs), max(u.last for u in runs), min(peaks), max(peaks))


@dataclass(frozen=True)
class KingLink:
    """A station page's link to the king-tide page while a run is coming up:
    the station's own run, or the nearest king-tide station's within
    kingtides.NEAR_KM (docs/DECISIONS.md 0015)."""

    up: kingtides.Upcoming
    km: float  # 0 for the station itself

    @property
    def own(self) -> bool:
        return self.km == 0


def king_links(
    stations: list[Station], seasons: list[kingtides.StationSeason], today: dt.date, cat: Catalog
) -> dict[str, KingLink]:
    """Station id -> its king-tide link, for WA, OR and CA stations: a
    king-tide station's own run, or for any other station the nearest
    king-tide station's within kingtides.NEAR_KM, while that run is coming
    up. Out of season, empty."""
    listed: list[tuple[Station, kingtides.StationSeason]] = []
    for k in seasons:
        st = cat.station(k.id)
        if st is None:
            raise ValueError(f"king tides: {k.id} is not in the catalog")
        listed.append((st, k))
    ids = {st.id for st, _ in listed}
    out: dict[str, KingLink] = {}
    for s in stations:
        if s.state not in ("WA", "OR", "CA"):
            continue
        if s.id in ids:
            season, km = next(k for st, k in listed if st.id == s.id), 0.0
        else:
            km, sid = min((distance_km(s, st), st.id) for st, _ in listed)
            if km > kingtides.NEAR_KM:
                continue
            season = next(k for st, k in listed if st.id == sid)
        up = kingtides.upcoming(season, today)
        if up is not None:
            out[s.id] = KingLink(up, km)
    return out


def king_calendar_pages(
    page: Callable[..., None], kt: dict[str, Any], states: list[State], king_common: dict[str, Any]
) -> None:
    """The WA, OR and CA winter calendar pages (docs/DECISIONS.md 0024)."""
    state_paths = {st.code: st.path for st in states}
    for code, (name, _) in kingtides.CALENDAR_STATES.items():
        page(
            kingtides.calendar_path(code),
            "king_tides_state.html.jinja",
            state_code=code,
            state_name=name,
            state_path=state_paths.get(code),
            calendar=kingtides.calendar(kt["seasons"], code),
            kt_station_count=sum(1 for k in kt["seasons"] if k.state == code),
            epochs=kingtides.epochs(kt["seasons"], kt["datum_epochs"], code),
            calendar_first=kingtides.CALENDAR_FIRST,
            calendar_last=kingtides.CALENDAR_LAST,
            calendar_states=kingtides.CALENDAR_STATES,
            **king_common,
        )


def king_calendar(season: kingtides.StationSeason | None, link: KingLink | None) -> tuple[str, str] | None:
    """The winter calendar page a station page links to, (path, state name):
    its own state's, for a king-tide station, or the nearby king-tide
    station's while that station's run is coming up."""
    state = season.state if season is not None else link.up.season.state if link is not None else None
    if state is None:
        return None
    return kingtides.calendar_path(state), kingtides.CALENDAR_STATES[state][0]


def derived_from(cat: Catalog, by_id: dict[str, Station]) -> dict[str, list[Derived]]:
    """Reference station id -> the built subordinate stations predicted from
    it, nearest first."""
    out: dict[str, list[Derived]] = defaultdict(list)
    for s in by_id.values():
        if s.reference_id is not None and s.reference_id in by_id:
            out[s.reference_id].append(Derived(s, cat.offsets(s.id), distance_km(by_id[s.reference_id], s)))
    for subs in out.values():
        subs.sort(key=lambda d: (d.km, d.station.id))
    return out


def region_king(region: Region, links: dict[str, KingLink], up: list[kingtides.Upcoming]) -> list[kingtides.Upcoming]:
    """The runs coming up that the region's station pages link to, in the
    king-tide page's order."""
    ids = {links[s.id].up.season.id for s in region.stations if s.id in links}
    return [u for u in up if u.season.id in ids]


def moved_regions(states: list[State]) -> dict[str, dict[str, list[Station]]]:
    """Old region path -> each new region path its stations went to, with
    those stations: MOVED_REGIONS, plus each region page whose stations are
    now filed under another state or region (DECISIONS 0018), from NOAA's own
    state and region for each station. An old region can split: NOAA's
    "Hawaiin Islands" is now Johnston Atoll and Midway Islands."""
    moves: dict[str, dict[str, list[Station]]] = defaultdict(lambda: defaultdict(list))
    for st in states:
        for r in st.regions:
            for s in r.stations:
                if s.noaa_region is None:
                    continue
                old = f"states/{(s.noaa_state or OTHER).lower()}/{slug(s.noaa_region)}/"
                if old != r.path:
                    moves[old][r.path].append(s)
    for old, new in MOVED_REGIONS.items():
        moves[old].setdefault(new, [])
    return {old: dict(sorted(news.items())) for old, news in sorted(moves.items())}


def moved_pages(template: Template, common: dict[str, Any], states: list[State]) -> list[Page]:
    """A noindex stub at each moved region page's old path, when this build
    has no page there. A region that moved whole sends visitors to its new
    page; one that split lists each new page and the stations it holds,
    instead of picking one of them."""
    regions = {r.path: (r, st) for st in states for r in st.regions}
    pages: list[Page] = []
    for old, news in moved_regions(states).items():
        built = [(regions[new][0], regions[new][1], stations) for new, stations in news.items() if new in regions]
        if old in regions or not built:
            continue
        if len(news) == 1:
            name = built[0][0].name
        else:
            first = next(s for ss in news.values() for s in ss)
            name = region_label(first.noaa_region or "", STATE_NAMES.get(first.noaa_state))
        ctx: dict[str, Any] = {"path": old, "noindex": True, "name": name, "destinations": built}
        if len(news) == 1:
            ctx["canonical_path"] = built[0][0].path
        pages.append(Page(old, template.render(**common, **ctx), False))
    return pages


def render(cat: Catalog, cfg: Config, now: dt.datetime) -> list[Page]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    e = env()
    stations = [s for s in cat.stations if cfg.states is None or (s.state or OTHER) in cfg.states]
    if not stations:
        raise ValueError("no stations selected")
    states = group(stations)
    by_id = {s.id: s for s in stations}
    kt = king_tide_context(cat)
    kt_by_id = {s.id: s for s in kt["seasons"]}
    kt_today = kingtides.today_on_coast(now)
    kt_up = kingtides.coming_up(kt["seasons"], kt_today)
    kt_months = kingtides.months(kt_up, kt_today)
    kt_states = {code: king_span([u for u in kt_up if u.season.state == code]) for code in ("WA", "OR", "CA")}
    links = king_links(stations, kt["seasons"], kt_today, cat)
    base = cfg.base_url if cfg.base_url.endswith("/") else cfg.base_url + "/"
    common: dict[str, Any] = {
        "ui": {lang: kt["copy"][lang]["chrome"] for lang in ("en", "es")},
        "base_url": base,
        "ga4_measurement_id": cfg.ga4_measurement_id,
        "ga4_denied_regions": GA4_DENIED_REGIONS,
        "app_store_url": cfg.app_store_url,
        "amazon_links": bool(cfg.amazon_tag),
        "retrieved": cat.retrieved,
        "built": now.astimezone(dt.UTC).date().isoformat(),
        "station_count": len(cat.stations),
    }
    gear = affiliate.block(cfg.amazon_tag)
    region_of: dict[str, tuple[State, Region | None]] = {}
    for st in states:
        for r in st.regions:
            for s in r.stations:
                region_of[s.id] = (st, r)
        for s in st.unregioned:
            region_of[s.id] = (st, None)

    near = Nearby(stations)
    pages: list[Page] = []

    def page(path: str, template: str, index: bool = True, **ctx: Any) -> None:
        html = e.get_template(template).render(**common, path=path, noindex=not index, **ctx)
        pages.append(Page(path, html, index))

    derived = derived_from(cat, by_id)

    king_common: dict[str, Any] = {
        "king_today": kt_today.isoformat(),
        "king_lead": kingtides.LEAD_DAYS,
        "king_up": kt_up,
        "king_months": kt_months,
        "king_span": king_span(kt_up),
        "king_states": kt_states,
        "kc": kt["copy"]["en"],
    }
    page("", "index.html.jinja", states=states, partial=cfg.states is not None, **king_common)
    page("about/", "about.html.jinja")
    page("privacy/", "privacy.html.jinja")
    page("terms/", "terms.html.jinja")
    for lang in ("en", "es"):
        page(
            "king-tides/" if lang == "en" else "es/king-tides/",
            "king_tides.html.jinja",
            lang=lang,
            c=kt["copy"][lang],
            affiliate=gear if lang == "en" else None,
            **kt,
            **{k: v for k, v in king_common.items() if k != "kc"},
        )
    king_calendar_pages(page, kt, states, king_common)
    for st in states:
        page(
            st.path,
            "state.html.jinja",
            state=st,
            king=kt_states.get(st.code),
            king_calendar=kingtides.calendar_path_for(st.code),
            **king_common,
        )
        for r in st.regions:
            page(
                r.path, "region.html.jinja", state=st, region=r, region_king=region_king(r, links, kt_up), **king_common
            )
    pages += moved_pages(e.get_template("moved.html.jinja"), common, states)
    for s in stations:
        today = local_today(s, now)
        p = cat.predictor(s.id)
        # The station's date at build time and the next; the page's script
        # says which of them is "today" when it is read.
        days: list[Day] = [station_day(s, p, today), station_day(s, p, today + dt.timedelta(days=1))]
        st, region = region_of[s.id]
        ref = cat.station(s.reference_id) if s.reference_id else None
        season = kt_by_id.get(s.id)
        page(
            f"stations/{s.id}/",
            "station.html.jinja",
            index=indexable(s),
            station=s,
            state=st,
            region=region,
            days=days,
            reference=ref,
            reference_listed=ref is not None and ref.id in by_id,
            nearby=near(s),
            derived=derived.get(s.id, []),
            tide_type=cat.tide_type(s.id),
            king_season=season,
            king_next=kingtides.next_run(season, today) if season else None,
            king_link=links.get(s.id),
            king_calendar=king_calendar(season, links.get(s.id)),
            kc=kt["copy"]["en"],
        )
    return pages


def sitemap(pages: list[Page], base: str, built: str) -> str:
    rows = [
        f"<url><loc>{escape(base + p.path)}</loc><lastmod>{built}</lastmod></url>"
        for p in pages
        if p.path != "404" and p.index
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"
    )


def write(cat: Catalog, cfg: Config, now: dt.datetime, out: Path) -> int:
    """Builds into `out` (replaced). Returns the number of HTML pages."""
    pages = render(cat, cfg, now)
    e = env()
    base = cfg.base_url if cfg.base_url.endswith("/") else cfg.base_url + "/"
    built = now.astimezone(dt.UTC).date().isoformat()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in pages:
        target = out / p.path / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(p.html, encoding="utf-8")
    copy = json.loads((Path(__file__).parent / "copy" / "king_tides.json").read_text(encoding="utf-8"))
    common = {
        "ui": {lang: copy[lang]["chrome"] for lang in ("en", "es")},
        "base_url": base,
        "ga4_measurement_id": cfg.ga4_measurement_id,
        "ga4_denied_regions": GA4_DENIED_REGIONS,
        "app_store_url": cfg.app_store_url,
        "amazon_links": bool(cfg.amazon_tag),
        "retrieved": cat.retrieved,
        "built": built,
        "station_count": len(cat.stations),
    }
    (out / "404.html").write_text(e.get_template("404.html.jinja").render(**common, path="404"), encoding="utf-8")
    (out / "sitemap.xml").write_text(sitemap(pages, base, built), encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    shutil.copyfile(Path(__file__).parent / "templates" / "style.css", out / "style.css")
    (out / "lastmod.json").write_text(page_manifest(pages), encoding="utf-8")
    # The IndexNow ownership file (indexnow.py), served from the domain's
    # root. Public by design. Only a build for tidehours.com carries it,
    # because the key proves ownership of that one host; find_key reads the
    # templates directory, which holds exactly one such file.
    if urlsplit(base).hostname == urlsplit(DEFAULT_BASE_URL).hostname:
        indexnow.copy_key_file(Path(__file__).parent / "templates", out)
    return len(pages) + 1


def page_manifest(pages: list[Page]) -> str:
    """Each sitemap page's path and a SHA-256 of its HTML (schema 1, as read
    by indexnow.py's "manifest" kind). The sitemap's lastmod is the build date
    on every page, so it cannot tell a changed page from an unchanged one;
    this can, because a rebuild of the same day is byte-identical. The next
    build compares its manifest with the live one and announces only the pages
    whose HTML changed (docs/DECISIONS.md 0011). Noindex pages are left out,
    as they are from the sitemap (0013)."""
    entries = {
        "/" + p.path: {"fingerprint": hashlib.sha256(p.html.encode("utf-8")).hexdigest()}
        for p in pages
        if p.path != "404" and p.index
    }
    return json.dumps({"schema": 1, "pages": entries}, sort_keys=True, separators=(",", ":")) + "\n"
