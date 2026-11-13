"""schema.org markup and dateModified (docs/DECISIONS.md 0034).

Validation is stdlib only: every JSON-LD block is parsed with `json`, and
every type and property it uses must be in VOCABULARY below, a table checked
against schema.org's own vocabulary file (schemaorg-current-https.jsonld,
release 30.1, read 2026-11-12): each type exists, and each property's
domainIncludes covers the type or one of its supertypes. A type or property
not in the table fails the test until it is checked the same way and added.
"""

from __future__ import annotations

import dataclasses
import html as htmllib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, schema, site
from tidehours.catalog import load

NOW = "2026-11-01T11:20:00Z"
BASE = "https://tidehours.com/"
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
META_MODIFIED = re.compile(r'<meta name="dateModified" content="([^"]*)">')
DATA_DATE = re.compile(r'<section class="day"[^>]*data-date="(\d{4}-\d{2}-\d{2})"')
TAG = re.compile(r"<[^>]+>")

# Type -> the properties the site may use on it, each checked against the
# schema.org vocabulary (see the module docstring).
VOCABULARY: dict[str, set[str]] = {
    "AdministrativeArea": {"name"},
    "BreadcrumbList": {"itemListElement"},
    "Dataset": {
        "creator",
        "creditText",
        "dateModified",
        "description",
        "inLanguage",
        "isAccessibleForFree",
        "isBasedOn",
        "license",
        "name",
        "spatialCoverage",
        "temporalCoverage",
        "url",
    },
    "GeoCoordinates": {"latitude", "longitude"},
    "GovernmentOrganization": {"name", "url"},
    "ListItem": {"item", "name", "position"},
    "Organization": {"name", "url"},
    "Place": {"containedInPlace", "geo", "name"},
    "WebPage": {"about", "dateModified", "isBasedOn", "name", "url"},
    "State": {"name"},
    "WebSite": {"name", "url"},
}
# Never on this site: nothing here is an event, a product or an offer, and
# nothing is reviewed or rated.
FORBIDDEN = {
    "Event",
    "Product",
    "Offer",
    "AggregateOffer",
    "Review",
    "AggregateRating",
    "Rating",
    "SearchAction",
    "FAQPage",
}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("jsonld")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,HI,AS,other"]) == 0
    return out


def nodes(page: str) -> list[dict[str, Any]]:
    return [json.loads(block) for block in LD.findall(page)]


def vocabulary_problems(node: Any, where: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(node, list):
        for item in node:
            problems += vocabulary_problems(item, where)
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind is not None:
            if kind in FORBIDDEN or kind not in VOCABULARY:
                problems.append(f"{where}type {kind}")
            else:
                problems += [f"{where}{kind}.{k}" for k in node if not k.startswith("@") and k not in VOCABULARY[kind]]
        for value in node.values():
            problems += vocabulary_problems(value, where)
    return problems


def visible_text(page: str) -> str:
    body = page.split("<body>", 1)[1]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    return re.sub(r"\s+", " ", htmllib.unescape(TAG.sub(" ", body)))


def lastmods(root: Path) -> dict[str, str]:
    text = (root / "sitemap.xml").read_text(encoding="utf-8")
    return dict(re.findall(r"<loc>https://tidehours\.com/([^<]*)</loc><lastmod>([^<]*)</lastmod>", text))


def date_problems(root: Path) -> list[str]:
    """Every page in the sitemap, and every station page, carries one
    dateModified meta equal to its sitemap lastmod (the build date for a
    station page outside the sitemap), and every JSON-LD dateModified on it
    is the same date; any other page carries none."""
    mods = lastmods(root)
    built = max(mods.values())
    problems: list[str] = []
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        path = "" if rel == "index.html" else rel.removesuffix("index.html")
        page = f.read_text(encoding="utf-8")
        if schema.DATE_MODIFIED in page:
            problems.append(f"{rel}: placeholder left in")
        metas = META_MODIFIED.findall(page)
        ld_dates = [n["dateModified"] for n in nodes(page) if "dateModified" in n]
        want = mods.get(path, built if path.startswith("stations/") else None)
        if want is None:
            if metas or ld_dates:
                problems.append(f"{rel}: dated though not in the sitemap")
            continue
        if metas != [want]:
            problems.append(f"{rel}: meta {metas} != lastmod {want}")
        problems += [f"{rel}: JSON-LD {d} != lastmod {want}" for d in ld_dates if d != want]
    return problems


def test_every_block_parses_and_uses_checked_vocabulary(built: Path) -> None:
    seen: set[str] = set()
    for f in sorted(built.rglob("*.html")):
        rel = f.relative_to(built).as_posix()
        for node in nodes(f.read_text(encoding="utf-8")):
            assert node["@context"] == "https://schema.org", rel
            assert vocabulary_problems(node, f"{rel}: ") == []
            seen.add(node["@type"])
    assert {"WebSite", "BreadcrumbList", "Place", "Dataset", "WebPage"} <= seen, seen
    # Negative control: a forbidden type and an unchecked property are caught.
    assert vocabulary_problems({"@type": "Event", "name": "King tides"})
    assert vocabulary_problems({"@type": "Dataset", "aggregateRating": {"@type": "AggregateRating"}})


def test_station_place_and_dataset(built: Path) -> None:
    cat = load()
    page = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    types = [n["@type"] for n in nodes(page)]
    assert types == ["WebPage", "BreadcrumbList", "Place", "Dataset"]
    (place,) = [n for n in nodes(page) if n["@type"] == "Place"]
    (dataset,) = [n for n in nodes(page) if n["@type"] == "Dataset"]
    station = cat.station("9414290")
    assert station is not None
    assert place["name"] == station.display_name
    assert place["geo"] == {"@type": "GeoCoordinates", "latitude": station.lat, "longitude": station.lon}
    assert place["containedInPlace"] == {"@type": "AdministrativeArea", "name": "California"}
    first, last = DATA_DATE.findall(page)
    assert dataset["temporalCoverage"] == f"{first}/{last}"
    assert dataset["url"] == BASE + "stations/9414290/"
    assert 50 <= len(dataset["description"]) <= 5000
    for promise in ("not for navigation", "not a NOAA product", "mean lower low water (MLLW)"):
        assert promise in dataset["description"], promise
    assert dataset["creator"]["name"] == "Tide Hours"
    source = dataset["isBasedOn"]
    assert source["url"] == "https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id=9414290"
    assert source["url"] in page.split("</head>", 1)[1]  # the same link the page shows
    assert source["creator"]["@type"] == "GovernmentOrganization" and "CO-OPS" in source["creator"]["name"]
    assert source["license"] == "https://tidesandcurrents.noaa.gov/disclaimers.html"
    assert "license" not in dataset  # Tide Hours' own terms are the owner's call
    assert (
        dataset["creditText"] == "Source: NOAA CO-OPS station 9414290, predictions computed by Tide Hours on 2026-11-01"
    )
    assert dataset["spatialCoverage"] == {k: v for k, v in place.items() if k != "@context"}


def test_every_station_place_matches_the_catalog(built: Path) -> None:
    cat = load()
    checked = 0
    for f in sorted((built / "stations").glob("*/index.html")):
        station = cat.station(f.parent.name)
        assert station is not None
        places = [n for n in nodes(f.read_text(encoding="utf-8")) if n["@type"] == "Place"]
        assert len(places) == 1, f
        geo = places[0]["geo"]
        assert (geo["latitude"], geo["longitude"]) == (station.lat, station.lon), f
        checked += 1
    assert checked > 100


def test_no_coordinates_no_place() -> None:
    """Negative control: a station without a usable position gets no Place and
    no spatialCoverage, and still gets its Dataset."""
    cat = load()
    station = cat.station("9414290")
    assert station is not None
    kwargs: dict[str, Any] = {
        "state_code": "CA",
        "state_name": "California",
        "base_url": BASE,
        "path": "stations/9414290/",
        "first": "2026-11-01",
        "last": "2026-11-02",
        "built": "2026-11-01",
    }
    assert [n["@type"] for n in schema.station_nodes(station, **kwargs)] == ["Place", "Dataset"]
    for bad in (float("nan"), float("inf"), 91.0, None):
        lost = dataclasses.replace(station, lat=bad)  # type: ignore[arg-type]
        out = schema.station_nodes(lost, **kwargs)
        assert [n["@type"] for n in out] == ["Dataset"], bad
        assert "spatialCoverage" not in out[0], bad


def test_place_claims_a_state_only_where_the_station_is() -> None:
    cat = load()
    station = cat.station("9414290")
    assert station is not None
    by_reference = dataclasses.replace(station, filed_by="reference")
    assert schema.located_state(by_reference, "CA", "California") is None
    assert schema.located_state(station, "other", "Stations without a state") is None
    assert schema.located_state(station, "CA", "California") == "California"
    place = schema.place(by_reference, schema.located_state(by_reference, "CA", "California"))
    assert place is not None and "containedInPlace" not in place


def test_stations_without_a_state_claim_none(built: Path) -> None:
    cat = load()
    for s in cat.stations:
        if s.state:
            continue
        page = (built / "stations" / s.id / "index.html").read_text(encoding="utf-8")
        (place,) = [n for n in nodes(page) if n["@type"] == "Place"]
        assert "containedInPlace" not in place, s.id


@pytest.mark.parametrize(("path", "lang"), [("king-tides/", "en"), ("es/king-tides/", "es")])
def test_king_tides_dataset(built: Path, path: str, lang: str) -> None:
    page = (built / path / "index.html").read_text(encoding="utf-8")
    (dataset,) = nodes(page)
    assert dataset["@type"] == "Dataset"
    assert dataset["url"] == BASE + path
    assert dataset["temporalCoverage"] == "2026-11-01/2027-10-31"
    # Name and description are the page's own visible heading and lead.
    text = visible_text(page)
    assert f"<h1>{htmllib.escape(dataset['name'], quote=False)}</h1>" in page
    assert dataset["description"] in text
    assert dataset["isBasedOn"] == "https://tidesandcurrents.noaa.gov/"
    assert [a["name"] for a in dataset["spatialCoverage"]] == ["Washington", "Oregon", "California"]


def test_date_modified_matches_the_sitemap(built: Path) -> None:
    assert date_problems(built) == []
    page = (built / "about/index.html").read_text(encoding="utf-8")
    assert META_MODIFIED.findall(page) == ["2026-11-01"]
    assert "datePublished" not in page  # never guessed (DECISIONS 0034)
    # Negative control: a page whose date differs from its lastmod is caught.
    f = built / "privacy/index.html"
    original = f.read_text(encoding="utf-8")
    try:
        f.write_text(original.replace('content="2026-11-01"', 'content="2026-10-02"'), encoding="utf-8")
        assert f.read_text(encoding="utf-8") != original
        assert date_problems(built) == ["privacy/index.html: meta ['2026-10-02'] != lastmod 2026-11-01"]
    finally:
        f.write_text(original, encoding="utf-8")


def test_date_modified_carries_over_with_the_lastmod(tmp_path: Path, built: Path) -> None:
    """An unchanged page keeps its earlier lastmod in the sitemap and in its
    own dateModified, though the HTML it was written with carried another
    date: the fingerprint is taken before the date goes in."""
    prev = tmp_path / "prev"
    prev.mkdir()
    shutil.copy(built / "lastmod.json", prev / "lastmod.json")
    old = (built / "sitemap.xml").read_text(encoding="utf-8").replace("<lastmod>2026-11-01<", "<lastmod>2026-10-20<")
    (prev / "sitemap.xml").write_text(old, encoding="utf-8")
    out = tmp_path / "next"
    argv = ["--out", str(out), "--now", "2026-11-02T11:20:00Z", "--states", "CA,HI,AS,other", "--previous", str(prev)]
    assert cli.main(argv) == 0
    mods = lastmods(out)
    assert mods["privacy/"] == "2026-10-20"
    assert META_MODIFIED.findall((out / "privacy/index.html").read_text(encoding="utf-8")) == ["2026-10-20"]
    assert mods["stations/9414290/"] == "2026-11-02"
    assert date_problems(out) == []


def test_station_dates_use_the_lastmod_not_the_clock() -> None:
    page = site.Page("stations/1/", f'<meta name="dateModified" content="{schema.DATE_MODIFIED}">')
    prev = {"stations/1/": (site.fingerprint(page), "2026-10-30")}
    assert site.dated_html(page, "2026-11-01", prev) == '<meta name="dateModified" content="2026-10-30">'
    assert site.dated_html(page, "2026-11-01", {}) == '<meta name="dateModified" content="2026-11-01">'


def test_llms_txt_is_linked_from_the_about_page_only(built: Path) -> None:
    linking = sorted(
        f.relative_to(built).as_posix()
        for f in built.rglob("*.html")
        if 'href="/llms.txt"' in f.read_text(encoding="utf-8")
    )
    assert linking == ["about/index.html"]
    text = (built / "llms.txt").read_text(encoding="utf-8")
    for link in (
        "(https://tidehours.com/#states)",
        "(https://tidehours.com/king-tides/)",
        "(https://tidehours.com/about/)",
    ):
        assert link in text, link
    for promise in (
        "not a NOAA product",
        "not for navigation",
        "MLLW",
        "local to each station",
        "when the site is built",
    ):
        assert promise in text, promise
