"""State and region hubs (docs/DECISIONS.md 0039): state pages list their
regions in coast order (copy/region_order.json, else north to south) with a
jump list, a count per region and a find box; region pages show each
place's highs and lows for the day, from the same numbers as its station
page. Negative controls prove check_site's check_hubs fails a hub that is
out of order or out of step with its station pages, and the find script is
run under Node against a stand-in for the page."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, site
from tidehours.catalog import load

NOW = "2026-11-13T11:20:00Z"
CA_ORDER = [
    "outer-coast-san-francisco",
    "humboldt-bay",
    "san-francisco-bay",
    "san-pablo-bay",
    "carquinez-strait",
    "suisun-bay",
    "sacramento-river",
    "san-joaquin-river",
    "mokelumne-river",
    "outer-coast-port-san-luis",
    "monterey-bay",
    "santa-barbara-channel",
    "santa-barbara-islands",
    "san-pedro-channel",
    "southern-california",
]
TAG = re.compile(r"<[^>]+>")


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("hubs")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,FL"]) == 0
    return out


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def text(html: str) -> str:
    return " ".join(TAG.sub(" ", html).split())


# The order file.


def test_committed_order_is_the_owners_california_order() -> None:
    order = site.region_order()
    assert order == {"CA": CA_ORDER}  # approved by the owner on 2026-11-14
    ca = next(st for st in site.group(load().stations) if st.code == "CA")
    assert [r.slug for r in site.coast_order(ca, order)] == CA_ORDER


def _order_file(tmp_path: Path, states: Any, **extra: Any) -> Path:
    f = tmp_path / "region_order.json"
    f.write_text(json.dumps({"about": "test", "states": states, **extra}), encoding="utf-8")
    return f


@pytest.mark.parametrize(
    ("states", "extra", "message"),
    [
        ({"XX": ["a"]}, {}, "'XX' is not a state"),
        ({"other": ["a"]}, {}, "'other' is not a state"),
        ({"CA": ["monterey-bay", "monterey-bay"]}, {}, "listed twice"),
        ({"CA": ["Monterey Bay"]}, {}, "region URL slugs"),
        ({"CA": "monterey-bay"}, {}, "region URL slugs"),
        ({"CA": []}, {"note": "x"}, "exactly 'about' and 'states'"),
    ],
)
def test_order_file_refuses_bad_entries(tmp_path: Path, states: Any, extra: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        site.region_order(_order_file(tmp_path, states, **extra))


def test_a_listed_state_must_list_each_region_once() -> None:
    ca = next(st for st in site.group(load().stations) if st.code == "CA")
    with pytest.raises(ValueError, match=r"regions not listed \['southern-california'\]"):
        site.coast_order(ca, {"CA": CA_ORDER[:-1]})
    with pytest.raises(ValueError, match=r"unknown regions \['nowhere'\]"):
        site.coast_order(ca, {"CA": [*CA_ORDER, "nowhere"]})


def test_unlisted_states_go_north_to_south() -> None:
    fl = next(st for st in site.group(load().stations) if st.code == "FL")
    regions = site.coast_order(fl, site.region_order())
    means = [sum(s.lat for s in r.stations) / len(r.stations) for r in regions]
    assert means == sorted(means, reverse=True) and len(regions) == len(fl.regions)
    other = next(st for st in site.group(load().stations) if st.code == site.OTHER)
    assert site.coast_order(other, {}) == other.regions  # alphabetical, as before


# The built pages.


def test_state_page_lists_regions_in_coast_order(built: Path) -> None:
    ca = read(built, "states/ca")
    assert re.findall(r'<section aria-labelledby="r-([^"]+)">', ca) == CA_ORDER
    assert "205 NOAA tide prediction stations, by NOAA's regions, north to south.</p>" in ca
    assert '<summary id="jump">Jump to a region, north to south (15)</summary>' in ca
    jump = ca[ca.index('<details class="regions-jump">') : ca.index("</details>")]
    assert re.findall(r'href="#r-([^"]+)"', jump) == CA_ORDER
    assert (
        '<a href="/states/ca/outer-coast-san-francisco/">Outer Coast, San Francisco</a> <span class="count">20 places</span></h2>'
        in ca
    )
    assert '<main id="main" class="wrap" data-find-label="Find a place in California">' in ca
    # The lead is still the one paragraph between the H1 and the first list.
    assert ca.count("<p", ca.index("<h1>"), ca.index('<ul class="stations">')) == 1
    fl = read(built, "states/fl")
    # Each region's count is the number of places listed under it.
    for page in (ca, fl):
        counted = re.findall(r'<span class="count">(\d+) places?</span></h2>(.*?)</section>', page, re.S)
        assert len(counted) == page.count('<section aria-labelledby="r-')
        for n, inner in counted:
            assert inner.count("<li") == int(n)
    assert "r-none" in fl and fl.index('aria-labelledby="r-florida-keys"') < fl.index('aria-labelledby="r-none"')


def test_region_page_shows_each_places_times(built: Path) -> None:
    mb = read(built, "states/ca/monterey-bay")
    assert '<main id="main" class="wrap" data-region>' in mb
    assert (
        '<h2 class="hub-day" data-date="2026-11-13">High and low tides, Friday, November 13, 2026 '
        '<span class="meta">(Pacific Time; heights on each place\'s page)</span></h2>'
    ) in mb
    row = re.search(r'<li data-station="9413450">.*?</li>', mb)
    assert row and text(row.group(0)) == "Monterey, Monterey Bay High 2:25 AM, 11:34 AM Low 5:30 AM, 7:35 PM"
    assert " ft" not in mb[mb.index('<ul class="stations">') : mb.index("</ul>")]  # times only
    assert mb.count("<p", mb.index("<h1>"), mb.index('<ul class="stations">')) == 1
    # A region across two zones says so instead of naming one.
    pb = read(built, "states/fl/pensacola-bay")
    assert "(local time at each place; heights on each place's page)</span></h2>" in pb


def test_row_wording_for_absence() -> None:
    check = _check_site()
    assert check.hub_times([]) == "no high or low tide predicted"
    assert check.hub_times([("High", "2:25 AM")]) == "High 2:25 AM no low tide"
    assert check.hub_times([("Low", "1:39 PM")]) == "no high tide Low 1:39 PM"


def test_check_hubs_passes_the_build(built: Path) -> None:
    assert _check_site().check_hubs(built, load()) == []


def _sabotage(page: Path, old: str, new: str) -> None:
    html = page.read_text(encoding="utf-8")
    assert old in html
    page.write_text(html.replace(old, new, 1), encoding="utf-8")
    assert page.read_text(encoding="utf-8") != html  # the sabotage applied


CASES: dict[str, tuple[str, str, str, str]] = {
    "wrong-time": (
        "states/ca/monterey-bay",
        '<span class="lo">Low</span> 5:30 AM, 7:35 PM',
        '<span class="lo">Low</span> 5:30 AM, 7:53 PM',
        "9413450: times",
    ),
    "kind-swapped": (
        "states/ca/monterey-bay",
        '<span class="hi">High</span> 2:25 AM, 11:34 AM</span> <span class="grp"><span class="lo">Low</span> 5:30 AM',
        '<span class="hi">High</span> 2:25 AM, 11:34 AM, 5:30 AM</span> <span class="grp"><span class="lo">Low</span>',
        "9413450: times",
    ),
    "row-removed": ("states/ca/monterey-bay", '<li data-station="9413450">', '<li data-gone="9413450">', "rows"),
    "date": ("states/ca/monterey-bay", 'data-date="2026-11-13">', 'data-date="2026-11-14">', "first day is not"),
    "heading-removed": (
        "states/ca/monterey-bay",
        '<h2 class="hub-day" data-date="2026-11-13">',
        '<h2 class="hub-gone">',
        "times under no dated heading",
    ),
    "placeholder": (
        "states/ca/monterey-bay",
        '11:34 AM</span> <span class="grp"><span class="lo">Low</span> 5:30 AM',
        'None</span> <span class="grp"><span class="lo">Low</span> 5:30 AM',
        "9413450: contains 'None'",
    ),
    "order": (
        "states/ca",
        '<section aria-labelledby="r-humboldt-bay">',
        '<section aria-labelledby="r-humboldt-bay"></section><section aria-labelledby="r-humboldt-bay">',
        "states/ca/: regions",
    ),
}


@pytest.mark.parametrize("how", sorted(CASES))
def test_check_hubs_catches_a_bad_hub(tmp_path: Path, built: Path, how: str) -> None:
    """Negative controls: check_hubs passes a copy of the build, then fails
    each sabotage of one hub page."""
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    cat = load()
    assert check.check_hubs(root, cat) == []
    rel, old, new, expect = CASES[how]
    _sabotage(root / rel / "index.html", old, new)
    problems = check.check_hubs(root, cat)
    assert problems and any(expect in p for p in problems), problems


def test_check_hubs_catches_regions_out_of_order(tmp_path: Path, built: Path) -> None:
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    page = root / "states/ca/index.html"
    html = page.read_text(encoding="utf-8")
    humboldt = re.search(r'<section aria-labelledby="r-humboldt-bay">.*?</section>\n', html, re.S)
    assert humboldt is not None
    moved = html.replace(humboldt.group(0), "", 1).replace("</main>", humboldt.group(0) + "</main>", 1)
    page.write_text(moved, encoding="utf-8")
    assert page.read_text(encoding="utf-8") != html
    problems = check.check_hubs(root, load())
    assert any(p.startswith("states/ca/: regions") for p in problems), problems


# The find script, run under Node against a stand-in for the state page.

HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const items = input.items.map((it) => ({
  textContent: it.text, section: it.section, hidden: false,
  getAttribute: (n) => (n === "data-aka" ? it.aka : null),
}));
const sections = input.sections.map((id) => ({
  id, hidden: false,
  querySelector: (q) => (q === "li:not([hidden])" ? items.find((i) => i.section === id && !i.hidden) || null : null),
}));
const jump = { hidden: false };
let handler = null, added = null;
const input_ = { value: "", addEventListener: (t, f) => { if (t === "input") handler = f; } };
const label = { textContent: "" }, output = { textContent: "" };
const main = {
  getAttribute: (n) => (n === "data-find-label" ? input.label : null),
  querySelectorAll: (q) => (q === "ul.stations li" ? items : q === "section[aria-labelledby^='r-']" ? sections : []),
  querySelector: (q) => (q === ".lead" ? { after: (b) => { added = b; } } : q === ".regions-jump" ? jump : null),
};
const document = {
  getElementById: (id) => (id === "main" ? main : null),
  createElement: () => ({
    innerHTML: "",
    querySelector: (q) => (q === "label" ? label : q === "input" ? input_ : q === "output" ? output : null),
  }),
};
const context = { document };
vm.runInNewContext(input.script, context);
const results = input.queries.map((q) => {
  input_.value = q;
  handler();
  return {
    shown: items.filter((i) => !i.hidden).map((i) => i.textContent),
    sections: sections.filter((s) => !s.hidden).map((s) => s.id),
    status: output.textContent,
    jumpHidden: jump.hidden,
  };
});
process.stdout.write(JSON.stringify({
  added: added !== null, label: label.textContent, results,
  norms: (input.norms || []).map((s) => context.tidehoursFind.norm(s)),
}));
"""
FIND_SCRIPT = re.compile(r"<script>\s*(// Find a place.*?)</script>", re.S)


def node() -> str:
    # Not a skip: a missing Node would make these pass silently (test_today.py).
    found = shutil.which("node")
    assert found, "these tests need Node on PATH (Node 22+, see tools/site-checks/.nvmrc)"
    return found


def run_find(html: str, queries: list[str], norms: list[str] | None = None) -> dict[str, Any]:
    script = FIND_SCRIPT.search(html)
    label = re.search(r'data-find-label="([^"]+)"', html)
    assert script and label
    items = []
    for section in re.finditer(r'<section aria-labelledby="(r-[^"]+)">(.*?)</section>', html, re.S):
        for aka, inner in re.findall(r"<li(?: data-aka=\"([^\"]*)\")?>(.*?)</li>", section.group(2), re.S):
            items.append({"text": text(inner), "aka": aka or None, "section": section.group(1)})
    payload = {
        "script": script.group(1),
        "label": label.group(1),
        "items": items,
        "sections": re.findall(r'<section aria-labelledby="(r-[^"]+)">', html),
        "queries": queries,
        "norms": norms or [],
    }
    out = subprocess.run(  # noqa: S603 - our own harness, fixed arguments
        [node(), "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, check=True, timeout=60
    )
    result: dict[str, Any] = json.loads(out.stdout)
    return result


def test_find_filters_the_places_on_the_page(built: Path) -> None:
    ca = read(built, "states/ca")
    r = run_find(ca, ["half moon", "  HALF   Moon ", "xyz", "", "bay"])
    assert r["added"] and r["label"] == "Find a place in California"
    half, spaced, none, empty, bay = r["results"]
    assert half["shown"] == ["Pillar Point Harbor, Half Moon Bay"]
    assert half["sections"] == ["r-outer-coast-port-san-luis"] and half["jumpHidden"]
    assert half["status"] == "1 place matches “half moon”."
    assert spaced["shown"] == half["shown"] and spaced["status"] == "1 place matches “HALF   Moon”."
    assert none["shown"] == [] and none["sections"] == []
    assert none["status"] == "No place on this page matches “xyz”. Try the town, beach or bay name."
    assert len(empty["shown"]) == 205 and empty["status"] == "" and not empty["jumpHidden"]
    assert len(empty["sections"]) == 15
    assert bay["status"] == f"{len(bay['shown'])} places match “bay”." and len(bay["shown"]) > 1


def test_find_ignores_accents_and_okina_and_reads_searched_names(tmp_path: Path) -> None:
    out = tmp_path / "hi"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI"]) == 0
    hi = read(out, "states/hi")
    assert 'data-aka="Maui (Kahului, HI)"' in hi
    r = run_find(hi, ["maui", "nawiliwili"], norms=["Nāwiliwili", "Oʻahu", "O‘ahu"])
    assert r["norms"] == ["nawiliwili", "oahu", "oahu"]
    maui, nawi = r["results"]
    assert len(maui["shown"]) == 1 and "Kahului" in maui["shown"][0]
    assert any("Nawiliwili" in s or "Nāwiliwili" in s for s in nawi["shown"])
