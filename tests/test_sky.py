"""Sunrise, sunset, civil twilight, moonrise, moonset and the moon's phase
(src/tidehours/sky.py) against the U.S. Naval Observatory's published values
(tests/fixtures/usno-sky-2026.json, scripts/fetch_sky.py), the words for days
without one of them, times in each station's own zone, and negative controls
proving check_site fails a page whose sky line is missing or made up
(docs/DECISIONS.md 0019)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tidehours import cli, sky
from tidehours.catalog import load
from tidehours.days import civil_text, moon_text, moonrise_text, station_day, sun_text

FIXTURE = Path(__file__).parent / "fixtures" / "usno-sky-2026.json"
SUN_MINUTES = 2.0  # sunrise, sunset, civil dawn and dusk, minutes from USNO
MOON_MINUTES = 2.0  # moonrise and moonset, minutes from USNO
LIT_POINTS = 2  # percent of the moon lit, points from USNO
PHASE_MINUTES = 2.0  # a primary phase's time, minutes from USNO
PRUDHOE = "9497645"


def fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def usno_time(date: dt.date, hhmm: str, offset_h: float) -> dt.datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return dt.datetime.combine(date, dt.time(h, m), dt.timezone(dt.timedelta(hours=offset_h)))


def station_days() -> list[tuple[str, str]]:
    return [(sid, d) for sid, e in fixture()["stations"].items() for d in e["days"]]


def test_fixture_covers_the_hard_cases() -> None:
    fx = fixture()["stations"]
    assert len(fx) >= 20
    prudhoe = fx[PRUDHOE]["days"]
    phens = [p["phen"] for u in prudhoe.values() for p in u["sundata"]]
    assert "Object continuously below the Horizon" in phens  # polar night
    assert "Object continuously above the Horizon" in phens  # midnight sun
    zones = {load().station(sid).tz for sid in fx}  # type: ignore[union-attr]
    assert {"Pacific/Guam", "Pacific/Pago_Pago", "America/Adak", "America/Anchorage", "America/Puerto_Rico"} <= zones


@pytest.mark.parametrize(("sid", "date"), station_days())
def test_sun_matches_usno(sid: str, date: str) -> None:
    """Every sunrise and sunset within 2 minutes of USNO's, and the same
    days with none (USNO: "Object continuously above/below the Horizon")."""
    u = fixture()["stations"][sid]["days"][date]
    st = load().station(sid)
    assert st is not None
    d = dt.date.fromisoformat(date)
    ours = sky.sun_day(st.lat, st.lon, st.tz, d)
    theirs = [
        (p["phen"].lower(), usno_time(d, p["time"], u["tz"])) for p in u["sundata"] if p["phen"] in ("Rise", "Set")
    ]
    theirs.sort(key=lambda x: x[1])
    assert [e.kind for e in ours.events] == [k for k, _ in theirs], (sid, date)
    for e, (_, t) in zip(ours.events, theirs, strict=True):
        assert abs((e.time - t).total_seconds()) <= SUN_MINUTES * 60, (sid, date, e, t)
    if not theirs:
        always = [p["phen"] for p in u["sundata"] if p["phen"].startswith("Object continuously")]
        assert always, (sid, date)
        assert ours.up_all_day == ("above the Horizon" in always[0]), (sid, date)


CIVIL = {"Begin Civil Twilight": "dawn", "End Civil Twilight": "dusk"}


@pytest.mark.parametrize(("sid", "date"), station_days())
def test_civil_twilight_matches_usno(sid: str, date: str) -> None:
    """Civil dawn and dusk (the sun's center 6 degrees down) within 2 minutes
    of USNO's, and the same days without them."""
    u = fixture()["stations"][sid]["days"][date]
    st = load().station(sid)
    assert st is not None
    d = dt.date.fromisoformat(date)
    ours = sky.sun_day(st.lat, st.lon, st.tz, d)
    theirs = sorted(
        ((CIVIL[p["phen"]], usno_time(d, p["time"], u["tz"])) for p in u["sundata"] if p["phen"] in CIVIL),
        key=lambda x: x[1],
    )
    assert [e.kind for e in ours.civil] == [k for k, _ in theirs], (sid, date)
    for e, (_, t) in zip(ours.civil, theirs, strict=True):
        assert abs((e.time - t).total_seconds()) <= SUN_MINUTES * 60, (sid, date, e, t)


@pytest.mark.parametrize(("sid", "date"), station_days())
def test_moonrise_matches_usno(sid: str, date: str) -> None:
    """Moonrise and moonset within 2 minutes of USNO's, the same days
    without one, and the same days the moon stays up or down."""
    u = fixture()["stations"][sid]["days"][date]
    st = load().station(sid)
    assert st is not None
    d = dt.date.fromisoformat(date)
    ours = sky.moon_times(st.lat, st.lon, st.tz, d)
    theirs = sorted(
        ((p["phen"].lower(), usno_time(d, p["time"], u["tz"])) for p in u["moondata"] if p["phen"] in ("Rise", "Set")),
        key=lambda x: x[1],
    )
    # USNO's day is 24 hours at the noon offset (dst=false); ours runs from
    # local midnight to midnight, 23 or 25 hours on a daylight saving day.
    # Compare where the two days overlap; only on such a day may either have
    # an event outside the overlap.
    zone = ZoneInfo(st.tz)
    ours_begin = dt.datetime.combine(d, dt.time(), zone).timestamp()
    ours_end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), zone).timestamp()
    usno_begin = usno_time(d, "00:00", u["tz"]).timestamp()
    lo, hi = max(ours_begin, usno_begin), min(ours_end, usno_begin + 86400)
    inside = [e for e in ours.events if lo <= e.ts < hi]
    theirs_inside = [(k, w) for k, w in theirs if lo <= w.timestamp() < hi]
    if ours_end - ours_begin == 86400:
        assert (len(inside), len(theirs_inside)) == (len(ours.events), len(theirs)), (sid, date)
    assert [e.kind for e in inside] == [k for k, _ in theirs_inside], (sid, date)
    for e, (_, w) in zip(inside, theirs_inside, strict=True):
        assert abs((e.time - w).total_seconds()) <= MOON_MINUTES * 60, (sid, date, e, w)
    always = [p["phen"] for p in u["moondata"] if p["phen"].startswith("Object continuously")]
    if always:
        assert ours.up_all_day == ("above the Horizon" in always[0]), (sid, date)


@pytest.mark.parametrize(("sid", "date"), station_days())
def test_moon_matches_usno(sid: str, date: str) -> None:
    """The phase name and the share lit at local noon match USNO's (which
    calls the last quarter "Third Quarter"); a primary phase on the day is
    within 2 minutes of USNO's, and none is claimed on a day without one."""
    u = fixture()["stations"][sid]["days"][date]
    st = load().station(sid)
    assert st is not None
    d = dt.date.fromisoformat(date)
    m = sky.moon_day(st.tz, d)
    assert m.phase.lower() == u["curphase"].lower().replace("third quarter", "last quarter"), (sid, date)
    assert abs(m.percent - int(u["fracillum"].rstrip("%"))) <= LIT_POINTS, (sid, date)
    cp = u["closestphase"]
    when = usno_time(dt.date(cp["year"], cp["month"], cp["day"]), cp["time"], u["tz"])
    if when.astimezone(ZoneInfo(st.tz)).date() == d:
        assert m.primary is not None, (sid, date)
        assert m.primary[0].lower() == cp["phase"].lower(), (sid, date)
        assert abs((m.primary[1] - when).total_seconds()) <= PHASE_MINUTES * 60, (sid, date)
    else:
        assert m.primary is None, (sid, date, m.primary)


def test_polar_night_and_midnight_sun_are_words() -> None:
    """Prudhoe Bay: no time for a sunrise that does not happen."""
    st = load().station(PRUDHOE)
    assert st is not None
    night = sky.sun_day(st.lat, st.lon, st.tz, dt.date(2026, 12, 21))
    assert night.events == [] and not night.up_all_day and night.rise is None and night.set is None
    assert sun_text(night) == "The sun does not rise on this day (polar night)."
    assert len(night.dark) == 1  # the whole day shaded
    day = sky.sun_day(st.lat, st.lon, st.tz, dt.date(2027, 6, 21))
    assert day.events == [] and day.up_all_day and day.dark == []
    assert sun_text(day) == "The sun does not set on this day (midnight sun)."
    for text in (sun_text(night), sun_text(day)):
        assert not re.search(r"\d", text), text


def test_a_day_with_only_one_of_them_says_so() -> None:
    tz = ZoneInfo("America/Anchorage")
    at = dt.datetime(2027, 5, 1, 1, 5, tzinfo=tz)
    only_set = sky.SunDay(at.date(), [sky.SunEvent("set", at, at.timestamp())], False, [], [], False)
    assert sun_text(only_set) == "Sunset 1:05 AM. No sunrise on this day."
    only_rise = sky.SunDay(at.date(), [sky.SunEvent("rise", at, at.timestamp())], False, [], [], False)
    assert sun_text(only_rise) == "Sunrise 1:05 AM. No sunset on this day."
    only_dusk = sky.SunDay(at.date(), [], True, [], [sky.SunEvent("dusk", at, at.timestamp())], False)
    assert civil_text(only_dusk) == "Civil dusk 1:05 AM. No civil dawn on this day."
    only_moonset = sky.MoonTimes(at.date(), [sky.SunEvent("set", at, at.timestamp())], False)
    assert moonrise_text(only_moonset) == "Moonset 1:05 AM. No moonrise on this day."
    only_moonrise = sky.MoonTimes(at.date(), [sky.SunEvent("rise", at, at.timestamp())], False)
    assert moonrise_text(only_moonrise) == "Moonrise 1:05 AM. No moonset on this day."


def test_no_twilight_and_no_moonrise_are_words() -> None:
    """Days without civil twilight or without a moonrise or moonset have no
    time in their words."""
    d = dt.date(2027, 6, 21)
    white = sky.SunDay(d, [], True, [], [], True)
    assert civil_text(white) == "It does not get darker than civil twilight on this day."
    deep = sky.SunDay(d, [], False, [], [], False)
    assert civil_text(deep) == "No civil twilight on this day: the sun stays more than 6° below the horizon."
    assert moonrise_text(sky.MoonTimes(d, [], True)) == "The moon is up all day."
    assert moonrise_text(sky.MoonTimes(d, [], False)) == "The moon does not rise on this day."
    for text in (civil_text(white), civil_text(deep), moonrise_text(sky.MoonTimes(d, [], True))):
        assert not re.search(r"\d:\d", text), text


def test_sun_times() -> None:
    """The reusable (rise, set) pair: San Francisco's matches its SunDay;
    polar night, midnight sun, and a Prudhoe Bay May day whose sunset comes
    first have none."""
    st = load().station(PRUDHOE)
    assert st is not None
    sf = sky.sun_day(37.80631, -122.46589, "America/Los_Angeles", dt.date(2026, 11, 5))
    pair = sky.sun_times(37.80631, -122.46589, "America/Los_Angeles", dt.date(2026, 11, 5))
    assert pair == (sf.events[0].ts, sf.events[1].ts)
    for d in (dt.date(2026, 12, 21), dt.date(2027, 6, 21), dt.date(2027, 5, 14)):
        assert sky.sun_times(st.lat, st.lon, st.tz, d) is None, d


def test_moon_text() -> None:
    d = dt.date(2026, 11, 5)
    t = dt.datetime(2026, 11, 5, 23, 2, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert moon_text(sky.MoonDay(d, "Waning crescent", 0.12, None)) == "Moon: waning crescent, 12% lit at noon."
    assert (
        moon_text(sky.MoonDay(d, "New moon", 0.004, ("New moon", t))) == "Moon: new moon at 11:02 PM, 0% lit at noon."
    )
    assert (
        moon_text(sky.MoonDay(d, "Waxing gibbous", 0.54, ("First quarter", t)))
        == "Moon: waxing gibbous, 54% lit at noon; first quarter at 11:02 PM."
    )
    assert sky.phase_name(50, waxing=True) == "First quarter"
    assert sky.phase_name(100, waxing=False) == "Full moon"
    assert sky.phase_name(49, waxing=False) == "Waning crescent"


def test_times_are_in_the_station_zone() -> None:
    """Sun times use each station's own IANA zone, so they follow its
    daylight saving time: San Francisco on the day it ends (a 25-hour day),
    Adak in America/Adak (Hawaii-Aleutian daylight time, UTC-9, in June), and
    a western Aleutian station in whatever zone the catalog gives it."""
    cat = load()
    sf = cat.station("9414290")
    assert sf is not None
    fall = sky.sun_day(sf.lat, sf.lon, sf.tz, dt.date(2026, 11, 1))
    assert [e.time.utcoffset() for e in fall.events] == [dt.timedelta(hours=-8)] * 2
    assert fall.dark[-1][1] - fall.dark[0][0] == 25 * 3600  # midnight to midnight
    adak = cat.station("9461380")
    assert adak is not None and adak.tz == "America/Adak"
    june = sky.sun_day(adak.lat, adak.lon, adak.tz, dt.date(2027, 6, 21))
    assert {e.time.utcoffset() for e in june.events} == {dt.timedelta(hours=-9)}
    shemya = cat.station("TWC2309")
    assert shemya is not None
    for e in sky.sun_day(shemya.lat, shemya.lon, shemya.tz, dt.date(2027, 6, 21)).events:
        assert e.time.utcoffset() == dt.datetime(2027, 6, 21, 12, tzinfo=ZoneInfo(shemya.tz)).utcoffset()


def test_station_day_carries_the_sky() -> None:
    cat = load()
    st = cat.station(PRUDHOE)
    assert st is not None
    day = station_day(st, cat.predictor(PRUDHOE), dt.date(2026, 12, 21))
    assert day.sun_text == "The sun does not rise on this day (polar night)."
    assert day.moon_text.startswith("Moon: ")
    # The sun stays up to 4 degrees below the horizon at noon: civil twilight.
    assert day.civil_text.startswith("Civil dawn ")
    assert day.moonrise_text
    assert day.svg is not None and 'class="night"' in day.svg


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def winter(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Alaska in polar night at Prudhoe Bay, and Guam across the date line."""
    out = tmp_path_factory.mktemp("sky-site")
    assert cli.main(["--out", str(out), "--now", "2026-12-21T11:20:00Z", "--states", "AK,other"]) == 0
    return out


def test_built_pages_show_the_sky(winter: Path) -> None:
    html = (winter / f"stations/{PRUDHOE}/index.html").read_text(encoding="utf-8")
    assert html.count("The sun does not rise on this day (polar night).") == 2
    assert '<span class="sun">Sunrise' not in html
    juneau = (winter / "stations/9452210/index.html").read_text(encoding="utf-8")
    assert re.search(
        r'<span class="sun">Sunrise \d{1,2}:\d\d AM, sunset \d{1,2}:\d\d PM\. '
        r"Civil dawn \d{1,2}:\d\d AM, civil dusk \d{1,2}:\d\d PM\.</span>",
        juneau,
    )
    assert re.search(r"Moon(rise|set) \d{1,2}:\d\d [AP]M|No moon(rise|set) on this day", juneau)


def _sabotage(page: Path, old: str, new: str) -> None:
    html = page.read_text(encoding="utf-8")
    assert old in html
    page.write_text(html.replace(old, new, 1), encoding="utf-8")
    assert page.read_text(encoding="utf-8") != html  # the sabotage applied


@pytest.mark.parametrize("how", ["removed", "placeholder", "wrong-time", "moon", "civil", "moonrise"])
def test_check_site_catches_a_bad_sun_line(tmp_path: Path, winter: Path, how: str) -> None:
    """Negative controls: check_sky passes the build, then fails each
    sabotage of one page's sun and moon line."""
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(winter, root)
    cat = load()
    assert check.check_sky(root, cat) == []
    prudhoe = root / f"stations/{PRUDHOE}/index.html"
    juneau = root / "stations/9452210/index.html"
    if how == "removed":
        html = juneau.read_text(encoding="utf-8")
        line = re.search(r'<p class="sky".*?</p>', html, re.S)
        assert line is not None
        _sabotage(juneau, line.group(0), "")
        expect = "stations/9452210: sun and moon"
    elif how == "placeholder":
        _sabotage(prudhoe, "The sun does not rise on this day (polar night).", "Sunrise 00:00, sunset 00:00.")
        expect = f"stations/{PRUDHOE}: 2026-12-21: a sky line shows 00:00"
    elif how == "wrong-time":
        html = juneau.read_text(encoding="utf-8")
        m = re.search(r"Sunrise (\d{1,2}:\d\d) AM", html)
        assert m is not None
        _sabotage(juneau, m.group(0), "Sunrise 12:00 AM")
        expect = "stations/9452210: sun and moon"
    elif how == "moon":
        html = juneau.read_text(encoding="utf-8")
        m = re.search(r"Moon: [a-z ]+, \d+% lit", html)
        assert m is not None
        _sabotage(juneau, m.group(0), "Moon: full moon, 100% lit")
        expect = "stations/9452210: sun and moon"
    elif how == "civil":
        html = juneau.read_text(encoding="utf-8")
        m = re.search(r"civil dusk \d{1,2}:\d\d PM", html)
        assert m is not None
        _sabotage(juneau, m.group(0), "civil dusk 11:59 PM")
        expect = "stations/9452210: sun and moon"
    else:
        html = juneau.read_text(encoding="utf-8")
        m = re.search(r"Moon(rise|set) \d{1,2}:\d\d [AP]M", html)
        assert m is not None
        _sabotage(juneau, m.group(0), "Moonrise 12:00 AM")
        expect = "stations/9452210: sun and moon"
    found: list[str] = check.check_sky(root, cat)
    assert any(p.startswith(expect) for p in found), found
