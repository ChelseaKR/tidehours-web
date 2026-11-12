"""Structured data that restates what a page shows, and nothing more.

Every page's BreadcrumbList must list exactly the items of its visible
`<nav class="crumbs">` trail, in order, with the same names and links. The
home page carries a WebSite node with the name its header shows.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli

NOW = "2026-11-01T11:20:00Z"
BASE = "https://tidehours.com/"

NAV = re.compile(r'<nav class="crumbs" aria-label="Breadcrumb">(.*?)</nav>', re.S)
LINK = re.compile(r'<a href="([^"]*)">(.*?)</a>', re.S)
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,HI,AS,other"]) == 0
    return out


def visible_trail(page: str) -> list[tuple[str, str]]:
    """The trail a reader sees: (name, absolute URL) for each link, in order."""
    navs = NAV.findall(page)
    assert len(navs) <= 1
    if not navs:
        return []
    return [(htmllib.unescape(name).strip(), BASE + href.lstrip("/")) for href, name in LINK.findall(navs[0])]


def nodes(page: str) -> list[dict[str, Any]]:
    return [json.loads(block) for block in LD.findall(page)]


def crumb_problems(page: str) -> list[str]:
    """Why a page's breadcrumb markup differs from its visible trail (empty if it doesn't)."""
    trail = visible_trail(page)
    lists = [n for n in nodes(page) if n.get("@type") == "BreadcrumbList"]
    if len(trail) < 2:
        return [f"{len(lists)} BreadcrumbList for a {len(trail)}-item trail"] if lists else []
    if len(lists) != 1:
        return [f"{len(lists)} BreadcrumbList for a {len(trail)}-item trail"]
    items = lists[0]["itemListElement"]
    marked = [(i["name"], i["item"]) for i in items]
    problems = []
    if marked != trail:
        problems.append(f"markup {marked} != visible {trail}")
    if [i["position"] for i in items] != list(range(1, len(items) + 1)):
        problems.append("positions are not 1..n")
    if any(i["@type"] != "ListItem" for i in items) or lists[0].get("@context") != "https://schema.org":
        problems.append("not schema.org ListItems")
    return problems


def test_every_breadcrumb_matches_the_visible_trail(built: Path) -> None:
    kinds = {"station+region": 0, "station": 0, "region": 0, "state": 0, "king-tide state": 0}
    for f in sorted(built.rglob("*.html")):
        page = f.read_text(encoding="utf-8")
        rel = f.relative_to(built).as_posix()
        assert crumb_problems(page) == [], rel
        n = len(visible_trail(page))
        if rel.startswith("stations/"):
            assert n in (2, 3), rel
            kinds["station+region" if n == 3 else "station"] += 1
        elif re.fullmatch(r"states/[a-z]+/index\.html", rel):
            assert n == 1, rel
            kinds["state"] += 1
        elif re.fullmatch(r"states/[a-z]+/[^/]+/index\.html", rel) and n:
            assert n == 2, rel
            kinds["region"] += 1
        elif re.fullmatch(r"king-tides/[a-z-]+/index\.html", rel):
            assert n == 2, rel
            kinds["king-tide state"] += 1
        else:
            assert n == 0, rel
    # Each kind of trail was actually checked, not skipped.
    assert all(count > 0 for count in kinds.values()), kinds


def test_station_breadcrumb(built: Path) -> None:
    page = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    (crumbs,) = [n for n in nodes(page) if n["@type"] == "BreadcrumbList"]
    assert crumbs["itemListElement"] == [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "California", "item": BASE + "states/ca/"},
        {
            "@type": "ListItem",
            "position": 3,
            "name": "San Francisco Bay",
            "item": BASE + "states/ca/san-francisco-bay/",
        },
    ]
    # The station's existing WebPage node is still there and still first;
    # its Place and Dataset (tests/test_jsonld.py) follow.
    assert [n["@type"] for n in nodes(page)] == ["WebPage", "BreadcrumbList", "Place", "Dataset"]


def test_state_page_has_no_breadcrumb_markup(built: Path) -> None:
    page = (built / "states/ca/index.html").read_text(encoding="utf-8")
    assert visible_trail(page) == [("Home", BASE)]
    assert nodes(page) == []


def test_home_page_website_node(built: Path) -> None:
    page = (built / "index.html").read_text(encoding="utf-8")
    assert nodes(page) == [{"@context": "https://schema.org", "@type": "WebSite", "name": "Tide Hours", "url": BASE}]
    assert '<a class="brand" href="/">Tide Hours</a>' in page
    others = [f for f in built.rglob("*.html") if f != built / "index.html"]
    for f in others:
        assert '"WebSite"' not in f.read_text(encoding="utf-8"), f


def test_negative_controls_catch_markup_that_differs(built: Path) -> None:
    page = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert crumb_problems(page) == []
    # Each sabotage must change the page, or a "caught" would prove nothing.
    sabotage = {
        "renamed item": ('"name": "San Francisco Bay"', '"name": "SF Bay"'),
        "wrong link": ('"item": "https://tidehours.com/states/ca/"', '"item": "https://tidehours.com/states/or/"'),
        "extra item": (
            '"name": "San Francisco Bay", "position": 3}',
            '"name": "San Francisco Bay", "position": 3}, '
            '{"@type": "ListItem", "item": "https://tidehours.com/stations/9414290/", "name": "Golden Gate", "position": 4}',
        ),
        "hidden trail": ('<nav class="crumbs" aria-label="Breadcrumb">', '<nav class="other" aria-label="Breadcrumb">'),
        "visible item without markup": (
            '<li><a href="/states/ca/">California</a></li>',
            '<li><a href="/states/ca/">California</a></li><li><a href="/x/">X</a></li>',
        ),
        "bad position": ('"position": 2}', '"position": 7}'),
    }
    for what, (old, new) in sabotage.items():
        assert page.count(old) == 1, what
        broken = page.replace(old, new)
        assert broken != page, what
        assert crumb_problems(broken), what
    # A one-item trail with markup is also caught.
    state = (built / "states/ca/index.html").read_text(encoding="utf-8")
    crumbs_block = next(b for b in LD.findall(page) if "BreadcrumbList" in b)
    with_markup = state.replace("</head>", f'<script type="application/ld+json">{crumbs_block}</script></head>')
    assert with_markup != state
    assert crumb_problems(with_markup)
