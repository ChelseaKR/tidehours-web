"""The link to the Tide Hours print shop on Etsy (docs/DECISIONS.md 0029):
off by default, and off means no trace in the build; on means one plain link
on the About page and one on the English king-tide page, the privacy and
terms lines, and nothing anywhere else. Negative controls prove the off
check and check_site can fail."""

from __future__ import annotations

import html as htmllib
import importlib.util
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, printshop

NOW = "2026-11-01T11:20:00Z"
URL = "https://www.etsy.com/shop/TideHours"
TAG = "tidehours-20"
ETSY_A = re.compile(r'<a\b[^>]*href="(https://www\.etsy\.com/[^"]*)"[^>]*>', re.I)
SUFFIXES = (".html", ".xml", ".txt", ".json", ".css")
TERMS_OFF = "NOAA, other agency names, Apple and App Store are the names and trademarks of their owners."
TERMS_ON = "NOAA, other agency names, Apple, App Store and Etsy are the names and trademarks of their owners."
TERMS_BOTH = "NOAA, other agency names, Apple, App Store, Amazon and Etsy are the names and trademarks of their owners."


def build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "GU", *extra]) == 0
    return out


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("off"), "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("on"), "--ga4-id", "G-TEST123", "--print-shop-url", URL)


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_print_shop", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def text_of(html: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def traces(root: Path) -> list[str]:
    """Every file of a build that mentions Etsy at all. Shared by the off
    test and its negative control."""
    found = []
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.suffix in SUFFIXES and "etsy" in f.read_text(encoding="utf-8").lower():
            found.append(f.relative_to(root).as_posix())
    return found


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def test_valid_url_takes_a_shop_address_only() -> None:
    assert printshop.valid_url(URL)
    for bad in (
        "",
        URL + " ",
        URL + "\n",
        URL + "?ref=site",
        URL + "/",
        "http://www.etsy.com/shop/TideHours",
        "https://etsy.com/shop/TideHours",
        "https://www.etsy.com/listing/123456789/custom-tide-chart-print",
        "https://www.etsy.com.example.com/shop/TideHours",
        "https://www.etsy.com/shop/Ti",
    ):
        assert not printshop.valid_url(bad), bad


def test_cli_refuses_an_address_that_is_not_a_shop(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="--print-shop-url"):
        cli.main(["--out", str(tmp_path / "x"), "--now", NOW, "--states", "GU", "--print-shop-url", URL + "?ref=x"])


def test_off_leaves_no_trace(off: Path, check_site: Any) -> None:
    assert traces(off) == []
    assert TERMS_OFF in text_of(read(off, "terms"))
    assert check_site.check_print_shop(off, pages(off), "") == []


def test_off_check_can_fail(off: Path, tmp_path: Path, check_site: Any) -> None:
    """Negative control: put the link into an off build and both checks see it."""
    bad = tmp_path / "bad"
    shutil.copytree(off, bad)
    about = bad / "about" / "index.html"
    before = about.read_text(encoding="utf-8")
    after = before.replace("</main>", f'<p><a href="{URL}">shop</a></p></main>', 1)
    assert after != before  # the sabotage applied
    about.write_text(after, encoding="utf-8")
    assert traces(bad) == ["about/index.html"]
    assert check_site.check_print_shop(bad, pages(bad), "") == [
        "about/index.html: mentions etsy with no shop address set"
    ]


def test_on_links_from_about_and_the_english_king_tide_page_only(on: Path, check_site: Any) -> None:
    for rel in ("about", "king-tides"):
        html = read(on, rel)
        links = ETSY_A.findall(html)
        assert links == [URL], rel
        tag = ETSY_A.search(html)
        assert tag is not None and 'rel="noopener"' in tag.group(0), rel
        assert "data-ga-event" not in tag.group(0), rel
        assert "Tide Hours shop on Etsy" in text_of(html), rel
    assert sorted(traces(on)) == ["about/index.html", "king-tides/index.html", "privacy/index.html", "terms/index.html"]
    assert "etsy" not in read(on, "es/king-tides").lower()
    assert check_site.check_print_shop(on, pages(on), URL) == []


def test_on_privacy_and_terms_say_so(on: Path) -> None:
    privacy = read(on, "privacy")
    assert 'id="shop"' in privacy
    assert "This site sends nothing to Etsy." in text_of(privacy)
    assert ETSY_A.findall(privacy) == []
    assert TERMS_ON in text_of(read(on, "terms"))


def test_both_switches_name_both_marks(tmp_path: Path) -> None:
    both = build(tmp_path / "both", "--amazon-tag", TAG, "--print-shop-url", URL)
    assert TERMS_BOTH in text_of(read(both, "terms"))


def test_the_sentence_makes_no_claim() -> None:
    block = printshop.block(URL)
    assert block is not None
    prose = " ".join(str(v) for v in block["text"].values())
    assert not re.search(r"\b(best|top|only|first|cheap|deals?|rated|official)\b|[$%★]", prose, re.I)
    assert printshop.block("") is None
    with pytest.raises(ValueError, match="not an Etsy shop address"):
        printshop.block(URL + "?ref=x")


@pytest.mark.parametrize(
    ("name", "expect"),
    [
        ("missing", "about/index.html: no shop link with a shop address set"),
        ("repeated", "about/index.html: 2 etsy links, exactly 1 expected"),
        ("wrong address", "is not the configured shop address"),
        ("tracking rel", "rel is ['nofollow', 'noopener']"),
        ("another page", "etsy link outside about/, king-tides/"),
        ("in the sitemap", "sitemap.xml: mentions etsy"),
    ],
)
def test_check_site_catches_a_broken_on_build(
    on: Path, tmp_path: Path, check_site: Any, name: str, expect: str
) -> None:
    """Negative controls: each sabotage must change the build and be reported."""
    bad = tmp_path / "bad"
    shutil.copytree(on, bad)
    about = bad / "about" / "index.html"
    html = about.read_text(encoding="utf-8")
    tag = ETSY_A.search(html)
    assert tag is not None
    section = re.search(r'<section class="print-shop".*?</section>', html, re.S)
    assert section is not None
    target, before = about, html
    if name == "missing":
        after = html.replace(section.group(0), "")
    elif name == "repeated":
        after = html.replace(
            section.group(0), section.group(0) + section.group(0).replace('id="print-shop"', 'id="print-shop-2"')
        )
    elif name == "wrong address":
        after = html.replace(URL, URL + "?ref=x")
    elif name == "tracking rel":
        after = html.replace('rel="noopener"', 'rel="nofollow noopener"')
    elif name == "another page":
        target = sorted((bad / "stations").glob("*/index.html"))[0]
        before = target.read_text(encoding="utf-8")
        after = before.replace("</main>", f'<p><a href="{URL}" rel="noopener">shop</a></p></main>', 1)
    else:
        target = bad / "sitemap.xml"
        before = target.read_text(encoding="utf-8")
        after = before.replace("</urlset>", f"<url><loc>{URL}</loc></url></urlset>")
    assert after != before  # the sabotage applied
    target.write_text(after, encoding="utf-8")
    problems = check_site.check_print_shop(bad, pages(bad), URL)
    assert any(expect in p for p in problems), problems
