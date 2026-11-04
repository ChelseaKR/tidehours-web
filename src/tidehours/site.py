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
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import numpy as np
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from . import indexnow, kingtides, ktformat
from .catalog import DATA_DIR, Catalog, Station
from .days import Day, feet, local_today, long_date, short_date, station_day
from .engine import Offsets

DEFAULT_BASE_URL = "https://tidehours.com/"
# Analytics regions where analytics_storage defaults to denied (EEA, UK, CH),
# as on the portfolio's other sites.
GA4_DENIED_REGIONS = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "LV",
    "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH",
]  # fmt: skip

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AS": "American Samoa", "CA": "California", "CT": "Connecticut",
    "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "GU": "Guam",
    "HI": "Hawaii", "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine",
    "MS": "Mississippi", "NC": "North Carolina", "NH": "New Hampshire", "NJ": "New Jersey", "NY": "New York",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island", "SC": "South Carolina",
    "TX": "Texas", "VA": "Virginia", "VI": "U.S. Virgin Islands", "WA": "Washington",
}  # fmt: skip
OTHER = "other"
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


@dataclass
class Config:
    base_url: str = DEFAULT_BASE_URL
    ga4_measurement_id: str = ""
    app_store_url: str = ""
    states: set[str] | None = None  # None builds every state


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
                r = regions[s.region] = Region(code, s.region, slug(s.region))
            r.stations.append(s)
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
        fill=ktformat.fill,
        fmt_date=ktformat.fmt_date,
        fmt_long_date=ktformat.fmt_long_date,
        fmt_range=ktformat.fmt_range,
        fmt_time=ktformat.fmt_time,
        fmt_feet=ktformat.fmt_feet,
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
        "copy": copy,
    }


def next_series(season: kingtides.StationSeason, today: dt.date) -> list[kingtides.Day] | None:
    for series in season.series:
        if dt.date.fromisoformat(series[-1].date) >= today:
            return series
    return None


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
    base = cfg.base_url if cfg.base_url.endswith("/") else cfg.base_url + "/"
    common: dict[str, Any] = {
        "ui": {lang: kt["copy"][lang]["chrome"] for lang in ("en", "es")},
        "base_url": base,
        "ga4_measurement_id": cfg.ga4_measurement_id,
        "ga4_denied_regions": GA4_DENIED_REGIONS,
        "app_store_url": cfg.app_store_url,
        "retrieved": cat.retrieved,
        "built": now.astimezone(dt.UTC).date().isoformat(),
        "station_count": len(cat.stations),
    }
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

    page("", "index.html.jinja", states=states, partial=cfg.states is not None)
    page("about/", "about.html.jinja")
    page("privacy/", "privacy.html.jinja")
    page("terms/", "terms.html.jinja")
    for lang in ("en", "es"):
        page(
            "king-tides/" if lang == "en" else "es/king-tides/",
            "king_tides.html.jinja",
            lang=lang,
            c=kt["copy"][lang],
            **kt,
        )
    for st in states:
        page(st.path, "state.html.jinja", state=st)
        for r in st.regions:
            page(r.path, "region.html.jinja", state=st, region=r)
    for s in stations:
        today = local_today(s, now)
        p = cat.predictor(s.id)
        days: list[Day] = [
            station_day(s, p, today, "Today"),
            station_day(s, p, today + dt.timedelta(days=1), "Tomorrow"),
        ]
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
            king_season=season,
            king_next=next_series(season, today) if season else None,
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
