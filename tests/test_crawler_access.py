"""What a search or AI-answer crawler may do with every sitemap page
(docs/DECISIONS.md 0048): robots.txt lets each named crawler fetch it, and no
page tells a crawler not to keep or quote it. Negative controls prove
check_site's check_crawlers fails a robots.txt or a page that breaks either
rule, and that a robots.txt the old Bingbot-only check passes can still shut
out the others."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli
from tidehours import indexnow as ix

NOW = "2026-11-13T11:20:00Z"
SITEMAP_LINE = "Sitemap: https://tidehours.com/sitemap.xml\n"
OTHERS = {"bingbot", "OAI-SearchBot", "ChatGPT-User", "GPTBot", "PerplexityBot", "ClaudeBot"}


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("crawlers")
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "RI,OR"]) == 0
    return out


def _shut_out(problems: list[str]) -> set[str]:
    return {p.split(" ")[1] for p in problems if p.startswith("robots.txt: ")}


def test_the_build_lets_every_named_crawler_fetch_every_sitemap_page(built: Path) -> None:
    check = _check_site()
    assert set(check.CRAWLERS) == OTHERS
    assert len(check.LOC.findall((built / "sitemap.xml").read_text(encoding="utf-8"))) > 20
    assert check.check_crawlers(built) == []


ROBOTS_CASES: dict[str, tuple[str, set[str]]] = {
    # A group that names one crawler replaces "*" for it.
    "search crawler named and blocked": (
        "User-agent: OAI-SearchBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
        {"OAI-SearchBot"},
    ),
    # The longest rule wins, so "Allow: /" does not save a blocked folder.
    "station pages blocked for all": ("User-agent: *\nAllow: /\nDisallow: /stations/\n", OTHERS),
    # Blocking the training crawlers leaves the search and answer ones in.
    "training crawlers blocked": (
        "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
        {"GPTBot", "ClaudeBot"},
    ),
    # A wildcard rule with an end anchor.
    "wildcard": ("User-agent: perplexitybot\nDisallow: /stat*/*/$\n\nUser-agent: *\nAllow: /\n", {"PerplexityBot"}),
    "everything blocked": ("User-agent: *\nDisallow: /\n", OTHERS),
}


@pytest.mark.parametrize("how", sorted(ROBOTS_CASES))
def test_check_crawlers_catches_a_robots_file_that_shuts_a_crawler_out(tmp_path: Path, built: Path, how: str) -> None:
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    assert check.check_crawlers(root) == []
    robots, expect = ROBOTS_CASES[how]
    (root / "robots.txt").write_text(robots + "\n" + SITEMAP_LINE, encoding="utf-8")
    assert _shut_out(check.check_crawlers(root)) == expect


def test_the_bingbot_only_check_passes_a_file_that_shuts_out_chatgpt(built: Path) -> None:
    """Why check_crawlers exists: indexnow.check_robots asks only whether
    Bingbot may fetch the site root."""
    check = _check_site()
    robots = (
        "User-agent: OAI-SearchBot\nUser-agent: ChatGPT-User\nDisallow: /\n\nUser-agent: *\nAllow: /\n\n" + SITEMAP_LINE
    )
    assert ix.check_robots(robots, "https://tidehours.com") == []
    locs = check.LOC.findall((built / "sitemap.xml").read_text(encoding="utf-8"))
    shut = [
        c for c in check.CRAWLERS if not all(check.may_fetch(check.robots_rules(robots, c), "/" + loc) for loc in locs)
    ]
    assert shut == ["OAI-SearchBot", "ChatGPT-User"]


def test_the_longest_rule_wins_and_allow_wins_a_tie() -> None:
    check = _check_site()
    robots = "User-agent: *\nDisallow: /stations/\nAllow: /stations/8413320/\nAllow: /states/\nDisallow: /states/\n"
    rules = check.robots_rules(robots, "bingbot")
    assert not check.may_fetch(rules, "/stations/9414290/")
    assert check.may_fetch(rules, "/stations/8413320/")
    assert check.may_fetch(rules, "/states/me/")
    assert check.may_fetch(rules, "/king-tides/")
    assert check.may_fetch(check.robots_rules("", "bingbot"), "/anything/")
    # An empty Disallow allows everything, and a comment is not a rule.
    assert check.may_fetch(check.robots_rules("User-agent: *\nDisallow:\n# Disallow: /\n", "GPTBot"), "/stations/1/")


META_CASES: dict[str, tuple[str, list[str]]] = {
    "noarchive": ('<meta name="robots" content="noarchive">', ["robots: noarchive"]),
    "nocache for bing": ('<meta name="bingbot" content="index, NOCACHE">', ["bingbot: nocache"]),
    "nosnippet, content first": ('<meta content="nosnippet" name="robots">', ["robots: nosnippet"]),
    "no snippet length": ('<meta name="robots" content="max-snippet:0">', ["robots: max-snippet:0"]),
    "a snippet length": ('<meta name="robots" content="max-snippet:160">', []),
    "google alone": ('<meta name="googlebot" content="noarchive">', []),
    "not a robots tag": ('<meta name="description" content="nocache">', []),
}


@pytest.mark.parametrize("how", sorted(META_CASES))
def test_check_crawlers_catches_a_page_that_limits_keeping_or_quoting_it(tmp_path: Path, built: Path, how: str) -> None:
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    tag, expect = META_CASES[how]
    assert check.quote_limits(f"<html><head>{tag}</head></html>") == expect
    page = root / "states/or/index.html"
    html = page.read_text(encoding="utf-8")
    assert html.count("<head>") == 1
    page.write_text(html.replace("<head>", "<head>\n" + tag), encoding="utf-8")
    assert check.check_crawlers(root) == [f"states/or/: {limit}" for limit in expect]


def test_a_noindex_page_outside_the_sitemap_may_carry_a_limit(tmp_path: Path, built: Path) -> None:
    """The rule is about pages the site offers to crawlers, which is the sitemap."""
    check = _check_site()
    root = tmp_path / "site"
    shutil.copytree(built, root)
    (root / "404.html").write_text(
        '<html><head><meta name="robots" content="noindex,noarchive"></head></html>', encoding="utf-8"
    )
    assert check.check_crawlers(root) == []


def test_check_site_runs_the_crawler_check(built: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    check = _check_site()
    seen: list[Path] = []

    def record(root: Path) -> list[str]:
        seen.append(root)
        return []

    monkeypatch.setattr(check, "check_crawlers", record)
    check.main(built)  # a two-state build fails the page-count floor; only the call matters here
    assert seen == [built]
