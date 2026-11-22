"""Shop link clicks (docs/DECISIONS.md 0057): with GA4 on, a page that links
to the Tide Hours shop on Etsy carries one click handler that sends
`shop_click` with `link_kind` ("shop" or "listing") only, never the link's
address; no other page changes, and the Etsy links themselves keep no
`data-ga` attribute. The privacy page says so in the owner's sentence, word
for word, whenever the site links to Etsy, and not otherwise."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest

from tidehours import calendars, cli, posters, site

NOW = "2026-11-20T11:20:00Z"
URL = "https://www.etsy.com/shop/TideHours"
GA = "G-TEST123"
STATES = "WA,OR,CA"
# The owner's sentence, approved 2026-11-21, word for word.
SENTENCE = (
    "It also counts a click on a link to the Tide Hours shop on Etsy, noting only whether the link "
    "went to the shop or to one listing, not its address."
)
HANDLER = '"shop_click"'
ETSY_A = re.compile(r'<a\b[^>]*\bhref="https://www\.etsy\.com/[^"]*"[^>]*>')


def build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", STATES, *extra]) == 0
    return out


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("on"), "--ga4-id", GA, "--print-shop-url", URL)


@pytest.fixture(scope="module")
def no_ga(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("noga"), "--print-shop-url", URL)


@pytest.fixture(scope="module")
def no_etsy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # Guam: no calendar, poster or gift, and no shop address, so no Etsy link.
    out = tmp_path_factory.mktemp("noetsy")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "GU", "--ga4-id", GA]) == 0
    return out


@pytest.fixture(scope="module")
def check_site() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_site.py"
    spec = importlib.util.spec_from_file_location("check_site_for_shop_click", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pages(root: Path) -> dict[str, str]:
    return {f.relative_to(root).as_posix(): f.read_text(encoding="utf-8") for f in sorted(root.rglob("*.html"))}


def ga_script(html: str) -> str:
    start = html.index("<script>\n(function () {")
    return html[start : html.index("</script>", start)]


def handler(html: str) -> str:
    script = ga_script(html)
    start = script.index("// Shop link clicks")
    return script[start : script.index("});\n", script.index('gtag("event", "shop_click"')) + 4]


def test_handler_only_on_pages_that_link_to_etsy(on: Path) -> None:
    built = pages(on)
    with_links = {rel for rel, html in built.items() if ETSY_A.search(html)}
    with_handler = {rel for rel, html in built.items() if HANDLER in html}
    # The hub, a state calendar and at least one station page with a calendar.
    assert {"king-tides/index.html", "king-tides/washington/index.html", "about/index.html"} <= with_links
    assert any(rel.startswith("stations/") for rel in with_links)
    assert with_handler == with_links
    # The privacy and terms pages name Etsy in words only, so no handler.
    assert HANDLER not in built["privacy/index.html"] and HANDLER not in built["terms/index.html"]


def test_handler_sends_kind_only_and_runs_after_the_guards(on: Path) -> None:
    html = (on / "king-tides" / "washington" / "index.html").read_text(encoding="utf-8")
    script = ga_script(html)
    assert script.index("if (optedOut) return;") < script.index("// Shop link clicks")
    code = handler(html)
    params = code[code.index('gtag("event", "shop_click", {') :]
    # One parameter, from the path's first segment; the address never leaves.
    assert re.findall(r"^\s+(\w+):", params, re.M) == ["link_kind"]
    for leak in (".href", "getAttribute", "a.pathname,", "location", "+ a."):
        assert leak not in params, leak
    assert '"listing" : "shop"' in params
    assert 'a.hostname !== "www.etsy.com"' in code


def test_etsy_links_carry_no_data_ga(on: Path) -> None:
    for rel, html in pages(on).items():
        for m in ETSY_A.finditer(html):
            assert "data-ga" not in m.group(0), rel


def test_privacy_sentence(on: Path, no_ga: Path, no_etsy: Path) -> None:
    privacy = (on / "privacy" / "index.html").read_text(encoding="utf-8")
    first = "This site uses Google Analytics 4 to count page views."
    assert f"{first} {SENTENCE} It does not load" in privacy
    assert SENTENCE not in (no_ga / "privacy" / "index.html").read_text(encoding="utf-8")
    no_link = (no_etsy / "privacy" / "index.html").read_text(encoding="utf-8")
    assert first in no_link and SENTENCE not in no_link and "etsy" not in no_link.lower()


def test_nothing_without_ga4_or_without_etsy(no_ga: Path, no_etsy: Path) -> None:
    for root in (no_ga, no_etsy):
        assert not [rel for rel, html in pages(root).items() if "shop_click" in html]


def test_check_site_still_passes(on: Path, check_site: Any) -> None:
    want_calendars, problems = check_site.calendar_pages(on, calendars.load())
    want_posters, more = check_site.poster_pages(on, posters.load())
    assert problems == [] and more == []
    html = sorted(on.rglob("*.html"))
    assert check_site.check_print_shop(on, html, URL, want_calendars, want_posters) == []


def test_handler_is_the_only_page_change(on: Path, tmp_path: Path) -> None:
    """Negative control: with the handler stripped, a page with Etsy links
    is byte for byte what the build gives when no page gets the handler."""
    real = site.ETSY_LINK
    try:
        site.ETSY_LINK = "\x00never in a page\x00"
        plain = build(tmp_path / "plain", "--ga4-id", GA, "--print-shop-url", URL)
    finally:
        site.ETSY_LINK = real
    for rel in ("king-tides/washington/index.html", "about/index.html", "privacy/index.html"):
        html = (on / rel).read_text(encoding="utf-8")
        before = (plain / rel).read_text(encoding="utf-8")
        if HANDLER in html:
            assert html != before
            html, n = re.subn(r"\n\n  // Shop link clicks:.*?\n  \}\);\n", "\n", html, flags=re.S)
            assert n == 1, rel
        assert html == before, rel


def test_check_site_refuses_a_stray_handler(on: Path, check_site: Any) -> None:
    """Negative control: the handler on a page with no Etsy link, or reading
    the address, is a problem; on a page with one, it is set aside."""
    html = (on / "king-tides" / "washington" / "index.html").read_text(encoding="utf-8")
    block = re.search(r"\n\n  // Shop link clicks:.*?\n  \}\);\n", html, re.S)
    assert block is not None
    text, problems = check_site._without_shop_click("ok", html)
    assert problems == [] and HANDLER not in text and "etsy" in text.lower()
    stray = ETSY_A.sub("", html)
    assert check_site._without_shop_click("stray", stray)[1] == ["stray: a shop_click handler with no Etsy link"]
    leaky = html.replace(block.group(0), block.group(0).replace("a.pathname.indexOf", "a.href.indexOf"))
    assert check_site._without_shop_click("leaky", leaky)[1] == [
        "leaky: the shop_click handler reads an attribute or the address"
    ]
