"""The built site: every page carries what the product promises (predictions
not observations, not for navigation, not a NOAA product, the NOAA credit,
the app marked "coming soon"), nothing absent renders as a value, and the
config switches (GA4, App Store link) do what they say."""

from __future__ import annotations

import dataclasses
import datetime as dt
import importlib.util
import json
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tidehours import catalog as catalog_mod
from tidehours import cli, site, tidetype
from tidehours.catalog import Station, load, tidy_name
from tidehours.days import feet, meters, no_negative_zero, station_day

NOW = "2026-11-01T11:20:00Z"  # US daylight saving time ends this day


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,HI,other"]) == 0
    return out


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def test_every_page_has_the_promises(built: Path) -> None:
    files = pages(built)
    assert len(files) > 250
    for f in files:
        html = f.read_text(encoding="utf-8")
        rel = f.relative_to(built)
        assert (
            "Predictions, not observations. Not for navigation." in html or "Predicciones, no observaciones" in html
        ), rel
        assert "not a NOAA product" in html or "no es un producto de NOAA" in html, rel
        assert "NOAA CO-OPS" in html, rel
        assert "Coming soon to the App Store" in html or "Próximamente en la App Store" in html, rel
        assert "apps.apple.com" not in html, rel
        assert "googletagmanager" not in html, rel
        assert "amazon" not in html.lower(), rel  # affiliate links are off by default (DECISIONS 0016)
        for bad in ("None", "nan ft", "NaN", "undefined", "{{", "{place}", "{id}"):
            assert bad not in re.sub(r"<script.*?</script>", "", html, flags=re.S), (rel, bad)
        assert re.search(r"<title>[^<]+</title>", html), rel
        assert '<html lang="' in html, rel


def test_station_pages(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "San Francisco (Golden Gate), CA tide times" in sf and "SAN FRANCISCO" not in sf
    assert "Sunday, November 1, 2026" in sf and "Monday, November 2, 2026" in sf
    assert sf.count('<svg class="tide-chart"') == 2
    assert "stroke-dasharray" not in sf
    assert "/king-tides/#station-9414290" in sf
    assert 'rel="canonical" href="https://tidehours.com/stations/9414290/"' in sf
    assert "noaatidepredictions.html?id=9414290" in sf
    # The golden fixture's NOAA low at 2026-11-01 05:56Z is 22:56 PDT on Oct 31,
    # and the high at 13:40Z is 5:40 AM PST on Nov 1.
    assert ">5:40 AM</time>" in sf
    sub = (built / "stations/9413878/index.html").read_text(encoding="utf-8")
    assert "from a nearby reference station" in sub and 'href="/stations/9414290/"' in sub
    assert "stroke-dasharray" in sub


def test_indexes_sitemap_robots(built: Path) -> None:
    home = (built / "index.html").read_text(encoding="utf-8")
    assert "only some states" in home
    assert 'href="/states/ca/"' in home and 'href="/states/other/"' in home
    ca = (built / "states/ca/index.html").read_text(encoding="utf-8")
    assert 'href="/states/ca/san-francisco-bay/"' in ca
    other = (built / "states/other/index.html").read_text(encoding="utf-8")
    assert "have no state on this site" in other
    urls = [
        el.text
        for el in ET.parse(built / "sitemap.xml")  # noqa: S314 - our own build output
        .getroot()
        .iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    ]
    noindex = [f for f in pages(built) if 'name="robots" content="noindex' in f.read_text(encoding="utf-8")]
    stub = '<meta http-equiv="refresh"'
    thin = {"/" + r.path for st in site.group(load().stations) for r in st.regions if not site.region_indexable(r)}
    for f in noindex:
        rel = "/" + f.parent.relative_to(built).as_posix() + "/"
        assert f.parts[-3] == "stations" or stub in f.read_text(encoding="utf-8") or rel in thin, rel
    assert any("/" + f.parent.relative_to(built).as_posix() + "/" in thin for f in noindex)  # DECISIONS 0022
    assert len(urls) == len(pages(built)) - 1 - len(noindex)  # every indexable page but 404.html
    assert "https://tidehours.com/es/king-tides/" in urls
    assert "Sitemap: https://tidehours.com/sitemap.xml" in (built / "robots.txt").read_text(encoding="utf-8")
    assert (built / "style.css").exists()


def test_king_tide_pages(built: Path) -> None:
    en = (built / "king-tides/index.html").read_text(encoding="utf-8")
    es = (built / "es/king-tides/index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in en and '<html lang="es">' in es
    assert "Nov 23–26, 2026" in en or "Nov 24–26, 2026" in en
    assert 'hreflang="es"' in en and 'hreflang="en"' in es
    assert en.count('class="kt-station"') == 31 and es.count('class="kt-station"') == 31
    assert "pies" in es and " ft<" not in es


def test_privacy_and_analytics_switch(tmp_path: Path, built: Path) -> None:
    assert "collects nothing about you" in (built / "privacy/index.html").read_text(encoding="utf-8")
    out = tmp_path / "ga"
    cli.main(["--out", str(out), "--now", NOW, "--states", "GU", "--ga4-id", "G-TEST123",
              "--app-store-url", "https://apps.apple.com/app/id1"])  # fmt: skip
    priv = (out / "privacy/index.html").read_text(encoding="utf-8")
    assert "Google Analytics 4" in priv and "G-TEST123" in priv
    station = next(out.glob("stations/*/index.html")).read_text(encoding="utf-8")
    assert "https://apps.apple.com/app/id1" in station and "Coming soon" not in station
    assert 'id="analytics-opt-out"' in station


def test_cli_refuses_bad_input(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--out", str(tmp_path), "--ga4-id", "UA-1"])
    with pytest.raises(SystemExit):
        cli.main(["--out", str(tmp_path), "--app-store-url", "http://example.com"])
    with pytest.raises(SystemExit):
        cli.main(["--out", str(tmp_path), "--now", "2026-11-01T11:20:00"])
    with pytest.raises(ValueError, match="no stations"):
        cli.main(["--out", str(tmp_path), "--states", "ZZ"])
    assert cli.parse_now(None).tzinfo is not None


def test_formatting() -> None:
    assert feet(-0.04) == "0.0 ft"
    assert feet(-0.36) == "−0.4 ft"
    assert meters(5.4) == "1.65 m"
    assert no_negative_zero(-0.004, 2) == 0.0


def test_day_without_events_or_curve() -> None:
    """Absence renders as a sentence, never as a height."""

    class Flat:
        def events(self, start: float, end: float) -> list[object]:
            return []

        def curve(self, start: float, end: float, step: float) -> list[tuple[float, float]]:
            return []

    s = Station("1", "Nowhere", "CA", 0.0, 0.0, "America/Los_Angeles", "2", None)
    day = station_day(s, Flat(), dt.date(2026, 11, 1))  # type: ignore[arg-type]
    assert day.events == [] and day.svg is None
    assert day.summary() == "no high or low tide predicted"


def test_grouping_and_nearby() -> None:
    cat = load()
    states = site.group(cat.stations)
    assert sum(st.count for st in states) == len(cat.stations) == 3256
    assert states[-1].code == "other"
    s = cat.station("9414290")
    assert s is not None
    fast = site.Nearby(cat.stations)(s)
    slow = site.nearby(s, cat.stations)
    assert [x.id for x, _ in fast] == [x.id for x, _ in slow]
    assert site.slug("Outer Coast, San Francisco") == "outer-coast-san-francisco"
    with pytest.raises(ValueError, match="timezone-aware"):
        site.render(cat, site.Config(), dt.datetime(2026, 11, 1))


# The U.S. Virgin Islands stations NOAA's own metadata codes PR (the mdapi
# station record's "state" field, checked 2026-11-05), though each sits on
# St. Croix, St. John or St. Thomas by its coordinates and its NOAA region.
USVI_CODED_PR = {
    "9751082", "9751084", "9751219", "9751274", "9751389", "9751417",
    "9751419", "9751472", "9751561", "9751574", "9751693", "9751749",
}  # fmt: skip


def in_usvi(s: Station) -> bool:
    # St. Thomas, St. John and St. Croix; Culebra (PR) is west of -65.1.
    return 17.6 <= s.lat <= 18.45 and -65.1 <= s.lon <= -64.55


def test_no_virgin_islands_station_is_under_puerto_rico() -> None:
    raw = json.loads((catalog_mod.DATA_DIR / "stations.json").read_text(encoding="utf-8"))
    noaa_state = {r["id"]: r["st"] for r in raw["harmonic"] + raw["subordinate"]}
    cat = load()
    vi = {s.id for s in cat.stations if s.state == "VI"}
    for s in cat.stations:
        if noaa_state[s.id] == "VI" or s.id in USVI_CODED_PR or in_usvi(s) or s.region in catalog_mod.USVI_REGIONS:
            assert s.state == "VI" and s.tz == "America/St_Thomas", s
        if s.state == "PR":
            assert not in_usvi(s) and s.tz == "America/Puerto_Rico", s
    assert vi >= USVI_CODED_PR
    assert {i for i, st in noaa_state.items() if st == "VI"} <= vi
    assert {i for i in USVI_CODED_PR if noaa_state[i] == "PR"} == USVI_CODED_PR  # still NOAA's coding
    # PR: 35 NOAA-coded, plus 4 NOAA lists without a state, filed by reference station (0018).
    assert len(vi) == 25 and sum(s.state == "PR" for s in cat.stations) == 39
    assert catalog_mod.territory("PR", "America/Puerto_Rico", "Puerto Rico") == ("PR", "America/Puerto_Rico")
    assert catalog_mod.territory("PR", "America/Puerto_Rico", "St. Croix Island") == ("VI", "America/St_Thomas")


def test_virgin_islands_pages(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "PR,VI"]) == 0
    pr = (out / "states/pr/index.html").read_text(encoding="utf-8")
    vi = (out / "states/vi/index.html").read_text(encoding="utf-8")
    assert "Cruz Bay" not in pr and "St. Croix" not in pr and 'href="/states/pr/puerto-rico/"' in pr
    assert 'href="/states/vi/st-johns-island/"' in vi and "U.S. Virgin Islands" in vi
    for old, new in site.MOVED_REGIONS.items():  # each old PR island page sends visitors to the VI one
        stub = (out / old / "index.html").read_text(encoding="utf-8")
        assert f'<meta http-equiv="refresh" content="0; url=/{new}">' in stub, old
        assert f'<link rel="canonical" href="https://tidehours.com/{new}">' in stub, old
        assert f'<a href="/{new}">' in stub and 'content="noindex,follow"' in stub, old
        assert (out / new / "index.html").is_file(), new
        assert f"https://tidehours.com/{old}" not in (out / "sitemap.xml").read_text(encoding="utf-8")
    assert len(site.MOVED_REGIONS) == 3
    cruz = (out / "stations/9751472/index.html").read_text(encoding="utf-8")  # the station URL is unchanged
    assert "Cruz Bay, St. John, VI" in cruz and "America/St_Thomas" in cruz
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://tidehours.com/states/vi/st-croix-island/" in sitemap
    assert "/states/pr/st-" not in sitemap


# Stations NOAA lists without a state whose position rules out their
# reference station's state (DECISIONS 0018), checked by hand on 2026-11-05.
STILL_WITHOUT_STATE = {
    "8218447": "AK",  # Wales Island (Cannery), Pearse Canal: British Columbia
    "8659899": "SC",  # Sunset Beach Bridge: North Carolina
    "8748038": "LA",  # Wolf River, Henderson Avenue bridge: Mississippi
    "TEC3327": "GA",  # Euhaw Creek, Broad River: South Carolina
    "TEC3531": "FL",  # Below Spring Bluff, Little Satilla River: Georgia
    "TEC3541": "FL",  # Burnt Fort, Satilla River: Georgia
    "TWC0817": "CA",  # Wedderburn, Rogue River: Oregon
    "TWC0857": "CA",  # Nestucca Bay entrance: Oregon
    "TWC0863": "CA",  # Miami Cove, Tillamook Bay: Oregon
    "TWC0865": "CA",  # Bay City, Tillamook Bay: Oregon
}
# Filed by the state their NOAA name ends in, which beats the reference
# station's (Harrington Point is predicted from Astoria, OR; Clifton Beach
# from Washington, DC).
FILED_BY_NAME = {"8578931": "MD", "TWC0881": "OR", "TWC0883": "OR", "TWC0895": "WA"}
# NOAA codes this Saipan station GU; it is the one NOAA-coded station outside
# its own state's border checks.
NOAA_CODED_ACROSS_BORDER = {"1633227"}


def test_stations_without_a_state_are_filed() -> None:
    raw = json.loads((catalog_mod.DATA_DIR / "stations.json").read_text(encoding="utf-8"))
    noaa = {r["id"]: r["st"] for r in raw["harmonic"] + raw["subordinate"]}
    cat = load()
    by_id = {s.id: s for s in cat.stations}
    assert sum(noaa[s.id] == "" for s in cat.stations) == 194
    for s in cat.stations:
        assert s.noaa_state == noaa[s.id]
        if s.filed_by == "correction":
            assert s.state == catalog_mod.STATE_CORRECTIONS[s.id][0] != s.noaa_state, s
        elif noaa[s.id]:
            assert s.filed_by is None, s
        elif s.filed_by == "territory":
            assert s.state == catalog_mod.TERRITORY_STATES[s.id], s
        elif s.filed_by == "place":
            assert s.state == catalog_mod.PLACE_STATES[s.id][0], s
        elif s.filed_by == "name":
            assert s.state == FILED_BY_NAME[s.id] == catalog_mod.name_state(s.name), s
        elif s.filed_by == "reference":
            ref = by_id[s.reference_id or ""]
            assert s.state == ref.state != "" and catalog_mod.across_border(s.state, s.lat, s.lon) is None, s
        else:
            assert s.state == "" and catalog_mod.across_border(STILL_WITHOUT_STATE[s.id], s.lat, s.lon), s
    filed = Counter(s.filed_by for s in cat.stations)
    assert (filed["territory"], filed["place"], filed["name"], filed["reference"], filed["correction"]) == (
        10,
        1,
        4,
        169,
        2,
    )
    chelsea = by_id["TEC1645"]  # Staten Island, though its reference station (Sandy Hook) is NJ
    assert (chelsea.state, chelsea.filed_by, by_id[chelsea.reference_id or ""].state) == ("NY", "place", "NJ")
    assert chelsea.correction_note is not None and "Staten Island" in chelsea.correction_note
    assert {s.id for s in cat.stations if s.state == ""} == set(STILL_WITHOUT_STATE) | {"1778000"}  # and Apia
    for sid, code in STILL_WITHOUT_STATE.items():  # each would take this state without the border check
        assert by_id[by_id[sid].reference_id or ""].state == code, sid
    named = {"TEC2789": "NC", "TEC2793": "NC", "8723667": "FL", "1630000": "GU", "1631428": "GU", "1890000": "UM"}
    assert {sid: by_id[sid].state for sid in named} == named  # Cape Hatteras, Ocracoke, Key Largo, Guam, Wake
    assert {s.id for s in cat.stations if s.state == "GU"} == {"1630000", "1631428"}
    assert {s.id for s in cat.stations if s.state == "MP"} == {"1633227", "TPT2621", "TPT2623", "TPT2625", "TPT2627"}
    assert all(s.region == "Northern Marianas Islands" for s in cat.stations if s.state == "MP")
    assert {by_id[i].region for i in ("1630000", "1631428")} == {"Guam"}
    assert [by_id[i].region for i in ("1619000", "1619910", "1890000")] == [
        "Johnston Atoll",
        "Midway Islands",
        "Wake Island",
    ]
    apia = by_id["1778000"]
    assert (apia.state, apia.noaa_state, apia.tz) == ("", "AS", "Pacific/Apia")  # independent Samoa, UTC+13
    assert apia.correction_note is not None and "independent Samoa" in apia.correction_note
    assert by_id["TWC2303"].display_name == "Constantine Harbor, Amchitka Island, AK"


def test_western_aleutians_keep_daylight_saving_time() -> None:
    # NOAA's UTC-10 offset put these AK-filed stations in Pacific/Honolulu,
    # which has no daylight saving time; Adak's clock is UTC-9 in summer.
    cat = load()
    aleutian = [s for s in cat.stations if s.filed_by and s.state == "AK" and s.tz == "America/Adak"]
    assert len(aleutian) == 10 and not any(s.tz == "Pacific/Honolulu" for s in cat.stations if s.state == "AK")
    kiska = cat.station("TWC2307")  # Kiska Harbor, Kiska Island
    assert kiska is not None and kiska.tz == "America/Adak"
    summer = station_day(kiska, cat.predictor(kiska.id), dt.date(2027, 7, 1))
    winter = station_day(kiska, cat.predictor(kiska.id), dt.date(2027, 1, 15))
    assert summer.events and all(e.iso.endswith("-09:00") for e in summer.events)
    assert winter.events and all(e.iso.endswith("-10:00") for e in winter.events)
    # Negative control: the old zone shows the same summer tides an hour earlier.
    old = station_day(dataclasses.replace(kiska, tz="Pacific/Honolulu"), cat.predictor(kiska.id), dt.date(2027, 7, 1))
    first_old = dt.datetime.fromisoformat(old.events[0].iso)
    match = [dt.datetime.fromisoformat(e.iso) for e in summer.events if dt.datetime.fromisoformat(e.iso) == first_old]
    assert match and match[0].hour == (first_old.hour + 1) % 24


def test_display_name_does_not_repeat_the_state() -> None:
    cat = load()
    names = {i: cat.station(i).display_name for i in ("1630000", "1631428", "TWC0881", "8539487", "8594900", "1890000", "1633227")}  # type: ignore[union-attr]  # fmt: skip
    assert names == {
        "1630000": "Apra Harbor, Guam",
        "1631428": "Pago Bay, Guam",
        "TWC0881": "Point Adams, Oreg.",
        "8539487": "Fieldsboro, N.J.",
        "8594900": "Washington, Washington Channel, D.C.",
        "1890000": "Wake Island, UM",
        "1633227": "Tanapag Harbor, Saipan Island, MP",
    }
    for s in cat.stations:
        if s.state:
            assert s.display_name.endswith(", " + s.state) or catalog_mod.name_state(s.display_name) == s.state, s
    # A name's other words are not a suffix: "N.C. State Fisheries" still gets ", NC".
    assert cat.station("TEC2831").display_name == "N.C. State Fisheries, NC"  # type: ignore[union-attr]
    assert (
        Station("1", "Chesapeake City, Maryland", "MD", 0, 0, "UTC", None, None).display_name
        == "Chesapeake City, Maryland"
    )
    assert Station("1", "Burlington, N.J.", "PA", 0, 0, "UTC", None, None).display_name == "Burlington, N.J., PA"


def test_border_checks() -> None:
    raw = json.loads((catalog_mod.DATA_DIR / "stations.json").read_text(encoding="utf-8"))
    # Every station NOAA itself codes with a state passes that state's checks,
    # so they are not tighter than NOAA's own coding.
    across = {
        r["id"] for r in raw["harmonic"] + raw["subordinate"] if catalog_mod.across_border(r["st"], r["la"], r["lo"])
    }
    assert across == NOAA_CODED_ACROSS_BORDER
    # The checks apply: points just over each border fail, just inside pass.
    over = [("WA", 49.01, -122.75), ("WA", 48.45, -123.4), ("AK", 54.77, -130.55), ("CA", 42.01, -124.2),
            ("OR", 46.27, -123.65), ("FL", 30.95, -81.9), ("GA", 32.43, -80.85), ("SC", 33.88, -78.51),
            ("LA", 30.36, -89.27), ("DC", 38.41, -77.27), ("GU", 15.2, 145.72), ("MP", 13.44, 144.66)]  # fmt: skip
    inside = [("WA", 48.99, -122.75), ("WA", 48.37, -124.6), ("AK", 54.94, -130.34), ("CA", 41.99, -124.2),
              ("OR", 46.2, -123.95), ("FL", 30.79, -81.84), ("GA", 32.08, -81.09), ("SC", 33.1, -78.43),
              ("LA", 29.26, -89.96), ("DC", 38.87, -77.02), ("GU", 13.44, 144.66), ("MP", 15.2, 145.72)]  # fmt: skip
    assert all(catalog_mod.across_border(*p) for p in over)
    assert not any(catalog_mod.across_border(*p) for p in inside)
    assert catalog_mod.across_border("WA", 49.5, -123.0) == "British Columbia (49th parallel)"
    assert catalog_mod.across_border("ME", 47.0, -68.0) is None  # no checks for a state means no veto


def test_without_the_border_check_wales_island_would_be_alaska(monkeypatch: pytest.MonkeyPatch) -> None:
    # Negative control: the border check is what keeps a British Columbia
    # station off the Alaska page.
    s = load().station("8218447")
    assert s is not None and s.state == ""
    monkeypatch.setattr(catalog_mod, "BORDERS", ())
    s = load().station("8218447")
    assert s is not None and s.state == "AK" and s.filed_by == "reference"


def test_filed_stations_pages(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "NC,GU,MP,UM,other"]) == 0
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    nc = (out / "states/nc/index.html").read_text(encoding="utf-8")
    assert 'href="/stations/TEC2789/"' in nc and 'href="/states/nc/outer-banks/"' in nc
    hatteras = (out / "stations/TEC2789/index.html").read_text(encoding="utf-8")
    assert "Cape Hatteras, NC tide times" in hatteras
    assert "listed under North Carolina, the state of the reference station" in hatteras
    apra = (out / "stations/1630000/index.html").read_text(encoding="utf-8")
    assert "<h1>Apra Harbor, Guam tide times</h1>" in apra and "where NOAA's station name places it" in apra
    assert 'href="/states/gu/guam/"' in apra and "Northern Marianas" not in apra
    tanapag = (out / "stations/1633227/index.html").read_text(encoding="utf-8")
    assert "codes this station GU. Tanapag Harbor is on Saipan" in tanapag
    apia = (out / "stations/1778000/index.html").read_text(encoding="utf-8")
    assert "codes this station AS. Apia is in independent Samoa" in apia and "Pacific/Apia" in apia
    um = (out / "states/um/index.html").read_text(encoding="utf-8")
    assert "U.S. Minor Outlying Islands" in um and "Hawaiin" not in um
    assert "Northern Mariana Islands" in (out / "states/mp/index.html").read_text(encoding="utf-8")
    other = (out / "states/other/index.html").read_text(encoding="utf-8")
    assert "Cape Hatteras" not in other and "Wales Island" in other and "Saipan" not in other and "Apia" in other
    for old, new, where in [
        ("states/other/outer-banks/", "states/nc/outer-banks/", "North Carolina"),  # was a live region page
        ("states/gu/northern-marianas-islands/", "states/mp/northern-marianas-islands/", "Northern Mariana Islands"),
        ("states/other/marshall-islands/", "states/um/wake-island/", "U.S. Minor Outlying Islands"),
    ]:
        stub = (out / old / "index.html").read_text(encoding="utf-8")
        assert f'<meta http-equiv="refresh" content="0; url=/{new}">' in stub, old
        assert 'content="noindex,follow"' in stub and f"listed under {where}" in stub, old
        assert f"https://tidehours.com/{old}" not in sitemap, old
        # The new page is in the sitemap unless it is a thin region (DECISIONS 0022):
        # Wake Island is one station, so its region page is noindex.
        listed = f"https://tidehours.com/{new}" in sitemap
        assert listed == (new != "states/um/wake-island/"), new
        assert listed != ('content="noindex,follow"' in (out / new / "index.html").read_text(encoding="utf-8")), new
    # A region that split lists each part, with its stations, and sends no one
    # to just one of them (Midway is not Johnston Atoll; Guam is not the CNMI).
    for old, parts in [
        (
            "states/other/hawaiin-islands/",
            {"states/um/johnston-atoll/": ["1619000"], "states/um/midway-islands/": ["1619910"]},
        ),
        (
            "states/other/northern-marianas-islands/",
            {
                "states/gu/guam/": ["1630000", "1631428"],
                "states/mp/northern-marianas-islands/": ["TPT2621", "TPT2623", "TPT2625", "TPT2627"],
            },
        ),
    ]:
        split = (out / old / "index.html").read_text(encoding="utf-8")
        assert "http-equiv" not in split and 'content="noindex,follow"' in split, old
        assert f'<link rel="canonical" href="https://tidehours.com/{old}">' in split, old
        assert "now listed in 2 places" in split and f"https://tidehours.com/{old}" not in sitemap, old
        sections = [p.split("</section>")[0] for p in split.split('aria-labelledby="to-')[1:]]
        assert len(sections) == len(parts), old
        for section, (new, ids) in zip(sections, parts.items(), strict=True):
            assert f'href="/{new}"' in section, new
            assert sorted(re.findall(r'href="/stations/([^/]+)/"', section)) == ids, new
    assert "Johnston Atoll, U.S. Minor Outlying Islands" in (out / "states/other/hawaiin-islands/index.html").read_text(
        encoding="utf-8"
    )
    # A region that still has a station without a state keeps its own page, not a stub.
    southeast = (out / "states/other/southeast-coast/index.html").read_text(encoding="utf-8")
    assert "http-equiv" not in southeast and "Sunset Beach Bridge" in southeast


def test_group_rejects_unknown_state() -> None:
    with pytest.raises(ValueError, match="no name"):
        site.group([Station("1", "X", "ZZ", 0, 0, "UTC", None, "R")])


def test_terms_page_and_footer_link(tmp_path: Path, built: Path) -> None:
    terms = (built / "terms/index.html").read_text(encoding="utf-8")
    text = " ".join(re.sub(r"<[^>]+>", " ", terms).split())
    for want in (
        "Chelsea Kelly-Reif",
        "chelsea@chelseakr.com",
        "The predictions are not for navigation.",
        "not a NOAA product",
        "laws of the State of California",
        "will be sold through",
    ):
        assert want in text, want
    assert len(text.split()) < 700
    for f in built.rglob("*.html"):
        if f.name != "404.html":
            assert '<a href="/terms/">' in f.read_text(encoding="utf-8"), f
    es = (built / "es/king-tides/index.html").read_text(encoding="utf-8")
    assert '<a href="/terms/">Términos de uso</a>' in es
    assert "/terms/</loc>" in (built / "sitemap.xml").read_text(encoding="utf-8")
    out = tmp_path / "live"
    cli.main(["--out", str(out), "--now", NOW, "--states", "GU",
              "--app-store-url", "https://apps.apple.com/app/id1"])  # fmt: skip
    assert "app is sold through" in " ".join((out / "terms/index.html").read_text(encoding="utf-8").split())


def test_tidy_name() -> None:
    assert tidy_name("SAN FRANCISCO (Golden Gate)") == "San Francisco (Golden Gate)"
    assert tidy_name("PORT O'CONNOR, MATAGORDA BAY") == "Port O'Connor, Matagorda Bay"
    assert tidy_name("CHARLOTTE AMALIE, ST. THOMAS ISLAND") == "Charlotte Amalie, St. Thomas Island"
    # Abbreviations stay in capitals; names already in mixed case are untouched.
    assert tidy_name("VACA KEY, USCG STATION, FLORIDA BAY") == "Vaca Key, USCG Station, Florida Bay"
    assert tidy_name("Shinn Point, ICWW") == "Shinn Point, ICWW"
    assert tidy_name("Cox WC-53 Platform") == "Cox WC-53 Platform"
    assert tidy_name("Seaside Heights, N.J.") == "Seaside Heights, N.J."


def test_subordinate_pages_are_noindex_and_out_of_the_sitemap(built: Path) -> None:
    """DECISIONS 0013: a subordinate station's page is served and linked but
    asks not to be indexed, and is in neither the sitemap nor lastmod.json
    (so IndexNow never announces it); a harmonic station's page is indexed."""
    robots = '<meta name="robots" content="noindex,follow">'
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    manifest = json.loads((built / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    sub = (built / "stations/9413878/index.html").read_text(encoding="utf-8")
    assert robots in sub
    assert "/stations/9413878/<" not in sitemap and "/stations/9413878/" not in manifest
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "noindex" not in sf
    assert "https://tidehours.com/stations/9414290/</loc>" in sitemap and "/stations/9414290/" in manifest
    # The reference page links each station predicted from it, with its time corrections.
    assert "Stations predicted from this one" in sf and 'href="/stations/9413878/"' in sf
    assert re.search(r"high tide (at the same time|\d+ (h|min)[^,]* (later|earlier))", sf)
    cat = load()
    for f in built.glob("stations/*/index.html"):
        s = cat.station(f.parent.name)
        assert s is not None
        assert (robots in f.read_text(encoding="utf-8")) == s.is_subordinate == (not site.indexable(s)), s.id


def test_thin_region_pages_are_noindex_and_out_of_the_sitemap(built: Path) -> None:
    """DECISIONS 0022: a region page of one or two stations is served, linked
    from its state page and followed, but asks not to be indexed and is in
    neither the sitemap nor lastmod.json; its stations keep their own rule,
    so a harmonic station in a thin region is still indexed."""
    robots = '<meta name="robots" content="noindex,follow">'
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    manifest = json.loads((built / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    states = site.group([s for s in load().stations if (s.state or site.OTHER) in ("CA", "HI", "other")])
    regions = [r for st in states for r in st.regions]
    thin = [r for r in regions if len(r.stations) < 3]
    assert thin and len(thin) < len(regions)
    for st in states:
        state_page = (built / st.path / "index.html").read_text(encoding="utf-8")
        assert "noindex" not in state_page, st.path
        for r in st.regions:
            html = (built / r.path / "index.html").read_text(encoding="utf-8")
            assert f'rel="canonical" href="https://tidehours.com/{r.path}"' in html, r.path
            assert f'href="/{r.path}"' in state_page, r.path  # still linked
            listed = f"https://tidehours.com/{r.path}</loc>" in sitemap
            assert (robots in html) == (r in thin) == (not site.region_indexable(r)) == (not listed), r.path
            assert ("/" + r.path in manifest) == listed, r.path
            if r in thin:
                for s in r.stations:
                    assert f'href="/stations/{s.id}/"' in state_page, (r.path, s.id)
                    station = (built / "stations" / s.id / "index.html").read_text(encoding="utf-8")
                    assert (robots in station) == s.is_subordinate, s.id
    # The rule never holds back a harmonic station's own page; 34 sit in thin regions.
    full = [r for st in site.group(load().stations) for r in st.regions if not site.region_indexable(r)]
    assert any(not s.is_subordinate and site.indexable(s) for r in full for s in r.stations)
    sfbay = (built / "states/ca/san-francisco-bay/index.html").read_text(encoding="utf-8")
    assert "noindex" not in sfbay and "https://tidehours.com/states/ca/san-francisco-bay/</loc>" in sitemap


def test_check_site_catches_a_thin_region_mistake(tmp_path: Path, built: Path) -> None:
    """Negative control: the gate fails once a thin region page loses its
    noindex, and once a full region page gains one."""
    check: Any = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    stations = load().stations
    robots = '<meta name="robots" content="noindex,follow">'
    assert check.check_indexing(site_dir, sorted(site_dir.rglob("*.html")), stations) == []
    thin = site_dir / "states/hi/kahoolawe-island/index.html"
    html = thin.read_text(encoding="utf-8")
    assert robots in html
    thin.write_text(html.replace(robots, ""), encoding="utf-8")
    assert "noindex" not in thin.read_text(encoding="utf-8")  # the sabotage applied
    full = site_dir / "states/ca/san-francisco-bay/index.html"
    html = full.read_text(encoding="utf-8")
    full.write_text(html.replace("<head>", "<head>" + robots, 1), encoding="utf-8")
    assert robots in full.read_text(encoding="utf-8")  # the sabotage applied
    found: list[str] = check.check_indexing(site_dir, sorted(site_dir.rglob("*.html")), stations)
    assert "states/hi/kahoolawe-island/: a region of 2 station(s) needs noindex" in found
    assert any(
        p.startswith("states/ca/san-francisco-bay/: a region of") and p.endswith("needs no noindex") for p in found
    )
    assert any(p.startswith("sitemap lists") for p in found)


def test_offset_phrase() -> None:
    assert site.offset_phrase(0.2) == "at the same time"
    assert site.offset_phrase(12) == "12 min later"
    assert site.offset_phrase(-75) == "1 h 15 min earlier"
    assert site.offset_phrase(120) == "2 h later"


def _check_site() -> object:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_site_catches_an_indexing_mistake(tmp_path: Path, built: Path) -> None:
    """Negative control: the gate's noindex, sitemap and lastmod.json checks
    pass on the build and fail once a subordinate page loses its noindex."""
    check: Any = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    stations = load().stations

    def problems() -> list[str]:
        found: list[str] = check.check_indexing(site_dir, sorted(site_dir.rglob("*.html")), stations)
        return found

    assert problems() == []
    page = site_dir / "stations/9413878/index.html"
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace('<meta name="robots" content="noindex,follow">', ""), encoding="utf-8")
    assert "noindex" not in page.read_text(encoding="utf-8")  # the sabotage applied
    found = problems()
    assert "stations/9413878: a subordinate station needs noindex" in found
    assert any(p.startswith("sitemap lists") for p in found)
    assert any(p.startswith("lastmod.json lists") for p in found)


def test_tide_type_thresholds() -> None:
    """NOAA's Tide and Current Glossary, "type of tide": F under 0.25,
    0.25 to 1.5, 1.5 to 3.0, over 3.0 (DECISIONS 0014)."""
    assert tidetype.classify(0.0) is tidetype.SEMI
    assert tidetype.classify(0.24) is tidetype.SEMI
    assert tidetype.classify(0.25) is tidetype.MIXED_SEMI
    assert tidetype.classify(1.49) is tidetype.MIXED_SEMI
    assert tidetype.classify(1.5) is tidetype.MIXED_DIURNAL
    assert tidetype.classify(3.0) is tidetype.MIXED_DIURNAL
    assert tidetype.classify(3.01) is tidetype.DIURNAL_KIND
    t = tidetype.tide_type({"K1": 0.5, "O1": 0.3, "M2": 1.5, "S2": 0.5})
    assert t is not None and t.form_factor == 0.4 and t.kind is tidetype.MIXED_SEMI
    # Classified as shown, to 2 decimals: 0.2466 shows as 0.25, so it is mixed.
    t = tidetype.tide_type({"K1": 0.1233, "O1": 0.0, "M2": 0.5, "S2": 0.0})
    assert t is not None and t.form_factor == 0.25 and t.kind is tidetype.MIXED_SEMI
    # Nothing is guessed: a missing constituent or no semidiurnal tide gives no type.
    assert tidetype.tide_type({"K1": 0.1, "O1": 0.1, "M2": 0.5}) is None
    assert tidetype.tide_type({"K1": 0.1, "O1": 0.1, "M2": 0.0, "S2": 0.0}) is None
    assert len({k.key for k in tidetype.KINDS}) == 4


def test_tide_type_from_the_catalog() -> None:
    cat = load()
    expect = {
        "8443970": "semidiurnal",  # Boston, F 0.16
        "9414290": "mixed-semidiurnal",  # San Francisco, F 0.84
        "8771450": "mixed-diurnal",  # Galveston, F 2.33
        "8729840": "diurnal",  # Pensacola, F 11.25
    }
    for sid, key in expect.items():
        t = cat.tide_type(sid)
        assert t is not None and t.kind.key == key, sid
    sf = cat.tide_type("9414290")
    assert sf is not None and sf.form_factor == 0.84
    # NOAA's constants for Pungo River, NC list no S2: no type, not a guess.
    assert cat.tide_type("8653244") is None
    # Subordinate stations have no constants of their own.
    assert cat.tide_type("9413878") is None
    harmonic = [s for s in cat.stations if not s.is_subordinate]
    typed = [s for s in harmonic if cat.tide_type(s.id) is not None]
    assert len(harmonic) == 1232 and len(typed) == 1230


def test_station_page_tide_type(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert 'data-tide-type="mixed-semidiurnal"' in sf
    assert "Type of tide: mixed, mainly semidiurnal" in sf
    assert "two high tides and two low tides a day, but of different heights" in sf
    assert "(K1 + O1) / (M2 + S2) is 0.84" in sf
    sub = (built / "stations/9413878/index.html").read_text(encoding="utf-8")
    assert "data-tide-type" not in sub and "Type of tide" not in sub


def test_check_site_catches_a_wrong_tide_type(tmp_path: Path, built: Path) -> None:
    """Negative control: the gate's type-of-tide check passes on the build and
    fails when a page shows the wrong type, or one where there is none."""
    check: Any = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    cat = load()
    assert check.check_tide_types(site_dir, cat) == []
    sf = site_dir / "stations/9414290/index.html"
    sf.write_text(
        sf.read_text(encoding="utf-8").replace('data-tide-type="mixed-semidiurnal"', 'data-tide-type="diurnal"')
    )
    assert 'data-tide-type="diurnal"' in sf.read_text(encoding="utf-8")  # the sabotage applied
    sub = site_dir / "stations/9413878/index.html"
    sub.write_text(sub.read_text(encoding="utf-8").replace("<main", '<main data-tide-type="semidiurnal"', 1))
    assert 'data-tide-type="semidiurnal"' in sub.read_text(encoding="utf-8")  # applied
    found = check.check_tide_types(site_dir, cat)
    assert "stations/9414290: type of tide ['diurnal'], expected ['mixed-semidiurnal']" in found
    assert "stations/9413878: type of tide ['semidiurnal'], expected none" in found
    assert len(found) == 2


def test_king_tides_coming_up(built: Path) -> None:
    """Built on Nov 1, the November run is 22 days out: the king-tide pages
    lead with it and name the month, and nearby pages link to it (0015)."""
    en = (built / "king-tides/index.html").read_text(encoding="utf-8")
    es = (built / "es/king-tides/index.html").read_text(encoding="utf-8")
    assert "<title>King tides November 2026: WA, OR and CA dates and times | Tide Hours</title>" in en
    assert 'content="West Coast king tides Nov 23–Dec 1, 2026:' in en
    assert "The next king tides: Nov 23–Dec 1, 2026" in en
    assert en.index('id="kt-next"') < en.index('id="kt-safety"') < en.index('id="kt-california"')
    assert en.count("data-kt-next=") == 31 and es.count("data-kt-next=") == 31
    assert 'data-kt-next="9414290 2026-11-24 2026-11-26 2026-11-25 10:49"' in en
    assert "Washington: Nov 23–Dec 1, 2026, peaking Nov 25–27, 2026." in en
    assert "<td>Nov 25, 2026, 10:49 AM</td>" in en
    assert "<title>Mareas reales (king tides) noviembre de 2026: WA, OR y CA, fechas y horas | Tide Hours</title>" in es
    assert "Las próximas mareas reales: 23 nov–1 dic 2026" in es and "<td>25 nov 2026, 10:49</td>" in es

    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "King tides Nov 24–26, 2026</h2>" in sf and "King tides Nov 24–26, 2026.</title>" not in sf
    assert sf.index('id="king"') < sf.index('id="day-1"') and sf.count('id="king"') == 1
    assert "highest on Nov 25, 2026 at 10:49 AM, 7.0 ft" in sf
    assert sf.count('data-kt-run="9414290 2026-11-24') == 1
    # Rincon Point is 4 mi from the Golden Gate station and not on the king-tide page.
    rp = (built / "stations/9414317/index.html").read_text(encoding="utf-8")
    assert "King tides nearby, Nov 24–26, 2026" in rp and "San Francisco (Golden Gate), 4 mi away" in rp
    assert "not this one's" in rp and 'href="/king-tides/#station-9414290"' in rp
    assert "data-kt-run" not in (built / "stations/1612340/index.html").read_text(encoding="utf-8")  # Honolulu

    region = (built / "states/ca/san-francisco-bay/index.html").read_text(encoding="utf-8")
    assert "King tides November 2026" in region and 'href="/king-tides/#station-9414290"' in region
    ca = (built / "states/ca/index.html").read_text(encoding="utf-8")
    assert "California's next king tides are Nov 23–27, 2026, highest on Nov 25, 2026." in ca
    assert 'href="/king-tides/#kt-CA"' in ca
    assert "kt-link" not in (built / "states/hi/index.html").read_text(encoding="utf-8")
    home = (built / "index.html").read_text(encoding="utf-8")
    assert "King tides November 2026" in home and "Nov 23–Dec 1, 2026" in home


def test_king_tides_out_of_season(tmp_path: Path) -> None:
    """In March 2027 no station has a run within 30 days: the pages fall back
    to the season's title and copy, no summary or link renders, and the gate
    agrees."""
    out = tmp_path / "march"
    assert cli.main(["--out", str(out), "--now", "2027-03-15T12:00:00Z", "--states", "CA"]) == 0
    en = (out / "king-tides/index.html").read_text(encoding="utf-8")
    assert "<title>King tides 2026–27: WA, OR and CA dates and heights | Tide Hours</title>" in en
    assert "kt-next" not in en and "data-kt-next" not in en
    sf = (out / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "data-kt-run" not in sf and 'href="/king-tides/#station-9414290"' in sf  # the section lower down
    assert "King tides 2026–27" in (out / "index.html").read_text(encoding="utf-8")
    assert "kt-link" not in (out / "states/ca/index.html").read_text(encoding="utf-8")
    check: Any = _check_site()
    assert check.check_king_tides(out, load()) == []
    # With no king-tide station page to date the build, it says so, not passes.
    assert check.check_king_tides(tmp_path / "empty", load()) == [
        "king-tides: no king-tide station page to date the build"
    ]


def test_check_site_catches_a_wrong_king_tide_summary(tmp_path: Path, built: Path) -> None:
    """Negative control: the gate's king-tide check passes on the build and
    fails when the summary, the title or a station's link disagrees with the
    computed season."""
    check: Any = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    cat = load()
    assert check.check_king_tides(site_dir, cat) == []

    en = site_dir / "king-tides/index.html"
    html = en.read_text(encoding="utf-8")
    html = html.replace("2026-11-25 10:49", "2026-11-25 11:49").replace("King tides November 2026", "King tides 2026")
    en.write_text(html, encoding="utf-8")
    assert "2026-11-25 11:49" in en.read_text(encoding="utf-8")  # the sabotage applied
    sf = site_dir / "stations/9414290/index.html"
    sf.write_text(re.sub(r' data-kt-run="[^"]*"', "", sf.read_text(encoding="utf-8")), encoding="utf-8")
    assert "data-kt-run" not in sf.read_text(encoding="utf-8")  # applied
    hi = site_dir / "stations/1612340/index.html"
    hi.write_text(hi.read_text(encoding="utf-8").replace("<main", '<main data-kt-run="x"', 1), encoding="utf-8")
    assert 'data-kt-run="x"' in hi.read_text(encoding="utf-8")  # applied

    found = check.check_king_tides(site_dir, cat)
    assert any(p.startswith("king-tides: runs coming up differ") and "11:49" in p for p in found)
    assert any(p.startswith("king-tides: title") for p in found)
    assert "stations/9414290: king-tide link none, expected ['9414290 2026-11-24 2026-11-26 2026-11-25 10:49']" in found
    assert "stations/1612340: king-tide link ['x'], expected none" in found
    assert not any(p.startswith("es/king-tides") for p in found)
    assert len(found) == 4


def _site_sample() -> Any:
    spec = importlib.util.spec_from_file_location(
        "site_sample", Path(__file__).parent.parent / "scripts/site_sample.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_checks_sample_skips_redirect_stubs(tmp_path: Path) -> None:
    # The axe and reflow checks lost their page context on a stub's meta
    # refresh (DECISIONS 0018). Redirect stubs are left out of the sample;
    # split-region pages, which do not redirect, are put in it.
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "NC,GU,MP,UM,PR,VI,other"]) == 0
    sample_mod = _site_sample()
    picked: list[str] = sample_mod.sample(out)
    stubs = [p for p in out.glob("states/*/*/index.html") if sample_mod.redirects(p)]
    assert len(stubs) >= 5  # the outer banks, marshall islands and PR island stubs, at least
    assert "states/other/outer-banks/" not in picked and "states/pr/st-croix-island/" not in picked
    assert not any(sample_mod.redirects(out / p / "index.html") for p in picked if p.startswith("states/"))
    assert {"states/other/hawaiin-islands/", "states/other/northern-marianas-islands/"} <= set(picked)
    assert "states/nc/outer-banks/" in [
        p.parent.relative_to(out).as_posix() + "/" for p in out.glob("states/*/*/index.html")
    ]
    assert "states/nc/" in picked and "stations/1630000/" in picked
