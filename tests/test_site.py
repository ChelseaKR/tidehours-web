"""The built site: every page carries what the product promises (predictions
not observations, not for navigation, not a NOAA product, the NOAA credit,
the app marked "coming soon"), nothing absent renders as a value, and the
config switches (GA4, App Store link) do what they say."""

from __future__ import annotations

import dataclasses
import datetime as dt
import html as htmllib
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
from tidehours import cli, site, subordinate, tidetype
from tidehours.catalog import Station, load, tidy_name
from tidehours.days import Day, Event, feet, meters, no_negative_zero, station_day

NOW = "2026-11-01T11:20:00Z"  # US daylight saving time ends this day


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    # An empty booklet list, so these tests stay about the site without one
    # when a California booklet is listed (docs/DECISIONS.md 0030;
    # tests/test_station_booklets.py covers a listed one).
    no_booklets = tmp_path_factory.mktemp("lists") / "booklets.json"
    no_booklets.write_text('{"booklets": {}}', encoding="utf-8")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,HI,other", "--booklets", str(no_booklets)]) == 0
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
    assert "<h1>San Francisco (Golden Gate), CA tides today</h1>" in sf and "SAN FRANCISCO" not in sf
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
    assert "<h1>Cape Hatteras, NC tides today</h1>" in hatteras
    assert "listed under North Carolina, the state of the reference station" in hatteras
    apra = (out / "stations/1630000/index.html").read_text(encoding="utf-8")
    assert "<h1>Apra Harbor, Guam tides today</h1>" in apra and "where NOAA's station name places it" in apra
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


ROBOTS = '<meta name="robots" content="noindex,follow">'
ROWS = re.compile(r'<tr class="ev-[^"]+">.*?</tr>')
# The subordinate stations whose NOAA corrections leave every time and every
# high-tide height as their reference station's (DECISIONS 0033), from the
# data retrieved 2026-10-24: Cabrillo Beach (0 min, 0 min, x1.00, x1.00 from
# Los Angeles) and Great Diamond Island (0 min, 0 min, x1.00, x1.03 from
# Portland, ME). Windham Bay (0 min, 0 min, -1.1 ft, -0.1 ft from Juneau) has
# its own heights, so it is not one.
TWINS = {"9410650": "9410660", "8417988": "8418150"}


def _rows(root: Path, sid: str) -> list[str]:
    return ROWS.findall((root / "stations" / sid / "index.html").read_text(encoding="utf-8"))


def test_subordinate_pages_are_indexed_with_their_own_answers(built: Path) -> None:
    """DECISIONS 0033 (superseding 0013's noindex): a subordinate station's
    page is indexed, in the sitemap and lastmod.json, and its answer lines,
    the highs and lows, differ from its reference station's page."""
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    manifest = json.loads((built / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    sub = (built / "stations/9413878/index.html").read_text(encoding="utf-8")  # Ano Nuevo Island
    assert "noindex" not in sub and 'rel="canonical" href="https://tidehours.com/stations/9413878/"' in sub
    assert "https://tidehours.com/stations/9413878/</loc>" in sitemap and "/stations/9413878/" in manifest
    rows, ref_rows = _rows(built, "9413878"), _rows(built, "9414290")
    assert len(rows) >= 6 and len(ref_rows) >= 6 and not set(rows) & set(ref_rows)
    # Its own line with NOAA's published corrections, its own coordinates.
    text = " ".join(re.sub(r"<[^>]+>", " ", sub).split())
    assert (
        "Ano Nuevo Island, CA is a NOAA subordinate station of San Francisco (Golden Gate), CA (station 9414290)"
        in text
    )
    assert "high tide 1 h 24 min earlier, low tide 1 h 4 min earlier; heights 0.7 ft lower at high tide" in text
    assert "Station 9413878 · 37.1083, -122.3380" in sub
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "noindex" not in sf and 'class="subordinate"' not in sf
    # The reference page still lists each station predicted from it.
    assert "Stations predicted from this one" in sf and 'href="/stations/9413878/"' in sf
    assert re.search(r"high tide (at the same time|\d+ (h|min)[^,]* (later|earlier))", sf)
    # Every built subordinate page but a twin is indexed and differs from its reference.
    cat = load()
    for f in built.glob("stations/*/index.html"):
        s = cat.station(f.parent.name)
        assert s is not None
        html = f.read_text(encoding="utf-8")
        assert (ROBOTS in html) == (s.id in TWINS) == (not site.indexable(s)), s.id
        if s.is_subordinate and s.id not in TWINS and (built / "stations" / str(s.reference_id)).exists():
            assert _rows(built, s.id) != _rows(built, str(s.reference_id)), s.id


def test_a_twin_stays_noindex_with_its_reference_as_canonical(built: Path) -> None:
    """Negative control for DECISIONS 0033: Cabrillo Beach's corrections are
    0 min and x1.00, so its answer lines are Los Angeles's, byte for byte;
    its page carries noindex, a canonical to Los Angeles, and is out of the
    sitemap and lastmod.json."""
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    manifest = json.loads((built / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    twin = (built / "stations/9410650/index.html").read_text(encoding="utf-8")
    assert _rows(built, "9410650") == _rows(built, "9410660") != []  # a true copy of the answer
    assert ROBOTS in twin and '<link rel="canonical" href="https://tidehours.com/stations/9410660/">' in twin
    assert '<meta property="og:url" content="https://tidehours.com/stations/9410660/">' in twin
    assert "/stations/9410650/<" not in sitemap and "/stations/9410650/" not in manifest
    assert "asks search engines to show that station's page instead" in twin
    la = (built / "stations/9410660/index.html").read_text(encoding="utf-8")
    assert "noindex" not in la and 'href="/stations/9410650/"' in la  # still linked from its reference
    cat = load()
    assert {s.id: s.twin_of for s in cat.stations if s.twin_of} == TWINS
    windham = cat.station("9451962")  # 0 min times, but its own heights
    assert windham is not None and windham.twin_of is None and site.indexable(windham)
    # The rule is what holds it back: with Cabrillo Beach's high tides scaled
    # by 1.01 it is no longer a twin.
    o = cat.offsets("9410650")
    assert subordinate.is_twin(o) and not subordinate.is_twin(dataclasses.replace(o, high_height=1.01))
    assert not subordinate.is_twin(dataclasses.replace(o, low_time_minutes=1.0))
    assert subordinate.is_twin(dataclasses.replace(o, adjustment="F", high_height=0.0, low_height=0.4))


def test_sitemap_counts_every_station_but_the_twins(built: Path) -> None:
    """The sitemap lists every station page in the build but the twins, and
    over the whole catalog that is 3,254 of 3,256 (1,232 harmonic and 2,022
    subordinate), with the 2 twins left out (DECISIONS 0033)."""
    cat = load()
    assert sum(site.indexable(s) for s in cat.stations) == 3254 == len(cat.stations) - len(TWINS)
    assert sum(s.is_subordinate and site.indexable(s) for s in cat.stations) == 2022
    sitemap = (built / "sitemap.xml").read_text(encoding="utf-8")
    locs = set(re.findall(r"<loc>https://tidehours\.com/stations/([^/<]+)/</loc>", sitemap))
    built_ids = {f.parent.name for f in built.glob("stations/*/index.html")}
    assert locs == built_ids - set(TWINS) and "9410650" in built_ids
    assert sum(cat.station(i).is_subordinate for i in locs) > 100  # type: ignore[union-attr]


def test_height_phrase() -> None:
    assert subordinate.height_phrase("R", 0.96) == "multiplied by 0.96"
    assert subordinate.height_phrase("R", 1.0) == "unchanged"
    assert subordinate.height_phrase("F", -0.7) == "0.7 ft lower"
    assert subordinate.height_phrase("F", 0.3) == "0.3 ft higher"
    assert subordinate.height_phrase("F", 0.0) == "unchanged"


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
                    assert (robots in station) == (not site.indexable(s)), s.id
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
    pass on the build and fail once a twin's page loses its noindex or its
    canonical, and once an indexed subordinate page gains a noindex."""
    check: Any = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    stations = load().stations

    def problems() -> list[str]:
        found: list[str] = check.check_indexing(site_dir, sorted(site_dir.rglob("*.html")), stations)
        return found

    assert problems() == []
    page = site_dir / "stations/9410650/index.html"  # Cabrillo Beach, a twin
    html = page.read_text(encoding="utf-8")
    html = html.replace(ROBOTS, "").replace(
        '<link rel="canonical" href="https://tidehours.com/stations/9410660/">',
        '<link rel="canonical" href="https://tidehours.com/stations/9410650/">',
    )
    page.write_text(html, encoding="utf-8")
    assert "noindex" not in page.read_text(encoding="utf-8")  # the sabotage applied
    sub = site_dir / "stations/9413878/index.html"
    sub.write_text(sub.read_text(encoding="utf-8").replace("<head>", "<head>" + ROBOTS, 1), encoding="utf-8")
    assert ROBOTS in sub.read_text(encoding="utf-8")  # applied
    found = problems()
    assert "stations/9410650: a twin station needs noindex" in found
    assert "stations/9410650: canonical stations/9410650/, expected stations/9410660/" in found
    assert "stations/9413878: a subordinate station needs no noindex" in found
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
    assert "<title>King tides November 2026: Washington, Oregon and California | Tide Hours</title>" in en
    assert 'content="The next West Coast king tides are Nov 23–Dec 1, 2026: the peak day, local time' in en
    assert "height at 31 NOAA stations, from Seattle and Puget Sound to the Oregon coast" in en
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
    assert "<title>King tides 2026–27: Washington, Oregon and California dates | Tide Hours</title>" in en
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


def _lastmods(root: Path) -> dict[str, str]:
    text = (root / "sitemap.xml").read_text(encoding="utf-8")
    return dict(re.findall(r"<loc>https://tidehours\.com/([^<]*)</loc><lastmod>([^<]*)</lastmod>", text))


def test_sitemap_lastmod_carries_over_for_unchanged_pages(tmp_path: Path, built: Path) -> None:
    """DECISIONS 0028: with the live sitemap and lastmod.json, a page whose
    HTML is unchanged keeps the date it last changed, and a changed page gets
    the build date. Without them, or with a record that cannot be trusted,
    every page gets the build date."""
    prev = tmp_path / "prev"
    prev.mkdir()
    shutil.copy(built / "lastmod.json", prev / "lastmod.json")
    old = (built / "sitemap.xml").read_text(encoding="utf-8").replace("<lastmod>2026-11-01<", "<lastmod>2026-10-20<")
    (prev / "sitemap.xml").write_text(old, encoding="utf-8")
    # Negative control: the about page's recorded fingerprint no longer
    # matches, so it must get the build date, not the carried one.
    manifest = json.loads((prev / "lastmod.json").read_text(encoding="utf-8"))
    manifest["pages"]["/about/"]["fingerprint"] = "0" * 64
    (prev / "lastmod.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "<lastmod>2026-10-20<" in old and "2026-11-01" not in old  # the sabotage applied

    out = tmp_path / "next"
    assert (
        cli.main(
            ["--out", str(out), "--now", "2026-11-02T11:20:00Z", "--states", "CA,HI,other", "--previous", str(prev)]
        )
        == 0
    )
    mods = _lastmods(out)
    # Unchanged since the previous build: the king-tide calendars, privacy, terms.
    for path in ("king-tides/california/", "privacy/", "terms/"):
        assert mods[path] == "2026-10-20", path
    assert mods["about/"] == "2026-11-02"  # the record no longer matched
    assert mods["stations/9414290/"] == "2026-11-02"  # today's tides are new
    assert set(mods.values()) == {"2026-10-20", "2026-11-02"}

    # Nothing to compare with, or a lastmod after the build date: build date.
    assert set(_lastmods(built).values()) == {"2026-11-01"}
    (prev / "lastmod.json").unlink()
    assert site.previous_lastmods(prev, "https://tidehours.com/", "2026-11-02") == {}
    assert site.previous_lastmods(None, "https://tidehours.com/", "2026-11-02") == {}
    shutil.copy(built / "lastmod.json", prev / "lastmod.json")
    assert site.previous_lastmods(prev, "https://tidehours.com/", "2026-10-19") == {}
    (prev / "lastmod.json").write_text("not json", encoding="utf-8")
    assert site.previous_lastmods(prev, "https://tidehours.com/", "2026-11-02") == {}


# Answer first (docs/DECISIONS.md 0032): the title in the shape people search
# with, each day's highs and lows under a plain question before anything
# else, the same answer in the meta description, and a nearby list by radius.


def _meta_description(html: str) -> str:
    m = re.search(r'<meta name="description" content="([^"]*)">', html)
    assert m
    return htmllib.unescape(m.group(1))


def test_station_title_shape_and_lead_answer(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "<title>San Francisco (Golden Gate), CA tides today: high and low</title>" in sf
    # The answer comes before the first table, tide chart and nearby list.
    answer = sf.index('<div class="answer">')
    assert answer < sf.index('<table class="events">') < sf.index('id="near"')
    assert sf.index("<h1>") < answer
    assert "When is high tide at San Francisco (Golden Gate), CA today?</h2>" in sf
    assert "When is low tide at San Francisco (Golden Gate), CA today?</h2>" in sf
    block = sf[answer : sf.index("</div>", answer)]
    # Each question lists both days, by date, in the order of the page.
    for kind in ("high", "low"):
        part = block[block.index(f'id="q-{kind}"') :]
        assert part.index('data-date="2026-11-01"') < part.index('data-date="2026-11-02"')
    # The 5:40 AM high (the golden fixture's NOAA high at 13:40Z) is the
    # first high of November 1, with its height.
    high = block[block.index('id="q-high"') :]
    first = high[high.index('data-date="2026-11-01"') : high.index("</li>")]
    assert "Sunday, Nov 1: " in first and '<time datetime="2026-11-01T05:40-08:00">5:40 AM</time></strong> (' in first
    assert re.search(r"\(−?\d+\.\d ft\)", first)
    lead = re.search(r'<p class="lead">(.*?)</p>', sf, re.S)
    assert lead and "Times are Pacific Time (PT), local to the station;" in lead.group(1)


def test_meta_description_carries_the_answer(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    desc = _meta_description(sf)
    assert desc.startswith("San Francisco (Golden Gate), CA tides Nov 1: high 5:40 AM (")
    assert "; low " in desc
    for f in built.glob("stations/*/index.html"):
        d = _meta_description(f.read_text(encoding="utf-8"))
        assert len(d) <= site.DESCRIPTION_MAX, (f, len(d))
        assert " tides Nov " in d or " high and low tides, " in d, f


def test_description_tiers_and_absence() -> None:
    def ev(kind: str, time: str, ft: str) -> Event:
        return Event(kind, time, "", ft, "", 0.0)

    one = Day(dt.date(2026, 11, 1), [ev("High", "5:40 AM", "5.6 ft"), ev("Low", "11:58 AM", "0.8 ft")], None, False)
    two = Day(dt.date(2026, 11, 2), [ev("High", "6:20 AM", "5.5 ft")], None, False)
    empty = Day(dt.date(2026, 11, 2), [], None, False)
    assert site.day_answer(one) == "high 5:40 AM (5.6 ft); low 11:58 AM (0.8 ft)"
    assert site.day_answer(two) == "high 6:20 AM (5.5 ft); no low tide"  # absence says so
    assert site.day_answer(empty) == "no high or low tide predicted"
    assert site.station_description("Monterey, CA", [one, two]) == (
        "Monterey, CA tides Nov 1: high 5:40 AM (5.6 ft); low 11:58 AM (0.8 ft). Nov 2: high 6:20 AM (5.5 ft); no low tide."
    )
    long = "x" * 60  # tomorrow no longer fits; today does
    assert site.station_description(long, [one, two]).endswith("Nov 2 too, with a tide chart.")
    longer = "x" * 120
    assert site.station_description(longer, [one, two]) == f"{longer} high and low tides, Nov 1 and Nov 2."
    # An extra sentence is added only when it fits.
    assert site.station_description("Monterey, CA", [one, two], "King tides Nov 24–26.").endswith(
        "King tides Nov 24–26."
    )
    assert "King" not in site.station_description("x" * 60, [one, two], "King tides Nov 24–26.")


def test_nearby_list_by_radius_and_state(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    near = sf[sf.index('id="near"') : sf.index("</section>", sf.index('id="near"'))]
    miles = [int(m) for m in re.findall(r'<span class="dist">(\d+) mi</span>', near)]
    assert 1 <= len(re.findall(r"<li>", near)) <= site.NEARBY_MAX
    assert miles == sorted(miles) and all(m <= site.NEARBY_MILES for m in miles)
    assert "within 25 miles" in near
    cat = load()
    stations = [s for s in cat.stations if s.state in ("CA", "HI", "")]
    near_all = site.Nearby(stations)
    for f in built.glob("stations/*/index.html"):
        sid = f.parent.name
        html = f.read_text(encoding="utf-8")
        s = cat.station(sid)
        assert s is not None
        expect = site.neighbors(near_all, s)
        assert ('id="near"' in html) == bool(expect), sid
        for other, km in expect:
            assert other.state == s.state and km <= site.NEARBY_KM
            assert f'href="/stations/{other.id}/"' in html


def test_no_neighbor_within_the_radius_renders_no_list(built: Path) -> None:
    # Negative control: a station with no other station of its state within
    # the radius gets no "Nearby" section at all, not an empty one.
    cat = load()
    stations = [s for s in cat.stations if s.state in ("CA", "HI", "")]
    near_all = site.Nearby(stations)
    alone = [s for s in stations if not site.neighbors(near_all, s)]
    assert alone
    for s in alone[:5]:
        html = (built / f"stations/{s.id}/index.html").read_text(encoding="utf-8")
        assert 'id="near"' not in html and ">Nearby<" not in html, s.id
    # Unit level: two stations 30 miles apart are not neighbors; 20 miles
    # apart they are; across a state line they are not.
    base = Station("A", "A", "CA", 37.0, -122.0, "America/Los_Angeles", None, None)
    far = dataclasses.replace(base, id="B", lat=37.0 + 30 / 69.05)
    close = dataclasses.replace(base, id="C", lat=37.0 + 20 / 69.05)
    other = dataclasses.replace(base, id="D", state="OR", lat=37.0 + 1 / 69.05)
    assert [s.id for s, _ in site.neighbors(site.Nearby([base, far, close, other]), base)] == ["C"]
    assert site.neighbors(site.Nearby([base, far, other]), base) == []


def test_state_and_region_pages_lead_with_the_list(built: Path) -> None:
    ca = (built / "states/ca/index.html").read_text(encoding="utf-8")
    assert re.search(r"<title>California tides today: tide times at \d+ stations</title>", ca)
    assert "<h1>California tides today</h1>" in ca
    first_list = ca.index('<ul class="stations">')
    if 'id="king"' in ca:
        assert first_list < ca.index('id="king"')
    assert ca.count("<p", ca.index("<h1>"), first_list) == 1  # one line of lead, then the list
    region = (built / "states/ca/san-francisco-bay/index.html").read_text(encoding="utf-8")
    assert "<title>San Francisco Bay, California tides today: tide times</title>" in region
    assert "<h1>San Francisco Bay tides today</h1>" in region
    lst = region.index('<ul class="stations">')
    assert region.count("<p", region.index("<h1>"), lst) == 1
    if 'id="king"' in region:
        assert lst < region.index('id="king"')
    for f in list(built.glob("states/*/index.html")) + list(built.glob("states/*/*/index.html")):
        title = re.search(r"<title>([^<]*)</title>", f.read_text(encoding="utf-8"))
        assert title and len(htmllib.unescape(title.group(1))) <= site.TITLE_MAX, f


def test_searched_place_names_lead_their_pages(built: Path) -> None:
    # copy/place_names.json (DECISIONS 0032): each entry names a station that
    # exists, is pinned to its current display name, comes from a Search
    # Console query, and leads with the searched place, then the station.
    cat = load()
    names = site.place_names()
    assert len(names) >= 5
    titles = Counter(site.station_title(site.place_name(s, names)) for s in cat.stations)
    assert [t for t, n in titles.items() if n > 1] == []
    for sid, entry in names.items():
        s = cat.station(sid)
        assert s is not None, sid
        assert entry["station"] == s.display_name, sid  # a rename makes this fail
        assert entry["query"] and entry["basis"], sid
        assert s.display_name in entry["name"] and not entry["name"].startswith(s.display_name), sid
        assert site.place_name(s, names) == entry["name"]
        assert len(site.station_title(entry["name"])) <= site.TITLE_MAX, sid
    kahului = (built / "stations/1615680/index.html").read_text(encoding="utf-8")
    assert "<title>Maui (Kahului, HI) tides today: high and low tide chart</title>" in kahului
    assert "<h1>Maui (Kahului, HI) tides today</h1>" in kahului
    assert "When is high tide at Maui (Kahului, HI) today?" in kahului
    assert _meta_description(kahului).startswith("Maui (Kahului, HI) tides Nov 1: ")
    # Negative control: an entry pinned to a name the station no longer has
    # does not apply, and a station without an entry keeps its own name.
    s = cat.station("1615680")
    assert s is not None
    stale = {"1615680": {**names["1615680"], "station": "Kahului Harbor, HI"}}
    assert site.place_name(s, stale) == "Kahului, HI"
    sf = cat.station("9414290")
    assert sf is not None and site.place_name(sf, names) == sf.display_name


def test_region_pages_do_not_repeat_the_state() -> None:
    cat = load()
    states = {st.code: st for st in site.group(cat.stations)}
    regions = {r.path: (r, st) for st in states.values() for r in st.regions}
    al, al_st = regions["states/al/alabama/"]
    assert site.region_place(al, al_st) == "Alabama"
    assert site.region_title(al, al_st) == "Alabama tides today: tide times"
    keys = next((r, st) for r, st in regions.values() if r.name == "Florida Keys")
    assert site.region_place(*keys) == "Florida Keys"
    hawaiian = next((r, st) for r, st in regions.values() if r.name == "Hawaiian Islands")
    assert site.region_place(*hawaiian) == "Hawaiian Islands, Hawaii"  # a word, not a substring
    sf = regions["states/ca/san-francisco-bay/"]
    assert site.region_place(*sf) == "San Francisco Bay, California"
    for r, st in regions.values():
        place = site.region_place(r, st)
        named = re.findall(rf"\b{re.escape(st.name)}\b", place, re.I)
        assert len(named) <= 1, place  # "Alabama, Alabama" never
        assert len(site.region_title(r, st)) <= site.TITLE_MAX, place
    for st in states.values():
        assert len(site.state_title(st)) <= site.TITLE_MAX, st.code


def test_every_station_description_can_fit() -> None:
    # The shortest description tier fits for every station's name (the
    # longest date is "Sep 30"), so no station page's meta description can
    # exceed DESCRIPTION_MAX, whatever its day holds.
    cat = load()
    names = site.place_names()
    for s in cat.stations:
        fallback = f"{site.place_name(s, names)} high and low tides, Sep 30 and Sep 30."
        assert len(fallback) <= site.DESCRIPTION_MAX, s.id
