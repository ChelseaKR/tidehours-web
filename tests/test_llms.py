"""/llms.txt: built at the site root from the catalog, uploaded as text/plain,
carrying the site's promises and no placeholder."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

import pytest

from tidehours import cli, llms
from tidehours.catalog import load

NOW = "2026-11-01T11:20:00Z"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("llms")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "CA,HI,other"]) == 0
    return out


def test_llms_txt_is_built_and_typed_as_text(built: Path) -> None:
    assert (built / "llms.txt").is_file()
    # deploy.sh's second sync lets the AWS CLI pick the type from the extension.
    assert mimetypes.guess_type("llms.txt")[0] == "text/plain"
    deploy = (Path(__file__).parents[1] / "scripts" / "deploy.sh").read_text()
    assert "--exclude '*.html'" in deploy


def test_llms_txt_says_what_the_numbers_are(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# Tide Hours\n\n> ")
    for promise in (
        "predictions, not observations",
        "not for navigation",
        "not a NOAA product",
        "NOAA CO-OPS",
        "mean lower low water (MLLW)",
        "## Pages",
        "## Sources",
        "/king-tides/california/",
        "/king-tides/washington/",
        "/king-tides/oregon/",
        "coming soon",
    ):
        assert promise in text, promise


def test_llms_txt_numbers_come_from_the_catalog(built: Path) -> None:
    cat = load()
    text = (built / "llms.txt").read_text(encoding="utf-8")
    assert f"{len(cat.stations):,} NOAA tide stations" in text
    assert f"retrieved on {cat.retrieved}" in text


def test_llms_txt_has_no_placeholder(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    for bad in ("TO" + "DO", "T" + "BD", "lorem", "X" * 3, "None", "{", "}"):
        assert bad not in text, bad
    assert not re.search(r"\b0 stations\b", text)


CALENDARS_LINE = (
    "- [Printable 2027 tide calendars and posters](https://tidehours.com/tide-calendars/): "
    "every printable calendar and poster, by state"
)
GIFTS_LINE = (
    "- [Tide chart gifts and tide art prints](https://tidehours.com/tide-gifts/): "
    "every Tide Hours product, by kind and by town"
)


def test_llms_txt_lists_the_calendars_and_gifts_pages_after_california() -> None:
    # The owner's wording of 2026-11-15, right after the California calendar.
    lines = llms.render(load(), "https://tidehours.com", printables_page=True, gifts_page=True).splitlines()
    california = next(i for i, line in enumerate(lines) if line.startswith("- [California king tides]("))
    assert lines[california + 1 : california + 3] == [CALENDARS_LINE, GIFTS_LINE]


def test_llms_txt_lists_a_page_only_when_the_build_has_it(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    for path, line in (("tide-calendars", CALENDARS_LINE), ("tide-gifts", GIFTS_LINE)):
        assert (line in text) == (built / path / "index.html").is_file(), path
    cat = load()
    text = llms.render(cat, "https://tidehours.com")
    assert "/tide-calendars/" not in text and "/tide-gifts/" not in text
    text = llms.render(cat, "https://tidehours.com", gifts_page=True)
    assert "/tide-calendars/" not in text and GIFTS_LINE in text
