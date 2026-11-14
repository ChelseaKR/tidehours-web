"""The home page (docs/DECISIONS.md 0040): states grouped by coast, and a
find box over /places.json, a static list of every station page the build
writes, fetched only when the box is used. Negative controls prove
check_site's check_places fails a list or a home page out of step with the
build, and the find script is run under Node against a stand-in for the
page and its fetch."""

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
from tidehours.catalog import STATE_NAMES, load

NOW = "2026-11-13T11:20:00Z"


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("home")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI,FL,other"]) == 0
    return out


def test_every_state_is_in_a_group_and_florida_in_two() -> None:
    codes = [c for _, cs in site.COAST_GROUPS for c in cs]
    assert set(codes) == {*STATE_NAMES, site.OTHER}
    assert [c for c in codes if codes.count(c) > 1] == ["FL", "FL"]
    assert [name for name, _ in site.COAST_GROUPS] == [
        "Pacific coast, north to south",
        "Alaska",
        "Hawaii and the Pacific islands",
        "Atlantic coast, north to south",
        "Gulf Coast, east to west",
        "Caribbean",
        "Other",
    ]
    stray = site.State("ZZ", "Nowhere", [], [])
    with pytest.raises(ValueError, match=r"states in no home page group: \['ZZ'\]"):
        site.coast_groups([stray])


def test_home_lists_the_builds_states_by_coast(built: Path) -> None:
    home = (built / "index.html").read_text(encoding="utf-8")
    groups = re.findall(r'<h3 class="coast" id="c-(\d)">([^<]*)</h3>', home)
    assert [g for _, g in groups] == [
        "Hawaii and the Pacific islands",
        "Atlantic coast, north to south",
        "Gulf Coast, east to west",
        "Other",
    ]
    assert home.count('<a href="/states/fl/">Florida</a>') == 2
    assert '<ul class="states" aria-labelledby="c-0">' in home
    assert home.index('<p class="lead">') < home.index('<div id="find-anchor"></div>') < home.index('id="states"')
    assert "SearchAction" not in home  # still no search page (0034)


def test_places_json_is_every_station_page(built: Path) -> None:
    rows = json.loads((built / "places.json").read_text(encoding="utf-8"))
    pages = {p.parent.name for p in (built / "stations").glob("*/index.html")}
    assert [r[0] for r in rows] == sorted(pages)
    assert ["1615680", "Kahului, HI", "Maui (Kahului, HI)"] in rows
    assert all(len(r) == 2 for r in rows if r[0] not in site.place_names())
    assert "places.json" not in (built / "sitemap.xml").read_text(encoding="utf-8")


def test_check_places_passes_the_build(built: Path) -> None:
    assert _check_site().check_places(built, load()) == []


def _rows(root: Path) -> list[list[str]]:
    data: list[list[str]] = json.loads((root / "places.json").read_text(encoding="utf-8"))
    return data


def _write(root: Path, rows: Any) -> None:
    (root / "places.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _drop(root: Path) -> None:
    _write(root, _rows(root)[1:])


def _extra(root: Path) -> None:
    _write(root, [*_rows(root), ["9999999", "Nowhere, HI"]])


def _rename(root: Path) -> None:
    rows = _rows(root)
    rows[0][1] = "Somewhere Else"
    _write(root, rows)


def _no_aka(root: Path) -> None:
    _write(root, [r[:2] for r in _rows(root)])


def _missing(root: Path) -> None:
    (root / "places.json").unlink()


def _not_json(root: Path) -> None:
    (root / "places.json").write_text("[", encoding="utf-8")


def _home_group(root: Path) -> None:
    home = root / "index.html"
    html = home.read_text(encoding="utf-8")
    new = html.replace('<li><a href="/states/fl/">Florida</a>', "<li>", 1)
    assert new != html
    home.write_text(new, encoding="utf-8")


CASES = {
    "row-dropped": (_drop, "places.json: "),
    "row-extra": (_extra, "places.json: "),
    "renamed": (_rename, "places.json: "),
    "searched-name-lost": (_no_aka, "places.json: "),
    "missing": (_missing, "places.json: missing"),
    "not-json": (_not_json, "places.json: not JSON"),
    "home-group": (_home_group, "index.html: state groups"),
}


@pytest.mark.parametrize("how", sorted(CASES))
def test_check_places_catches_a_bad_list(tmp_path: Path, built: Path, how: str) -> None:
    """Negative controls: check_places passes a copy of the build, then fails
    each sabotage of the list or the home page."""
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    cat = load()
    assert check.check_places(root, cat) == []
    sabotage, expect = CASES[how]
    sabotage(root)
    problems = check.check_places(root, cat)
    assert problems and any(p.startswith(expect) for p in problems), problems


# The find script, under Node, with the full catalog's list.

HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
function el(tag) {
  return {
    tag, children: [], href: "", _text: "",
    get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text; },
    set textContent(v) { this.children = []; this._text = v; },
    append(...n) { this.children.push(...n); },
  };
}
let replaced = false, fetches = 0;
const handlers = {};
const field = { value: "", addEventListener: (t, f) => { handlers[t] = f; } };
const out = el("output"), list = el("ul"), label = el("label");
const document = {
  getElementById: (id) => (id === "find-anchor" ? { replaceWith: () => { replaced = true; } } : null),
  createElement: (tag) => (tag === "div"
    ? { innerHTML: "", querySelector: (q) => (q === "input" ? field : q === "output" ? out : q === "ul" ? list : null) }
    : el(tag)),
};
function fetch(url) {
  fetches++;
  if (input.fail || url !== "/places.json") return Promise.reject(new Error("offline"));
  return Promise.resolve({ ok: true, json: () => Promise.resolve(input.places) });
}
const context = { document, window: { fetch }, fetch, Promise, String, Error };
vm.runInNewContext(input.script, context);
const tick = () => new Promise((r) => setTimeout(r, 0));
(async () => {
  const fetchesBefore = fetches;
  handlers.focus();
  await tick();
  const results = [];
  for (const q of input.queries) {
    field.value = q;
    handlers.input();
    for (let i = 0; i < 3; i++) await tick();
    results.push({
      status: out.textContent,
      links: list.children.map((li) => [li.children[0].href, li.children[0].textContent]),
    });
  }
  process.stdout.write(JSON.stringify({ replaced, fetchesBefore, fetches, results }));
})();
"""
SCRIPT = re.compile(r"<script>\s*(// Find a tide station.*?)</script>", re.S)


def node() -> str:
    # Not a skip: a missing Node would make these pass silently (test_today.py).
    found = shutil.which("node")
    assert found, "these tests need Node on PATH (Node 22+, see tools/site-checks/.nvmrc)"
    return found


def run_find(html: str, queries: list[str], fail: bool = False) -> dict[str, Any]:
    script = SCRIPT.search(html)
    assert script
    places = json.loads(site.places_json(load().stations, site.place_names()))
    payload = {"script": script.group(1), "places": places, "queries": queries, "fail": fail}
    out = subprocess.run(  # noqa: S603 - our own harness, fixed arguments
        [node(), "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, check=True, timeout=60
    )
    result: dict[str, Any] = json.loads(out.stdout)
    return result


def test_find_box_matches_station_names(built: Path) -> None:
    home = (built / "index.html").read_text(encoding="utf-8")
    r = run_find(home, ["half moon", "maui", "a", "bay", "zzzz", "OCMD"])
    assert r["replaced"] and r["fetchesBefore"] == 0 and r["fetches"] == 1  # once, on first use
    half, maui, one, bay, none, ocmd = r["results"]
    assert half["status"] == "2 stations match."
    assert half["links"] == [
        ["/stations/9414131/", "Pillar Point Harbor, Half Moon Bay, CA"],
        ["/stations/9433445/", "Umpqua River Entrance, Half Moon Bay, OR"],
    ]
    assert maui["status"] == "1 station matches." and maui["links"] == [["/stations/1615680/", "Kahului, HI"]]
    assert one == {"status": "", "links": []}  # one letter is not a search yet
    assert re.fullmatch(r"The first 12 of \d+ stations that match\. Type more to narrow them\.", bay["status"])
    assert len(bay["links"]) == 12
    assert none["status"] == "No station name matches “zzzz”. Try a nearby town, or pick a state below."
    assert none["links"] == []
    assert ocmd["links"] == [["/stations/8570280/", "Ocean City (Fishing Pier), MD"]]


def test_find_box_says_when_the_list_does_not_load(built: Path) -> None:
    home = (built / "index.html").read_text(encoding="utf-8")
    r = run_find(home, ["bay"], fail=True)
    assert r["results"][0] == {
        "status": "The list of places did not load. The states below list every station.",
        "links": [],
    }
