"""Which day is "today" on a station page.

The site is built once a day at 11:20 UTC, so a page holds the station's date
at that moment and the next. Before dawn on the East Coast, and for most of
the day in Guam, the first of those is already yesterday. The page's script
labels the days from the station's own clock when the page is read, hides the
days that have passed, and says so when today is not on the page at all.
Without the script the headings are plain dates.

These run the page's real inline script under Node with a pinned clock and a
small stand-in for the page's DOM (the sections' dates, the zone, the status
box), so they test the script that ships, not a copy of it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tidehours import cli

BUILT = "2026-11-04T11:20:00Z"  # the daily build's time of day

# Runs the page script against a stand-in DOM. Reads {"script", "tz",
# "dates", "now"} on stdin, prints each section's label and visibility and the
# status box. `new Date()` with no argument is the pinned clock.
HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const RealDate = Date;
const pinned = RealDate.parse(input.now);
class PinnedDate extends RealDate {
  constructor(...a) { if (a.length === 0) super(pinned); else super(...a); }
  static now() { return pinned; }
}
const sections = input.dates.map((d) => ({
  hidden: false,
  label: { textContent: "" },
  getAttribute: (n) => (n === "data-date" ? d : null),
  querySelector: (q) => (q === ".day-label" ? sections.find((s) => s.date === d).label : null),
  date: d,
}));
const stale = { hidden: true, textContent: "" };
const main = { getAttribute: (n) => (n === "data-tz" ? input.tz : null) };
const document = {
  getElementById: (id) => (id === "main" ? main : id === "stale" ? stale : null),
  querySelectorAll: (q) => (q === "section.day[data-date]" ? sections : []),
};
vm.runInNewContext(input.script, { document, Date: PinnedDate, Intl });
process.stdout.write(JSON.stringify({
  days: sections.map((s) => ({ date: s.date, hidden: s.hidden, label: s.label.textContent })),
  stale: stale.hidden ? null : stale.textContent,
}));
"""

SECTION = re.compile(r'<section class="day"[^>]*data-date="(\d{4}-\d{2}-\d{2})"')
TZ = re.compile(r'<main id="main"[^>]*data-tz="([^"]+)"')
SCRIPT = re.compile(r"<script>\s*(// The page is built once a day.*?)</script>", re.S)


def node() -> str:
    # Not a skip: a missing Node would make every test here pass silently.
    # CI installs it (ci.yml, tools/site-checks/.nvmrc).
    found = shutil.which("node")
    assert found, "these tests need Node on PATH (Node 22+, see tools/site-checks/.nvmrc)"
    return found


def build(tmp_path: Path, states: str, now: str = BUILT) -> Path:
    assert cli.main(["--out", str(tmp_path), "--now", now, "--states", states]) == 0
    return tmp_path


def run(html: str, now: str, tz: str | None = None, dates: list[str] | None = None) -> dict[str, Any]:
    script = SCRIPT.search(html)
    zone = TZ.search(html)
    assert script and zone
    payload = {
        "script": script.group(1),
        "tz": tz or zone.group(1),
        "dates": dates or SECTION.findall(html),
        "now": now,
    }
    out = subprocess.run(  # noqa: S603 - our own harness, fixed arguments
        [node(), "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, check=True, timeout=60
    )
    result: dict[str, Any] = json.loads(out.stdout)
    return result


def shown(result: dict[str, Any]) -> list[tuple[str, str]]:
    return [(d["date"], d["label"]) for d in result["days"] if not d["hidden"]]


@pytest.fixture(scope="module")
def battery(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = build(tmp_path_factory.mktemp("ny"), "NY")
    return (out / "stations/8518750/index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def guam(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = build(tmp_path_factory.mktemp("other"), "other")
    return (out / "stations/1630000/index.html").read_text(encoding="utf-8")


def test_headings_without_script_are_plain_dates(battery: str) -> None:
    headings = re.findall(r'<h2 id="day-\d">(.*?)</h2>', battery)
    assert len(headings) == 2 and not any("Today" in h or "Tomorrow" in h for h in headings)
    assert SECTION.findall(battery) == ["2026-11-04", "2026-11-05"]
    assert '<span class="day-label"></span><time datetime="2026-11-04">Wednesday, November 4, 2026</time>' in battery
    assert "Thursday, November 5, 2026</time>" in battery


def test_east_coast_after_the_build(battery: str) -> None:
    # 9:00 AM EST on Nov 4: the page's first day is today.
    r = run(battery, "2026-11-04T14:00:00Z")
    assert shown(r) == [("2026-11-04", "Today, "), ("2026-11-05", "Tomorrow, ")]
    assert r["stale"] is None


def test_east_coast_before_dawn(battery: str) -> None:
    # 3:41 AM EST on Nov 5, before the next build: Nov 4 has passed, and Nov 5
    # is today, not "Tomorrow". This is what the live site got wrong.
    r = run(battery, "2026-11-05T08:41:00Z")
    assert shown(r) == [("2026-11-05", "Today, ")]
    assert r["stale"] is None
    # One minute before midnight on Nov 4 the page is still right as built.
    assert shown(run(battery, "2026-11-05T04:59:00Z")) == [("2026-11-04", "Today, "), ("2026-11-05", "Tomorrow, ")]
    assert shown(run(battery, "2026-11-05T05:00:00Z")) == [("2026-11-05", "Today, ")]


def test_guam_most_of_the_day(guam: str) -> None:
    # Guam is UTC+10. Built at 21:20 on Nov 4 local, so from midnight Nov 5
    # local (14:00 UTC Nov 4) until the next build, Nov 5 is today.
    assert SECTION.findall(guam) == ["2026-11-04", "2026-11-05"]
    assert shown(run(guam, "2026-11-04T13:59:00Z")) == [("2026-11-04", "Today, "), ("2026-11-05", "Tomorrow, ")]
    r = run(guam, "2026-11-05T08:41:00Z")  # 18:41 on Nov 5 in Guam
    assert shown(r) == [("2026-11-05", "Today, ")]
    assert r["stale"] is None


def test_missed_build_says_so_instead_of_mislabeling(guam: str, battery: str) -> None:
    # The daily build failed: two days later neither day on the page is today.
    r = run(guam, "2026-11-06T08:41:00Z")  # 18:41 on Nov 6 in Guam
    assert shown(r) == []
    assert r["stale"] == (
        "Today, Friday, November 6, 2026, is not on this page yet. It has Wednesday, November 4, 2026 "
        "and Thursday, November 5, 2026, which have passed. The site updates once a day; NOAA's own "
        "predictions for this station are linked below."
    )
    assert "noaatidepredictions.html?id=1630000" in guam
    # A clock behind the build: the days are ahead, so nothing is hidden and
    # nothing is called today.
    r = run(battery, "2026-11-03T12:00:00Z")
    assert shown(r) == [("2026-11-04", "Tomorrow, "), ("2026-11-05", "")]
    assert r["stale"] is not None and "Tuesday, November 3, 2026, is not on this page" in r["stale"]
    assert "passed" not in r["stale"]


def test_daylight_saving_days(battery: str) -> None:
    # Spring forward, 2027-03-14 at 2:00 AM in New York: midnight is 05:00 UTC
    # (still EST), and the next midnight is 04:00 UTC (EDT).
    spring = ["2027-03-14", "2027-03-15"]
    assert shown(run(battery, "2027-03-14T04:59:00Z", dates=spring)) == [
        ("2027-03-14", "Tomorrow, "),
        ("2027-03-15", ""),
    ]
    assert shown(run(battery, "2027-03-14T05:00:00Z", dates=spring)) == [
        ("2027-03-14", "Today, "),
        ("2027-03-15", "Tomorrow, "),
    ]
    assert shown(run(battery, "2027-03-15T03:59:00Z", dates=spring))[0] == ("2027-03-14", "Today, ")
    assert shown(run(battery, "2027-03-15T04:00:00Z", dates=spring)) == [("2027-03-15", "Today, ")]
    # Fall back, 2026-11-01: midnight Nov 1 is 04:00 UTC (EDT), midnight
    # Nov 2 is 05:00 UTC (EST), a 25-hour day.
    fall = ["2026-11-01", "2026-11-02"]
    assert shown(run(battery, "2026-11-01T03:59:00Z", dates=fall))[0] == ("2026-11-01", "Tomorrow, ")
    assert shown(run(battery, "2026-11-02T04:59:00Z", dates=fall))[0] == ("2026-11-01", "Today, ")
    assert shown(run(battery, "2026-11-02T05:00:00Z", dates=fall)) == [("2026-11-02", "Today, ")]


def test_unknown_zone_leaves_the_plain_dates(battery: str) -> None:
    r = run(battery, "2026-11-05T08:41:00Z", tz="Not/AZone")
    assert shown(r) == [("2026-11-04", ""), ("2026-11-05", "")]
    assert r["stale"] is None
