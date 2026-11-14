"""IndexNow (src/tidehours/indexnow.py): selection, submission and the publish
workflow, with a fake HTTP client and negative controls. Nothing here touches
the network."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli
from tidehours import indexnow as ix

BASE = "https://example.test"
# Deliberately low-entropy so the secret scanners do not read it as a key; a
# real IndexNow key is public by design anyway.
KEY = "ab" * 16
PAGE = "<html><head><title>t</title></head><body>x</body></html>"
NOINDEX = '<html><head><meta name="robots" content="noindex,follow"></head></html>'
NOW = "2026-11-01T11:20:00Z"
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"


class FakeClient:
    def __init__(self, status: int = 200, raises: Exception | None = None) -> None:
        self.status, self.raises = status, raises
        self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def post_json(self, url: str, body: bytes, headers: Mapping[str, str]) -> int:
        self.calls.append((url, json.loads(body), dict(headers)))
        if self.raises:
            raise self.raises
        return self.status


def _sitemap(urls: list[str]) -> str:
    rows = "\n".join(f"<url><loc>{u}</loc><lastmod>2026-11-01</lastmod></url>" for u in urls)
    return f'<?xml version="1.0"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'


def _manifest(d: Mapping[str, str]) -> str:
    return json.dumps({"schema": 1, "pages": {p: {"fingerprint": f} for p, f in d.items()}})


def _site(tmp_path: Path, pages: Mapping[str, str]) -> Path:
    root = tmp_path / "site"
    for rel, html in pages.items():
        f = root / rel / "index.html" if rel else root / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
    (root / f"{KEY}.txt").write_text(KEY + "\n", encoding="utf-8")
    (root / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    return root


def _select(tmp_path: Path, site: Path, live: str | None, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(ix, "fetch_text", lambda url, missing_is_empty: live)
    out = tmp_path / "urls.json"
    argv = ["select", "--site-dir", str(site), "--base-url", BASE, "--kind", "manifest"]
    assert ix.main([*argv, "--file", "lastmod.json", "--out", str(out)]) == 0
    payload: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return payload


# -- the module ---------------------------------------------------------------


def test_new_and_changed_pages_are_selected_and_unchanged_are_not() -> None:
    prev = {f"{BASE}/a/": "1", f"{BASE}/b/": "1"}
    cur = {f"{BASE}/a/": "1", f"{BASE}/b/": "2", f"{BASE}/c/": "1"}
    assert ix.select_changed(prev, cur) == [f"{BASE}/b/", f"{BASE}/c/"]


def test_an_unreadable_live_site_selects_nothing_but_an_empty_one_selects_all() -> None:
    cur = {f"{BASE}/a/": "1"}
    assert ix.select_changed(None, cur) == []
    assert ix.select_changed({}, cur) == [f"{BASE}/a/"]


def test_filter_drops_noindex_foreign_host_and_unbuilt_pages(tmp_path: Path) -> None:
    site = _site(tmp_path, {"": PAGE, "a": PAGE, "thin": NOINDEX})
    urls = [f"{BASE}/a/", f"{BASE}/thin/", "https://evil.test/a/", f"{BASE}/missing/", "http://example.test/a/"]
    kept, notes = ix.filter_submittable(urls, base_url=BASE, site_dir=site)
    assert kept == [f"{BASE}/a/"]
    assert len(notes) == 4


def test_negative_control_validate_rejects_over_cap_duplicates_and_foreign_hosts(tmp_path: Path) -> None:
    site = _site(tmp_path, {"a": PAGE})
    ix.validate_submission([f"{BASE}/a/"], base_url=BASE, site_dir=site)  # the clean list passes
    over = [f"{BASE}/p{i}/" for i in range(ix.MAX_URLS + 1)]
    with pytest.raises(ix.IndexNowError, match="exceeds"):
        ix.validate_submission(over, base_url=BASE, site_dir=site)
    with pytest.raises(ix.IndexNowError, match="duplicate"):
        ix.validate_submission([f"{BASE}/a/", f"{BASE}/a/"], base_url=BASE, site_dir=site)
    with pytest.raises(ix.IndexNowError, match="not on"):
        ix.validate_submission(["https://evil.test/a/"], base_url=BASE, site_dir=site)


def test_the_key_file_must_exist_once_and_match_its_name(tmp_path: Path) -> None:
    site = _site(tmp_path, {"": PAGE})
    assert ix.find_key(site) == KEY
    (site / f"{KEY}.txt").write_text("wrong\n", encoding="utf-8")
    with pytest.raises(ix.IndexNowError, match="body must equal"):
        ix.find_key(site)
    (site / f"{KEY}.txt").unlink()
    with pytest.raises(ix.IndexNowError, match="exactly one"):
        ix.find_key(site)


def test_submit_posts_the_documented_payload_and_never_raises() -> None:
    payload = ix.build_payload(BASE, KEY, [f"{BASE}/a/"])
    assert payload == {
        "host": "example.test",
        "key": KEY,
        "keyLocation": f"{BASE}/{KEY}.txt",
        "urlList": [f"{BASE}/a/"],
    }
    ok = FakeClient(200)
    assert "accepted 1 URLs" in ix.submit(payload, ok)
    assert ok.calls[0][0] == ix.ENDPOINT
    for client in (FakeClient(403), FakeClient(429), FakeClient(raises=OSError("down"))):
        assert "normal crawl" in ix.submit(payload, client)
        assert client.calls  # the failure path really ran


def test_submit_command_exits_zero_even_when_the_list_is_unreadable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ix.main(["submit", "--list", str(tmp_path / "nope.json")]) == 0
    assert "::notice" in capsys.readouterr().out


def test_select_on_a_manifest_diff_announces_only_changed_sitemap_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = _site(tmp_path, {"": PAGE, "a": PAGE, "b": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/a/", f"{BASE}/b/"]), encoding="utf-8")
    (site / "lastmod.json").write_text(_manifest({"/a/": "x2", "/b/": "y", "/": "z"}), encoding="utf-8")
    payload = _select(tmp_path, site, _manifest({"/a/": "x1", "/b/": "y"}), monkeypatch)
    # "/" changed but is not in the sitemap, so it is not announced.
    assert payload["urlList"] == [f"{BASE}/a/"]
    assert payload["key"] == KEY


def test_select_with_an_unreadable_live_manifest_submits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _site(tmp_path, {"a": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/a/"]), encoding="utf-8")
    (site / "lastmod.json").write_text(_manifest({"/a/": "1"}), encoding="utf-8")
    assert _select(tmp_path, site, None, monkeypatch)["urlList"] == []
    assert "submitting nothing" in capsys.readouterr().out


def test_negative_control_an_unchanged_site_sends_no_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero changed URLs end to end: select finds nothing and submit sends
    nothing. The same site with one changed fingerprint does send, so the
    empty case is not an accident of the fixture."""
    site = _site(tmp_path, {"": PAGE, "a": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/", f"{BASE}/a/"]), encoding="utf-8")
    current = {"/": "h0", "/a/": "h1"}
    (site / "lastmod.json").write_text(_manifest(current), encoding="utf-8")
    same = _select(tmp_path, site, _manifest(current), monkeypatch)
    assert same["urlList"] == []
    quiet = FakeClient()
    assert "nothing to submit" in ix.submit(same, quiet)
    assert quiet.calls == []

    older = {**current, "/a/": "h-old"}
    assert older != current  # the sabotage applied
    changed = _select(tmp_path, site, _manifest(older), monkeypatch)
    assert changed["urlList"] == [f"{BASE}/a/"]
    sent = FakeClient()
    ix.submit(changed, sent)
    assert len(sent.calls) == 1


# -- the real build -----------------------------------------------------------


def _build(out: Path, *extra: str) -> Path:
    assert cli.main(["--out", str(out), "--now", NOW, "--states", "HI", *extra]) == 0
    return out


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build(tmp_path_factory.mktemp("ixsite"))


def test_the_build_carries_one_key_file_and_robots_lets_bingbot_in(built: Path) -> None:
    key = ix.find_key(built)
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert ix.check_robots((built / "robots.txt").read_text(encoding="utf-8"), "https://tidehours.com") == []


def test_a_build_for_another_host_has_no_key_file(tmp_path: Path) -> None:
    other = _build(tmp_path / "other", "--base-url", "http://127.0.0.1:8000/")
    assert not [p for p in other.iterdir() if ix.KEY_FILE_RE.match(p.name)]


def test_the_manifest_covers_exactly_the_sitemap_and_every_url_is_announceable(built: Path) -> None:
    tree = ET.parse(built / "sitemap.xml")  # noqa: S314 - our own build output
    locs = sorted(str(el.text) for el in tree.iter() if el.tag.endswith("loc"))
    tokens = ix.tokens("manifest", (built / "lastmod.json").read_text(encoding="utf-8"), "https://tidehours.com")
    assert sorted(tokens) == locs
    assert len(locs) > 20
    kept, notes = ix.filter_submittable(locs, base_url="https://tidehours.com", site_dir=built)
    assert notes == [] and kept == locs


def test_a_rebuild_of_the_same_day_announces_nothing_and_the_next_day_only_changes(tmp_path: Path) -> None:
    def manifest(day: str) -> dict[str, str]:
        out = tmp_path / day
        assert cli.main(["--out", str(out), "--now", f"{day}T11:20:00Z", "--states", "HI"]) == 0
        return ix.tokens("manifest", (out / "lastmod.json").read_text(encoding="utf-8"), "https://tidehours.com")

    first, again, next_day = manifest("2026-11-01"), manifest("2026-11-01"), manifest("2026-11-02")
    assert ix.select_changed(first, again) == []
    changed = ix.select_changed(first, next_day)
    assert changed, "a new day must change the station pages, or this check proves nothing"
    # Station pages, and since 0039 the region pages, whose rows carry the
    # day's times; nothing else.
    region = re.compile(r"https://tidehours\.com/states/[a-z]+/[^/]+/$")
    assert all("/stations/" in u or region.match(u) for u in changed)
    assert any(region.match(u) for u in changed)
    assert len(changed) < len(next_day)


# -- the workflow --------------------------------------------------------------


def _block(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))] if end else text[i:]


def test_workflow_selects_before_the_deploy_and_submits_in_a_job_after_it() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _block(text, "\n  build:\n", "\n  deploy:\n")
    assert build.index("- name: pick the pages to announce") < build.index("- name: keep the IndexNow list")
    job = _block(text, "\n  indexnow:\n", None)
    assert "    needs: deploy\n" in job
    assert "indexnow.py submit" in job
    assert "indexnow.py submit" not in build
    assert "id-token" not in job and "secrets." not in job and "aws-actions" not in job
    # The standards ban continue-on-error; indexnow.py exits 0 instead.
    code = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    assert not [ln for ln in code if "continue-on-error" in ln]
    # Only the publish workflow calls it, never pull-request CI.
    assert "indexnow" not in (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
