"""The design layer's promises: every chart names its datum and draws 0 ft
only when 0 ft is inside the drawing, every page carries the mark, the
favicon and the "how to read" link, and the reading guide explains the
datum. Colors are checked separately (WCAG contrast below)."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from tidehours import cli
from tidehours.catalog import Station
from tidehours.days import station_day

NOW = "2026-11-01T11:20:00Z"
CSS = Path(__file__).parent.parent / "src" / "tidehours" / "templates" / "style.css"


class Sine:
    """A fake predictor: one high and one low around a chosen mean level."""

    def __init__(self, mean: float) -> None:
        self.mean = mean

    def events(self, start: float, end: float) -> list[object]:
        return []

    def curve(self, start: float, end: float, step: float) -> list[tuple[float, float]]:
        n = int((end - start) // step)
        return [(start + i * step, self.mean + (1.0 if i < n / 2 else -1.0)) for i in range(n + 1)]


STATION = Station("1", "Somewhere", "CA", 0.0, 0.0, "America/Los_Angeles", "2", None)


def test_chart_draws_the_datum_when_zero_is_in_range() -> None:
    svg = station_day(STATION, Sine(0.5), dt.date(2026, 11, 1)).svg  # type: ignore[arg-type]
    assert svg is not None
    assert svg.count('class="grid datum"') == 1
    assert "feet above mean lower low water (MLLW); the dotted line is 0 ft, the datum." in svg


def test_chart_names_the_datum_without_a_line_when_zero_is_out_of_range() -> None:
    svg = station_day(STATION, Sine(8.0), dt.date(2026, 11, 1)).svg  # type: ignore[arg-type]
    assert svg is not None
    assert "datum" not in svg.split('<div class="ax-key">')[0]
    assert "Heights in feet above mean lower low water (MLLW)." in svg
    assert "dotted line" not in svg


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI"]) == 0
    return out


def test_every_page_has_the_mark_favicon_and_reading_link(built: Path) -> None:
    assert (built / "favicon.svg").read_text(encoding="utf-8").startswith("<svg")
    files = sorted(built.rglob("*.html"))
    assert len(files) > 20
    for f in files:
        html = f.read_text(encoding="utf-8")
        if '<meta http-equiv="refresh"' in html:
            continue
        rel = f.relative_to(built)
        assert '<link rel="icon" href="/favicon.svg"' in html, rel
        assert '<a class="brand" href="/">' in html and "<span>Tide Hours</span>" in html, rel
        assert 'href="/about/#reading"' in html, rel
        assert 'class="wave-rule" aria-hidden="true"' in html, rel


def test_reading_guide_explains_the_datum_and_absence(built: Path) -> None:
    about = (built / "about/index.html").read_text(encoding="utf-8")
    section = about.split('id="reading"', 1)[1].split("</section>", 1)[0]
    assert "mean lower low water (MLLW)" in section and "dotted line is 0 ft" in section
    assert "never shows a zero" in section
    assert "predictions, not observations or flood forecasts" in section


def test_station_charts_carry_the_key(built: Path) -> None:
    html = (built / "stations/1612340/index.html").read_text(encoding="utf-8")
    assert html.count('<svg class="tide-chart"') == html.count('<div class="ax-key">Heights in feet above') == 2


# WCAG 2.x contrast, computed from the tokens in style.css.
def _lum(hex_: str) -> float:
    rgb = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})", block))


TEXT_PAIRS = [
    ("fg", "bg"),
    ("muted", "bg"),
    ("link", "bg"),
    ("brand", "bg"),
    ("high", "bg"),
    ("low", "bg"),
    ("fg", "surface"),
    ("muted", "surface"),
    ("high", "surface"),
    ("low", "surface"),
    ("brand", "surface"),
    ("fg", "panel"),
    ("muted", "panel"),
    ("link", "panel"),
    ("fg", "warn"),
    ("link", "warn"),
    ("fg", "buoy-tint"),
    ("link", "buoy-tint"),
    ("foot-fg", "foot-bg"),
    ("foot-link", "foot-bg"),
    ("on-brand", "brand"),
]
GRAPHIC_PAIRS = [("curve", "surface"), ("datum", "surface"), ("buoy", "buoy-tint"), ("brand", "bg")]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_tokens_meet_wcag_aa(scheme: str) -> None:
    css = CSS.read_text(encoding="utf-8")
    light = _tokens(css.split("@media (prefers-color-scheme: dark)")[0])
    dark = {**light, **_tokens(css.split("@media (prefers-color-scheme: dark)")[1].split("}")[0])}
    t = light if scheme == "light" else dark
    for fg, bg in TEXT_PAIRS:
        assert _ratio(t[fg], t[bg]) >= 4.5, (scheme, fg, bg, round(_ratio(t[fg], t[bg]), 2))
    for fg, bg in GRAPHIC_PAIRS:
        assert _ratio(t[fg], t[bg]) >= 3.0, (scheme, fg, bg, round(_ratio(t[fg], t[bg]), 2))
