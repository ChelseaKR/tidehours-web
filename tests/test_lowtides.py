"""The lowest daylight low tides (docs/DECISIONS.md 0021): sunrise and sunset
against the U.S. Naval Observatory, the picked lows against NOAA's own
published predictions, the list's rules (daylight, threshold, one a day, at
most LIST_SIZE), absence in words, the page in the sitemap, and a negative
control for the gate's check."""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
import shutil
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tidehours import cli, lowtides, site
from tidehours.catalog import Catalog, load

NOW = "2026-11-01T11:20:00Z"
UTC = dt.UTC

# U.S. Naval Observatory, Astronomical Applications API (rstt/oneday), read
# 2026-11-05: (lat, lon, zone, local date, sunrise UTC, sunset UTC). The last
# is the day daylight saving time starts in 2027.
USNO_SUN = [
    (37.8063, -122.4659, "America/Los_Angeles", "2026-12-21", "2026-12-21T15:22", "2026-12-22T00:54"),
    (47.6026, -122.3393, "America/Los_Angeles", "2027-06-21", "2027-06-21T12:12", "2027-06-22T04:11"),
    (21.3033, -157.8645, "Pacific/Honolulu", "2026-12-21", "2026-12-21T17:05", "2026-12-22T03:55"),
    (43.6567, -70.2467, "America/New_York", "2027-01-15", "2027-01-15T12:11", "2027-01-15T21:30"),
    (48.3703, -124.6013, "America/Los_Angeles", "2027-03-14", "2027-03-14T14:34", "2027-03-15T02:22"),
]

# NOAA CO-OPS published high/low predictions (datagetter, product=predictions,
# interval=hilo, datum=MLLW, lst_ldt), read 2026-11-05: local time and feet.
NOAA_LOWS = {
    ("9414131", "2026-12-23"): ("16:22", -1.855),  # Half Moon Bay
    ("9443090", "2027-01-18"): ("15:57", -0.218),  # Neah Bay
    ("1617433", "2026-12-26"): ("13:14", -0.102),  # Kawaihae; its 23:32 low (-0.105 ft) is at night
}


@pytest.fixture(scope="module")
def cat() -> Catalog:
    return load()


def utc(text: str) -> float:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp()


@pytest.mark.parametrize(("lat", "lon", "tz", "day", "rise", "set_"), USNO_SUN)
def test_sun_times_match_the_naval_observatory(lat: float, lon: float, tz: str, day: str, rise: str, set_: str) -> None:
    got = lowtides.sun_times(lat, lon, tz, dt.date.fromisoformat(day))
    assert got is not None
    # USNO prints whole minutes; within a minute and a half of them.
    assert abs(got[0] - utc(rise)) <= 90
    assert abs(got[1] - utc(set_)) <= 90


def test_no_sunrise_or_sunset_is_none_not_a_time() -> None:
    # Prudhoe Bay: polar night in December, midnight sun in June.
    for day in ("2026-12-21", "2027-06-21"):
        assert lowtides.sun_times(70.4114, -148.5317, "America/Anchorage", dt.date.fromisoformat(day)) is None


def test_threshold_is_what_the_page_prints() -> None:
    assert not lowtides.qualifies(-0.04)  # prints as 0.0 ft
    assert not lowtides.qualifies(0.0)
    assert lowtides.qualifies(-0.06)
    assert lowtides.qualifies(-2.0)


def regions_at(cat: Catalog, now: str) -> list[lowtides.RegionLows]:
    return lowtides.season(cat, dt.datetime.fromisoformat(now.replace("Z", "+00:00")))


def test_picked_lows_match_noaa(cat: Catalog) -> None:
    """The lows on the 2026-11-01 and 2026-12-16 pages agree with NOAA's
    published predictions: the time within a minute, the height within
    0.02 ft."""
    found: dict[tuple[str, str], lowtides.Low] = {}
    for now in (NOW, "2026-12-16T15:00:00Z"):
        for r in regions_at(cat, now):
            for lo in [*r.lows, *([r.next_after] if r.next_after else [])]:
                found[(lo.station_id, lo.date)] = lo
    for key, (time, height) in NOAA_LOWS.items():
        lo = found[key]
        minutes = (dt.datetime.strptime(lo.time, "%H:%M") - dt.datetime.strptime(time, "%H:%M")).total_seconds() / 60
        assert abs(minutes) <= 1, key
        assert abs(lo.height - height) <= 0.02, key


def test_washington_in_november_has_none_and_says_when(cat: Catalog) -> None:
    wa = next(r for r in regions_at(cat, NOW) if r.code == "WA")
    assert wa.lows == []
    assert wa.next_after is not None
    assert (wa.next_after.station_id, wa.next_after.date, wa.next_after.time) == ("9443090", "2027-01-18", "15:57")
    ca = next(r for r in regions_at(cat, NOW) if r.code == "CA")
    assert ca.next_after is None  # only looked for when the window has none
    assert [lo.date for lo in ca.lows] == [
        "2026-11-23", "2026-11-24", "2026-11-25", "2026-12-22", "2026-12-23", "2026-12-24",
    ]  # fmt: skip


@pytest.mark.parametrize("now", [NOW, "2026-12-16T15:00:00Z", "2027-03-01T15:00:00Z", "2027-06-01T15:00:00Z"])
def test_list_rules(cat: Catalog, now: str) -> None:
    """At most LIST_SIZE, one a day, in date order, inside the window, below
    the threshold, inside the daylight margin, and the lowest days: every
    qualifying day left out is no lower than the highest one listed."""
    for r in regions_at(cat, now):
        assert len(r.lows) <= lowtides.LIST_SIZE
        dates = [lo.date for lo in r.lows]
        assert dates == sorted(set(dates))
        assert all(r.first <= d <= r.last for d in dates)
        zone = ZoneInfo(r.spec.zone)
        for lo in r.lows:
            assert lowtides.qualifies(lo.height)
            st = cat.station(lo.station_id)
            assert st is not None
            day = dt.date.fromisoformat(lo.date)
            sun = lowtides.sun_times(st.lat, st.lon, r.spec.zone, day)
            assert sun is not None
            at = dt.datetime.combine(day, dt.time.fromisoformat(lo.time), zone).timestamp()
            margin = lowtides.MARGIN_MINUTES * 60 - 30
            assert sun[0] + margin <= at <= sun[1] - margin, (r.code, lo)
        every = lowtides.daylight_lows(cat, r.spec, dt.date.fromisoformat(r.first), lowtides.WINDOW_DAYS)
        if r.lows:
            worst = max(lo.height for lo in r.lows)
            assert all(lo.height >= worst for d, lo in every.items() if d not in dates)
        else:
            assert every == {}


def test_night_lows_are_left_out(cat: Catalog) -> None:
    """In California's winter the lowest lows are at night. The lowest low
    in the window is lower than anything listed, and it is not listed."""
    ca = next(r for r in regions_at(cat, NOW) if r.code == "CA")
    zone = ZoneInfo(ca.spec.zone)
    t0 = dt.datetime.combine(dt.date.fromisoformat(ca.first), dt.time(), zone).timestamp()
    t1 = t0 + lowtides.WINDOW_DAYS * 86_400
    lows = [
        (e.height, sid, e.time)
        for sid, _ in ca.spec.stations
        for e in cat.harmonic(sid).events(t0, t1)
        if e.kind == "L"
    ]
    height, sid, at = min(lows)
    assert height < min(lo.height for lo in ca.lows)
    local = dt.datetime.fromtimestamp(at, zone)
    st = cat.station(sid)
    assert st is not None
    sun = lowtides.sun_times(st.lat, st.lon, ca.spec.zone, local.date())
    assert sun is not None and not sun[0] <= at <= sun[1]  # at night
    assert (sid, local.date().isoformat()) not in {(lo.station_id, lo.date) for lo in ca.lows}


def test_every_region_station_is_harmonic_and_on_its_clock(cat: Catalog) -> None:
    for spec in lowtides.REGIONS:
        for sid, _ in spec.stations:
            st = cat.station(sid)
            assert st is not None and not st.is_subordinate, sid
            assert st.tz == spec.zone and st.state == spec.code, sid


def test_refuses_a_subordinate_station(cat: Catalog) -> None:
    bad = lowtides.RegionSpec("CA", "California", "America/Los_Angeles", (("9413878", "x"),))
    with pytest.raises(ValueError, match="not a harmonic station"):
        lowtides.region_lows(cat, bad, dt.date(2026, 11, 1))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "WA,CA"]) == 0
    return out


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_page_sitemap_and_links(built: Path) -> None:
    text = (built / "low-tides/index.html").read_text(encoding="utf-8")
    assert "<title>Lowest daylight low tides for tide pooling: WA and CA | Tide Hours</title>" in text
    assert "https://tidehours.com/low-tides/</loc>" in (built / "sitemap.xml").read_text(encoding="utf-8")
    assert '"/low-tides/"' in (built / "lastmod.json").read_text(encoding="utf-8")
    assert 'name="robots"' not in text
    assert 'data-lt-none="WA"' in text
    assert "No daylight low tide below 0 ft at these stations in the next 60 days." in text
    assert 'id="lt-HI"' not in text  # not in this build
    assert len(re.findall(r'data-lt="', text)) == lowtides.LIST_SIZE  # California's six
    assert "Not for navigation" in text and "NOAA CO-OPS" in text
    for bad in ("None", "NaN", "nan ft", "−0.0 ft", "0:00 AM", "12:00 AM"):
        assert bad not in text, bad
    assert 'href="/low-tides/"' in (built / "index.html").read_text(encoding="utf-8")
    assert 'href="/low-tides/#lt-CA"' in (built / "states/ca/index.html").read_text(encoding="utf-8")


def test_low_tides_are_off_when_no_region_is_built(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "NH"]) == 0
    assert not (out / "low-tides").exists()
    assert "low-tides" not in (out / "index.html").read_text(encoding="utf-8")
    assert "low-tides" not in (out / "states/nh/index.html").read_text(encoding="utf-8")
    assert _check_site().check_low_tides(out, load()) == []


def test_check_site_catches_a_wrong_low_tide_list(tmp_path: Path, built: Path, cat: Catalog) -> None:
    """Negative control: the gate's check passes on the build and fails when
    a row's time moves, a row is dropped, Washington's words are removed, or
    the page is missing."""
    check = _check_site()
    site_dir = tmp_path / "site"
    shutil.copytree(built, site_dir)
    assert check.check_low_tides(site_dir, cat) == []

    f = site_dir / "low-tides/index.html"
    html = f.read_text(encoding="utf-8")
    html = html.replace("9414131 2026-12-23 16:21", "9414131 2026-12-23 19:21")
    html = re.sub(r'<tr data-lt="9410840 2026-11-24[^"]*">', "<tr>", html)
    html = html.replace('data-lt-none="WA"', "")
    f.write_text(html, encoding="utf-8")
    after = f.read_text(encoding="utf-8")
    assert "9414131 2026-12-23 19:21" in after and "9410840 2026-11-24" not in after  # the sabotage applied
    assert 'data-lt-none="WA"' not in after  # applied

    found = check.check_low_tides(site_dir, cat)
    assert any(p.startswith("low-tides CA: rows") for p in found), found
    assert "low-tides CA: 9414131 2026-12-23 19:21 -1.9 is not in daylight" in found
    assert "low-tides WA: neither rows nor a no-lows line" in found
    assert not any(p.startswith("low-tides WA: rows") for p in found)

    shutil.rmtree(site_dir / site.LOW_TIDES_PATH)
    assert check.check_low_tides(site_dir, cat) == ["low-tides: no page"]
