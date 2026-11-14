"""Which day is "today" on a station page.

The site is built once a day at 11:20 UTC, so a page holds the station's date
at that moment and the next. Before dawn on the East Coast, and for most of
the day in Guam, the first of those is already yesterday. The page's script
labels the days from the station's own clock when the page is read, hides the
days that have passed, and says so when today is not on the page at all.
Without the script the headings are plain dates.

The same script then says when the next high or low is (docs/DECISIONS.md
0038). It never computes a tide: it takes the first of the build's own times
after the reader's clock, and marks the times in the answer that have passed.
When it cannot, the build's sentence, which names the date, stays.

These run the page's real inline script under Node with a pinned clock and a
small stand-in for the page's DOM (the sections' dates, the zone, the status
box, the day tables' rows, the answer's times and the next-tide line), so
they test the script that ships, not a copy of it.
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
# "dates", "now", "rows", "evs", "next", "untils"} on stdin, prints each
# section's label and visibility, the status box, the next-tide line and
# which of the answer's times were marked as passed. `new Date()` with no
# argument is the pinned clock.
HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const RealDate = Date;
const pinned = RealDate.parse(input.now);
class PinnedDate extends RealDate {
  constructor(...a) { if (a.length === 0) super(pinned); else super(...a); }
  static now() { return pinned; }
}
const text = (n) => (typeof n === "string" ? n : n.textContent);
function element(tag) {
  const el = {
    tag, className: "", children: [],
    get textContent() { return this.children.length ? this.children.map(text).join("") : this._text || ""; },
    set textContent(v) { this.children = []; this._text = v; },
    append(...nodes) { this._text = ""; this.children.push(...nodes); },
  };
  return el;
}
const time = (iso, t) => ({ getAttribute: (n) => (n === "datetime" ? iso : null), textContent: t });
const sections = input.dates.map((d) => ({
  hidden: false,
  label: { textContent: "" },
  getAttribute: (n) => (n === "data-date" ? d : null),
  querySelector: (q) => (q === ".day-label" ? sections.find((s) => s.date === d).label : null),
  date: d,
}));
const rows = input.rows.map((r) => ({
  className: r.cls,
  querySelector: (q) => (q === "time" ? time(r.iso, r.time) : null),
  cells: [null, null, { firstChild: { textContent: r.ft } }],
}));
const evs = input.evs.map((iso) => {
  const classes = new Set();
  const ev = {
    iso, said: "",
    classList: { contains: (c) => classes.has(c), add: (c) => classes.add(c) },
    querySelector: (q) => (q === "time" ? time(iso, "") : null),
    firstChild: {},
    insertBefore(node, ref) { if (ref === ev.firstChild) ev.said = node.className + ":" + text(node); },
    get past() { return classes.has("past"); },
  };
  return ev;
});
const next = element("p");
next.textContent = input.next;
const stale = { hidden: true, textContent: "" };
const main = { getAttribute: (n) => (n === "data-tz" ? input.tz : null) };
const document = {
  getElementById: (id) => (id === "main" ? main : id === "stale" ? stale : id === "next" ? next : null),
  querySelectorAll: (q) =>
    q === "section.day[data-date]" ? sections
    : q === "section.day tr.ev-high, section.day tr.ev-low" ? rows
    : q === ".answer .ev" ? evs
    : [],
  createElement: element,
};
const context = { document, Date: PinnedDate, Intl };
vm.runInNewContext(input.script, context);
const kind = next.children.find((c) => typeof c !== "string" && c.tag === "span" && c.className.startsWith("kind"));
process.stdout.write(JSON.stringify({
  days: sections.map((s) => ({ date: s.date, hidden: s.hidden, label: s.label.textContent })),
  stale: stale.hidden ? null : stale.textContent,
  next: next.textContent,
  kind: kind ? kind.className : null,
  past: evs.filter((e) => e.past).map((e) => e.iso),
  said: [...new Set(evs.filter((e) => e.past).map((e) => e.said))],
  untils: (input.untils || []).map((ms) => context.tidehoursNext.until(ms)),
}));
"""

SECTION = re.compile(r'<section class="day"[^>]*data-date="(\d{4}-\d{2}-\d{2})"')
TZ = re.compile(r'<main id="main"[^>]*data-tz="([^"]+)"')
SCRIPT = re.compile(r"<script>\s*(// The page is built once a day.*?)</script>", re.S)
ROW = re.compile(
    r'<tr class="(ev-high|ev-low)"><th scope="row">\w+</th><td><time datetime="([^"]+)">([^<]+)</time></td>'
    r"<td>([^<]*)<span"
)
EV = re.compile(r'<span class="ev"><strong><time datetime="([^"]+)">')
NEXT = re.compile(r'<p class="next" id="next">([^<]*)</p>')
NBSP = " "


def node() -> str:
    # Not a skip: a missing Node would make every test here pass silently.
    # CI installs it (ci.yml, tools/site-checks/.nvmrc).
    found = shutil.which("node")
    assert found, "these tests need Node on PATH (Node 22+, see tools/site-checks/.nvmrc)"
    return found


def build(tmp_path: Path, states: str, now: str = BUILT) -> Path:
    assert cli.main(["--out", str(tmp_path), "--now", now, "--states", states]) == 0
    return tmp_path


def run(
    html: str, now: str, tz: str | None = None, dates: list[str] | None = None, untils: list[int] | None = None
) -> dict[str, Any]:
    script = SCRIPT.search(html)
    zone = TZ.search(html)
    line = NEXT.search(html)
    assert script and zone and line
    payload = {
        "script": script.group(1),
        "tz": tz or zone.group(1),
        "dates": dates or SECTION.findall(html),
        "now": now,
        "rows": [{"cls": c, "iso": iso, "time": t, "ft": ft} for c, iso, t, ft in ROW.findall(html)],
        "evs": EV.findall(html),
        "next": line.group(1),
        "untils": untils or [],
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
    out = build(tmp_path_factory.mktemp("guam"), "GU")  # Apra Harbor is GU (DECISIONS 0018)
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


# The next tide (docs/DECISIONS.md 0038). The Battery's page built at 11:20
# UTC on Nov 4: highs 3:59 AM (4.9 ft) and 4:17 PM, lows 10:18 AM (0.6 ft) and
# 10:47 PM on Nov 4; high 4:56 AM (5.1 ft) first on Nov 5; last, a low at
# 11:33 PM on Nov 5. New York is UTC-5 in November.
BUILT_LINE = "Wednesday, Nov 4, in order: high 3:59 AM, low 10:18 AM, high 4:17 PM, low 10:47 PM."
PASSED = ["vh:passed: "]


def test_next_tide_without_script_is_the_build_sentence(battery: str) -> None:
    line = NEXT.search(battery)
    assert line and line.group(1) == BUILT_LINE
    answer = battery.index('<div class="answer">')
    assert answer < battery.index('<p class="next" id="next">') < battery.index('id="q-high"')
    assert len(ROW.findall(battery)) == 8 and len(EV.findall(battery)) == 8


def test_next_tide_before_the_first_tide(battery: str) -> None:
    r = run(battery, "2026-11-04T08:00:00Z")  # 3:00 AM
    assert r["next"] == f"Next high tide: 3:59 AM (4.9 ft), in 59{NBSP}min. The predicted tide is rising until then."
    assert r["kind"] == "kind ev-high"
    assert r["past"] == []


def test_next_tide_between_tides(battery: str) -> None:
    r = run(battery, "2026-11-04T14:00:00Z")  # 9:00 AM, after the 3:59 AM high
    assert r["next"] == (
        f"Next low tide: 10:18 AM (0.6 ft), in 1{NBSP}h{NBSP}18{NBSP}min. The predicted tide is falling until then."
    )
    assert r["kind"] == "kind ev-low"
    assert r["past"] == ["2026-11-04T03:59-05:00"] and r["said"] == PASSED
    # At the minute of a tide, that one has passed and the next is named.
    r = run(battery, "2026-11-04T15:18:00Z")
    assert r["next"].startswith(f"Next high tide: 4:17 PM (4.8 ft), in 5{NBSP}h{NBSP}59{NBSP}min.")
    assert r["past"] == ["2026-11-04T03:59-05:00", "2026-11-04T10:18-05:00"]


def test_next_tide_after_todays_last_is_tomorrows(battery: str) -> None:
    r = run(battery, "2026-11-05T04:00:00Z")  # 11:00 PM on Nov 4
    assert r["next"] == (
        f"Next high tide: 4:56 AM tomorrow (5.1 ft), in 5{NBSP}h{NBSP}56{NBSP}min. The predicted tide is rising until then."
    )
    assert sorted(r["past"]) == sorted(
        ["2026-11-04T03:59-05:00", "2026-11-04T16:17-05:00", "2026-11-04T10:18-05:00", "2026-11-04T22:47-05:00"]
    )


def test_next_tide_keeps_the_build_sentence_when_every_tide_has_passed(battery: str) -> None:
    r = run(battery, "2026-11-06T04:40:00Z")  # 11:40 PM on Nov 5, after its last low
    assert shown(r) == [("2026-11-05", "Today, ")]
    assert r["next"] == BUILT_LINE and r["kind"] is None
    assert r["past"] == []  # nothing is changed when there is no next tide to name


def test_next_tide_after_a_missed_build_keeps_the_build_sentence(battery: str, guam: str) -> None:
    r = run(battery, "2026-11-07T15:00:00Z")
    assert r["stale"] is not None and r["next"] == BUILT_LINE
    g = run(guam, "2026-11-06T08:41:00Z")
    assert g["stale"] is not None and g["next"] == NEXT.search(guam).group(1)  # type: ignore[union-attr]
    # A clock a day behind the build: the page's first day is the station's
    # tomorrow, and its first tide is named as tomorrow's.
    r = run(battery, "2026-11-03T12:00:00Z")  # 7:00 AM on Nov 3
    assert r["next"].startswith(f"Next high tide: 3:59 AM tomorrow (4.9 ft), in 20{NBSP}h{NBSP}59{NBSP}min.")
    # Two days behind: the next tide is not today's or tomorrow's.
    assert run(battery, "2026-11-02T12:00:00Z")["next"] == BUILT_LINE


def test_next_tide_with_an_unknown_zone_keeps_the_build_sentence(battery: str) -> None:
    r = run(battery, "2026-11-04T14:00:00Z", tz="Not/AZone")
    assert r["next"] == BUILT_LINE and r["past"] == []


@pytest.fixture(scope="module")
def fall_back(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = build(tmp_path_factory.mktemp("ny-dst"), "NY", "2026-11-01T11:20:00Z")
    return (out / "stations/8518750/index.html").read_text(encoding="utf-8")


def test_next_tide_on_a_daylight_saving_day(fall_back: str) -> None:
    # Nov 1, 2026: 2:00 AM EDT becomes 1:00 AM EST. At 1:56 AM EDT (05:56 UTC),
    # after the 1:55 AM EDT high, the next tide is the 6:53 AM EST low: 5 h 57
    # min away by the clock that runs, though the wall clock says 4 h 57.
    assert '<time datetime="2026-11-01T01:55-04:00">' in fall_back
    assert '<time datetime="2026-11-01T06:53-05:00">6:53 AM</time></td><td>0.8 ft' in fall_back
    r = run(fall_back, "2026-11-01T05:56:00Z")
    assert shown(r)[0] == ("2026-11-01", "Today, ")
    assert r["next"] == (
        f"Next low tide: 6:53 AM (0.8 ft), in 5{NBSP}h{NBSP}57{NBSP}min. The predicted tide is falling until then."
    )
    assert r["past"] == ["2026-11-01T01:55-04:00"]


def test_until_says_hours_and_minutes(battery: str) -> None:
    r = run(battery, "2026-11-04T14:00:00Z", untils=[1, 29_999, 60_000, 3_600_000, 3_660_000, 89_999, 7_200_000 - 1])
    assert r["untils"] == [
        f"1{NBSP}min",
        f"1{NBSP}min",
        f"1{NBSP}min",
        f"1{NBSP}h",
        f"1{NBSP}h{NBSP}1{NBSP}min",
        f"1{NBSP}min",
        f"2{NBSP}h",
    ]
