"""Fetch the U.S. Naval Observatory's sun and moon for the sky fixture,
tests/fixtures/usno-sky-2026.json, the oracle for tests/test_sky.py
(docs/DECISIONS.md 0019). Network; run by hand.

    uv run python scripts/fetch_sky.py

For SKY_STATIONS on SKY_DATES, plus the polar edges at Prudhoe Bay: USNO's
`api/rstt/oneday` sunrise, sunset, start and end of civil twilight, moonrise,
moonset, phase name, share lit and nearest primary phase. The offset sent is
the station's UTC offset at local noon, with dst=false, so each time in the
fixture is unambiguous; the tests convert it to an instant. Days already in
the fixture with every field are kept, not fetched again.

aa.usno.navy.mil has no robots.txt (404, checked 2026-11-05 and 2026-11-12).
USNO's API documentation asks callers to name themselves with `ID=`; requests
do, carry a User-Agent that names the site, and are spaced a second apart.
USNO's values are a test oracle only: the site never shows them.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tidehours.catalog import load

ROOT = Path(__file__).resolve().parent.parent
USNO = "https://aa.usno.navy.mil/api/rstt/oneday"
SKY_OUT = ROOT / "tests" / "fixtures" / "usno-sky-2026.json"
USER_AGENT = "tidehours-web test fixture (https://tidehours.com; run by hand)"
USNO_ID = "tidehours"
# Every time zone in the catalog, both hemispheres, the Arctic, and a western
# Aleutian station across the date line (DECISIONS 0018).
SKY_STATIONS = [
    "9414290", "9447130", "8443970", "8518750", "8665530", "8410140", "8724580", "8729840",
    "8771450", "9759110", "9751639", "1612340", "1630000", "1770000", "1890000", "9461380",
    "TWC2309", "9451600", "9455920", "9468756", "9491094", "9497645",
]  # fmt: skip
# The end and start of US daylight saving time, a new moon, a full moon, and
# both solstices.
SKY_DATES = ["2026-11-01", "2026-11-05", "2026-11-09", "2026-11-24", "2026-12-21", "2027-03-14", "2027-06-21"]
# Prudhoe Bay: the last sunrises before polar night, the first after it, and
# the edges of the midnight sun.
PRUDHOE = "9497645"
PRUDHOE_DATES = [
    "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22",
    "2026-11-23", "2027-01-17", "2027-01-18",
    "2027-01-19", "2027-01-20", "2027-01-21", "2027-01-22", "2027-01-23", "2027-01-24", "2027-01-25",
    "2027-05-09", "2027-05-10", "2027-05-11", "2027-05-12", "2027-05-13", "2027-05-14", "2027-05-15", "2027-05-16",
    "2027-07-28", "2027-07-29", "2027-07-30", "2027-07-31", "2027-08-01", "2027-08-02", "2027-08-03",
]  # fmt: skip
FIELDS = ("tz", "sundata", "moondata", "curphase", "fracillum", "closestphase")


def usno_day(lat: float, lon: float, date: str, offset_h: float) -> dict[str, Any]:
    q = urllib.parse.urlencode(
        {"date": date, "coords": f"{lat:.5f},{lon:.5f}", "tz": f"{offset_h:g}", "dst": "false", "ID": USNO_ID}
    )
    req = urllib.request.Request(f"{USNO}?{q}", headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
        data: dict[str, Any] = json.load(res)["properties"]["data"]
    return {
        "tz": offset_h,
        # Transits are left out: the site does not show them.
        "sundata": [s for s in data["sundata"] if s["phen"] != "Upper Transit"],
        "moondata": [s for s in data.get("moondata", []) if s["phen"] != "Upper Transit"],
        "curphase": data["curphase"],
        "fracillum": data["fracillum"],
        "closestphase": data["closestphase"],
    }


def main() -> int:
    cat = load()
    out: dict[str, Any] = {"stations": {}}
    if SKY_OUT.exists():
        out = json.loads(SKY_OUT.read_text(encoding="utf-8"))
    out["source"] = "U.S. Naval Observatory Astronomical Applications Department, one-day rise, set and transit data (rstt/oneday, dst=false)"
    jobs = [(sid, d) for sid in SKY_STATIONS for d in SKY_DATES] + [(PRUDHOE, d) for d in PRUDHOE_DATES]
    fetched = 0
    for sid, d in jobs:
        have = out["stations"].get(sid, {}).get("days", {}).get(d, {})
        if all(k in have for k in FIELDS):
            continue
        st = cat.station(sid)
        assert st is not None  # noqa: S101
        noon = dt.datetime.combine(dt.date.fromisoformat(d), dt.time(12), ZoneInfo(st.tz))
        offset = noon.utcoffset()
        assert offset is not None  # noqa: S101
        entry = out["stations"].setdefault(sid, {"label": st.display_name, "lat": st.lat, "lon": st.lon, "days": {}})
        entry["days"][d] = usno_day(st.lat, st.lon, d, offset.total_seconds() / 3600)
        fetched += 1
        print(f"{sid} {d}", flush=True)
        time.sleep(1)
    if fetched:
        out["retrieved"] = dt.date.today().isoformat()
    SKY_OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SKY_OUT}: {len(jobs)} station-days, {fetched} fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
