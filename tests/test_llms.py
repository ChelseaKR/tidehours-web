"""/llms.txt: built at the site root from the catalog, uploaded as text/plain,
carrying the site's promises and no placeholder."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

import pytest

from tidehours import cli
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
