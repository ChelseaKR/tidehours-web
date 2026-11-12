"""Readers see a time zone's name, not its IANA id, and the king-tide tables'
sideways-scrolling boxes can be reached and named from the keyboard."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tidehours import cli, zones
from tidehours.catalog import load

NOW = "2026-11-01T11:20:00Z"
IANA = re.compile(r"\b(?:America|Pacific|Asia|Europe|Etc)/[A-Za-z_]+")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("zones-site")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI,GU,AS,VI"]) == 0
    return out


def test_every_zone_in_the_catalog_has_a_name() -> None:
    used = {s.tz for s in load().stations}
    assert len(used) >= 10  # the measured catalog has 12
    missing = sorted(used - zones.NAMES.keys())
    assert not missing, f"add a plain name to zones.NAMES for {missing}"
    for tz in used:
        name = zones.label(tz)
        assert name.strip() and name != tz and not IANA.search(name)


def test_names_of_the_zones_readers_ask_about() -> None:
    assert zones.label("America/Los_Angeles") == "Pacific Time (PT)"
    assert zones.label("America/Adak") == "Hawaii–Aleutian Time (HST/HDT)"
    assert zones.label("Pacific/Honolulu") == "Hawaii Standard Time (HST)"
    assert zones.label("Pacific/Guam") == "Chamorro Standard Time (ChST)"
    assert zones.label("Pacific/Pago_Pago") == "Samoa Standard Time (SST)"
    assert zones.label("Pacific/Apia") == "Samoa Time (Apia, UTC+13)"
    assert zones.label("America/Puerto_Rico") == zones.label("America/St_Thomas") == "Atlantic Standard Time (AST)"


def test_a_zone_without_a_name_falls_back_to_its_offset() -> None:
    assert zones.label("Asia/Kathmandu", 2026) == "UTC+5:45"
    assert zones.label("Europe/London", 2026) == "UTC+0/+1"
    assert zones.label("America/Santiago", 2026) == "UTC−4/−3"  # daylight time in January
    assert zones.label("Etc/GMT+10", 2026) == "UTC−10"
    assert zones.label("Not/AZone") == zones.UNKNOWN
    assert zones.label("") == zones.UNKNOWN
    assert zones.label("../etc") == zones.UNKNOWN
    assert zones.label("Asia/Tokyo").startswith("UTC+9")  # the current year by default


def _lede(page: str) -> str:
    m = re.search(r'<p class="lead">(.*?)</p>', page, re.S)
    assert m
    return m.group(1)


def test_station_pages_name_the_zone(built: Path) -> None:
    cases = {
        "1612340": "Times are Hawaii Standard Time (HST), local to the station;",  # Honolulu
        "1630000": "Times are Chamorro Standard Time (ChST), local to the station;",  # Apra Harbor, Guam
    }
    for sid, words in cases.items():
        page = (built / f"stations/{sid}/index.html").read_text(encoding="utf-8")
        assert words in _lede(page)
    pages = sorted(built.glob("stations/*/index.html"))
    assert len(pages) >= 40
    for p in pages:
        page = p.read_text(encoding="utf-8")
        lede = _lede(page)
        assert not IANA.search(lede), p
        assert "Times are , " not in lede and "Times are  " not in lede, p
        assert re.search(r'data-tz="[A-Za-z_]+/[A-Za-z_]+"', page), p  # the script still gets the id


class _Scrollers(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.boxes: list[dict[str, str | None]] = []
        self.ids: list[str] = []
        self.caption_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(str(a["id"]))
        if tag == "caption" and a.get("id"):
            self.caption_ids.add(str(a["id"]))
        if tag == "div" and "table-scroll" in (a.get("class") or "").split():
            self.boxes.append(a)


@pytest.mark.parametrize("path", ["king-tides/index.html", "es/king-tides/index.html"])
def test_king_tide_scroll_boxes_are_reachable_and_named(built: Path, path: str) -> None:
    parser = _Scrollers()
    parser.feed((built / path).read_text(encoding="utf-8"))
    assert len(parser.boxes) >= 10  # the coming-up table and one per station
    for box in parser.boxes:
        assert box.get("role") == "region" and box.get("tabindex") == "0"
        assert box.get("aria-labelledby") in parser.caption_ids
    assert len(parser.ids) == len(set(parser.ids)), "duplicate ids"


def test_scroll_box_css() -> None:
    css = (Path(zones.__file__).parent / "templates/style.css").read_text(encoding="utf-8")
    assert re.search(r"\.table-scroll:focus-visible[^{]*\{[^}]*outline:", css)
    rule = re.search(r"\.table-scroll \{([^}]*)\}", css)
    assert rule and "position: relative" in rule.group(1)  # the hidden caption cannot widen the page
    assert "display: block" not in rule.group(1)
