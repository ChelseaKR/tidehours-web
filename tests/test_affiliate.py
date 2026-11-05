"""Amazon affiliate links (docs/DECISIONS.md 0016): off by default, and off
means no trace in the build; on means four tagged searches on the English
king-tide page only, after the method section, with the disclosure next to
them, and the privacy, terms and about lines. Negative controls prove the
off checks and check_site can fail."""

from __future__ import annotations

import html as htmllib
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from tidehours import affiliate, cli, site

NOW = "2026-11-01T11:20:00Z"
TAG = "tidehours-20"
AMAZON_A = re.compile(r'<a\b[^>]*href="(https://www\.amazon\.com/[^"]*)"[^>]*>', re.I)
# Words and signs the block's own prose must never use (no claims, prices or ratings).
FORBIDDEN = re.compile(r"\b(best|top|only|first|cheap|deals?|rated)\b|[$%★]", re.I)
PRIVACY_OFF = ("no accounts, no forms and no ads.",)
TERMS_OFF = "NOAA, other agency names, Apple and App Store are the names and trademarks of their owners."
TERMS_ON = "NOAA, other agency names, Apple, App Store and Amazon are the names and trademarks of their owners."


def build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "GU", *extra]) == 0
    return out


@pytest.fixture(scope="module")
def off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("off"), "--ga4-id", "G-TEST123")


@pytest.fixture(scope="module")
def on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("on"), "--ga4-id", "G-TEST123", "--amazon-tag", TAG)


def read(root: Path, rel: str) -> str:
    return (root / rel / "index.html").read_text(encoding="utf-8")


def text_of(html: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def off_problems(root: Path) -> list[str]:
    """Everything the switch-off build must not contain. Shared by the off
    test and its negative control, so the control exercises the same checks."""
    problems: list[str] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in (".html", ".xml", ".txt", ".json"):
            continue
        body = f.read_text(encoding="utf-8")
        rel = f.relative_to(root).as_posix()
        if "amazon.com" in body.lower():
            problems.append(f"{rel}: amazon.com")
        if affiliate.DISCLOSURE in body:
            problems.append(f"{rel}: disclosure")
        if "gear_click" in body:
            problems.append(f"{rel}: gear_click")
    privacy = text_of(read(root, "privacy"))
    if not all(p in privacy for p in PRIVACY_OFF) or "display ads" in privacy or "Affiliate links" in privacy:
        problems.append("privacy: changed")
    if TERMS_OFF not in text_of(read(root, "terms")) or "Amazon" in read(root, "terms"):
        problems.append("terms: changed")
    if "affiliate" in read(root, "about"):
        problems.append("about: changed")
    return problems


def _check_site() -> Any:
    spec = importlib.util.spec_from_file_location("check_site", Path(__file__).parent.parent / "scripts/check_site.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def affiliate_problems(root: Path, tag: str) -> list[str]:
    found: list[str] = _check_site().check_affiliate(root, sorted(root.rglob("*.html")), tag)
    return found


def test_off_by_default() -> None:
    assert site.Config().amazon_tag == ""
    assert affiliate.block("") is None


def test_switch_off_build_has_no_trace(off: Path) -> None:
    assert off_problems(off) == []
    assert affiliate_problems(off, "") == []


def test_off_test_fails_when_the_switch_is_forced_on(on: Path) -> None:
    """Negative control: the same off checks, run on a build with the switch
    forced on, must fail on every count."""
    assert AMAZON_A.search(read(on, "king-tides"))  # the switch really is on
    found = off_problems(on)
    assert "king-tides/index.html: amazon.com" in found
    assert "king-tides/index.html: disclosure" in found
    assert "privacy: changed" in found and "terms: changed" in found and "about: changed" in found
    assert affiliate_problems(on, "") != []


def test_switch_on_links(on: Path) -> None:
    en = read(on, "king-tides")
    links = AMAZON_A.findall(en)
    assert len(links) == 4
    copy = json.loads(affiliate.COPY.read_text(encoding="utf-8"))
    want_terms = [item["terms"] for item in copy["links"]]
    assert want_terms == ["phone tripod", "waterproof phone pouch", "waterproof rubber boots", "rain jacket"]
    for href, terms in zip(links, want_terms, strict=True):
        parts = urlsplit(htmllib.unescape(href))
        assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.amazon.com/s"
        assert parse_qs(parts.query) == {"k": [terms], "tag": [TAG]}
    for a in re.findall(r"<a\b[^>]*amazon\.com[^>]*>", en):
        assert 'rel="sponsored nofollow noopener"' in a
    labels = re.findall(r'data-ga-type="amazon_search"[^>]*>([^<]+)</a>', en)
    assert labels == ["Phone tripod", "Waterproof phone pouch", "Rubber boots", "Rain jacket"]
    assert affiliate_problems(on, TAG) == []


def test_links_only_on_the_english_king_tide_page(on: Path) -> None:
    for f in on.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".xml", ".txt", ".json"):
            rel = f.relative_to(on).as_posix()
            if rel != "king-tides/index.html":
                assert "amazon.com" not in f.read_text(encoding="utf-8").lower(), rel
    assert affiliate.DISCLOSURE not in read(on, "es/king-tides")


def test_disclosure_next_to_the_links_after_the_method(on: Path) -> None:
    en = read(on, "king-tides")
    first = AMAZON_A.search(en)
    assert first is not None
    method = en.index('id="kt-method"')
    app_body = json.loads((Path(affiliate.__file__).parent / "copy" / "king_tides.json").read_text(encoding="utf-8"))
    app_line = en.index(str(htmllib.escape(app_body["en"]["app"]["body"], quote=True)), method)  # c.app.body
    disclosure = en.index(affiliate.DISCLOSURE)
    assert en.count(affiliate.DISCLOSURE) == 1
    assert method < app_line < en.index("</section>", method) < disclosure < first.start()
    between = en[disclosure : first.start()]
    assert "<h2" not in between and "</section>" not in between  # next to the links, same section
    block = en[en.index('<section class="affiliate"') :]
    prose = text_of(block)
    assert "As an Amazon Associate I earn from qualifying purchases." in prose
    assert "NOAA does not endorse them or Amazon" in prose
    assert "The California Coastal Commission does not endorse them either." in prose
    assert FORBIDDEN.search(prose) is None, FORBIDDEN.search(prose)
    assert "<img" not in block


def test_no_price_strings(on: Path) -> None:
    en = read(on, "king-tides")
    block = text_of(en[en.index('<section class="affiliate"') :])
    privacy = text_of(read(on, "privacy"))
    about = text_of(read(on, "about"))
    for rel, page in (("king-tides block", block), ("privacy", privacy), ("about", about)):
        assert not re.search(r"[$€£]|\bUSD\b|\bdollars?\b|\bprice", page, re.I), rel


def test_privacy_terms_and_about_when_on(on: Path, off: Path) -> None:
    privacy = text_of(read(on, "privacy"))
    assert "no accounts, no forms and no display ads." in privacy
    assert "no ads." not in privacy
    assert 'id="affiliate"' in read(on, "privacy")
    assert "As an Amazon Associate I earn from qualifying purchases." in privacy
    assert "Amazon Services LLC" not in privacy
    assert TERMS_ON in text_of(read(on, "terms"))
    assert 'Some pages carry Amazon affiliate links; see <a href="/privacy/#affiliate">Privacy</a>.' in read(
        on, "about"
    )
    assert 'href="/privacy/#affiliate"' in read(on, "king-tides")
    assert "no display ads" not in text_of(read(off, "privacy"))


def test_privacy_without_analytics(tmp_path: Path) -> None:
    plain_on = text_of(read(build(tmp_path / "on", "--amazon-tag", TAG), "privacy"))
    assert "no forms and no display ads. The host" in plain_on
    plain_off = text_of(read(build(tmp_path / "off"), "privacy"))
    assert "no forms and no ads. The host" in plain_off and "Affiliate" not in plain_off


def test_tag_comes_from_config(tmp_path: Path) -> None:
    other = build(tmp_path / "other", "--amazon-tag", "kingtides-21")
    en = read(other, "king-tides")
    assert "tag=kingtides-21" in en and TAG not in en
    assert affiliate_problems(other, "kingtides-21") == []
    assert affiliate_problems(other, TAG) != []


def test_ga4_handler(on: Path, off: Path) -> None:
    src = (Path(affiliate.__file__).parent / "templates" / "_ga4.html.jinja").read_text(encoding="utf-8")
    assert "gear_click" in src and "href" not in src
    en = read(on, "king-tides")
    script = en[en.index("<script>") : en.index("</script>")]
    assert "gear_click" in script and "href" not in script
    guards = script.index("if (optedOut) return;")
    assert guards < script.index("a[data-ga-event]")
    assert "gear_click" not in read(on, "privacy")  # only the page with the links
    assert "gear_click" not in read(off, "king-tides")


@pytest.mark.parametrize("bad", ["UA-1", "TideHours", "x-20 ", "tidehours-20\n", "tidehours", "-20"])
def test_cli_refuses_bad_tags(tmp_path: Path, bad: str) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--out", str(tmp_path), "--amazon-tag", bad])


def test_search_url_refuses_bad_input() -> None:
    assert affiliate.amazon_search_url("rain jacket", TAG) == "https://www.amazon.com/s?k=rain+jacket&tag=tidehours-20"
    with pytest.raises(ValueError):
        affiliate.amazon_search_url("rain jacket", "TideHours")
    with pytest.raises(ValueError):
        affiliate.amazon_search_url(" ", TAG)


def test_block_refuses_too_many_links(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy = json.loads(affiliate.COPY.read_text(encoding="utf-8"))
    copy["links"] = copy["links"] * 2
    path = tmp_path / "affiliate.json"
    path.write_text(json.dumps(copy), encoding="utf-8")
    monkeypatch.setattr(affiliate, "COPY", path)
    with pytest.raises(ValueError):
        affiliate.block(TAG)


def _sabotage(page: Path, old: str, new: str, count: int = 1) -> None:
    html = page.read_text(encoding="utf-8")
    changed = html.replace(old, new, count)
    page.write_text(changed, encoding="utf-8")
    assert page.read_text(encoding="utf-8") != html  # the sabotage applied


@pytest.mark.parametrize(
    ("name", "expect"),
    [
        ("strip-rel", "rel is"),
        ("no-disclosure", "no disclosure before the first amazon link"),
        ("link-on-state-page", "amazon link outside king-tides/"),
        ("untagged", "does not carry tag"),
        ("before-method", "before the end of the method section"),
        ("heading-between", "the disclosure is not next to the links"),
        ("in-sitemap", "sitemap.xml: mentions amazon"),
    ],
)
def test_check_site_catches_affiliate_mistakes(tmp_path: Path, on: Path, name: str, expect: str) -> None:
    """Negative controls: check_site passes the tagged build and fails each sabotage."""
    root = tmp_path / "site"
    shutil.copytree(on, root)
    assert affiliate_problems(root, TAG) == []
    kt = root / "king-tides/index.html"
    if name == "strip-rel":
        _sabotage(kt, ' rel="sponsored nofollow noopener"', "")
    elif name == "no-disclosure":
        _sabotage(kt, affiliate.DISCLOSURE, "")
    elif name == "link-on-state-page":
        state = next(p for p in root.glob("states/*/index.html"))
        _sabotage(state, "</main>", f'<a href="https://www.amazon.com/s?k=boots&amp;tag={TAG}">x</a></main>')
    elif name == "untagged":
        _sabotage(kt, f"&amp;tag={TAG}", "")
    elif name == "before-method":
        block_start = kt.read_text(encoding="utf-8").index('<section class="affiliate"')
        html = kt.read_text(encoding="utf-8")
        block = html[block_start : html.index("</section>", block_start) + len("</section>")]
        moved = html.replace(block, "").replace(
            '<section aria-labelledby="kt-method">', block + '<section aria-labelledby="kt-method">'
        )
        kt.write_text(moved, encoding="utf-8")
        assert moved != html and moved.index(affiliate.DISCLOSURE) < moved.index('id="kt-method"')
    elif name == "heading-between":
        _sabotage(kt, f"{affiliate.DISCLOSURE} ", f"{affiliate.DISCLOSURE} <h2>x</h2> ")
    else:
        _sabotage(root / "sitemap.xml", "</urlset>", "<!-- amazon --></urlset>")
    found = affiliate_problems(root, TAG)
    assert any(expect in p for p in found), found
