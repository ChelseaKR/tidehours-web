"""schema.org JSON-LD that restates what a page shows, and nothing more
(docs/DECISIONS.md 0034).

Emitted: a ``Place`` and a ``Dataset`` on each station page, and a
``Dataset`` on the king-tide pages. The home page's ``WebSite`` and the ``BreadcrumbList``
nodes live in their templates (DECISIONS 0013's follow-up, #13).

Never emitted: ``Event``, ``Product``, ``Offer``, reviews or ratings, an
``FAQPage`` (see king_tide_nodes), a
``SearchAction`` (the site has no search), a ``license`` on Tide Hours' own
predictions (an owner decision), or NOAA as the creator of the predictions:
Tide Hours computes them and is not a NOAA product, so NOAA CO-OPS is the
creator of the source data the ``Dataset`` is based on.

``dateModified`` is never the build clock: each node carries
``DATE_MODIFIED``, a placeholder ``site.write`` replaces with the page's
sitemap ``lastmod`` after it has decided it (0028), so the two cannot differ.
"""

from __future__ import annotations

import json
import math
from typing import Any

from markupsafe import Markup

from .catalog import Station

CONTEXT = "https://schema.org"
# Replaced by the page's sitemap lastmod in site.write. The page's fingerprint
# (lastmod.json) is taken with the placeholder in place, so the date a page
# carries does not by itself make the page "changed" the next day.
DATE_MODIFIED = "TIDEHOURS-DATE-MODIFIED"

NOAA_HOME = "https://tidesandcurrents.noaa.gov/"
NOAA_PUBLIC_DOMAIN = "https://tidesandcurrents.noaa.gov/disclaimers.html"
NOAA_COOPS: dict[str, Any] = {
    "@type": "GovernmentOrganization",
    "name": "NOAA Center for Operational Oceanographic Products and Services (CO-OPS)",
    "url": NOAA_HOME,
}


# What a JSON string must not carry inside an HTML <script>: the same
# escapes as Jinja's tojson, which this replaces only to drop its spaces and
# its \u escapes of non-ASCII letters (about 10% of a node).
_HTML_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", "'": "\\u0027"}


def dumps(node: dict[str, Any]) -> Markup:
    """A node as compact JSON, safe inside <script type="application/ld+json">."""
    text = json.dumps(node, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for char, escaped in _HTML_UNSAFE.items():
        text = text.replace(char, escaped)
    return Markup(text)  # noqa: S704 - every HTML-significant character is escaped above


def noaa_station_url(station_id: str) -> str:
    """NOAA's own prediction page for a station, as the station page links it."""
    return f"https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id={station_id}"


def tide_hours(base_url: str) -> dict[str, Any]:
    return {"@type": "Organization", "name": "Tide Hours", "url": base_url}


def has_coordinates(station: Station) -> bool:
    """Whether the catalog gives the station a usable position. A missing or
    impossible one emits no Place: absence is never rendered as a value."""
    lat, lon = getattr(station, "lat", None), getattr(station, "lon", None)
    if not isinstance(lat, int | float) or not isinstance(lon, int | float):
        return False
    if isinstance(lat, bool) or isinstance(lon, bool):
        return False
    return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def place(station: Station, state_name: str | None) -> dict[str, Any] | None:
    """The station as a Place: its name, the catalog's coordinates, and the
    state it is in. `state_name` is None when the site cannot say the station
    is in a state (no state, or filed under its reference station's state,
    which says nothing about where it is)."""
    if not has_coordinates(station):
        return None
    node: dict[str, Any] = {
        "@type": "Place",
        "name": station.display_name,
        "geo": {"@type": "GeoCoordinates", "latitude": station.lat, "longitude": station.lon},
    }
    if state_name:
        node["containedInPlace"] = {"@type": "AdministrativeArea", "name": state_name}
    return node


def located_state(station: Station, state_code: str, state_name: str) -> str | None:
    """The state a Place may claim the station is in: the state the site lists
    it under, except "Stations without a state" and stations filed under
    their reference station's state (DECISIONS 0018)."""
    if not state_code or state_code == "other" or station.filed_by == "reference":
        return None
    return state_name


def source_data(name: str, url: str) -> dict[str, Any]:
    """NOAA's data a Tide Hours dataset is computed from: NOAA CO-OPS is its
    creator, and it is U.S. Government work in the public domain."""
    return {
        "@type": "Dataset",
        "name": name,
        "url": url,
        "creator": NOAA_COOPS,
        "license": NOAA_PUBLIC_DOMAIN,
    }


def station_nodes(
    station: Station,
    *,
    state_code: str,
    state_name: str,
    base_url: str,
    path: str,
    first: str,
    last: str,
    built: str,
) -> list[dict[str, Any]]:
    """A station page's Place (when it has coordinates) and Dataset. `first`
    and `last` are the two dates the page shows; `built` is the build date
    the page's visible "page built" line prints."""
    nodes: list[dict[str, Any]] = []
    where = place(station, located_state(station, state_code, state_name))
    if where is not None:
        nodes.append({"@context": CONTEXT, **where})
    sub = " and the station's published time and height corrections" if station.is_subordinate else ""
    dataset: dict[str, Any] = {
        "@context": CONTEXT,
        "@type": "Dataset",
        "name": f"Predicted high and low tides at {station.display_name}, {first} to {last}",
        "description": (
            f"Predicted times and heights of high and low tide at NOAA station {station.id}, "
            f"{station.display_name}, for {first} and {last}, in local time and feet above "
            f"mean lower low water (MLLW). Computed by Tide Hours from NOAA CO-OPS harmonic constants{sub}. "
            "Predictions, not observations; not for navigation. Tide Hours is not a NOAA product."
        ),
        "url": base_url + path,
        "creator": tide_hours(base_url),
        "isAccessibleForFree": True,
        "isBasedOn": source_data(f"NOAA CO-OPS data for station {station.id}", noaa_station_url(station.id)),
        "temporalCoverage": f"{first}/{last}",
        "dateModified": DATE_MODIFIED,
        "creditText": (f"Source: NOAA CO-OPS station {station.id}, predictions computed by Tide Hours on {built}"),
    }
    if where is not None:
        dataset["spatialCoverage"] = where
    nodes.append(dataset)
    return nodes


def king_tide_nodes(base_url: str, path: str, copy: dict[str, Any], first: str, last: str) -> list[dict[str, Any]]:
    """The king-tide page's Dataset: the season's window, the three states,
    and the page's own heading and lead as its name and description.

    No FAQPage, though the page has a "What is a king tide?" section: with
    the affiliate and print-shop switches on, the English page is within
    about a kilobyte of check_site's 120,000-byte limit, and the question
    and answer would repeat 760 bytes of text the page already shows
    (docs/DECISIONS.md 0034)."""
    return [
        {
            "@context": CONTEXT,
            "@type": "Dataset",
            "name": copy["heading"],
            "description": copy["lead"],
            "url": base_url + path,
            "creator": tide_hours(base_url),
            "isBasedOn": NOAA_HOME,
            "temporalCoverage": f"{first}/{last}",
            "spatialCoverage": [
                {"@type": "AdministrativeArea", "name": name} for name in ("Washington", "Oregon", "California")
            ],
            "dateModified": DATE_MODIFIED,
        }
    ]
