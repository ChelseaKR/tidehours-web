"""Station names, titles and region labels (docs/DECISIONS.md 0020): NOAA's
misspellings, lost diacritics, casing and punctuation slips are corrected for
display, no two stations share a title, titles fit in 60 characters where they
can, and region labels read as names. URLs do not change."""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from tidehours import cli, names, site
from tidehours.catalog import DATA_DIR, Catalog, Station, load, tidy_name

NOW = "2026-11-01T11:20:00Z"
STATION = Station("0", "x", "ME", 43.0, -70.0, "America/New_York", None, "MAINE, outer coast")
# The indexed station titles still over 60 characters with the shortest tier.
LONG_INDEXED_TITLES = {"8447180", "8534319", "8668918", "9448614"}


@pytest.fixture(scope="module")
def cat() -> Catalog:
    return load()


def noaa_names() -> dict[str, str]:
    raw = json.loads((DATA_DIR / "stations.json").read_text(encoding="utf-8"))
    return {r["id"]: r["n"] for r in raw["harmonic"] + raw["subordinate"]}


def duplicate_titles(cat: Catalog) -> list[str]:
    counts = Counter(site.station_title(s.display_name) for s in cat.stations)
    return sorted(t for t, n in counts.items() if n > 1)


def test_every_fix_applies_to_the_bundled_names(cat: Catalog) -> None:
    # Each entry corrects the name NOAA gives now; one left behind by a data
    # refresh fails here instead of silently doing nothing.
    noaa = noaa_names()
    tables = (names.MISSPELLINGS, names.SPANISH, names.HAWAIIAN, names.CASING, names.PUNCTUATION, names.SAINT)
    assert [len(t) for t in tables] == [45, 5, 13, 12, 4, 8]
    assert len(names.DUPLICATES) == 6
    assert sum(len(t) for t in (*tables, names.DUPLICATES)) == len(names.NAME_FIXES) == 93
    for sid, (before, after) in names.NAME_FIXES.items():
        assert tidy_name(noaa[sid]) == before, sid
        st = cat.station(sid)
        assert st is not None and st.name == after != before, sid


def test_corrected_names(cat: Catalog) -> None:
    shown = {sid: cat.station(sid).display_name for sid in (  # type: ignore[union-attr]
        "8518934", "8638445", "9751584", "9759421", "9759394", "1611400", "1611347", "1612480", "8448157",
        "9448614", "9751082", "8728912", "9439201", "8412581", "8578465", "8772440", "8772471", "9451317",
        "9455606", "8542885", "8543024", "8724224", "8724223", "9451095",
    )}  # fmt: skip
    assert shown == {
        "8518934": "Beacon, Hudson River, NY",
        "8638445": "Lanexa, Chickahominy River, VA",
        "9751584": "Frederiksted, St. Croix, VI",
        "9759421": "Punta Guanajibo, Mayagüez, PR",
        "9759394": "Mayagüez, PR",
        "1611400": "Nāwiliwili, HI",
        "1611347": "Port Allen, Hanapēpē Bay, HI",
        "1612480": "Moku o Loe, HI",
        "8448157": "Vineyard Haven, Vineyard Haven Harbor, MA",
        "9448614": "Deception Pass State Park, Bowman Bay, Fidalgo I., WA",
        "9751082": "Grapetree Bay, St. Croix, VI",
        "8728912": "Port St. Joe, St. Joseph Bay, FL",
        "9439201": "St. Helens, OR",
        "8412581": "Milbridge, Narraguagus River, Maine",
        "8578465": "Coltons Point, Md.",
        "8772440": "Freeport, TX",
        "8772471": "Freeport Harbor, TX",
        "9451317": "Anchor Point, Wrangell Narrows, AK",
        "9455606": "Anchor Point, Cook Inlet, AK",
        "8542885": "Tinicum National Wildlife Refuge 4, PA",
        "8543024": "Tinicum National Wildlife Refuge 3, PA",
        "8724224": "Little Torch Key, FL",
        "8724223": "Little Torch Key, Pine Channel Bridge, south side, FL",
        "9451095": "Port Protection, Prince of Wales Island, AK",
    }


def test_no_two_stations_share_a_title(cat: Catalog) -> None:
    assert duplicate_titles(cat) == []


def test_without_the_fixes_the_duplicates_and_misspellings_return(monkeypatch: pytest.MonkeyPatch) -> None:
    # Negative control: the corrections are what tell the four pairs apart
    # and fix the spelling; with the table empty, both come back.
    monkeypatch.setattr(names, "NAME_FIXES", {})
    bare = load()
    assert duplicate_titles(bare) == [
        "Anchor Point, AK tide times today | Tide Hours",
        "Freeport Harbor, TX tide times today | Tide Hours",
        "Little Torch Key, Pine Channel Bridge, south side, FL tide times",
        "Tinicum National Wildlife Refuge, PA tide times today",
    ]
    assert bare.station("8638445").name == "Lanexa, Chicahomny River"  # type: ignore[union-attr]
    assert bare.station("1611400").name == "Nawiliwili"  # type: ignore[union-attr]


def test_a_fix_stops_when_noaa_changes_the_name() -> None:
    assert names.fixed_name("8518934", "Beacon, Flushkill") == "Beacon, Hudson River"
    assert names.fixed_name("8518934", "Beacon, Fishkill Creek") == "Beacon, Fishkill Creek"
    assert names.fixed_name("9414290", "San Francisco (Golden Gate)") == "San Francisco (Golden Gate)"


def test_saint_is_written_st(cat: Catalog) -> None:
    for s in cat.stations:
        assert not re.search(r"\bSaint |\bSt (?=[A-Z])|\bSt\.(?=[A-Za-z])|\bSt, ", s.name), s.id


def test_title_tiers() -> None:
    assert site.station_title("Monterey, CA") == "Monterey, CA tide times today | Tide Hours"
    name30 = "x" * 30  # 30 + 30 = 60: the brand still fits
    assert site.station_title(name30) == name30 + " tide times today | Tide Hours"
    assert site.station_title(name30 + "y") == name30 + "y tide times today"
    name43 = "x" * 43  # 43 + 17 = 60
    assert site.station_title(name43) == name43 + " tide times today"
    assert site.station_title(name43 + "y") == name43 + "y tide times"
    assert site.station_title("x" * 70) == "x" * 70 + " tide times"


def test_titles_fit(cat: Catalog) -> None:
    long = {s.id for s in cat.stations if not s.is_subordinate and len(site.station_title(s.display_name)) > 60}
    assert long == LONG_INDEXED_TITLES
    for sid in long:
        assert site.station_title(cat.station(sid).display_name).endswith(" tide times")  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("region", "state", "label"),
    [
        ("FLORIDA, East Coast", "Florida", "East Coast"),
        ("FLORIDA, St. Johns River", "Florida", "St. Johns River"),
        ("MAINE, outer coast-cont.", "Maine", "Outer Coast"),
        ("RHODE ISLAND, Outer Coast", "Rhode Island", "Outer Coast"),
        ("MAINE and NEW HAMPSHIRE", "New Hampshire", "Maine and New Hampshire"),
        ("CONNECTICUT, Long Island Sound", "New York", "Connecticut, Long Island Sound"),
        ("CONNECTICUT, Long Island Sound", "Connecticut", "Long Island Sound"),
        ("Gulf Coast-cont.", "Florida", "Gulf Coast"),
        ("Lower New York Bay, Raritan Bay, etc.", "New Jersey", "Lower New York Bay, Raritan Bay"),
        ("Portland Canal, etc.", None, "Portland Canal"),
        ("Hawaiin Islands", "Hawaii", "Hawaiian Islands"),
        ("St. Johns Island", "U.S. Virgin Islands", "St. John Island"),
        ("Chesapeake Bay, western shore", "Maryland", "Chesapeake Bay, Western Shore"),
        ("Chesapeake Bay, Western Shore-cont.", "Virginia", "Chesapeake Bay, Western Shore"),
        ("Long Island Sound, north side", "New York", "Long Island Sound, north side"),
        ("Texas", "Louisiana", "Texas"),
    ],
)
def test_region_label(region: str, state: str | None, label: str) -> None:
    assert site.region_label(region, state) == label


def test_region_urls_do_not_change(cat: Catalog) -> None:
    states = site.group(cat.stations)
    paths = {r.path: r.name for st in states for r in st.regions}
    assert paths["states/me/maine-outer-coast/"] == "Outer Coast (north)"
    assert paths["states/me/maine-outer-coast-cont/"] == "Outer Coast (south)"
    assert paths["states/hi/hawaiin-islands/"] == "Hawaiian Islands"
    assert paths["states/vi/st-johns-island/"] == "St. John Island"
    for st in states:
        for r in st.regions:
            assert r.slug == site.slug(r.stations[0].region or ""), r.path
            assert not re.search(r"[A-Z]{3,}|-cont\.|, etc\.|Hawaiin", r.name), r.path


def region_titles(states: list[site.State]) -> dict[str, list[str]]:
    # A region page's label and <title>, per state, as region.html.jinja
    # writes the title.
    out: dict[str, list[str]] = {}
    for st in states:
        place = "" if st.code == "other" else f", {st.name}"
        out[st.code] = [r.name for r in st.regions] + [f"{r.name}{place} tide times | Tide Hours" for r in st.regions]
    return out


def test_no_two_region_pages_in_a_state_share_a_label_or_title(cat: Catalog) -> None:
    for code, shown in region_titles(site.group(cat.stations)).items():
        assert sorted(t for t, n in Counter(shown).items() if n > 1) == [], code


def test_split_regions_are_told_apart_north_and_south(cat: Catalog) -> None:
    states = {st.code: st for st in site.group(cat.stations)}
    paths = {r.path: r for st in states.values() for r in st.regions}
    pairs = {
        "states/me/maine-outer-coast/": "Outer Coast (north)",
        "states/me/maine-outer-coast-cont/": "Outer Coast (south)",
        "states/sc/south-carolina-outer-coast/": "Outer Coast (north)",
        "states/sc/south-carolina-outer-coast-cont/": "Outer Coast (south)",
        "states/fl/gulf-coast-cont/": "Gulf Coast (north)",
        "states/fl/gulf-coast/": "Gulf Coast (south)",
        "states/nj/delaware-river-cont/": "Delaware River (north)",
        "states/nj/delaware-river/": "Delaware River (south)",
    }
    assert {p: paths[p].name for p in pairs} == pairs
    assert sorted(r.path for r in paths.values() if r.name.endswith(("(north)", "(south)"))) == sorted(pairs)
    # The label is true of NOAA's coordinates: every station of the north
    # part is north of every station of the south part.
    for south, north in zip(list(pairs)[1::2], list(pairs)[::2], strict=True):
        if "(south)" in paths[north].name:
            south, north = north, south
        assert max(s.lat for s in paths[south].stations) < min(s.lat for s in paths[north].stations)
    title = region_titles([states["ME"]])["ME"]
    assert "Outer Coast (north), Maine tide times | Tide Hours" in title


def test_without_tell_apart_the_region_pairs_share_labels(cat: Catalog, monkeypatch: pytest.MonkeyPatch) -> None:
    # Negative control: with the pairs left alone, four states show two
    # region pages with the same label and title.
    monkeypatch.setattr(site, "tell_apart", lambda code, regions: None)
    shared = {
        code: sorted({t for t, n in Counter(shown).items() if n > 1 and "|" not in t})
        for code, shown in region_titles(site.group(cat.stations)).items()
    }
    assert {c: v for c, v in shared.items() if v} == {
        "FL": ["Gulf Coast"],
        "ME": ["Outer Coast"],
        "NJ": ["Delaware River"],
        "SC": ["Outer Coast"],
    }


def _region(code: str, label: str, slug: str, *lats: float) -> site.Region:
    return site.Region(code, label, slug, [dataclasses.replace(STATION, lat=lat) for lat in lats])


def test_tell_apart_refuses_parts_that_overlap() -> None:
    a = _region("ME", "Outer Coast", "a", 43.0, 43.5)
    b = _region("ME", "Outer Coast", "b", 43.4, 44.0)
    with pytest.raises(ValueError, match="overlap north to south"):
        site.tell_apart("ME", [a, b])
    c = _region("ME", "Outer Coast", "c", 45.0)
    with pytest.raises(ValueError, match="3 regions"):
        site.tell_apart("ME", [_region("ME", "Outer Coast", "a", 43.0), c, _region("ME", "Outer Coast", "d", 46.0)])


def test_st_john_station_names(cat: Catalog) -> None:
    vi = [s for s in cat.stations if s.region == "St. Johns Island"]
    assert len(vi) == 8
    assert [s.name for s in vi if "Johns" in s.name.replace("Johns Folly", "")] == []
    assert cat.station("9751373").name == "Coral Harbor, St. John"  # type: ignore[union-attr]
    assert cat.station("9751309").name == "Leinster Point, Leinster Bay, St. John Island"  # type: ignore[union-attr]


def test_station_page_title_and_labels(built: Path) -> None:
    nawiliwili = (built / "stations/1611400/index.html").read_text(encoding="utf-8")
    assert "<title>Nāwiliwili, HI tide times today | Tide Hours</title>" in nawiliwili
    assert '<meta property="og:title" content="Nāwiliwili, HI tide times today | Tide Hours">' in nawiliwili
    assert "<h1>Nāwiliwili, HI tide times</h1>" in nawiliwili
    hawaii = (built / "states/hi/index.html").read_text(encoding="utf-8")
    assert '<a href="/states/hi/hawaiin-islands/">Hawaiian Islands</a>' in hawaii and "Hawaiin Islands" not in hawaii
    region = (built / "states/hi/hawaiin-islands/index.html").read_text(encoding="utf-8")
    assert "<title>Hawaiian Islands, Hawaii tide times | Tide Hours</title>" in region
    for f in built.glob("stations/*/index.html"):
        title = re.search(r"<title>([^<]*)</title>", f.read_text(encoding="utf-8"))
        assert title and (len(title.group(1)) <= 60 or title.group(1).endswith(" tide times")), f


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI"]) == 0
    return out


def test_split_region_stub_uses_the_label(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "UM,other"]) == 0
    stub = (out / "states/other/hawaiin-islands/index.html").read_text(encoding="utf-8")
    assert "<h1>Hawaiian Islands has moved</h1>" in stub and "Hawaiin" not in stub
