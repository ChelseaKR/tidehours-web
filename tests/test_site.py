"""The built site: every page carries what the product promises (predictions
not observations, not for navigation, not a NOAA product, the NOAA credit,
the app marked "coming soon"), nothing absent renders as a value, and the
config switches (GA4, App Store link) do what they say."""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tidehours import cli, site
from tidehours.catalog import Station, load
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
        for bad in ("None", "nan ft", "NaN", "undefined", "{{", "{place}", "{id}"):
            assert bad not in re.sub(r"<script.*?</script>", "", html, flags=re.S), (rel, bad)
        assert re.search(r"<title>[^<]+</title>", html), rel
        assert '<html lang="' in html, rel


def test_station_pages(built: Path) -> None:
    sf = (built / "stations/9414290/index.html").read_text(encoding="utf-8")
    assert "SAN FRANCISCO (Golden Gate), CA tide times" in sf
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
    assert "gives these" in other and "no state" in other
    urls = [
        el.text
        for el in ET.parse(built / "sitemap.xml")  # noqa: S314 - our own build output
        .getroot()
        .iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    ]
    assert len(urls) == len(pages(built)) - 1  # every page but 404.html
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
    day = station_day(s, Flat(), dt.date(2026, 11, 1), "Today")  # type: ignore[arg-type]
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
