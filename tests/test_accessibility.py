"""Accessibility fixes found by the Accessibility Conformance Report of
2026-11-19 (docs/accessibility/ACR.md, docs/DECISIONS.md 0054), and the
checks that keep the accessibility gate looking at every kind of page.

Each test fails on the code before its fix."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli, htmlq

NOW = "2026-11-01T11:20:00Z"
ROOT = Path(__file__).resolve().parent.parent
SHOP = "https://www.etsy.com/shop/TideHoursTest"


@pytest.fixture(scope="module")
def with_analytics(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("ga")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "WA", "--ga4-id", "G-TEST123"]) == 0
    return out


def _choice(page: Path) -> htmlq.Element:
    els = htmlq.read(page.read_text(encoding="utf-8"))
    found = [el for el in els if el.attrs.get("id") == "analytics-choice"]
    assert len(found) == 1, page
    return found[0]


def test_english_analytics_control_is_marked_english_on_the_spanish_page(with_analytics: Path) -> None:
    # WCAG 3.1.2: the opt-out button and its status lines are English
    # (_ga4.html.jinja); on the Spanish king-tide page they are marked so a
    # screen reader speaks them in English.
    es = with_analytics / "es/king-tides/index.html"
    assert '<html lang="es">' in es.read_text(encoding="utf-8")
    assert _choice(es).attrs.get("lang") == "en"
    # The English pages need no mark, and carry none.
    for rel in ("king-tides/index.html", "index.html", "about/index.html"):
        assert "lang" not in _choice(with_analytics / rel).attrs, rel


def _sample_module() -> Any:
    spec = importlib.util.spec_from_file_location("site_sample_for_a11y", ROOT / "scripts" / "site_sample.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_checks_sample_has_every_page_kind(tmp_path: Path) -> None:
    # The terms page and the three state king-tide calendars are pages of
    # their own template; the axe and pa11y sample left them out.
    out = tmp_path / "site"
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "WA,OR,CA"]) == 0
    picked = _sample_module().sample(out)
    for page in ("terms/", "king-tides/washington/", "king-tides/oregon/", "king-tides/california/"):
        assert (out / page / "index.html").is_file(), page
        assert page in picked, page
    assert len(picked) == len(set(picked))


def test_site_checks_build_shows_the_shop_and_analytics_surfaces() -> None:
    # The Prints sections (about, king-tide hub and state calendars) and the
    # footer's analytics opt-out appear only with a shop address and a GA4
    # ID, so the gate's build sets both; its browsers block Google Analytics.
    run = (ROOT / "tools/site-checks/run.sh").read_text(encoding="utf-8")
    build = next(line for line in run.splitlines() if "tidehours --out" in line)
    assert "--print-shop-url https://www.etsy.com/shop/" in build
    assert "--ga4-id G-" in build
    assert "googletagmanager" in (ROOT / "tools/site-checks/axe.mjs").read_text(encoding="utf-8")
    assert "googletagmanager.com" in run


def test_site_checks_axe_checks_contrast_in_dark_mode() -> None:
    # The site has a dark palette (prefers-color-scheme); the gate checked
    # contrast in light mode only.
    axe = (ROOT / "tools/site-checks/axe.mjs").read_text(encoding="utf-8")
    assert '{ name: "prefers-color-scheme", value: "dark" }' in axe
    assert 'withRules(["color-contrast"' in axe
