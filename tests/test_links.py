"""Links between the hubs (docs/DECISIONS.md 0043): a state page ends with
the other states along its coast, as the home page groups them; a region
page ends with every region of its state, in the state page's order; and,
once its heading is approved, a station page lists more places in its
region past Nearby. Negative controls prove check_site's check_links fails
a page whose lists are wrong."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, site
from tidehours.catalog import load

NOW = "2026-11-15T11:20:00Z"


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("links")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "NH,MS,AL,PR,other"]) == 0
    return out


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def _states() -> list[site.State]:
    return site.group(load().stations)


def _state(code: str) -> site.State:
    return next(st for st in _states() if st.code == code)


# The lists, on the full catalog.


def test_coast_neighbors_are_the_home_page_groups_that_hold_the_state() -> None:
    groups = site.coast_groups(_states())
    names = {
        code: [name for name, _ in site.coast_neighbors(_state(code), groups)] for code in ("ME", "FL", "WA", "PR")
    }
    assert names == {
        "ME": ["Atlantic coast, north to south"],
        "FL": ["Atlantic coast, north to south", "Gulf Coast, east to west"],
        "WA": ["Pacific coast, north to south"],
        "PR": ["Caribbean"],
    }
    # A group of one state links nowhere: Alaska, and the stations without a state.
    assert site.coast_neighbors(_state("AK"), groups) == []
    assert site.coast_neighbors(_state(site.OTHER), groups) == []


def test_sibling_regions_follow_the_state_page() -> None:
    order = site.region_order()
    ca = _state("CA")
    assert site.sibling_regions(ca, site.coast_order(ca, order)) == site.coast_order(ca, order)
    assert site.sibling_regions(_state("PR"), _state("PR").regions) == []  # one region
    other = _state(site.OTHER)
    assert len(other.regions) > 1 and site.sibling_regions(other, other.regions) == []


# The built pages.


def test_state_page_ends_with_its_coast(built: Path) -> None:
    ms = read(built, "states/ms")
    section = ms[ms.index('<section class="coast-states"') :]
    assert '<h2 id="coast-0">Gulf Coast, east to west</h2>' in section
    assert '<a href="/states/al/">Alabama</a> <span class="count">23 stations</span>' in section
    assert '<span aria-current="page">Mississippi</span> <span class="count">22 stations</span>' in section
    assert section.index("Alabama") < section.index("Mississippi")
    # It is not one of the find box's lists, nor a region section.
    assert '<ul class="stations">' not in section and 'aria-labelledby="r-' not in section
    # New Hampshire is the only Atlantic state in this build, so its page has no list.
    assert "coast-states" not in read(built, "states/nh")
    assert "coast-states" not in read(built, "states/other")


def test_region_page_lists_its_states_regions(built: Path) -> None:
    nh = site.coast_order(_state("NH"), site.region_order())
    for r in nh:
        page = read(built, r.path)
        jump = page[page.index('<details class="regions-jump">') : page.index("</details>")]
        assert f'<summary id="jump">Jump to a region, north to south ({len(nh)})</summary>' in jump
        assert re.findall(r'href="/(states/[^"]+/)"', jump) == [x.path for x in nh if x is not r]
        assert f'<span aria-current="page">{r.name}</span>' in jump
        # After the day's list, so the answer stays first.
        assert page.index('<ul class="stations">') < page.index('<details class="regions-jump">')
    for rel in ("states/pr/" + _state("PR").regions[0].slug, "states/other/" + _state(site.OTHER).regions[0].slug):
        assert "regions-jump" not in read(built, rel)


def test_more_places_is_off_without_its_copy(built: Path) -> None:
    assert not site.MORE_PLACES_FILE.exists(), "copy/more_places.json is new wording for the owner to approve"
    assert site.more_places_heading() is None
    for f in (built / "stations").glob("*/index.html"):
        assert 'id="more"' not in f.read_text(encoding="utf-8")


def _render(tmp_path: Path, heading: str, states: set[str]) -> dict[str, str]:
    copy = tmp_path / "more_places.json"
    copy.write_text(json.dumps({"heading": heading}), encoding="utf-8")
    cfg = site.Config(states=states, more_places_file=copy)
    now = dt.datetime.fromisoformat(NOW.replace("Z", "+00:00"))
    return {p.path: p.html for p in site.render(load(), cfg, now)}


def test_more_places_lists_the_rest_of_the_region(tmp_path: Path) -> None:
    pages = _render(tmp_path, "More places in {region}", {"AL"})
    al = _state("AL")
    region = al.regions[0]
    for s in region.stations:
        page = pages[f"stations/{s.id}/"]
        nearby = (
            re.findall(r'href="/stations/(\d+)/"', page.split('id="near"', 1)[1].split("</section>", 1)[0])
            if 'id="near"' in page
            else []
        )
        more = page.split('<h2 id="more">', 1)
        rest = sorted((site.distance_km(s, o), o.id) for o in region.stations if o.id != s.id and o.id not in nearby)
        if not rest:
            assert len(more) == 1
            continue
        assert more[1].startswith(f"More places in {region.name}</h2>")
        listed = re.findall(r'href="/stations/(\d+)/"', more[1].split("</section>", 1)[0])
        assert listed == [sid for _, sid in rest[: site.MORE_PLACES_MAX]]
        assert not set(listed) & set(nearby)
    # A station without a region has no such list.
    for s in al.unregioned:
        assert 'id="more"' not in pages[f"stations/{s.id}/"]


def test_more_places_heading_must_name_the_region(tmp_path: Path) -> None:
    f = tmp_path / "more_places.json"
    f.write_text(json.dumps({"heading": "More places"}), encoding="utf-8")
    with pytest.raises(ValueError, match="must name"):
        site.more_places_heading(f)


# check_site.


def test_check_links_passes_the_build(built: Path) -> None:
    assert _check_site().check_links(built, load()) == []


@pytest.mark.parametrize("how", ["drop-state", "link-self", "drop-region", "reorder-regions", "list-on-one-region"])
def test_check_links_catches_a_bad_list(tmp_path: Path, built: Path, how: str) -> None:
    root = tmp_path / "site"
    shutil.copytree(built, root)
    check = _check_site()
    nh = site.coast_order(_state("NH"), site.region_order())
    if how in ("drop-state", "link-self"):
        f = root / "states/ms/index.html"
        page = f.read_text(encoding="utf-8")
        if how == "drop-state":
            page = re.sub(r'<li><a href="/states/al/">Alabama</a>.*?</li>', "", page, count=1)
        else:
            page = page.replace('<span aria-current="page">Mississippi</span>', '<a href="/states/ms/">Mississippi</a>')
    elif how in ("drop-region", "reorder-regions"):
        f = root / nh[0].path / "index.html"
        page = f.read_text(encoding="utf-8")
        a, b = (f'<li><a href="/{r.path}">{r.name}</a></li>' for r in nh[1:3])
        assert a in page and b in page
        page = page.replace(a, "") if how == "drop-region" else page.replace(a, "@@").replace(b, a).replace("@@", b)
    else:
        f = root / "states/pr" / _state("PR").regions[0].slug / "index.html"
        page = f.read_text(encoding="utf-8").replace(
            "</main>", '<details class="regions-jump"><summary id="jump">x</summary><ul></ul></details></main>'
        )
    f.write_text(page, encoding="utf-8")
    assert check.check_links(root, load())
